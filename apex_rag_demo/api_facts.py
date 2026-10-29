"""Structured facts from API payloads for grounded answers (no generative invention)."""

from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.event_list import event_table_rows

_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.I,
)


def _facts_from_payload(intent: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"intent": intent, "events": [], "uuids": [], "error": None}

    rows = event_table_rows(payload)
    uuids = sorted({r["id"] for r in rows if r.get("id") and r["id"] != "—"})
    uuids.extend(_UUID_RE.findall(str(payload)))
    uuids = sorted(set(uuids))

    lifecycle = payload.get("_lifecycle_filter") if isinstance(payload.get("_lifecycle_filter"), dict) else None
    events = [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "status": r.get("status"),
            "startDate": r.get("startDate"),
        }
        for r in rows[:50]
    ]

    return {
        "intent": intent,
        "source": payload.get("_source") or payload.get("_resolution"),
        "event_count": len(rows),
        "lifecycle_filter": lifecycle,
        "events": events,
        "uuids": uuids[:80],
        "api_error": payload.get("_mutation_error"),
    }


def build_api_facts(
    api_trace: list[dict[str, Any]] | None,
    last_payload: dict[str, Any] | None,
    intent: str,
) -> dict[str, Any]:
    trace = api_trace or []
    steps: list[dict[str, Any]] = []
    all_uuids: set[str] = set()

    for step in trace:
        if not isinstance(step, dict):
            continue
        step_intent = str(step.get("intent") or intent)
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else None
        fact = _facts_from_payload(step_intent, payload)
        steps.append(fact)
        all_uuids.update(fact.get("uuids") or [])

    last_fact = _facts_from_payload(intent, last_payload if isinstance(last_payload, dict) else None)
    all_uuids.update(last_fact.get("uuids") or [])

    return {
        "steps": steps,
        "last": last_fact,
        "all_uuids": sorted(all_uuids),
    }


def format_facts_for_answer(facts: dict[str, Any]) -> str:
    last = facts.get("last") or {}
    lines = ["API facts (from live HTTP responses only):"]
    lf = last.get("lifecycle_filter")
    if isinstance(lf, dict) and lf.get("_matched") is not None:
        lines.append(
            f"Lifecycle filter ({lf.get('mode')}): {lf.get('_matched')} of "
            f"{lf.get('_total_before_filter')} events match.",
        )
    lines.append(f"Events in last payload: {last.get('event_count', 0)}")
    for ev in (last.get("events") or [])[:12]:
        lines.append(f"- {ev.get('name')} | {ev.get('status')} | id {ev.get('id')}")
    if len((last.get("events") or [])) > 12:
        lines.append(f"… and {len(last['events']) - 12} more in api_facts.")
    return "\n".join(lines)
