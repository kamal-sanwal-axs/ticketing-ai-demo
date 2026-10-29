"""Fan checkout vs back-office APEX flows (from axs-apex-* MFEs)."""

from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.response_formatters import strip_ui_region

_FAN_PURCHASE_RE = re.compile(
    r"("
    r"\b(buy|purchase|order|book|reserve|hold)\b.*\b(seat|seats|ticket|tickets)\b|"
    r"\b(seat|ticket)\b.*\b(for me|for myself)\b|"
    r"\bcan you (buy|get|sell)\b.*\b(ticket|seat)\b|"
    r"\bsell me\b.*\b(ticket|seat)\b|"
    r"\bcheckout\b.*\b(ticket|seat)\b"
    r")",
    re.I,
)

_ORDER_LOOKUP_RE = re.compile(
    r"\b(find|search|lookup|show)\b.*\borders?\b|\borders?\b.*\b(search|number)\b",
    re.I,
)


def looks_like_fan_purchase_request(question: str) -> bool:
    return bool(_FAN_PURCHASE_RE.search(strip_ui_region(question)))


def looks_like_order_search_request(question: str) -> bool:
    bare = strip_ui_region(question)
    if looks_like_fan_purchase_request(bare):
        return False
    return bool(_ORDER_LOOKUP_RE.search(bare))


def format_fan_purchase_guidance(question: str = "") -> str:
    lines = [
        "I can’t complete a **fan seat purchase** from this assistant — checkout runs in the "
        "consumer sales channel after you publish inventory, not via a single back-office API call.",
        "",
        "**How seat sales work in APEX (MFE flow):**",
        "1. **Events** (`axs-apex-events`) — create event, **Ticket purchase** settings (waiting room, sales channels), then **publish** to on-sale.",
        "2. **Inventory** (`axs-apex-inventory`) — map/zone, ticket types, price levels, GA manifest (what fans see in purchase flow).",
        "3. **Admin** (`axs-apex-admin`) — org/client/venue, MMC maps for Pick a Seat.",
        "4. Fans buy seats in the **fan purchase flow** (not exposed here as “buy one seat”).",
        "5. **Search** (`axs-apex-search`) — **Orders** tab to find sold orders (search-api `POST /v1/orders`).",
        "",
        "**What you can ask this assistant:**",
        "• `publish event <event-uuid>`",
        "• `inventory zones for event <event-uuid>` / price codes for event <uuid>",
        "• `show on-sale events` / `search events matching <name>`",
        "• (coming) `search orders for customer <email>` — order search API",
        "",
        "OpenAPI: events `/events/swagger`, inventory `/inventory/swagger`, search `/search/swagger`.",
    ]
    return "\n".join(lines)


def build_fan_purchase_display() -> dict[str, Any]:
    return {
        "type": "article",
        "title": "Fan seat purchase (out of scope for live buy)",
        "badge": "explain",
        "level": "info",
        "paragraphs": [
            "Back-office APEX configures and publishes inventory; fans checkout elsewhere. "
            "Use Search → Orders or POST /v1/orders to verify sales after publish.",
        ],
        "sections": [
            {
                "title": "MFE steps (operator)",
                "table": {
                    "columns": [
                        {"key": "step", "label": "Step"},
                        {"key": "mfe", "label": "MFE"},
                        {"key": "action", "label": "Action"},
                    ],
                    "rows": [
                        {
                            "step": "1",
                            "mfe": "axs-apex-events",
                            "action": "Event settings → ticket purchase; publish event on-sale",
                        },
                        {
                            "step": "2",
                            "mfe": "axs-apex-inventory",
                            "action": "Zones, map, ticket types, price levels, manifest",
                        },
                        {
                            "step": "3",
                            "mfe": "axs-apex-admin",
                            "action": "Client venue + MMC maps (Pick a Seat)",
                        },
                        {
                            "step": "4",
                            "mfe": "Fan channel",
                            "action": "Fan completes purchase (not this chat API)",
                        },
                        {
                            "step": "5",
                            "mfe": "axs-apex-search",
                            "action": "Orders search — POST /v1/orders",
                        },
                    ],
                },
            },
        ],
        "citations": [
            {
                "label": "Search API — POST /v1/orders",
                "href": "https://api.apex-dev.axsdevops.io/search/swagger/v1/swagger.json",
                "status": "read",
            },
            {
                "label": "Inventory API — event zones",
                "href": "https://api.apex-dev.axsdevops.io/inventory/swagger/v1/swagger.json",
                "status": "read",
            },
            {
                "label": "Events API — publish",
                "href": "https://api.apex-dev.axsdevops.io/events/swagger/v1/swagger.json",
                "status": "read",
            },
        ],
    }
