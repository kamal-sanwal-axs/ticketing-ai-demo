"""Filter marketing/search event lists by lifecycle (on-sale, live) in Python — not LLM."""

from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.event_list import event_state_label, iter_event_dicts, unwrap_event_payload
from apex_rag_demo.response_formatters import strip_ui_region

_ONSALE_QUESTION_RE = re.compile(
    r"\b(on[- ]?sale|onsale)\b|\blive\b.*\bevents?\b|\bpublished\b.*\bevents?\b",
    re.I,
)

_ONSALE_STATUS_RE = re.compile(
    r"\b(onsale|on[- ]?sale|on sale|live|published|active)\b",
    re.I,
)


def question_requests_onsale_filter(question: str) -> bool:
    return bool(_ONSALE_QUESTION_RE.search(strip_ui_region(question)))


def enrich_marketing_plan_from_question(plan: dict[str, Any], question: str) -> dict[str, Any]:
    from apex_rag_demo.order_intent_helpers import parse_result_limit

    out = dict(plan or {})
    if question_requests_onsale_filter(question) and not out.get("lifecycleFilter"):
        out["lifecycleFilter"] = "onsale"
    limit = parse_result_limit(question)
    if limit is not None:
        out["pageSize"] = limit
    return out


def _event_matches_lifecycle(ev: dict[str, Any], mode: str) -> bool:
    label = event_state_label(ev).lower()
    if mode != "onsale":
        return True
    if _ONSALE_STATUS_RE.search(label):
        return True
    if label in ("—", "", "draft"):
        return False
    return False


def apply_lifecycle_filter_to_payload(
    payload: dict[str, Any] | None,
    *,
    lifecycle_filter: str | None,
) -> dict[str, Any]:
    if not payload or not lifecycle_filter or lifecycle_filter != "onsale":
        return payload or {}

    events = iter_event_dicts(payload)
    if not events:
        return payload

    filtered = [ev for ev in events if _event_matches_lifecycle(ev, lifecycle_filter)]
    total = len(events)
    matched = len(filtered)

    out = dict(payload)
    for key in ("events", "Events", "items"):
        if key in out:
            out[key] = filtered
            break
    else:
        out["events"] = filtered

    out["_lifecycle_filter"] = {
        "mode": lifecycle_filter,
        "description": "Events filtered to on-sale / live / published lifecycle (Status field)",
        "_matched": matched,
        "_total_before_filter": total,
    }
    return out
