"""Dynamic UI shapes: column sets, charts, multi-step layouts (not one fixed datatable)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from apex_rag_demo.event_list import (
    EVENT_HIERARCHY_TABLE_COLUMNS,
    EVENT_NAME_ONLY_TABLE_COLUMNS,
)
from apex_rag_demo.response_formatters import strip_ui_region

EVENT_CATALOG_TABLE_COLUMNS: list[dict[str, str]] = [
    {"key": "name", "label": "Event"},
    {"key": "startDate", "label": "Start"},
    {"key": "endDate", "label": "End"},
    {"key": "status", "label": "Status"},
    {"key": "id", "label": "Event ID"},
]

_ORG_HIERARCHY_LIST_RE = re.compile(
    r"\b(org|organization|principal|contractual|client venue|hierarchy|venue registry)\b",
    re.I,
)

_TIMELINE_RE = re.compile(
    r"\b(by\s+month|by\s+date|timeline|over\s+time|chart|graph|trend|schedule)\b",
    re.I,
)


def wants_org_hierarchy_in_event_list(question: str) -> bool:
    return bool(_ORG_HIERARCHY_LIST_RE.search(strip_ui_region(question)))


def wants_event_timeline_chart(question: str) -> bool:
    return bool(_TIMELINE_RE.search(strip_ui_region(question)))


def resolve_event_list_columns(question: str) -> list[dict[str, str]]:
    from apex_rag_demo.event_query_helpers import wants_event_names_only

    bare = strip_ui_region(question)
    if wants_event_names_only(bare):
        return list(EVENT_NAME_ONLY_TABLE_COLUMNS)
    if wants_org_hierarchy_in_event_list(bare):
        return list(EVENT_HIERARCHY_TABLE_COLUMNS)
    return list(EVENT_CATALOG_TABLE_COLUMNS)


def project_event_rows(rows: list[dict[str, str]], columns: list[dict[str, str]]) -> list[dict[str, str]]:
    keys = {c["key"] for c in columns}
    return [{k: row.get(k, "—") for k in keys} for row in rows]


def build_events_timeline_chart(rows: list[dict[str, str]]) -> dict[str, Any] | None:
    """Bar chart of event counts by start month (when dates exist)."""
    buckets: Counter[str] = Counter()
    for row in rows:
        start = str(row.get("startDate") or "—")
        if start == "—" or len(start) < 7:
            continue
        month = start[:7]
        buckets[month] += 1
    if not buckets:
        return None
    labels = sorted(buckets.keys())
    return {
        "kind": "bar",
        "title": "Events by start month",
        "labels": labels,
        "values": [buckets[m] for m in labels],
    }


def build_get_event_fields(
    ev: dict[str, Any],
    *,
    eid: str,
    include_org: bool,
    chain: dict[str, str],
    client: dict[str, Any],
    venue: dict[str, Any],
    start_date: str,
    end_date: str,
    status: str,
    name: str,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Event-api fields first; org hierarchy only when explicitly requested."""
    fields: list[dict[str, str]] = [
        {"label": "Event", "value": name},
        {"label": "Start", "value": start_date},
        {"label": "End", "value": end_date},
        {"label": "Status", "value": status},
        {"label": "Event ID", "value": eid},
    ]
    venue_name = str(venue.get("name") or venue.get("Name") or "—")
    if venue_name != "—":
        fields.append({"label": "Venue (on event)", "value": venue_name})
    cv_id = str(ev.get("clientVenueId") or ev.get("ClientVenueId") or "—")
    if cv_id != "—":
        fields.append({"label": "Client venue ID", "value": cv_id})

    sections: list[dict[str, Any]] = []
    if include_org:
        sections.append(
            {
                "title": "Organization context (admin registry)",
                "fields": [
                    {"label": "Principal org", "value": chain.get("principalOrganization", "—")},
                    {"label": "Contractual org", "value": chain.get("contractualOrganization", "—")},
                    {"label": "Client", "value": chain.get("client") or str(client.get("name") or "—")},
                    {
                        "label": "Client venue",
                        "value": chain.get("clientVenue") or venue_name,
                    },
                ],
            },
        )
    return fields, sections


def orchestration_trace_sections(api_trace: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not api_trace or len(api_trace) < 2:
        return []
    blocks: list[dict[str, Any]] = []
    for i, step in enumerate(api_trace, start=1):
        intent = str(step.get("intent") or "api")
        err = step.get("error")
        blocks.append(
            {
                "title": f"API step {i}: {intent.replace('_', ' ')}",
                "paragraphs": [
                    str(step.get("plan") or "")[:400] if isinstance(step.get("plan"), dict) else "",
                    f"Error: {err}" if err else "Completed.",
                ],
            },
        )
    return blocks
