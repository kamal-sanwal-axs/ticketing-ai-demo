"""Run script plugins in a hardened Docker container or isolated subprocess."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from apex_rag_demo.config import PLUGIN_SCRIPT_TIMEOUT_SEC
from apex_rag_demo.plugins.sandbox import SandboxViolation
from apex_rag_demo.plugins.sandbox_backend import (
    configured_docker_image,
    configured_sandbox_backend,
    resolve_sandbox_backend,
)


def _docker_build_hint() -> str:
    return (
        "Build the worker image: docker compose build plugin-worker "
        f"(image: {configured_docker_image() or 'ticketing-ai-demo-plugin-worker:local'})"
    )


def _run_subprocess(job: dict[str, Any]) -> Any:
    proc = subprocess.run(
        [sys.executable, "-m", "apex_rag_demo.plugins.worker_runner"],
        input=json.dumps(job),
        capture_output=True,
        text=True,
        timeout=PLUGIN_SCRIPT_TIMEOUT_SEC + 2,
        check=False,
        start_new_session=True,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        stderr = (proc.stderr or "").strip()[:500]
        raise SandboxViolation(f"Worker process failed: {stderr or proc.returncode}")
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise SandboxViolation(f"Invalid worker output: {proc.stdout[:200]}") from exc
    if not payload.get("ok"):
        raise SandboxViolation(str(payload.get("error") or "Worker error"))
    return payload.get("result")


def _docker_run_argv(image: str) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-i",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=16m",
        "--security-opt",
        "no-new-privileges",
        "--cap-drop",
        "ALL",
        "--pids-limit",
        "64",
        "--memory",
        "256m",
        "--cpus",
        "1",
        "--user",
        "nobody",
        image,
    ]


def _run_docker(job: dict[str, Any]) -> Any:
    image = configured_docker_image()
    if not image:
        raise SandboxViolation("PLUGIN_DOCKER_IMAGE is not set")
    proc = subprocess.run(
        _docker_run_argv(image),
        input=json.dumps(job),
        capture_output=True,
        text=True,
        timeout=PLUGIN_SCRIPT_TIMEOUT_SEC + 15,
        check=False,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        raise SandboxViolation((proc.stderr or "docker worker failed")[:500])
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise SandboxViolation(f"Invalid docker worker output: {proc.stdout[:200]}") from exc
    if not payload.get("ok"):
        raise SandboxViolation(str(payload.get("error") or "Docker worker error"))
    return payload.get("result")


def run_isolated_script(
    *,
    language: str,
    source: str,
    entry: str,
    payload: dict[str, Any],
) -> Any:
    job = {
        "language": language,
        "source": source,
        "entry": entry,
        "input": payload,
    }
    configured = configured_sandbox_backend()
    backend = resolve_sandbox_backend()

    if configured == "docker" and backend != "docker":
        raise SandboxViolation(
            f"PLUGIN_SANDBOX_BACKEND=docker but worker image is not available. {_docker_build_hint()}",
        )

    if backend == "docker":
        return _run_docker(job)
    if backend == "inprocess":
        from apex_rag_demo.plugins.worker_runner import run_job

        out = run_job(job)
        if not out.get("ok"):
            raise SandboxViolation(str(out.get("error")))
        return out.get("result")
    return _run_subprocess(job)
