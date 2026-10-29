from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from apex_rag_demo.auth import REGIONS, profile_from_token, validate_token_with_admin
from apex_rag_demo.graph import run_demo
from apex_rag_demo.runtime.graph_runtime import init_runtime, shutdown_runtime
from apex_rag_demo.web.chat_handlers import build_chat_response_dict, phase_label
from apex_rag_demo.web.plugins_api import router as plugins_router

STATIC_DIR = Path(__file__).resolve().parent / "static"
FRONTEND_DIST = STATIC_DIR / "dist"
_LEGACY_INDEX = STATIC_DIR / "index.html"

app = FastAPI(title="APEX AI Helper Demo", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend_assets")
app.include_router(plugins_router)


@app.on_event("startup")
def _on_startup() -> None:
    import threading

    init_runtime()

    from apex_rag_demo.intent_semantic import warm_intent_semantic_index

    threading.Thread(target=warm_intent_semantic_index, daemon=True).start()


@app.on_event("shutdown")
def _on_shutdown() -> None:
    from apex_rag_demo.rag.embeddings import shutdown_embedding_workers

    shutdown_embedding_workers()
    shutdown_runtime()


class LoginRequest(BaseModel):
    token: str = Field(min_length=20)
    region: str = "US-West"


class LoginResponse(BaseModel):
    ok: bool
    profile: dict
    message: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    region: str = "US-West"
    confirm_mutation: bool = False
    mutation_token: str | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    intent: str
    display: dict | None = None
    requires_confirmation: bool = False
    mutation_token: str | None = None
    session_id: str
    memory_source: str | None = None
    error: bool = False
    error_code: str | None = None
    error_message: str | None = None
    stack_status: dict | None = None


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer <token>")
    return authorization[7:].strip()


@app.get("/")
async def index() -> FileResponse:
    built = FRONTEND_DIST / "index.html"
    if built.is_file():
        return FileResponse(built)
    return FileResponse(_LEGACY_INDEX)


@app.get("/api/regions")
async def list_regions() -> list[dict[str, str]]:
    return list(REGIONS)


@app.post("/api/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    region = body.region
    valid_regions = {r["id"] for r in REGIONS}
    if region not in valid_regions:
        raise HTTPException(status_code=400, detail="Unknown region")

    ok, err = validate_token_with_admin(body.token)
    profile = profile_from_token(body.token, region)
    if not ok:
        return LoginResponse(ok=False, profile=profile, message=err)
    return LoginResponse(ok=True, profile=profile, message=None)


@app.get("/api/profile")
async def profile(
    authorization: str | None = Header(default=None),
    region: str = "US-West",
) -> dict:
    token = _extract_bearer(authorization)
    ok, err = validate_token_with_admin(token)
    if not ok:
        raise HTTPException(status_code=401, detail=err or "Invalid token")
    return profile_from_token(token, region)


@app.get("/api/ui/stack")
async def ui_stack_status(region: str = "") -> dict:
    from apex_rag_demo.web.ui_stack import build_ui_stack_status

    return build_ui_stack_status(region=region or None)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    authorization: str | None = Header(default=None),
) -> ChatResponse:
    token = _extract_bearer(authorization)
    ok, err = validate_token_with_admin(token)
    if not ok:
        raise HTTPException(status_code=401, detail=err or "Invalid token")

    question = body.message.strip()
    if body.region:
        question = f"[User region: {body.region}] {question}"

    profile = profile_from_token(token, body.region)
    user_id = str(profile.get("userId") or profile.get("email") or "anonymous")
    session_id = (body.session_id or "").strip() or str(uuid.uuid4())

    try:
        state = run_demo(
            question,
            bearer_token=token,
            confirm_mutation=body.confirm_mutation,
            mutation_token=body.mutation_token,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception as exc:  # noqa: BLE001
        from apex_rag_demo.pipeline_errors import failure_state_patch

        state = {
            "question": question,
            "intent": "explain",
            "answer": "",
            "api_error": None,
            "api_payload": None,
            "kb_snippets": [],
            "action_plan": {},
            "mutations_dry_run": False,
            **failure_state_patch(exc, phase="chat_api", question=question),
        }
    payload = build_chat_response_dict(
        state,
        question=question,
        session_id=session_id,
        region=body.region,
    )
    return ChatResponse(**payload)


@app.post("/api/chat/stream")
async def chat_stream(
    body: ChatRequest,
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    token = _extract_bearer(authorization)
    ok, err = validate_token_with_admin(token)
    if not ok:
        raise HTTPException(status_code=401, detail=err or "Invalid token")

    question = body.message.strip()
    if body.region:
        question = f"[User region: {body.region}] {question}"

    profile = profile_from_token(token, body.region)
    user_id = str(profile.get("userId") or profile.get("email") or "anonymous")
    session_id = (body.session_id or "").strip() or str(uuid.uuid4())

    async def event_generator():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

        def on_phase(phase: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ("status", phase))

        async def run_pipeline() -> None:
            try:
                state = await asyncio.to_thread(
                    run_demo,
                    question,
                    bearer_token=token,
                    confirm_mutation=body.confirm_mutation,
                    mutation_token=body.mutation_token,
                    user_id=user_id,
                    session_id=session_id,
                    progress_callback=on_phase,
                )
                await queue.put(("done", state))
            except Exception as exc:  # noqa: BLE001
                await queue.put(("error", exc))

        worker = asyncio.create_task(run_pipeline())
        yield f"event: status\ndata: {json.dumps({'phase': 'started', 'label': 'Starting…'})}\n\n"

        while True:
            kind, payload = await queue.get()
            if kind == "status":
                phase = str(payload)
                yield (
                    f"event: status\ndata: {json.dumps({'phase': phase, 'label': phase_label(phase)})}\n\n"
                )
            elif kind == "error":
                from apex_rag_demo.pipeline_errors import failure_state_patch

                exc = payload if isinstance(payload, BaseException) else RuntimeError(str(payload))
                state = {
                    "question": question,
                    "intent": "explain",
                    "answer": "",
                    "kb_snippets": [],
                    "action_plan": {},
                    "mutations_dry_run": False,
                    **failure_state_patch(exc, phase="chat_stream", question=question),
                }
                result = build_chat_response_dict(state, question=question, session_id=session_id, region=body.region)
                yield f"event: result\ndata: {json.dumps(result)}\n\n"
                break
            elif kind == "done":
                state = payload if isinstance(payload, dict) else {}
                result = build_chat_response_dict(state, question=question, session_id=session_id, region=body.region)
                yield f"event: result\ndata: {json.dumps(result)}\n\n"
                break

        await worker

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
