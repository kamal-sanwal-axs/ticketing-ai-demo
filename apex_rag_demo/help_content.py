from __future__ import annotations

import re

SEARCH_SWAGGER_UI = "https://api.apex-dev.axsdevops.io/search/swagger/index.html"
SEARCH_OPENAPI = "https://api.apex-dev.axsdevops.io/search/swagger/v1/swagger.json"
APEX_LOGIN = "https://apex-dev.axsdevops.io/login"

HELP_SUMMARY = "Here's what this assistant can do on apex-dev."
WELCOME_SUMMARY = (
    "Hello! I call live APEX APIs on apex-dev for venues, event search, event details, "
    "inventory zones, and marketing lists.\n\n"
    "Type Help for the full guide, or try an example below."
)

_GENERAL_HELP_PHRASES = frozenset(
    {
        "help",
        "help me",
        "what can you do",
        "what do you do",
        "what can i ask",
        "commands",
        "menu",
        "getting started",
        "how do i use this",
        "show crud operations",
        "crud catalog",
    },
)


def is_general_help_question(bare_question: str) -> bool:
    b = bare_question.lower().strip().rstrip(".!?")
    if b in _GENERAL_HELP_PHRASES:
        return True
    if b.startswith("help ") and len(b) < 40:
        return True
    return False

HELP_EXAMPLE_TABLE = {
    "columns": [
        {"key": "goal", "label": "Goal"},
        {"key": "example", "label": "Example prompt"},
    ],
    "rows": [
        {"goal": "List venues", "example": "List all client venues"},
        {"goal": "Admin users & roles", "example": "Show me users"},
        {"goal": "Search events", "example": "Search events matching Splash House"},
        {
            "goal": "Event details (events API only)",
            "example": "Show details for event id 8f0a2f5c-… only",
        },
        {
            "goal": "Id lookup (event or client venue)",
            "example": "Show event id 019fcc21-… (falls back to search if not an event UUID)",
        },
        {
            "goal": "Event + inventory",
            "example": "Get event 8f0a2f5c-… with inventory",
        },
        {
            "goal": "Inventory zones",
            "example": "Inventory zones for event 8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10",
        },
        {"goal": "Marketing events", "example": "List marketing events"},
        {
            "goal": "Fan buy seat (guidance only)",
            "example": "Explains Events → Inventory → fan checkout → Search orders (not live buy)",
        },
        {
            "goal": "Orders (search)",
            "example": "Search orders for customer email (search-api POST /v1/orders)",
        },
        {
            "goal": "Customers (search)",
            "example": "Search customers for fan@example.com (POST /v1/customers)",
        },
        {
            "goal": "Upcoming events",
            "example": "Show upcoming events",
        },
        {
            "goal": "Best available (inventory)",
            "example": "Show best available for event <event-uuid>",
        },
        {
            "goal": "Customer by name",
            "example": "Show me customers named Kamal",
        },
        {"goal": "Create org (preview)", "example": "Create organization QA Demo Org"},
        {
            "goal": "Create venue (preview)",
            "example": "Create client venue Test Arena for client <client-uuid>",
        },
        {
            "goal": "Update event title",
            "example": "Update event name for event id <uuid> to My Show",
        },
        {
            "goal": "Delete event",
            "example": "Delete event <event-uuid>",
        },
        {
            "goal": "Reset inventory publish",
            "example": "Reset inventory publish for zone <zone-uuid>",
        },
        {
            "goal": "CRUD catalog",
            "example": "Show CRUD operations",
        },
    ],
}

CRUD_CATALOG_TABLE = {
    "columns": [
        {"key": "domain", "label": "API"},
        {"key": "operation", "label": "Kind"},
        {"key": "summary", "label": "Operation"},
        {"key": "http", "label": "HTTP"},
    ],
    "rows": [],
}


def build_help_display() -> dict:
    from apex_rag_demo.crud_registry import catalog_table_rows

    crud_table = {**CRUD_CATALOG_TABLE, "rows": catalog_table_rows()}
    return {
        "type": "article",
        "title": "APEX AI Helper",
        "subtitle": "Plain-English questions → real API calls on api.apex-dev.axsdevops.io (not made-up answers).",
        "badge": "help",
        "paragraphs": [
            "Sign in with your apex-dev JWT. Read-only actions run immediately. "
            "Organization and client-venue creates show a preview first.",
        ],
        "sections": [
            {"title": "Example prompts", "table": HELP_EXAMPLE_TABLE},
            {
                "title": "Writes & safety",
                "paragraphs": [
                    "Reads (search, list events, get event, inventory): always call live APIs.",
                    "Creates, publish, and resets: sent to apex-dev automatically (no extra toggle).",
                    "Updates and deletes: dry-run preview first; click Confirm to apply.",
                    "Set DEMO_MUTATIONS_DRY_RUN=true on the server to force dry-run for all mutations.",
                    "Session memory: each browser tab gets a session id (sessionStorage). "
                    "After you look up an event, follow-ups like “price levels and sections” reuse that "
                    "event id in the same session (not the client-venue list). "
                    "Intents and answers are embedded in Chroma keyed by JWT user id + session id. "
                    "Repeat the same question in that session reuses the LangGraph result; similar "
                    "phrasing (e.g. events with status publish) recalls prior intents.",
                ],
            },
            {"title": "CRUD catalog (events, admin, inventory, marketing)", "table": crud_table},
            {
                "title": "Region in the UI",
                "paragraphs": [
                    "US-West (and other region picks) are a session preference label only. "
                    "They are not sent as a Search API filter. To narrow client venues, "
                    "include organization or client IDs in your message when the API supports it.",
                ],
            },
            {
                "title": "API documentation",
                "links": [
                    {"label": "Search API — Swagger UI", "href": SEARCH_SWAGGER_UI},
                    {"label": "Search OpenAPI JSON", "href": SEARCH_OPENAPI},
                    {"label": "apex-dev login", "href": APEX_LOGIN},
                    {
                        "label": "All services (CLI)",
                        "href": SEARCH_SWAGGER_UI,
                        "note": "python -m apex_rag_demo.main --list-services · docs/API_LINKS.md in repo",
                    },
                ],
            },
        ],
        "footnote": "This helper summarizes API responses only; it does not invent events, prices, or inventory.",
    }


ASSISTANT_NAME = "APEX AI Helper"
IDENTITY_SUMMARY = f"I'm {ASSISTANT_NAME} — your apex-dev ticketing API assistant."


def build_identity_display() -> dict:
    return {
        "type": "article",
        "title": ASSISTANT_NAME,
        "badge": "about",
        "paragraphs": [
            f"I'm {ASSISTANT_NAME} for the apex-dev environment.",
            "I don't chat from general knowledge — I call Search, Admin, Events, Inventory, "
            "and Marketing APIs with your JWT and show the results.",
        ],
        "sections": [
            {"title": "Example prompts", "table": HELP_EXAMPLE_TABLE},
        ],
        "footnote": "Type Help for writes, safety, and documentation links.",
    }


def build_welcome_display() -> dict:
    return {
        "type": "article",
        "title": "Welcome",
        "badge": "welcome",
        "paragraphs": [
            "Hello! I call live APEX APIs on apex-dev for venues, event search, event details, "
            "inventory zones, and marketing lists.",
            "Type Help for the full guide, or try an example below.",
        ],
        "footnote": "This helper summarizes API responses only; it does not invent events, prices, or inventory.",
    }


def format_help_text() -> str:
    lines = [
        HELP_SUMMARY,
        "",
        "Example prompts:",
        "  • List all client venues",
        "  • Search events matching Splash House",
        "  • Get event <event-uuid>",
        "  • Inventory zones for event <event-uuid>",
        "  • List marketing events",
        "",
        "Writes follow CRUD type (create live; update/delete need Confirm). CLI: --execute for live mutations.",
        "",
        f"Search docs: {SEARCH_SWAGGER_UI}",
    ]
    return "\n".join(lines)


def kb_snippets_to_display_items(snippets: list[str], *, max_items: int = 8) -> list[str]:
    """Split long KB chunks into short bullets for the chat UI."""
    items: list[str] = []
    for snippet in snippets[:5]:
        text = str(snippet).strip()
        if not text:
            continue
        if len(text) <= 320:
            items.append(text)
            continue
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text):
            part = part.strip()
            if part:
                items.append(part)
            if len(items) >= max_items:
                break
        if len(items) >= max_items:
            break
    return items[:max_items]
