from __future__ import annotations

import json
from typing import Any
import httpx

from apex_rag_demo.clients.http_common import auth_headers, use_mock_api
from apex_rag_demo.config import APEX_ADMIN_BASE_URL, APEX_ADMIN_SWAGGER_URL, DEMO_CLIENT_ID

DEFAULT_ADDRESS = {
    "addressLine": "123 Main St",
    "city": "Portland",
    "state": "OR",
    "zip": "97202",
    "country": "US",
}

DEFAULT_VENUE_MAP = {
    "name": "Main Floor",
    "mmcId": "MMC-DEMO-100",
    "capacity": 5000,
    "sections": [
        {"sectionName": "101", "capacity": 2500},
        {"sectionName": "102", "capacity": 2500},
    ],
}


def build_create_organization_body(plan: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": plan.get("name") or "Demo Organization",
        "currency": plan.get("currency") or "USD",
        "region": plan.get("region") or "US-West",
        "address": {**DEFAULT_ADDRESS, **(plan.get("address") or {})},
    }
    parent = plan.get("parentOrganizationId")
    if parent:
        body["parentOrganizationId"] = parent
    return body


def build_create_client_venue_body(plan: dict[str, Any]) -> dict[str, Any]:
    client_id = plan.get("clientId") or DEMO_CLIENT_ID
    if not client_id:
        raise ValueError(
            "clientId is required for client venue creation. "
            "Set DEMO_CLIENT_ID in .env or include client id in your question.",
        )
    venue_type = plan.get("venueType") or "Open"
    return {
        "clientId": client_id,
        "name": plan.get("name") or "Demo Client Venue",
        "venueType": venue_type,
        "timezoneId": plan.get("timezoneId") or "America/Los_Angeles",
        "address": {**DEFAULT_ADDRESS, **(plan.get("address") or {})},
        "venueMaps": plan.get("venueMaps") or [DEFAULT_VENUE_MAP],
    }


def create_organization(body: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_ADMIN_BASE_URL}/v1/organizations"
    if dry_run or use_mock_api():
        return {
            "_dry_run": dry_run or use_mock_api(),
            "_mock": use_mock_api(),
            "_openapi": APEX_ADMIN_SWAGGER_URL,
            "endpoint": url,
            "request": body,
            "organizationId": "00000000-0000-4000-8000-000000000099",
            "isSuccess": True,
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        return response.json()


def create_client_venue(body: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_ADMIN_BASE_URL}/v1/client-venues"
    if dry_run or use_mock_api():
        return {
            "_dry_run": dry_run or use_mock_api(),
            "_mock": use_mock_api(),
            "_openapi": APEX_ADMIN_SWAGGER_URL,
            "endpoint": url,
            "request": body,
            "clientVenue": {
                "id": "00000000-0000-4000-8000-000000000088",
                "venue": {"name": body.get("name"), "venueType": body.get("venueType")},
            },
            "isSuccess": True,
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        return response.json()


def format_payload(payload: dict[str, Any], max_chars: int = 5000) -> str:
    text = json.dumps(payload, indent=2, default=str)
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text
