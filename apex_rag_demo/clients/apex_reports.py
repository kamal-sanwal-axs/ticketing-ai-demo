from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from apex_rag_demo.clients.http_common import auth_headers, use_mock_api
from apex_rag_demo.config import APEX_REPORTS_BASE_URL, APEX_REPORTS_SWAGGER_URL

_FLASH_PATHS: dict[str, str] = {
    "sales_event": "/v1/Sales/event",
    "sales_date_range": "/v1/Sales/dateRange",
    "ticket_lifecycle": "/v1/TicketLifeCycle/event",
    "ticket_in_transfer": "/v1/TicketInTransfer/event",
}


def _mock_flash(kind: str, plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "_mock": True,
        "_openapi": APEX_REPORTS_SWAGGER_URL,
        "flashReport": kind,
        "contextId": plan.get("contextId"),
        "eventId": plan.get("eventId"),
        "rows": [{"label": "Demo row", "quantity": 0, "amount": 0.0}],
        "note": "Live call needs reports API permission on apex-dev JWT.",
    }


def _flash_body(kind: str, plan: dict[str, Any]) -> dict[str, Any]:
    locale = str(plan.get("locale") or "en-US")
    context_id = int(plan.get("contextId") or -1)
    event_id = int(plan.get("eventId") or -1)
    if kind == "sales_date_range":
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        return {
            "locale": locale,
            "payload": {
                "contextId": context_id,
                "timeZoneId": int(plan.get("timeZoneId") or 1),
                "startDateTime": str(plan.get("startDateTime") or start.isoformat()),
                "endDateTime": str(plan.get("endDateTime") or end.isoformat()),
            },
        }
    return {
        "locale": locale,
        "payload": {
            "contextId": context_id,
            "eventId": event_id,
            "zoneIds": plan.get("zoneIds") or [],
        },
    }


def run_flash_report(plan: dict[str, Any]) -> dict[str, Any]:
    kind = str(plan.get("flashReport") or "sales_event")
    path = _FLASH_PATHS.get(kind)
    if not path:
        return {"error": f"Unknown flashReport {kind}"}
    if use_mock_api():
        return _mock_flash(kind, plan)
    region_id = str(plan.get("regionId") or "1")
    url = f"{APEX_REPORTS_BASE_URL}{path}"
    params = {"regionId": region_id}
    body = _flash_body(kind, plan)
    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
        response = client.put(url, params=params, json=body, headers=auth_headers())
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            data.setdefault("_flashReport", kind)
            data.setdefault("_openapi", APEX_REPORTS_SWAGGER_URL)
        return data if isinstance(data, dict) else {"data": data, "_flashReport": kind}


def get_inventory_event_report(context_id: int, event_id: int) -> dict[str, Any]:
    if use_mock_api():
        return {
            "_mock": True,
            "_openapi": APEX_REPORTS_SWAGGER_URL,
            "contextId": context_id,
            "eventId": event_id,
            "summary": "Inventory report (mock)",
        }
    url = f"{APEX_REPORTS_BASE_URL}/v1/Inventory/contexts/{context_id}/events/{event_id}/report"
    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
        response = client.get(url, headers=auth_headers())
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            data.setdefault("_openapi", APEX_REPORTS_SWAGGER_URL)
        return data if isinstance(data, dict) else {"data": data}


def list_report_timezones() -> dict[str, Any]:
    if use_mock_api():
        return {
            "_mock": True,
            "_openapi": APEX_REPORTS_SWAGGER_URL,
            "timezones": [{"id": 1, "name": "Pacific Time (mock)"}],
        }
    url = f"{APEX_REPORTS_BASE_URL}/v1/Timezones/timezones"
    with httpx.Client(timeout=45.0, follow_redirects=True) as client:
        response = client.get(url, headers=auth_headers())
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {"timezones": data}
