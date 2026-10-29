#!/usr/bin/env python3
"""Run chat prompts derived from TestRail catalog (automatable rows only)."""

from __future__ import annotations

import json
import os
import sys
import urllib.request

from apex_rag_demo.testrail_catalog import catalog_entries, load_harness_prompts

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
    sid = os.getenv("APEX_TEST_SESSION", "e2e-testrail")
    seen: set[str] = set()
    ok = fail = 0
    harness_rows = [
        {"example_prompt": r["prompt"], "assistant_intent": r["expected_intent"], "testrail_id": r.get("id")}
        for r in load_harness_prompts()
        if r.get("prompt") and r.get("expected_intent") and not r.get("anti_hallucination")
    ]
    rows = harness_rows + catalog_entries()
    for row in rows:
        if not row.get("chat_automatable"):
            continue
        prompt = row.get("example_prompt")
        intent = row.get("assistant_intent")
        if not prompt or not intent or prompt in seen:
            continue
        seen.add(prompt)
        if len(seen) > int(os.getenv("TESTRAIL_E2E_LIMIT", "25")):
            break
        print("=" * 60)
        print(row.get("testrail_id"), intent, prompt[:70])
        try:
            data = chat(prompt, sid, token)
            got = data.get("intent")
            print("got intent:", got, "memory:", data.get("memory_source"), "err:", data.get("error"))
            if got == intent:
                ok += 1
            else:
                fail += 1
                print("EXPECTED", intent)
        except Exception as exc:
            fail += 1
            print("FAIL", exc)
    print(f"\nSummary: ok={ok} fail={fail} prompts={len(seen)}")


if __name__ == "__main__":
    main()
