import httpx
import pytest
import respx

from igmcp.config import Settings
from igmcp.errors import AuthError, NotFound, PermissionDenied, RateLimited, UpstreamError
from igmcp.graph.client import GraphClient
from tests.conftest import TOKEN

BASE = "https://graph.facebook.com/v21.0"


@pytest.fixture
async def client(settings: Settings):
    c = GraphClient(settings)
    yield c
    await c.aclose()


@respx.mock
async def test_token_in_header_never_in_url(client: GraphClient):
    route = respx.get(f"{BASE}/17841400000000000").mock(
        return_value=httpx.Response(200, json={"id": "17841400000000000", "username": "u"})
    )
    profile = await client.profile()
    assert profile.username == "u"
    req = route.calls.last.request
    assert req.headers["authorization"] == f"Bearer {TOKEN}"
    assert "access_token" not in str(req.url)


@respx.mock
async def test_only_get_is_issued(client: GraphClient):
    route = respx.route().mock(return_value=httpx.Response(200, json={"data": []}))
    await client.list_media()
    assert {c.request.method for c in route.calls} == {"GET"}


@respx.mock
@pytest.mark.parametrize(
    ("status", "body", "exc"),
    [
        (400, {"error": {"code": 190, "message": "expired"}}, AuthError),
        (400, {"error": {"code": 4, "message": "limit"}}, RateLimited),
        (403, {"error": {"code": 10, "message": "no perm"}}, PermissionDenied),
        (404, {"error": {"code": 100, "message": "x"}}, NotFound),
    ],
)
async def test_errors_are_classified_and_not_retried(client, status, body, exc):
    route = respx.get(f"{BASE}/17841400000000000").mock(
        return_value=httpx.Response(status, json=body)
    )
    with pytest.raises(exc):
        await client.profile()
    assert route.call_count == 1


@respx.mock
async def test_5xx_is_retried_then_raised(client: GraphClient, monkeypatch):
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("igmcp.graph.client.asyncio.sleep", no_sleep)
    route = respx.get(f"{BASE}/17841400000000000").mock(return_value=httpx.Response(503))
    with pytest.raises(UpstreamError):
        await client.profile()
    assert route.call_count == 2


@respx.mock
async def test_media_id_is_validated_before_any_request(client: GraphClient):
    route = respx.route().mock(return_value=httpx.Response(200, json={}))
    with pytest.raises(ValueError):
        await client.media("123/../me")
    assert route.call_count == 0


@respx.mock
async def test_page_size_is_clamped(client: GraphClient):
    route = respx.get(f"{BASE}/17841400000000000/media").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    await client.list_media(limit=9999)
    assert route.calls.last.request.url.params["limit"] == "50"


@respx.mock
async def test_insights_rejects_bad_metric(client: GraphClient):
    with pytest.raises(ValueError):
        await client.insights(["reach,impressions&x=1"])


@respx.mock
async def test_comments_flatten_replies_and_cursor(client: GraphClient):
    respx.get(f"{BASE}/17841400000000001/comments").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "1",
                        "text": "hi",
                        "replies": {"data": [{"id": "2", "text": "yo"}]},
                    }
                ],
                "paging": {"cursors": {"after": "CUR"}, "next": "https://x"},
            },
        )
    )
    page = await client.comments("17841400000000001")
    assert page.items[0].replies[0].id == "2"
    assert page.next_cursor == "CUR"
