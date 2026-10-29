"""Settings. Secrets come from files (`<NAME>_FILE`) or env, and never reach logs."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SECRET_FIELDS = ("ig_graph_token", "mcp_auth_token")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore", frozen=True)

    ig_graph_token: SecretStr
    mcp_auth_token: SecretStr = Field(min_length=24)
    instagram_account_id: str = Field(pattern=r"^\d+$")
    graph_base_url: str = "https://graph.facebook.com"
    graph_version: str = Field(default="v21.0", pattern=r"^v\d+\.\d+$")
    http_timeout_s: float = 15.0
    http_max_attempts: int = Field(default=3, ge=1, le=6)
    max_page_size: int = Field(default=50, ge=1, le=100)
    host: str = "0.0.0.0"  # noqa: S104  (container-internal; no host port is published)
    port: int = 8000
    allowed_hosts: str = "instagram-mcp:8000,localhost:8000,127.0.0.1:8000"
    log_level: str = "INFO"

    @model_validator(mode="before")
    @classmethod
    def _load_file_secrets(cls, data: dict[str, Any]) -> dict[str, Any]:
        out = dict(data)
        for name in _SECRET_FIELDS:
            path = os.environ.get(f"{name.upper()}_FILE")
            if path:
                out[name] = Path(path).read_text(encoding="utf-8").strip()
        return out

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
