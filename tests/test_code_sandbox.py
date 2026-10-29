import pytest

from apex_rag_demo.plugins.code_sandbox import execute_script_plugin
from apex_rag_demo.plugins.models import CustomPluginTool, PluginParameter
from apex_rag_demo.plugins.sandbox import SandboxViolation


def test_javascript_handler():
    tool = CustomPluginTool(
        kind="script",
        id="js-sum",
        name="Sum",
        language="javascript",
        source=(
            "function handler(input) {\n"
            "  return { sum: input.a + input.b };\n"
            "}\n"
        ),
        parameters=[
            PluginParameter(name="a", type="integer", required=True),
            PluginParameter(name="b", type="integer", required=True),
        ],
    )
    out = execute_script_plugin(tool, {"a": 2, "b": 3}, dry_run=False)
    assert out["result"]["sum"] == 5


def test_python_handler():
    tool = CustomPluginTool(
        kind="script",
        id="py-upper",
        name="Upper",
        language="python",
        source=(
            "def handler(input):\n"
            "    name = str(input.get('name') or '')\n"
            "    return {'upper': name.upper()}\n"
        ),
        parameters=[PluginParameter(name="name", type="string", required=True)],
    )
    out = execute_script_plugin(tool, {"name": "apex"}, dry_run=False)
    assert out["result"]["upper"] == "APEX"


def test_script_blocks_import():
    tool = CustomPluginTool(
        kind="script",
        id="bad-js",
        name="Bad",
        language="javascript",
        source="import fs from 'fs'; function handler(i) { return i; }",
    )
    with pytest.raises(SandboxViolation, match="disallowed"):
        execute_script_plugin(tool, {}, dry_run=True)


def test_invoke_routes_script_kind():
    from apex_rag_demo.plugins.sandbox import execute_plugin

    tool = CustomPluginTool(
        kind="script",
        id="js-echo",
        name="Echo",
        language="javascript",
        source="function handler(input) { return input; }\n",
        parameters=[PluginParameter(name="x", type="string", required=True)],
    )
    out = execute_plugin(tool, {"x": "ok"}, dry_run=False)
    assert out["result"]["x"] == "ok"
