from __future__ import annotations

import json
import re
from typing import Any

from apex_rag_demo.config import SANDBOX_MAX_SOURCE_BYTES, SANDBOX_TOOLKIT_ENABLED
from apex_rag_demo.sandbox_toolkit.models import SandboxJob

_SANDBOX_HINT = re.compile(
    r"\b(custom\s+(python|react|chart|viz|visualization|component)|"
    r"sandbox\s+(python|react|tool|code)|"
    r"run\s+(python|react)\s+code|"
    r"build\s+a\s+react\s+chart)\b",
    re.I,
)


def looks_like_sandbox_tool_request(bare_question: str) -> bool:
    if not SANDBOX_TOOLKIT_ENABLED:
        return False
    return bool(_SANDBOX_HINT.search(bare_question))


def _trim_files(files: dict[str, str]) -> dict[str, str]:
    total = sum(len(v) for v in files.values())
    if total <= SANDBOX_MAX_SOURCE_BYTES:
        return files
    raise ValueError(f"Sandbox source exceeds {SANDBOX_MAX_SOURCE_BYTES} bytes")


def parse_sandbox_job_from_llm(data: dict[str, Any]) -> SandboxJob | None:
    action = str(data.get("action") or "").strip().lower()
    if action != "run_sandbox":
        return None
    block = data.get("sandbox")
    if not isinstance(block, dict):
        block = data
    runtime = str(block.get("runtime") or "python").strip().lower()
    if runtime not in ("python", "react"):
        runtime = "python"
    files_raw = block.get("files")
    if not isinstance(files_raw, dict) or not files_raw:
        return None
    files = {str(k): str(v) for k, v in files_raw.items()}
    try:
        files = _trim_files(files)
    except ValueError:
        return None
    pip = block.get("pip_packages") if isinstance(block.get("pip_packages"), list) else []
    npm = block.get("npm_packages") if isinstance(block.get("npm_packages"), list) else []
    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
    return SandboxJob(
        runtime=runtime,  # type: ignore[arg-type]
        files=files,
        input=inp,
        entry=str(block.get("entry") or "handler"),
        pip_packages=[str(x) for x in pip],
        npm_packages=[str(x) for x in npm],
        reason=str(data.get("reason") or block.get("reason") or ""),
    )


def orchestrator_sandbox_catalog_block() -> str:
    return """Sandbox toolkit (Docker, network isolated):
- action run_sandbox when user needs custom Python transform or React UI/chart from api_trace data.
- JSON shape:
  "action": "run_sandbox",
  "sandbox": {
    "runtime": "python" | "react",
    "files": { "main.py": "def handler(input): ..." } OR { "App.jsx": "export default function App({input}){...}" },
    "input": { ... data from api_trace or user ... },
    "pip_packages": [],
    "npm_packages": []
  }
Preinstalled: pandas, numpy, matplotlib, react, react-dom, recharts. Only allowlisted extra pip/npm names."""


def try_sandbox_orchestrator_step(
    question: str,
    *,
    api_trace: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    from apex_rag_demo.response_formatters import strip_ui_region

    bare = strip_ui_region(question)
    if not looks_like_sandbox_tool_request(bare):
        return None
    trace = api_trace or []
    sample_input = {"api_trace": trace[-3:] if trace else [], "question": bare}
    if "react" in bare.lower() or "chart" in bare.lower() or "component" in bare.lower():
        files = {
            "App.jsx": (
                "import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';\n"
                "export default function App({ input }) {\n"
                "  const rows = (input?.api_trace?.[0]?.result?.rows) || "
                "[{ name: 'A', value: 1 }, { name: 'B', value: 2 }];\n"
                "  const data = rows.map((r, i) => ({ name: String(r.name || r.label || i), value: Number(r.value || r.count || 0) }));\n"
                "  return (\n"
                "    <div style={{ padding: 16, fontFamily: 'system-ui' }}>\n"
                "      <h3>Sandbox chart</h3>\n"
                "      <ResponsiveContainer width='100%' height={260}>\n"
                "        <BarChart data={data}><XAxis dataKey='name' /><YAxis /><Tooltip /><Bar dataKey='value' fill='#4a9eff' /></BarChart>\n"
                "      </ResponsiveContainer>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            ),
        }
        job = SandboxJob(runtime="react", files=files, input=sample_input, reason="deterministic_react_chart")
    else:
        files = {
            "main.py": (
                "def handler(input):\n"
                "    trace = input.get('api_trace') or []\n"
                "    return {'trace_steps': len(trace), 'question': input.get('question')}\n"
            ),
        }
        job = SandboxJob(runtime="python", files=files, input=sample_input, reason="deterministic_python")
    return {
        "orchestrator_action": "run_sandbox",
        "intent": "explain",
        "action_plan": job.model_dump(mode="json"),
        "orchestrator_reason": job.reason or "sandbox_tool",
    }


def build_sandbox_display(result: dict[str, Any]) -> dict[str, Any] | None:
    if not result.get("ok"):
        return {
            "type": "article",
            "title": "Sandbox error",
            "level": "error",
            "paragraphs": [str(result.get("error") or "Sandbox failed")],
        }
    if result.get("html"):
        return {
            "type": "sandbox",
            "badge": "sandbox react",
            "title": "Custom React sandbox",
            "subtitle": "Rendered in an isolated Docker container",
            "sandbox_html": result["html"],
        }
    return {
        "type": "article",
        "badge": "sandbox python",
        "title": "Custom Python sandbox result",
        "paragraphs": [json.dumps(result.get("result"), indent=2, default=str)[:4000]],
    }
