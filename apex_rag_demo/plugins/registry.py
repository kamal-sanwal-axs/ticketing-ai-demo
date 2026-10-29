"""Persist custom plugins in the LangGraph SQLite store."""

from __future__ import annotations

from typing import Any

from apex_rag_demo.plugins.models import CustomPluginTool
from apex_rag_demo.plugins.tenant import assert_plugin_tenant
from apex_rag_demo.runtime.graph_runtime import get_store, runtime_enabled


def _namespace(scope: str) -> tuple[str, ...]:
    return ("plugins", scope)


def _require_store() -> Any:
    store = get_store()
    if store is None:
        raise RuntimeError(
            "Plugin store is not available — set LANGGRAPH_RUNTIME_ENABLED=true and restart the app",
        )
    return store


def save_plugin(scope: str, tool: CustomPluginTool, *, user_id: str | None = None) -> CustomPluginTool:
    if user_id is not None:
        assert_plugin_tenant(scope, user_id)
    store = _require_store()
    payload = tool.model_dump(mode="json")
    store.put(_namespace(scope), tool.id, payload)
    return tool


def get_plugin(scope: str, plugin_id: str, *, user_id: str | None = None) -> CustomPluginTool | None:
    if user_id is not None:
        assert_plugin_tenant(scope, user_id)
    if not runtime_enabled():
        return None
    store = get_store()
    if store is None:
        return None
    item = store.get(_namespace(scope), plugin_id)
    if item is None or not item.value:
        return None
    return CustomPluginTool.model_validate(item.value)


def delete_plugin(scope: str, plugin_id: str) -> bool:
    store = _require_store()
    if get_plugin(scope, plugin_id) is None:
        return False
    store.delete(_namespace(scope), plugin_id)
    return True


def list_plugins(scope: str) -> list[CustomPluginTool]:
    if not runtime_enabled():
        return []
    store = get_store()
    if store is None:
        return []
    tools: list[CustomPluginTool] = []
    for item in store.search(_namespace(scope)):
        try:
            tools.append(CustomPluginTool.model_validate(item.value))
        except Exception:
            continue
    return sorted(tools, key=lambda t: t.id)


def list_enabled_tools(scope: str) -> list[CustomPluginTool]:
    return [t for t in list_plugins(scope) if t.enabled]
