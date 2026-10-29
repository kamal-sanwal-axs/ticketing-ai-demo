from __future__ import annotations

from typing import Any

import httpx

from apex_rag_demo.clients.http_common import auth_headers, use_mock_api
from apex_rag_demo.config import (
    APEX_RESOURCES_BASE_URL,
    APEX_RESOURCES_SWAGGER_URL,
    RESOURCES_AXS_CLIENT_ID,
    RESOURCES_CLIENT_ID,
)


def list_users(
    *,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    client_id: int | None = None,
    axs_client_id: int | None = None,
    is_disabled: bool | None = None,
) -> dict[str, Any]:
    """GET /v1/Users — B2B user directory (resources-api), same as axs-b2b-admin user list."""
    url = f"{APEX_RESOURCES_BASE_URL}/v1/Users"
    params: dict[str, Any] = {
        "ClientId": client_id if client_id is not None else RESOURCES_CLIENT_ID,
        "AxsClientId": axs_client_id if axs_client_id is not None else RESOURCES_AXS_CLIENT_ID,
        "Limit": limit,
        "Offset": offset,
    }
    if search:
        params["Search"] = search.strip()
    if is_disabled is not None:
        params["IsDisabled"] = is_disabled

    if use_mock_api():
        return {
            "_mock": True,
            "_endpoint": url,
            "success": True,
            "users": [
                {
                    "id": 10201317,
                    "email": "admin@axs.com",
                    "firstName": "Demo",
                    "lastName": "Admin",
                    "userType": "B2B",
                    "isDisabled": False,
                    "emailConfirmed": True,
                    "mfaEnabled": False,
                },
            ],
            "count": 1,
            "totalCount": 1,
        }

    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=auth_headers(), params=params)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            data["_endpoint"] = url
        return data
