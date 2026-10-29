#!/usr/bin/env python3
"""Extended E2E chat run — reports intent, memory_source, citations, display."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.getenv("APEX_CHAT_BASE", "http://localhost:8080/api/chat")


def chat(message: str, session_id: str, token: str, confirm: bool = False) -> dict:
    body: dict = {"message": message, "region": "US-West", "session_id": session_id}
    if confirm:
        body["confirm_mutation"] = True
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE,
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode())


def summarize(label: str, data: dict) -> None:
    print(f"\n{'=' * 70}\n[{label}]")
    print("intent:", data.get("intent"))
    print("memory_source:", data.get("memory_source"))
    print("requires_confirmation:", data.get("requires_confirmation"))
    print("error:", data.get("error"), data.get("error_message") or "")
    ans = (data.get("answer") or "").strip()
    print("answer (first 800 chars):\n", ans[:800])
    disp = data.get("display") or {}
    print(
        "display:",
        disp.get("type"),
        "|",
        disp.get("title"),
        "| count=",
        disp.get("count"),
    )
    cites = disp.get("citations") or []
    if cites:
        print("citations:", len(cites), "—", cites[:3])
    rows = disp.get("rows") or []
    if rows and len(rows) <= 5:
        print("rows sample:", rows[:3])
    elif rows:
        print("rows:", len(rows), "first:", rows[0])


def main() -> None:
    token = os.environ.get("APEX_TEST_TOKEN", "").strip()
    if not token:
        print("Set APEX_TEST_TOKEN", file=sys.stderr)
        sys.exit(1)

    smoke_sid = os.getenv("APEX_TEST_SESSION", "e2e-ai-smoke-v2")
    smoke = [
        "hello",
        "show me customers for kamal@example.com",
        "search orders for customer kamal@example.com",
        "show upcoming events",
        "show all events",
        "search events matching lakers",
        "list all client venues",
    ]
    for q in smoke:
        try:
            summarize(q, chat(q, smoke_sid, token))
        except Exception as exc:
            print(f"\nFAIL {q}: {exc}")

    flow_sid = "e2e-create-publish-" + os.getenv("USER", "run")[:8]
    flow = [
        "create a new event called E2E Agent Test Concert on 2026-08-15 at Madison Square Garden",
        "publish that event to on sale",
    ]
    for q in flow:
        try:
            summarize(q, chat(q, flow_sid, token))
        except Exception as exc:
            print(f"\nFAIL {q}: {exc}")

    # Follow-up publish with confirm if needed
    try:
        last = chat("yes confirm publish", flow_sid, token, confirm=True)
        summarize("confirm publish", last)
    except Exception as exc:
        print(f"\nconfirm skip: {exc}")


if __name__ == "__main__":
    main()
