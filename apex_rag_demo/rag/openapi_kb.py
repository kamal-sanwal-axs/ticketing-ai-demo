from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from apex_rag_demo.api_guidance import load_apex_services
from apex_rag_demo.config import DATA_DIR
from apex_rag_demo.rag.kb import KbChunk

OPENAPI_KB_PATH = DATA_DIR / "kb_openapi.json"
CACHE_DIR = DATA_DIR / "openapi_cache"


def _path_summary(path: str, methods: dict[str, Any]) -> str:
    bits: list[str] = []
    for method, detail in methods.items():
        if method.lower() in ("get", "post", "put", "patch", "delete"):
            summary = ""
            if isinstance(detail, dict):
                summary = str(detail.get("summary") or detail.get("operationId") or "")[:120]
            bits.append(f"{method.upper()} {path}" + (f" — {summary}" if summary else ""))
    return "; ".join(bits[:6])


def swagger_spec_to_chunks(service: dict[str, Any], spec: dict[str, Any]) -> list[KbChunk]:
    service_id = str(service.get("id") or "api")
    base = str(service.get("default_base_url") or "")
    swagger_url = str(service.get("swagger_url") or "")
    chunks: list[KbChunk] = []

    chunks.append(
        KbChunk(
            id=f"openapi-{service_id}-overview",
            text=(
                f"{service.get('name', service_id)} base {base}. OpenAPI: {swagger_url}. "
                f"Demo operations: {', '.join(service.get('demo_operations') or [])}."
            ),
        ),
    )

    paths = spec.get("paths") if isinstance(spec.get("paths"), dict) else {}
    ranked: list[tuple[str, str]] = []
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        summary = _path_summary(path, methods)
        if summary:
            ranked.append((path, summary))
    ranked.sort(key=lambda x: x[0])
    for path, summary in ranked[:40]:
        chunk_id = f"openapi-{service_id}-{path.strip('/').replace('/', '-')[:80]}"
        chunks.append(
            KbChunk(
                id=chunk_id,
                text=f"{service.get('name', service_id)} {summary}. Base: {base}. Spec: {swagger_url}",
            ),
        )
    return chunks


def fetch_swagger_json(url: str, timeout: float = 45.0) -> dict[str, Any]:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("swagger response is not an object")
        return data


def build_openapi_kb_chunks(fetch_live: bool = True) -> list[KbChunk]:
    chunks: list[KbChunk] = []
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for service in load_apex_services():
        swagger_url = str(service.get("swagger_url") or "").strip()
        if not swagger_url:
            continue
        cache_file = CACHE_DIR / f"{service.get('id')}.json"
        spec: dict[str, Any] | None = None
        if fetch_live:
            try:
                spec = fetch_swagger_json(swagger_url)
                cache_file.write_text(json.dumps(spec), encoding="utf-8")
            except Exception:
                if cache_file.is_file():
                    spec = json.loads(cache_file.read_text(encoding="utf-8"))
        elif cache_file.is_file():
            spec = json.loads(cache_file.read_text(encoding="utf-8"))
        if spec:
            chunks.extend(swagger_spec_to_chunks(service, spec))
    return chunks


def write_openapi_kb_file(chunks: list[KbChunk]) -> Path:
    payload = [{"id": c.id, "text": c.text} for c in chunks]
    OPENAPI_KB_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return OPENAPI_KB_PATH


def load_openapi_kb_chunks() -> list[KbChunk]:
    if not OPENAPI_KB_PATH.is_file():
        return []
    raw = json.loads(OPENAPI_KB_PATH.read_text(encoding="utf-8"))
    return [KbChunk(id=item["id"], text=item["text"]) for item in raw if item.get("text")]
