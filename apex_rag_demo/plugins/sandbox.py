"""Safe execution for declarative plugins — no eval/exec of user scripts."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from apex_rag_demo.config import PLUGIN_ALLOWED_HOST_SUFFIXES, PLUGIN_HTTP_TIMEOUT_SEC
from apex_rag_demo.plugins.models import CustomPluginTool, PluginParameter

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class SandboxViolation(Exception):
    pass


def _allowed_host(hostname: str) -> bool:
    host = (hostname or "").lower().strip(".")
    if not host:
        return False
    for suffix in PLUGIN_ALLOWED_HOST_SUFFIXES:
        s = suffix.lower().strip(".")
        if host == s or host.endswith(f".{s}"):
            return True
    return False


def _substitute(template: str, params: dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in params:
            raise SandboxViolation(f"Missing parameter for placeholder {{{key}}}")
        return str(params[key])

    return _PLACEHOLDER_RE.sub(repl, template)


def _substitute_json(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):
        if "{" in value and "}" in value:
            return _substitute(value, params)
        return value
    if isinstance(value, dict):
        return {k: _substitute_json(v, params) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_json(item, params) for item in value]
    return value


def coerce_params(tool: CustomPluginTool, raw: dict[str, Any] | None) -> dict[str, Any]:
    incoming = dict(raw or {})
    out: dict[str, Any] = {}
    for spec in tool.parameters:
        if spec.name in incoming:
            val = incoming[spec.name]
        elif spec.default is not None:
            val = spec.default
        elif spec.required:
            raise SandboxViolation(f"Required parameter missing: {spec.name}")
        else:
            continue
        out[spec.name] = _coerce_type(spec, val)
    extra = set(incoming) - {p.name for p in tool.parameters}
    if extra:
        raise SandboxViolation(f"Unknown parameters: {', '.join(sorted(extra))}")
    return out


def _coerce_type(spec: PluginParameter, val: Any) -> Any:
    if spec.type == "string":
        return str(val)[:4000]
    if spec.type == "boolean":
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("1", "true", "yes", "on")
    if spec.type == "integer":
        return int(val)
    if spec.type == "number":
        return float(val)
    return val


def validate_url_template(url_template: str) -> None:
    if any(ch in url_template for ch in ("\n", "\r", "`", "$(", "<?", "javascript:")):
        raise SandboxViolation("url_template contains disallowed characters")
    parsed = urlparse(url_template.split("{", 1)[0] if "{" in url_template else url_template)
    if parsed.scheme not in ("https", "http"):
        raise SandboxViolation("Only http(s) URLs are allowed")
    if not _allowed_host(parsed.hostname or ""):
        raise SandboxViolation(f"Host not in allowlist: {parsed.hostname}")


def execute_plugin(
    tool: CustomPluginTool,
    params: dict[str, Any] | None,
    *,
    bearer_token: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if tool.kind == "script":
        from apex_rag_demo.plugins.code_sandbox import execute_script_plugin

        return execute_script_plugin(tool, params, dry_run=dry_run)

    if not tool.enabled:
        raise SandboxViolation("Plugin is disabled")

    coerced = coerce_params(tool, params)
    validate_url_template(tool.url_template)
    url = _substitute(tool.url_template, coerced)
    parsed = urlparse(url)
    if not _allowed_host(parsed.hostname or ""):
        raise SandboxViolation(f"Resolved host not allowed: {parsed.hostname}")

    headers = {k: str(v) for k, v in tool.headers.items()}
    if bearer_token:
        headers.setdefault("Authorization", f"Bearer {bearer_token}")

    body = None
    if tool.body_template is not None:
        body = _substitute_json(tool.body_template, coerced)

    preview = {
        "method": tool.method,
        "url": url,
        "headers": {k: ("***" if k.lower() == "authorization" else v) for k, v in headers.items()},
        "body": body,
    }
    if dry_run:
        return {"dry_run": True, "request": preview}

    with httpx.Client(timeout=PLUGIN_HTTP_TIMEOUT_SEC) as client:
        response = client.request(
            tool.method,
            url,
            headers=headers,
            json=body if tool.method in ("POST", "PUT", "PATCH") else None,
        )

    text = response.text[:120_000]
    if tool.response_format == "text":
        payload: Any = text
    else:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = {"raw_text": text}

    return {
        "dry_run": False,
        "status_code": response.status_code,
        "request": preview,
        "response": payload,
    }
