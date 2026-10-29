#!/usr/bin/env python3
"""Smoke-test /api/chat against local web (token via APEX_TEST_TOKEN env)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.getenv("APEX_CHAT_BASE", "http://localhost:8080/api/chat")


def chat(message: str, session_id: str, token: str) -> dict:
    body = json.dumps({"message": message, "region": "US-West", "session_id": session_id}).encode()
    req = urllib.request.Request(
        BASE,
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    token = os.environ.get("APEX_TEST_TOKEN", "").strip()
    if not token:
        print("Set APEX_TEST_TOKEN", file=sys.stderr)
        sys.exit(1)
    sid = os.getenv("APEX_TEST_SESSION", "e2e-smoke")
    queries = [
        "hello",
        "show me on-sale events",
        "how many events are on sale",
        "show all events",
        "show price codes for event defa7917-1a3f-4717-8328-3278cfa7449b",
        "change event defa7917-1a3f-4717-8328-3278cfa7449b start date to 2026-07-01",
    ]
    for q in queries:
        print("=" * 60)
        print("QUERY:", q)
        try:
            data = chat(q, sid, token)
        except urllib.error.HTTPError as exc:
            print("HTTP", exc.code, exc.read().decode()[:500])
            continue
        print("intent:", data.get("intent"))
        print("memory_source:", data.get("memory_source"))
        print("answer:", (data.get("answer") or "")[:500])
        disp = data.get("display") or {}
        print(
            "display:",
            disp.get("type"),
            "|",
            disp.get("title"),
            "| count=",
            disp.get("count"),
        )
        if disp.get("subtitle"):
            print("subtitle:", str(disp.get("subtitle"))[:180])


if __name__ == "__main__":
    main()
