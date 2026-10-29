"""Entity extraction from text (GLiNER + regex fallbacks) for the knowledge graph."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from apex_rag_demo.config import KG_GLINER_ENABLED, KG_GLINER_MODEL, KG_GLINER_THRESHOLD
from apex_rag_demo.rag.kg_ontology import gliner_labels, load_ontology

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
)
_API_PATH_RE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[a-zA-Z0-9_./{}-]+)|"
    r"\b(/(?:v1|v2)/[a-zA-Z0-9_./{}-]+)\b",
)


@dataclass(frozen=True)
class ExtractedEntity:
    entity_type: str
    text: str
    start: int = 0
    end: int = 0
    score: float = 1.0

    def canonical_key(self) -> str:
        raw = self.text.strip()
        if self.entity_type == "Event" and _UUID_RE.fullmatch(raw):
            return f"Event:{raw.lower()}"
        if self.entity_type == "ApiEndpoint":
            norm = re.sub(r"\s+", " ", raw.upper().strip())
            return f"ApiEndpoint:{hashlib.sha256(norm.encode()).hexdigest()[:24]}"
        norm = re.sub(r"\s+", " ", raw.lower().strip())
        digest = hashlib.sha256(f"{self.entity_type}:{norm}".encode()).hexdigest()[:20]
        return f"{self.entity_type}:{digest}"


def _map_gliner_label(label: str) -> str | None:
    ont = load_ontology()
    mapping = (ont.get("extraction") or {}).get("gliner_label_map") or {}
    key = label.strip().lower()
    if key in mapping:
        return str(mapping[key])
    for gl, ont_type in mapping.items():
        if gl.lower() == key:
            return str(ont_type)
    return None


@lru_cache(maxsize=1)
def _gliner_model() -> Any | None:
    if not KG_GLINER_ENABLED:
        return None
    try:
        from gliner import GLiNER

        return GLiNER.from_pretrained(KG_GLINER_MODEL)
    except Exception:
        return None


def _extract_gliner(text: str) -> list[ExtractedEntity]:
    model = _gliner_model()
    if model is None or not text.strip():
        return []
    labels = gliner_labels()
    if not labels:
        return []
    try:
        raw = model.predict_entities(text, labels, threshold=KG_GLINER_THRESHOLD)
    except Exception:
        return []
    out: list[ExtractedEntity] = []
    for item in raw:
        label = str(item.get("label") or "")
        ont_type = _map_gliner_label(label)
        if not ont_type:
            continue
        span = str(item.get("text") or "").strip()
        if not span:
            continue
        out.append(
            ExtractedEntity(
                entity_type=ont_type,
                text=span,
                start=int(item.get("start") or 0),
                end=int(item.get("end") or 0),
                score=float(item.get("score") or 0.0),
            ),
        )
    return out


def _extract_regex(text: str) -> list[ExtractedEntity]:
    out: list[ExtractedEntity] = []
    for match in _UUID_RE.finditer(text):
        out.append(ExtractedEntity(entity_type="Event", text=match.group(0)))
    for match in _API_PATH_RE.finditer(text):
        span = match.group(0).strip()
        if span.startswith("/"):
            span = f"GET {span}"
        out.append(ExtractedEntity(entity_type="ApiEndpoint", text=span))
    return out


def extract_entities(text: str) -> list[ExtractedEntity]:
    """Deduplicate by canonical_key, prefer higher GLiNER score."""
    merged: dict[str, ExtractedEntity] = {}
    for ent in _extract_regex(text) + _extract_gliner(text):
        key = ent.canonical_key()
        prev = merged.get(key)
        if prev is None or ent.score > prev.score:
            merged[key] = ent
    return list(merged.values())


def lookup_terms(question: str, session_focus: dict[str, Any] | None = None) -> list[str]:
    """Terms for graph lookup: ids from focus, UUIDs, and GLiNER spans."""
    terms: list[str] = []
    focus = session_focus or {}
    for key in ("eventId", "clientVenueId", "organizationId"):
        val = str(focus.get(key) or "").strip()
        if val:
            terms.append(val)
    label = str(focus.get("eventLabel") or "").strip()
    if label and len(label) >= 3:
        terms.append(label[:120])
    for ent in extract_entities(question):
        if ent.text and len(ent.text.strip()) >= 2:
            terms.append(ent.text.strip()[:200])
    seen: set[str] = set()
    unique: list[str] = []
    for t in terms:
        low = t.lower()
        if low in seen:
            continue
        seen.add(low)
        unique.append(t)
    return unique[:12]
