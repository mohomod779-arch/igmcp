import httpx
import pytest
from pydantic import ValidationError

from igmcp.config import Settings
from igmcp.logging import redact
from igmcp.server import create_app
from tests.conftest import MCP_TOKEN, TOKEN


@pytest.fixture
async def http(settings: Settings):
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def test_probes_are_open(http):
    assert (await http.get("/healthz")).status_code == 200


@pytest.mark.parametrize("path", ["/mcp", "/metrics"])
async def test_everything_else_needs_bearer(http, path):
    assert (await http.get(path)).status_code == 401
    bad = await http.get(path, headers={"Authorization": "Bearer wrong"})
    assert bad.status_code == 401
    assert bad.headers["www-authenticate"] == "Bearer"


async def test_metrics_with_bearer(http):
    r = await http.get("/metrics", headers={"Authorization": f"Bearer {MCP_TOKEN}"})
    assert r.status_code == 200
    assert "igmcp_graph_requests_total" in r.text or "python_info" in r.text


async def test_no_debug_endpoints(http):
    r = await http.get("/debug-instagram-auth", headers={"Authorization": f"Bearer {MCP_TOKEN}"})
    assert r.status_code == 404


def test_server_refuses_to_start_without_auth_token():
    with pytest.raises(ValidationError):
        Settings(ig_graph_token="x" * 30, instagram_account_id="1234567")  # type: ignore[arg-type,call-arg]


def test_short_auth_token_rejected():
    with pytest.raises(ValidationError):
        Settings(
            ig_graph_token="x" * 30,  # type: ignore[arg-type]
            mcp_auth_token="short",  # type: ignore[arg-type]
            instagram_account_id="1234567",
        )


def test_secrets_read_from_files(tmp_path, monkeypatch):
    (tmp_path / "g").write_text(TOKEN + "\n")
    (tmp_path / "m").write_text(MCP_TOKEN + "\n")
    monkeypatch.setenv("IG_GRAPH_TOKEN_FILE", str(tmp_path / "g"))
    monkeypatch.setenv("MCP_AUTH_TOKEN_FILE", str(tmp_path / "m"))
    monkeypatch.setenv("INSTAGRAM_ACCOUNT_ID", "17841400000000000")
    s = Settings()  # type: ignore[call-arg]
    assert s.ig_graph_token.get_secret_value() == TOKEN
    assert TOKEN not in repr(s)


def test_redaction():
    assert TOKEN not in redact(f"GET /x?access_token={TOKEN} failed")
    assert TOKEN not in redact(f"token {TOKEN}")
    assert "secret" not in redact("Authorization: Bearer secret")
