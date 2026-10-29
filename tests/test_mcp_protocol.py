from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from igmcp.config import Settings
from igmcp.server import create_app
from tests.conftest import MCP_TOKEN

HEADERS = {
    "Authorization": f"Bearer {MCP_TOKEN}",
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


@asynccontextmanager
async def running(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c


async def test_tools_list_is_exactly_the_five_read_only_tools(settings):
    async with running(settings) as http:
        r = await http.post(
            "/mcp", headers=HEADERS, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )
    assert r.status_code == 200, r.text
    tools = r.json()["result"]["tools"]
    assert {t["name"] for t in tools} == {
        "get_instagram_profile",
        "list_instagram_media",
        "get_instagram_media",
        "get_instagram_comments",
        "get_instagram_insights",
    }
    assert all(t["annotations"]["readOnlyHint"] is True for t in tools)


async def test_wrong_host_header_is_rejected(settings):
    async with running(settings) as http:
        r = await http.post(
            "/mcp",
            headers={**HEADERS, "Host": "evil.example"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
    assert r.status_code in (400, 421)
