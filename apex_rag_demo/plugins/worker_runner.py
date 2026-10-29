"""Subprocess entrypoint — user script runs only in this fresh interpreter."""

from __future__ import annotations

import json
import sys
from typing import Any

# ruff: noqa: T201 — CLI worker writes JSON to stdout


def _apply_resource_limits() -> None:
    try:
        import resource

        from apex_rag_demo.config import PLUGIN_SCRIPT_TIMEOUT_SEC

        cpu = max(int(PLUGIN_SCRIPT_TIMEOUT_SEC) + 1, 2)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    except (ImportError, OSError, ValueError):
        pass


def _run_javascript(source: str, entry: str, payload: dict[str, Any]) -> Any:
    import quickjs

    ctx = quickjs.Context()
    ctx.eval(source)
    input_json = json.dumps(payload)
    expr = (
        f"(function() {{"
        f"const __input = {input_json};"
        f"const __fn = {entry};"
        f"if (typeof __fn !== 'function') throw new Error('entry must be a function');"
        f"const __out = __fn(__input);"
        f"return JSON.stringify(__out === undefined ? null : __out);"
        f"}})()"
    )
    raw = ctx.eval(expr)
    if raw is None or raw == "null":
        return None
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _run_python(source: str, entry: str, payload: dict[str, Any]) -> Any:
    from RestrictedPython import compile_restricted_exec
    from RestrictedPython.Guards import guarded_iter_unpack_sequence, safe_globals, safer_getattr

    compiled = compile_restricted_exec(source, filename="<plugin>")
    if compiled.errors:
        raise RuntimeError("; ".join(compiled.errors))
    if compiled.code is None:
        raise RuntimeError("Python compile failed")
    glb = safe_globals.copy()
    glb["_getattr_"] = safer_getattr
    glb["_getitem_"] = lambda obj, index: obj[index]
    glb["_getiter_"] = lambda it: iter(it)
    glb["_iter_unpack_"] = guarded_iter_unpack_sequence
    loc: dict[str, Any] = {}
    exec(compiled.code, glb, loc)
    handler = loc.get(entry) or glb.get(entry)
    if not callable(handler):
        raise RuntimeError(f"Entry function '{entry}' not found")
    return handler(payload)


def run_job(job: dict[str, Any]) -> dict[str, Any]:
    language = job.get("language")
    source = job.get("source") or ""
    entry = job.get("entry") or "handler"
    payload = job.get("input") if isinstance(job.get("input"), dict) else {}
    if language == "javascript":
        result = _run_javascript(source, entry, payload)
    elif language == "python":
        result = _run_python(source, entry, payload)
    else:
        raise ValueError(f"Unsupported language: {language}")
    return {"ok": True, "result": result}


def main() -> None:
    _apply_resource_limits()
    try:
        raw = sys.stdin.read()
        job = json.loads(raw) if raw.strip() else {}
        out = run_job(job)
    except Exception as exc:  # noqa: BLE001 — worker boundary
        out = {"ok": False, "error": str(exc)}
    sys.stdout.write(json.dumps(out, default=str))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
