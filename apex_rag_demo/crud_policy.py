from __future__ import annotations

from enum import Enum


class WriteKind(str, Enum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESET = "reset"


# Intent → write classification for consent and dry-run policy.
INTENT_WRITE_KIND: dict[str, WriteKind] = {
    "explain": WriteKind.READ,
    "search_events": WriteKind.READ,
    "search_orders": WriteKind.READ,
    "search_order_payment_statuses": WriteKind.READ,
    "search_customers": WriteKind.READ,
    "list_client_venues": WriteKind.READ,
    "list_users": WriteKind.READ,
    "marketing_events": WriteKind.READ,
    "get_event": WriteKind.READ,
    "inventory_zones": WriteKind.READ,
    "get_venue_config": WriteKind.READ,
    "b2b_flash_report": WriteKind.READ,
    "reports_inventory_event": WriteKind.READ,
    "reports_timezones": WriteKind.READ,
    "list_marketing_pixels": WriteKind.READ,
    "create_organization": WriteKind.CREATE,
    "create_client_venue": WriteKind.CREATE,
    "create_event": WriteKind.CREATE,
    "create_marketing_pixel": WriteKind.CREATE,
    "create_inventory_zone": WriteKind.CREATE,
    "update_event": WriteKind.UPDATE,
    "update_organization": WriteKind.UPDATE,
    "update_client_venue": WriteKind.UPDATE,
    "update_marketing_pixel": WriteKind.UPDATE,
    "update_inventory_ticket_types": WriteKind.UPDATE,
    "update_inventory_ga_manifest": WriteKind.UPDATE,
    "publish_event": WriteKind.CREATE,
    "delete_event": WriteKind.DELETE,
    "delete_marketing_pixel": WriteKind.DELETE,
    "reset_inventory_publish": WriteKind.RESET,
    "reset_hierarchy_cache": WriteKind.RESET,
}


def write_kind_for_intent(intent: str) -> WriteKind:
    return INTENT_WRITE_KIND.get(intent, WriteKind.READ)


def requires_human_confirmation(intent: str) -> bool:
    kind = write_kind_for_intent(intent)
    return kind in (WriteKind.UPDATE, WriteKind.DELETE)


def allows_without_confirmation(intent: str) -> bool:
    return write_kind_for_intent(intent) == WriteKind.RESET


def needs_live_writes(intent: str) -> bool:
    return write_kind_for_intent(intent) != WriteKind.READ


def mutation_executes_live(
    intent: str,
    *,
    confirm_mutation: bool = False,
    mutations_dry_run: bool = False,
) -> bool:
    """Whether a non-read intent should call apex-dev (vs dry-run preview)."""
    if mutations_dry_run:
        return False
    kind = write_kind_for_intent(intent)
    if kind == WriteKind.READ:
        return False
    if kind in (WriteKind.UPDATE, WriteKind.DELETE):
        return bool(confirm_mutation)
    return True


def is_dry_run_payload(payload: dict | None) -> bool:
    return isinstance(payload, dict) and bool(payload.get("_dry_run"))
