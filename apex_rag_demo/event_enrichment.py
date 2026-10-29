"""Fill marketing list stubs via events-api; separate displayable vs ID-only rows."""

from __future__ import annotations

from typing import Any

from apex_rag_demo.config import MARKETING_EVENT_ENRICH_MAX
from apex_rag_demo.event_list import (
    event_display_name,
    event_has_actionable_name,
    iter_event_dicts,
    unwrap_event_payload,
)


def event_record_id(ev: dict[str, Any]) -> str | None:
    for key in ("eventId", "id", "Id", "EventId"):
        raw = ev.get(key)
        if raw is not None and str(raw).strip() and str(raw) != "—":
            return str(raw).strip()
    return None


def enrich_marketing_events_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """GET events-api for rows missing headliners/name (marketing catalog stubs)."""
    if not payload or payload.get("_mock"):
        return payload or {}

    events = iter_event_dicts(payload)
    if not events:
        return payload

    from apex_rag_demo.clients import apex_events

    enriched: list[dict[str, Any]] = []
    fetched = 0
    errors = 0
    for ev in events:
        row = dict(ev)
        if event_has_actionable_name(row) or fetched >= MARKETING_EVENT_ENRICH_MAX:
            enriched.append(row)
            continue
        eid = event_record_id(row)
        if not eid:
            enriched.append(row)
            continue
        try:
            detail = apex_events.get_event(eid)
            merged = unwrap_event_payload(detail)
            if merged:
                row = {**row, **merged}
                if event_has_actionable_name(row):
                    fetched += 1
        except Exception:
            errors += 1
        enriched.append(row)

    out = dict(payload)
    for key in ("events", "Events", "items"):
        if key in out:
            out[key] = enriched
            break
    else:
        out["events"] = enriched

    out["_event_enrichment"] = {
        "attempted": min(len(events), MARKETING_EVENT_ENRICH_MAX),
        "resolved_names": fetched,
        "errors": errors,
        "description": (
            "Marketing list rows missing names were hydrated from events-api GET /{eventId} "
            f"(up to {MARKETING_EVENT_ENRICH_MAX} per request)."
        ),
    }
    return out


def partition_event_table_rows(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Actionable rows vs ID-only stubs (not shown in main table)."""
    ok: list[dict[str, str]] = []
    incomplete: list[dict[str, str]] = []
    for row in rows:
        name = str(row.get("name") or "—")
        eid = str(row.get("id") or "—")
        has_name = name != "—" and not name.startswith("⚠")
        has_context = (
            has_name
            or row.get("startDate", "—") != "—"
            or row.get("status", "—") != "—"
            or row.get("clientVenueId", "—") != "—"
        )
        if has_name:
            ok.append(row)
        elif eid != "—":
            incomplete.append({**row, "name": "—", "dataQuality": "ID only — cannot use for follow-up"})
        elif has_context:
            ok.append(row)
        else:
            incomplete.append({**row, "dataQuality": "Empty marketing row"})
    return ok, incomplete
