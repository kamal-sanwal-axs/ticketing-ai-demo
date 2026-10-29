from __future__ import annotations

import json
from typing import Any

import httpx

from apex_rag_demo.clients.http_common import auth_headers, use_mock_api
from apex_rag_demo.config import APEX_INVENTORY_BASE_URL, APEX_INVENTORY_SWAGGER_URL

INVENTORY_AUTH_SCOPE_MESSAGE = (
    "Inventory API returned 401/403 for this JWT on publish-data or ticket-types. "
    "Primary zone (GET …/zones/primary) may still work. Ask your tenant admin for "
    "inventory read access on apex-dev, or use a token with inventory API scope."
)


def _problem_details_hint(response: httpx.Response) -> str:
    """Pull traceId / detail from inventory ProblemDetails JSON when present."""
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(body, dict):
        return ""
    bits: list[str] = []
    detail = str(body.get("detail") or "").strip()
    if detail and detail.lower() not in ("internal system error", "internal server error."):
        bits.append(detail)
    trace = str(body.get("traceId") or body.get("trace_id") or "").strip()
    if trace:
        bits.append(f"traceId {trace}")
    if not bits and response.status_code >= 500:
        return " (inventory service error on apex-dev — not caused by this demo client)"
    return f" ({'; '.join(bits)})" if bits else ""


def _inventory_error_label(method_path: str, exc: Exception) -> tuple[str, bool]:
    """Return (message, is_auth_scope)."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return INVENTORY_AUTH_SCOPE_MESSAGE, True
        hint = _problem_details_hint(exc.response)
        return f"{method_path}: HTTP {code}{hint}", False
    return f"{method_path}: {exc}", False


def _mock_zone_details(event_id: str) -> dict[str, Any]:
    pl_ga = "pl-ga-floor"
    pl_balc = "pl-balcony"
    sec_a = "sec-101"
    sec_b = "sec-102"
    pc_std = "pc-standard"
    return {
        "_mock": True,
        "_openapi": APEX_INVENTORY_SWAGGER_URL,
        "eventId": event_id,
        "primary": {
            "zone": {
                "id": "demo-zone-1",
                "eventId": event_id,
                "description": "Admissions",
                "type": 0,
                "mmcMapId": "mmc-map-demo-42",
                "clientVenueId": "demo-client-venue",
                "venueCapacity": 5000,
            },
            "sections": {
                sec_a: {
                    "id": sec_a,
                    "zoneId": "demo-zone-1",
                    "priceLevelId": pl_ga,
                },
                sec_b: {
                    "id": sec_b,
                    "zoneId": "demo-zone-1",
                    "priceLevelId": pl_balc,
                },
            },
            "priceLevels": {
                pl_ga: {
                    "id": pl_ga,
                    "description": "GA Floor",
                    "color": "#4CAF50",
                },
                pl_balc: {
                    "id": pl_balc,
                    "description": "Balcony",
                    "color": "#2196F3",
                },
            },
        },
        "publish": {
            "zones": [
                {
                    "id": "demo-zone-1",
                    "description": "Admissions",
                    "type": "Admissions",
                    "mmcMapId": "mmc-map-demo-42",
                    "priceCodes": {pc_std: 0},
                    "priceChart": [
                        {"priceCodeId": pc_std, "priceLevelId": pl_ga, "price": 49.5},
                        {"priceCodeId": pc_std, "priceLevelId": pl_balc, "price": 39.0},
                    ],
                    "gaSections": [
                        {"id": sec_a, "sectionName": "101", "priceLevelId": pl_ga},
                        {"id": sec_b, "sectionName": "102", "priceLevelId": pl_balc},
                    ],
                },
            ],
            "priceLevels": {
                pl_ga: {"id": pl_ga, "description": "GA Floor", "color": "#4CAF50"},
                pl_balc: {"id": pl_balc, "description": "Balcony", "color": "#2196F3"},
            },
            "priceCodes": {
                pc_std: {
                    "id": pc_std,
                    "description": "Standard",
                    "type": "Standard",
                    "pricingMode": "Dynamic",
                },
            },
        },
        "ticketTypes": {
            "ticketTypes": [
                {
                    "id": "tt-1",
                    "name": "General admission",
                    "category": "Standard",
                    "minQty": 1,
                    "maxQty": 8,
                    "statusCode": {"id": "sc-open", "description": "Open"},
                    "priceChart": [
                        {"priceLevelId": pl_ga, "price": 49.5},
                        {"priceLevelId": pl_balc, "price": 39.0},
                    ],
                },
            ],
            "facilityFee": 2.5,
        },
    }


def get_event_primary_zones(event_id: str) -> dict[str, Any]:
    url = f"{APEX_INVENTORY_BASE_URL}/events/{event_id}/zones/primary"
    if use_mock_api():
        snap = _mock_zone_details(event_id)
        return {
            "_mock": True,
            "_openapi": APEX_INVENTORY_SWAGGER_URL,
            "endpoint": url,
            "eventId": event_id,
            **snap["primary"],
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=auth_headers())
        response.raise_for_status()
        return response.json()


def get_event_zones_publish_data(
    event_id: str,
    *,
    client_venue_id: str | None = None,
) -> dict[str, Any]:
    url = f"{APEX_INVENTORY_BASE_URL}/events/{event_id}/zones/publish-data"
    if use_mock_api():
        return _mock_zone_details(event_id)["publish"]
    params: dict[str, str] = {}
    if client_venue_id:
        # OpenAPI query name is client_venue_id (C# binding: clientVenueId).
        params["client_venue_id"] = client_venue_id
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=auth_headers(), params=params or None)
        response.raise_for_status()
        return response.json()


def get_zone_ticket_types(zone_id: str) -> dict[str, Any]:
    url = f"{APEX_INVENTORY_BASE_URL}/zones/{zone_id}/ticket-types"
    if use_mock_api():
        return _mock_zone_details("mock-event")["ticketTypes"]
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=auth_headers())
        response.raise_for_status()
        return response.json()


def get_event_inventory_snapshot(
    event_id: str,
    *,
    client_venue_id: str | None = None,
    include_ticket_types: bool = True,
) -> dict[str, Any]:
    """Primary zone, publish data (price codes/chart), and ticket types for UI."""
    if use_mock_api():
        return _mock_zone_details(event_id)

    errors: list[str] = []
    auth_scope_limited = False
    primary: dict[str, Any] | None = None
    publish: dict[str, Any] | None = None
    ticket_types: dict[str, Any] | None = None

    def _note(path: str, exc: Exception) -> None:
        nonlocal auth_scope_limited
        msg, is_auth = _inventory_error_label(path, exc)
        if is_auth:
            auth_scope_limited = True
            if INVENTORY_AUTH_SCOPE_MESSAGE not in errors:
                errors.append(msg)
        else:
            errors.append(msg)

    try:
        primary = get_event_primary_zones(event_id)
    except Exception as exc:  # noqa: BLE001
        _note(f"GET /events/{event_id}/zones/primary", exc)

    cv_id = client_venue_id
    if not cv_id and isinstance(primary, dict):
        zone = primary.get("zone")
        if isinstance(zone, dict) and zone.get("clientVenueId"):
            cv_id = str(zone["clientVenueId"])

    try:
        publish = get_event_zones_publish_data(event_id, client_venue_id=cv_id)
    except Exception as exc:  # noqa: BLE001
        _note(f"GET /events/{event_id}/zones/publish-data", exc)

    zone_id: str | None = None
    if isinstance(primary, dict):
        zone = primary.get("zone")
        if isinstance(zone, dict) and zone.get("id"):
            zone_id = str(zone["id"])

    if zone_id and include_ticket_types and not auth_scope_limited:
        try:
            ticket_types = get_zone_ticket_types(zone_id)
        except Exception as exc:  # noqa: BLE001
            _note(f"GET /zones/{zone_id}/ticket-types", exc)

    return {
        "eventId": event_id,
        "primary": primary,
        "publish": publish,
        "ticketTypes": ticket_types,
        "_fetch_errors": errors,
        "_inventory_auth_scope_limited": auth_scope_limited,
    }


def create_zone(plan: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_INVENTORY_BASE_URL}/zones"
    body = {
        "eventId": plan.get("eventId"),
        "clientVenueId": plan.get("clientVenueId"),
        "sections": plan.get("sections") or ["101"],
        "venueCapacity": int(plan.get("venueCapacity") or 1000),
    }
    body = {k: v for k, v in body.items() if v}
    if dry_run or use_mock_api():
        return {"_dry_run": dry_run, "_mock": use_mock_api(), "endpoint": url, "request": body}
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        return response.json() if response.content else {"request": body}


def reset_zone_publish(zone_id: str, *, dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_INVENTORY_BASE_URL}/zones/{zone_id}/publish-status"
    body = plan_reset_body()
    if dry_run or use_mock_api():
        return {
            "_dry_run": dry_run,
            "_mock": use_mock_api(),
            "endpoint": url,
            "zoneId": zone_id,
            "request": body,
            "_reset": False,
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.patch(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        return response.json() if response.content else {"zoneId": zone_id, "_reset": True}


def plan_reset_body() -> dict[str, Any]:
    import uuid

    return {"operationId": str(uuid.uuid4()), "state": "NotStarted"}
