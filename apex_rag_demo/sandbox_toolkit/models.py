from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SandboxJob(BaseModel):
    runtime: Literal["python", "react"] = "python"
    files: dict[str, str] = Field(default_factory=dict)
    input: dict[str, Any] = Field(default_factory=dict)
    entry: str = "handler"
    pip_packages: list[str] = Field(default_factory=list)
    npm_packages: list[str] = Field(default_factory=list)
    reason: str | None = None


class SandboxResult(BaseModel):
    ok: bool
    runtime: str = ""
    result: Any = None
    html: str | None = None
    error: str | None = None
    container_id: str | None = None
