"""User plugin catalog + orchestrator helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from apex_rag_demo.plugins.registry import list_enabled_tools
from apex_rag_demo.plugins.tenant import tenant_scope


def plugin_catalog_block(user_id: str) -> str:
    tools = list_enabled_tools(tenant_scope(user_id))
    if not tools:
        return "User plugins: (none registered)"
    lines = ["User plugins (tenant-isolated; action call_plugin):"]
    for t in tools:
        params = ", ".join(p.name for p in t.parameters) or "(no params)"
        lines.append(
            f"- id={t.id} kind={t.kind} name={t.name}: {t.description[:200]} | params: {params}",
        )
    return "\n".join(lines)


def try_plugin_orchestrator_step(
    question: str,
    *,
    user_id: str,
    api_trace: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Deterministic: run plugin when user says 'run plugin <id>' or '@plugin-id'."""
    if api_trace:
        return None
    tools = list_enabled_tools(tenant_scope(user_id))
    if not tools:
        return None
    q = question.strip().lower()
    m = re.search(r"\b(?:run|invoke|call)\s+plugin\s+([a-z0-9_-]+)", q)
    if m:
        pid = m.group(1)
    elif question.strip().startswith("@") and len(question.strip()) > 1:
        pid = question.strip().lstrip("@").split()[0].lower()
    else:
        return None
    if not any(t.id == pid for t in tools):
        return None
    return {
        "orchestrator_action": "call_plugin",
        "intent": "explain",
        "action_plan": {"plugin_id": pid, "parameters": {}},
        "orchestrator_reason": "user_plugin_invoke",
    }


def parse_call_plugin_from_llm(data: dict[str, Any]) -> dict[str, Any] | None:
    action = str(data.get("action") or "").strip().lower()
    if action != "call_plugin":
        return None
    plugin_id = str(data.get("plugin_id") or "").strip().lower()
    if not plugin_id:
        return None
    params = data.get("plugin_parameters")
    if not isinstance(params, dict):
        params = data.get("parameters") if isinstance(data.get("parameters"), dict) else {}
    return {
        "orchestrator_action": "call_plugin",
        "intent": "explain",
        "action_plan": {"plugin_id": plugin_id, "parameters": params},
        "orchestrator_reason": str(data.get("reason") or "llm_call_plugin"),
    }
