from __future__ import annotations

from typing import Any

import httpx

from apex_rag_demo.clients.http_common import auth_headers, use_mock_api
from apex_rag_demo.config import APEX_MANIFEST_BASE_URL, APEX_MANIFEST_SWAGGER_URL


def _mock_venue_config(venue_config_id: str) -> dict[str, Any]:
    return {
        "_mock": True,
        "_openapi": APEX_MANIFEST_SWAGGER_URL,
        "venueConfigId": venue_config_id,
        "venueName": "Demo Venue (mock)",
        "note": "Set APEX_BEARER_TOKEN for live manifest-api GET /venue-configs/{id}.",
    }


def get_venue_config(venue_config_id: str) -> dict[str, Any]:
    vid = (venue_config_id or "").strip()
    if not vid:
        return {"error": "venueConfigId required"}
    if use_mock_api():
        return _mock_venue_config(vid)
    url = f"{APEX_MANIFEST_BASE_URL}/venue-configs/{vid}"
    with httpx.Client(timeout=45.0, follow_redirects=True) as client:
        response = client.get(url, headers=auth_headers())
        response.raise_for_status()
        body = response.json()
        if isinstance(body, dict):
            body.setdefault("_openapi", APEX_MANIFEST_SWAGGER_URL)
            body.setdefault("venueConfigId", vid)
        return body if isinstance(body, dict) else {"data": body, "venueConfigId": vid}
