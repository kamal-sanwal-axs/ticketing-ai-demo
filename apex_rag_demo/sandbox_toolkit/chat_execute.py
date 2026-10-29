from __future__ import annotations

from typing import Any

from apex_rag_demo.sandbox_toolkit.docker_runner import SandboxToolkitError, run_sandbox_job
from apex_rag_demo.sandbox_toolkit.models import SandboxJob, SandboxResult


def execute_sandbox_from_plan(action_plan: dict[str, Any]) -> dict[str, Any]:
    job = SandboxJob.model_validate(action_plan)
    try:
        out: SandboxResult = run_sandbox_job(job)
    except SandboxToolkitError as exc:
        return {"ok": False, "error": str(exc), "runtime": job.runtime}
    return out.model_dump(mode="json")
