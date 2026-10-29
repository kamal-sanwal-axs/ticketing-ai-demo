from __future__ import annotations

import json
import re
import time
from typing import Any

from apex_rag_demo.config import (
    CHAT_MESSAGE_MAX_CHARS_ROUTING,
    CHAT_RAW_LOG_MAX_MESSAGES,
    CHAT_SUMMARY_LLM_ENABLED,
    CHAT_SUMMARY_MAX_MESSAGES,
    CHROMA_SESSION_COLLECTION,
    SESSION_MEMORY_ENABLED,
)
from apex_rag_demo.prompt_budget import truncate_text
from apex_rag_demo.rag.chat_history import _session_path, normalize_chat_history
from apex_rag_demo.response_formatters import strip_ui_region

_SUMMARY_LLM_SYSTEM = """You compress APEX ticketing chat history for the next LLM call.
Return JSON only with shape: {"messages":[{"role":"user"|"assistant"|"tool","content":"..."}, ...]}

Rules:
- Use only roles user, assistant, tool (no system).
- tool = APEX API intent, plan, and outcome (not user-facing prose).
- assistant = short answer the user saw.
- user = what the user asked.
- Max messages in output: given in the user block. Max ~180 chars per content.
- Keep event UUIDs, AINV codes, publish/get/list intents, and date filters.
- Merge older turns; keep the newest turn detailed."""


def _parse_summary_json(raw: str) -> list[dict[str, Any]] | None:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    block = data.get("messages")
    if not isinstance(block, list):
        return None
    return normalize_chat_history(
        block,
        max_messages=CHAT_SUMMARY_MAX_MESSAGES,
        max_chars_per_message=CHAT_MESSAGE_MAX_CHARS_ROUTING,
    )


def _rule_rollup_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic compression into role-structured turns."""
    if not messages:
        return []

    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    for msg in messages:
        role = str(msg.get("role") or "").lower()
        if role == "user":
            if current:
                groups.append(current)
            current = [msg]
        elif role in ("tool", "assistant"):
            if current:
                current.append(msg)
            else:
                current = [msg]
        else:
            current.append(msg)
    if current:
        groups.append(current)

    if len(groups) <= CHAT_SUMMARY_MAX_MESSAGES:
        return normalize_chat_history(
            [m for g in groups for m in g],
            max_messages=CHAT_SUMMARY_MAX_MESSAGES,
            max_chars_per_message=CHAT_MESSAGE_MAX_CHARS_ROUTING,
        )

    early = groups[:-2]
    recent = groups[-2:]

    user_bits: list[str] = []
    tool_bits: list[str] = []
    asst_bits: list[str] = []
    for g in early:
        for msg in g:
            role = msg.get("role")
            text = str(msg.get("content") or "")[:120]
            if role == "user":
                user_bits.append(text)
            elif role == "tool":
                tool_bits.append(text)
            elif role == "assistant":
                asst_bits.append(text)

    rolled: list[dict[str, Any]] = []
    if user_bits:
        rolled.append(
            {
                "role": "user",
                "content": truncate_text(
                    "Earlier asks: " + " | ".join(user_bits),
                    CHAT_MESSAGE_MAX_CHARS_ROUTING,
                    note="summary",
                ),
            },
        )
    if tool_bits:
        rolled.append(
            {
                "role": "tool",
                "name": "apex_api",
                "tool_call_id": "apex_summary",
                "content": truncate_text(
                    "Earlier API: " + " | ".join(tool_bits),
                    CHAT_MESSAGE_MAX_CHARS_ROUTING,
                    note="summary",
                ),
            },
        )
    if asst_bits:
        rolled.append(
            {
                "role": "assistant",
                "content": truncate_text(
                    "Earlier replies: " + " | ".join(asst_bits),
                    CHAT_MESSAGE_MAX_CHARS_ROUTING,
                    note="summary",
                ),
            },
        )
    for g in recent:
        rolled.extend(g)
    return normalize_chat_history(
        rolled,
        max_messages=CHAT_SUMMARY_MAX_MESSAGES,
        max_chars_per_message=CHAT_MESSAGE_MAX_CHARS_ROUTING,
    )


def _llm_refresh_summary(
    prior: list[dict[str, Any]],
    latest_turn: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    if not CHAT_SUMMARY_LLM_ENABLED:
        return None
    from apex_rag_demo.clients.llama import chat_completion

    user = (
        f"Max output messages: {CHAT_SUMMARY_MAX_MESSAGES}\n\n"
        f"Previous summary JSON:\n{json.dumps({'messages': prior}, ensure_ascii=False)[:3500]}\n\n"
        f"New turn to merge:\n{json.dumps({'messages': latest_turn}, ensure_ascii=False)[:2000]}"
    )
    try:
        raw = chat_completion(
            _SUMMARY_LLM_SYSTEM,
            user,
            routing=True,
            history=None,
            chroma_system_context=None,
        )
        parsed = _parse_summary_json(raw)
        if parsed:
            return parsed
    except Exception:  # noqa: BLE001 — demo boundary
        return None
    return None


def _persist_summary_chroma(
    user_id: str,
    session_id: str,
    summary_messages: list[dict[str, Any]],
) -> None:
    if not SESSION_MEMORY_ENABLED or not user_id or not session_id:
        return
    from apex_rag_demo.rag.embeddings import embed_texts
    from apex_rag_demo.rag.session_memory import _ensure_collection, _scoped_id

    doc_lines = ["Session chat summary (role-structured):"]
    for msg in summary_messages:
        role = msg.get("role", "?")
        content = str(msg.get("content") or "")[:400]
        doc_lines.append(f"[{role}] {content}")
    doc = "\n".join(doc_lines)[:4000]
    summary_json = json.dumps(summary_messages, ensure_ascii=False)[:3500]

    try:
        collection = _ensure_collection(
            CHROMA_SESSION_COLLECTION,
            "Per-user session intent memory",
        )
        sid = _scoped_id(user_id, session_id, "chat-summary")
        collection.upsert(
            ids=[sid],
            documents=[doc],
            embeddings=embed_texts([doc]),
            metadatas=[
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "record_type": "chat_summary",
                    "summary_json": summary_json,
                    "ts": int(time.time()),
                },
            ],
        )
        print(
            f"--- CHROMA chat summary upsert roles={len(summary_messages)} ---",
            flush=True,
        )
    except Exception:
        pass


def _load_summary_chroma(user_id: str, session_id: str) -> list[dict[str, Any]]:
    if not SESSION_MEMORY_ENABLED or not user_id or not session_id:
        return []
    from apex_rag_demo.rag.session_memory import _ensure_collection, _scoped_id

    try:
        collection = _ensure_collection(
            CHROMA_SESSION_COLLECTION,
            "Per-user session intent memory",
        )
        sid = _scoped_id(user_id, session_id, "chat-summary")
        got = collection.get(ids=[sid], include=["metadatas"])
        metas = (got.get("metadatas") or [[]])[0]
        if not metas:
            return []
        meta = metas[0] if isinstance(metas, list) else metas
        raw_json = (meta or {}).get("summary_json")
        if not raw_json:
            return []
        data = json.loads(str(raw_json))
        if isinstance(data, list):
            return normalize_chat_history(
                data,
                max_messages=CHAT_SUMMARY_MAX_MESSAGES,
                max_chars_per_message=CHAT_MESSAGE_MAX_CHARS_ROUTING,
            )
    except Exception:
        return []
    return []


def refresh_session_chat_summary(user_id: str, session_id: str) -> list[dict[str, Any]]:
    """Rebuild role-structured summary from raw log; store locally + Chroma."""
    path = _session_path(user_id, session_id)
    if not path.is_file():
        return []
    try:
        store = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    raw = store.get("messages")
    if not isinstance(raw, list) or not raw:
        store["summary_messages"] = []
        return []

    raw = normalize_chat_history(raw, max_messages=CHAT_RAW_LOG_MAX_MESSAGES)
    store["messages"] = raw

    prior = store.get("summary_messages")
    if not isinstance(prior, list):
        prior = []

    latest_turn: list[dict[str, Any]] = []
    if len(raw) >= 1:
        # last group: user (+ optional tool, assistant)
        idx = len(raw) - 1
        while idx >= 0 and raw[idx].get("role") != "user":
            idx -= 1
        if idx >= 0:
            latest_turn = raw[idx:]

    summary = _llm_refresh_summary(prior, latest_turn)
    if not summary or len(summary) < 2:
        summary = _rule_rollup_messages(raw)

    store["summary_messages"] = summary
    try:
        path.write_text(json.dumps(store, default=str), encoding="utf-8")
    except OSError:
        pass

    _persist_summary_chroma(user_id, session_id, summary)
    return summary


def load_role_summary_messages(user_id: str, session_id: str) -> list[dict[str, Any]]:
    """History for LLM: Chroma-backed role summary (not verbatim log)."""
    if not user_id or not session_id:
        return []
    path = _session_path(user_id, session_id)
    summary: list[dict[str, Any]] = []
    if path.is_file():
        try:
            store = json.loads(path.read_text(encoding="utf-8"))
            block = store.get("summary_messages")
            if isinstance(block, list) and block:
                summary = normalize_chat_history(
                    block,
                    max_messages=CHAT_SUMMARY_MAX_MESSAGES,
                    max_chars_per_message=CHAT_MESSAGE_MAX_CHARS_ROUTING,
                )
        except (json.JSONDecodeError, OSError):
            summary = []

    if not summary:
        summary = _load_summary_chroma(user_id, session_id)

    if summary:
        print(
            f"--- CHAT history via role summary ({len(summary)} messages) ---",
            flush=True,
        )
    return summary
