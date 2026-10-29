from __future__ import annotations

import contextvars
from collections.abc import Callable

_on_progress: contextvars.ContextVar[Callable[[str], None] | None] = contextvars.ContextVar(
    "chat_progress",
    default=None,
)


def set_progress_callback(cb: Callable[[str], None] | None) -> contextvars.Token:
    return _on_progress.set(cb)


def reset_progress_callback(token: contextvars.Token) -> None:
    _on_progress.reset(token)


def emit_progress(phase: str) -> None:
    cb = _on_progress.get()
    if cb:
        cb(phase)
