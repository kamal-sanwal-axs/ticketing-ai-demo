"""LangGraph SQLite checkpointer + store (thread state and plugin definitions)."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apex_rag_demo.config import DATA_DIR, LANGGRAPH_CHECKPOINT_PATH, LANGGRAPH_RUNTIME_ENABLED, LANGGRAPH_STORE_PATH

_RUNTIME_DIR = DATA_DIR / "langgraph"
_CHECKPOINT_PATH = Path(LANGGRAPH_CHECKPOINT_PATH)
_STORE_PATH = Path(LANGGRAPH_STORE_PATH)


@dataclass
class RuntimeHandles:
    checkpointer: Any | None
    store: Any | None
    checkpoint_path: str
    store_path: str


_handles: RuntimeHandles | None = None
_checkpoint_cm: AbstractContextManager[Any] | None = None
_store_cm: AbstractContextManager[Any] | None = None


def runtime_enabled() -> bool:
    return LANGGRAPH_RUNTIME_ENABLED


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    root = DATA_DIR.parent
    return root / path


def init_runtime() -> RuntimeHandles:
    """Open SQLite checkpointer + store. Safe to call once at app startup."""
    global _handles, _checkpoint_cm, _store_cm
    if _handles is not None:
        return _handles

    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    cp_path = _resolve_path(_CHECKPOINT_PATH)
    st_path = _resolve_path(_STORE_PATH)
    cp_path.parent.mkdir(parents=True, exist_ok=True)
    st_path.parent.mkdir(parents=True, exist_ok=True)

    if not runtime_enabled():
        _handles = RuntimeHandles(None, None, str(cp_path), str(st_path))
        return _handles

    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.store.sqlite import SqliteStore

    _checkpoint_cm = SqliteSaver.from_conn_string(str(cp_path))
    _store_cm = SqliteStore.from_conn_string(str(st_path))
    checkpointer = _checkpoint_cm.__enter__()
    store = _store_cm.__enter__()
    _handles = RuntimeHandles(checkpointer, store, str(cp_path), str(st_path))
    return _handles


def shutdown_runtime() -> None:
    global _handles, _checkpoint_cm, _store_cm
    if _checkpoint_cm is not None:
        _checkpoint_cm.__exit__(None, None, None)
        _checkpoint_cm = None
    if _store_cm is not None:
        _store_cm.__exit__(None, None, None)
        _store_cm = None
    _handles = None


def get_checkpointer() -> Any | None:
    if _handles is None:
        init_runtime()
    return _handles.checkpointer if _handles else None


def get_store() -> Any | None:
    if _handles is None:
        init_runtime()
    return _handles.store if _handles else None


def runtime_status() -> dict[str, Any]:
    if _handles is None:
        init_runtime()
    h = _handles
    from apex_rag_demo.config import PLUGIN_SANDBOX_BACKEND, PLUGIN_SCRIPT_ENABLED, PLUGIN_TENANT_STRICT
    from apex_rag_demo.capability_routing import capability_routing_status
    from apex_rag_demo.plugins.sandbox_backend import resolve_sandbox_backend, sandbox_status

    sb = sandbox_status()
    return {
        "enabled": runtime_enabled(),
        "checkpointer_ready": h.checkpointer is not None if h else False,
        "store_ready": h.store is not None if h else False,
        "checkpoint_path": h.checkpoint_path if h else str(_resolve_path(_CHECKPOINT_PATH)),
        "store_path": h.store_path if h else str(_resolve_path(_STORE_PATH)),
        "script_sandbox_enabled": PLUGIN_SCRIPT_ENABLED,
        "script_sandbox_backend": PLUGIN_SANDBOX_BACKEND,
        "script_sandbox_effective_backend": resolve_sandbox_backend(),
        "script_sandbox": sb,
        "tenant_strict": PLUGIN_TENANT_STRICT,
        "capability_routing": capability_routing_status(),
    }


def thread_config(user_id: str, session_id: str) -> dict[str, Any]:
    if not runtime_enabled() or not user_id or not session_id:
        return {}
    return {"configurable": {"thread_id": f"{user_id}:{session_id}"}}
