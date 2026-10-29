"""Fetch APEX OpenAPI specs and write data/kb_openapi.json for Chroma sync."""

from __future__ import annotations

from apex_rag_demo.rag._deps_check import require_rag_cli_deps

require_rag_cli_deps(chroma=False)

from apex_rag_demo.rag.openapi_kb import build_openapi_kb_chunks, write_openapi_kb_file


def main() -> None:
    chunks = build_openapi_kb_chunks(fetch_live=True)
    path = write_openapi_kb_file(chunks)
    print(f"Wrote {len(chunks)} OpenAPI KB chunks to {path}")
    print("Run: python -m apex_rag_demo.rag.sync_index --store chroma")


if __name__ == "__main__":
    main()
