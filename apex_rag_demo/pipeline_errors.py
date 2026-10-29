from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class PipelineFailure:
    code: str
    title: str
    summary: str
    detail: str
    remediation: str
    http_status: int | None = None
    endpoint: str | None = None
    component: str = "pipeline"
    debug_curl: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_client_dict(self) -> dict[str, Any]:
        """Payload for UI/API — omits server-only debug fields."""
        d = self.to_dict()
        d.pop("debug_curl", None)
        if d.get("detail") and "Replay:" in str(d["detail"]):
            d["detail"] = str(d.get("summary") or "")[:500]
        return d

    def ui_display(self) -> dict[str, Any]:
        paragraphs = [self.summary]
        paragraphs.append(f"What to do: {self.remediation}")
        if self.component in ("llm_chat", "embeddings", "chroma"):
            paragraphs.append("Full replay curl is printed in the server terminal (DEBUG CURL).")
        fields = [
            {"label": "Error code", "value": self.code},
            {"label": "Component", "value": self.component},
        ]
        if self.http_status is not None:
            fields.append({"label": "HTTP status", "value": str(self.http_status)})
        if self.endpoint:
            fields.append({"label": "Endpoint", "value": self.endpoint})
        return {
            "type": "article",
            "title": self.title,
            "badge": "error",
            "level": "error",
            "paragraphs": paragraphs,
            "fields": fields,
        }


def log_pipeline_failure(failure: PipelineFailure, *, exc: BaseException | None = None) -> None:
    print("\n!!! PIPELINE FAILURE !!!", flush=True)
    print(f"CODE: {failure.code}", flush=True)
    print(f"COMPONENT: {failure.component}", flush=True)
    if failure.http_status is not None:
        print(f"HTTP: {failure.http_status}", flush=True)
    if failure.endpoint:
        print(f"ENDPOINT: {failure.endpoint}", flush=True)
    print(f"TITLE: {failure.title}", flush=True)
    print(f"SUMMARY: {failure.summary}", flush=True)
    if failure.detail:
        print(f"DETAIL: {failure.detail}", flush=True)
    if failure.debug_curl:
        print("DEBUG CURL (replay request):", flush=True)
        print(failure.debug_curl, flush=True)
    print(f"FIX: {failure.remediation}", flush=True)
    if exc is not None:
        print(f"EXCEPTION: {type(exc).__name__}: {exc}", flush=True)
    print("!!! end failure !!!\n", flush=True)


def log_api_route_failure(
    *,
    component: str,
    method: str,
    url: str,
    http_status: int | None,
    detail: str,
) -> None:
    failure = explain_http_failure(
        component=component,
        method=method,
        url=url,
        http_status=http_status,
        detail=detail,
    )
    log_pipeline_failure(failure)


def _extract_error_message(body: Any) -> str:
    if body is None:
        return ""
    if isinstance(body, str):
        return body.strip()
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            parts = [str(err.get("message") or ""), str(err.get("type") or "")]
            return " — ".join(p for p in parts if p).strip()
        return str(body.get("message") or body.get("detail") or body)
    return str(body)


def _openai_status_failure(exc: Any) -> PipelineFailure | None:
    status = getattr(exc, "status_code", None)
    if status is None:
        return None
    body = getattr(exc, "body", None)
    detail = _extract_error_message(body) or str(exc)
    message = getattr(exc, "message", "") or ""
    endpoint = ""
    if "embeddings" in message.lower():
        endpoint = "/v1/embeddings"
        component = "embeddings"
        code = f"embedding_http_{status}"
        title = f"Embedding server error (HTTP {status})"
        remediation = (
            "Confirm ./scripts/run-embed-server.sh is running on EMBED_BASE_URL "
            "(default :8081) and RAG_EMBEDDING_BACKEND matches your setup."
        )
    else:
        endpoint = "/v1/chat/completions"
        component = "llm_chat"
        code = f"llm_http_{status}"
        title = f"Chat server error (HTTP {status})"
        remediation = (
            "Confirm llama.cpp is running on CHAT_BASE_URL (default :8000). "
            "Check its console for validation errors (logprobs must be boolean on llama.cpp; "
            "use CHAT_LOGPROBS=5 in .env for top_logprobs). See the LLM API log block above."
        )
    summary = detail[:500] if detail else f"Request failed with HTTP {status}."
    return PipelineFailure(
        code=code,
        title=title,
        summary=summary,
        detail=detail[:2000] if detail else summary,
        remediation=remediation,
        http_status=int(status),
        endpoint=endpoint,
        component=component,
    )


def _redact_header(name: str, value: str) -> str:
    if name.lower() == "authorization":
        if not value:
            return value
        if value.lower().startswith("bearer "):
            return "Bearer ***"
        return "***"
    return value


def format_debug_curl(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    body_max_chars: int = 1200,
) -> str:
    """Shell-friendly curl for reproducing failed HTTP calls (secrets redacted)."""
    replay_headers: dict[str, str] = {}
    if headers:
        auth = headers.get("Authorization") or headers.get("authorization")
        if auth:
            replay_headers["Authorization"] = auth
        ct = headers.get("Content-Type") or headers.get("content-type")
        if ct:
            replay_headers["Content-Type"] = ct
    if "Content-Type" not in replay_headers and json_body is not None:
        replay_headers["Content-Type"] = "application/json"
    if "Authorization" not in replay_headers and "authorization" not in replay_headers:
        replay_headers["Authorization"] = "Bearer local"

    lines = [f"curl -sS -X {method.upper()} '{url}'"]
    for key, val in replay_headers.items():
        lines.append(f"  -H '{key}: {_redact_header(key, val)}'")
    if json_body is not None:
        body = json.dumps(json_body, ensure_ascii=False, default=str)
        if len(body) > body_max_chars:
            body = body[: body_max_chars - 20] + "…(truncated)"
        escaped = body.replace("'", "'\"'\"'")
        lines.append(f"  -d '{escaped}'")
    return " \\\n".join(lines)


def _component_and_remediation_for_url(url: str, *, phase: str) -> tuple[str, str]:
    if "/v1/chat/completions" in url:
        return (
            "llm_chat",
            "Start llama.cpp on port 8000 (CHAT_BASE_URL). Test: curl -s http://localhost:8000/v1/models",
        )
    if "/v1/embeddings" in url or "/embeddings" in url:
        return (
            "embeddings",
            "Start ./scripts/run-embed-server.sh on :8081 or set RAG_EMBEDDING_BACKEND=sentence-transformers in .env",
        )
    if ":8002" in url or "chroma" in url.lower():
        return (
            "chroma",
            "Run docker compose up -d chroma and check CHROMA_HOST/CHROMA_PORT (default localhost:8002).",
        )
    if "apex-dev" in url or "apex" in url.lower():
        return (
            "apex_api",
            "Check VPN, APEX_*_BASE_URL in .env, and APEX_BEARER_TOKEN.",
        )
    return (
        phase if phase not in ("pipeline", "langgraph") else "http",
        "Check VPN, base URLs in .env, and that the target service is running.",
    )


def _request_from_exception_chain(exc: BaseException) -> httpx.Request | None:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, httpx.HTTPStatusError):
            return current.request
        if isinstance(current, httpx.RequestError) and current.request is not None:
            return current.request
        current = current.__cause__ or current.__context__
    return None


def _default_debug_curl_for_phase(phase: str) -> tuple[str, str] | None:
    from apex_rag_demo.config import CHAT_BASE_URL, CHROMA_HOST, CHROMA_PORT, EMBED_BASE_URL

    if phase in ("llm_chat", "classify"):
        url = f"{CHAT_BASE_URL.rstrip('/')}/chat/completions"
        return url, format_debug_curl(
            "POST",
            url,
            headers={"Authorization": "Bearer local", "Content-Type": "application/json"},
            json_body={"model": "(see CHAT_MODEL)", "messages": [{"role": "user", "content": "ping"}]},
        )
    if phase == "embeddings":
        url = f"{EMBED_BASE_URL.rstrip('/')}/embeddings"
        return url, format_debug_curl(
            "POST",
            url,
            headers={"Authorization": "Bearer local", "Content-Type": "application/json"},
            json_body={"model": "(see EMBED_MODEL)", "input": ["test"]},
        )
    if phase == "chroma":
        url = f"http://{CHROMA_HOST}:{CHROMA_PORT}/api/v2/heartbeat"
        return url, format_debug_curl("GET", url)
    return None


def explain_network_failure(
    exc: BaseException,
    *,
    phase: str = "pipeline",
) -> PipelineFailure:
    req = _request_from_exception_chain(exc)
    debug_curl: str | None = None
    endpoint: str | None = None
    method = "GET"
    component = phase
    remediation = "Check VPN, base URLs in .env, and that the target service is running."

    if req is not None:
        endpoint = str(req.url)
        method = req.method
        header_map = {k: v for k, v in req.headers.items()}
        body: Any = None
        if req.content:
            try:
                body = json.loads(req.content.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                body = {"_raw": req.content[:500].decode("utf-8", errors="replace")}
        debug_curl = format_debug_curl(method, endpoint, headers=header_map, json_body=body)
        component, remediation = _component_and_remediation_for_url(endpoint, phase=phase)
    else:
        fallback = _default_debug_curl_for_phase(phase)
        if fallback:
            endpoint, debug_curl = fallback
            component, remediation = _component_and_remediation_for_url(endpoint, phase=phase)

    summary = str(exc)[:500]
    if endpoint:
        summary = f"{method} {endpoint} — {summary}"
    return PipelineFailure(
        code="network_unreachable",
        title="Network request failed",
        summary=summary,
        detail=str(exc)[:500],
        remediation=remediation + " Replay curl is logged on the server (DEBUG CURL).",
        endpoint=endpoint,
        component=component,
        debug_curl=debug_curl,
    )


def explain_exception(exc: BaseException, *, phase: str = "pipeline") -> PipelineFailure:
    try:
        from openai import APIStatusError
    except ImportError:
        APIStatusError = type(None)  # type: ignore[misc, assignment]

    if isinstance(exc, APIStatusError):
        openai_err = _openai_status_failure(exc)
        if openai_err is not None:
            return openai_err

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        detail = exc.response.text[:2000]
        url = str(exc.request.url)
        component = "apex_api" if "apex" in url else "http"
        return explain_http_failure(
            component=component,
            method=exc.request.method,
            url=url,
            http_status=status,
            detail=detail,
            phase=phase,
        )

    if isinstance(exc, httpx.RequestError):
        return explain_network_failure(exc, phase=phase)

    try:
        from openai import APIConnectionError
    except ImportError:
        APIConnectionError = type(None)  # type: ignore[misc, assignment]

    if isinstance(exc, APIConnectionError):
        return explain_network_failure(exc, phase=phase)

    if type(exc).__name__ in ("APIConnectionError", "ConnectError") and not isinstance(
        exc,
        httpx.RequestError,
    ):
        return explain_network_failure(exc, phase=phase)

    return PipelineFailure(
        code="unhandled_exception",
        title="Request failed",
        summary=str(exc)[:500] or type(exc).__name__,
        detail=str(exc)[:2000],
        remediation="See the server console for the full traceback and API log blocks.",
        component=phase,
    )


def explain_http_failure(
    *,
    component: str,
    method: str,
    url: str,
    http_status: int | None,
    detail: str,
    phase: str = "pipeline",
) -> PipelineFailure:
    status = http_status or 0
    short_url = url
    if "/v1/chat/completions" in url:
        component = "llm_chat"
        code = f"llm_http_{status}"
        title = f"Chat server error (HTTP {status})"
        remediation = (
            "Start llama.cpp on port 8000 and fix any validation errors shown in its log "
            "(e.g. POST /v1/chat/completions 500)."
        )
    elif "/v1/embeddings" in url:
        component = "embeddings"
        code = f"embedding_http_{status}"
        title = f"Embedding server error (HTTP {status})"
        remediation = "Start ./scripts/run-embed-server.sh and verify EMBED_BASE_URL."
    elif "chroma" in url.lower() or ":8002" in url:
        component = "chroma"
        code = f"chroma_http_{status}"
        title = f"ChromaDB error (HTTP {status})"
        remediation = "Run docker compose up -d chroma and check CHROMA_HOST/CHROMA_PORT."
    elif "/search/v1/orders" in url:
        component = "apex_search_orders"
        code = f"search_orders_http_{status}"
        title = f"Search API orders error (HTTP {status})"
        remediation = (
            "apex-dev search-api returned an error for POST /v1/orders. "
            "Use a specific email or order number (`search orders for fan@example.com`). "
            "Confirm `b2b_search_orders` on your JWT. If the body is valid, the failure is "
            "likely upstream — retry in apex-dev or check search-api logs."
        )
    else:
        code = f"{component}_http_{status}"
        title = f"{component} error (HTTP {status})"
        remediation = "Check the service URL in .env and the upstream API response."

    summary = (detail or f"{method} {short_url} failed").strip()[:500]
    return PipelineFailure(
        code=code,
        title=title,
        summary=summary,
        detail=(detail or summary)[:2000],
        remediation=remediation,
        http_status=status or None,
        endpoint=short_url,
        component=component,
    )


def pipeline_error_display(data: dict[str, Any]) -> dict[str, Any]:
    fields = PipelineFailure.__dataclass_fields__
    kwargs = {k: data[k] for k in fields if k in data and k != "debug_curl"}
    return PipelineFailure(**kwargs).ui_display()


def failure_state_patch(
    exc: BaseException,
    *,
    phase: str,
    question: str,
) -> dict[str, Any]:
    failure = explain_exception(exc, phase=phase)
    log_pipeline_failure(failure, exc=exc)
    short = failure.summary
    if len(short) > 280:
        short = short[:277] + "…"
    answer = short
    return {
        "question": question,
        "intent": "explain",
        "memory_source": "error",
        "answer": answer,
        "pipeline_error": failure.to_client_dict(),
        "api_error": failure.summary,
        "api_payload": None,
    }


def format_apex_api_error(intent: str, api_error: str, http_status: int | None = None) -> PipelineFailure:
    return PipelineFailure(
        code=f"apex_{intent}_error",
        title=f"APEX API error ({intent.replace('_', ' ')})",
        summary=api_error[:500],
        detail=api_error[:2000],
        remediation=(
            "Verify your JWT, region, and permissions for apex-dev. "
            "See docs/API_LINKS.md for the swagger contract."
        ),
        http_status=http_status,
        component="apex_api",
    )
