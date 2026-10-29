"""Neo4j driver helpers for hybrid Chroma + knowledge-graph memory."""

from __future__ import annotations

from typing import Any

from apex_rag_demo.config import (
    KG_NEO4J_ENABLED,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
)


def neo4j_configured() -> bool:
    return KG_NEO4J_ENABLED and bool(NEO4J_URI) and bool(NEO4J_PASSWORD)


def get_driver() -> Any:
    if not neo4j_configured():
        raise RuntimeError("Neo4j is disabled or NEO4J_URI / NEO4J_PASSWORD is missing")
    from neo4j import GraphDatabase

    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def verify_connectivity() -> tuple[bool, str]:
    if not neo4j_configured():
        return False, "KG_NEO4J_ENABLED=false or credentials unset"
    try:
        driver = get_driver()
        driver.verify_connectivity()
        driver.close()
        return True, "ok"
    except ModuleNotFoundError as exc:
        if exc.name == "neo4j":
            return (
                False,
                "Python package 'neo4j' not installed — use project .venv: "
                "source .venv/bin/activate && pip install -r requirements.txt",
            )
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def run_cypher(query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    driver = get_driver()
    try:
        with driver.session() as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]
    finally:
        driver.close()
