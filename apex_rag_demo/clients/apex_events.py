from __future__ import annotations

from typing import Any

import httpx

from apex_rag_demo.clients.http_common import auth_headers, use_mock_api
from apex_rag_demo.config import APEX_EVENTS_BASE_URL, APEX_EVENTS_SWAGGER_URL


def get_event(event_id: str) -> dict[str, Any]:
    url = f"{APEX_EVENTS_BASE_URL}/{event_id}"
    if use_mock_api():
        return {
            "_mock": True,
            "_openapi": APEX_EVENTS_SWAGGER_URL,
            "endpoint": url,
            "eventId": event_id,
            "name": "Demo Event",
            "status": "Draft",
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=auth_headers())
        response.raise_for_status()
        return response.json()


def update_event(event_id: str, body: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_EVENTS_BASE_URL}/{event_id}"
    if dry_run or use_mock_api():
        return {
            "_dry_run": dry_run or use_mock_api(),
            "_mock": use_mock_api(),
            "_openapi": APEX_EVENTS_SWAGGER_URL,
            "endpoint": url,
            "eventId": event_id,
            "request": body,
            "previousHeadliners": body.get("_previousHeadliners"),
            "headliners": body.get("headliners"),
            "isSuccess": True,
        }
    put_body = {k: v for k, v in body.items() if not str(k).startswith("_")}
    with httpx.Client(timeout=60.0) as client:
        response = client.put(url, headers=auth_headers(), json=put_body)
        if response.status_code == 204:
            return {
                "eventId": event_id,
                "_updated": True,
                "headliners": put_body.get("headliners"),
                "endpoint": url,
            }
        response.raise_for_status()
        if response.content:
            return response.json()
        return {"eventId": event_id, "_updated": True, "headliners": put_body.get("headliners")}


def delete_event(event_id: str, *, dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_EVENTS_BASE_URL}/{event_id}"
    if dry_run or use_mock_api():
        return {
            "_dry_run": dry_run or use_mock_api(),
            "_mock": use_mock_api(),
            "endpoint": url,
            "eventId": event_id,
            "_deleted": False,
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.delete(url, headers=auth_headers())
        response.raise_for_status()
        return {"eventId": event_id, "_deleted": True, "endpoint": url}


def create_event(plan: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_EVENTS_BASE_URL}/"
    body = {
        "headliners": plan.get("headliners") or "Demo event",
        "clientVenueId": plan.get("clientVenueId"),
    }
    body = {k: v for k, v in body.items() if v}
    if dry_run or use_mock_api():
        return {
            "_dry_run": dry_run or use_mock_api(),
            "_mock": use_mock_api(),
            "endpoint": url,
            "request": body,
            "eventId": "00000000-0000-4000-8000-00000000e1",
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        data = response.json() if response.content else {}
        return {**data, "endpoint": url, "request": body}


def publish_event(event_id: str, *, dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_EVENTS_BASE_URL}/{event_id}/publish"
    if dry_run or use_mock_api():
        return {
            "_dry_run": dry_run or use_mock_api(),
            "_mock": use_mock_api(),
            "endpoint": url,
            "eventId": event_id,
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=auth_headers())
        response.raise_for_status()
        return {"eventId": event_id, "_published": True, "endpoint": url}
