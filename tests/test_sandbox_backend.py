import pytest

from apex_rag_demo.plugins.sandbox_backend import (
    docker_image_available,
    resolve_sandbox_backend,
    sandbox_status,
)


def test_resolve_subprocess_when_configured(monkeypatch):
    monkeypatch.setenv("PLUGIN_SANDBOX_BACKEND", "subprocess")
    assert resolve_sandbox_backend() == "subprocess"


def test_resolve_inprocess_when_configured(monkeypatch):
    monkeypatch.setenv("PLUGIN_SANDBOX_BACKEND", "inprocess")
    assert resolve_sandbox_backend() == "inprocess"


def test_sandbox_status_shape():
    st = sandbox_status()
    assert "effective_backend" in st
    assert "true_sandbox" in st
    assert st["isolation"] in ("container", "subprocess", "inprocess")


@pytest.mark.skipif(
    not docker_image_available("ticketing-ai-demo-plugin-worker:local"),
    reason="plugin-worker image not built",
)
def test_script_runs_in_docker_when_image_ready(monkeypatch):
    monkeypatch.setenv("PLUGIN_SANDBOX_BACKEND", "auto")
    from apex_rag_demo.plugins.code_sandbox import execute_script_plugin
    from apex_rag_demo.plugins.models import CustomPluginTool

    from apex_rag_demo.plugins.models import PluginParameter

    tool = CustomPluginTool(
        kind="script",
        id="docker-echo",
        name="Echo",
        language="javascript",
        source="function handler(input) { return { ok: true, n: input.n }; }\n",
        parameters=[PluginParameter(name="n", type="integer", required=True)],
    )
    out = execute_script_plugin(tool, {"n": 7}, dry_run=False)
    assert out["script"]["isolation"] == "container"
    assert out["result"]["n"] == 7
