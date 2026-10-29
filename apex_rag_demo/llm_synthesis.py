from __future__ import annotations

import json
from typing import Any

from apex_rag_demo.clients.llama import chat_completion
from apex_rag_demo.response_formatters import strip_ui_region

APEX_ASSISTANT_SYSTEM = """You are the APEX AI assistant (system role: internal ticketing operations).

Rules:
- Answer using ONLY the JSON context blocks provided (events-api, search-api, admin, inventory).
- If the user's id was a client-venue id, say so clearly and summarize the venue and related events.
- If events-api returned 404 but search found data, explain the correct id type and list matches.
- Do not invent event ids, prices, inventory, or org names not present in context.
- Do not mention LangGraph, intents, embeddings, or internal routing.
- Prefer bullet lists for multiple events. Max 8 short paragraphs."""


def _trim_json(data: Any, max_chars: int = 12000) -> str:
    text = json.dumps(data, indent=2, default=str)
    if len(text) > max_chars:
        return text[: max_chars - 20] + "\n…(truncated)"
    return text


def synthesize_apex_answer(
    question: str,
    intent: str,
    *,
    api_payload: dict[str, Any] | None,
    api_error: str | None,
    kb_snippets: list[str] | None = None,
    session_snippets: list[str] | None = None,
    action_plan: dict[str, Any] | None = None,
    chroma_system_context: str | None = None,
    semantic_context_block: str | None = None,
    topic_shift: bool = False,
    chat_history: list[dict[str, Any]] | None = None,
) -> str:
    bare = strip_ui_region(question)
    blocks: list[str] = [f"User question: {bare}", f"Routed intent: {intent}"]
    if action_plan:
        blocks.append(f"Action plan: {json.dumps(action_plan, default=str)}")
    if api_error:
        blocks.append(f"Primary API error: {api_error}")
    if api_payload:
        if isinstance(api_payload, dict) and api_payload.get("orchestrator_trace"):
            blocks.append(
                "Orchestrator API trace (LangGraph executed these calls for you):\n"
                + _trim_json(api_payload.get("orchestrator_trace")),
            )
            last = api_payload.get("last")
            if last:
                blocks.append(f"Latest API payload:\n{_trim_json(last)}")
        if isinstance(api_payload, dict) and api_payload.get("publishContext"):
            blocks.append(
                "Publish failure context (from events-api, authoritative):\n"
                + _trim_json(api_payload.get("publishContext")),
            )
        blocks.append(f"API context JSON:\n{_trim_json(api_payload)}")
    if kb_snippets:
        blocks.append("KB snippets (reference only):\n" + "\n".join(f"- {s}" for s in kb_snippets[:3]))
    if session_snippets and not topic_shift:
        blocks.append(
            "Session memory (Chroma semantic search, prior turns in this tab):\n"
            + "\n---\n".join(session_snippets[:3]),
        )

    user = "\n\n".join(blocks)
    return chat_completion(
        APEX_ASSISTANT_SYSTEM,
        user,
        chroma_system_context=chroma_system_context,
        semantic_turn_context=semantic_context_block,
        history=chat_history,
    )
