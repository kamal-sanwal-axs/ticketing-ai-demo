"""APEX v2 MFEs covered by TestRail / smoke / integration tests (operational assistant scope)."""

from __future__ import annotations

# Eleven product MFEs (+ platform host is not a feature surface for this assistant).
APEX_11_MFES: tuple[str, ...] = (
    "axs-apex-admin",
    "axs-apex-events",
    "axs-apex-marketing",
    "axs-apex-search",
    "axs-apex-inventory",
    "axs-apex-home",
    "axs-apex-accounts",
    "axs-apex-control",
    "axs-b2b-control",
    "axs-b2b-platform",
    "axs-apex-auth",
    "axs-b2b-reports",
)

# Home dashboard is the same remote as home (TestRail on axs-apex-home only).
APEX_MFE_ALIASES: dict[str, str] = {
    "axs-apex-dashboard": "axs-apex-home",
}

OPERATIONAL_INTENTS: frozenset[str] = frozenset(
    {
        "search_events",
        "search_orders",
        "search_order_payment_statuses",
        "search_customers",
        "list_client_venues",
        "list_users",
        "create_organization",
        "create_client_venue",
        "get_event",
        "update_event",
        "delete_event",
        "create_event",
        "publish_event",
        "update_organization",
        "update_client_venue",
        "create_inventory_zone",
        "reset_inventory_publish",
        "update_inventory_ticket_types",
        "update_inventory_ga_manifest",
        "list_marketing_pixels",
        "create_marketing_pixel",
        "update_marketing_pixel",
        "delete_marketing_pixel",
        "inventory_zones",
        "marketing_events",
        "get_venue_config",
        "b2b_flash_report",
        "reports_inventory_event",
        "reports_timezones",
    },
)
