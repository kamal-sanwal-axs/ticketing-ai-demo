"""Sync kb.json (and related sources) into Neo4j knowledge graph."""

from __future__ import annotations

import argparse

from apex_rag_demo.rag.kg_sync import sync_kb_to_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync KB text into Neo4j (GLiNER + regex)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract and merge even when KB fingerprint is unchanged",
    )
    args = parser.parse_args()
    result = sync_kb_to_graph(force=args.force)
    if result.get("skipped"):
        print(f"Neo4j KG unchanged ({result['chunks']} KB chunks). Use --force to re-sync.")
        return
    print(
        f"Neo4j KG synced: {result['chunks']} chunks, "
        f"{result['entities']} entity mentions (fp {result.get('fingerprint')}…).",
    )


if __name__ == "__main__":
    main()
