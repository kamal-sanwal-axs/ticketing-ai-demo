"""Deterministic orchestration for B2B reports (before agentic get_event loops)."""

from __future__ import annotations

from typing import Any

from apex_rag_demo.crud_policy import WriteKind, write_kind_for_intent
from apex_rag_demo.intent_helpers import guard_api_intent
from apex_rag_demo.planning import plan_for_intent
from apex_rag_demo.reports_intent_helpers import (
    enrich_reports_plan_from_question,
    extract_report_numeric_ids_from_event_payload,
    last_trace_report_catalog,
    looks_like_b2b_reports_question,
    looks_like_vague_report_request,
    report_event_uuid,
    reports_plan_needs_numeric_ids,
    resolve_report_ids_from_event,
    resolve_reports_guard_intent,
    trace_has_get_event_for_uuid,
)

_REPORT_INTENTS = frozenset(
    {
        "b2b_flash_report",
        "reports_inventory_event",
        "reports_timezones",
    },
)


def _planning_kwargs(
    *,
    session_focus: dict[str, Any] | None,
    chroma_system_context: str | None,
    semantic_context_block: str | None,
    chat_history: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    return {
        "session_focus": session_focus,
        "chroma_system_context": chroma_system_context,
        "semantic_context_block": semantic_context_block,
        "chat_history": chat_history,
    }


def _build_report_plan(question: str, intent: str, **plan_kw: Any) -> dict[str, Any]:
    kw = dict(plan_kw)
    session_focus = kw.pop("session_focus", None)
    plan = plan_for_intent(intent, question, session_focus, **kw)
    return enrich_reports_plan_from_question(intent, plan, question)


def _get_event_lookup_step(
    question: str,
    *,
    event_uuid: str,
    pending_report_intent: str,
    reason: str,
) -> dict[str, Any]:
    print(
        f"--- ORCHESTRATOR reports: get_event {event_uuid[:8]}… "
        f"then {pending_report_intent} ---",
        flush=True,
    )
    return {
        "orchestrator_action": "call_api",
        "intent": "get_event",
        "action_plan": {
            "eventId": event_uuid,
            "_agentic": True,
            "_reports_chain": True,
            "_pending_report_intent": pending_report_intent,
        },
        "orchestrator_reason": reason,
    }


def _promote_report_after_get_event(
    question: str,
    trace: list[dict[str, Any]],
    *,
    report_intent: str,
    session_focus: dict[str, Any] | None,
    plan_kw: dict[str, Any],
) -> dict[str, Any] | None:
    if not trace or trace[-1].get("intent") != "get_event":
        return None
    payload = trace[-1].get("payload")
    if not isinstance(payload, dict):
        return None
    plan_step = trace[-1].get("plan") if isinstance(trace[-1].get("plan"), dict) else {}
    event_uuid = str(plan_step.get("eventId") or payload.get("id") or "").strip()
    ctx, ev = extract_report_numeric_ids_from_event_payload(payload)
    if (ctx is None or ev is None) and event_uuid:
        rctx, rev, _err = resolve_report_ids_from_event(event_uuid, event_payload=payload)
        if rctx is not None:
            ctx = ctx or rctx
        if rev is not None:
            ev = ev or rev

    pending = str(plan_step.get("_pending_report_intent") or report_intent or "").strip()
    intent = guard_api_intent(pending or report_intent, question)
    plan = _build_report_plan(question, intent, **plan_kw)
    if ctx is not None:
        plan["contextId"] = ctx
    if ev is not None:
        plan["eventId"] = ev
    if event_uuid:
        plan["eventUuid"] = event_uuid
    plan.pop("_report_catalog", None)

    if reports_plan_needs_numeric_ids(intent, plan):
        print(
            f"--- ORCHESTRATOR reports: missing numeric ids after get_event "
            f"(contextId={plan.get('contextId')} eventId={plan.get('eventId')}) ---",
            flush=True,
        )
        plan["_report_catalog"] = True
        plan["_resolve_error"] = (
            "Could not resolve numeric contextId/eventId from the event (including integration). "
            "Try numeric ids in your message or check events-api integration for this event."
        )
        return {
            "orchestrator_action": "call_api",
            "intent": intent,
            "action_plan": plan,
            "orchestrator_reason": "reports_ids_unresolved",
        }

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


def try_reports_finish_step(
    question: str,
    *,
    api_trace: list[dict[str, Any]] | None,
    session_focus: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Finish when a live report call succeeded (avoid LLM filler)."""
    if not looks_like_b2b_reports_question(question):
        return None
    trace = list(api_trace or [])
    for step in reversed(trace):
        intent = str(step.get("intent") or "")
        if intent not in _REPORT_INTENTS:
            continue
        payload = step.get("payload")
        if not isinstance(payload, dict) or payload.get("_report_catalog"):
            continue
        if step.get("api_error"):
            continue
        plan = step.get("plan") if isinstance(step.get("plan"), dict) else {}
        return {
            "orchestrator_action": "finish",
            "intent": intent,
            "action_plan": plan,
            "orchestrator_reason": "reports_api_complete",
        }
    return None


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
    plan_kw = _planning_kwargs(
        session_focus=session_focus,
        chroma_system_context=chroma_system_context,
        semantic_context_block=semantic_context_block,
        chat_history=chat_history,
    )

    promoted = _promote_report_after_get_event(
        question,
        trace,
        report_intent=report_intent,
        session_focus=session_focus,
        plan_kw=plan_kw,
    )
    if promoted:
        return promoted

    intent = guard_api_intent(report_intent, question)
    plan = _build_report_plan(question, intent, **plan_kw)
    event_uuid = report_event_uuid(question, plan, session_focus)

    if event_uuid and reports_plan_needs_numeric_ids(intent, plan):
        if last_trace_report_catalog(trace) and not trace_has_get_event_for_uuid(trace, event_uuid):
            return _get_event_lookup_step(
                question,
                event_uuid=event_uuid,
                pending_report_intent=intent,
                reason="reports_after_catalog_lookup",
            )
        if not trace and not trace_has_get_event_for_uuid(trace, event_uuid):
            return _get_event_lookup_step(
                question,
                event_uuid=event_uuid,
                pending_report_intent=intent,
                reason="reports_event_lookup_first",
            )

    if trace and not last_trace_report_catalog(trace):
        return None

    from apex_rag_demo.dynamic_tools import (
        dynamic_tools_enabled,
        get_dynamic_tool,
        parameters_to_action_plan,
        resolve_dynamic_tool_id,
    )

    if dynamic_tools_enabled() and not trace:
        tool_id = resolve_dynamic_tool_id(question)
        if tool_id:
            tool = get_dynamic_tool(tool_id)
            if tool and tool.legacy_intent in _REPORT_INTENTS:
                intent = tool.legacy_intent
                plan = parameters_to_action_plan(tool, {}, question)
                plan = enrich_reports_plan_from_question(intent, plan, question)
                event_uuid = report_event_uuid(question, plan, session_focus)
                if event_uuid and reports_plan_needs_numeric_ids(intent, plan):
                    return _get_event_lookup_step(
                        question,
                        event_uuid=event_uuid,
                        pending_report_intent=intent,
                        reason="reports_dynamic_tool_lookup",
                    )
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

    if looks_like_vague_report_request(question):
        plan["_report_catalog"] = True

    print(f"--- ORCHESTRATOR reports read intent={intent} (no LLM) ---", flush=True)
    return {
        "orchestrator_action": "call_api",
        "intent": intent,
        "action_plan": plan,
        "orchestrator_reason": "reports_single_step",
    }
