"""Custom plugins: declarative HTTP tools and sandboxed script handlers."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

_PLUGIN_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


class PluginParameter(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    type: Literal["string", "integer", "number", "boolean"] = "string"
    required: bool = False
    description: str = Field(default="", max_length=500)
    default: str | int | float | bool | None = None


class CustomPluginTool(BaseModel):
    """HTTP action (GPT Actions style) or sandboxed script handler."""

    kind: Literal["http", "script"] = "http"
    id: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    parameters: list[PluginParameter] = Field(default_factory=list)
    enabled: bool = True

    # --- HTTP (kind=http) ---
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    url_template: str = Field(
        default="",
        max_length=2000,
        description="HTTPS URL with {param} placeholders (http plugins only)",
    )
    headers: dict[str, str] = Field(default_factory=dict)
    body_template: dict[str, Any] | None = Field(
        default=None,
        description="JSON body for POST/PUT; string values may use {param} placeholders",
    )
    response_format: Literal["json", "text"] = "json"

    # --- Script (kind=script) ---
    language: Literal["javascript", "python"] | None = None
    source: str | None = Field(
        default=None,
        max_length=65536,
        description="Handler source; must define entry_function(input) -> output",
    )
    entry_function: str = Field(default="handler", max_length=64)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        slug = value.strip().lower()
        if not _PLUGIN_ID_RE.match(slug):
            raise ValueError("id must be lowercase slug: a-z, 0-9, hyphen, underscore")
        return slug

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, value: dict[str, str]) -> dict[str, str]:
        blocked = {"host", "content-length", "transfer-encoding"}
        out: dict[str, str] = {}
        for key, val in value.items():
            k = key.strip()
            if k.lower() in blocked:
                continue
            out[k] = str(val)[:500]
        return out

    @model_validator(mode="after")
    def validate_kind_fields(self) -> CustomPluginTool:
        if self.kind == "http":
            if len(self.url_template.strip()) < 8:
                raise ValueError("http plugins require url_template (min 8 chars)")
        if self.kind == "script":
            if not self.language or not (self.source or "").strip():
                raise ValueError("script plugins require language and source")
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", self.entry_function):
                raise ValueError("entry_function must be a valid identifier")
        return self
