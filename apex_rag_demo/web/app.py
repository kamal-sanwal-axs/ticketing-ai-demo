from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from apex_rag_demo.auth import REGIONS, profile_from_token, validate_token_with_admin
from apex_rag_demo.graph import run_demo

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="APEX AI Helper Demo", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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
    execute_writes: bool = False


class ChatResponse(BaseModel):
    answer: str
    intent: str


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer <token>")
    return authorization[7:].strip()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


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

    state = run_demo(
        question,
        execute_writes=body.execute_writes,
        bearer_token=token,
    )
    return ChatResponse(answer=state["answer"], intent=state["intent"])
