"""Load the domain ontology used to constrain GLiNER / graph extraction."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from apex_rag_demo.config import KG_ONTOLOGY_PATH


def _ontology_file() -> Path:
    path = Path(KG_ONTOLOGY_PATH)
    if path.is_file():
        return path
    fallback = Path(__file__).resolve().parents[2] / "data" / "kg" / "ontology" / "ticketing_apex.json"
    return fallback


@lru_cache(maxsize=1)
def load_ontology() -> dict[str, Any]:
    path = _ontology_file()
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def entity_type_names() -> frozenset[str]:
    ont = load_ontology()
    names = {str(e.get("name") or "") for e in ont.get("entity_types") or []}
    return frozenset(n for n in names if n)


def relation_type_names() -> frozenset[str]:
    ont = load_ontology()
    names = {str(r.get("name") or "") for r in ont.get("relation_types") or []}
    return frozenset(n for n in names if n)


def gliner_labels() -> list[str]:
    """Lower-case labels passed to GLiNER (mapped to ontology types in post-process)."""
    ont = load_ontology()
    mapping = (ont.get("extraction") or {}).get("gliner_label_map") or {}
    return sorted({str(k).strip() for k in mapping if str(k).strip()})
