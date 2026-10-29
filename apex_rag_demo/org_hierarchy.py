from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apex_rag_demo.clients import apex_admin


@dataclass
class HierarchyIndex:
    principal_org_name: str = "—"
    org_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    client_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    cv_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    loaded: bool = False
    error: str | None = None

    def org_names_for_client(self, client_id: str | None) -> tuple[str, str]:
        if not client_id:
            return self.principal_org_name, "—"
        client = self.client_by_id.get(client_id) or {}
        org_id = client.get("parentId")
        principal, contractual = self._walk_orgs(org_id)
        if principal == "—" and self.principal_org_name != "—":
            principal = self.principal_org_name
        return principal, contractual

    def _walk_orgs(self, start_org_id: str | None) -> tuple[str, str]:
        principal = contractual = "—"
        current = start_org_id
        visited: set[str] = set()
        while current and current not in visited:
            visited.add(current)
            org = self.org_by_id.get(current)
            if not org:
                break
            name = str(org.get("name") or "—")
            type_label = str(
                org.get("organizationTypeName") or org.get("organizationType") or "",
            ).lower()
            if "principal" in type_label:
                principal = name
            elif "contractual" in type_label:
                contractual = name
            current = org.get("parentId")
        return principal, contractual

    def for_client_venue_id(self, client_venue_id: str | None) -> dict[str, str]:
        cv = self.cv_by_id.get(client_venue_id or "") if client_venue_id else None
        client_id = cv.get("parentId") if cv else None
        client = self.client_by_id.get(client_id or "") if client_id else None
        principal, contractual = self.org_names_for_client(client_id)
        return {
            "principalOrganization": principal,
            "contractualOrganization": contractual,
            "client": str((client or {}).get("name") or "—"),
            "clientVenue": str((cv or {}).get("name") or "—"),
            "clientVenueId": str(client_venue_id or "—"),
        }

    def for_event(self, ev: dict[str, Any]) -> dict[str, str]:
        cv_id = str(ev.get("clientVenueId") or ev.get("ClientVenueId") or "")
        base = self.for_client_venue_id(cv_id or None)
        if base["clientVenue"] == "—":
            venue = ev.get("venue") or {}
            if isinstance(venue, dict) and venue.get("name"):
                base["clientVenue"] = str(venue["name"])
        if base["client"] == "—":
            client = ev.get("client") or {}
            if isinstance(client, dict) and client.get("name"):
                base["client"] = str(client["name"])
        return base


_ctx: HierarchyIndex | None = None


def reset_hierarchy_cache() -> None:
    global _ctx
    _ctx = None


def get_hierarchy_index() -> HierarchyIndex:
    global _ctx
    if _ctx is not None:
        return _ctx
    _ctx = _load_hierarchy_index()
    return _ctx


def hierarchy_for_event_list(use_admin_tree: bool) -> HierarchyIndex:
    """Empty index (no org columns) unless caller asked for admin org tree."""
    return get_hierarchy_index() if use_admin_tree else HierarchyIndex(loaded=False)


def _load_hierarchy_index() -> HierarchyIndex:
    index = HierarchyIndex(loaded=False)
    try:
        principals_payload = apex_admin.get_principal_organizations()
        organizations = principals_payload.get("organizations") or []
        if not organizations:
            index.error = "No principal organizations returned from admin API."
            return index
        principal = organizations[0]
        principal_id = str(principal.get("id") or "")
        index.principal_org_name = str(principal.get("name") or "—")
        if not principal_id:
            index.error = "Principal organization id missing."
            return index

        tree_payload = apex_admin.get_principal_organization_tree(principal_id)
        nodes = tree_payload.get("nodes") or {}
        for org in nodes.get("organizations") or []:
            if isinstance(org, dict) and org.get("id"):
                index.org_by_id[str(org["id"])] = org
        for client in nodes.get("clients") or []:
            if isinstance(client, dict) and client.get("id"):
                index.client_by_id[str(client["id"])] = client
        for cv in nodes.get("clientVenues") or []:
            if isinstance(cv, dict) and cv.get("id"):
                index.cv_by_id[str(cv["id"])] = cv
        index.loaded = True
    except Exception as exc:  # noqa: BLE001 — enrich only
        index.error = str(exc)
    return index
