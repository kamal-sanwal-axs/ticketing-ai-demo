from __future__ import annotations

import json
from dataclasses import dataclass

from apex_rag_demo.config import DATA_DIR, KB_PATH

KB_MFE_PATH = DATA_DIR / "kb_mfe_flows.json"


@dataclass
class KbChunk:
    id: str
    text: str


def load_kb() -> list[KbChunk]:
    raw = json.loads(KB_PATH.read_text(encoding="utf-8"))
    chunks = [KbChunk(id=item["id"], text=item["text"]) for item in raw]
    try:
        from apex_rag_demo.rag.openapi_kb import load_openapi_kb_chunks

        extra = load_openapi_kb_chunks()
        seen = {c.id for c in chunks}
        for c in extra:
            if c.id not in seen:
                chunks.append(c)
                seen.add(c.id)
    except Exception:
        pass
    if KB_MFE_PATH.is_file():
        try:
            extra_mfe = json.loads(KB_MFE_PATH.read_text(encoding="utf-8"))
            seen = {c.id for c in chunks}
            for item in extra_mfe:
                cid = str(item.get("id") or "")
                if cid and cid not in seen:
                    chunks.append(KbChunk(id=cid, text=str(item.get("text") or "")))
                    seen.add(cid)
        except Exception:
            pass
    try:
        from apex_rag_demo.testrail_catalog import catalog_kb_texts

        seen = {c.id for c in chunks}
        for cid, text in catalog_kb_texts():
            if cid not in seen and text.strip():
                chunks.append(KbChunk(id=cid, text=text))
                seen.add(cid)
    except Exception:
        pass
    return chunks
