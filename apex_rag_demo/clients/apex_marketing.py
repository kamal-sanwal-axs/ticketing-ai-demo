from __future__ import annotations

from typing import Any

import httpx

from apex_rag_demo.clients.http_common import auth_headers, use_mock_api
from apex_rag_demo.config import (
    APEX_MARKETING_BASE_URL,
    APEX_MARKETING_SWAGGER_URL,
    MARKETING_FALLBACK_SEARCH_QUERY,
    MARKETING_LIST_PAGE_SIZE,
)


def list_events() -> dict[str, Any]:
    url = f"{APEX_MARKETING_BASE_URL}/v1/events"
    if use_mock_api():
        return {
            "_mock": True,
            "_openapi": APEX_MARKETING_SWAGGER_URL,
            "endpoint": url,
            "events": [{"eventId": "demo-1", "name": "Demo Marketing Event"}],
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=auth_headers())
        response.raise_for_status()
        return response.json()


def list_events_with_search_fallback(
    *,
    fallback_query: str | None = None,
    page_size: int | None = None,
) -> dict[str, Any]:
    """Marketing catalog; on 401/403 falls back to Search POST /v1/events."""
    query = fallback_query or MARKETING_FALLBACK_SEARCH_QUERY
    size = page_size or MARKETING_LIST_PAGE_SIZE
    try:
        return list_events()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code not in (401, 403):
            raise
        from apex_rag_demo.clients import apex_search

        payload = apex_search.search_events(query, page_size=size)
        payload["_source"] = "search-api-fallback"
        payload["_marketing_status"] = exc.response.status_code
        payload["_marketing_url"] = f"{APEX_MARKETING_BASE_URL}/v1/events"
        payload["_fallback_query"] = query
        return payload


def list_pixels(event_id: str) -> dict[str, Any]:
    url = f"{APEX_MARKETING_BASE_URL}/v1/events/{event_id}/pixels"
    if use_mock_api():
        return {"_mock": True, "endpoint": url, "pixels": []}
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=auth_headers())
        response.raise_for_status()
        return response.json()


def create_pixel(event_id: str, plan: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_MARKETING_BASE_URL}/v1/events/{event_id}/pixels"
    body = plan.get("body") or {"name": plan.get("name") or "Demo pixel"}
    if dry_run or use_mock_api():
        return {"_dry_run": dry_run, "_mock": use_mock_api(), "endpoint": url, "request": body}
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        return response.json() if response.content else {"eventId": event_id}


def update_pixel(
    event_id: str,
    pixel_id: str,
    plan: dict[str, Any],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    url = f"{APEX_MARKETING_BASE_URL}/v1/events/{event_id}/pixels/{pixel_id}"
    body = plan.get("body") or {"name": plan.get("name") or "Updated pixel"}
    if dry_run or use_mock_api():
        return {"_dry_run": dry_run, "_mock": use_mock_api(), "endpoint": url, "request": body}
    with httpx.Client(timeout=60.0) as client:
        response = client.put(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        return response.json() if response.content else {"pixelId": pixel_id}


def delete_pixel(event_id: str, pixel_id: str, *, dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_MARKETING_BASE_URL}/v1/events/{event_id}/pixels/{pixel_id}"
    if dry_run or use_mock_api():
        return {"_dry_run": dry_run, "_mock": use_mock_api(), "endpoint": url}
    with httpx.Client(timeout=60.0) as client:
        response = client.delete(url, headers=auth_headers())
        response.raise_for_status()
        return {"eventId": event_id, "pixelId": pixel_id, "_deleted": True}
