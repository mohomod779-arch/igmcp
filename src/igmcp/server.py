"""ASGI app: MCP over Streamable HTTP, mandatory bearer auth, health and metrics."""

from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from igmcp.config import Settings
from igmcp.errors import GraphError
from igmcp.graph.client import GraphClient
from igmcp.tools import register_tools

log = structlog.get_logger()
OPEN_PATHS = frozenset({"/healthz", "/readyz"})


class BearerAuth:
    """Pure ASGI middleware. Everything except the probe paths needs the bearer token."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self._token = token.encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in OPEN_PATHS:
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        supplied = headers.get(b"authorization", b"")
        scheme, _, value = supplied.partition(b" ")
        if scheme.lower() != b"bearer" or not hmac.compare_digest(value.strip(), self._token):
            log.warning("auth_rejected", path=scope["path"])
            resp = JSONResponse(
                {"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"}
            )
            await resp(scope, receive, send)
            return
        await self.app(scope, receive, send)


def create_app(settings: Settings, client: GraphClient | None = None) -> Starlette:
    graph = client or GraphClient(settings)
    mcp = FastMCP(
        "instagram",
        instructions="Read-only access to one Instagram professional account via the Graph API.",
        host=settings.host,
        port=settings.port,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=settings.allowed_host_list,
            allowed_origins=[],
        ),
    )
    register_tools(mcp, graph)
    app = mcp.streamable_http_app()

    async def healthz(_: Request) -> Response:
        return JSONResponse({"status": "ok"})

    async def readyz(_: Request) -> Response:
        try:
            await graph.ready()
        except GraphError as exc:
            return JSONResponse({"status": "degraded", "reason": type(exc).__name__}, 503)
        return JSONResponse({"status": "ready"})

    async def metrics(_: Request) -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.add_route("/healthz", healthz)
    app.add_route("/readyz", readyz)
    app.add_route("/metrics", metrics)

    inner = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(a: Starlette) -> AsyncIterator[None]:
        async with inner(a):
            try:
                yield
            finally:
                await graph.aclose()

    app.router.lifespan_context = lifespan
    app.add_middleware(BearerAuth, token=settings.mcp_auth_token.get_secret_value())
    return app
