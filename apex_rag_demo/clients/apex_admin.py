from __future__ import annotations

import json
from typing import Any
import httpx

from apex_rag_demo.clients.http_common import auth_headers, use_mock_api
from apex_rag_demo.config import APEX_ADMIN_BASE_URL, APEX_ADMIN_SWAGGER_URL, DEMO_CLIENT_ID

DEFAULT_ADDRESS = {
    "addressLine": "123 Main St",
    "city": "Portland",
    "state": "OR",
    "zip": "97202",
    "country": "US",
}

DEFAULT_VENUE_MAP = {
    "name": "Main Floor",
    "mmcId": "MMC-DEMO-100",
    "capacity": 5000,
    "sections": [
        {"sectionName": "101", "capacity": 2500},
        {"sectionName": "102", "capacity": 2500},
    ],
}


def build_create_organization_body(plan: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": plan.get("name") or "Demo Organization",
        "currency": plan.get("currency") or "USD",
        "region": plan.get("region") or "US-West",
        "address": {**DEFAULT_ADDRESS, **(plan.get("address") or {})},
    }
    parent = plan.get("parentOrganizationId")
    if parent:
        body["parentOrganizationId"] = parent
    return body


def build_create_client_venue_body(plan: dict[str, Any]) -> dict[str, Any]:
    client_id = plan.get("clientId") or DEMO_CLIENT_ID
    if not client_id:
        raise ValueError(
            "clientId is required for client venue creation. "
            "Set DEMO_CLIENT_ID in .env or include client id in your question.",
        )
    venue_type = plan.get("venueType") or "Open"
    return {
        "clientId": client_id,
        "name": plan.get("name") or "Demo Client Venue",
        "venueType": venue_type,
        "timezoneId": plan.get("timezoneId") or "America/Los_Angeles",
        "address": {**DEFAULT_ADDRESS, **(plan.get("address") or {})},
        "venueMaps": plan.get("venueMaps") or [DEFAULT_VENUE_MAP],
    }


def create_organization(body: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_ADMIN_BASE_URL}/v1/organizations"
    if dry_run or use_mock_api():
        return {
            "_dry_run": dry_run or use_mock_api(),
            "_mock": use_mock_api(),
            "_openapi": APEX_ADMIN_SWAGGER_URL,
            "endpoint": url,
            "request": body,
            "organizationId": "00000000-0000-4000-8000-000000000099",
            "isSuccess": True,
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        return response.json()


def create_client_venue(body: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_ADMIN_BASE_URL}/v1/client-venues"
    if dry_run or use_mock_api():
        return {
            "_dry_run": dry_run or use_mock_api(),
            "_mock": use_mock_api(),
            "_openapi": APEX_ADMIN_SWAGGER_URL,
            "endpoint": url,
            "request": body,
            "clientVenue": {
                "id": "00000000-0000-4000-8000-000000000088",
                "venue": {"name": body.get("name"), "venueType": body.get("venueType")},
            },
            "isSuccess": True,
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        return response.json()


def get_current_user_workflows() -> dict[str, Any]:
    url = f"{APEX_ADMIN_BASE_URL}/v1/users/me/workflows"
    if use_mock_api():
        return {
            "_mock": True,
            "_endpoint": url,
            "workflows": [{"name": "EventOwner"}, {"name": "InventoryManager"}],
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=auth_headers())
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return {"workflows": data, "_endpoint": url}
        return {**data, "_endpoint": url}


def get_roles(is_internal: bool | None = None) -> dict[str, Any]:
    url = f"{APEX_ADMIN_BASE_URL}/v1/roles"
    params: dict[str, str] = {}
    if is_internal is not None:
        params["isInternal"] = "true" if is_internal else "false"
    if use_mock_api():
        return {
            "_mock": True,
            "_endpoint": url,
            "isSuccess": True,
            "roles": [
                {
                    "id": "00000000-0000-4000-8000-000000000010",
                    "name": "Event Owner",
                    "description": "Manage events for assigned org nodes",
                    "isInternal": False,
                    "permissions": [],
                },
            ],
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=auth_headers(), params=params or None)
        response.raise_for_status()
        return {**response.json(), "_endpoint": url}


def get_user_assignments(admin_user_id: str | int) -> dict[str, Any]:
    uid = str(admin_user_id).strip()
    url = f"{APEX_ADMIN_BASE_URL}/v1/users/{uid}/assignments"
    if use_mock_api():
        return {
            "_mock": True,
            "_endpoint": url,
            "isSuccess": True,
            "assignments": [
                {
                    "entityType": "Organization",
                    "entityId": "00000000-0000-4000-8000-00000001",
                    "entityName": "Demo Principal",
                    "roleIds": ["00000000-0000-4000-8000-000000000010"],
                },
            ],
            "nodes": {},
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=auth_headers())
        response.raise_for_status()
        return {**response.json(), "_endpoint": url}


def list_users_admin_snapshot(
    *,
    admin_user_id: str | None = None,
    jwt_claims: dict[str, Any] | None = None,
    resources_users: dict[str, Any] | None = None,
    resources_error: str | None = None,
    user_search: str | None = None,
    users_limit: int = 50,
    users_offset: int = 0,
) -> dict[str, Any]:
    """
    Resources-api user directory plus admin-api workflows, roles, and assignments.
    """
    from apex_rag_demo.auth import admin_numeric_user_id_from_claims
    from apex_rag_demo.clients import apex_resources

    claims = jwt_claims or {}
    directory: dict[str, Any] | None = resources_users
    directory_error = resources_error
    if directory is None and directory_error is None:
        try:
            directory = apex_resources.list_users(
                search=user_search,
                limit=users_limit,
                offset=users_offset,
            )
        except Exception as exc:  # noqa: BLE001
            directory_error = f"GET /v1/Users: {exc}"
    resolved_admin_id = (admin_user_id or "").strip() or admin_numeric_user_id_from_claims(claims)
    me = {
        "name": claims.get("name") or claims.get("email") or "—",
        "email": claims.get("email") or "—",
        "subject": claims.get("sub") or "—",
        "adminUserId": resolved_admin_id,
    }
    errors: list[str] = []
    workflows: dict[str, Any] | None = None
    roles: dict[str, Any] | None = None
    assignments: dict[str, Any] | None = None

    try:
        workflows = get_current_user_workflows()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"GET /v1/users/me/workflows: {exc}")

    try:
        roles = get_roles()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"GET /v1/roles: {exc}")

    target_id = resolved_admin_id
    if target_id:
        try:
            assignments = get_user_assignments(str(target_id))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"GET /v1/users/{target_id}/assignments: {exc}")

    return {
        "me": me,
        "usersDirectory": directory,
        "usersDirectoryError": directory_error,
        "workflows": workflows,
        "roles": roles,
        "assignments": assignments,
        "_fetch_errors": errors,
        "_note": (
            "User directory: resources-api GET /v1/Users (same as B2B Admin user list). "
            "Supplemental: admin-api workflows, roles catalog, and GET /v1/users/{id}/assignments."
        ),
    }


def get_principal_organizations() -> dict[str, Any]:
    url = f"{APEX_ADMIN_BASE_URL}/v1/organizations/principal"
    if use_mock_api():
        return {
            "_mock": True,
            "isSuccess": True,
            "organizations": [{"id": "00000000-0000-4000-8000-00000001", "name": "Demo Principal"}],
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=auth_headers())
        response.raise_for_status()
        return response.json()


def get_principal_organization_tree(principal_organization_id: str) -> dict[str, Any]:
    url = f"{APEX_ADMIN_BASE_URL}/v1/organizations/principals/{principal_organization_id}/tree"
    if use_mock_api():
        pid = principal_organization_id
        cid = "00000000-0000-4000-8000-00000002"
        cvid = "00000000-0000-4000-8000-00000003"
        return {
            "_mock": True,
            "isSuccess": True,
            "nodes": {
                "organizations": [
                    {
                        "id": pid,
                        "name": "Demo Principal",
                        "organizationTypeName": "Principal",
                        "parentId": None,
                    },
                    {
                        "id": "00000000-0000-4000-8000-00000004",
                        "name": "Demo Contractual",
                        "organizationTypeName": "Contractual",
                        "parentId": pid,
                    },
                ],
                "clients": [{"id": cid, "name": "Demo Client", "parentId": "00000000-0000-4000-8000-00000004"}],
                "clientVenues": [{"id": cvid, "name": "Demo Arena", "parentId": cid}],
            },
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=auth_headers())
        response.raise_for_status()
        return response.json()


def patch_organization(organization_id: str, body: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_ADMIN_BASE_URL}/v1/organizations/{organization_id}"
    if dry_run or use_mock_api():
        return {
            "_dry_run": dry_run or use_mock_api(),
            "_mock": use_mock_api(),
            "endpoint": url,
            "organizationId": organization_id,
            "request": body,
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.patch(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        return response.json() if response.content else {"organizationId": organization_id, "_updated": True}


def update_client_venue(client_venue_id: str, body: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    url = f"{APEX_ADMIN_BASE_URL}/v1/client-venues/{client_venue_id}"
    if dry_run or use_mock_api():
        return {
            "_dry_run": dry_run or use_mock_api(),
            "_mock": use_mock_api(),
            "endpoint": url,
            "clientVenueId": client_venue_id,
            "request": body,
        }
    with httpx.Client(timeout=60.0) as client:
        response = client.put(url, headers=auth_headers(), json=body)
        response.raise_for_status()
        return response.json() if response.content else {"clientVenueId": client_venue_id, "_updated": True}


def format_payload(payload: dict[str, Any], max_chars: int = 5000) -> str:
    text = json.dumps(payload, indent=2, default=str)
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text
