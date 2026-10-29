from __future__ import annotations

import json
from typing import Any


def _json_preview(payload: dict[str, Any] | None, limit: int = 2400) -> str:
    if not payload:
        return "—"
    text = json.dumps(payload, indent=2, default=str)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def build_reports_manifest_display(
    intent: str,
    payload: dict[str, Any] | None,
    plan: dict[str, Any],
    api_error: str | None,
) -> dict[str, Any] | None:
    if intent not in (
        "get_venue_config",
        "b2b_flash_report",
        "reports_inventory_event",
        "reports_timezones",
    ):
        return None

    if api_error:
        return {
            "type": "article",
            "title": "B2B reports / manifest",
            "badge": intent.replace("_", " "),
            "level": "warning",
            "paragraphs": [str(api_error)],
        }

    if isinstance(payload, dict) and payload.get("_report_catalog"):
        rows = payload.get("reports") or []
        paragraphs = [str(payload.get("hint") or "Choose a report type and pass numeric context/event ids.")]
        resolve_err = payload.get("_resolve_error")
        if resolve_err:
            paragraphs.insert(0, str(resolve_err))
        missing = payload.get("_missing")
        if missing:
            paragraphs.insert(0, f"Missing {missing} for this report call.")
        return {
            "type": "table",
            "title": "Available B2B reports (axs-b2b-reports)",
            "subtitle": "Dynamic OpenAPI tools · pick one and add numeric contextId / eventId",
            "badge": "b2b reports",
            "columns": [
                {"key": "summary", "label": "Report"},
                {"key": "method", "label": "Method"},
                {"key": "path", "label": "Path"},
                {"key": "intent", "label": "Intent"},
            ],
            "rows": rows,
            "paragraphs": paragraphs,
        }

    if intent == "get_venue_config":
        vid = plan.get("venueConfigId") or (payload or {}).get("venueConfigId") or "—"
        return {
            "type": "article",
            "title": "Venue configuration (manifest)",
            "subtitle": f"GET /venue-configs/{vid}",
            "badge": "manifest",
            "fields": [
                {"label": "venueConfigId", "value": str(vid)},
                {"label": "Response preview", "value": _json_preview(payload)},
            ],
        }

    if intent == "b2b_flash_report":
        kind = (payload or {}).get("_flashReport") or plan.get("flashReport") or "sales_event"
        return {
            "type": "article",
            "title": "Flash report (axs-b2b-reports)",
            "subtitle": f"reports-api PUT · {kind}",
            "badge": "b2b reports",
            "fields": [
                {"label": "Report", "value": str(kind)},
                {"label": "contextId", "value": str(plan.get("contextId") or "—")},
                {"label": "eventId", "value": str(plan.get("eventId") or "—")},
                {"label": "regionId", "value": str(plan.get("regionId") or "1")},
                {"label": "Payload preview", "value": _json_preview(payload)},
            ],
        }

    if intent == "reports_inventory_event":
        return {
            "type": "article",
            "title": "Inventory report",
            "subtitle": (
                f"GET /v1/Inventory/contexts/{plan.get('contextId')}/events/"
                f"{plan.get('eventId')}/report"
            ),
            "badge": "b2b reports",
            "fields": [
                {"label": "contextId", "value": str(plan.get("contextId") or "—")},
                {"label": "eventId", "value": str(plan.get("eventId") or "—")},
                {"label": "Payload preview", "value": _json_preview(payload)},
            ],
        }

    if intent == "reports_timezones":
        return {
            "type": "article",
            "title": "Report timezones",
            "subtitle": "GET /v1/Timezones/timezones",
            "badge": "b2b reports",
            "fields": [{"label": "Payload preview", "value": _json_preview(payload)}],
        }

    return None


def format_reports_manifest_text(
    intent: str,
    payload: dict[str, Any] | None,
    plan: dict[str, Any],
    api_error: str | None,
) -> str | None:
    """Plain-text answer from live report/manifest payloads (no answer LLM)."""
    display = build_reports_manifest_display(intent, payload, plan, api_error)
    if not display:
        return None

    if api_error:
        return str(api_error)

    dtype = display.get("type")
    title = str(display.get("title") or intent.replace("_", " "))
    subtitle = display.get("subtitle")
    header = title if not subtitle else f"{title} ({subtitle})"
    lines: list[str] = [header + ":", ""]

    for para in display.get("paragraphs") or []:
        if para:
            lines.append(str(para))

    for field in display.get("fields") or []:
        label = field.get("label") or "field"
        value = field.get("value") or "—"
        if label == "Payload preview" and isinstance(payload, dict) and payload.get("_report_catalog"):
            continue
        lines.append(f"{label}: {value}")

    if dtype == "table":
        rows = display.get("rows") or []
        if rows:
            lines.append("")
            lines.append(f"Available reports ({len(rows)}):")
            for row in rows[:12]:
                if not isinstance(row, dict):
                    continue
                summary = row.get("summary") or row.get("intent") or row.get("path")
                method = row.get("method") or ""
                lines.append(f"- {summary} · {method} {row.get('path', '')}".strip())

    text = "\n".join(lines).strip()
    return text or None
