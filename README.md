# igmcp

A small, read-only [MCP](https://modelcontextprotocol.io) server for the official
**Instagram Graph API**. It lets an MCP client (Claude Code, etc.) read your own professional
account's profile, media, comments and insights. It cannot publish, delete, or send anything.

Streamable HTTP, stateless. Python 3.12+, FastMCP, httpx, pydantic v2.

## Tools
All annotated `readOnlyHint`:

| Tool | Purpose |
|---|---|
| `get_instagram_profile` | Account name, bio, follower/following/media counts |
| `list_instagram_media` | Recent posts and reels |
| `get_instagram_media` | One media item |
| `get_instagram_comments` | Comments on a media item |
| `get_instagram_insights` | Account or media insights (`metrics` required, e.g. `reach`, `views`, `shares`) |

## Security design
- GET requests only. The Graph token travels in the `Authorization` header, never in a URL.
- Mandatory bearer auth on `/mcp` and `/metrics`; the server refuses to start without
  `MCP_AUTH_TOKEN` (>= 24 chars). `/healthz` and `/readyz` are open.
- Host-header allow-list. No debug endpoints.
- Secrets are read from `*_FILE` paths and redacted from logs.
- Container: non-root user, read-only filesystem, all capabilities dropped, no published port.
- `/metrics` (Prometheus): request counts and latency, tool outcomes, Meta app usage %.

## Configuration
| Variable | Meaning |
|---|---|
| `INSTAGRAM_ACCOUNT_ID` | Instagram professional account id |
| `GRAPH_VERSION` | Graph API version (default `v21.0`) |
| `IG_GRAPH_TOKEN_FILE` | Path to a file holding the Graph access token |
| `MCP_AUTH_TOKEN_FILE` | Path to a file holding the bearer token clients must send |

## Develop
    python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
    .venv/bin/ruff check src tests && .venv/bin/mypy src && .venv/bin/pytest

## Deploy
    mkdir -p secrets && chmod 700 secrets
    # create secrets/ig_graph_token and secrets/mcp_auth_token (readable by uid 10001)
    # create .env with INSTAGRAM_ACCOUNT_ID=... (and optionally GRAPH_VERSION=...)
    docker compose up -d --build

Register it in Claude Code:

    claude mcp add --transport http instagram http://<host>:8000/mcp \
      --header "Authorization: Bearer <MCP_AUTH_TOKEN>"

`compose.yml` attaches to an external Docker network named by `AI_NETWORK` (default `ai-network`);
create it first (`docker network create ai-network`) or set `AI_NETWORK` in `.env`.

## Limits
- The Graph user token lasts 60 days; renewing it needs the Meta app secret, which this service
  does not handle.
- Reads only the connected account, not other people's content.
- Not affiliated with Meta.

## License
MIT
