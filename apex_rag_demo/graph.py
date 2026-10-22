from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from apex_rag_demo.clients import (
    apex_admin,
    apex_events,
    apex_inventory,
    apex_marketing,
    apex_search,
)
from apex_rag_demo.config import DEMO_EXECUTE_WRITES
from apex_rag_demo.planning import classify_intent, plan_for_intent
from apex_rag_demo.rag.index import retrieve
from apex_rag_demo.response_formatters import format_deterministic, summarize_with_llm


class DemoState(TypedDict):
    question: str
    execute_writes: bool
    intent: str
    kb_snippets: list[str]
    action_plan: dict
    search_query: str
    api_payload: dict | None
    api_error: str | None
    answer: str


def retrieve_kb(state: DemoState) -> DemoState:
    snippets = retrieve(state["question"])
    return {**state, "kb_snippets": snippets}


def detect_intent(state: DemoState) -> DemoState:
    intent = classify_intent(state["question"])
    return {**state, "intent": intent}


def plan_action(state: DemoState) -> DemoState:
    plan = plan_for_intent(state["intent"], state["question"])
    search_query = plan.get("query", "") if state["intent"] == "search_events" else ""
    return {**state, "action_plan": plan, "search_query": search_query}


def execute_action(state: DemoState) -> DemoState:
    intent = state["intent"]
    plan = state["action_plan"]
    dry_run = not state["execute_writes"]

    try:
        if intent == "search_events":
            query = plan.get("query") or state["search_query"]
            payload = apex_search.search_events_suggest(query)
            suggestions = (payload or {}).get("suggestions") or (payload or {}).get("Suggestions") or []
            events = (payload or {}).get("events") or (payload or {}).get("Events") or []
            if not suggestions and not events:
                payload = apex_search.search_events(query)
            return {**state, "api_payload": payload, "api_error": None}
        if intent == "list_client_venues":
            payload = apex_search.search_client_venues(
                page_size=int(plan.get("pageSize") or 25),
                organization_ids=plan.get("organizationIds") or None,
            )
            return {**state, "api_payload": payload, "api_error": None}
        if intent == "create_organization":
            body = apex_admin.build_create_organization_body(plan)
            payload = apex_admin.create_organization(body, dry_run=dry_run)
            return {**state, "api_payload": payload, "api_error": None}
        if intent == "create_client_venue":
            body = apex_admin.build_create_client_venue_body(plan)
            payload = apex_admin.create_client_venue(body, dry_run=dry_run)
            return {**state, "api_payload": payload, "api_error": None}
        if intent == "get_event":
            event_id = plan.get("eventId") or ""
            if not event_id:
                return {**state, "api_payload": None, "api_error": None}
            payload = apex_events.get_event(event_id)
            return {**state, "api_payload": payload, "api_error": None}
        if intent == "inventory_zones":
            event_id = plan.get("eventId") or ""
            if not event_id:
                return {**state, "api_payload": None, "api_error": None}
            payload = apex_inventory.get_event_primary_zones(event_id)
            return {**state, "api_payload": payload, "api_error": None}
        if intent == "marketing_events":
            payload = apex_marketing.list_events()
            return {**state, "api_payload": payload, "api_error": None}
        if intent == "explain":
            return {**state, "api_payload": None, "api_error": None}
        return {**state, "api_payload": {"note": "unhandled intent"}, "api_error": None}
    except Exception as exc:  # noqa: BLE001 — demo boundary
        return {**state, "api_payload": None, "api_error": str(exc)}


def synthesize_answer(state: DemoState) -> DemoState:
    intent = state["intent"]
    answer = format_deterministic(
        intent,
        state["question"],
        state["api_payload"],
        state["api_error"],
        action_plan=state["action_plan"],
        execute_writes=state["execute_writes"],
        kb_snippets=state["kb_snippets"],
    )
    if answer is not None:
        return {**state, "answer": answer}

    api_block = apex_admin.format_payload(state["api_payload"]) if state["api_payload"] else ""
    answer = summarize_with_llm(state["question"], api_block or state["api_error"] or "")
    return {**state, "answer": answer}


def build_graph():
    graph = StateGraph(DemoState)
    graph.add_node("retrieve_kb", retrieve_kb)
    graph.add_node("detect_intent", detect_intent)
    graph.add_node("plan_action", plan_action)
    graph.add_node("execute_action", execute_action)
    graph.add_node("synthesize_answer", synthesize_answer)

    graph.add_edge(START, "retrieve_kb")
    graph.add_edge("retrieve_kb", "detect_intent")
    graph.add_edge("detect_intent", "plan_action")
    graph.add_edge("plan_action", "execute_action")
    graph.add_edge("execute_action", "synthesize_answer")
    graph.add_edge("synthesize_answer", END)

    return graph.compile()


def run_demo(
    question: str,
    execute_writes: bool | None = None,
    bearer_token: str | None = None,
) -> DemoState:
    from apex_rag_demo.clients.http_common import set_request_bearer

    if bearer_token:
        set_request_bearer(bearer_token)
    app = build_graph()
    initial: DemoState = {
        "question": question,
        "execute_writes": execute_writes
        if execute_writes is not None
        else DEMO_EXECUTE_WRITES,
        "intent": "explain",
        "kb_snippets": [],
        "action_plan": {},
        "search_query": "",
        "api_payload": None,
        "api_error": None,
        "answer": "",
    }
    return app.invoke(initial)
