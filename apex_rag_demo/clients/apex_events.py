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
