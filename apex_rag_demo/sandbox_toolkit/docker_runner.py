from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from apex_rag_demo.config import (
    SANDBOX_PIP_ALLOWLIST,
    SANDBOX_NPM_ALLOWLIST,
    SANDBOX_TOOLKIT_ENABLED,
    SANDBOX_TOOLKIT_IMAGE,
    SANDBOX_TOOLKIT_TIMEOUT_SEC,
)
from apex_rag_demo.sandbox_toolkit.models import SandboxJob, SandboxResult


class SandboxToolkitError(RuntimeError):
    pass


def _filter_packages(requested: list[str], allowlist: frozenset[str]) -> list[str]:
    out: list[str] = []
    for raw in requested:
        name = raw.strip().split("==")[0].split("[")[0].lower()
        if not name:
            continue
        if name not in allowlist:
            raise SandboxToolkitError(f"Package not allowlisted: {raw}")
        out.append(raw.strip())
    return out


def sandbox_toolkit_status() -> dict[str, Any]:
    image = SANDBOX_TOOLKIT_IMAGE
    docker_ok = bool(shutil.which("docker"))
    image_ok = False
    if docker_ok and image:
        proc = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        image_ok = proc.returncode == 0
    return {
        "enabled": SANDBOX_TOOLKIT_ENABLED,
        "image": image,
        "docker_cli": docker_ok,
        "image_ready": image_ok,
        "pip_allowlist": sorted(SANDBOX_PIP_ALLOWLIST),
        "npm_allowlist": sorted(SANDBOX_NPM_ALLOWLIST),
    }


def run_sandbox_job(job: SandboxJob) -> SandboxResult:
    if not SANDBOX_TOOLKIT_ENABLED:
        return SandboxResult(ok=False, error="SANDBOX_TOOLKIT_ENABLED=false")

    image = SANDBOX_TOOLKIT_IMAGE
    if not image:
        return SandboxResult(ok=False, error="SANDBOX_TOOLKIT_IMAGE not set")
    if not shutil.which("docker"):
        return SandboxResult(ok=False, error="docker CLI not found")

    pip = _filter_packages(job.pip_packages, SANDBOX_PIP_ALLOWLIST)
    npm = _filter_packages(job.npm_packages, SANDBOX_NPM_ALLOWLIST)

    payload = {
        "runtime": job.runtime,
        "files": job.files,
        "input": job.input,
        "entry": job.entry,
        "pip_packages": pip,
        "npm_packages": npm,
    }

    with tempfile.TemporaryDirectory(prefix="apex-sandbox-") as tmp:
        in_dir = Path(tmp) / "in"
        out_dir = Path(tmp) / "out"
        in_dir.mkdir()
        out_dir.mkdir()
        (in_dir / "job.json").write_text(json.dumps(payload), encoding="utf-8")

        name = f"sandbox-{uuid.uuid4().hex[:12]}"
        argv = [
            "docker",
            "run",
            "--rm",
            "--name",
            name,
            "--network",
            "none",
            "--memory",
            "768m",
            "--cpus",
            "1.5",
            "--pids-limit",
            "128",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "-v",
            f"{in_dir}:/workspace/in:ro",
            "-v",
            f"{out_dir}:/workspace/out:rw",
            image,
        ]
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=SANDBOX_TOOLKIT_TIMEOUT_SEC + 10,
                check=False,
            )
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)
            return SandboxResult(ok=False, error="sandbox container timed out", container_id=name)

        result_path = out_dir / "result.json"
        if not result_path.is_file():
            err = (proc.stderr or proc.stdout or "no result.json")[:800]
            return SandboxResult(ok=False, error=err, container_id=name)

        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return SandboxResult(ok=False, error=f"invalid result: {exc}", container_id=name)

        if not data.get("ok"):
            return SandboxResult(
                ok=False,
                error=str(data.get("error") or "sandbox failed"),
                container_id=name,
            )
        return SandboxResult(
            ok=True,
            runtime=str(data.get("runtime") or job.runtime),
            result=data.get("result"),
            html=data.get("html"),
            container_id=name,
        )
