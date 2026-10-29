"""Routing helpers for axs-b2b-reports (unified-api-reports) and manifest API."""

from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.config import REPORTS_DEFAULT_CONTEXT_ID, REPORTS_DEFAULT_REGION_ID
from apex_rag_demo.planning import _UUID_RE
from apex_rag_demo.response_formatters import strip_ui_region

_FLASH_SALES_RE = re.compile(
    r"\b(flash\s+)?sales\s+report\b|\bsales\s+report\b|\bresale\s+orders?\s+report\b",
    re.I,
)
_FLASH_LIFECYCLE_RE = re.compile(
    r"\bticket\s+life[- ]?cycle\b|\blifecycle\s+report\b",
    re.I,
)
_FLASH_TRANSFER_RE = re.compile(
    r"\btickets?\s+in\s+transfer\b|\btransfer\s+report\b",
    re.I,
)
_INVENTORY_REPORT_RE = re.compile(
    r"\binventory\s+report\b|\breports?\s+inventory\b|\bb2b[- ]?reports?\b.*\binventory\b",
    re.I,
)
_MANIFEST_VENUE_RE = re.compile(
    r"\bvenue\s+config(uration)?\b|\bmanifest\b.*\bvenue\b|\bgetVenueConfig\b",
    re.I,
)
_REPORTS_GENERIC_RE = re.compile(
    r"\b(b2b[- ]?reports?|flash\s+report|unified[- ]?api[- ]?reports)\b",
    re.I,
)
_REPORTS_NATURAL_RE = re.compile(
    r"("
    r"\breports?\s+for\b|"
    r"\bshow\s+me\s+reports?\b|"
    r"\bget\s+me\s+(a\s+)?reports?\b|"
    r"\bgive\s+me\s+(a\s+)?reports?\b|"
    r"\bcan you show\s+.*\breports?\b|"
    r"\breports?\s+for\s+the\s+event\b|"
    r"\bevent\s+report\b"
    r")",
    re.I,
)
_LONG_ID_RE = re.compile(r"\b(\d{5,})\b")
_CONTEXT_RE = re.compile(r"\bcontext\s*(?:id)?\s*[:=]?\s*(\d+)\b", re.I)
_EVENT_NUM_RE = re.compile(
    r"\b(?:reports?\s+)?event\s*(?:id)?\s*[:=]?\s*(\d+)\b",
    re.I,
)


def looks_like_manifest_venue_config(question: str) -> bool:
    bare = strip_ui_region(question)
    if not _MANIFEST_VENUE_RE.search(bare):
        return False
    return bool(_UUID_RE.search(bare) or "venue config" in bare.lower())


def looks_like_b2b_reports_question(question: str) -> bool:
    bare = strip_ui_region(question)
    return bool(
        _REPORTS_GENERIC_RE.search(bare)
        or _REPORTS_NATURAL_RE.search(bare)
        or _FLASH_SALES_RE.search(bare)
        or _FLASH_LIFECYCLE_RE.search(bare)
        or _FLASH_TRANSFER_RE.search(bare)
        or _INVENTORY_REPORT_RE.search(bare)
    )


def resolve_reports_guard_intent(question: str) -> str | None:
    """Map natural-language reports asks to a wired read intent."""
    if not looks_like_b2b_reports_question(question):
        return None
    bare = strip_ui_region(question)
    if infer_flash_report_kind(question) == "sales_date_range":
        return "b2b_flash_report"
    if re.search(r"\binventory\s+report\b", bare, re.I) or (
        re.search(r"\breports?\b", bare, re.I) and re.search(r"\binventory\b", bare, re.I)
    ):
        return "reports_inventory_event"
    if re.search(r"\btimezones?\b", bare, re.I):
        return "reports_timezones"
    return "b2b_flash_report"


def looks_like_vague_report_request(question: str) -> bool:
    """Report wording without numeric context/event ids or event UUID."""
    if not looks_like_b2b_reports_question(question):
        return False
    context_id, event_id = _parse_long_ids(question)
    if context_id is not None or event_id is not None:
        return False
    return not bool(_UUID_RE.search(strip_ui_region(question)))


def extract_event_uuid_from_question(question: str) -> str | None:
    m = _UUID_RE.search(strip_ui_region(question))
    return m.group(0) if m else None


def extract_report_numeric_ids_from_event_payload(
    payload: dict[str, Any] | None,
) -> tuple[int | None, int | None]:
    """Best-effort AXS numeric contextId / eventId from events-api JSON."""
    if not payload or not isinstance(payload, dict):
        return None, None

    context_id: int | None = None
    event_id: int | None = None

    def consider(key: str, value: Any) -> None:
        nonlocal context_id, event_id
        if not isinstance(value, int) or value <= 0:
            return
        kl = key.lower().replace("_", "")
        if kl in ("contextid", "axscontextid", "clientcontextid"):
            context_id = context_id or value
        elif kl in ("eventid", "axseventid", "numericeventid"):
            event_id = event_id or value

    def walk(obj: Any, depth: int = 0) -> None:
        if depth > 10:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                consider(str(k), v)
                walk(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj[:25]:
                walk(item, depth + 1)

    walk(payload)
    return context_id, event_id


def resolve_report_ids_via_events_api(event_uuid: str) -> tuple[int | None, int | None, str | None]:
    """Load event by UUID and scrape numeric ids for reports-api."""
    from apex_rag_demo.event_resolve import get_event_with_context

    payload, err = get_event_with_context(event_uuid)
    if err:
        return None, None, err
    ctx, ev = extract_report_numeric_ids_from_event_payload(payload)
    if ctx is None and ev is None:
        return None, None, (
            "Events API returned the event but no numeric contextId/eventId for B2B reports. "
            "Pass numeric ids (e.g. sales report context 123 event 456) or set REPORTS_DEFAULT_CONTEXT_ID."
        )
    return ctx, ev, None


def build_report_catalog_payload() -> dict[str, Any]:
    from apex_rag_demo.dynamic_tools import load_dynamic_tool_catalog

    rows: list[dict[str, str]] = []
    for tool in load_dynamic_tool_catalog().values():
        if tool.service_id != "reports":
            continue
        rows.append(
            {
                "tool_id": tool.tool_id,
                "method": tool.method.upper(),
                "path": tool.path_template,
                "summary": tool.summary or tool.legacy_intent,
                "intent": tool.legacy_intent,
            },
        )
    return {
        "_report_catalog": True,
        "reports": rows,
        "hint": (
            "Flash reports need numeric contextId and eventId "
            "(e.g. “flash sales report context 100 event 200”). "
            "For an events-api UUID, include “reports for the event <uuid>” — "
            "the app will resolve numeric ids when present on the event payload."
        ),
    }


def infer_flash_report_kind(question: str) -> str:
    bare = strip_ui_region(question)
    if _FLASH_LIFECYCLE_RE.search(bare):
        return "ticket_lifecycle"
    if _FLASH_TRANSFER_RE.search(bare):
        return "ticket_in_transfer"
    if re.search(r"\bdate\s*range\b|\bfrom\b.*\bto\b", bare, re.I):
        return "sales_date_range"
    if _FLASH_SALES_RE.search(bare) or _REPORTS_GENERIC_RE.search(bare):
        return "sales_event"
    return "sales_event"


def _parse_long_ids(question: str) -> tuple[int | None, int | None]:
    bare = strip_ui_region(question)
    ctx_m = _CONTEXT_RE.search(bare)
    ev_m = _EVENT_NUM_RE.search(bare)
    context_id = int(ctx_m.group(1)) if ctx_m else None
    event_id = int(ev_m.group(1)) if ev_m else None
    if context_id is None or event_id is None:
        nums = [int(m.group(1)) for m in _LONG_ID_RE.finditer(bare)]
        if len(nums) >= 2:
            context_id = context_id if context_id is not None else nums[0]
            event_id = event_id if event_id is not None else nums[1]
        elif len(nums) == 1 and event_id is None:
            event_id = nums[0]
    return context_id, event_id


def enrich_reports_plan_from_question(intent: str, plan: dict[str, Any], question: str) -> dict[str, Any]:
    out = dict(plan or {})
    context_id, event_id = _parse_long_ids(question)
    default_ctx = int(REPORTS_DEFAULT_CONTEXT_ID) if str(REPORTS_DEFAULT_CONTEXT_ID).strip().isdigit() else None

    if intent == "b2b_flash_report":
        out.setdefault("flashReport", infer_flash_report_kind(question))
        event_uuid = extract_event_uuid_from_question(question)
        if event_uuid:
            out["eventUuid"] = event_uuid
        if context_id is not None:
            out["contextId"] = context_id
        elif default_ctx is not None:
            out.setdefault("contextId", default_ctx)
        if event_id is not None:
            out["eventId"] = event_id
        out.setdefault("regionId", str(REPORTS_DEFAULT_REGION_ID))
        out.setdefault("locale", "en-US")
        if looks_like_vague_report_request(question):
            out["_report_catalog"] = True
        return out

    if intent == "reports_inventory_event":
        event_uuid = extract_event_uuid_from_question(question)
        if event_uuid:
            out["eventUuid"] = event_uuid
        if context_id is not None:
            out["contextId"] = context_id
        elif default_ctx is not None:
            out.setdefault("contextId", default_ctx)
        if event_id is not None:
            out["eventId"] = event_id
        return out

    if intent == "get_venue_config":
        eid = str(out.get("venueConfigId") or "").strip()
        if not eid:
            m = _UUID_RE.search(strip_ui_region(question))
            if m:
                out["venueConfigId"] = m.group(0)
        return out

    return out
