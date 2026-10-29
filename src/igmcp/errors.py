"""Typed failures. Messages are safe to return to the model: no URLs, no tokens."""

from __future__ import annotations


class GraphError(Exception):
    """Base for every Graph API failure."""

    def __init__(self, message: str, *, status: int = 0, code: int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class AuthError(GraphError):
    """Token invalid or expired (Meta code 190, or HTTP 401)."""


class PermissionDenied(GraphError):
    """Token lacks a permission (Meta codes 10, 200-299) or the object is not accessible."""


class RateLimited(GraphError):
    """Meta app or account throttling (codes 4, 17, 32, 613)."""


class NotFound(GraphError):
    """Object does not exist or is not visible to this token."""


class UpstreamError(GraphError):
    """Meta 5xx, network failure, or an unparseable response."""
