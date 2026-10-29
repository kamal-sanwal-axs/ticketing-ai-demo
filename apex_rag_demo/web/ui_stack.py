"""Last LLM prompt size + static stack info for the UI context bar."""

from __future__ import annotations

from typing import Any

from apex_rag_demo.config import (
    APEX_SEARCH_BASE_URL,
    CHAT_CONTEXT_MAX_TOKENS,
    CHAT_CONTEXT_MAX_TOKENS_ROUTING,
    CHAT_MODEL,
    DATA_DIR,
    EMBEDDING_BACKEND,
    KG_NEO4J_ENABLED,
    RAG_RERANK_MODEL,
    RAG_VECTOR_STORE,
    SENTENCE_TRANSFORMERS_MODEL,
)

_last_llm_context: dict[str, Any] | None = None


def record_llm_context_usage(
    *,
    estimated_tokens: int,
    budget_tokens: int,
    routing: bool,
    prompt_trimmed: bool = False,
) -> None:
    global _last_llm_context
    budget = max(budget_tokens, 1)
    used_pct = min(100, int(round(100 * estimated_tokens / budget)))
    _last_llm_context = {
        "estimated_tokens": estimated_tokens,
        "budget_tokens": budget_tokens,
        "percent_used": used_pct,
        "percent_left": max(0, 100 - used_pct),
        "routing": routing,
        "prompt_trimmed": prompt_trimmed,
        "model": CHAT_MODEL or "llama.cpp",
    }


def get_last_llm_context() -> dict[str, Any] | None:
    return dict(_last_llm_context) if _last_llm_context else None


def _kb_chunk_count() -> int:
    path = DATA_DIR / "kb.json"
    if not path.is_file():
        return 0
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict) and isinstance(data.get("chunks"), list):
            return len(data["chunks"])
    except (OSError, ValueError):
        pass
    return 0


def _environment_label() -> str:
    url = (APEX_SEARCH_BASE_URL or "").lower()
    if "apex-dev" in url:
        return "apex-dev"
    if "localhost" in url:
        return "local APIs"
    return "custom gateway"


def _display_model_name(model_id: str) -> str:
    if not model_id:
        return "llama.cpp"
    base = model_id.rsplit("/", 1)[-1]
    base = base.replace(".gguf", "").replace("-", " ")
    if "qwen2.5" in base.lower() and "3b" in base.lower():
        return "Qwen2.5-3B"
    if "qwen2.5" in base.lower() and "1.5b" in base.lower():
        return "Qwen2.5-1.5B"
    if len(base) > 28:
        return base[:25] + "…"
    return base


def build_ui_stack_status(*, region: str | None = None) -> dict[str, Any]:
    from apex_rag_demo.dynamic_tools import dynamic_tools_enabled, dynamic_tools_status

    tools_meta = dynamic_tools_status() if dynamic_tools_enabled() else {}
    tool_count = int(tools_meta.get("tool_count") or 0)
    kb_chunks = _kb_chunk_count()
    openapi_files = len(list((DATA_DIR / "openapi_cache").glob("*.json"))) if (DATA_DIR / "openapi_cache").is_dir() else 0
    sources_count = tool_count + kb_chunks + openapi_files

    last = get_last_llm_context()
    ctx_left = last.get("percent_left") if last else None

    return {
        "environment": _environment_label(),
        "region": region or "",
        "chat_model": CHAT_MODEL or "",
        "chat_model_label": _display_model_name(CHAT_MODEL),
        "embed_model": SENTENCE_TRANSFORMERS_MODEL,
        "embed_backend": EMBEDDING_BACKEND,
        "rerank_model": RAG_RERANK_MODEL,
        "vector_store": RAG_VECTOR_STORE,
        "kg_enabled": KG_NEO4J_ENABLED,
        "context_budget_tokens": CHAT_CONTEXT_MAX_TOKENS,
        "context_routing_budget_tokens": CHAT_CONTEXT_MAX_TOKENS_ROUTING,
        "last_llm_context": last,
        "context_percent_left": ctx_left,
        "tool_count": tool_count,
        "kb_chunks": kb_chunks,
        "openapi_sources": openapi_files,
        "sources_count": sources_count,
        "bar_label": _format_bar_label(
            model_label=_display_model_name(CHAT_MODEL),
            context_percent_left=ctx_left,
            sources_count=sources_count,
            region=region,
            environment=_environment_label(),
        ),
    }


def _format_bar_label(
    *,
    model_label: str,
    context_percent_left: int | None,
    sources_count: int,
    region: str | None,
    environment: str,
) -> str:
    parts = [model_label]
    if context_percent_left is not None:
        parts.append(f"{context_percent_left}% ctx left")
    else:
        parts.append("ctx —")
    parts.append(f"{sources_count} sources")
    if region:
        parts.append(region)
    else:
        parts.append(environment)
    return " · ".join(parts)
