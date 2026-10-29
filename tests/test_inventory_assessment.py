from __future__ import annotations

import unittest

from apex_rag_demo.inventory_assessment import (
    build_inventory_assessment,
    looks_like_price_code_setup_question,
)


class InventoryAssessmentTests(unittest.TestCase):
    def test_detects_price_code_setup_question(self) -> None:
        self.assertTrue(looks_like_price_code_setup_question("do we have price code setup for this event"))

    def test_publish_data_missing_means_unknown_verdict(self) -> None:
        eid = "defa7917-1a3f-4717-8328-3278cfa7449b"
        ev = {"id": eid, "state": "Draft", "clientVenueId": "019fcc21-907e-79cf-aae2-287a7d7b26dc"}
        inv = {
            "primary": {
                "zone": {
                    "id": "c5bfc682-ad45-4c76-ab91-8215ead59760",
                    "description": "Admissions",
                    "eventId": eid,
                    "clientVenueId": "019fcc21-907e-79cf-aae2-287a7d7b26dc",
                },
                "priceLevels": {
                    "a": {"id": "a", "description": "GA Floor"},
                    "b": {"id": "b", "description": "GA Balcony"},
                },
            },
            "publish": None,
            "_fetch_errors": [
                f"GET /events/{eid}/zones/publish-data: HTTP 500",
            ],
        }
        result = build_inventory_assessment(ev, inv, eid)
        self.assertEqual(result["verdict"], "unknown")
        self.assertTrue(any("Draft" in p for p in result["paragraphs"]))
        self.assertTrue(any("cannot confirm" in p.lower() for p in result["paragraphs"]))
        self.assertEqual(len(result["citations"]), 3)


if __name__ == "__main__":
    unittest.main()
