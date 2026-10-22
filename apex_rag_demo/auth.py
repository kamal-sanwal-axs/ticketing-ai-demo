from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from apex_rag_demo.clients.http_common import auth_headers, set_request_bearer
from apex_rag_demo.config import APEX_ADMIN_BASE_URL

REGIONS = (
    {"id": "US-West", "label": "United States — West"},
    {"id": "US-East", "label": "United States — East"},
    {"id": "EU-West", "label": "Europe — West"},
)


def decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode JWT payload without signature verification (demo display only)."""
    parts = token.strip().split(".")
    if len(parts) < 2:
        return {}
    segment = parts[1]
    padding = "=" * (-len(segment) % 4)
    try:
        raw = base64.urlsafe_b64decode(segment + padding)
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}


def profile_from_token(token: str, region: str) -> dict[str, Any]:
    claims = decode_jwt_payload(token)
    name = (
        claims.get("name")
        or claims.get("given_name")
        or claims.get("preferred_username")
        or claims.get("email")
        or "APEX User"
    )
    email = claims.get("email") or claims.get("sub") or ""
    user_id = claims.get("sub") or claims.get("user_id") or ""
    return {
        "name": name,
        "email": email,
        "userId": user_id,
        "region": region,
        "tenant": claims.get("tenant") or claims.get("TENANT") or "apex-dev",
    }


def validate_token_with_admin(token: str) -> tuple[bool, str | None]:
    """Light check: call an authenticated admin route."""
    set_request_bearer(token)
    url = f"{APEX_ADMIN_BASE_URL}/v1/users/me/workflows"
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, headers=auth_headers())
        if response.status_code == 401:
            return False, "Token rejected (401). Sign in to apex-dev and copy a fresh JWT."
        if response.status_code == 403:
            return False, "Token valid but forbidden (403) for admin workflows."
        if response.status_code >= 400:
            return False, f"Admin API returned {response.status_code}."
        return True, None
    except httpx.HTTPError as exc:
        return False, f"Could not reach admin API: {exc}"
