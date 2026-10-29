from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from apex_rag_demo.clients import apex_admin
from apex_rag_demo.llm_synthesis import synthesize_apex_answer
from apex_rag_demo.config import DEMO_MUTATIONS_DRY_RUN, RAG_RETRIEVE_K, TOP_K
from apex_rag_demo.rag.index import (
    retrieve,
    retrieve_bi_encoder_candidates,
    rerank_retrieval_candidates,
)
from apex_rag_demo.org_hierarchy import reset_hierarchy_cache
from apex_rag_demo.response_formatters import format_deterministic, summarize_with_llm


class _DemoStateRequired(TypedDict):
    question: str
    mutations_dry_run: bool
    confirm_mutation: bool
    mutation_token: str | None
    user_id: str
    session_id: str
    memory_source: str
    intent: str
    kb_snippets: list[str]
    action_plan: dict
    search_query: str
    api_payload: dict | None
    api_error: str | None
    answer: str


class DemoState(_DemoStateRequired, total=False):
    session_focus: dict
    session_snippets: list[str]
    chat_messages: list[dict]
    topic_shift: bool
    conversational_turn: bool
    semantic_context_block: str
    semantic_intent_hint: str | None
    semantic_score: float
    skip_rag_retrieve: bool
    api_trace: list[dict]
    api_facts: dict
    orchestrator_round: int
    orchestrator_action: str
    needs_id_clarification: bool
    pipeline_error: dict | None
    need_kb_retrieval: bool
    chroma_system_context: str
    retrieval_candidates: list[str]
    sandbox_display: dict


def load_agent_context(state: DemoState) -> DemoState:
    from apex_rag_demo.chat_progress import emit_progress
    from apex_rag_demo.rag.chat_history import load_chat_messages
    from apex_rag_demo.rag.session_memory import recall_for_session

    emit_progress("load_session")
    emit_progress("semantic_turn")

    from apex_rag_demo.semantic_turn import prepare_semantic_turn

    user_id = state.get("user_id") or ""
    session_id = state.get("session_id") or ""
    raw_messages = load_chat_messages(user_id, session_id)
    semantic = prepare_semantic_turn(state["question"], raw_messages)
    skip_rag = _should_skip_rag_retrieve(semantic)
    from apex_rag_demo.rag.intent_chroma import format_progress_phase

    emit_progress(format_progress_phase(semantic.pre_llm))

    pre = semantic.pre_llm
    semantic_fields = {
        "chat_messages": semantic.chat_messages,
        "topic_shift": semantic.topic_shift,
        "conversational_turn": semantic.conversational_turn,
        "semantic_context_block": semantic.context_block,
        "semantic_intent_hint": semantic.intent_hint,
        "semantic_score": semantic.semantic_score,
        "skip_rag_retrieve": skip_rag,
        "semantic_routing_label": pre.label if pre else None,
        "semantic_route_intent": pre.intent if pre else None,
        "semantic_route_score": pre.score if pre else 0.0,
        "skip_llm_classify": bool(pre and pre.skip_llm_classify),
    }

    if state.get("confirm_mutation"):
        return {
            **state,
            "memory_source": "fresh",
            "session_focus": state.get("session_focus") or {},
            **semantic_fields,
        }

    fresh_session = not raw_messages
    if fresh_session or semantic.conversational_turn or semantic.topic_shift:
        return {
            **state,
            "memory_source": (
                "new_chat"
                if fresh_session
                else ("semantic_fresh_topic" if semantic.topic_shift else "conversational")
            ),
            "session_focus": {},
            "session_snippets": [],
            **semantic_fields,
            "kb_snippets": [],
            "need_kb_retrieval": False,
            "topic_shift": True if fresh_session else semantic.topic_shift,
        }

    hit = recall_for_session(user_id, session_id, state["question"])
    return {
        **state,
        "memory_source": hit.get("source") or "context_only",
        "session_focus": hit.get("focus") or {},
        "session_snippets": hit.get("session_snippets") or [],
        **semantic_fields,
        "topic_shift": False,
        "kb_snippets": [],
        "need_kb_retrieval": False,
    }


def _should_skip_rag_retrieve(semantic: object) -> bool:
    from apex_rag_demo.crud_policy import WriteKind, write_kind_for_intent
    from apex_rag_demo.config import INTENT_SEMANTIC_MIN_SCORE

    if getattr(semantic, "conversational_turn", False):
        return True
    hint = getattr(semantic, "intent_hint", None)
    score = float(getattr(semantic, "semantic_score", 0.0) or 0.0)
    if hint and score >= INTENT_SEMANTIC_MIN_SCORE:
        try:
            if write_kind_for_intent(str(hint)) == WriteKind.READ:
                return True
        except KeyError:
            pass
    return False


def enrich_from_kg(state: DemoState) -> DemoState:
    from apex_rag_demo.chat_progress import emit_progress
    from apex_rag_demo.rag.kg_enrich import fetch_kg_system_appendix

    emit_progress("kg_enrich")

    if state.get("topic_shift"):
        return state

    appendix = fetch_kg_system_appendix(
        state["question"],
        state.get("session_focus") if isinstance(state.get("session_focus"), dict) else {},
    )
    if not appendix:
        return state

    base = (state.get("chroma_system_context") or "").strip()
    combined = f"{base}\n\n{appendix}".strip() if base else appendix
    return {**state, "chroma_system_context": combined}


def enrich_system_from_chroma(state: DemoState) -> DemoState:
    from apex_rag_demo.chat_progress import emit_progress
    from apex_rag_demo.rag.agent_chroma import fetch_chroma_system_enrichment

    emit_progress("chroma_enrich")

    if state.get("topic_shift"):
        return {
            **state,
            "chroma_system_context": "",
            "session_snippets": [],
            "retrieval_candidates": [],
        }

    enrichment = fetch_chroma_system_enrichment(
        state.get("user_id") or "",
        state.get("session_id") or "",
        state["question"],
    )
    appendix = enrichment.to_system_appendix(include_kb=False)
    return {
        **state,
        "chroma_system_context": appendix,
        "session_snippets": enrichment.session_turns or state.get("session_snippets") or [],
        "retrieval_candidates": [],
    }


def retrieve_bi_encoder(state: DemoState) -> DemoState:
    from apex_rag_demo.chat_progress import emit_progress

    emit_progress("retrieve_kb")
    fetch_k = max(TOP_K, RAG_RETRIEVE_K)
    candidates = retrieve_bi_encoder_candidates(state["question"], fetch_k)
    return {**state, "retrieval_candidates": candidates}


def _route_after_enrich(state: DemoState) -> str:
    if state.get("skip_rag_retrieve"):
        return "classify_agent"
    return "retrieve_bi_encoder"


def rerank_cross_encoder(state: DemoState) -> DemoState:
    from apex_rag_demo.rag.agent_chroma import append_kb_to_system_context

    candidates = state.get("retrieval_candidates") or []
    hint = state.get("semantic_route_intent") or state.get("semantic_intent_hint")
    hint_str = str(hint).strip() if hint else None
    ranked = rerank_retrieval_candidates(
        state["question"],
        candidates,
        TOP_K,
        intent_hint=hint_str,
    )
    appendix = append_kb_to_system_context(state.get("chroma_system_context") or "", ranked)
    return {
        **state,
        "kb_snippets": ranked,
        "chroma_system_context": appendix,
    }


def classify_agent(state: DemoState) -> DemoState:
    from apex_rag_demo.agent_classify import classify_with_routing
    from apex_rag_demo.chat_progress import emit_progress

    if state.get("skip_llm_classify") and state.get("semantic_route_intent"):
        print(
            f"--- AGENT CLASSIFY reuse pre-LLM semantic → {state['semantic_route_intent']} ---",
            flush=True,
        )
        return {
            **state,
            "intent": state["semantic_route_intent"],
            "need_kb_retrieval": False,
            "memory_source": "semantic_pre_llm",
        }

    emit_progress("classify_llm")
    intent, need_kb = classify_with_routing(
        state["question"],
        session_focus=state.get("session_focus"),
        session_snippets=state.get("session_snippets"),
        chroma_system_context=state.get("chroma_system_context"),
        semantic_context_block=state.get("semantic_context_block"),
        topic_shift=bool(state.get("topic_shift")),
        chat_history=state.get("chat_messages"),
    )
    return {
        **state,
        "intent": intent,
        "need_kb_retrieval": need_kb,
        "memory_source": "llm_classify",
    }


def retrieve_agent_context(state: DemoState) -> DemoState:
    print("--- AGENT RETRIEVE KB (vector + rerank) ---", flush=True)
    from apex_rag_demo.rag.session_memory import persist_retrieval_trace

    snippets = retrieve(state["question"])
    persist_retrieval_trace(
        state.get("user_id") or "",
        state.get("session_id") or "",
        state["question"],
        state.get("intent") or "explain",
        snippets,
    )
    return {
        **state,
        "kb_snippets": snippets,
        "memory_source": "agent_retrieve",
    }


def _route_after_classify(state: DemoState) -> str:
    from apex_rag_demo.compound_request import is_compound_operational_request

    if is_compound_operational_request(state.get("question") or ""):
        return "orchestrator_decide"
    if state.get("conversational_turn"):
        return "synthesize_answer"
    if state.get("need_kb_retrieval"):
        return "retrieve_agent_context"
    return "orchestrator_decide"


def _route_after_orchestrator_decide(state: DemoState) -> str:
    from apex_rag_demo.config import ORCHESTRATOR_MAX_ROUNDS

    if state.get("pipeline_error"):
        return "synthesize_answer"
    round_num = int(state.get("orchestrator_round") or 0)
    action = state.get("orchestrator_action")
    if action in ("call_api", "call_plugin", "run_sandbox") and round_num < ORCHESTRATOR_MAX_ROUNDS:
        if action == "run_sandbox":
            return "sandbox_tool_run"
        return "orchestrator_execute"
    return "synthesize_answer"


def extract_api_facts(state: DemoState) -> DemoState:
    from apex_rag_demo.api_facts import build_api_facts

    facts = build_api_facts(
        state.get("api_trace"),
        state.get("api_payload"),
        state.get("intent") or "explain",
    )
    return {**state, "api_facts": facts}


def _route_after_extract_api_facts(state: DemoState) -> str:
    from apex_rag_demo.config import ORCHESTRATOR_MAX_ROUNDS

    if state.get("pipeline_error"):
        return "synthesize_answer"
    round_num = int(state.get("orchestrator_round") or 0)
    if round_num < ORCHESTRATOR_MAX_ROUNDS:
        return "orchestrator_decide"
    return "synthesize_answer"


def orchestrator_decide(state: DemoState) -> DemoState:
    from apex_rag_demo.agent_orchestrator import decide_orchestrator_step
    from apex_rag_demo.chat_progress import emit_progress

    emit_progress("orchestrator_llm")
    round_num = int(state.get("orchestrator_round") or 0) + 1
    decision = decide_orchestrator_step(
        state["question"],
        classified_intent=state.get("intent") or "explain",
        session_focus=state.get("session_focus"),
        api_trace=state.get("api_trace"),
        orchestrator_round=round_num,
        user_id=state.get("user_id") or "",
        session_id=state.get("session_id") or "",
        chroma_system_context=state.get("chroma_system_context"),
        semantic_context_block=state.get("semantic_context_block"),
        chat_history=state.get("chat_messages"),
        semantic_intent_hint=state.get("semantic_intent_hint"),
        semantic_score=float(state.get("semantic_score") or 0.0),
    )
    reason = str(decision.get("orchestrator_reason") or "")
    _deterministic_reasons = frozenset(
        {
            "deterministic_single_step_read",
            "missing_event_id",
            "reports_single_step",
            "reports_after_event_lookup",
            "reports_event_lookup_first",
            "reports_after_catalog_lookup",
            "reports_dynamic_tool_lookup",
            "reports_dynamic_tool",
            "reports_ids_unresolved",
            "reports_api_complete",
            "dynamic_openapi_tool",
        },
    )
    used_llm = reason not in _deterministic_reasons
    out: DemoState = {
        **state,
        "orchestrator_round": round_num,
        "orchestrator_action": decision.get("orchestrator_action") or "finish",
        "memory_source": "orchestrator_llm" if used_llm else "orchestrator_deterministic",
        "needs_id_clarification": bool(decision.get("needs_id_clarification")),
    }
    if decision.get("intent"):
        out["intent"] = decision["intent"]
    if decision.get("action_plan") is not None:
        out["action_plan"] = decision["action_plan"]
        if out["intent"] == "search_events":
            out["search_query"] = decision["action_plan"].get("query", "")
    return out


def sandbox_tool_run(state: DemoState) -> DemoState:
    from apex_rag_demo.chat_progress import emit_progress
    from apex_rag_demo.sandbox_toolkit.chat_execute import execute_sandbox_from_plan
    from apex_rag_demo.sandbox_toolkit.orchestrator import build_sandbox_display

    emit_progress("sandbox_tool_run")
    plan = state.get("action_plan") or {}
    trace = list(state.get("api_trace") or [])
    result = execute_sandbox_from_plan(plan if isinstance(plan, dict) else {})
    trace.append({"sandbox": True, "plan": plan, "result": result, "error": result.get("error")})
    display = build_sandbox_display(result)
    answer = ""
    if display and display.get("paragraphs"):
        answer = str(display["paragraphs"][0])[:1200]
    elif result.get("ok"):
        answer = "Sandbox finished successfully."
    return {
        **state,
        "api_trace": trace,
        "api_payload": result,
        "api_error": None if result.get("ok") else str(result.get("error")),
        "intent": "explain",
        "memory_source": "sandbox_toolkit",
        "answer": answer if answer else state.get("answer", ""),
        "sandbox_display": display,
    }


def orchestrator_execute(state: DemoState) -> DemoState:
    from apex_rag_demo.api_dispatch import execute_intent_api
    from apex_rag_demo.chat_progress import emit_progress

    emit_progress("orchestrator_api")

    if state.get("orchestrator_action") == "call_plugin":
        from apex_rag_demo.plugins.chat_execute import execute_user_plugin_from_plan
        from apex_rag_demo.plugins.sandbox import SandboxViolation

        plan = state.get("action_plan") or {}
        trace = list(state.get("api_trace") or [])
        try:
            result = execute_user_plugin_from_plan(state.get("user_id") or "", plan)
            trace.append(
                {
                    "plugin_id": plan.get("plugin_id"),
                    "parameters": plan.get("parameters"),
                    "result": result,
                    "error": None,
                },
            )
            return {
                **state,
                "api_trace": trace,
                "api_payload": result,
                "api_error": None,
                "intent": "explain",
                "memory_source": "orchestrator_plugin",
            }
        except SandboxViolation as exc:
            trace.append(
                {
                    "plugin_id": plan.get("plugin_id"),
                    "parameters": plan.get("parameters"),
                    "error": str(exc),
                },
            )
            return {
                **state,
                "api_trace": trace,
                "api_error": str(exc),
                "memory_source": "orchestrator_plugin",
            }

    intent = state["intent"]
    plan = dict(state.get("action_plan") or {})
    from apex_rag_demo.id_prompts import resolve_event_id

    if intent == "get_event":
        eid = resolve_event_id(state["question"], plan, state.get("session_focus"))
        if eid and not str(plan.get("eventId") or "").strip():
            plan = {**plan, "eventId": eid}
    result = execute_intent_api(
        intent,
        plan,
        question=state["question"],
        search_query=state.get("search_query") or "",
        mutations_dry_run=state["mutations_dry_run"],
        confirm_mutation=state.get("confirm_mutation", False),
        mutation_token=state.get("mutation_token"),
    )
    trace = list(state.get("api_trace") or [])
    trace.append(
        {
            "intent": intent,
            "plan": plan,
            "tool_id": plan.get("tool_id"),
            "error": result.get("api_error"),
            "payload": result.get("api_payload"),
        },
    )
    merged: DemoState = {
        **state,
        "api_trace": trace,
        "api_payload": result.get("api_payload"),
        "api_error": result.get("api_error"),
        "memory_source": "orchestrator_api",
    }
    if result.get("pipeline_error"):
        merged["pipeline_error"] = result["pipeline_error"]
    if result.get("answer"):
        merged["answer"] = result["answer"]
    return merged


def synthesize_answer(state: DemoState) -> DemoState:
    if state.get("pipeline_error"):
        return state
    from apex_rag_demo.trace_payload import enrich_state_from_best_trace

    state = enrich_state_from_best_trace(state)
    from apex_rag_demo.marketing_list_followup import apply_marketing_session_reuse

    state = apply_marketing_session_reuse(state)
    from apex_rag_demo.crud_policy import WriteKind, write_kind_for_intent
    from apex_rag_demo.id_prompts import clarify_missing_event_id
    from apex_rag_demo.intent_semantic import is_conversational_message
    from apex_rag_demo.response_formatters import strip_ui_region

    bare = strip_ui_region(state["question"])
    from apex_rag_demo.compound_request import format_compound_answer, looks_like_events_plus_seat_level_detail

    trace = state.get("api_trace") or []
    if looks_like_events_plus_seat_level_detail(state["question"]):
        if len(trace) >= 1:
            return {
                **state,
                "intent": state.get("intent") or "marketing_events",
                "answer": format_compound_answer(state["question"], trace),
                "memory_source": "compound_formatter",
            }
        if (state.get("intent") or "") == "marketing_events":
            from apex_rag_demo.compound_request import compound_plan_chunks

            chunks = compound_plan_chunks(state["question"])
            return {
                **state,
                "answer": (
                    "Running a multi-step live API plan:\n"
                    + "\n".join(f"• {c}" for c in chunks)
                    + "\n\nIf this message persists, restart the server — orchestrator did not execute."
                ),
                "memory_source": "compound_pending",
            }

    if state.get("needs_id_clarification") or (
        not state.get("api_trace") and state.get("api_payload") is None
    ):
        clarify = clarify_missing_event_id(
            state.get("intent") or "explain",
            state["question"],
            action_plan=state.get("action_plan"),
            session_focus=state.get("session_focus"),
        )
        if clarify:
            return {**state, "answer": clarify, "memory_source": "id_clarify"}
    if state.get("conversational_turn") or is_conversational_message(state["question"]):
        answer = format_deterministic(
            "explain",
            state["question"],
            None,
            None,
            kb_snippets=state.get("kb_snippets"),
        )
        if answer:
            return {
                **state,
                "intent": "explain",
                "answer": answer,
                "api_payload": None,
                "api_error": None,
                "api_trace": [],
                "memory_source": "conversational_welcome",
            }
    intent = state["intent"]
    _formatter_first = frozenset(
        {
            "marketing_events",
            "search_events",
            "search_orders",
            "search_order_payment_statuses",
            "search_customers",
            "list_client_venues",
            "list_users",
            "inventory_zones",
            "list_marketing_pixels",
            "get_event",
            "get_venue_config",
            "b2b_flash_report",
            "reports_inventory_event",
            "reports_timezones",
        },
    )
    if intent in _formatter_first and state.get("api_payload") is not None:
        answer = format_deterministic(
            intent,
            state["question"],
            state["api_payload"],
            state.get("api_error"),
            action_plan=state.get("action_plan"),
            kb_snippets=state.get("kb_snippets"),
        )
        if answer is not None:
            return {**state, "answer": answer, "memory_source": "formatter_grounded"}

    trace = state.get("api_trace") or []
    is_mutation = write_kind_for_intent(intent) != WriteKind.READ
    if trace and intent != "explain" and is_mutation:
        answer = format_deterministic(
            intent,
            state["question"],
            state["api_payload"],
            state.get("api_error"),
            action_plan=state.get("action_plan"),
            kb_snippets=state.get("kb_snippets"),
        )
        if answer is not None:
            return {**state, "answer": answer, "memory_source": "mutation_formatter_grounded"}

    if trace and intent != "explain" and not is_mutation and intent not in _formatter_first:
        try:
            from apex_rag_demo.api_facts import format_facts_for_answer
            from apex_rag_demo.chat_progress import emit_progress

            emit_progress("synthesize_llm")
            facts_block = format_facts_for_answer(state.get("api_facts") or {})
            answer = synthesize_apex_answer(
                state["question"],
                intent,
                api_payload={
                    "orchestrator_trace": trace,
                    "last": state.get("api_payload"),
                    "api_facts": state.get("api_facts"),
                    "facts_bullets": facts_block,
                },
                api_error=state.get("api_error"),
                kb_snippets=state.get("kb_snippets"),
                session_snippets=state.get("session_snippets"),
                action_plan=state.get("action_plan"),
                chroma_system_context=state.get("chroma_system_context"),
                semantic_context_block=state.get("semantic_context_block"),
                topic_shift=bool(state.get("topic_shift")),
                chat_history=state.get("chat_messages"),
            )
            return {**state, "answer": answer, "memory_source": "orchestrator_synthesize"}
        except Exception:
            pass
    answer = format_deterministic(
        intent,
        state["question"],
        state["api_payload"],
        state["api_error"],
        action_plan=state["action_plan"],
        kb_snippets=state["kb_snippets"],
    )
    if answer is not None:
        return {**state, "answer": answer}

    payload = state.get("api_payload")
    resolution = payload.get("_resolution") if isinstance(payload, dict) else None
    if intent == "get_event" and (
        resolution not in (None, "events_get")
        or (state.get("api_error") and isinstance(payload, dict))
    ):
        try:
            answer = synthesize_apex_answer(
                state["question"],
                intent,
                api_payload=payload,
                api_error=state.get("api_error"),
                kb_snippets=state.get("kb_snippets"),
                session_snippets=state.get("session_snippets"),
                action_plan=state.get("action_plan"),
                chroma_system_context=state.get("chroma_system_context"),
                semantic_context_block=state.get("semantic_context_block"),
                topic_shift=bool(state.get("topic_shift")),
                chat_history=state.get("chat_messages"),
            )
            return {**state, "answer": answer}
        except Exception:
            pass

    api_block = apex_admin.format_payload(state["api_payload"]) if state["api_payload"] else ""
    answer = summarize_with_llm(state["question"], api_block or state["api_error"] or "")
    return {**state, "answer": answer}


def persist_session_memory(state: DemoState) -> DemoState:
    from apex_rag_demo.answer_verifier import strip_ungrounded_uuids
    from apex_rag_demo.rag.agent_chroma import persist_agent_role_hint
    from apex_rag_demo.rag.chat_history import append_chat_turn, build_tool_message_content
    from apex_rag_demo.rag.session_memory import persist_turn

    user_id = state.get("user_id") or ""
    session_id = state.get("session_id") or ""
    answer = strip_ungrounded_uuids(
        str(state.get("answer") or ""),
        state.get("api_facts"),
    )
    state = {**state, "answer": answer}
    tool_content = build_tool_message_content(state) if not state.get("pipeline_error") else None
    append_chat_turn(
        user_id,
        session_id,
        state["question"],
        answer,
        tool_content=tool_content,
    )

    persist_turn(user_id, session_id, state["question"], state)
    if not state.get("pipeline_error") and state.get("intent"):
        persist_agent_role_hint(
            state.get("user_id") or "",
            state.get("session_id") or "",
            state["question"],
            state.get("intent") or "explain",
            state.get("action_plan") or {},
            str(state.get("answer") or "")[:500],
        )
    return state

def build_graph():
    graph = StateGraph(DemoState)
    graph.add_node("load_agent_context", load_agent_context)
    graph.add_node("enrich_system_from_chroma", enrich_system_from_chroma)
    graph.add_node("enrich_from_kg", enrich_from_kg)
    graph.add_node("retrieve_bi_encoder", retrieve_bi_encoder)
    graph.add_node("rerank_cross_encoder", rerank_cross_encoder)
    graph.add_node("classify_agent", classify_agent)
    graph.add_node("retrieve_agent_context", retrieve_agent_context)
    graph.add_node("orchestrator_decide", orchestrator_decide)
    graph.add_node("orchestrator_execute", orchestrator_execute)
    graph.add_node("sandbox_tool_run", sandbox_tool_run)
    graph.add_node("extract_api_facts", extract_api_facts)
    graph.add_node("synthesize_answer", synthesize_answer)
    graph.add_node("persist_session_memory", persist_session_memory)

    graph.add_edge(START, "load_agent_context")
    graph.add_edge("load_agent_context", "enrich_system_from_chroma")
    graph.add_edge("enrich_system_from_chroma", "enrich_from_kg")
    graph.add_conditional_edges(
        "enrich_from_kg",
        _route_after_enrich,
        {
            "retrieve_bi_encoder": "retrieve_bi_encoder",
            "classify_agent": "classify_agent",
        },
    )
    graph.add_edge("retrieve_bi_encoder", "rerank_cross_encoder")
    graph.add_edge("rerank_cross_encoder", "classify_agent")
    graph.add_conditional_edges(
        "classify_agent",
        _route_after_classify,
        {
            "retrieve_agent_context": "retrieve_agent_context",
            "orchestrator_decide": "orchestrator_decide",
            "synthesize_answer": "synthesize_answer",
        },
    )
    graph.add_edge("retrieve_agent_context", "orchestrator_decide")
    graph.add_conditional_edges(
        "orchestrator_decide",
        _route_after_orchestrator_decide,
        {
            "orchestrator_execute": "orchestrator_execute",
            "sandbox_tool_run": "sandbox_tool_run",
            "synthesize_answer": "synthesize_answer",
        },
    )
    graph.add_edge("orchestrator_execute", "extract_api_facts")
    graph.add_edge("sandbox_tool_run", "extract_api_facts")
    graph.add_conditional_edges(
        "extract_api_facts",
        _route_after_extract_api_facts,
        {
            "orchestrator_decide": "orchestrator_decide",
            "synthesize_answer": "synthesize_answer",
        },
    )
    graph.add_edge("synthesize_answer", "persist_session_memory")
    graph.add_edge("persist_session_memory", END)

    from apex_rag_demo.runtime.graph_runtime import get_checkpointer, get_store

    return graph.compile(checkpointer=get_checkpointer(), store=get_store())


def run_demo(
    question: str,
    execute_writes: bool | None = None,  # CLI: --execute sets mutations_dry_run=False
    bearer_token: str | None = None,
    *,
    confirm_mutation: bool = False,
    mutation_token: str | None = None,
    user_id: str = "",
    session_id: str = "",
    progress_callback: object | None = None,
) -> DemoState:
    from apex_rag_demo.chat_progress import reset_progress_callback, set_progress_callback
    from apex_rag_demo.clients.http_common import set_request_bearer

    if bearer_token:
        set_request_bearer(bearer_token)
    reset_hierarchy_cache()
    progress_token = None
    if callable(progress_callback):
        progress_token = set_progress_callback(progress_callback)
    app = build_graph()
    initial: DemoState = {
        "question": question,
        "mutations_dry_run": (not execute_writes)
        if execute_writes is not None
        else DEMO_MUTATIONS_DRY_RUN,
        "confirm_mutation": confirm_mutation,
        "mutation_token": mutation_token,
        "user_id": user_id,
        "session_id": session_id,
        "memory_source": "",
        "intent": "explain",
        "kb_snippets": [],
        "action_plan": {},
        "search_query": "",
        "api_payload": None,
        "api_error": None,
        "answer": "",
        "pipeline_error": None,
        "need_kb_retrieval": False,
        "chroma_system_context": "",
        "retrieval_candidates": [],
        "api_trace": [],
        "orchestrator_round": 0,
        "orchestrator_action": "",
    }
    from apex_rag_demo.runtime.graph_runtime import thread_config

    invoke_config = thread_config(user_id, session_id)
    try:
        return app.invoke(initial, invoke_config)
    except Exception as exc:  # noqa: BLE001 — LangGraph / LLM / RAG boundary
        from apex_rag_demo.pipeline_errors import failure_state_patch

        return {**initial, **failure_state_patch(exc, phase="langgraph", question=question)}
    finally:
        if progress_token is not None:
            reset_progress_callback(progress_token)
