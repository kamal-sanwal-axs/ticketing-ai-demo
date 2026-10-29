import pytest

from apex_rag_demo.plugins.models import CustomPluginTool, PluginParameter
from apex_rag_demo.plugins.registry import delete_plugin, get_plugin, list_plugins, save_plugin
from apex_rag_demo.plugins.sandbox import SandboxViolation, execute_plugin
from apex_rag_demo.runtime.graph_runtime import init_runtime, shutdown_runtime


@pytest.fixture
def runtime_store():
    init_runtime()
    yield
    shutdown_runtime()


def test_sandbox_blocks_disallowed_host():
    tool = CustomPluginTool(
        id="evil",
        name="Evil",
        method="GET",
        url_template="https://evil.example.com/steal",
    )
    with pytest.raises(SandboxViolation, match="allowlist"):
        execute_plugin(tool, {}, dry_run=True)


def test_sandbox_dry_run_substitution():
    tool = CustomPluginTool(
        id="orders",
        name="Orders",
        method="GET",
        url_template="https://api.apex-dev.axsdevops.io/search/v1/orders/{orderId}",
        parameters=[PluginParameter(name="orderId", type="string", required=True)],
    )
    result = execute_plugin(tool, {"orderId": "ABC123"}, dry_run=True)
    assert result["dry_run"] is True
    assert "ABC123" in result["request"]["url"]


def test_plugin_registry_roundtrip(runtime_store):
    tool = CustomPluginTool(
        id="demo-tool",
        name="Demo",
        method="GET",
        url_template="https://api.apex-dev.axsdevops.io/search/swagger/v1/swagger.json",
    )
    save_plugin("user:test", tool)
    loaded = get_plugin("user:test", "demo-tool")
    assert loaded is not None
    assert loaded.name == "Demo"
    assert any(p.id == "demo-tool" for p in list_plugins("user:test"))
    assert delete_plugin("user:test", "demo-tool")
    assert get_plugin("user:test", "demo-tool") is None
