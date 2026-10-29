from __future__ import annotations

from apex_rag_demo.sandbox_toolkit.orchestrator import (
    looks_like_sandbox_tool_request,
    parse_sandbox_job_from_llm,
)


def test_looks_like_sandbox():
    assert looks_like_sandbox_tool_request("build a react chart from the data")
    assert not looks_like_sandbox_tool_request("list all events")


def test_parse_sandbox_job():
    job = parse_sandbox_job_from_llm(
        {
            "action": "run_sandbox",
            "sandbox": {
                "runtime": "python",
                "files": {"main.py": "def handler(input):\n    return input\n"},
                "input": {"x": 1},
            },
        },
    )
    assert job is not None
    assert job.runtime == "python"
    assert "main.py" in job.files
