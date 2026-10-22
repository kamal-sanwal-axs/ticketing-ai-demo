from __future__ import annotations

from contextvars import ContextVar

from apex_rag_demo.config import APEX_BEARER_TOKEN

_request_bearer: ContextVar[str] = ContextVar("request_bearer", default="")


def set_request_bearer(token: str) -> None:
    _request_bearer.set(token.strip())


def get_bearer_token() -> str:
    return _request_bearer.get() or APEX_BEARER_TOKEN


def auth_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    token = get_bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def use_mock_api() -> bool:
    from apex_rag_demo.config import APEX_MOCK

    return APEX_MOCK or not get_bearer_token()
