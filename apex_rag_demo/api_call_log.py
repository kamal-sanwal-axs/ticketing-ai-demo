from __future__ import annotations

import json
from typing import Any


def _truncate_embedding_values(obj: Any, preview: int = 8) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, val in obj.items():
            if key == "embedding" and isinstance(val, list) and val and isinstance(val[0], (int, float)):
                out[key] = {
                    "dimension": len(val),
                    "preview": val[:preview],
                }
            else:
                out[key] = _truncate_embedding_values(val, preview)
        return out
    if isinstance(obj, list):
        return [_truncate_embedding_values(item, preview) for item in obj]
    return obj


def _pretty_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str, indent=2)


def _print_llm_message_contents(messages: Any, *, header: str) -> None:
    if not isinstance(messages, list):
        return
    print(header, flush=True)
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "?")
        content = msg.get("content")
        if content is None:
            continue
        label = role
        if role == "tool" and msg.get("name"):
            label = f"tool ({msg.get('name')})"
        print(f"--- {label} ---", flush=True)
        print(str(content), flush=True)
        print("", flush=True)


def _print_llm_assistant_text(response_body: Any) -> None:
    if not isinstance(response_body, dict):
        return
    choices = response_body.get("choices")
    if not isinstance(choices, list):
        return
    printed = False
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") or {}
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if content is None or content == "":
            continue
        if not printed:
            print("ASSISTANT TEXT:", flush=True)
            printed = True
        print(str(content), flush=True)
        print("", flush=True)


def _response_failed(response_body: Any) -> bool:
    if isinstance(response_body, dict):
        if response_body.get("error"):
            return True
        if "type" in response_body and str(response_body.get("type", "")).endswith("Error"):
            return True
    return False


def log_api_call(
    *,
    call_type: str,
    method: str,
    url: str,
    request_body: Any,
    response_body: Any,
    failed: bool | None = None,
) -> None:
    """Print LLM / embedding request and response to the console."""
    if call_type == "EMBEDDING":
        response_body = _truncate_embedding_values(response_body)
    is_failed = failed if failed is not None else _response_failed(response_body)
    req = _pretty_json(request_body)
    resp = _pretty_json(response_body)
    print(f"\n=== {call_type} API call ===", flush=True)
    print(f"STATUS: {'FAILED' if is_failed else 'OK'}", flush=True)
    print(f"METHOD: {method}", flush=True)
    print(f"URL: {url}", flush=True)
    if call_type == "LLM" and isinstance(request_body, dict):
        _print_llm_message_contents(request_body.get("messages"), header="REQUEST MESSAGES:")
    print("REQUEST JSON:", flush=True)
    print(req, flush=True)
    if call_type == "LLM":
        _print_llm_assistant_text(response_body)
    print("RESPONSE JSON:", flush=True)
    print(resp, flush=True)
    if is_failed:
        print(
            f"NOTE: {call_type} request failed — check the message above and the service log "
            f"(e.g. llama.cpp POST /v1/chat/completions HTTP 500).",
            flush=True,
        )
    print(f"=== end {call_type} ===\n", flush=True)
