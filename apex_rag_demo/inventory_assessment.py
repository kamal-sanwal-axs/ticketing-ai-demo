from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.config import APEX_EVENTS_BASE_URL, APEX_INVENTORY_BASE_URL
from apex_rag_demo.event_list import event_state_label, unwrap_event_payload
from apex_rag_demo.inventory_display import _dict_values, _price_code_lookup, _publish_zone_for_id

_PRICE_CODE_SETUP_RE = re.compile(
    r"("
    r"\bprice\s*codes?\b.*\b(setup|set\s*up|configured|available|defined)\b|"
    r"\b(do we|have we|is there|are there).*\bprice\s*codes?\b|"
    r"\bprice\s*code\s+setup\b|"
    r"\b(show|list|what)\b.*\bprice\s*codes?\b"
    r")",
    re.I,
)


def looks_like_price_code_setup_question(bare_question: str) -> bool:
    return bool(_PRICE_CODE_SETUP_RE.search(bare_question))


def _citation(label: str, href: str, status: str) -> dict[str, str]:
    return {"label": label, "href": href, "status": status}


def _publish_data_error(fetch_errors: list[str]) -> str | None:
    for err in fetch_errors:
        if "publish-data" in err:
            return err
    return None


def build_inventory_assessment(
    event_payload: dict[str, Any] | None,
    inventory_payload: dict[str, Any] | None,
    event_id: str,
) -> dict[str, Any]:
    """
    Deterministic summary from events-api + inventory-api responses only.
    """
    ev = unwrap_event_payload(event_payload or {})
    lifecycle = event_state_label(ev) if ev else "—"
    inv = inventory_payload or {}
    fetch_errors = [str(e) for e in (inv.get("_fetch_errors") or [])]

    citations: list[dict[str, str]] = [
        _citation(
            f"events-api GET /{event_id}",
            f"{APEX_EVENTS_BASE_URL}/{event_id}",
            "used for event lifecycle",
        ),
    ]

    primary = inv.get("primary") if isinstance(inv.get("primary"), dict) else None
    zone = (primary or {}).get("zone") if isinstance((primary or {}).get("zone"), dict) else {}
    zone_id = str(zone.get("id") or "").strip()
    pl_count = len(_dict_values((primary or {}).get("priceLevels")))

    if primary:
        citations.append(
            _citation(
                f"inventory-api GET /events/{event_id}/zones/primary",
                f"{APEX_INVENTORY_BASE_URL}/events/{event_id}/zones/primary",
                "ok" if zone_id else "no primary zone in body",
            ),
        )
    else:
        citations.append(
            _citation(
                f"inventory-api GET /events/{event_id}/zones/primary",
                f"{APEX_INVENTORY_BASE_URL}/events/{event_id}/zones/primary",
                "failed or empty",
            ),
        )

    cv_id = str(zone.get("clientVenueId") or ev.get("clientVenueId") or "").strip()
    publish_url = f"{APEX_INVENTORY_BASE_URL}/events/{event_id}/zones/publish-data"
    if cv_id:
        publish_url += f"?client_venue_id={cv_id}"

    publish = inv.get("publish") if isinstance(inv.get("publish"), dict) else None
    publish_err = _publish_data_error(fetch_errors)
    if publish is not None:
        pub_status = "ok"
    elif publish_err:
        pub_status = publish_err
    else:
        pub_status = "not called or empty"
    citations.append(
        _citation(
            f"inventory-api GET /events/{event_id}/zones/publish-data",
            publish_url,
            pub_status,
        ),
    )

    paragraphs: list[str] = []
    lifecycle_note = (
        f"Event lifecycle from events-api: **{lifecycle}**."
        if lifecycle != "—"
        else "Event lifecycle from events-api: not returned in payload."
    )
    paragraphs.append(lifecycle_note.replace("**", ""))

    if not zone_id:
        paragraphs.append(
            "Admissions inventory: no primary zone returned from GET …/zones/primary. "
            "Price codes cannot be configured without a zone.",
        )
        return {
            "headline": "No primary inventory zone",
            "verdict": "no_inventory",
            "paragraphs": paragraphs,
            "citations": citations,
        }

    paragraphs.append(
        f"Primary zone “{zone.get('description') or 'Admissions'}” ({zone_id}): "
        f"{pl_count} price level(s) on the primary snapshot.",
    )

    publish_zone = _publish_zone_for_id(publish, zone_id)
    pc_by_id = _price_code_lookup(publish)
    zone_pc_ids = set((publish_zone or {}).get("priceCodes") or {})
    pc_rows: list[str] = []
    for pc_id, pc in sorted(pc_by_id.items(), key=lambda x: (x[1].get("description") or x[0]).lower()):
        if zone_pc_ids and pc_id not in zone_pc_ids:
            continue
        name = pc.get("description") or pc_id
        pc_rows.append(str(name))

    chart = (publish_zone or {}).get("priceChart") or []
    chart_count = len([e for e in chart if isinstance(e, dict)])

    if publish is None:
        paragraphs.append(
            "Price codes: **cannot confirm** — publish-data was not available. "
            f"{publish_err or 'The inventory API did not return publish-data for this event.'} "
            "Price levels and sections from the primary zone may still exist; price codes and "
            "published price charts require a successful publish-data response.",
        )
        verdict = "unknown"
    elif not pc_rows:
        paragraphs.append(
            "Price codes: **no** price codes on the primary zone in publish-data "
            f"(price chart entries: {chart_count}).",
        )
        verdict = "no"
    else:
        paragraphs.append(
            f"Price codes: **yes** — {len(pc_rows)} on the primary zone: {', '.join(pc_rows)}. "
            f"Price chart rows (code × level): {chart_count}.",
        )
        verdict = "yes"

    headline = {
        "yes": "Price codes are configured (publish-data)",
        "no": "No price codes on publish-data",
        "unknown": "Price code status unknown (publish-data unavailable)",
        "no_inventory": "No admissions inventory",
    }.get(verdict, "Inventory assessment")

    clean = [p.replace("**", "") for p in paragraphs]
    return {
        "headline": headline,
        "verdict": verdict,
        "paragraphs": clean,
        "citations": citations,
    }


def format_price_code_setup_answer(
    event_payload: dict[str, Any] | None,
    inventory_payload: dict[str, Any] | None,
    event_id: str,
) -> str:
    assessment = build_inventory_assessment(event_payload, inventory_payload, event_id)
    lines = [assessment["headline"], ""]
    lines.extend(assessment["paragraphs"])
    lines.append("")
    lines.append("Sources:")
    for cite in assessment["citations"]:
        lines.append(f"- {cite['label']} ({cite['status']})")
    return "\n".join(lines)
