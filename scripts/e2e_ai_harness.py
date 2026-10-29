#!/usr/bin/env python3
"""Label-check operator prompts (no server) — guard_api_intent vs harness expected_intent."""

from __future__ import annotations

import json
import os
import sys

from apex_rag_demo.config import DATA_DIR
from apex_rag_demo.intent_helpers import guard_api_intent
from apex_rag_demo.testrail_catalog import load_harness_prompts


def main() -> None:
    path = DATA_DIR / "ai_harness_prompts.json"
    rows = load_harness_prompts()
    if not rows:
        print(f"No harness rows in {path}", file=sys.stderr)
        sys.exit(1)
    ok = fail = 0
    for row in rows:
        prompt = str(row.get("prompt") or "")
        expected = str(row.get("expected_intent") or "")
        got = guard_api_intent("explain", prompt)
        label = row.get("id", prompt[:40])
        if got == expected:
            ok += 1
            print(f"OK  {label}: {got}")
        else:
            fail += 1
            print(f"FAIL {label}: expected {expected} got {got}")
    limit = int(os.getenv("HARNESS_FAIL_MAX", "0"))
    print(f"\nSummary: ok={ok} fail={fail}")
    if fail > limit:
        sys.exit(1)


if __name__ == "__main__":
    main()
