from __future__ import annotations

from typing import Any

import httpx

from apex_rag_demo.clients.http_common import auth_headers, use_mock_api
from apex_rag_demo.config import APEX_INVENTORY_BASE_URL, APEX_INVENTORY_SWAGGER_URL


def get_event_primary_zones(event_id: str) -> dict[str, Any]:
    url = f"{APEX_INVENTORY_BASE_URL}/events/{event_id}/zones/primary"
    if use_mock_api():
        return {
            "_mock": True,
            "_openapi": APEX_INVENTORY_SWAGGER_URL,
            "endpoint": url,
            "eventId": event_id,
            "zones": [{"zoneId": "demo-zone-1", "name": "GA Floor"}],
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=auth_headers())
        response.raise_for_status()
        return response.json()
