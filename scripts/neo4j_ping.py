#!/usr/bin/env python3
"""Check Neo4j Bolt connectivity (after docker compose up -d neo4j)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from apex_rag_demo.rag.kg_ontology import entity_type_names, load_ontology
from apex_rag_demo.rag.neo4j_client import verify_connectivity


def main() -> None:
    ont = load_ontology()
    print(f"Ontology: {ont.get('domain')} v{ont.get('version')} — entity types: {len(entity_type_names())}")
    ok, msg = verify_connectivity()
    if ok:
        print("Neo4j: connected", msg)
        return
    print("Neo4j: not available —", msg, file=sys.stderr)
    print(
        "Hint: source .venv/bin/activate && pip install -r requirements.txt",
        file=sys.stderr,
    )
    print("      docker compose up -d neo4j && KG_NEO4J_ENABLED=true in .env", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
