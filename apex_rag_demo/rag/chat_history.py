from __future__ import annotations

import json
from typing import Any

from apex_rag_demo.config import (
    CHAT_HISTORY_MAX_MESSAGES,
    CHAT_MESSAGE_MAX_CHARS,
    CHAT_MESSAGE_MAX_CHARS_ROUTING,
    CHAT_RAW_LOG_MAX_MESSAGES,
    DATA_DIR,
)
from apex_rag_demo.prompt_budget import truncate_text
from apex_rag_demo.response_formatters import strip_ui_region

_GRAPH_STATE_DIR = DATA_DIR / "session_graph"

_ALLOWED_ROLES = frozenset({"user", "assistant", "tool"})


def _session_path(user_id: str, session_id: str):
    return _GRAPH_STATE_DIR / user_id / f"{session_id}.json"


def normalize_chat_history(
    messages: list[dict[str, Any]] | None,
    *,
    max_messages: int | None = None,
    max_chars_per_message: int | None = None,
) -> list[dict[str, Any]]:
    """OpenAI-style turns for llama.cpp chat/completions (user / assistant / tool)."""
    cap = max_messages if max_messages is not None else CHAT_HISTORY_MAX_MESSAGES
    char_cap = max_chars_per_message if max_chars_per_message is not None else CHAT_MESSAGE_MAX_CHARS
    if not messages:
        return []
    out: list[dict[str, Any]] = []
    for msg in messages[-cap:]:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "").lower()
        if role not in _ALLOWED_ROLES:
            continue
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        entry: dict[str, Any] = {
            "role": role,
            "content": truncate_text(content, char_cap, note="history trimmed"),
        }
        if role == "tool":
            entry["name"] = str(msg.get("name") or "apex_api")[:64]
            entry["tool_call_id"] = str(msg.get("tool_call_id") or "apex_api_turn")[:64]
        out.append(entry)
    return out


def load_chat_messages(user_id: str, session_id: str) -> list[dict[str, Any]]:
    """Role-structured session history (Chroma summary), not the full raw log."""
    from apex_rag_demo.rag.chat_summary import load_role_summary_messages

    return load_role_summary_messages(user_id, session_id)


def build_tool_message_content(state: dict[str, Any]) -> str | None:
    intent = str(state.get("intent") or "").strip()
    if not intent:
        return None
    plan = state.get("action_plan")
    trace = state.get("api_trace")
    lines = [f"intent: {intent}"]
    if isinstance(trace, list) and trace:
        lines.append(f"orchestrator_steps: {len(trace)}")
    if isinstance(plan, dict) and plan:
        lines.append(f"plan: {json.dumps(plan, default=str)[:600]}")
    err = state.get("api_error")
    if err:
        lines.append(f"api_error: {str(err)[:500]}")
    else:
        payload = state.get("api_payload")
        if isinstance(payload, dict):
            slim = {
                k: v
                for k, v in payload.items()
                if not str(k).startswith("_") and k not in ("event", "events", "primary")
            }
            if slim:
                lines.append(f"api_payload: {json.dumps(slim, default=str)[:600]}")
    return truncate_text("\n".join(lines), 900, note="tool summary trimmed")


def append_chat_turn(
    user_id: str,
    session_id: str,
    question: str,
    answer: str,
    *,
    tool_content: str | None = None,
) -> None:
    if not user_id or not session_id:
        return
    user_text = strip_ui_region(question).strip()
    assistant_text = str(answer or "").strip()
    if not user_text:
        return

    _GRAPH_STATE_DIR.mkdir(parents=True, exist_ok=True)
    user_dir = _GRAPH_STATE_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    path = _session_path(user_id, session_id)

    store: dict[str, Any] = {}
    if path.is_file():
        try:
            store = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            store = {}

    messages = store.get("messages")
    if not isinstance(messages, list):
        messages = []

    store_cap = CHAT_MESSAGE_MAX_CHARS
    tool_cap = min(800, CHAT_MESSAGE_MAX_CHARS_ROUTING)
    messages.append(
        {
            "role": "user",
            "content": truncate_text(user_text, store_cap, note="history trimmed"),
        },
    )
    if tool_content:
        messages.append(
            {
                "role": "tool",
                "name": "apex_api",
                "tool_call_id": f"apex_{len(messages)}",
                "content": truncate_text(tool_content, tool_cap, note="tool summary trimmed"),
            },
        )
    if assistant_text:
        messages.append(
            {
                "role": "assistant",
                "content": truncate_text(assistant_text, store_cap, note="history trimmed"),
            },
        )

    store["messages"] = normalize_chat_history(messages, max_messages=CHAT_RAW_LOG_MAX_MESSAGES)
    try:
        path.write_text(json.dumps(store, default=str), encoding="utf-8")
    except OSError:
        pass

    from apex_rag_demo.rag.chat_summary import refresh_session_chat_summary

    refresh_session_chat_summary(user_id, session_id)
