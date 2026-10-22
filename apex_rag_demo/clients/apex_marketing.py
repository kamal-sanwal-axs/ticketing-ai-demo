from __future__ import annotations

from typing import Any

import httpx

from apex_rag_demo.clients.http_common import auth_headers, use_mock_api
from apex_rag_demo.config import APEX_MARKETING_BASE_URL, APEX_MARKETING_SWAGGER_URL


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
