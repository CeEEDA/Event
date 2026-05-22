"""
Engine-State-Tracker: erkennt Motor-Start/-Stop-Transitions und schreibt
automatisch Einträge in `deployment_history`, damit die Einsatzhistorie
eines Generators ohne manuellen Eingriff entsteht.

Wird von beiden Telemetrie-Pfaden aufgerufen:
  - MQTT-Service (`_process_message` in mqtt_service.py)  - Pi-Ingest (`POST /api/generators/ingest` in routes/generators.py)
"""
from __future__ import annotations
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Entfernung zwischen 2 GPS-Punkten in km (Haversine)."""
    R = 6371.0
    a = math.radians(lat1); b = math.radians(lat2)
    da = math.radians(lat2 - lat1); db = math.radians(lng2 - lng1)
    x = math.sin(da / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(db / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


async def _find_active_order_for_generator(
    db, generator_id: str, lat: Optional[float], lng: Optional[float]
) -> Optional[dict]:
    """Findet den aktuell aktiven Auftrag eines Generators.

    Priorität:
      1. Manuelle Zuordnung (order_settings.manual_generator_ids)
      2. GPS-Radius-Match (lat/lng innerhalb center_lat/lng + radius_km)

    Bei Treffer wird (order_pk, order_label) zurueckgegeben. Sonst None.

    Aufträge, deren end_date in der Vergangenheit liegt, werden ignoriert -
    sonst werden Maschinen die nach Auftrags-Ende noch laufen weiter dem
    erledigten Auftrag zugeschrieben.
    """
    today_iso = datetime.now(timezone.utc).date().isoformat()

    async def _order_is_active(order_pk) -> bool:
        if order_pk is None:
            return True
        doc = await db.orders_cache.find_one(
            {"$or": [{"primary_key": order_pk}, {"primary_key": str(order_pk)}]},
            {"_id": 0, "end_date": 1, "date_end": 1}
        )
        if not doc:
            return True  # Kein Cache-Eintrag -> nicht abblocken
        end_raw = doc.get("end_date") or doc.get("date_end")
        if not end_raw:
            return True
        # end_raw kommt typisch als "YYYY-MM-DD" rein
        try:
            return str(end_raw)[:10] >= today_iso
        except Exception:
            return True

    # 1) Manuelle Zuordnung
    manual = await db.order_settings.find_one(
        {"manual_generator_ids": generator_id}, {"_id": 0, "order_pk": 1}
    )
    if manual:
        order_pk = manual.get("order_pk")
        if await _order_is_active(order_pk):
            label = await _resolve_order_label(db, order_pk)
            return {"order_pk": order_pk, "order_label": label, "match_via": "manual"}

    # 2) GPS-Radius
    if lat is None or lng is None:
        return None
    try:
        lat_f = float(lat); lng_f = float(lng)
    except (TypeError, ValueError):
        return None
    settings_cursor = db.order_settings.find(
        {"center_lat": {"$ne": None}}, {"_id": 0, "order_pk": 1, "center_lat": 1, "center_lng": 1, "radius_km": 1}
    )
    best = None
    async for s in settings_cursor:
        try:
            d = _haversine_km(s["center_lat"], s["center_lng"], lat_f, lng_f)
        except (KeyError, TypeError, ValueError):
            continue
        radius = float(s.get("radius_km") or 5.0)
        if d <= radius:
            # Auftrag-Endedatum pruefen - abgelaufene NICHT mehr matchen
            if not await _order_is_active(s.get("order_pk")):
                continue
            if best is None or d < best["distance"]:
                best = {"order_pk": s.get("order_pk"), "distance": d}
    if best is None:
        return None
    label = await _resolve_order_label(db, best["order_pk"])
    return {"order_pk": best["order_pk"], "order_label": label, "match_via": "radius", "distance_km": round(best["distance"], 2)}


async def _resolve_order_label(db, order_pk) -> str:
    """Holt den Anzeigenamen eines Auftrags fuer die Einsatzhistorie."""
    doc = await db.orders_cache.find_one(
        {"primary_key": order_pk}, {"_id": 0, "name": 1, "title": 1, "event": 1}
    ) or await db.orders_cache.find_one(
        {"primary_key": str(order_pk)}, {"_id": 0, "name": 1, "title": 1, "event": 1}
    )
    if doc:
        return doc.get("name") or doc.get("title") or doc.get("event") or f"Auftrag #{order_pk}"
    return f"Auftrag #{order_pk}"


async def _resolve_generator_meta(db, generator_id: str) -> dict:
    """Holt Name + GPS eines Generators (aus generators ODER devices)."""
    gen = await db.generators.find_one(
        {"id": generator_id},
        {"_id": 0, "name": 1, "serial_number": 1, "latitude": 1, "longitude": 1}
    )
    if gen:
        return {
            "name": gen.get("serial_number") or gen.get("name") or "",
            "lat": gen.get("latitude"),
            "lng": gen.get("longitude"),
        }
    if generator_id.startswith("dev-"):
        dev = await db.devices.find_one(
            {"id": generator_id[4:]},
            {"_id": 0, "user_field": 1, "model": 1, "serial_number": 1,
             "latest_snapshot.gps_lat": 1, "latest_snapshot.gps_lng": 1}
        )
        if dev:
            snap = dev.get("latest_snapshot") or {}
            return {
                "name": dev.get("user_field") or dev.get("model") or dev.get("serial_number") or "",
                "lat": snap.get("gps_lat"),
                "lng": snap.get("gps_lng"),
            }
    return {"name": "", "lat": None, "lng": None}


async def track_engine_transition(
    db,
    generator_id: str,
    new_engine_running: bool,
    telemetry_data: dict,
    old_snapshot: dict,
    timestamp: str,
) -> Optional[str]:
    """Wird aufgerufen, wenn engine_running sich zwischen Updates aendert.

    Rueckgabe: 'started' / 'stopped' / None (kein State-Change-Eintrag)
    """
    old_engine = old_snapshot.get("engine_running")
    if old_engine is None and old_snapshot.get("rpm") is not None:
        old_engine = (old_snapshot.get("rpm") or 0) > 0
    if old_engine == new_engine_running:
        return None  # Keine Aenderung

    if new_engine_running:
        # Engine START
        return await _open_deployment(db, generator_id, telemetry_data, timestamp)
    # Engine STOP
    return await _close_deployment(db, generator_id, telemetry_data, timestamp)


async def _open_deployment(db, generator_id: str, telemetry: dict, timestamp: str) -> str:
    # Falls bereits ein offener Eintrag existiert -> nichts tun (Duplikate vermeiden)
    existing_open = await db.deployment_history.find_one(
        {"generator_id": generator_id, "stopped_at": None,
         "auto_assigned": {"$ne": True}},  # auto_assigned-Stubs sind keine echten Starts
        {"_id": 0, "id": 1}
    )
    if existing_open:
        logger.debug(f"deployment_history: offener Eintrag existiert bereits fuer {generator_id}")
        return "already_open"

    meta = await _resolve_generator_meta(db, generator_id)
    order = await _find_active_order_for_generator(db, generator_id, meta["lat"], meta["lng"])
    if order:
        order_pk = order["order_pk"]
        order_label = order["order_label"]
        notes = f"Motor-Start erkannt (Zuordnung: {order['match_via']})"
    else:
        order_pk = None
        order_label = _format_standalone_label(meta)
        notes = "Motor-Start erkannt (kein zugeordneter Auftrag)"

    doc = {
        "id": str(uuid.uuid4()),
        "order_pk": order_pk,
        "order_label": order_label,
        "generator_id": generator_id,
        "generator_name": meta["name"],
        "started_at": timestamp,
        "stopped_at": None,
        "operating_hours": None,
        "hours_run_start": telemetry.get("hours_run"),
        "hours_run_end": None,
        "kwh_start": telemetry.get("energy_kwh"),
        "kwh_end": None,
        "faults": None,
        "notes": notes,
        "auto_assigned": False,
        "source": "engine_transition",
        "created_at": timestamp,
        "created_by": "System (Engine-Tracker)",
    }
    await db.deployment_history.insert_one(doc)
    logger.info(f"deployment_history START: gen={generator_id} order={order_pk} ({order_label})")
    return "started"


async def _close_deployment(db, generator_id: str, telemetry: dict, timestamp: str) -> str:
    open_entry = await db.deployment_history.find_one(
        {"generator_id": generator_id, "stopped_at": None,
         "source": "engine_transition"},
        {"_id": 0, "id": 1, "started_at": 1, "hours_run_start": 1, "kwh_start": 1}
    )
    if not open_entry:
        logger.debug(f"deployment_history: kein offener Eintrag zum Schliessen fuer {generator_id}")
        return "no_open"

    # operating_hours: bevorzugt Differenz von hours_run, sonst Wand-Uhr-Differenz
    operating_hours = None
    h_now = telemetry.get("hours_run")
    h_start = open_entry.get("hours_run_start")
    if isinstance(h_now, (int, float)) and isinstance(h_start, (int, float)):
        operating_hours = round(max(0.0, float(h_now) - float(h_start)), 2)
    else:
        try:
            t_start = datetime.fromisoformat(open_entry["started_at"])
            if t_start.tzinfo is None:
                t_start = t_start.replace(tzinfo=timezone.utc)
            t_end = datetime.fromisoformat(timestamp)
            if t_end.tzinfo is None:
                t_end = t_end.replace(tzinfo=timezone.utc)
            operating_hours = round((t_end - t_start).total_seconds() / 3600.0, 2)
        except (ValueError, TypeError, KeyError):
            pass

    kwh_end = telemetry.get("energy_kwh")
    update = {
        "stopped_at": timestamp,
        "operating_hours": operating_hours,
        "hours_run_end": h_now,
        "kwh_end": kwh_end,
    }
    await db.deployment_history.update_one(
        {"id": open_entry["id"]}, {"$set": update}
    )
    logger.info(f"deployment_history STOP: gen={generator_id} dauer={operating_hours}h")
    return "stopped"


def _format_standalone_label(meta: dict) -> str:
    if meta.get("lat") is not None and meta.get("lng") is not None:
        return f"Standort {meta['lat']:.4f}, {meta['lng']:.4f}"
    return "Ohne Auftragsbezug"


def extract_engine_state(telemetry: dict) -> Optional[bool]:
    """Bestimmt engine_running aus telemetry, mit rpm-Fallback. None wenn unbekannt."""
    er = telemetry.get("engine_running")
    if isinstance(er, bool):
        return er
    rpm = telemetry.get("rpm")
    if isinstance(rpm, (int, float)):
        return rpm > 0
    return None
