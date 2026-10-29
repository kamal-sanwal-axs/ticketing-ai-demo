from apex_rag_demo.event_lifecycle_filters import (
    apply_lifecycle_filter_to_payload,
    question_requests_onsale_filter,
)


def test_onsale_question_detected():
    assert question_requests_onsale_filter("how many events on sale")
    assert not question_requests_onsale_filter("list all client venues")


def test_onsale_filter_reduces_rows():
    payload = {
        "events": [
            {"id": "a", "name": "Live Show", "status": "OnSale"},
            {"id": "b", "name": "Draft", "status": "Draft"},
        ],
    }
    out = apply_lifecycle_filter_to_payload(payload, lifecycle_filter="onsale")
    assert len(out["events"]) == 1
    assert out["_lifecycle_filter"]["_matched"] == 1
    assert out["_lifecycle_filter"]["_total_before_filter"] == 2
