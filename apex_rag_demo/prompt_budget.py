from __future__ import annotations

from typing import Any

from apex_rag_demo.config import (
    CHAT_CHROMA_MAX_CHARS,
    CHAT_CHROMA_MAX_CHARS_ROUTING,
    CHAT_CONTEXT_MAX_TOKENS,
    CHAT_CONTEXT_MAX_TOKENS_ROUTING,
    CHAT_MESSAGE_MAX_CHARS,
    CHAT_MESSAGE_MAX_CHARS_ROUTING,
)


def estimate_message_tokens(messages: list[dict[str, Any]]) -> int:
    """Rough token count for llama.cpp budgeting (chars / 4 + per-message overhead)."""
    total = 0
    for msg in messages:
        content = str(msg.get("content") or "")
        total += 4 + max(1, len(content) // 4)
    return total


def truncate_text(text: str, max_chars: int, *, note: str = "truncated") -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    suffix = f"\n…({note})"
    keep = max(0, max_chars - len(suffix))
    return text[:keep].rstrip() + suffix


def trim_chroma_appendix(appendix: str | None, max_chars: int) -> str | None:
    if not appendix:
        return appendix
    text = appendix.strip()
    if not text:
        return None
    return truncate_text(text, max_chars, note="Chroma context trimmed for context window")


def _truncate_message_contents(
    messages: list[dict[str, Any]],
    max_chars: int,
) -> None:
    for msg in messages:
        content = str(msg.get("content") or "")
        if len(content) > max_chars:
            msg["content"] = truncate_text(content, max_chars, note="message trimmed")


def fit_messages_to_context(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int,
    max_chars_per_message: int,
    routing: bool = False,
) -> tuple[list[dict[str, Any]], bool]:
    """
    Ensure prompt fits llama n_ctx. Keeps system (index 0) and latest user (last).
    Drops oldest history turns first, then truncates system, then shrinks all contents.
    """
    if len(messages) < 2:
        return messages, False

    out = [dict(m) for m in messages]
    trimmed = False

    _truncate_message_contents(out, max_chars_per_message)

    while estimate_message_tokens(out) > max_tokens and len(out) > 2:
        out.pop(1)
        trimmed = True

    while estimate_message_tokens(out) > max_tokens:
        system = str(out[0].get("content") or "")
        if len(system) <= 400:
            break
        out[0]["content"] = truncate_text(
            system,
            int(len(system) * 0.75),
            note="system prompt trimmed for context window",
        )
        trimmed = True
        if estimate_message_tokens(out) <= max_tokens:
            break

    while estimate_message_tokens(out) > max_tokens:
        shrunk = False
        for msg in out[1:-1]:
            content = str(msg.get("content") or "")
            if len(content) > 120:
                msg["content"] = truncate_text(content, int(len(content) * 0.7), note="trimmed")
                shrunk = True
        if not shrunk:
            user = str(out[-1].get("content") or "")
            if len(user) > 200:
                out[-1]["content"] = truncate_text(user, int(len(user) * 0.85), note="trimmed")
                trimmed = True
            break
        trimmed = True

    if trimmed and routing:
        print(
            f"--- LLM prompt trimmed (routing) ~{estimate_message_tokens(out)} est. tokens "
            f"<= budget {max_tokens} ---",
            flush=True,
        )
    elif trimmed:
        print(
            f"--- LLM prompt trimmed ~{estimate_message_tokens(out)} est. tokens "
            f"<= budget {max_tokens} ---",
            flush=True,
        )

    return out, trimmed


def routing_budget_kwargs() -> dict[str, int]:
    return {
        "max_tokens": CHAT_CONTEXT_MAX_TOKENS_ROUTING,
        "max_chars_per_message": CHAT_MESSAGE_MAX_CHARS_ROUTING,
        "chroma_max_chars": CHAT_CHROMA_MAX_CHARS_ROUTING,
    }


def synthesis_budget_kwargs() -> dict[str, int]:
    return {
        "max_tokens": CHAT_CONTEXT_MAX_TOKENS,
        "max_chars_per_message": CHAT_MESSAGE_MAX_CHARS,
        "chroma_max_chars": CHAT_CHROMA_MAX_CHARS,
    }
