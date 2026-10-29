#!/usr/bin/env python3
"""Execute sandbox job.json in an isolated workspace (Docker entrypoint)."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

WORK = Path("/tmp/sandbox-work")
OUT = Path("/workspace/out")


def _fail(msg: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "result.json").write_text(json.dumps({"ok": False, "error": msg}), encoding="utf-8")
    sys.exit(1)


def _write_ok(payload: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "result.json").write_text(json.dumps({"ok": True, **payload}, default=str), encoding="utf-8")


def _install_pip(packages: list[str]) -> None:
    if not packages:
        return
    target = WORK / ".pydeps"
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--target", str(target), *packages],
        check=True,
        timeout=120,
    )
    sys.path.insert(0, str(target))


def _run_python(job: dict[str, Any], files: dict[str, str]) -> None:
    entry = str(job.get("entry") or "handler")
    payload = job.get("input") if isinstance(job.get("input"), dict) else {}
    _install_pip(list(job.get("pip_packages") or []))

    src_dir = WORK / "python"
    src_dir.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (src_dir / name).write_text(body, encoding="utf-8")

    main_path = src_dir / "main.py"
    if main_path.is_file():
        spec = importlib.util.spec_from_file_location("sandbox_main", main_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "handler") and callable(mod.handler):
                result = mod.handler(payload)
                _write_ok({"runtime": "python", "result": result})
                return
        _fail("main.py must define handler(input)")

    handler_src = files.get(f"{entry}.py") or files.get("handler.py")
    if not handler_src:
        _fail(f"Missing Python entry {entry}.py or main.py")

    glb: dict[str, Any] = {"__builtins__": __builtins__}
    loc: dict[str, Any] = {}
    exec(handler_src, glb, loc)
    fn = loc.get(entry) or loc.get("handler")
    if not callable(fn):
        _fail(f"Entry function {entry} not found")
    result = fn(payload)
    _write_ok({"runtime": "python", "result": result})


def _run_react(job: dict[str, Any], files: dict[str, str]) -> None:
    payload = job.get("input") if isinstance(job.get("input"), dict) else {}
    shell = Path("/opt/react-shell")
    build_dir = WORK / "react"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    shutil.copytree(shell, build_dir)

    npm_packages = list(job.get("npm_packages") or [])
    if npm_packages:
        subprocess.run(
            ["npm", "install", "--no-audit", "--no-fund", *npm_packages],
            cwd=build_dir,
            check=True,
            timeout=180,
        )

    src = build_dir / "src"
    for name, body in files.items():
        if not name.endswith((".jsx", ".js", ".tsx", ".ts", ".css")):
            continue
        (src / name).write_text(body, encoding="utf-8")

    input_js = build_dir / "public" / "input.js"
    input_js.parent.mkdir(parents=True, exist_ok=True)
    input_js.write_text(
        f"window.__SANDBOX_INPUT__ = {json.dumps(payload)};\n",
        encoding="utf-8",
    )
    index_html = build_dir / "index.html"
    html = index_html.read_text(encoding="utf-8")
    if "input.js" not in html:
        html = html.replace("</head>", '    <script src="/input.js"></script>\n  </head>')
        index_html.write_text(html, encoding="utf-8")

    subprocess.run(["npm", "run", "build"], cwd=build_dir, check=True, timeout=180, env=os.environ | {"CI": "true"})
    dist = build_dir / "dist"
    index = dist / "index.html"
    if not index.is_file():
        _fail("React build did not produce index.html")
    html_out = index.read_text(encoding="utf-8")
    _write_ok({"runtime": "react", "html": html_out, "result": {"built": True}})


def main() -> None:
    job_path = Path("/workspace/in/job.json")
    if not job_path.is_file():
        _fail("job.json missing")
    try:
        job = json.loads(job_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _fail(f"invalid job.json: {exc}")

    files_raw = job.get("files")
    if not isinstance(files_raw, dict):
        _fail("files must be an object")
    files = {str(k): str(v) for k, v in files_raw.items()}

    runtime = str(job.get("runtime") or "python").lower()
    WORK.mkdir(parents=True, exist_ok=True)
    try:
        if runtime == "react":
            _run_react(job, files)
        elif runtime == "python":
            _run_python(job, files)
        else:
            _fail(f"unsupported runtime: {runtime}")
    except subprocess.CalledProcessError as exc:
        _fail(f"subprocess failed: {exc}")
    except Exception as exc:  # noqa: BLE001
        _fail(str(exc)[:800])


if __name__ == "__main__":
    main()
