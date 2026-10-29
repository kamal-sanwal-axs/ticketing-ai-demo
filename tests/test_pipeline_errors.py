import httpx

from apex_rag_demo.pipeline_errors import explain_network_failure, format_debug_curl


def test_format_debug_curl_redacts_bearer():
    curl = format_debug_curl(
        "POST",
        "http://localhost:8081/v1/embeddings",
        headers={"Authorization": "Bearer secret-token", "Content-Type": "application/json"},
        json_body={"input": ["hi"]},
    )
    assert "secret-token" not in curl
    assert "Bearer ***" in curl
    assert "8081" in curl


def test_explain_network_failure_includes_request():
    req = httpx.Request("GET", "http://localhost:8002/api/v2/heartbeat")
    exc = httpx.ConnectError("[Errno 61] Connection refused", request=req)
    failure = explain_network_failure(exc, phase="langgraph")
    assert failure.code == "network_unreachable"
    assert failure.endpoint == "http://localhost:8002/api/v2/heartbeat"
    assert failure.debug_curl and "curl" in failure.debug_curl
    assert failure.component == "chroma"
