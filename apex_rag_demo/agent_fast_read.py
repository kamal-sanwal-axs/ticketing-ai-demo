"""Deterministic single-step read orchestration (skip orchestrator LLM when intent is clear)."""

from __future__ import annotations

from typing import Any

from apex_rag_demo.config import INTENT_SEMANTIC_MIN_SCORE
from apex_rag_demo.crud_policy import WriteKind, write_kind_for_intent
from apex_rag_demo.id_prompts import clarify_missing_event_id, guard_intent_needs_event_id
from apex_rag_demo.intent_helpers import guard_api_intent
from apex_rag_demo.planning import INTENTS, plan_for_intent

_SINGLE_STEP_READ = frozenset(
    {
        "marketing_events",
        "search_events",
        "search_orders",
        "search_order_payment_statuses",
        "search_customers",
        "list_client_venues",
        "list_users",
        "list_marketing_pixels",
        "get_event",
        "inventory_zones",
        "get_venue_config",
        "b2b_flash_report",
        "reports_inventory_event",
        "reports_timezones",
    },
)


def try_deterministic_orchestrator_step(
    question: str,
    *,
    classified_intent: str,
    semantic_intent_hint: str | None,
    semantic_score: float,
    api_trace: list[dict[str, Any]] | None,
    session_focus: dict[str, Any] | None,
    chroma_system_context: str | None = None,
    semantic_context_block: str | None = None,
    chat_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if api_trace:
        return None

    from apex_rag_demo.dynamic_tools import (
        dynamic_tools_enabled,
        get_dynamic_tool,
        parameters_to_action_plan,
        resolve_dynamic_tool_id,
    )

    if dynamic_tools_enabled():
        tool_id = resolve_dynamic_tool_id(question)
        if tool_id:
            tool = get_dynamic_tool(tool_id)
            if tool and write_kind_for_intent(tool.legacy_intent) == WriteKind.READ:
                intent = guard_api_intent(tool.legacy_intent, question)
                if intent == tool.legacy_intent:
                    plan = parameters_to_action_plan(tool, {}, question)
                    print(
                        f"--- ORCHESTRATOR dynamic tool {tool_id} → {intent} (no LLM) ---",
                        flush=True,
                    )
                    return {
                        "orchestrator_action": "call_api",
                        "intent": intent,
                        "action_plan": plan,
                        "orchestrator_reason": "dynamic_openapi_tool",
                    }

    intent = guard_api_intent(classified_intent, question)
    intent = guard_intent_needs_event_id(intent, question, session_focus)

    from apex_rag_demo.agentic_event import (
        looks_like_any_event_inventory_demo,
        looks_like_event_or_venue_detail_with_id,
    )

    if clarify_missing_event_id(intent, question, session_focus=session_focus):
        if not (
            looks_like_any_event_inventory_demo(question)
            or looks_like_event_or_venue_detail_with_id(question)
        ):
            return {
                "orchestrator_action": "finish",
                "intent": "explain",
                "action_plan": {},
                "orchestrator_reason": "missing_event_id",
                "needs_id_clarification": True,
            }

    if intent not in INTENTS or write_kind_for_intent(intent) != WriteKind.READ:
        return None
    if intent not in _SINGLE_STEP_READ:
        return None

    if classified_intent != intent:
        return None
    if (
        not semantic_intent_hint
        or semantic_intent_hint != intent
        or semantic_score < INTENT_SEMANTIC_MIN_SCORE
    ):
        return None

    plan = plan_for_intent(
        intent,
        question,
        session_focus,
        chroma_system_context=chroma_system_context,
        semantic_context_block=semantic_context_block,
        chat_history=chat_history,
    )
    print(f"--- ORCHESTRATOR deterministic read intent={intent} (no LLM) ---", flush=True)
    return {
        "orchestrator_action": "call_api",
        "intent": intent,
        "action_plan": plan,
        "orchestrator_reason": "deterministic_single_step_read",
    }
