from __future__ import annotations

import argparse
import json
import sys

from apex_rag_demo.graph import run_demo
from apex_rag_demo.service_catalog import format_catalog_markdown


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LangGraph RAG demo: local llama.cpp + APEX dev APIs",
    )
    parser.add_argument(
        "--list-services",
        action="store_true",
        help="Print apex-dev API base URLs and OpenAPI swagger links",
    )
    parser.add_argument("question", nargs="?", help="Natural language question")
    parser.add_argument("--json", action="store_true", help="Print full state as JSON")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="POST create requests to apex-admin-api (default: dry-run preview)",
    )
    args = parser.parse_args()

    if args.list_services:
        print(format_catalog_markdown())
        return

    question = args.question or input("Question: ").strip()
    if not question:
        print("Question is required.", file=sys.stderr)
        sys.exit(1)

    state = run_demo(question, execute_writes=args.execute)
    if args.json:
        print(json.dumps(state, indent=2, default=str))
    else:
        print(state["answer"])


if __name__ == "__main__":
    main()
