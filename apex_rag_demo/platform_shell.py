"""APEX v2 shell: axs-b2b-platform + axs-b2b-control + child MFE remotes."""

from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.response_formatters import strip_ui_region

_PLATFORM_QUESTION_RE = re.compile(
    r"("
    r"\b(b2b[- ]?platform|single[- ]?spa|module federation|remote MFE)\b|"
    r"\bwhat (MFE|micro-frontend|apps)\b|"
    r"\baxs[- ]?apex[- ](accounts|control|home)\b|"
    r"\btestrail\s+C9312\b|"
    r"\bplatform shell\b|\bv2 stack\b"
    r")",
    re.I,
)

_APEX_V2_MFES = [
    ("axs-b2b-platform", "Single-spa host; loads auth, control, accounts, home, inventory, search, events, marketing, admin"),
    ("axs-b2b-control", "Chrome: sidebar, header, account menu, platform viewport (hybrid v1/v2 layout)"),
    ("axs-apex-accounts", "Accounts MFE — user/account surfaces (UI shell TestRail C9312PILOT)"),
    ("axs-apex-home / axs-apex-dashboard", "APEX v2 home dashboard (C9203PILOT, HOME-FUNC-*)"),
    ("axs-b2b-dashboard", "v1 ticketing dashboard (dashboard_QA5_US, B2B-DASH-*)"),
    ("axs-apex-search", "Global search: events, customers, orders (permissions b2b_search_*)"),
    ("axs-apex-events", "Event lifecycle & ticket purchase settings"),
    ("axs-apex-inventory", "Inventory creation & zones"),
    ("axs-apex-marketing", "Marketing pixels & catalog"),
    ("axs-apex-admin", "Admin org/client/venue"),
]


def looks_like_platform_shell_question(question: str) -> bool:
    return bool(_PLATFORM_QUESTION_RE.search(strip_ui_region(question)))


def format_platform_shell_guidance() -> str:
    lines = [
        "**APEX v2 platform stack** (from axs-b2b-platform `buildV2StackConfig` + axs-b2b-control permissions):",
        "",
    ]
    for mfe, role in _APEX_V2_MFES:
        lines.append(f"- **{mfe}** — {role}")
    lines.extend(
        [
            "",
            "This chat assistant calls **apex-dev HTTP APIs** (search, events, admin, inventory, marketing, resources). "
            "It does not drive single-spa navigation or UI shell layout tests (C9312PILOT, PLATFORM-* catalog rows).",
            "",
            "Search permissions → assistant intents:",
            "- `b2b_search_events` → search events",
            "- `b2b_search_orders` → search orders",
            "- `b2b_search_customers` → search customers",
            "- `list_users` → B2B user directory (resources/admin)",
        ],
    )
    return "\n".join(lines)


def build_platform_shell_display() -> dict[str, Any]:
    return {
        "type": "article",
        "title": "APEX platform & MFE map",
        "badge": "explain",
        "level": "info",
        "paragraphs": [
            "Child MFEs are hosted by axs-b2b-platform; chrome from axs-b2b-control. "
            "Operational API tasks are available in this assistant per TestRail-mapped intents.",
        ],
        "sections": [
            {
                "title": "APEX v2 remotes",
                "table": {
                    "columns": [
                        {"key": "mfe", "label": "MFE / layer"},
                        {"key": "role", "label": "Role"},
                    ],
                    "rows": [{"mfe": m, "role": r} for m, r in _APEX_V2_MFES],
                },
            },
        ],
    }
