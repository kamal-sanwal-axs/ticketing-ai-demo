from __future__ import annotations

import json
from typing import Any

from apex_rag_demo.config import CHROMA_HOST, CHROMA_PORT


def _silence_chroma_telemetry() -> None:
    """Chroma 0.6.x calls posthog.capture with a legacy signature; noop before import."""
    try:
        import posthog

        posthog.disabled = True
        posthog.capture = lambda *args, **kwargs: None  # type: ignore[method-assign, assignment]
    except ImportError:
        pass


_silence_chroma_telemetry()

import chromadb  # noqa: E402
from chromadb import Collection  # noqa: E402
from chromadb.config import Settings  # noqa: E402


def _truncate_chroma_payload(obj: Any, preview: int = 8) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, val in obj.items():
            if key in ("embeddings", "query_embeddings") and isinstance(val, list):
                out[key] = _truncate_chroma_payload(val, preview)
            elif key == "embedding" and isinstance(val, list) and val and isinstance(val[0], (int, float)):
                out[key] = {"dimension": len(val), "preview": val[:preview]}
            else:
                out[key] = _truncate_chroma_payload(val, preview)
        return out
    if isinstance(obj, list):
        if obj and isinstance(obj[0], (int, float)):
            return {"dimension": len(obj), "preview": obj[:preview]}
        if obj and isinstance(obj[0], list) and obj[0] and isinstance(obj[0][0], (int, float)):
            return [
                {"index": i, "dimension": len(row), "preview": row[:preview]}
                for i, row in enumerate(obj)
            ]
        return [_truncate_chroma_payload(item, preview) for item in obj]
    return obj


def log_chroma_call(
    *,
    operation: str,
    method: str,
    collection: str,
    request_body: Any,
    response_body: Any,
) -> None:
    req = json.dumps(_truncate_chroma_payload(request_body), ensure_ascii=False, default=str)
    resp = json.dumps(_truncate_chroma_payload(response_body), ensure_ascii=False, default=str)
    url = f"http://{CHROMA_HOST}:{CHROMA_PORT}"
    print("\n=== CHROMADB call ===", flush=True)
    print(f"OPERATION: {operation}", flush=True)
    print(f"METHOD: {method}", flush=True)
    print(f"URL: {url}", flush=True)
    print(f"COLLECTION: {collection}", flush=True)
    print(f"REQUEST: {req}", flush=True)
    print(f"RESPONSE: {resp}", flush=True)
    print("=== end CHROMADB ===\n", flush=True)


class _LoggedCollection:
    """Wraps a Chroma collection and logs get/save operations."""

    def __init__(self, collection: Collection, name: str) -> None:
        self._collection = collection
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def metadata(self) -> dict[str, Any] | None:
        return self._collection.metadata

    def count(self) -> int:
        n = self._collection.count()
        log_chroma_call(
            operation="count",
            method="GET",
            collection=self._name,
            request_body={},
            response_body={"count": n},
        )
        return n

    def query(self, **kwargs: Any) -> dict[str, Any]:
        result = self._collection.query(**kwargs)
        log_chroma_call(
            operation="query",
            method="GET",
            collection=self._name,
            request_body=kwargs,
            response_body=result,
        )
        return result

    def add(self, **kwargs: Any) -> None:
        self._collection.add(**kwargs)
        log_chroma_call(
            operation="add",
            method="POST",
            collection=self._name,
            request_body=kwargs,
            response_body={"ok": True},
        )

    def upsert(self, **kwargs: Any) -> None:
        self._collection.upsert(**kwargs)
        log_chroma_call(
            operation="upsert",
            method="POST",
            collection=self._name,
            request_body=kwargs,
            response_body={"ok": True},
        )


def get_http_client() -> chromadb.HttpClient:
    settings = Settings(anonymized_telemetry=False)
    return chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
        settings=settings,
    )


def get_collection(client: chromadb.HttpClient, name: str) -> _LoggedCollection:
    collection = client.get_collection(name=name)
    log_chroma_call(
        operation="get_collection",
        method="GET",
        collection=name,
        request_body={"name": name},
        response_body={"ok": True, "metadata": collection.metadata},
    )
    return _LoggedCollection(collection, name)


def create_collection(
    client: chromadb.HttpClient,
    name: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> _LoggedCollection:
    from apex_rag_demo.rag.chroma_metrics import chroma_collection_metadata

    merged = chroma_collection_metadata(metadata)
    collection = client.create_collection(name=name, metadata=merged)
    log_chroma_call(
        operation="create_collection",
        method="POST",
        collection=name,
        request_body={"name": name, "metadata": merged or {}},
        response_body={"ok": True, "metadata": collection.metadata},
    )
    return _LoggedCollection(collection, name)


def delete_collection(client: chromadb.HttpClient, name: str) -> None:
    client.delete_collection(name)
    log_chroma_call(
        operation="delete_collection",
        method="DELETE",
        collection=name,
        request_body={"name": name},
        response_body={"ok": True},
    )
