from __future__ import annotations

from typing import Any

import httpx

from apex_rag_demo.clients import apex_events, apex_search


def get_event_with_context(requested_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Resolve an id that may be an event id or client-venue id.
    Returns (payload, error). On success error is None; partial context may still have _notes.
    """
    rid = requested_id.strip()
    if not rid:
        return None, "Missing event or venue id."

    notes: list[str] = []

    try:
        direct = apex_events.get_event(rid)
        return {
            **direct,
            "_resolution": "events_get",
            "_requested_id": rid,
        }, None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            return None, str(exc)
        notes.append(f"Events API GET /{rid} returned 404 (not an event id in events-api).")
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)

    try:
        by_id = apex_search.search_events(
            query=None,
            page_size=15,
            event_ids=[rid],
        )
        events = _extract_events_list(by_id)
        if events:
            notes.append("Search API matched eventIds filter.")
            first_id = str(events[0].get("eventId") or events[0].get("id") or "")
            if first_id and first_id != rid:
                try:
                    ev = apex_events.get_event(first_id)
                    return {
                        **ev,
                        "_resolution": "events_get_via_search",
                        "_requested_id": rid,
                        "_search": by_id,
                        "_notes": notes,
                    }, None
                except Exception:
                    pass
            return {
                "_resolution": "search_events_only",
                "_requested_id": rid,
                "search": by_id,
                "_notes": notes,
            }, None
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Search POST /v1/events (eventIds): {exc}")

    try:
        cv = apex_search.get_client_venue(rid)
        notes.append("Search API GET /v1/client-venues/{id} succeeded — id is a client venue.")
        venue_name = _venue_name(cv)
        search: dict[str, Any] | None = None
        try:
            search = apex_search.search_events(
                query=venue_name if venue_name else None,
                page_size=25,
                venue_filters=[rid],
            )
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Search events for venue: {exc}")
            if venue_name:
                try:
                    search = apex_search.search_events_suggest(venue_name, size=10)
                except Exception as exc2:  # noqa: BLE001
                    notes.append(f"Search suggest for venue name: {exc2}")

        return {
            "_resolution": "client_venue_context",
            "_requested_id": rid,
            "clientVenue": cv,
            "search": search,
            "_notes": notes,
        }, None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            notes.append(f"Search GET client-venue: {exc}")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Search GET client-venue: {exc}")

    try:
        suggest = apex_search.search_events_suggest(rid, size=5)
        if _extract_events_list(suggest) or suggest.get("suggestions"):
            return {
                "_resolution": "search_suggest",
                "_requested_id": rid,
                "suggest": suggest,
                "_notes": notes,
            }, None
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Search suggest: {exc}")

    return {
        "_resolution": "not_found",
        "_requested_id": rid,
        "_notes": notes,
    }, (
        f"No event or client venue found for id {rid}. "
        "Use an events-api event UUID, or ask “list client venues” / “search events matching <name>”."
    )


def _extract_events_list(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    for key in ("events", "Events", "items"):
        block = payload.get(key)
        if isinstance(block, list):
            return [x for x in block if isinstance(x, dict)]
    return []


def _venue_name(cv_payload: dict[str, Any]) -> str:
    cv = cv_payload.get("clientVenue") or cv_payload.get("ClientVenue") or cv_payload
    venue = cv.get("venue") or cv.get("Venue") or {}
    if isinstance(venue, dict):
        return str(venue.get("name") or venue.get("Name") or "")
    return ""
