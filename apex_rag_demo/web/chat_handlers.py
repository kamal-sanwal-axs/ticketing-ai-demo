from __future__ import annotations

from apex_rag_demo.help_content import (
    HELP_SUMMARY,
    IDENTITY_SUMMARY,
    WELCOME_SUMMARY,
    is_general_help_question,
)
from apex_rag_demo.compound_request import is_compound_operational_request
from apex_rag_demo.intent_helpers import is_assistant_meta_question, is_greeting
from apex_rag_demo.response_formatters import strip_ui_region
from apex_rag_demo.ui_display import build_ui_display

PHASE_LABELS: dict[str, str] = {
    "compound_list_events": "Step 1 — Listing published / on-sale events (marketing-api)…",
    "compound_event_inventory": "Step 2 — Loading seat-level inventory (price codes, ticket types)…",
    "load_session": "Loading session and chat summary…",
    "chroma_enrich": "Querying Chroma (roles + API docs)…",
    "kg_enrich": "Querying Neo4j knowledge graph…",
    "retrieve_kb": "Retrieving knowledge base (bi-encoder)…",
    "classify_llm": "LLM routing (intent)…",
    "plan_llm": "LLM planning…",
    "execute_api": "Calling APEX APIs…",
    "semantic_turn": "Sentence-transformer topic & intent…",
    "orchestrator_llm": "Orchestrator LLM (next API step)…",
    "orchestrator_api": "LangGraph executing API call…",
    "synthesize_llm": "LLM answering from API data…",
}


def phase_label(phase: str) -> str:
    if phase.startswith("semantic_route|"):
        parts = phase.split("|")
        intent = parts[1].replace("_", " ") if len(parts) > 1 else "route"
        score = parts[2] if len(parts) > 2 else ""
        kind = parts[3] if len(parts) > 3 else ""
        suffix = f" ({score})" if score else ""
        if kind == "compound":
            return f"Semantic (pre-LLM): compound plan · {intent}{suffix}"
        return f"Semantic (pre-LLM): Chroma + embeddings → {intent}{suffix}"
    return PHASE_LABELS.get(phase, phase.replace("_", " "))


def build_chat_response_dict(
    state: dict,
    *,
    question: str,
    session_id: str,
) -> dict:
    display = build_ui_display(state)
    pipeline_error = state.get("pipeline_error") if isinstance(state.get("pipeline_error"), dict) else None
    pending = (state.get("api_payload") or {}) if isinstance(state.get("api_payload"), dict) else {}
    mutation_token = pending.get("mutation_token")
    requires_confirmation = bool(pending.get("_pending_confirmation"))
    summary = state.get("answer") or ""
    if display and display.get("type") == "table" and display.get("count") is not None:
        summary = f"Found {display['count']} result(s)."
    bare_q = strip_ui_region(question)
    if not pipeline_error and display:
        if is_compound_operational_request(bare_q) and display.get("badge") == "compound":
            summary = (state.get("answer") or summary)[:1200]
        elif state.get("intent") == "explain":
            if is_assistant_meta_question(bare_q):
                summary = IDENTITY_SUMMARY
            elif is_greeting(bare_q):
                summary = WELCOME_SUMMARY
            elif is_general_help_question(bare_q):
                summary = HELP_SUMMARY
            elif display.get("paragraphs"):
                summary = str(display["paragraphs"][0])
    if pipeline_error:
        summary = str(pipeline_error.get("summary") or state.get("answer") or summary)
    semantic_routing = None
    if state.get("semantic_routing_label"):
        semantic_routing = {
            "label": state.get("semantic_routing_label"),
            "intent": state.get("semantic_route_intent"),
            "score": state.get("semantic_route_score"),
            "pre_llm": bool(state.get("skip_llm_classify")),
        }
    return {
        "answer": summary,
        "intent": state.get("intent") or "explain",
        "semantic_routing": semantic_routing,
        "display": display,
        "requires_confirmation": requires_confirmation,
        "mutation_token": mutation_token,
        "session_id": session_id,
        "memory_source": state.get("memory_source") or None,
        "error": bool(pipeline_error),
        "error_code": str(pipeline_error.get("code")) if pipeline_error else None,
        "error_message": str(pipeline_error.get("summary")) if pipeline_error else None,
    }
