from __future__ import annotations

import json
from typing import Any

import httpx

from apex_rag_demo.clients.http_common import auth_headers, use_mock_api
from apex_rag_demo.config import APEX_SEARCH_BASE_URL, APEX_SEARCH_SWAGGER_URL

MOCK_CLIENT_VENUES_RESPONSE: dict[str, Any] = {
    "clientVenues": [
        {
            "id": "8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10",
            "venue": {"name": "Demo Arena West"},
            "client": {"name": "Demo Client US-West"},
        },
        {
            "id": "9a1b3c4d-5e6f-4789-a012-3456789abcde",
            "venue": {"name": "Coastal Pavilion"},
            "client": {"name": "West Coast Promoters"},
        },
    ],
}

MOCK_SUGGEST_RESPONSE: dict[str, Any] = {
    "suggestions": [
        {"id": "demo-event-1", "name": "Demo Concert Night", "venueName": "Demo Arena"},
        {"id": "demo-event-2", "name": "Demo Festival", "venueName": "Demo Park"},
    ],
}


def search_events_suggest(query: str, size: int = 5) -> dict[str, Any]:
    """POST /v1/events/suggest — smallest read-only search surface."""
    if use_mock_api():
        return {
            **MOCK_SUGGEST_RESPONSE,
            "_mock": True,
            "_openapi": APEX_SEARCH_SWAGGER_URL,
            "_query": query,
        }

    url = f"{APEX_SEARCH_BASE_URL}/v1/events/suggest"
    body = {"query": query, "size": size}
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        return response.json()


def search_events(query: str, page_size: int = 5) -> dict[str, Any]:
    """POST /v1/events — full search (used if suggest is too thin)."""
    if use_mock_api():
        return {
            "events": [
                {
                    "id": "demo-event-1",
                    "name": f"Demo result for '{query}'",
                    "status": "Published",
                }
            ],
            "_mock": True,
            "_openapi": APEX_SEARCH_SWAGGER_URL,
        }

    url = f"{APEX_SEARCH_BASE_URL}/v1/events"
    body = {
        "query": query,
        "pagination": {"size": page_size, "from": 0},
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        return response.json()


def search_client_venues(
    page_size: int = 25,
    organization_ids: list[str] | None = None,
    client_ids: list[str] | None = None,
    venue_ids: list[str] | None = None,
) -> dict[str, Any]:
    """POST /v1/client-venues — list/search client venues (read-only)."""
    if use_mock_api():
        return {
            **MOCK_CLIENT_VENUES_RESPONSE,
            "_mock": True,
            "_openapi": APEX_SEARCH_SWAGGER_URL,
        }

    url = f"{APEX_SEARCH_BASE_URL}/v1/client-venues"
    body: dict[str, Any] = {
        "pagination": {"size": page_size, "from": 0},
    }
    if organization_ids:
        body["organizationIds"] = organization_ids
    if client_ids:
        body["clientIds"] = client_ids
    if venue_ids:
        body["venueIds"] = venue_ids

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        return response.json()


def format_api_payload(payload: dict[str, Any], max_chars: int = 4000) -> str:
    text = json.dumps(payload, indent=2, default=str)
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text
