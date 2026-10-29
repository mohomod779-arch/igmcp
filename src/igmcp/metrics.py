"""Prometheus metrics."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

GRAPH_REQUESTS = Counter(
    "igmcp_graph_requests_total", "Graph API requests", ["path_kind", "outcome"]
)
GRAPH_LATENCY = Histogram("igmcp_graph_request_seconds", "Graph API latency", ["path_kind"])
APP_USAGE_PCT = Gauge("igmcp_app_usage_percent", "Meta X-App-Usage call_volume percent")
TOOL_CALLS = Counter("igmcp_tool_calls_total", "MCP tool calls", ["tool", "outcome"])
