from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from apex_rag_demo.config import DATA_DIR

CATALOG_PATH = DATA_DIR / "apex_services.json"


@dataclass(frozen=True)
class ApexService:
    id: str
    name: str
    base_url: str
    swagger_url: str
    swagger_ui_url: str | None
    demo_operations: list[str]


def _resolve_base_url(entry: dict) -> str:
    env_key = entry.get("base_url_env", "")
    default = entry.get("default_base_url", "").rstrip("/")
    if env_key:
        return os.getenv(env_key, default).rstrip("/")
    return default


def load_catalog() -> list[ApexService]:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    services: list[ApexService] = []
    for item in raw:
        services.append(
            ApexService(
                id=item["id"],
                name=item["name"],
                base_url=_resolve_base_url(item),
                swagger_url=item["swagger_url"],
                swagger_ui_url=item.get("swagger_ui_url"),
                demo_operations=list(item.get("demo_operations", [])),
            )
        )
    return services


def get_service(service_id: str) -> ApexService | None:
    for svc in load_catalog():
        if svc.id == service_id:
            return svc
    return None


def format_catalog_markdown() -> str:
    lines = [
        "| Service | Base URL | OpenAPI | Swagger UI |",
        "|---------|----------|---------|------------|",
    ]
    for svc in load_catalog():
        ui = (
            f"[UI]({svc.swagger_ui_url})"
            if svc.swagger_ui_url
            else "—"
        )
        lines.append(
            f"| **{svc.name}** | `{svc.base_url}` | [openapi]({svc.swagger_url}) | {ui} |",
        )
    lines.append("")
    lines.append("Full index: `docs/API_LINKS.md` in the project root.")
    return "\n".join(lines)
