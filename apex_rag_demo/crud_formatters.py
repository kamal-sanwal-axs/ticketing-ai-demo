from __future__ import annotations

from typing import Any

from apex_rag_demo.crud_policy import write_kind_for_intent, WriteKind


def format_crud_mutation(
    intent: str,
    payload: dict[str, Any] | None,
    api_error: str | None,
    plan: dict[str, Any],
) -> str | None:
    if api_error:
        if payload and payload.get("_mutation_error") and intent == "publish_event":
            from apex_rag_demo.http_errors import format_publish_event_failure

            return format_publish_event_failure(payload, api_error)
        return api_error
    if not payload:
        return "No API response."

    if payload.get("_pending_confirmation"):
        preview = (payload.get("preview") or {}).get("summary") or ""
        return (
            f"{payload.get('message')}\n\n"
            f"Intent: {intent}\n"
            f"{preview}\n\n"
            "Click Confirm in the chat UI to apply."
        )

    kind = write_kind_for_intent(intent)
    lines: list[str] = []

    if payload.get("_dry_run"):
        lines.append(f"Dry-run — no {kind.value} was sent to apex-dev.")
        if payload.get("endpoint"):
            lines.append(f"Would call: {payload['endpoint']}")
        if payload.get("request"):
            lines.append(f"Body preview: {payload['request']}")
        if payload.get("preview"):
            lines.append(str(payload["preview"]))
        return "\n".join(lines)

    if payload.get("_updated") or payload.get("_deleted") or payload.get("_published") or payload.get("_reset"):
        lines.append(f"{kind.value.capitalize()} completed for intent {intent}.")
    else:
        lines.append(f"{intent} response received.")

    for key in ("eventId", "organizationId", "clientVenueId", "pixelId", "zoneId", "headliners"):
        if payload.get(key):
            lines.append(f"{key}: {payload[key]}")

    if kind == WriteKind.RESET:
        lines.append("Reset completed (no separate confirmation step).")

    return "\n".join(lines)
