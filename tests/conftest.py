import pytest

from igmcp.config import Settings

TOKEN = "EAAfakefakefakefakefakefakefake0000"
MCP_TOKEN = "m" * 32


@pytest.fixture
def settings() -> Settings:
    return Settings(
        ig_graph_token=TOKEN,  # type: ignore[arg-type]
        mcp_auth_token=MCP_TOKEN,  # type: ignore[arg-type]
        instagram_account_id="17841400000000000",
        http_max_attempts=2,
        allowed_hosts="testserver",
    )
