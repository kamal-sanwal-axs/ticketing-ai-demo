from __future__ import annotations

from typing import Any

from apex_rag_demo.config import (
    APEX_ADMIN_BASE_URL,
    APEX_ADMIN_SWAGGER_URL,
    APEX_RESOURCES_BASE_URL,
    APEX_RESOURCES_SWAGGER_URL,
    RESOURCES_AXS_CLIENT_ID,
    RESOURCES_CLIENT_ID,
)

USERS_DIRECTORY_COLUMNS = [
    {"key": "userId", "label": "User ID"},
    {"key": "email", "label": "Email"},
    {"key": "name", "label": "Name"},
    {"key": "userType", "label": "Type"},
    {"key": "status", "label": "Status"},
    {"key": "emailConfirmed", "label": "Email confirmed"},
    {"key": "lastLoginDate", "label": "Last login"},
    {"key": "mfaEnabled", "label": "MFA"},
]


def _role_name_lookup(roles_payload: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for role in (roles_payload or {}).get("roles") or []:
        if isinstance(role, dict):
            rid = str(role.get("id") or "")
            if rid:
                out[rid] = str(role.get("name") or rid)
    return out


def users_directory_rows(directory: dict[str, Any] | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for user in (directory or {}).get("users") or []:
        if not isinstance(user, dict):
            continue
        first = str(user.get("firstName") or "").strip()
        last = str(user.get("lastName") or "").strip()
        name = f"{first} {last}".strip() or "—"
        rows.append(
            {
                "userId": str(user.get("id") or "—"),
                "email": str(user.get("email") or "—"),
                "name": name,
                "userType": str(user.get("userType") or "—"),
                "status": "disabled" if user.get("isDisabled") else "active",
                "emailConfirmed": "yes" if user.get("emailConfirmed") else "no",
                "lastLoginDate": str(user.get("lastLoginDate") or "—"),
                "mfaEnabled": "yes" if user.get("mfaEnabled") else "no",
            },
        )
    return rows


def admin_user_citations(me: dict[str, Any] | None, directory: dict[str, Any] | None) -> list[dict[str, str]]:
    admin_id = (me or {}).get("adminUserId")
    cites = [
        {
            "label": "resources-api GET /v1/Users",
            "href": (
                f"{APEX_RESOURCES_BASE_URL}/v1/Users"
                f"?ClientId={RESOURCES_CLIENT_ID}&AxsClientId={RESOURCES_AXS_CLIENT_ID}"
            ),
            "status": f"{(directory or {}).get('totalCount', len((directory or {}).get('users') or []))} total",
        },
        {
            "label": "admin-api GET /v1/users/me/workflows",
            "href": f"{APEX_ADMIN_BASE_URL}/v1/users/me/workflows",
            "status": "current user workflows",
        },
        {
            "label": "admin-api GET /v1/roles",
            "href": f"{APEX_ADMIN_BASE_URL}/v1/roles",
            "status": "role catalog (CRUD reference)",
        },
        {
            "label": "resources OpenAPI",
            "href": APEX_RESOURCES_SWAGGER_URL,
            "status": "resources swagger.json",
        },
        {
            "label": "admin OpenAPI",
            "href": APEX_ADMIN_SWAGGER_URL,
            "status": "admin swagger.json",
        },
    ]
    if admin_id:
        cites.insert(
            2,
            {
                "label": f"admin-api GET /v1/users/{admin_id}/assignments",
                "href": f"{APEX_ADMIN_BASE_URL}/v1/users/{admin_id}/assignments",
                "status": "direct role assignments",
            },
        )
    return cites


def build_list_users_display(payload: dict[str, Any] | None) -> dict[str, Any]:
    p = payload or {}
    me = p.get("me") if isinstance(p.get("me"), dict) else {}
    directory = p.get("usersDirectory") if isinstance(p.get("usersDirectory"), dict) else None
    directory_error = p.get("usersDirectoryError")
    user_rows = users_directory_rows(directory)
    roles_payload = p.get("roles") if isinstance(p.get("roles"), dict) else {}
    assignments_payload = p.get("assignments") if isinstance(p.get("assignments"), dict) else {}
    workflows_payload = p.get("workflows") if isinstance(p.get("workflows"), dict) else {}

    role_names = _role_name_lookup(roles_payload)

    workflow_items = []
    raw_wf = workflows_payload.get("workflows")
    if isinstance(raw_wf, list):
        for wf in raw_wf:
            if isinstance(wf, dict):
                workflow_items.append(str(wf.get("name") or "—"))
            else:
                workflow_items.append(str(wf))

    role_rows = []
    for role in (roles_payload.get("roles") or []):
        if not isinstance(role, dict):
            continue
        perms = role.get("permissions") or []
        perm_count = len(perms) if isinstance(perms, list) else 0
        role_rows.append(
            {
                "name": str(role.get("name") or "—"),
                "description": str(role.get("description") or "—"),
                "isInternal": "yes" if role.get("isInternal") else "no",
                "permissionCount": str(perm_count),
                "roleId": str(role.get("id") or "—"),
            },
        )

    assignment_rows = []
    for row in (assignments_payload.get("assignments") or []):
        if not isinstance(row, dict):
            continue
        role_ids = row.get("roleIds") or []
        role_labels = ", ".join(role_names.get(str(rid), str(rid)) for rid in role_ids) if role_ids else "—"
        assignment_rows.append(
            {
                "entityType": str(row.get("entityType") or "—"),
                "entityName": str(row.get("entityName") or "—"),
                "entityId": str(row.get("entityId") or "—"),
                "roles": role_labels,
            },
        )

    paragraphs = [str(p.get("_note") or "")]
    if directory_error:
        paragraphs.append(str(directory_error))
    elif directory is not None:
        total = directory.get("totalCount")
        shown = len(user_rows)
        paragraphs.append(
            f"Showing {shown} user(s)"
            + (f" of {total} total (resources-api)." if total is not None else " from resources-api."),
        )
    errors = p.get("_fetch_errors") or []
    if errors:
        paragraphs.append("Some admin-api calls failed: " + "; ".join(str(e) for e in errors))
    if not me.get("adminUserId"):
        paragraphs.append(
            "No numeric admin user id in JWT — role assignments were not requested. "
            "Ask: show user assignments for user id 10201317",
        )

    sections: list[dict[str, Any]] = []
    if user_rows:
        sections.append(
            {
                "title": "Users (GET /v1/Users)",
                "table": {
                    "columns": USERS_DIRECTORY_COLUMNS,
                    "rows": user_rows,
                },
            },
        )
    elif directory_error:
        sections.append(
            {
                "title": "Users (GET /v1/Users)",
                "paragraphs": [str(directory_error)],
            },
        )

    sections.append(
        {
            "title": "Signed-in user (JWT)",
            "fields": [
                {"label": "Name", "value": me.get("name") or "—"},
                {"label": "Email", "value": me.get("email") or "—"},
                {"label": "Subject (sub)", "value": me.get("subject") or "—"},
                {"label": "Admin user id (numeric)", "value": me.get("adminUserId") or "—"},
            ],
        },
    )
    if workflow_items:
        sections.append(
            {
                "title": "Workflows (GET /v1/users/me/workflows)",
                "items": workflow_items,
            },
        )
    if role_rows:
        sections.append(
            {
                "title": "Roles catalog (GET /v1/roles)",
                "table": {
                    "columns": [
                        {"key": "name", "label": "Role"},
                        {"key": "description", "label": "Description"},
                        {"key": "isInternal", "label": "Internal"},
                        {"key": "permissionCount", "label": "# permissions"},
                        {"key": "roleId", "label": "Role ID"},
                    ],
                    "rows": role_rows,
                },
            },
        )
    if assignment_rows:
        sections.append(
            {
                "title": "Role assignments",
                "table": {
                    "columns": [
                        {"key": "entityType", "label": "Entity type"},
                        {"key": "entityName", "label": "Entity"},
                        {"key": "entityId", "label": "Entity ID"},
                        {"key": "roles", "label": "Roles"},
                    ],
                    "rows": assignment_rows,
                },
            },
        )

    return {
        "paragraphs": [x for x in paragraphs if x],
        "sections": sections,
        "citations": admin_user_citations(me, directory),
        "user_count": len(user_rows),
        "role_count": len(role_rows),
        "assignment_count": len(assignment_rows),
    }
