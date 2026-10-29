from __future__ import annotations

from typing import Any

ZONE_TYPE_LABELS = {
    0: "Admissions",
    1: "Parking",
    2: "Priority entry",
    3: "Venue experience",
    "Admissions": "Admissions",
    "Parking": "Parking",
    "PriorityEntry": "Priority entry",
    "VenueExperience": "Venue experience",
}


def _dash(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def _zone_type_label(raw: Any) -> str:
    if raw is None:
        return "—"
    if isinstance(raw, str):
        return ZONE_TYPE_LABELS.get(raw, raw)
    return ZONE_TYPE_LABELS.get(raw, str(raw))


def _dict_values(block: Any) -> list[dict[str, Any]]:
    if not isinstance(block, dict):
        return []
    return [v for v in block.values() if isinstance(v, dict)]


def _publish_zone_for_id(publish: dict[str, Any] | None, zone_id: str | None) -> dict[str, Any] | None:
    if not publish or not zone_id:
        return None
    for z in publish.get("zones") or []:
        if isinstance(z, dict) and str(z.get("id") or "") == zone_id:
            return z
    return None


def _price_level_lookup(publish: dict[str, Any] | None, primary: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for pl in _dict_values((primary or {}).get("priceLevels")):
        pid = str(pl.get("id") or "")
        if pid:
            out[pid] = pl
    for pid, pl in ((publish or {}).get("priceLevels") or {}).items():
        if isinstance(pl, dict):
            out[str(pid)] = {**out.get(str(pid), {}), **pl, "id": str(pl.get("id") or pid)}
    return out


def _price_code_lookup(publish: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for pid, pc in ((publish or {}).get("priceCodes") or {}).items():
        if isinstance(pc, dict):
            out[str(pid)] = {**pc, "id": str(pc.get("id") or pid)}
    return out


def seating_selection_summary(zone: dict[str, Any] | None, publish_zone: dict[str, Any] | None) -> list[dict[str, str]]:
    mmc = _dash((zone or {}).get("mmcMapId") or (publish_zone or {}).get("mmcMapId"))
    pick_a_seat = mmc != "—"
    return [
        {"label": "Best available", "value": "Yes (default admissions flow)"},
        {
            "label": "Pick a seat",
            "value": "Available (MMC map configured)" if pick_a_seat else "Not available (no MMC map on zone)",
        },
        {"label": "MMC map ID", "value": mmc},
    ]


def build_inventory_sections(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return [{"title": "Inventory", "paragraphs": ["No inventory data in response."]}]

    primary = payload.get("primary") if isinstance(payload.get("primary"), dict) else payload
    if primary is payload and "zone" not in primary and "zones" not in primary:
        primary = None

    publish = payload.get("publish") if isinstance(payload.get("publish"), dict) else None
    ticket_types_payload = payload.get("ticketTypes") if isinstance(payload.get("ticketTypes"), dict) else None
    fetch_errors = payload.get("_fetch_errors") or []

    zone_wrapper = (primary or {}).get("zone") if primary else None
    zone = zone_wrapper if isinstance(zone_wrapper, dict) else {}
    zone_id = str(zone.get("id") or "—")
    publish_zone = _publish_zone_for_id(publish, zone_id if zone_id != "—" else None)

    pl_by_id = _price_level_lookup(publish, primary)
    pc_by_id = _price_code_lookup(publish)

    sections: list[dict[str, Any]] = []

    zone_fields = [
        {"label": "Zone", "value": _dash(zone.get("description"))},
        {"label": "Zone ID", "value": zone_id},
        {"label": "Zone type", "value": _zone_type_label(zone.get("type"))},
        {"label": "Event ID", "value": _dash(zone.get("eventId") or payload.get("eventId"))},
        {"label": "Client venue ID", "value": _dash(zone.get("clientVenueId"))},
        {"label": "Venue capacity", "value": _dash(zone.get("venueCapacity"))},
    ]
    sections.append({"title": "Primary admissions zone", "fields": zone_fields})
    sections.append(
        {
            "title": "Seat selection (inventory)",
            "fields": seating_selection_summary(zone, publish_zone),
            "paragraphs": [
                "Best available uses status codes and quantity grids; pick a seat requires an MMC map on the zone "
                "(same signal as B2B sales: mmcMapId on the offer/zone).",
            ],
        },
    )

    pl_rows: list[dict[str, str]] = []
    seen_pl: set[str] = set()
    for pl in _dict_values((primary or {}).get("priceLevels")):
        pid = str(pl.get("id") or "")
        if pid:
            seen_pl.add(pid)
        pl_rows.append(
            {
                "description": _dash(pl.get("description")),
                "color": _dash(pl.get("color")),
                "priceLevelId": _dash(pl.get("id")),
            },
        )
    for pid, pl in sorted(pl_by_id.items(), key=lambda x: (x[1].get("description") or x[0]).lower()):
        if pid in seen_pl:
            continue
        pl_rows.append(
            {
                "description": _dash(pl.get("description")),
                "color": _dash(pl.get("color")),
                "priceLevelId": pid,
            },
        )
    if pl_rows:
        sections.append(
            {
                "title": "Price levels",
                "table": {
                    "columns": [
                        {"key": "description", "label": "Price level"},
                        {"key": "color", "label": "Color", "cellType": "color"},
                        {"key": "priceLevelId", "label": "Price level ID"},
                    ],
                    "rows": pl_rows,
                },
            },
        )

    section_rows: list[dict[str, str]] = []
    ga_sections = (publish_zone or {}).get("gaSections") or []
    primary_sections = _dict_values((primary or {}).get("sections"))
    ga_by_id = {str(s.get("id") or ""): s for s in ga_sections if isinstance(s, dict)}

    for sec in primary_sections:
        sid = str(sec.get("id") or "—")
        ga = ga_by_id.get(sid) or {}
        pl_id = str(sec.get("priceLevelId") or ga.get("priceLevelId") or "")
        pl = pl_by_id.get(pl_id) or {}
        section_rows.append(
            {
                "sectionName": _dash(ga.get("sectionName") or pl.get("description")),
                "priceLevel": _dash(pl.get("description")),
                "color": _dash(pl.get("color")),
                "sectionId": sid,
                "priceLevelId": pl_id or "—",
            },
        )
    for ga in ga_sections:
        if not isinstance(ga, dict):
            continue
        sid = str(ga.get("id") or "")
        if any(r.get("sectionId") == sid for r in section_rows):
            continue
        pl_id = str(ga.get("priceLevelId") or "")
        pl = pl_by_id.get(pl_id) or {}
        section_rows.append(
            {
                "sectionName": _dash(ga.get("sectionName")),
                "priceLevel": _dash(pl.get("description")),
                "color": _dash(pl.get("color")),
                "sectionId": sid or "—",
                "priceLevelId": pl_id or "—",
            },
        )
    if section_rows:
        sections.append(
            {
                "title": "Sections",
                "table": {
                    "columns": [
                        {"key": "sectionName", "label": "Section"},
                        {"key": "priceLevel", "label": "Price level"},
                        {"key": "color", "label": "Color", "cellType": "color"},
                        {"key": "sectionId", "label": "Section ID"},
                        {"key": "priceLevelId", "label": "Price level ID"},
                    ],
                    "rows": section_rows,
                },
            },
        )

    zone_pc_ids = set((publish_zone or {}).get("priceCodes") or {})
    pc_rows: list[dict[str, str]] = []
    for pc_id, pc in sorted(pc_by_id.items(), key=lambda x: (x[1].get("description") or x[0]).lower()):
        if zone_pc_ids and pc_id not in zone_pc_ids:
            continue
        pc_rows.append(
            {
                "description": _dash(pc.get("description")),
                "type": _dash(pc.get("type")),
                "pricingMode": _dash(pc.get("pricingMode")),
                "priceCodeId": pc_id,
            },
        )
    if not pc_rows and publish is None and fetch_errors:
        pub_err = next((str(e) for e in fetch_errors if "publish-data" in str(e)), None)
        paras = [
            "Price codes and price charts come from inventory-api GET …/zones/publish-data. "
            "That call failed for this event, so price codes cannot be listed here.",
            "Primary zone data (price levels, sections) may still be shown above.",
        ]
        if pub_err:
            paras.append(f"API error: {pub_err}")
        sections.append(
            {
                "title": "Inventory price codes",
                "paragraphs": paras,
            },
        )
    elif pc_rows:
        sections.append(
            {
                "title": "Inventory price codes",
                "table": {
                    "columns": [
                        {"key": "description", "label": "Price code"},
                        {"key": "type", "label": "Type"},
                        {"key": "pricingMode", "label": "Pricing mode"},
                        {"key": "priceCodeId", "label": "Price code ID"},
                    ],
                    "rows": pc_rows,
                },
            },
        )

    chart_rows: list[dict[str, str]] = []
    for entry in (publish_zone or {}).get("priceChart") or []:
        if not isinstance(entry, dict):
            continue
        pl_id = str(entry.get("priceLevelId") or "")
        pc_id = str(entry.get("priceCodeId") or "")
        pl = pl_by_id.get(pl_id) or {}
        pc = pc_by_id.get(pc_id) or {}
        chart_rows.append(
            {
                "priceCode": _dash(pc.get("description")),
                "priceLevel": _dash(pl.get("description")),
                "color": _dash(pl.get("color")),
                "price": _dash(entry.get("price")),
                "priceCodeId": pc_id or "—",
                "priceLevelId": pl_id or "—",
            },
        )
    if chart_rows:
        sections.append(
            {
                "title": "Price chart (price code × price level)",
                "table": {
                    "columns": [
                        {"key": "priceCode", "label": "Price code"},
                        {"key": "priceLevel", "label": "Price level"},
                        {"key": "color", "label": "Color", "cellType": "color"},
                        {"key": "price", "label": "Price"},
                        {"key": "priceCodeId", "label": "Price code ID"},
                        {"key": "priceLevelId", "label": "Price level ID"},
                    ],
                    "rows": chart_rows,
                },
            },
        )

    tt_rows: list[dict[str, str]] = []
    for tt in (ticket_types_payload or {}).get("ticketTypes") or []:
        if not isinstance(tt, dict):
            continue
        status = tt.get("statusCode") or {}
        status_label = status.get("description") if isinstance(status, dict) else "—"
        chart_bits: list[str] = []
        for entry in tt.get("priceChart") or []:
            if not isinstance(entry, dict):
                continue
            pl_id = str(entry.get("priceLevelId") or "")
            pl = pl_by_id.get(pl_id) or {}
            chart_bits.append(f"{pl.get('description') or pl_id}: {entry.get('price')}")
        tt_rows.append(
            {
                "name": _dash(tt.get("name")),
                "category": _dash(tt.get("category")),
                "statusCode": _dash(status_label),
                "priceChart": "; ".join(chart_bits) if chart_bits else "—",
                "minQty": _dash(tt.get("minQty")),
                "maxQty": _dash(tt.get("maxQty")),
                "offerId": _dash(tt.get("id")),
            },
        )
    if tt_rows:
        sections.append(
            {
                "title": "Ticket types (offers)",
                "table": {
                    "columns": [
                        {"key": "name", "label": "Ticket type"},
                        {"key": "category", "label": "Category"},
                        {"key": "statusCode", "label": "Status code"},
                        {"key": "priceChart", "label": "Prices by price level"},
                        {"key": "minQty", "label": "Min qty"},
                        {"key": "maxQty", "label": "Max qty"},
                        {"key": "offerId", "label": "Offer ID"},
                    ],
                    "rows": tt_rows,
                },
            },
        )

    if fetch_errors:
        from apex_rag_demo.clients.apex_inventory import INVENTORY_AUTH_SCOPE_MESSAGE

        notes = list(fetch_errors)
        if payload.get("_inventory_auth_scope_limited"):
            notes = [e for e in notes if e != INVENTORY_AUTH_SCOPE_MESSAGE]
            notes.insert(0, INVENTORY_AUTH_SCOPE_MESSAGE)
        sections.append(
            {
                "title": "Inventory access",
                "paragraphs": notes,
            },
        )

    if len(sections) <= 2 and not pl_rows and not section_rows:
        sections.append(
            {
                "title": "Inventory",
                "paragraphs": [
                    "No primary zone, price levels, or sections returned for this event. "
                    "The event may not have admissions inventory configured yet.",
                ],
            },
        )

    return sections
