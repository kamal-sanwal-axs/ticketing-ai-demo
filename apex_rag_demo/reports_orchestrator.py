"""Deterministic orchestration for B2B reports (before agentic get_event loops)."""

from __future__ import annotations

from typing import Any

from apex_rag_demo.crud_policy import WriteKind, write_kind_for_intent
from apex_rag_demo.intent_helpers import guard_api_intent
from apex_rag_demo.planning import plan_for_intent
from apex_rag_demo.reports_intent_helpers import (
    enrich_reports_plan_from_question,
    extract_report_numeric_ids_from_event_payload,
    looks_like_b2b_reports_question,
    looks_like_vague_report_request,
    resolve_reports_guard_intent,
)


def try_reports_orchestrator_step(
    question: str,
    *,
    classified_intent: str,
    api_trace: list[dict[str, Any]] | None,
    session_focus: dict[str, Any] | None,
    chroma_system_context: str | None = None,
    semantic_context_block: str | None = None,
    chat_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    report_intent = resolve_reports_guard_intent(question)
    if not report_intent:
        return None
    if write_kind_for_intent(report_intent) != WriteKind.READ:
        return None

    trace = list(api_trace or [])

    # After get_event, promote to reports when numeric ids appear on the payload.
    if trace and trace[-1].get("intent") == "get_event":
        payload = trace[-1].get("payload")
        if isinstance(payload, dict):
            ctx, ev = extract_report_numeric_ids_from_event_payload(payload)
            if ctx is not None or ev is not None:
                intent = guard_api_intent(report_intent, question)
                plan = plan_for_intent(
                    intent,
                    question,
                    session_focus,
                    chroma_system_context=chroma_system_context,
                    semantic_context_block=semantic_context_block,
                    chat_history=chat_history,
                )
                plan = enrich_reports_plan_from_question(intent, plan, question)
                if ctx is not None:
                    plan["contextId"] = ctx
                if ev is not None:
                    plan["eventId"] = ev
                print(
                    f"--- ORCHESTRATOR reports after get_event → {intent} "
                    f"(contextId={plan.get('contextId')} eventId={plan.get('eventId')}) ---",
                    flush=True,
                )
                return {
                    "orchestrator_action": "call_api",
                    "intent": intent,
                    "action_plan": plan,
                    "orchestrator_reason": "reports_after_event_lookup",
                }

    if trace:
        return None

    from apex_rag_demo.dynamic_tools import (
        dynamic_tools_enabled,
        get_dynamic_tool,
        parameters_to_action_plan,
        resolve_dynamic_tool_id,
    )

    intent = guard_api_intent(report_intent, question)
    if intent != report_intent and resolve_reports_guard_intent(question) != intent:
        intent = report_intent

    if dynamic_tools_enabled():
        tool_id = resolve_dynamic_tool_id(question)
        if tool_id:
            tool = get_dynamic_tool(tool_id)
            if tool and tool.legacy_intent in (
                "b2b_flash_report",
                "reports_inventory_event",
                "reports_timezones",
            ):
                intent = tool.legacy_intent
                plan = parameters_to_action_plan(tool, {}, question)
                print(
                    f"--- ORCHESTRATOR reports dynamic tool {tool_id} → {intent} (no LLM) ---",
                    flush=True,
                )
                return {
                    "orchestrator_action": "call_api",
                    "intent": intent,
                    "action_plan": plan,
                    "orchestrator_reason": "reports_dynamic_tool",
                }

    plan = plan_for_intent(
        intent,
        question,
        session_focus,
        chroma_system_context=chroma_system_context,
        semantic_context_block=semantic_context_block,
        chat_history=chat_history,
    )
    plan = enrich_reports_plan_from_question(intent, plan, question)
    if looks_like_vague_report_request(question):
        plan["_report_catalog"] = True

    print(f"--- ORCHESTRATOR reports read intent={intent} (no LLM) ---", flush=True)
    return {
        "orchestrator_action": "call_api",
        "intent": intent,
        "action_plan": plan,
        "orchestrator_reason": "reports_single_step",
    }
