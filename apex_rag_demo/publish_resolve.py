from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.event_list import iter_event_dicts
from apex_rag_demo.response_formatters import strip_ui_region

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
)
_AINV_RE = re.compile(r"\b(AINV-\d+)\b", re.I)
_HEX_ID_RE = re.compile(r"\b([0-9a-fA-F]{8,32})\b")


def _event_id_from_dict(ev: dict[str, Any]) -> str:
    return str(ev.get("eventId") or ev.get("id") or ev.get("Id") or "").strip()


def _filter_by_id_prefix(events: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    p = prefix.lower()
    return [ev for ev in events if _event_id_from_dict(ev).lower().startswith(p)]


def resolve_publish_event_id(question: str, session_focus: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve events-api UUID from publish phrasing (full UUID, AINV code, or id prefix)."""
    focus = session_focus or {}
    bare = strip_ui_region(question)

    full = _UUID_RE.search(bare)
    if full:
        return {"eventId": full.group(0)}

    ainv = _AINV_RE.search(bare)
    id_prefix: str | None = None
    for match in _HEX_ID_RE.finditer(bare):
        token = match.group(1)
        if len(token) >= 8 and "-" not in token:
            id_prefix = token.lower()
            break

    if not ainv and not id_prefix:
        focus_id = str(focus.get("eventId") or "").strip()
        return {"eventId": focus_id} if focus_id else {"eventId": ""}

    from apex_rag_demo.clients import apex_search

    query = ainv.group(1) if ainv else id_prefix or ""
    try:
        payload = apex_search.search_events(query=query, page_size=25)
        events = iter_event_dicts(payload)
    except Exception as exc:  # noqa: BLE001 — demo boundary
        out: dict[str, Any] = {"eventId": str(focus.get("eventId") or "")}
        if ainv:
            out["_inventoryCode"] = ainv.group(1)
        out["_resolveError"] = str(exc)
        return out

    if id_prefix:
        events = _filter_by_id_prefix(events, id_prefix)

    if len(events) == 1:
        eid = _event_id_from_dict(events[0])
        plan: dict[str, Any] = {"eventId": eid}
        if ainv:
            plan["_resolvedFrom"] = ainv.group(1)
        if id_prefix:
            plan["_resolvedIdPrefix"] = id_prefix
        return plan

    if len(events) > 1:
        return {
            "eventId": "",
            "_resolveError": (
                f"Multiple events match “{query}”"
                + (f" with id starting {id_prefix}" if id_prefix else "")
                + ". Paste the full event UUID."
            ),
            "_candidates": [_event_id_from_dict(ev) for ev in events[:8]],
        }

    focus_id = str(focus.get("eventId") or "").strip()
    if focus_id:
        return {"eventId": focus_id}
    return {
        "eventId": "",
        "_resolveError": f"No search-api match for “{query}”"
        + (f" (id prefix {id_prefix})" if id_prefix else "")
        + ".",
    }
