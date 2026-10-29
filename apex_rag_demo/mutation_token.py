from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any

_DEFAULT_SECRET = "apex-ai-demo-mutation-token"


def _secret() -> bytes:
    return (os.getenv("MUTATION_TOKEN_SECRET") or _DEFAULT_SECRET).encode()


def issue_mutation_token(intent: str, plan: dict[str, Any]) -> str:
    payload_obj = {"intent": intent, "plan": plan}
    raw = base64.urlsafe_b64encode(json.dumps(payload_obj, sort_keys=True).encode()).decode()
    sig = hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def verify_mutation_token(token: str) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    raw, sig = token.rsplit(".", 1)
    expected = hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(raw.encode()))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict) or "intent" not in data:
        return None
    return data
