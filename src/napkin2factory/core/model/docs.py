"""Front matter of ``model/docs/*.md`` (decision D8)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from napkin2factory.core.model.base import Model, Slug, UriField

Audience = Literal["owner", "engineer", "manufacturer"]
DEFAULT_AUDIENCE: tuple[Audience, ...] = ("owner", "engineer")


class DocMeta(Model):
    """Front matter: id, title, audience, declared dependencies."""

    id: Slug
    title: str
    audience: list[Audience] = Field(default_factory=lambda: list(DEFAULT_AUDIENCE))
    depends_on: list[UriField] = Field(default_factory=list)
    order: int = 100
    safety: bool = False
