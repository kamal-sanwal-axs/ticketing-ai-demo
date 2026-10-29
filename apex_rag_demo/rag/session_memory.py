from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from apex_rag_demo.config import (
    CHROMA_STATE_COLLECTION,
    CHROMA_SESSION_COLLECTION,
    DATA_DIR,
    SESSION_MEMORY_ENABLED,
    SESSION_MEMORY_TOP_K,
)
from apex_rag_demo.rag.chroma_client import create_collection, get_collection, get_http_client
from apex_rag_demo.rag.embeddings import embed_texts
from apex_rag_demo.rag.intent_interpretation import memory_document_text
from apex_rag_demo.response_formatters import strip_ui_region

_GRAPH_STATE_DIR = DATA_DIR / "session_graph"


def _normalize_question(question: str) -> str:
    return strip_ui_region(question).strip().lower()


def question_fingerprint(question: str) -> str:
    return hashlib.sha256(_normalize_question(question).encode()).hexdigest()


def _scoped_id(user_id: str, session_id: str, suffix: str) -> str:
    raw = f"{user_id}:{session_id}:{suffix}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _ensure_collection(name: str, description: str):
    client = get_http_client()
    try:
        return get_collection(client, name)
    except Exception:
        return create_collection(client, name, metadata={"description": description})


def load_session_focus(user_id: str, session_id: str) -> dict[str, Any]:
    if not user_id or not session_id:
        return {}
    graph_path = _GRAPH_STATE_DIR / user_id / f"{session_id}.json"
    try:
        if graph_path.is_file():
            store = json.loads(graph_path.read_text(encoding="utf-8"))
            focus = store.get("focus")
            if isinstance(focus, dict):
                return focus
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _update_session_focus(
    store: dict[str, Any],
    intent: str,
    plan: dict[str, Any],
    state: dict[str, Any],
) -> None:
    focus = store.get("focus")
    if not isinstance(focus, dict):
        focus = {}
    store["focus"] = focus

    eid = str((plan or {}).get("eventId") or "").strip()
    if intent in ("get_event", "inventory_zones", "update_event", "delete_event", "publish_event") and eid:
        focus["eventId"] = eid
        focus["lastIntent"] = intent

    payload = state.get("api_payload")
    if isinstance(payload, dict) and intent == "get_event":
        resolution = payload.get("_resolution")
        if resolution in (None, "events_get", "events_get_via_search"):
            from apex_rag_demo.event_list import unwrap_event_payload

            ev = unwrap_event_payload(payload)
            if ev:
                resolved = str(ev.get("id") or ev.get("eventId") or eid or "").strip()
                if resolved:
                    focus["eventId"] = resolved
                cv = str(ev.get("clientVenueId") or ev.get("ClientVenueId") or "").strip()
                if cv:
                    focus["clientVenueId"] = cv
                name = str(ev.get("headliners") or ev.get("name") or "").strip()
                if name:
                    focus["eventLabel"] = name[:200]

    if intent == "list_client_venues" and isinstance(payload, dict):
        from apex_rag_demo.event_list import iter_event_dicts

        focus["lastIntent"] = "list_client_venues"
        cached_cv = _client_venues_payload_for_storage(payload)
        if cached_cv:
            focus["hasClientVenueList"] = True
            store["last_client_venues_payload"] = cached_cv

    if intent == "marketing_events" and isinstance(payload, dict):
        from apex_rag_demo.event_list import iter_event_dicts

        focus["lastIntent"] = "marketing_events"
        events = iter_event_dicts(payload)
        if events:
            focus["hasMarketingList"] = True
            cached = _marketing_payload_for_storage(payload)
            if cached:
                store["last_marketing_payload"] = cached


def load_last_marketing_payload(user_id: str, session_id: str) -> dict[str, Any] | None:
    if not user_id or not session_id:
        return None
    path = _GRAPH_STATE_DIR / user_id / f"{session_id}.json"
    try:
        if not path.is_file():
            return None
        store = json.loads(path.read_text(encoding="utf-8"))
        block = store.get("last_marketing_payload")
        if isinstance(block, dict):
            from apex_rag_demo.event_list import iter_event_dicts

            if iter_event_dicts(block):
                return block
    except (json.JSONDecodeError, OSError):
        return None
    return None


def _marketing_payload_for_storage(payload: dict[str, Any]) -> dict[str, Any]:
    from apex_rag_demo.event_list import iter_event_dicts

    if not iter_event_dicts(payload):
        return {}
    out: dict[str, Any] = {}
    for key in ("events", "Events", "items"):
        if key in payload and isinstance(payload[key], list):
            out[key] = payload[key]
            break
    for meta_key in ("_date_filter", "_event_enrichment", "_source", "_marketing_status"):
        if meta_key in payload:
            out[meta_key] = payload[meta_key]
    return out


def _client_venues_payload_for_storage(payload: dict[str, Any]) -> dict[str, Any]:
    venues = list(payload.get("clientVenues") or payload.get("ClientVenues") or [])
    if not venues:
        return {}
    return {"clientVenues": venues}


def load_last_client_venues_payload(user_id: str, session_id: str) -> dict[str, Any] | None:
    if not user_id or not session_id:
        return None
    path = _GRAPH_STATE_DIR / user_id / f"{session_id}.json"
    try:
        if not path.is_file():
            return None
        store = json.loads(path.read_text(encoding="utf-8"))
        block = store.get("last_client_venues_payload")
        if isinstance(block, dict) and block.get("clientVenues"):
            return block
    except (json.JSONDecodeError, OSError):
        return None
    return None


def recall_for_session(
    user_id: str,
    session_id: str,
    question: str,
) -> dict[str, Any]:
    """Load session focus + Chroma snippets for LLM context only (no routing decisions)."""
    if not SESSION_MEMORY_ENABLED or not user_id or not session_id:
        return {"focus": load_session_focus(user_id, session_id), "source": "context_only"}

    focus = load_session_focus(user_id, session_id)

    try:
        collection = _ensure_collection(
            CHROMA_SESSION_COLLECTION,
            "Per-user session intent memory",
        )
        if collection.count() == 0:
            return {"focus": focus, "session_snippets": [], "source": "context_only"}
        vectors = embed_texts([question])
        result = collection.query(
            query_embeddings=vectors,
            n_results=SESSION_MEMORY_TOP_K,
            where={
                "$and": [
                    {"user_id": {"$eq": user_id}},
                    {"session_id": {"$eq": session_id}},
                ],
            },
            include=["documents", "metadatas", "distances"],
        )
        doc_rows = (result.get("documents") or [[]])[0]
        snippets = [str(d) for d in doc_rows if d][:SESSION_MEMORY_TOP_K]
        return {
            "focus": focus,
            "session_snippets": snippets,
            "source": "context_only",
        }
    except Exception:
        return {"focus": focus, "session_snippets": [], "source": "context_only"}


def persist_retrieval_trace(
    user_id: str,
    session_id: str,
    question: str,
    intent: str,
    kb_snippets: list[str],
) -> None:
    """Store KB retriever output in Chroma (agent memory), not used to skip LLM routing."""
    if not SESSION_MEMORY_ENABLED or not user_id or not session_id or not kb_snippets:
        return
    fp = question_fingerprint(question)
    doc = (
        f"KB retrieval for: {strip_ui_region(question)[:500]}\n"
        f"Intent (LLM): {intent}\n"
        + "\n---\n".join(kb_snippets[:5])
    )[:4000]
    try:
        collection = _ensure_collection(
            CHROMA_SESSION_COLLECTION,
            "Per-user session intent memory",
        )
        turn_id = _scoped_id(user_id, session_id, f"retrieve-{fp}")
        collection.upsert(
            ids=[turn_id],
            documents=[doc],
            embeddings=embed_texts([doc]),
            metadatas=[
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "intent": intent,
                    "record_type": "kb_retrieval",
                    "question_fp": fp,
                    "ts": int(time.time()),
                },
            ],
        )
    except Exception:
        pass


def persist_turn(
    user_id: str,
    session_id: str,
    question: str,
    state: dict[str, Any],
) -> None:
    if not SESSION_MEMORY_ENABLED or not user_id or not session_id:
        return

    intent = str(state.get("intent") or "")
    plan = state.get("action_plan") or {}
    answer = str(state.get("answer") or "")[:2000]
    fp = question_fingerprint(question)
    doc = memory_document_text(question, intent, answer, plan=plan)

    try:
        collection = _ensure_collection(
            CHROMA_SESSION_COLLECTION,
            "Per-user session intent memory",
        )
        turn_id = _scoped_id(user_id, session_id, fp)
        collection.upsert(
            ids=[turn_id],
            documents=[doc],
            embeddings=embed_texts([doc]),
            metadatas=[
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "intent": intent,
                    "plan_json": json.dumps(plan, default=str)[:4000],
                    "question_fp": fp,
                    "record_type": "turn",
                    "kb_count": len(state.get("kb_snippets") or []),
                    "ts": int(time.time()),
                },
            ],
        )
    except Exception:
        pass

    try:
        _GRAPH_STATE_DIR.mkdir(parents=True, exist_ok=True)
        user_dir = _GRAPH_STATE_DIR / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        path = user_dir / f"{session_id}.json"
        store: dict[str, Any] = {}
        if path.is_file():
            store = json.loads(path.read_text(encoding="utf-8"))
        by_q = store.setdefault("by_question", {})
        serializable = _state_for_storage(state)
        by_q[fp] = {
            "intent": intent,
            "state": serializable,
            "ts": int(time.time()),
        }
        store["latest"] = {"question_fp": fp, "intent": intent, "ts": int(time.time())}
        _update_session_focus(store, intent, plan if isinstance(plan, dict) else {}, state)
        path.write_text(json.dumps(store, default=str), encoding="utf-8")
    except (OSError, TypeError, ValueError):
        pass

    try:
        state_coll = _ensure_collection(
            CHROMA_STATE_COLLECTION,
            "LangGraph state snapshots metadata",
        )
        state_id = _scoped_id(user_id, session_id, "latest")
        snapshot = json.dumps(_state_for_storage(state), default=str)[:12000]
        state_coll.upsert(
            ids=[state_id],
            documents=[snapshot],
            embeddings=embed_texts([doc]),
            metadatas=[
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "intent": intent,
                    "question_fp": fp,
                    "ts": int(time.time()),
                },
            ],
        )
    except Exception:
        pass


def _state_for_storage(state: dict[str, Any]) -> dict[str, Any]:
    payload = state.get("api_payload")
    slim_payload = None
    if isinstance(payload, dict):
        slim_payload = {
            k: v
            for k, v in payload.items()
            if not str(k).startswith("_") and k not in ("event", "events", "primary", "publish")
        }
        if payload.get("_pending_confirmation"):
            slim_payload = {"_pending_confirmation": True, "intent": payload.get("intent")}
    return {
        "question": state.get("question"),
        "intent": state.get("intent"),
        "action_plan": state.get("action_plan"),
        "answer": state.get("answer"),
        "api_error": state.get("api_error"),
        "api_payload": slim_payload,
        "mutations_dry_run": state.get("mutations_dry_run"),
    }
