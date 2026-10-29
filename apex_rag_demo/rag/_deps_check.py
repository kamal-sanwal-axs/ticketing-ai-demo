"""Fail fast when RAG CLI is run outside the project .venv."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_VENV_PY = _ROOT / ".venv" / "bin" / "python"


def _hint() -> str:
    if _VENV_PY.is_file():
        return (
            f"Activate the project venv or call Python explicitly:\n"
            f"  source {_ROOT}/.venv/bin/activate\n"
            f"  pip install -r requirements.txt\n"
            f"Or: {_VENV_PY} -m apex_rag_demo.rag.sync_index\n"
            f"(Do not use ~/.venv-llama-cpp — that env is only for llama_cpp.server.)"
        )
    return (
        f"Create the project venv under {_ROOT}:\n"
        f"  cd {_ROOT} && python3 -m venv .venv && source .venv/bin/activate\n"
        f"  pip install -r requirements.txt"
    )


def require_rag_cli_deps(*, chroma: bool = False) -> None:
    try:
        import httpx  # noqa: F401
    except ImportError:
        print(f"ModuleNotFoundError: httpx — {_hint()}", file=sys.stderr)
        raise SystemExit(1) from None
    if chroma:
        try:
            import chromadb  # noqa: F401
        except ImportError:
            print(f"ModuleNotFoundError: chromadb — {_hint()}", file=sys.stderr)
            raise SystemExit(1) from None
