from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from apex_rag_demo.crud_policy import WriteKind

_UUID = (
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_UUID_RE = re.compile(_UUID)


@dataclass(frozen=True)
class CrudCatalogEntry:
    intent: str
    domain: str
    kind: WriteKind
    summary: str
    http: str


# Full CRUD catalog (Events, Admin, Inventory, Marketing) for help/docs and policy.
CRUD_CATALOG: tuple[CrudCatalogEntry, ...] = (
    # Events
    CrudCatalogEntry("create_event", "events", WriteKind.CREATE, "Create event", "POST /events"),
    CrudCatalogEntry("get_event", "events", WriteKind.READ, "Get event by id", "GET /events/{eventId}"),
    CrudCatalogEntry("update_event", "events", WriteKind.UPDATE, "Replace event (title, dates, …)", "PUT /events/{eventId}"),
    CrudCatalogEntry("delete_event", "events", WriteKind.DELETE, "Delete event", "DELETE /events/{eventId}"),
    CrudCatalogEntry("publish_event", "events", WriteKind.CREATE, "Publish event", "POST /events/{eventId}/publish"),
    # Admin
    CrudCatalogEntry(
        "create_organization",
        "admin",
        WriteKind.CREATE,
        "Create organization",
        "POST /admin/v1/organizations",
    ),
    CrudCatalogEntry(
        "create_client_venue",
        "admin",
        WriteKind.CREATE,
        "Create client venue",
        "POST /admin/v1/client-venues",
    ),
    CrudCatalogEntry(
        "update_organization",
        "admin",
        WriteKind.UPDATE,
        "Patch organization",
        "PATCH /admin/v1/organizations/{organizationId}",
    ),
    CrudCatalogEntry(
        "update_client_venue",
        "admin",
        WriteKind.UPDATE,
        "Update client venue",
        "PUT /admin/v1/client-venues/{clientVenueId}",
    ),
    CrudCatalogEntry(
        "list_users",
        "resources",
        WriteKind.READ,
        "List B2B users (directory)",
        "GET /resources/v1/Users",
    ),
    # Inventory
    CrudCatalogEntry(
        "inventory_zones",
        "inventory",
        WriteKind.READ,
        "Primary zone + price levels",
        "GET /inventory/events/{eventId}/zones/primary",
    ),
    CrudCatalogEntry(
        "create_inventory_zone",
        "inventory",
        WriteKind.CREATE,
        "Add admissions zone",
        "POST /inventory/zones",
    ),
    CrudCatalogEntry(
        "update_inventory_ticket_types",
        "inventory",
        WriteKind.UPDATE,
        "Save ticket types",
        "POST /inventory/zones/{zoneId}/ticket-types",
    ),
    CrudCatalogEntry(
        "update_inventory_ga_manifest",
        "inventory",
        WriteKind.UPDATE,
        "Save GA manifest grid",
        "POST /inventory/zones/{zoneId}/manifest/general-admission",
    ),
    CrudCatalogEntry(
        "reset_inventory_publish",
        "inventory",
        WriteKind.RESET,
        "Reset zone publish lifecycle",
        "PATCH /inventory/zones/{zoneId}/publish-status",
    ),
    # Marketing
    CrudCatalogEntry("marketing_events", "marketing", WriteKind.READ, "List events", "GET /marketing/v1/events"),
    CrudCatalogEntry(
        "list_marketing_pixels",
        "marketing",
        WriteKind.READ,
        "List pixels for event",
        "GET /marketing/v1/events/{eventId}/pixels",
    ),
    CrudCatalogEntry(
        "create_marketing_pixel",
        "marketing",
        WriteKind.CREATE,
        "Create tracking pixel",
        "POST /marketing/v1/events/{eventId}/pixels",
    ),
    CrudCatalogEntry(
        "update_marketing_pixel",
        "marketing",
        WriteKind.UPDATE,
        "Update pixel",
        "PUT /marketing/v1/events/{eventId}/pixels/{pixelId}",
    ),
    CrudCatalogEntry(
        "delete_marketing_pixel",
        "marketing",
        WriteKind.DELETE,
        "Delete pixel",
        "DELETE /marketing/v1/events/{eventId}/pixels/{pixelId}",
    ),
)


@dataclass
class _Matcher:
    intent: str
    pattern: re.Pattern[str]
    priority: int = 0


def _m(pattern: str, intent: str, priority: int = 0) -> _Matcher:
    return _Matcher(intent=intent, pattern=re.compile(pattern, re.I), priority=priority)


# Higher priority runs first (delete/update before generic get with uuid).
MUTATION_MATCHERS: tuple[_Matcher, ...] = tuple(
    sorted(
        (
            _m(rf"\bdelete\s+marketing\s+pixel\b.*{_UUID}.*{_UUID}", "delete_marketing_pixel", 100),
            _m(rf"\bdelete\s+pixel\b.*{_UUID}.*{_UUID}", "delete_marketing_pixel", 95),
            _m(rf"\bdelete\s+event\b.*{_UUID}", "delete_event", 100),
            _m(rf"\bupdate\s+marketing\s+pixel\b.*{_UUID}", "update_marketing_pixel", 90),
            _m(rf"\bupdate\s+organization\b.*{_UUID}", "update_organization", 90),
            _m(rf"\bupdate\s+client\s+venue\b.*{_UUID}", "update_client_venue", 90),
            _m(rf"\b(reset|unpublish)\s+.*publish\b.*{_UUID}", "reset_inventory_publish", 85),
            _m(rf"\breset\s+inventory\s+publish\b.*{_UUID}", "reset_inventory_publish", 85),
            _m(rf"\b(create|add)\s+marketing\s+pixel\b.*{_UUID}", "create_marketing_pixel", 80),
            _m(rf"\b(create|add)\s+inventory\s+zone\b.*{_UUID}", "create_inventory_zone", 80),
            _m(r"\bpublish\b.*\bAINV-\d+\b", "publish_event", 81),
            _m(rf"\bpublish\s+event\b.*{_UUID}", "publish_event", 78),
            _m(rf"\bpublish\b.*{_UUID}", "publish_event", 77),
            _m(rf"{_UUID}.*\bpublish\b", "publish_event", 77),
            _m(rf"\bevent\s+id\s+{_UUID}.*\bpublish", "publish_event", 79),
            _m(r"\bpublish\s+(the\s+)?events?\b", "publish_event", 76),
            _m(r"\bpublish\s+it\b", "publish_event", 76),
            _m(rf"\b(create|new)\s+event\b", "create_event", 70),
            _m(rf"\blist\s+marketing\s+pixels\b.*{_UUID}", "list_marketing_pixels", 60),
        ),
        key=lambda m: -m.priority,
    ),
)


def match_mutation_intent(question: str) -> str | None:
    from apex_rag_demo.event_update import looks_like_update_event_name

    if looks_like_update_event_name(question):
        return "update_event"
    for matcher in MUTATION_MATCHERS:
        if matcher.pattern.search(question):
            return matcher.intent
    return None


def catalog_table_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in CRUD_CATALOG:
        rows.append(
            {
                "domain": entry.domain,
                "operation": entry.kind.value,
                "intent": entry.intent,
                "summary": entry.summary,
                "http": entry.http,
            },
        )
    return rows
