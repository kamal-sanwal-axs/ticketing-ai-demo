"""Multi-part operator asks: list events + per-event inventory / seat-level detail."""

from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.event_list import event_display_name, event_table_rows, iter_event_dicts, unwrap_event_payload
from apex_rag_demo.inventory_display import build_inventory_sections
from apex_rag_demo.org_hierarchy import get_hierarchy_index
from apex_rag_demo.planning import plan_for_intent
from apex_rag_demo.response_formatters import strip_ui_region

_MAX_INVENTORY_EVENTS = 2

_SEAT_LEVEL_DETAIL_RE = re.compile(
    r"("
    r"\bseat(s)?\s+sold\b|\bsold\s+seats?\b|"
    r"\bprice\s*codes?\b|\bticket\s+types?\b|"
    r"\bseat[- ]lev\w*\b|\bprice\s+levels?\b|"
    r"\b(all\s+other|other)\b.*\b(info|detail)\b|"
    r"\bsections?\b.*\b(inventory|zone)\b|"
    r"\b(inventory|zones?)\b.*\b(detail|info)\b"
    r")",
    re.I,
)

_EVENTS_CATALOG_RE = re.compile(
    r"("
    r"\b(show|list|get)\b.*\bevents?\b|"
    r"\bevents?\b.*\b(published|on[- ]?sale|live|catalog)\b|"
    r"\b(published|on[- ]?sale|live)\b.*\bevents?\b"
    r")",
    re.I,
)


def looks_like_events_plus_seat_level_detail(question: str) -> bool:
    bare = strip_ui_region(question)
    if _EVENTS_CATALOG_RE.search(bare) and _SEAT_LEVEL_DETAIL_RE.search(bare):
        return True
    from apex_rag_demo.agentic_event import looks_like_any_event_inventory_demo

    return looks_like_any_event_inventory_demo(question)


def is_compound_operational_request(question: str) -> bool:
    """Multi-step catalog + inventory — never conversational / never docs-only explain."""
    return looks_like_events_plus_seat_level_detail(question)


def compound_plan_chunks(question: str) -> list[str]:
    return [
        "List published / on-sale events (marketing-api, lifecycle filter).",
        "For each selected event, load events-api record + inventory-api "
        "(zones, price codes, ticket types, sections — seat-level detail).",
        "Summarize sold capacity from inventory publish-data when the API returns it.",
    ]


def _event_ids_from_marketing_payload(payload: dict[str, Any] | None, limit: int = _MAX_INVENTORY_EVENTS) -> list[str]:
    if not payload:
        return []
    ids: list[str] = []
    for ev in iter_event_dicts(payload):
        eid = str(ev.get("id") or ev.get("eventId") or "").strip()
        if eid and eid not in ids:
            ids.append(eid)
        if len(ids) >= limit:
            break
    return ids


def _fetched_event_ids(api_trace: list[dict[str, Any]] | None) -> set[str]:
    out: set[str] = set()
    for step in api_trace or []:
        if step.get("intent") != "get_event":
            continue
        plan = step.get("plan") if isinstance(step.get("plan"), dict) else {}
        eid = str(plan.get("eventId") or "").strip()
        if eid:
            out.add(eid)
    return out


def try_compound_orchestrator_step(
    question: str,
    *,
    api_trace: list[dict[str, Any]] | None,
    session_focus: dict[str, Any] | None,
    chroma_system_context: str | None = None,
    semantic_context_block: str | None = None,
    chat_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not looks_like_events_plus_seat_level_detail(question):
        return None

    trace = list(api_trace or [])

    if not trace:
        plan = plan_for_intent(
            "marketing_events",
            question,
            session_focus,
            chroma_system_context=chroma_system_context,
            semantic_context_block=semantic_context_block,
            chat_history=chat_history,
        )
        plan["_compound"] = True
        from apex_rag_demo.chat_progress import emit_progress

        emit_progress("compound_list_events")
        print("--- ORCHESTRATOR compound step 1: marketing_events (published list) ---", flush=True)
        return {
            "orchestrator_action": "call_api",
            "intent": "marketing_events",
            "action_plan": plan,
            "orchestrator_reason": "compound_1_published_events",
        }

    marketing_steps = [s for s in trace if s.get("intent") == "marketing_events"]
    if not marketing_steps:
        return None

    last_list = marketing_steps[-1].get("payload")
    if not isinstance(last_list, dict):
        return {
            "orchestrator_action": "finish",
            "intent": "marketing_events",
            "orchestrator_reason": "compound_list_failed",
        }

    fetched = _fetched_event_ids(trace)
    for eid in _event_ids_from_marketing_payload(last_list):
        if eid in fetched:
            continue
        plan = {
            "eventId": eid,
            "includeInventory": True,
            "includeTicketTypes": True,
            "_compound": True,
        }
        from apex_rag_demo.chat_progress import emit_progress

        emit_progress("compound_event_inventory")
        print(f"--- ORCHESTRATOR compound step: get_event+inventory {eid[:8]}… ---", flush=True)
        return {
            "orchestrator_action": "call_api",
            "intent": "get_event",
            "action_plan": plan,
            "orchestrator_reason": "compound_2_event_inventory",
        }

    return {
        "orchestrator_action": "finish",
        "intent": "marketing_events",
        "orchestrator_reason": "compound_complete",
    }


def format_compound_answer(question: str, api_trace: list[dict[str, Any]] | None) -> str:
    trace = api_trace or []
    lines = ["Multi-step request (live APIs):"]
    for i, chunk in enumerate(compound_plan_chunks(question)):
        lines.append(f"{i + 1}. {chunk}")
    lines.append("")
    for step in trace:
        intent = step.get("intent")
        err = step.get("error")
        if err:
            lines.append(f"• {intent}: error — {err}")
            continue
        payload = step.get("payload")
        if intent == "marketing_events" and isinstance(payload, dict):
            lf = payload.get("_lifecycle_filter")
            if isinstance(lf, dict):
                lines.append(
                    f"• Events list: {lf.get('_matched', '?')} row(s) after lifecycle filter "
                    f"({lf.get('description', 'filter')}).",
                )
            else:
                rows = event_table_rows(payload)
                lines.append(f"• Events list: {len(rows)} row(s).")
        if intent == "get_event" and isinstance(payload, dict):
            ev = unwrap_event_payload(payload)
            name = event_display_name(ev) if ev else "Event"
            eid = str(ev.get("id") or "—")
            inv = payload.get("_inventory")
            lines.append(f"• Inventory detail for **{name}** (`{eid}`).")
            if isinstance(inv, dict) and inv.get("_fetch_errors"):
                lines.append(f"  Inventory partial: {inv['_fetch_errors'][0]}")
    lines.append("")
    lines.append("See the tables below for price codes, ticket types, and zones.")
    return "\n".join(lines)


def build_compound_display(state: dict[str, Any]) -> dict[str, Any] | None:
    question = str(state.get("question") or "")
    trace = state.get("api_trace") or []
    if not looks_like_events_plus_seat_level_detail(question) or not trace:
        return None

    hierarchy = get_hierarchy_index()
    sections: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    lifecycle_note = ""

    for step in trace:
        if step.get("intent") != "marketing_events":
            continue
        payload = step.get("payload")
        if not isinstance(payload, dict):
            continue
        event_rows = event_table_rows(payload, hierarchy=hierarchy)
        lf = payload.get("_lifecycle_filter")
        if isinstance(lf, dict):
            lifecycle_note = str(lf.get("description") or "")
            matched = lf.get("_matched")
            total = lf.get("_total_before_filter")
            if matched is not None and total is not None:
                lifecycle_note += f" — {matched} of {total} fetched."

    sections.append(
        {
            "title": "Step 1 — Published / on-sale events",
            "paragraphs": [lifecycle_note] if lifecycle_note else [],
            "table": {
                "columns": [
                    {"key": "name", "label": "Event"},
                    {"key": "startDate", "label": "Start"},
                    {"key": "endDate", "label": "End"},
                    {"key": "status", "label": "Status"},
                    {"key": "id", "label": "Event ID"},
                ],
                "rows": event_rows[:25],
            },
        },
    )

    inv_sections_added = 0
    for step in trace:
        if step.get("intent") != "get_event":
            continue
        payload = step.get("payload")
        if not isinstance(payload, dict):
            continue
        ev = unwrap_event_payload(payload)
        inv = payload.get("_inventory")
        title = f"Step 2+ — Seat-level inventory · {event_display_name(ev) if ev else 'Event'}"
        block_sections = build_inventory_sections(inv if isinstance(inv, dict) else None)
        sections.append(
            {
                "title": title,
                "paragraphs": [
                    f"Event ID: {ev.get('id') if ev else '—'} · "
                    "Price codes, ticket types, sections from inventory-api (publish-data / primary zone).",
                ],
                "sections": block_sections,
            },
        )
        inv_sections_added += 1

    chunks = compound_plan_chunks(question)
    from apex_rag_demo.ui_schema import orchestration_trace_sections

    trace_sections = orchestration_trace_sections(trace)
    return {
        "type": "dashboard",
        "title": "Published events + inventory detail",
        "badge": "compound",
        "level": "info",
        "paragraphs": [
            "Your question spans event catalog and seat-level inventory. "
            "The assistant ran these steps against apex-dev:",
            *[f"• {c}" for c in chunks],
        ],
        "sections": trace_sections + sections,
        "count": len(event_rows),
        "footnote": (
            f"Loaded inventory for {inv_sections_added} event(s) "
            f"(max {_MAX_INVENTORY_EVENTS} per request). "
            "Ask follow-up with a specific event UUID for deeper detail."
        ),
    }
