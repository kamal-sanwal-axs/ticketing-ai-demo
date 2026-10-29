"""Resolve script-plugin isolation backend (container vs subprocess)."""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from typing import Literal

SandboxBackend = Literal["docker", "subprocess", "inprocess"]

_DEFAULT_DOCKER_IMAGE = "ticketing-ai-demo-plugin-worker:local"


def configured_sandbox_backend() -> str:
    return os.getenv("PLUGIN_SANDBOX_BACKEND", "auto").strip().lower()


def configured_docker_image() -> str:
    return os.getenv("PLUGIN_DOCKER_IMAGE", _DEFAULT_DOCKER_IMAGE).strip()


@lru_cache(maxsize=1)
def docker_cli_available() -> bool:
    return shutil.which("docker") is not None


@lru_cache(maxsize=8)
def docker_image_available(image: str) -> bool:
    if not image or not docker_cli_available():
        return False
    proc = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return proc.returncode == 0


def resolve_sandbox_backend() -> SandboxBackend:
    """Pick how script plugins run. ``auto`` prefers Docker when the worker image exists."""
    raw = configured_sandbox_backend()
    if raw == "inprocess":
        return "inprocess"
    if raw == "subprocess":
        return "subprocess"
    if raw == "docker":
        return "docker"
    # auto (default)
    image = configured_docker_image()
    if image and docker_image_available(image):
        return "docker"
    return "subprocess"


def sandbox_isolation_label(backend: SandboxBackend) -> str:
    if backend == "docker":
        return "container"
    if backend == "inprocess":
        return "inprocess"
    return "subprocess"


def sandbox_status() -> dict[str, object]:
    backend = resolve_sandbox_backend()
    image = configured_docker_image()
    return {
        "configured_backend": configured_sandbox_backend(),
        "effective_backend": backend,
        "isolation": sandbox_isolation_label(backend),
        "docker_cli": docker_cli_available(),
        "docker_image": image or None,
        "docker_image_ready": bool(image and docker_image_available(image)),
        "true_sandbox": backend == "docker",
    }
