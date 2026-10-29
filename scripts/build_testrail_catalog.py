#!/usr/bin/env python3
"""Harvest TestRail / integration catalog rows from axs-apex-* MFEs and apex-* APIs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_APEX_ROOT = Path("/Users/kamals/Documents/axs/apex")
_OUT = _REPO_ROOT / "data" / "testrail_catalog.json"

_TESTRAIL_RE = re.compile(r"\b(C\d{5,}|C\d+PILOT)\b", re.I)
_SPEC_RE = re.compile(r"`([a-z0-9-]+)`", re.I)


def _infer_intent(row: dict[str, Any]) -> str | None:
    text = " ".join(
        str(row.get(k) or "")
        for k in ("title", "description", "method", "spec", "suite")
    ).lower()
    if "customer" in text and ("search" in text or "/v1/customers" in text or "getcustomers" in text):
        return "search_customers"
    if "getorders" in text or "order search" in text or "/v1/orders" in text:
        return "search_orders"
    if "paymentstatus" in text or "payment-status" in text:
        return "search_order_payment_statuses"
    if "post/events/suggest" in text or "events/suggest" in text or "suggest" in text and "event" in text:
        return "search_events"
    if "post /v1/events" in text or "getevents" in text or "search events" in text:
        return "search_events"
    if "client-venues" in text or "client venues" in text or "listclientvenues" in text:
        return "list_client_venues"
    if "marketing" in text and "event" in text and "get" in text:
        return "marketing_events"
    if "publish" in text and "event" in text:
        return "publish_event"
    if "createevent" in text or "post-events" in text or "create event" in text:
        return "create_event"
    if "geteventbyid" in text or "get event" in text:
        return "get_event"
    if "putevent" in text or "update event" in text:
        return "update_event"
    if "best available" in text or "bestavailable" in text:
        return "inventory_zones"
    if "inventory" in text or "zones" in text or "mapselection" in text or "ticket type" in text:
        return "inventory_zones"
    if "organization" in text and "create" in text:
        return "create_organization"
    if "client venue" in text and "create" in text:
        return "create_client_venue"
    if "pixel" in text:
        return "list_marketing_pixels"
    if "users" in text or "roles" in text or "b2b_search" in text and "users" in text:
        return "list_users"
    if "upcoming" in text and "event" in text:
        return "marketing_events"
    if "home-func" in text and ("upcoming" in text or "events query" in text or "empty state" in text):
        return "marketing_events"
    if "buy" in text or ("purchase" in text and "seat" in text):
        return "explain"
    return None


_OPERATIONAL_EXAMPLE: dict[str, str] = {
    "search_customers": "show me customers for kamal@example.com",
    "search_orders": "search orders for customer kamal@example.com",
    "search_order_payment_statuses": "list order payment statuses for splash",
    "search_events": "search events matching lakers",
    "marketing_events": "show upcoming events",
    "list_client_venues": "list all client venues",
    "get_event": "get event <event-uuid> with inventory",
    "create_event": "create a new event called Demo Show",
    "publish_event": "publish event <event-uuid>",
    "inventory_zones": "show best available for event <event-uuid>",
    "list_users": "list users",
    "create_organization": "create organization QA Demo Org",
    "update_event": "update event <event-uuid> title to New Name",
    "list_marketing_pixels": "list marketing pixels",
}


def _example_prompt(intent: str | None, row: dict[str, Any]) -> str | None:
    if not intent:
        return None
    if intent == "explain":
        desc = str(row.get("description") or row.get("title") or "").lower()
        if "buy" in desc or "purchase" in desc or "seat" in desc:
            return "buy one seat for this event"
        return None
    return _OPERATIONAL_EXAMPLE.get(intent)


def _parse_ui_tests_md(path: Path, mfe: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if "|" not in line or line.strip().startswith("|---"):
            continue
        m = _TESTRAIL_RE.search(line)
        if not m:
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        title = parts[0] if parts else line
        tid = m.group(1).upper()
        row = {
            "testrail_id": tid,
            "title": title,
            "mfe": mfe,
            "source": str(path.relative_to(_APEX_ROOT)) if path.is_relative_to(_APEX_ROOT) else str(path),
            "kind": "ui",
        }
        row["assistant_intent"] = _infer_intent(row)
        row["example_prompt"] = _example_prompt(row["assistant_intent"], row)
        row["chat_automatable"] = bool(row.get("example_prompt") and row["assistant_intent"] != "explain")
        rows.append(row)
    return rows


def _parse_api_tests_md(path: Path, service: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| Active") and not line.startswith("| Skipped"):
            continue
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]
        if len(parts) < 6:
            continue
        status = "skipped" if parts[0].lower() == "skipped" else "active"
        col1 = parts[1]
        if col1.startswith("C") and len(parts) >= 6:
            testrail, suite, _class, method, desc = col1, parts[2], parts[3], parts[4], parts[5]
            jira, spec_cell = None, ""
        elif len(parts) >= 7:
            jira, spec_cell, suite, _class, method, desc = (
                parts[1],
                parts[2],
                parts[3],
                parts[4],
                parts[5],
                parts[6],
            )
            tid = _TESTRAIL_RE.search(spec_cell + " " + method + " " + desc)
            testrail = tid.group(1).upper() if tid else None
        else:
            continue
        row = {
            "testrail_id": testrail,
            "jira": jira if jira and jira != "—" else None,
            "spec": spec_cell,
            "suite": suite,
            "method": method,
            "description": desc,
            "service": service,
            "source": str(path.relative_to(_APEX_ROOT)) if path.is_relative_to(_APEX_ROOT) else str(path),
            "kind": "api",
            "status": status,
        }
        row["title"] = desc or method
        row["mfe"] = f"apex-{service}-api"
        row["assistant_intent"] = _infer_intent(row)
        row["example_prompt"] = _example_prompt(row["assistant_intent"], row)
        row["chat_automatable"] = bool(
            row.get("example_prompt")
            and row["status"] == "active"
            and row["assistant_intent"] != "explain",
        )
        rows.append(row)
    return rows


def _parse_testrail_markdown(path: Path, service: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n### Test Case", text)
    for block in blocks[1:]:
        tid = re.search(r"\*\*TestRail ID:\*\*\s*(C\d+)", block)
        title_m = re.search(r"^\d+:\s*(.+)$", block.strip().splitlines()[0] if block.strip() else "")
        title = title_m.group(1).strip() if title_m else "API test case"
        row = {
            "testrail_id": tid.group(1) if tid else None,
            "title": title,
            "service": service,
            "mfe": f"apex-{service}-api",
            "source": str(path.relative_to(_APEX_ROOT)) if path.is_relative_to(_APEX_ROOT) else str(path),
            "kind": "api",
            "status": "active",
        }
        row["assistant_intent"] = _infer_intent({**row, "description": title})
        row["example_prompt"] = _example_prompt(row["assistant_intent"], row)
        row["chat_automatable"] = bool(row.get("example_prompt") and row["assistant_intent"] != "explain")
        rows.append(row)
    return rows


def _parse_testrail_table_md(path: Path, mfe: str) -> list[dict[str, Any]]:
    """QAA markdown tables: | Case ID | Title |."""
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if "|" not in line or line.strip().startswith("|---"):
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 2:
            continue
        if parts[0].lower() in ("case id", "test", "case"):
            continue
        tid_m = _TESTRAIL_RE.search(parts[0] + " " + " ".join(parts))
        if not tid_m:
            continue
        title = parts[1] if len(parts) > 1 else parts[0]
        row = {
            "testrail_id": tid_m.group(1).upper(),
            "title": title,
            "mfe": mfe,
            "source": str(path.relative_to(_APEX_ROOT)) if path.is_relative_to(_APEX_ROOT) else str(path),
            "kind": "ui",
        }
        row["assistant_intent"] = _infer_intent(row)
        row["example_prompt"] = _example_prompt(row["assistant_intent"], row)
        row["chat_automatable"] = bool(row.get("example_prompt") and row["assistant_intent"] != "explain")
        rows.append(row)
    return rows


def _synthetic_home_operational_catalog() -> list[dict[str, Any]]:
    """Unit/smoke rows from axs-apex-home — only API-backed operator flows."""
    home_tests = [
        ("HOME-FUNC-02", "passes search query args to useGetEventsQuery on mount", "marketing_events"),
        ("HOME-FUNC-03", "renders the upcoming events section", "marketing_events"),
        ("HOME-FUNC-04", "maps events into upcoming event links", "marketing_events"),
        ("HOME-FUNC-07", "empty state when no upcoming events", "marketing_events"),
        ("HOME-FUNC-08", "navigate to events from empty state", "marketing_events"),
    ]
    rows: list[dict[str, Any]] = []
    for tid, title, intent in home_tests:
        rows.append(
            {
                "testrail_id": tid,
                "title": title,
                "mfe": "axs-apex-home",
                "source": "axs-apex-home/src/components/Home/Home.test.tsx",
                "kind": "unit",
                "assistant_intent": intent,
                "example_prompt": _example_prompt(intent, {"title": title, "description": title}),
                "chat_automatable": True,
            },
        )
    return rows


def _synthetic_control_permissions_catalog() -> list[dict[str, Any]]:
    """axs-b2b-control permissions mirror Search MFE API smoke."""
    permission_intents = [
        ("b2b_search_events", "search_events", "search events matching lakers"),
        ("b2b_search_orders", "search_orders", "search orders for kamal@example.com"),
        ("b2b_search_customers", "search_customers", "show me customers for kamal@example.com"),
    ]
    rows: list[dict[str, Any]] = []
    for perm, intent, prompt in permission_intents:
        rows.append(
            {
                "testrail_id": f"PERM-{perm}",
                "title": f"permission {perm} gates search API",
                "mfe": "axs-b2b-control",
                "source": "axs-b2b-control/src/constants/permissions.ts",
                "kind": "permission",
                "assistant_intent": intent,
                "example_prompt": prompt,
                "chat_automatable": True,
            },
        )
    return rows


def build() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []

    ui_sources = [
        ("axs-apex-admin", "axs-apex-admin/tests/integration/ui/TESTS.md"),
        ("axs-apex-events", "axs-apex-events/tests/integration/ui/TESTS.md"),
        ("axs-apex-marketing", "axs-apex-marketing/tests/integration/ui/TESTS.md"),
        ("axs-apex-search", "axs-apex-search/tests/integration/ui/TESTS.md"),
        ("axs-apex-inventory", "axs-apex-inventory/tests/integration/ui/TESTS.md"),
        ("axs-apex-home", "axs-apex-home/tests/integration/ui/TESTS.md"),
        ("axs-apex-accounts", "axs-apex-accounts/tests/integration/ui/TESTS.md"),
    ]
    for mfe, rel in ui_sources:
        entries.extend(_parse_ui_tests_md(_APEX_ROOT / rel, mfe))

    for md in (_APEX_ROOT / "axs-apex-accounts/tests/integration/framework/testrail").glob("*.md"):
        entries.extend(_parse_ui_tests_md(md, "axs-apex-accounts"))

    entries.extend(_synthetic_home_operational_catalog())
    entries.extend(_synthetic_control_permissions_catalog())

    for md in (_APEX_ROOT / "axs-apex-home/tests/integration/framework/testrail").glob("*.md"):
        entries.extend(_parse_testrail_table_md(md, "axs-apex-home"))

    for md in (_APEX_ROOT / "axs-apex-admin/tests/integration/framework/testrail").glob("*.md"):
        entries.extend(_parse_ui_tests_md(md, "axs-apex-admin"))
    for md in (_APEX_ROOT / "axs-apex-events/tests/integration/framework/testrail").glob("*.md"):
        entries.extend(_parse_ui_tests_md(md, "axs-apex-events"))
    for md in (_APEX_ROOT / "axs-apex-marketing/tests/integration/framework/testrail").glob("*.md"):
        entries.extend(_parse_ui_tests_md(md, "axs-apex-marketing"))
    for md in (_APEX_ROOT / "axs-apex-search/tests/integration/framework/testrail").glob("*.md"):
        entries.extend(_parse_ui_tests_md(md, "axs-apex-search"))

    api_tests = [
        ("search", "apex-search-api/tests/integration/APEX.Search.WebApi.ITests/Controllers/Orders/V1/TESTS.md"),
        ("search", "apex-search-api/tests/integration/APEX.Search.WebApi.ITests/Controllers/Events/V1/TESTS.md"),
        ("search", "apex-search-api/tests/integration/APEX.Search.WebApi.ITests/Controllers/ClientVenues/V1/TESTS.md"),
        ("search", "apex-search-api/tests/integration/APEX.Search.WebApi.ITests/Framework/TESTS.md"),
        ("resources", "apex-resources-api/tests/integration/APEX.Resources.Api.Grpc.ITests/Resources/TESTS.md"),
        ("marketing", "apex-marketing-api/tests/integration/APEX.Marketing.WebApi.ITests/Events/TESTS.md"),
        ("events", "apex-events-api/tests/integration/APEX.Events.WebApi/Events/TESTS.md"),
        ("admin", "apex-admin-api/tests/integration/APEX.Admin.WebApi/Clients/TESTS.md"),
        ("admin", "apex-admin-api/tests/integration/APEX.Admin.WebApi/ClientVenues/TESTS.md"),
        ("admin", "apex-admin-api/tests/integration/APEX.Admin.WebApi/Organizations/TESTS.md"),
        ("inventory", "apex-inventory-api/tests/integration/APEX.Inventory.WebApi/MapSelection/TESTS.md"),
        ("inventory", "apex-inventory-api/tests/integration/APEX.Inventory.WebApi/Smoke/TESTS.md"),
    ]
    for service, rel in api_tests:
        entries.extend(_parse_api_tests_md(_APEX_ROOT / rel, service))

    entries.extend(
        _parse_testrail_markdown(
            _APEX_ROOT / "apex-search-api/tests/integration/testrail/test-cases/QAA-9537-test-cases.md",
            "search",
        ),
    )

    # de-dupe by testrail_id + title
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for e in entries:
        key = f"{e.get('testrail_id')}|{e.get('title')}|{e.get('source')}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)

    by_mfe: dict[str, int] = {}
    by_intent: dict[str, int] = {}
    for e in unique:
        by_mfe[e.get("mfe") or "unknown"] = by_mfe.get(e.get("mfe") or "unknown", 0) + 1
        intent = e.get("assistant_intent") or "unmapped"
        by_intent[intent] = by_intent.get(intent, 0) + 1

    return {
        "generated_from": str(_APEX_ROOT),
        "entry_count": len(unique),
        "by_mfe": by_mfe,
        "by_intent": by_intent,
        "entries": unique,
    }


def main() -> None:
    catalog = build()
    _OUT.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Wrote {catalog['entry_count']} entries to {_OUT}")
    print("by_intent:", catalog["by_intent"])


if __name__ == "__main__":
    main()
