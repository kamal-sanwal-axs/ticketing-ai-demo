"""Script plugin validation + isolated worker execution (multi-tenant safe)."""

from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.config import (
    PLUGIN_SCRIPT_ENABLED,
    PLUGIN_SCRIPT_MAX_BYTES,
)
from apex_rag_demo.plugins.isolated_runner import run_isolated_script
from apex_rag_demo.plugins.models import CustomPluginTool
from apex_rag_demo.plugins.sandbox import SandboxViolation, coerce_params
from apex_rag_demo.plugins.sandbox_backend import resolve_sandbox_backend, sandbox_isolation_label

_JS_FORBIDDEN = re.compile(
    r"\b(import|require)\b|"
    r"\beval\s*\(|"
    r"\bFunction\s*\(|"
    r"\bfetch\s*\(|"
    r"\bXMLHttpRequest\b|"
    r"\bWebSocket\b|"
    r"\bprocess\.",
    re.IGNORECASE,
)
_PY_FORBIDDEN = re.compile(
    r"\b(import|exec|eval|compile|open|__import__|subprocess|os\.|sys\.|socket|pickle)\b",
    re.IGNORECASE,
)


def _check_source(language: str, source: str) -> None:
    if not PLUGIN_SCRIPT_ENABLED:
        raise SandboxViolation("Script plugins are disabled (PLUGIN_SCRIPT_ENABLED=false)")
    if len(source.encode("utf-8")) > PLUGIN_SCRIPT_MAX_BYTES:
        raise SandboxViolation(f"Script exceeds {PLUGIN_SCRIPT_MAX_BYTES} bytes")
    if language == "javascript" and _JS_FORBIDDEN.search(source):
        raise SandboxViolation("JavaScript source contains disallowed tokens (import, eval, fetch, …)")
    if language == "python" and _PY_FORBIDDEN.search(source):
        raise SandboxViolation("Python source contains disallowed tokens (import, open, exec, …)")


def execute_script_plugin(
    tool: CustomPluginTool,
    params: dict[str, Any] | None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    if tool.kind != "script":
        raise SandboxViolation("Not a script plugin")
    if not tool.enabled:
        raise SandboxViolation("Plugin is disabled")
    if not tool.language or not tool.source:
        raise SandboxViolation("Script plugin missing language or source")

    coerced = coerce_params(tool, params)
    _check_source(tool.language, tool.source)
    entry = tool.entry_function or "handler"

    backend = resolve_sandbox_backend()
    meta = {
        "kind": "script",
        "language": tool.language,
        "entry_function": entry,
        "source_bytes": len(tool.source.encode("utf-8")),
        "input": coerced,
        "backend": backend,
        "isolation": sandbox_isolation_label(backend),
    }
    if dry_run:
        return {"dry_run": True, "script": meta}

    result = run_isolated_script(
        language=tool.language,
        source=tool.source,
        entry=entry,
        payload=coerced,
    )
    return {
        "dry_run": False,
        "script": meta,
        "result": result,
    }
