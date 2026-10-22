from __future__ import annotations

import json
from dataclasses import dataclass

from apex_rag_demo.config import KB_PATH


@dataclass
class KbChunk:
    id: str
    text: str


def load_kb() -> list[KbChunk]:
    raw = json.loads(KB_PATH.read_text(encoding="utf-8"))
    return [KbChunk(id=item["id"], text=item["text"]) for item in raw]
