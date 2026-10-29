"""Pytest hooks shared across the suite."""


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    from apex_rag_demo.rag.embeddings import shutdown_embedding_workers

    shutdown_embedding_workers()
