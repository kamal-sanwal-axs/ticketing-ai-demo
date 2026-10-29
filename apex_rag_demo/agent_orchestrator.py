from __future__ import annotations

import json
from typing import Any

from apex_rag_demo.clients.llama import chat_completion
from apex_rag_demo.config import CHAT_TEMPERATURE_ROUTING, ORCHESTRATOR_MAX_ROUNDS
from apex_rag_demo.crud_registry import CRUD_CATALOG
from apex_rag_demo.intent_helpers import guard_api_intent
from apex_rag_demo.intent_semantic import is_conversational_message
from apex_rag_demo.planning import INTENTS, _parse_json_object, plan_for_intent
from apex_rag_demo.response_formatters import strip_ui_region

_ORCHESTRATOR_SYSTEM = f"""You are the LangGraph orchestrator for APEX ticketing APIs.
You decide the NEXT step: call a live API, or finish and let the answer LLM use results you already collected.

Return JSON only:
{{
  "action": "call_api" | "call_plugin" | "run_sandbox" | "finish",
  "tool_id": "<dynamic tool id from catalog, preferred>",
  "parameters": {{ ... request fields: pageSize, query, keyword, eventId, ... }},
  "intent": "<legacy intent fallback if no tool_id>",
  "plan": {{ ... same as parameters when using tool_id ... }},
  "plugin_id": "<user plugin id when action is call_plugin>",
  "plugin_parameters": {{ ... }},
  "reason": "short why"
}}

Rules:
- Prefer tool_id + parameters from the dynamic OpenAPI catalog (not inventing URLs).
- Fan orders need email/order number; event catalog/list uses marketing GET /v1/events tool when listed.
- You may chain calls up to {ORCHESTRATOR_MAX_ROUNDS} rounds.
- Use call_plugin only for registered user plugins.
- Use run_sandbox for custom Python or React+Recharts code in Docker (see sandbox block below)."""


def _api_catalog_block(
    question: str = "",
    *,
    classified_intent: str = "",
    semantic_intent_hint: str | None = None,
) -> str:
    from apex_rag_demo.dynamic_tools import dynamic_tools_enabled, tool_catalog_for_orchestrator

    lines: list[str] = []
    if dynamic_tools_enabled():
        lines.append(
            tool_catalog_for_orchestrator(
                question,
                classified_intent=classified_intent,
                semantic_intent_hint=semantic_intent_hint,
            ),
        )
    lines.append("Callable intents (legacy fallback → HTTP wrappers):")
    for entry in CRUD_CATALOG:
        lines.append(f"- {entry.intent}: {entry.http} ({entry.summary})")
    lines.append("Also: search_events, list_client_venues, marketing_events (wired in demo).")
    return "\n".join(lines)


def _trace_block(api_trace: list[dict[str, Any]]) -> str:
    if not api_trace:
        return "api_trace: (empty — no API calls yet)"
    return "api_trace:\n" + json.dumps(api_trace, default=str, indent=2)[:4500]


def decide_orchestrator_step(
    question: str,
    *,
    classified_intent: str,
    session_focus: dict[str, Any] | None,
    api_trace: list[dict[str, Any]] | None,
    orchestrator_round: int,
    user_id: str = "",
    session_id: str = "",
    chroma_system_context: str | None = None,
    semantic_context_block: str | None = None,
    chat_history: list[dict[str, Any]] | None = None,
    semantic_intent_hint: str | None = None,
    semantic_score: float = 0.0,
) -> dict[str, Any]:
    from apex_rag_demo.plugins.orchestrator_plugins import (
        plugin_catalog_block,
        try_plugin_orchestrator_step,
    )

    plugin_step = try_plugin_orchestrator_step(
        question,
        user_id=user_id,
        api_trace=api_trace,
    )
    if plugin_step:
        return plugin_step

    from apex_rag_demo.compound_request import try_compound_orchestrator_step

    compound = try_compound_orchestrator_step(
        question,
        api_trace=api_trace,
        session_focus=session_focus,
        chroma_system_context=chroma_system_context,
        semantic_context_block=semantic_context_block,
        chat_history=chat_history,
    )
    if compound:
        return compound

    from apex_rag_demo.marketing_list_followup import try_marketing_list_followup_step

    marketing_followup = try_marketing_list_followup_step(
        question,
        session_focus=session_focus,
        user_id=user_id,
        session_id=session_id,
    )
    if marketing_followup:
        return marketing_followup

    from apex_rag_demo.reports_orchestrator import try_reports_orchestrator_step

    reports_step = try_reports_orchestrator_step(
        question,
        classified_intent=classified_intent,
        api_trace=api_trace,
        session_focus=session_focus,
        chroma_system_context=chroma_system_context,
        semantic_context_block=semantic_context_block,
        chat_history=chat_history,
    )
    if reports_step:
        return reports_step

    from apex_rag_demo.sandbox_toolkit.orchestrator import try_sandbox_orchestrator_step

    sandbox_step = try_sandbox_orchestrator_step(question, api_trace=api_trace)
    if sandbox_step:
        return sandbox_step

    from apex_rag_demo.agentic_event import try_agentic_orchestrator_step

    agentic = try_agentic_orchestrator_step(
        question,
        api_trace=api_trace,
        session_focus=session_focus,
        chroma_system_context=chroma_system_context,
        semantic_context_block=semantic_context_block,
        chat_history=chat_history,
    )
    if agentic:
        return agentic

    from apex_rag_demo.reports_orchestrator import try_reports_finish_step

    reports_finish = try_reports_finish_step(
        question,
        api_trace=api_trace,
        session_focus=session_focus,
    )
    if reports_finish:
        return reports_finish

    from apex_rag_demo.agentic_event import try_agentic_finish_step
    from apex_rag_demo.reports_intent_helpers import looks_like_b2b_reports_question

    if looks_like_b2b_reports_question(strip_ui_region(question)):
        return None

    finish = try_agentic_finish_step(
        question,
        api_trace=api_trace,
        session_focus=session_focus,
    )
    if finish:
        return finish

    from apex_rag_demo.agent_fast_read import try_deterministic_orchestrator_step

    fast = try_deterministic_orchestrator_step(
        question,
        classified_intent=classified_intent,
        semantic_intent_hint=semantic_intent_hint,
        semantic_score=semantic_score,
        api_trace=api_trace,
        session_focus=session_focus,
        chroma_system_context=chroma_system_context,
        semantic_context_block=semantic_context_block,
        chat_history=chat_history,
    )
    if fast:
        return fast

    print(f"--- ORCHESTRATOR LLM round={orchestrator_round} ---", flush=True)
    from apex_rag_demo.compound_request import is_compound_operational_request

    if is_conversational_message(question) and not is_compound_operational_request(question):
        return {
            "orchestrator_action": "finish",
            "intent": "explain",
            "orchestrator_reason": "conversational_no_api",
        }
    classified_intent = guard_api_intent(classified_intent, question)
    focus = session_focus or {}
    from apex_rag_demo.sandbox_toolkit.orchestrator import orchestrator_sandbox_catalog_block

    catalog_and_intents = _api_catalog_block(
        question,
        classified_intent=classified_intent,
        semantic_intent_hint=semantic_intent_hint,
    )
    orchestrator_system = (
        f"{_ORCHESTRATOR_SYSTEM}\n\n"
        f"{catalog_and_intents}\n\n"
        f"{plugin_catalog_block(user_id)}\n\n"
        f"{orchestrator_sandbox_catalog_block()}"
    )
    user = (
        f"classified_intent (hint): {classified_intent}\n"
        f"semantic_intent_hint: {semantic_intent_hint or '(none)'} score={semantic_score:.2f}\n"
        f"session_focus: {json.dumps(focus, default=str)[:600]}\n"
        f"round: {orchestrator_round} / max {ORCHESTRATOR_MAX_ROUNDS}\n\n"
        f"{_trace_block(api_trace or [])}\n\n"
        f"User message (authoritative — follow this, not similar history alone):\n"
        f"{strip_ui_region(question)}"
    )
    raw = chat_completion(
        orchestrator_system,
        user,
        temperature=CHAT_TEMPERATURE_ROUTING,
        chroma_system_context=chroma_system_context,
        semantic_turn_context=semantic_context_block,
        history=chat_history,
        routing=True,
    )
    try:
        data = _parse_json_object(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        data = {"action": "call_api", "intent": classified_intent, "plan": {}, "reason": "parse_fallback"}

    from apex_rag_demo.plugins.orchestrator_plugins import parse_call_plugin_from_llm
    from apex_rag_demo.sandbox_toolkit.orchestrator import (
        orchestrator_sandbox_catalog_block,
        parse_sandbox_job_from_llm,
    )

    plugin_decision = parse_call_plugin_from_llm(data)
    if plugin_decision:
        return plugin_decision

    sandbox_job = parse_sandbox_job_from_llm(data)
    if sandbox_job:
        return {
            "orchestrator_action": "run_sandbox",
            "intent": "explain",
            "action_plan": sandbox_job.model_dump(mode="json"),
            "orchestrator_reason": str(data.get("reason") or sandbox_job.reason or "run_sandbox"),
        }

    action = str(data.get("action") or "finish").strip().lower()
    intent = str(data.get("intent") or classified_intent).strip().lower()
    if intent not in INTENTS:
        intent = classified_intent
    plan = data.get("plan") if isinstance(data.get("plan"), dict) else {}
    params = data.get("parameters") if isinstance(data.get("parameters"), dict) else {}
    tool_id = str(data.get("tool_id") or plan.get("tool_id") or "").strip()

    from apex_rag_demo.dynamic_tools import (
        dynamic_tools_enabled,
        get_dynamic_tool,
        parameters_to_action_plan,
        tool_matches_question,
    )

    if dynamic_tools_enabled() and tool_id:
        tool = get_dynamic_tool(tool_id)
        if tool and not tool_matches_question(tool, question):
            tool_id = ""
            plan = data.get("plan") if isinstance(data.get("plan"), dict) else {}
        elif tool:
            intent = tool.legacy_intent
            plan = parameters_to_action_plan(tool, params or plan, question)

    if intent not in INTENTS:
        intent = classified_intent
    intent = guard_api_intent(intent, question)

    if dynamic_tools_enabled() and not tool_id:
        from apex_rag_demo.dynamic_tools import resolve_dynamic_tool_id

        resolved_tool = resolve_dynamic_tool_id(question)
        if resolved_tool:
            tool = get_dynamic_tool(resolved_tool)
            if tool:
                tool_id = resolved_tool
                intent = guard_api_intent(tool.legacy_intent, question)
                plan = parameters_to_action_plan(tool, params or plan, question)

    if not api_trace and classified_intent not in ("explain",) and action != "call_api":
        action = "call_api"
        if not tool_id:
            intent = guard_api_intent(classified_intent, question)
            if not plan:
                plan = {}

    if action == "call_api" and intent != "explain":
        from apex_rag_demo.agentic_event import looks_like_seat_inventory_demo
        from apex_rag_demo.event_query_helpers import get_event_enrichment_flags
        from apex_rag_demo.id_prompts import resolve_event_id

        bare = strip_ui_region(question)
        eid = resolve_event_id(question, plan, session_focus)
        if (
            eid
            and looks_like_seat_inventory_demo(bare)
            and intent in ("search_events", "list_client_venues", "inventory_zones")
        ):
            flags = get_event_enrichment_flags(bare)
            flags.setdefault("includeInventory", True)
            flags.setdefault("includeTicketTypes", True)
            intent = guard_api_intent("get_event", question)
            plan = {"eventId": eid, **flags, **{k: v for k, v in plan.items() if k == "_agentic"}}
        if not plan and not tool_id:
            plan = plan_for_intent(
                intent,
                question,
                session_focus,
                chroma_system_context=chroma_system_context,
                semantic_context_block=semantic_context_block,
                chat_history=chat_history,
            )
        return {
            "orchestrator_action": "call_api",
            "intent": intent,
            "action_plan": plan,
            "orchestrator_reason": str(data.get("reason") or ""),
        }

    return {
        "orchestrator_action": "finish",
        "intent": intent if intent in INTENTS else classified_intent,
        "orchestrator_reason": str(data.get("reason") or "finish"),
    }
