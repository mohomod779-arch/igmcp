"""Typed views of Graph API objects. Unknown fields are dropped, not forwarded."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class Profile(_Model):
    id: str
    username: str | None = None
    name: str | None = None
    biography: str | None = None
    website: str | None = None
    followers_count: int | None = None
    follows_count: int | None = None
    media_count: int | None = None
    profile_picture_url: str | None = None


class Media(_Model):
    id: str
    media_type: str | None = None
    media_product_type: str | None = None
    caption: str | None = None
    permalink: str | None = None
    timestamp: str | None = None
    like_count: int | None = None
    comments_count: int | None = None
    thumbnail_url: str | None = None


class MediaPage(_Model):
    items: list[Media]
    next_cursor: str | None = None


class Comment(_Model):
    id: str
    text: str | None = None
    username: str | None = None
    timestamp: str | None = None
    like_count: int | None = None
    replies: list[Comment] = Field(default_factory=list)


class CommentPage(_Model):
    items: list[Comment]
    next_cursor: str | None = None


class InsightValue(_Model):
    name: str
    period: str | None = None
    title: str | None = None
    value: float | int | None = None
    values: list[dict[str, object]] = Field(default_factory=list)


class Insights(_Model):
    items: list[InsightValue]
