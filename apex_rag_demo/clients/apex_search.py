from __future__ import annotations

import json
from typing import Any

import httpx

from apex_rag_demo.clients.http_common import auth_headers, use_mock_api
from apex_rag_demo.config import APEX_SEARCH_BASE_URL

MOCK_SUGGEST_RESPONSE: dict[str, Any] = {
    "suggestions": [
        {"id": "demo-event-1", "name": "Demo Concert Night", "venueName": "Demo Arena"},
        {"id": "demo-event-2", "name": "Demo Festival", "venueName": "Demo Park"},
    ],
}


def search_events_suggest(query: str, size: int = 5) -> dict[str, Any]:
    """POST /v1/events/suggest — smallest read-only search surface."""
    if use_mock_api():
        return {**MOCK_SUGGEST_RESPONSE, "_mock": True, "_query": query}

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


def format_api_payload(payload: dict[str, Any], max_chars: int = 4000) -> str:
    text = json.dumps(payload, indent=2, default=str)
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text
