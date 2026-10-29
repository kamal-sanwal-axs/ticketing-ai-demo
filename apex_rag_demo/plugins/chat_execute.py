"""Execute tenant plugins from LangGraph orchestrator."""

from __future__ import annotations

from typing import Any

from apex_rag_demo.clients.http_common import get_bearer_token
from apex_rag_demo.plugins.registry import get_plugin
from apex_rag_demo.plugins.sandbox import SandboxViolation, execute_plugin
from apex_rag_demo.plugins.tenant import tenant_scope


def execute_user_plugin(
    user_id: str,
    plugin_id: str,
    parameters: dict[str, Any] | None,
) -> dict[str, Any]:
    scope = tenant_scope(user_id)
    tool = get_plugin(scope, plugin_id)
    if tool is None:
        raise SandboxViolation(f"Plugin not found: {plugin_id}")
    return execute_plugin(tool, parameters or {}, bearer_token=get_bearer_token(), dry_run=False)


def execute_user_plugin_from_plan(user_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    plugin_id = str(plan.get("plugin_id") or "").strip()
    if not plugin_id:
        raise SandboxViolation("plugin_id required in action_plan")
    params = plan.get("parameters") if isinstance(plan.get("parameters"), dict) else {}
    return execute_user_plugin(user_id, plugin_id, params)
