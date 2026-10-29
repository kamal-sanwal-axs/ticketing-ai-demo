from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from apex_rag_demo.config import APEX_EVENTS_BASE_URL

# Exact strings from apex-events-api EventStateTransitionErrors (publish-related).
_API_PUBLISH_MESSAGES: dict[str, str] = {
    "Cannot publish an event that is already published.": "already_published",
    "Cannot publish a cancelled event.": "cancelled",
    "Cannot publish a deleted event.": "deleted",
    "Cannot publish an event without all required images.": "missing_required_images",
}


@dataclass(frozen=True)
class PublishConflictContext:
    """Structured interpretation of POST /events/{id}/publish failures."""

    reason_code: str
    headline: str
    api_detail: str
    http_status: int
    meaning: str
    next_steps: tuple[str, ...] = field(default_factory=tuple)
    event_state_after: str | None = None

    def paragraphs(self) -> list[str]:
        lines = [
            self.headline,
            "",
            f"What happened: {self.meaning}",
        ]
        if self.api_detail:
            lines.append(f"Events-api detail: {self.api_detail}")
        if self.event_state_after:
            lines.append(f"Event state now (GET /events/{{id}}): {self.event_state_after}")
        if self.next_steps:
            lines.append("")
            lines.append("What to do:")
            lines.extend(f"• {step}" for step in self.next_steps)
        return lines


_REASON_COPY: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "already_published": (
        "Already published",
        "This event is already in Published state. Events-api does not allow publishing again.",
        (
            "Confirm with: get event <uuid> only — Status should show Published.",
            "Use marketing/search flows if you need on-sale visibility, not another publish POST.",
        ),
    ),
    "missing_required_images": (
        "Missing required images",
        "Draft events must have all required image types before publish (events-api validation).",
        (
            "Open the event in apex-dev Events UI and upload required images.",
            "Retry publish after images are complete.",
        ),
    ),
    "cancelled": (
        "Event is cancelled",
        "Cancelled events cannot be moved back to Published via publish.",
        ("Create a new event or change lifecycle in the Events UI if your tenant allows it.",),
    ),
    "deleted": (
        "Event is deleted",
        "Deleted events cannot be published.",
        ("Use a different event id or restore the event in your admin workflow if applicable.",),
    ),
    "state_conflict_unknown": (
        "Publish blocked (state conflict)",
        "Events-api returned 409 Conflict for an invalid lifecycle transition.",
        (
            "Read the API detail below — it is authoritative.",
            "Run get event <uuid> only to see current Status (Draft, Published, etc.).",
        ),
    ),
    "other_http_error": (
        "Publish failed",
        "Events-api rejected the publish request.",
        ("Check API detail and event state, then fix the blocking issue and retry.",),
    ),
}


def parse_http_error_response(exc: httpx.HTTPStatusError) -> dict[str, Any]:
    status = exc.response.status_code
    detail = ""
    title = ""
    code = ""
    raw: Any = None
    try:
        raw = exc.response.json()
        if isinstance(raw, dict):
            detail = str(raw.get("detail") or "")
            title = str(raw.get("title") or raw.get("type") or "")
            code = str(raw.get("code") or raw.get("errorCode") or "")
            if not detail:
                detail = str(
                    raw.get("message")
                    or (raw.get("error") or {}).get("message")
                    or title
                    or "",
                )
            errors = raw.get("errors")
            if not detail and isinstance(errors, list) and errors:
                detail = "; ".join(str(e) for e in errors[:3])
    except (json.JSONDecodeError, ValueError):
        text = (exc.response.text or "").strip()
        if text:
            detail = text[:500]

    return {
        "status": status,
        "detail": detail.strip(),
        "title": title.strip(),
        "code": code.strip(),
        "url": str(exc.request.url) if exc.request else "",
        "raw": raw,
    }


def classify_publish_conflict(
    *,
    http_status: int,
    api_detail: str,
    api_code: str = "",
    event_state: str | None = None,
) -> PublishConflictContext:
    detail = (api_detail or "").strip()
    reason = _API_PUBLISH_MESSAGES.get(detail)

    if not reason:
        lowered = detail.lower()
        if "already published" in lowered:
            reason = "already_published"
        elif "required images" in lowered or "without all required images" in lowered:
            reason = "missing_required_images"
        elif "cancelled" in lowered:
            reason = "cancelled"
        elif "deleted" in lowered:
            reason = "deleted"
        elif api_code == "events.state.conflict" and http_status == 409:
            reason = "state_conflict_unknown"
        elif http_status == 409:
            reason = "state_conflict_unknown"
        else:
            reason = "other_http_error"

    state_norm = (event_state or "").strip().lower()
    if http_status == 409 and state_norm == "published" and reason == "state_conflict_unknown":
        reason = "already_published"
    if http_status == 409 and state_norm == "draft" and "image" in detail.lower():
        reason = "missing_required_images"

    headline, meaning, steps = _REASON_COPY.get(reason, _REASON_COPY["other_http_error"])
    return PublishConflictContext(
        reason_code=reason,
        headline=f"Publish not applied — {headline}",
        api_detail=detail,
        http_status=http_status,
        meaning=meaning,
        next_steps=steps,
        event_state_after=event_state or None,
    )


def explain_publish_conflict(detail: str, status: int, event_state: str | None = None) -> list[str]:
    ctx = classify_publish_conflict(
        http_status=status,
        api_detail=detail,
        event_state=event_state,
    )
    return ctx.paragraphs()


def build_mutation_error_payload(
    intent: str,
    plan: dict[str, Any],
    exc: httpx.HTTPStatusError,
    *,
    event_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed = parse_http_error_response(exc)
    event_state: str | None = None
    if isinstance(event_snapshot, dict):
        from apex_rag_demo.event_list import event_state_label, unwrap_event_payload

        ev = unwrap_event_payload(event_snapshot)
        if ev:
            event_state = event_state_label(ev)

    publish_context: dict[str, Any] | None = None
    if intent == "publish_event":
        ctx = classify_publish_conflict(
            http_status=int(parsed["status"]),
            api_detail=str(parsed["detail"]),
            api_code=str(parsed.get("code") or ""),
            event_state=event_state,
        )
        publish_context = {
            "reasonCode": ctx.reason_code,
            "headline": ctx.headline,
            "meaning": ctx.meaning,
            "nextSteps": list(ctx.next_steps),
            "apiDetail": ctx.api_detail,
            "httpStatus": ctx.http_status,
            "eventState": event_state,
        }

    return {
        "_mutation_error": True,
        "intent": intent,
        "plan": plan,
        "httpStatus": parsed["status"],
        "detail": parsed["detail"],
        "title": parsed["title"],
        "errorCode": parsed.get("code"),
        "endpoint": parsed["url"],
        "eventSnapshot": event_snapshot,
        "publishContext": publish_context,
    }


def format_publish_event_failure(payload: dict[str, Any], api_error: str | None) -> str:
    eid = (payload.get("plan") or {}).get("eventId") or "?"
    ctx_dict = payload.get("publishContext")
    if isinstance(ctx_dict, dict) and ctx_dict.get("headline"):
        lines = [
            str(ctx_dict["headline"]),
            f"POST {APEX_EVENTS_BASE_URL}/{eid}/publish",
            "",
            f"What happened: {ctx_dict.get('meaning', '')}",
        ]
        if ctx_dict.get("apiDetail"):
            lines.append(f"Events-api detail: {ctx_dict['apiDetail']}")
        if ctx_dict.get("eventState"):
            lines.append(f"Event state (GET): {ctx_dict['eventState']}")
        steps = ctx_dict.get("nextSteps") or []
        if steps:
            lines.append("")
            lines.append("What to do:")
            lines.extend(f"• {s}" for s in steps)
        return "\n".join(lines)

    detail = str(payload.get("detail") or "")
    status = int(payload.get("httpStatus") or 0)
    lines = explain_publish_conflict(detail, status)
    lines.insert(0, f"Publish failed for event {eid} (POST {APEX_EVENTS_BASE_URL}/{eid}/publish).")
    return "\n".join(lines)
