"""MCP tool layer: thin, typed, read-only. Failures become short safe messages."""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypeVar

import structlog
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from igmcp.errors import GraphError
from igmcp.graph.client import GraphClient
from igmcp.graph.models import CommentPage, Insights, Media, MediaPage, Profile
from igmcp.metrics import TOOL_CALLS

log = structlog.get_logger()
T = TypeVar("T")
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)


def _guard(name: str) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    def deco(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                result = await fn(*args, **kwargs)
            except ValueError as exc:
                TOOL_CALLS.labels(name, "invalid_input").inc()
                raise ValueError(str(exc)) from None
            except GraphError as exc:
                TOOL_CALLS.labels(name, type(exc).__name__).inc()
                log.warning("tool_failed", tool=name, error_type=type(exc).__name__)
                raise RuntimeError(f"{type(exc).__name__}: {exc}") from None
            TOOL_CALLS.labels(name, "ok").inc()
            return result

        return wrapper

    return deco


MediaId = Annotated[str, Field(description="Instagram media id (digits only)")]
Cursor = Annotated[str | None, Field(description="next_cursor from the previous page")]


def register_tools(mcp: FastMCP, client: GraphClient) -> None:
    @mcp.tool(annotations=READ_ONLY)
    @_guard("get_instagram_profile")
    async def get_instagram_profile() -> Profile:
        """Profile of the connected professional account: bio, counts, website."""
        return await client.profile()

    @mcp.tool(annotations=READ_ONLY)
    @_guard("list_instagram_media")
    async def list_instagram_media(
        limit: Annotated[int, Field(ge=1, le=100)] = 12, after: Cursor = None
    ) -> MediaPage:
        """Recent posts, reels and carousels, newest first, with a cursor for the next page."""
        return await client.list_media(limit, after)

    @mcp.tool(annotations=READ_ONLY)
    @_guard("get_instagram_media")
    async def get_instagram_media(media_id: MediaId) -> Media:
        """Details of one media item: caption, permalink, counts."""
        return await client.media(media_id)

    @mcp.tool(annotations=READ_ONLY)
    @_guard("get_instagram_comments")
    async def get_instagram_comments(
        media_id: MediaId,
        limit: Annotated[int, Field(ge=1, le=100)] = 25,
        after: Cursor = None,
    ) -> CommentPage:
        """Top-level comments on a media item, each with its replies."""
        return await client.comments(media_id, limit, after)

    @mcp.tool(annotations=READ_ONLY)
    @_guard("get_instagram_insights")
    async def get_instagram_insights(
        metrics: Annotated[
            list[str], Field(description="e.g. ['reach','views'] or ['likes','shares'] for media")
        ],
        period: Annotated[str, Field(description="day | week | days_28 | lifetime")] = "day",
        media_id: Annotated[
            str | None, Field(description="Omit for account-level insights")
        ] = None,
        metric_type: Annotated[
            str | None, Field(description="total_value | time_series (account-level)")
        ] = None,
    ) -> Insights:
        """Account-level or per-media insights. Metric availability depends on media type."""
        return await client.insights(metrics, period, media_id, metric_type)
