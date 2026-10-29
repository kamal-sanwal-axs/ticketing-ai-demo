from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.event_list import unwrap_event_payload

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
)

_UPDATE_INTENT_RE = re.compile(
    r"\b(update|change|rename|set)\b",
    re.I,
)
_NAME_FIELD_RE = re.compile(
    r"\b(name|headliner?s?|title)\b",
    re.I,
)


def looks_like_update_event_name(question: str) -> bool:
    if not _UUID_RE.search(question):
        return False
    if not _UPDATE_INTENT_RE.search(question):
        return False
    return bool(_NAME_FIELD_RE.search(question))


def extract_update_event_name_plan(question: str) -> dict[str, str] | None:
    if not looks_like_update_event_name(question):
        return None
    event_id = _UUID_RE.search(question)
    if not event_id:
        return None
    eid = event_id.group(0)
    text = question.strip()
    tail = re.search(r"\bname\s+to\s+(.+)\s*$", text, re.I) or re.search(r"\bto\s+(.+)\s*$", text, re.I)
    if not tail:
        return None
    new_name = tail.group(1).strip().strip("\"'")
    if not new_name:
        return None
    return {"eventId": eid, "headliners": new_name}


def _date_field(dates: dict[str, Any], key: str) -> dict[str, Any] | None:
    raw = dates.get(key)
    if not isinstance(raw, dict):
        return None
    on = raw.get("on")
    tz = raw.get("timeZoneId")
    if not on or not tz:
        return None
    return {"on": on, "timeZoneId": tz}


def build_update_event_body_from_get(
    get_payload: dict[str, Any],
    *,
    headliners: str | None = None,
) -> dict[str, Any]:
    ev = unwrap_event_payload(get_payload)
    dates = ev.get("dates") if isinstance(ev.get("dates"), dict) else {}

    genre_ids: list[int] = []
    for genre in ev.get("genres") or []:
        if isinstance(genre, dict) and genre.get("id") is not None:
            genre_ids.append(int(genre["id"]))

    images: list[dict[str, str]] = []
    for img in ev.get("images") or []:
        if not isinstance(img, dict):
            continue
        image_type = img.get("imageType") if isinstance(img.get("imageType"), dict) else {}
        type_id = image_type.get("id")
        object_key = img.get("objectKey")
        if type_id and object_key:
            images.append({"imageTypeId": str(type_id), "objectKey": str(object_key)})

    age_req = ev.get("ageRequirement") if isinstance(ev.get("ageRequirement"), dict) else {}
    age_id = age_req.get("id")

    title = headliners
    if title is None:
        title = ev.get("headliners") or ev.get("headlinersText") or ""

    body: dict[str, Any] = {
        "clientVenueId": ev.get("clientVenueId"),
        "headliners": title,
        "supporters": ev.get("supporters") or ev.get("supportersText"),
        "presentedBy": ev.get("presentedBy"),
        "tour": ev.get("tour"),
        "description": ev.get("description"),
        "tags": ev.get("tags"),
        "genreIds": genre_ids or None,
        "ageRequirementId": age_id,
        "images": images or None,
        "announcement": _date_field(dates, "announcement"),
        "publicOnsale": _date_field(dates, "publicOnsale"),
        "fulfillment": _date_field(dates, "fulfillment"),
        "doorsOpen": _date_field(dates, "doorsOpen"),
        "start": _date_field(dates, "start"),
        "end": _date_field(dates, "end"),
    }
    return {k: v for k, v in body.items() if v is not None}
