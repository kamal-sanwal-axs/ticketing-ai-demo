from apex_rag_demo.fan_purchase import (
    format_fan_purchase_guidance,
    looks_like_fan_purchase_request,
)
from apex_rag_demo.response_formatters import format_explain


def test_buy_seat_detected():
    assert looks_like_fan_purchase_request("can you buy one seat for me")


def test_explain_not_create_org():
    text = format_explain([], "can you buy one seat for me")
    assert "Create organization" not in text
    assert "fan" in text.lower() or "purchase" in text.lower()
    assert "POST /v1/orders" in format_fan_purchase_guidance()
