"""The only module that talks to Meta. GET-only by construction."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

import httpx
import structlog

from igmcp.config import Settings
from igmcp.errors import (
    AuthError,
    GraphError,
    NotFound,
    PermissionDenied,
    RateLimited,
    UpstreamError,
)
from igmcp.graph.models import (
    Comment,
    CommentPage,
    Insights,
    InsightValue,
    Media,
    MediaPage,
    Profile,
)
from igmcp.metrics import APP_USAGE_PCT, GRAPH_LATENCY, GRAPH_REQUESTS

log = structlog.get_logger()

_RATE_CODES = {4, 17, 32, 613}
_ID_RE = re.compile(r"^\d{5,25}$")
_METRIC_RE = re.compile(r"^[a-z_]{2,64}$")
PROFILE_FIELDS = (
    "id,username,name,biography,website,followers_count,follows_count,"
    "media_count,profile_picture_url"
)
MEDIA_FIELDS = (
    "id,media_type,media_product_type,caption,permalink,timestamp,"
    "like_count,comments_count,thumbnail_url"
)
COMMENT_FIELDS = "id,text,username,timestamp,like_count"


def _classify(status: int, body: Any) -> GraphError:
    err = body.get("error", {}) if isinstance(body, dict) else {}
    code = err.get("code") if isinstance(err.get("code"), int) else None
    msg = str(err.get("message") or f"Graph API HTTP {status}")[:300]
    if status == 401 or code == 190:
        return AuthError(msg, status=status, code=code)
    if code in _RATE_CODES or status == 429:
        return RateLimited(msg, status=status, code=code)
    if status == 404 or code == 100 and "does not exist" in msg:
        return NotFound(msg, status=status, code=code)
    if status == 403 or code == 10 or (code is not None and 200 <= code <= 299):
        return PermissionDenied(msg, status=status, code=code)
    if status >= 500:
        return UpstreamError(msg, status=status, code=code)
    return GraphError(msg, status=status, code=code)


def _check_id(value: str, what: str) -> str:
    if not _ID_RE.match(value):
        raise ValueError(f"invalid {what}")
    return value


class GraphClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._s = settings
        self._http = httpx.AsyncClient(
            base_url=f"{settings.graph_base_url}/{settings.graph_version}",
            headers={
                "Authorization": f"Bearer {settings.ig_graph_token.get_secret_value()}",
                "Accept": "application/json",
            },
            timeout=settings.http_timeout_s,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str, kind: str, params: dict[str, Any] | None = None) -> Any:
        last: GraphError | None = None
        for attempt in range(self._s.http_max_attempts):
            started = time.monotonic()
            try:
                resp = await self._http.get(path, params=params)
            except httpx.TransportError as exc:
                last = UpstreamError(f"network error: {type(exc).__name__}")
                GRAPH_REQUESTS.labels(kind, "network_error").inc()
            else:
                GRAPH_LATENCY.labels(kind).observe(time.monotonic() - started)
                self._record_usage(resp)
                body = self._json(resp)
                if resp.is_success and body is not None:
                    GRAPH_REQUESTS.labels(kind, "ok").inc()
                    return body
                last = _classify(resp.status_code, body)
                GRAPH_REQUESTS.labels(kind, type(last).__name__).inc()
                if not isinstance(last, UpstreamError):
                    raise last
            if attempt + 1 < self._s.http_max_attempts:
                await asyncio.sleep(0.5 * 2**attempt)
        assert last is not None
        log.warning("graph_request_failed", kind=kind, error=str(last))
        raise last

    @staticmethod
    def _json(resp: httpx.Response) -> Any:
        try:
            return resp.json()
        except ValueError:
            return None

    @staticmethod
    def _record_usage(resp: httpx.Response) -> None:
        raw = resp.headers.get("x-app-usage")
        if not raw:
            return
        match = re.search(r'"call_volume"\s*:\s*(\d+)', raw)
        if match:
            APP_USAGE_PCT.set(int(match.group(1)))

    def _limit(self, limit: int) -> int:
        return max(1, min(limit, self._s.max_page_size))

    async def ready(self) -> None:
        await self._get(f"/{self._s.instagram_account_id}", "ready", {"fields": "id"})

    async def profile(self) -> Profile:
        data = await self._get(
            f"/{self._s.instagram_account_id}", "profile", {"fields": PROFILE_FIELDS}
        )
        return Profile.model_validate(data)

    async def list_media(self, limit: int = 12, after: str | None = None) -> MediaPage:
        params: dict[str, Any] = {"fields": MEDIA_FIELDS, "limit": self._limit(limit)}
        if after:
            params["after"] = after
        data = await self._get(f"/{self._s.instagram_account_id}/media", "media_list", params)
        return MediaPage(
            items=[Media.model_validate(i) for i in data.get("data", [])],
            next_cursor=data.get("paging", {}).get("cursors", {}).get("after")
            if "next" in data.get("paging", {})
            else None,
        )

    async def media(self, media_id: str) -> Media:
        data = await self._get(
            f"/{_check_id(media_id, 'media_id')}", "media", {"fields": MEDIA_FIELDS}
        )
        return Media.model_validate(data)

    async def comments(
        self, media_id: str, limit: int = 25, after: str | None = None
    ) -> CommentPage:
        params: dict[str, Any] = {
            "fields": f"{COMMENT_FIELDS},replies{{{COMMENT_FIELDS}}}",
            "limit": self._limit(limit),
        }
        if after:
            params["after"] = after
        data = await self._get(f"/{_check_id(media_id, 'media_id')}/comments", "comments", params)
        items = []
        for raw in data.get("data", []):
            replies = [Comment.model_validate(r) for r in raw.pop("replies", {}).get("data", [])]
            items.append(Comment.model_validate({**raw, "replies": replies}))
        paging = data.get("paging", {})
        return CommentPage(
            items=items,
            next_cursor=paging.get("cursors", {}).get("after") if "next" in paging else None,
        )

    async def insights(
        self,
        metrics: list[str],
        period: str = "day",
        media_id: str | None = None,
        metric_type: str | None = None,
    ) -> Insights:
        if not metrics or len(metrics) > 10 or not all(_METRIC_RE.match(m) for m in metrics):
            raise ValueError("metrics must be 1-10 names like 'reach' or 'total_interactions'")
        if period not in {"day", "week", "days_28", "lifetime"}:
            raise ValueError("period must be day, week, days_28 or lifetime")
        params: dict[str, Any] = {"metric": ",".join(metrics), "period": period}
        if metric_type:
            if metric_type not in {"total_value", "time_series"}:
                raise ValueError("metric_type must be total_value or time_series")
            params["metric_type"] = metric_type
        target = _check_id(media_id, "media_id") if media_id else self._s.instagram_account_id
        data = await self._get(f"/{target}/insights", "insights", params)
        items = []
        for raw in data.get("data", []):
            total = raw.get("total_value", {}).get("value")
            values = raw.get("values", [])
            single = values[0].get("value") if len(values) == 1 else None
            items.append(
                InsightValue(
                    name=raw.get("name", ""),
                    period=raw.get("period"),
                    title=raw.get("title"),
                    value=total if total is not None else single,
                    values=values if len(values) > 1 else [],
                )
            )
        return Insights(items=items)
