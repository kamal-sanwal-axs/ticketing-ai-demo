"""REST API for declarative custom plugins and runtime status."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from apex_rag_demo.auth import profile_from_token, validate_token_with_admin
from apex_rag_demo.plugins.models import CustomPluginTool
from apex_rag_demo.plugins.registry import delete_plugin, get_plugin, list_plugins, save_plugin
from apex_rag_demo.plugins.tenant import tenant_scope
from apex_rag_demo.plugins.sandbox import SandboxViolation, execute_plugin
from apex_rag_demo.runtime.graph_runtime import runtime_status
from apex_rag_demo.sandbox_toolkit.docker_runner import sandbox_toolkit_status
from apex_rag_demo.sandbox_toolkit.models import SandboxJob
from apex_rag_demo.sandbox_toolkit import run_sandbox_job

router = APIRouter(prefix="/api", tags=["plugins"])


class PluginInvokeRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True


def _auth(authorization: str | None) -> tuple[str, str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer <token>")
    token = authorization[7:].strip()
    ok, err = validate_token_with_admin(token)
    if not ok:
        raise HTTPException(status_code=401, detail=err or "Invalid token")
    profile = profile_from_token(token, "US-West")
    user_id = str(profile.get("userId") or profile.get("email") or "anonymous")
    return user_id, token


@router.get("/runtime/status")
async def get_runtime_status() -> dict[str, Any]:
    status = runtime_status()
    status["sandbox_toolkit"] = sandbox_toolkit_status()
    return status


class SandboxRunRequest(BaseModel):
    job: SandboxJob


@router.post("/sandbox/run")
async def api_run_sandbox(
    body: SandboxRunRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _auth(authorization)
    result = run_sandbox_job(body.job)
    return result.model_dump(mode="json")


@router.get("/tools")
async def list_openapi_tools() -> dict[str, Any]:
    """OpenAPI-derived dynamic tool catalog (for debugging / UI)."""
    from apex_rag_demo.dynamic_tools import dynamic_tools_status, load_dynamic_tool_catalog

    catalog = load_dynamic_tool_catalog()
    tools = [
        {
            "tool_id": t.tool_id,
            "service_id": t.service_id,
            "method": t.method.upper(),
            "path": t.path_template,
            "summary": t.summary,
            "legacy_intent": t.legacy_intent,
        }
        for t in catalog.values()
    ]
    return {"status": dynamic_tools_status(), "tools": tools}


@router.get("/plugins")
async def api_list_plugins(
    authorization: Annotated[str | None, Header()] = None,
) -> list[dict[str, Any]]:
    user_id, _ = _auth(authorization)
    tools = list_plugins(tenant_scope(user_id))
    return [t.model_dump(mode="json") for t in tools]


@router.post("/plugins")
async def api_create_plugin(
    body: CustomPluginTool,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    user_id, _ = _auth(authorization)
    try:
        saved = save_plugin(tenant_scope(user_id), body, user_id=user_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return saved.model_dump(mode="json")


@router.get("/plugins/{plugin_id}")
async def api_get_plugin(
    plugin_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    user_id, _ = _auth(authorization)
    tool = get_plugin(tenant_scope(user_id), plugin_id, user_id=user_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return tool.model_dump(mode="json")


@router.put("/plugins/{plugin_id}")
async def api_update_plugin(
    plugin_id: str,
    body: CustomPluginTool,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    user_id, _ = _auth(authorization)
    if body.id != plugin_id:
        raise HTTPException(status_code=400, detail="Body id must match path plugin_id")
    try:
        saved = save_plugin(tenant_scope(user_id), body, user_id=user_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return saved.model_dump(mode="json")


@router.delete("/plugins/{plugin_id}")
async def api_delete_plugin(
    plugin_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    user_id, _ = _auth(authorization)
    try:
        ok = delete_plugin(tenant_scope(user_id), plugin_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"deleted": True}


@router.post("/plugins/{plugin_id}/invoke")
async def api_invoke_plugin(
    plugin_id: str,
    body: PluginInvokeRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    user_id, token = _auth(authorization)
    tool = get_plugin(tenant_scope(user_id), plugin_id, user_id=user_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    try:
        return execute_plugin(
            tool,
            body.parameters,
            bearer_token=token,
            dry_run=body.dry_run,
        )
    except SandboxViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
