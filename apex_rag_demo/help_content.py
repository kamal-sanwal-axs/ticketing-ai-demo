from __future__ import annotations

SEARCH_SWAGGER_UI = "https://api.apex-dev.axsdevops.io/search/swagger/index.html"
SEARCH_OPENAPI = "https://api.apex-dev.axsdevops.io/search/swagger/v1/swagger.json"
APEX_LOGIN = "https://apex-dev.axsdevops.io/login"

HELP_SUMMARY = "Here's what this assistant can do on apex-dev."
WELCOME_SUMMARY = "Hello! Here's how to get started on apex-dev."

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
        {"goal": "Search events", "example": "Search events matching Splash House"},
        {
            "goal": "Event details",
            "example": "Get event 8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10",
        },
        {
            "goal": "Inventory zones",
            "example": "Inventory zones for event 8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10",
        },
        {"goal": "Marketing events", "example": "List marketing events"},
        {"goal": "Create org (preview)", "example": "Create organization QA Demo Org"},
        {
            "goal": "Create venue (preview)",
            "example": "Create client venue Test Arena for client <client-uuid>",
        },
    ],
}


def build_help_display() -> dict:
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
                    "Organization and client-venue creates are dry-run by default: you see the JSON "
                    "that would be sent—nothing is posted until you opt in.",
                    "In the web UI, enable Live writes on the chat bar. From the CLI, use "
                    "--execute or DEMO_EXECUTE_WRITES=true. Always review payloads before "
                    "posting to a shared dev tenant.",
                ],
            },
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
    display = build_help_display()
    display["title"] = "Welcome"
    display["badge"] = "welcome"
    display["paragraphs"] = [
        "Hello! I call live APEX APIs on apex-dev for venues, event search, event details, "
        "inventory zones, and marketing lists.",
        "Type Help for the full guide, or try an example below.",
    ]
    return display


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
        "Writes: dry-run by default. Enable Live writes (web checkbox) or --execute for real POSTs.",
        "",
        f"Search docs: {SEARCH_SWAGGER_UI}",
    ]
    return "\n".join(lines)
