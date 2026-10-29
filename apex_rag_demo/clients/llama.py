from __future__ import annotations

import json
from typing import Any

import httpx
from openai import OpenAI

from apex_rag_demo.api_call_log import log_api_call
from apex_rag_demo.pipeline_errors import explain_exception, log_pipeline_failure
from apex_rag_demo.config import (
    CHAT_BASE_URL,
    CHAT_HISTORY_MAX_MESSAGES,
    CHAT_HISTORY_MAX_MESSAGES_ROUTING,
    CHAT_LOGPROBS,
    CHAT_MODEL,
    CHAT_STREAM,
    CHAT_TEMPERATURE,
    CHAT_TOP_K,
    CHAT_TOP_P,
    EMBED_BASE_URL,
    EMBED_MODEL,
)

_CHAT_TIMEOUT = httpx.Timeout(120.0, connect=30.0)


def embed_client() -> OpenAI:
    return OpenAI(base_url=EMBED_BASE_URL, api_key="local")


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = embed_client()
    request_body = {"model": EMBED_MODEL, "input": texts}
    url = f"{EMBED_BASE_URL.rstrip('/')}/embeddings"
    try:
        response = client.embeddings.create(model=EMBED_MODEL, input=texts)
        response_body = response.model_dump() if hasattr(response, "model_dump") else response
        log_api_call(
            call_type="EMBEDDING",
            method="POST",
            url=url,
            request_body=request_body,
            response_body=response_body,
            failed=False,
        )
        return [item.embedding for item in response.data]
    except Exception as exc:
        failure = explain_exception(exc, phase="embeddings")
        log_pipeline_failure(failure, exc=exc)
        log_api_call(
            call_type="EMBEDDING",
            method="POST",
            url=url,
            request_body=request_body,
            response_body={"error": failure.to_dict()},
            failed=True,
        )
        raise


def _build_chat_payload(
    messages: list[dict[str, str]],
    *,
    temperature: float,
    top_p: float | None = None,
    top_k: int | None = None,
    stream: bool | None = None,
    logprobs: int | None = None,
) -> dict[str, Any]:
    """JSON body for llama.cpp POST /v1/chat/completions (flat fields, not OpenAI SDK)."""
    top_p_val = top_p if top_p is not None else CHAT_TOP_P
    top_k_val = top_k if top_k is not None else CHAT_TOP_K
    stream_val = stream if stream is not None else CHAT_STREAM
    logprobs_val = logprobs if logprobs is not None else CHAT_LOGPROBS

    payload: dict[str, Any] = {
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p_val,
        "top_k": top_k_val,
        "stream": stream_val,
    }
    if CHAT_MODEL:
        payload["model"] = CHAT_MODEL
    if logprobs_val is not None and logprobs_val > 0:
        payload["logprobs"] = True
        payload["top_logprobs"] = int(logprobs_val)

    return payload


def _parse_stream_line(line: str) -> dict[str, Any] | None:
    if not line.startswith("data:"):
        return None
    data = line[5:].strip()
    if not data or data == "[DONE]":
        return None
    return json.loads(data)


def _chat_http(payload: dict[str, Any], url: str) -> tuple[str, dict[str, Any]]:
    headers = {"Content-Type": "application/json", "Authorization": "Bearer local"}
    with httpx.Client(timeout=_CHAT_TIMEOUT) as http:
        if payload.get("stream"):
            content_parts: list[str] = []
            logprob_chunks: list[Any] = []
            last_chunk: dict[str, Any] | None = None
            with http.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    chunk = _parse_stream_line(line)
                    if not chunk:
                        continue
                    last_chunk = chunk
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    delta = choice.get("delta") or {}
                    piece = delta.get("content")
                    if piece:
                        content_parts.append(piece)
                    if choice.get("logprobs") is not None:
                        logprob_chunks.append(choice["logprobs"])
            text = "".join(content_parts).strip()
            response_body: dict[str, Any] = {
                "stream": True,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": text},
                        "logprobs": logprob_chunks[-1] if logprob_chunks else None,
                    },
                ],
            }
            if last_chunk:
                response_body["last_chunk"] = last_chunk
            return text, response_body

        resp = http.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        body = resp.json()
        choices = body.get("choices") or []
        text = ""
        if choices:
            msg = choices[0].get("message") or {}
            text = str(msg.get("content") or "").strip()
        return text, body


def chat_completion(
    system: str,
    user: str,
    temperature: float | None = None,
    *,
    top_p: float | None = None,
    top_k: int | None = None,
    stream: bool | None = None,
    logprobs: int | None = None,
    chroma_system_context: str | None = None,
    semantic_turn_context: str | None = None,
    history: list[dict[str, Any]] | None = None,
    routing: bool = False,
) -> str:
    from apex_rag_demo.prompt_budget import (
        fit_messages_to_context,
        routing_budget_kwargs,
        synthesis_budget_kwargs,
        trim_chroma_appendix,
    )
    from apex_rag_demo.rag.agent_chroma import merge_system_role
    from apex_rag_demo.rag.chat_history import normalize_chat_history

    budget = routing_budget_kwargs() if routing else synthesis_budget_kwargs()
    chroma_trimmed = trim_chroma_appendix(chroma_system_context, budget["chroma_max_chars"])
    system_body = system
    if semantic_turn_context and semantic_turn_context.strip():
        system_body = f"{semantic_turn_context.strip()}\n\n{system.rstrip()}"
    system_content = merge_system_role(system_body, chroma_trimmed)
    temp = temperature if temperature is not None else CHAT_TEMPERATURE
    history_cap = CHAT_HISTORY_MAX_MESSAGES_ROUTING if routing else CHAT_HISTORY_MAX_MESSAGES
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_content}]
    prior = normalize_chat_history(
        history,
        max_messages=history_cap,
        max_chars_per_message=budget["max_chars_per_message"],
    )
    if prior:
        messages.extend(prior)
    messages.append({"role": "user", "content": user})
    messages, _ = fit_messages_to_context(
        messages,
        max_tokens=budget["max_tokens"],
        max_chars_per_message=budget["max_chars_per_message"],
        routing=routing,
    )
    request_body = _build_chat_payload(
        messages,
        temperature=temp,
        top_p=top_p,
        top_k=top_k,
        stream=stream,
        logprobs=logprobs,
    )
    if chroma_system_context:
        request_body["_chroma_system_enriched"] = True
    url = f"{CHAT_BASE_URL.rstrip('/')}/chat/completions"

    try:
        text, response_body = _chat_http(request_body, url)
    except Exception as exc:
        failure = explain_exception(exc, phase="llm_chat")
        log_pipeline_failure(failure, exc=exc)
        log_api_call(
            call_type="LLM",
            method="POST",
            url=url,
            request_body=request_body,
            response_body={"error": failure.to_dict(), "exception": str(exc)},
            failed=True,
        )
        raise

    log_api_call(
        call_type="LLM",
        method="POST",
        url=url,
        request_body=request_body,
        response_body=response_body,
        failed=False,
    )
    return text
