"""Multi-tenant isolation for plugin storage and execution."""

from __future__ import annotations

from apex_rag_demo.config import PLUGIN_TENANT_STRICT


def tenant_scope(user_id: str) -> str:
    uid = (user_id or "").strip()
    if not uid:
        if PLUGIN_TENANT_STRICT:
            raise PermissionError("user_id required for tenant-scoped plugin access")
        return "user:anonymous"
    if PLUGIN_TENANT_STRICT and uid.lower() in ("global", "shared", "admin"):
        raise PermissionError("Reserved tenant id")
    return f"user:{uid}"


def assert_plugin_tenant(scope: str, user_id: str) -> None:
    expected = tenant_scope(user_id)
    if scope != expected:
        raise PermissionError("Cross-tenant plugin access denied")
