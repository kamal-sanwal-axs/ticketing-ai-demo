from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from apex_rag_demo.event_list import event_start_end_labels, iter_event_dicts
from apex_rag_demo.response_formatters import strip_ui_region

_AFTER_THIS_MONTH_RE = re.compile(r"\bafter\s+this\s+month\b", re.I)
_BEFORE_THIS_MONTH_RE = re.compile(r"\bbefore\s+this\s+month\b", re.I)
_MONTH_NAMES: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_AFTER_NAMED_MONTH_RE = re.compile(
    r"\bafter\s+"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"(?:\s+(\d{4}))?\b",
    re.I,
)
_THIS_MONTH_RE = re.compile(r"\bthis\s+month\b", re.I)
_NEXT_MONTH_RE = re.compile(r"\bnext\s+month\b", re.I)
_TEMPORAL_HINT_RE = re.compile(
    r"\b(after|before|starting|from|until|through|during)\b.*\b("
    r"month|week|year|january|february|march|april|may|june|july|august|"
    r"september|october|november|december|today|tomorrow)\b|"
    r"\bthis\s+month\b|\bnext\s+month\b|\bafter\s+this\s+month\b",
    re.I,
)

_PLAN_MARKETING_DATE_SYSTEM = """Extract event list date filters for a ticketed-events catalog query.
Return JSON only with keys:
- startAfter: ISO date YYYY-MM-DD or null (event start on or after this day)
- startBefore: ISO date YYYY-MM-DD or null (event start strictly before this day)
- description: short label of the filter

Rules:
- "after this month" → startAfter = first day of the calendar month after the reference month.
- "after October 2026" (or any month + year) → startAfter = first day of the month AFTER that month (e.g. 2026-11-01), not the reference "today" date.
- "this month" → startAfter = first day of reference month, startBefore = first day of next month.
- "next month" → startAfter = first day of next calendar month, startBefore = first day of month after that.
Use the reference date in the user message for relative phrases."""


@dataclass(frozen=True)
class EventDateFilter:
    start_after: date | None = None
    start_before: date | None = None
    description: str = ""

    def to_plan(self) -> dict[str, Any]:
        return {
            "startAfter": self.start_after.isoformat() if self.start_after else None,
            "startBefore": self.start_before.isoformat() if self.start_before else None,
            "description": self.description,
        }

    @classmethod
    def from_plan(cls, plan: dict[str, Any] | None) -> EventDateFilter | None:
        if not plan:
            return None
        raw_after = plan.get("startAfter")
        raw_before = plan.get("startBefore")
        if not raw_after and not raw_before:
            return None
        start_after = _parse_iso_date(raw_after) if raw_after else None
        start_before = _parse_iso_date(raw_before) if raw_before else None
        desc = str(plan.get("description") or "").strip()
        return EventDateFilter(
            start_after=start_after,
            start_before=start_before,
            description=desc or _default_description(start_after, start_before),
        )


def _parse_iso_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _first_of_month(year: int, month: int) -> date:
    return date(year, month, 1)


def _first_of_next_month(ref: date) -> date:
    if ref.month == 12:
        return date(ref.year + 1, 1, 1)
    return date(ref.year, ref.month + 1, 1)


def _default_description(start_after: date | None, start_before: date | None) -> str:
    if start_after and start_before:
        return f"Events starting from {start_after.isoformat()} before {start_before.isoformat()}"
    if start_after:
        return f"Events starting on or after {start_after.isoformat()}"
    if start_before:
        return f"Events starting before {start_before.isoformat()}"
    return "Date filter"


def question_has_date_constraint(question: str) -> bool:
    bare = strip_ui_region(question)
    return bool(_TEMPORAL_HINT_RE.search(bare))


def parse_event_date_filter(question: str, *, reference: date | None = None) -> EventDateFilter | None:
    bare = strip_ui_region(question)
    ref = reference or date.today()

    if _AFTER_THIS_MONTH_RE.search(bare):
        start = _first_of_next_month(ref)
        return EventDateFilter(
            start_after=start,
            description=f"Start on or after {start.strftime('%B %Y')} (after this month)",
        )

    after_month = _AFTER_NAMED_MONTH_RE.search(bare)
    if after_month:
        month_num = _MONTH_NAMES[after_month.group(1).lower()]
        year = int(after_month.group(2)) if after_month.group(2) else ref.year
        month_end = date(year, month_num, 1)
        start = _first_of_next_month(month_end)
        month_label = after_month.group(1).capitalize()
        return EventDateFilter(
            start_after=start,
            description=f"Events starting after {month_label} {year}",
        )

    if _BEFORE_THIS_MONTH_RE.search(bare):
        start = _first_of_month(ref.year, ref.month)
        return EventDateFilter(
            start_before=start,
            description="Start before this month",
        )

    if _NEXT_MONTH_RE.search(bare) and "event" in bare.lower():
        start = _first_of_next_month(ref)
        end = _first_of_next_month(start)
        return EventDateFilter(
            start_after=start,
            start_before=end,
            description=f"Events in {start.strftime('%B %Y')}",
        )

    if _THIS_MONTH_RE.search(bare) and "event" in bare.lower():
        start = _first_of_month(ref.year, ref.month)
        end = _first_of_next_month(ref)
        return EventDateFilter(
            start_after=start,
            start_before=end,
            description=f"Events in {start.strftime('%B %Y')} (this month)",
        )

    return None


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def plan_marketing_date_filter(
    question: str,
    *,
    reference: date | None = None,
    chroma_system_context: str | None = None,
    semantic_context_block: str | None = None,
    chat_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ref = reference or date.today()
    parsed = parse_event_date_filter(question, reference=ref)
    has_dates = question_has_date_constraint(question) or parsed is not None
    if not has_dates:
        return {"pageSize": 25}

    from apex_rag_demo.clients.llama import chat_completion
    from apex_rag_demo.config import CHAT_TEMPERATURE_ROUTING

    print("--- AGENT PLAN marketing date filter (LLM) ---", flush=True)
    user = (
        f"Reference date (today): {ref.isoformat()} ({ref.strftime('%A, %B %d, %Y')})\n\n"
        f"User message:\n{strip_ui_region(question)}"
    )
    if parsed:
        user += (
            "\n\nNon-binding date parser suggestion (confirm or correct in your JSON):\n"
            + json.dumps(parsed.to_plan(), ensure_ascii=False)
        )
    raw = chat_completion(
        _PLAN_MARKETING_DATE_SYSTEM,
        user,
        temperature=CHAT_TEMPERATURE_ROUTING,
        chroma_system_context=chroma_system_context,
        semantic_turn_context=semantic_context_block,
        history=chat_history,
        routing=True,
    )
    try:
        data = _parse_json_object(raw)
        filt = EventDateFilter.from_plan(data)
        if filt:
            if not filt.description:
                filt = EventDateFilter(
                    start_after=filt.start_after,
                    start_before=filt.start_before,
                    description=_default_description(filt.start_after, filt.start_before),
                )
            return {
                "dateFilter": filt.to_plan(),
                "pageSize": 100,
                "_dateFilterSource": "llm",
            }
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    return {"pageSize": 25}


def _event_start_date(ev: dict[str, Any]) -> date | None:
    start_label, _ = event_start_end_labels(ev)
    if not start_label or start_label == "—":
        return None
    return _parse_iso_date(start_label)


def event_matches_filter(ev: dict[str, Any], filt: EventDateFilter) -> bool:
    start = _event_start_date(ev)
    if start is None:
        return False
    if filt.start_after and start < filt.start_after:
        return False
    if filt.start_before and start >= filt.start_before:
        return False
    return True


def apply_date_filter_to_payload(
    payload: dict[str, Any] | None,
    date_filter_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    if not payload:
        return {}
    filt = EventDateFilter.from_plan(date_filter_plan or {})
    if not filt:
        return payload

    events = iter_event_dicts(payload)
    kept = [ev for ev in events if event_matches_filter(ev, filt)]
    out = dict(payload)
    for key in ("events", "Events", "items", "suggestions", "Suggestions"):
        if key in out and isinstance(out[key], list):
            out[key] = kept
    out["_date_filter"] = {
        **filt.to_plan(),
        "_matched": len(kept),
        "_total_before_filter": len(events),
    }
    return out
