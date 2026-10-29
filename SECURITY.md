# Security policy

## Reporting a vulnerability
Please report security issues privately through GitHub's "Report a vulnerability" button
(Security tab) instead of opening a public issue.

## Scope and design notes
- The server is read-only: it only issues GET requests to the Instagram Graph API.
- Never commit `secrets/`, `.env`, Graph access tokens or `MCP_AUTH_TOKEN` values.
- If a Graph token or bearer token was ever exposed, rotate it immediately; deleting the commit is not enough.
