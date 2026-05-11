"""Admin-Endpunkte fuer GPS-Diagnose und Reset.

- GET  /api/admin/gps/log       : letzte MQTT-GPS-Events (Topic, Route, applied_to)
- GET  /api/admin/gps/status    : Devices + Generators mit aktueller GPS-Position +
                                  Zeit seit letztem Update (Alters-Check)
- POST /api/admin/gps/reset     : setzt latitude/longitude/last_gps_update zurueck
                                  (optional Filter: ?older_than_hours=N oder
                                  ?device_id=<id>). Damit kann der Admin alte
                                  Spread-Reste entfernen.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/gps", tags=["admin-gps"])
security = HTTPBearer()

db = None
decode_jwt_token = None


def init_admin_gps_routes(_db, _decode_jwt_token):
    global db, decode_jwt_token
    db = _db
    decode_jwt_token = _decode_jwt_token


async def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_jwt_token(credentials.credentials)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin-Berechtigung erforderlich")
    return user


@router.get("/log")
async def gps_log(limit: int = Query(default=200, ge=1, le=1000),
                  admin: dict = Depends(require_admin)):
    """Liste der letzten verarbeiteten MQTT-GPS-Events."""
    events = await db.mqtt_gps_log.find({}, {"_id": 0}).sort("ts", -1).to_list(limit)
    routes = {}
    for e in events:
        r = e.get("route", "?")
        routes[r] = routes.get(r, 0) + 1
    return {
        "count": len(events),
        "by_route": routes,
        "events": events,
    }


@router.get("/status")
async def gps_status(admin: dict = Depends(require_admin)):
    """Liefert pro Device + Generator die letzte GPS-Position + Alter."""
    now = datetime.now(timezone.utc)

    def _age_hours(ts_str):
        if not ts_str:
            return None
        try:
            t = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return round((now - t).total_seconds() / 3600.0, 1)
        except Exception:
            return None

    devices = await db.devices.find(
        {"device_type": {"$in": ["stromerzeuger", "lichtmast", "messkoffer", "kirmeskiste"]}},
        {"_id": 0, "id": 1, "serial_number": 1, "user_field": 1, "device_type": 1,
         "latitude": 1, "longitude": 1, "last_gps_update": 1, "dse_module_uid": 1,
         "status": 1}
    ).to_list(2000)
    dev_rows = []
    for d in devices:
        dev_rows.append({
            "kind": "device",
            "id": d.get("id"),
            "serial_number": d.get("serial_number"),
            "name": d.get("user_field") or d.get("serial_number"),
            "device_type": d.get("device_type"),
            "status": d.get("status"),
            "latitude": d.get("latitude"),
            "longitude": d.get("longitude"),
            "last_gps_update": d.get("last_gps_update"),
            "age_hours": _age_hours(d.get("last_gps_update")),
            "dse_module_uid": d.get("dse_module_uid"),
        })

    gens = await db.generators.find(
        {}, {"_id": 0, "id": 1, "serial_number": 1, "name": 1,
             "latitude": 1, "longitude": 1, "last_gps_update": 1,
             "dse_mqtt_topic_prefix": 1, "dse_module_uid": 1, "is_active": 1}
    ).to_list(2000)
    gen_rows = []
    for g in gens:
        if g.get("is_active") is False:
            continue
        gen_rows.append({
            "kind": "generator",
            "id": g.get("id"),
            "serial_number": g.get("serial_number"),
            "name": g.get("name"),
            "latitude": g.get("latitude"),
            "longitude": g.get("longitude"),
            "last_gps_update": g.get("last_gps_update"),
            "age_hours": _age_hours(g.get("last_gps_update")),
            "dse_mqtt_topic_prefix": g.get("dse_mqtt_topic_prefix"),
            "dse_module_uid": g.get("dse_module_uid"),
        })

    # Zaehle Devices/Generators ohne dse_module_uid (= koennen kein GPS via Module-UID-Match bekommen)
    missing_uid_devices = [d for d in dev_rows if not d.get("dse_module_uid")]
    missing_uid_generators = [g for g in gen_rows if not g.get("dse_module_uid")]

    # Duplikate erkennen: identische lat/lng auf mehreren Devices/Generators
    coord_counts = {}
    for r in dev_rows + gen_rows:
        if r.get("latitude") is not None and r.get("longitude") is not None:
            key = f"{round(r['latitude'], 5)},{round(r['longitude'], 5)}"
            coord_counts[key] = coord_counts.get(key, 0) + 1
    duplicates = {k: v for k, v in coord_counts.items() if v > 1}

    return {
        "devices": dev_rows,
        "generators": gen_rows,
        "duplicate_coords": duplicates,
        "missing_dse_module_uid": {
            "devices": [{"id": d["id"], "serial_number": d.get("serial_number"), "name": d.get("name")} for d in missing_uid_devices],
            "generators": [{"id": g["id"], "serial_number": g.get("serial_number"), "name": g.get("name")} for g in missing_uid_generators],
            "total": len(missing_uid_devices) + len(missing_uid_generators),
        },
    }


@router.post("/reset")
async def gps_reset(older_than_hours: Optional[int] = Query(default=None, ge=0),
                    device_id: Optional[str] = Query(default=None),
                    generator_id: Optional[str] = Query(default=None),
                    all: bool = Query(default=False),
                    admin: dict = Depends(require_admin)):
    """Setzt latitude/longitude/last_gps_update fuer ausgewaehlte Geraete/Generatoren zurueck.

    Aufrufmuster:
      ?all=true                      -> alle Devices+Generators
      ?older_than_hours=24           -> nur Eintraege mit last_gps_update aelter als 24h
      ?device_id=xyz                 -> gezielt ein Device
      ?generator_id=xyz              -> gezielt einen Generator
    """
    if not (all or older_than_hours is not None or device_id or generator_id):
        raise HTTPException(
            status_code=400,
            detail="Mindestens einer dieser Parameter erforderlich: all, older_than_hours, device_id, generator_id"
        )

    unset_fields = {"latitude": "", "longitude": "", "last_gps_update": ""}
    dev_filter = {}
    gen_filter = {}

    if device_id:
        dev_filter["id"] = device_id
    if generator_id:
        gen_filter["id"] = generator_id

    if older_than_hours is not None and not (device_id or generator_id):
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=older_than_hours)).isoformat()
        # OR: last_gps_update fehlt oder ist alt
        age_clause = {"$or": [
            {"last_gps_update": {"$exists": False}},
            {"last_gps_update": {"$lt": cutoff}},
        ]}
        dev_filter = {**dev_filter, **age_clause}
        gen_filter = {**gen_filter, **age_clause}

    if all and not (device_id or generator_id):
        # Alle aktiven, ohne Datumsfilter
        dev_filter = {}
        gen_filter = {}

    devices_reset = 0
    generators_reset = 0

    if not generator_id:
        res_dev = await db.devices.update_many(dev_filter, {"$unset": unset_fields})
        devices_reset = res_dev.modified_count
    if not device_id:
        res_gen = await db.generators.update_many(gen_filter, {"$unset": unset_fields})
        generators_reset = res_gen.modified_count

    logger.info(
        f"GPS-Reset durch {admin.get('email','?')}: devices={devices_reset}, generators={generators_reset} "
        f"(filter: older_than_hours={older_than_hours}, device_id={device_id}, generator_id={generator_id}, all={all})"
    )

    return {
        "message": "GPS zurueckgesetzt",
        "devices_reset": devices_reset,
        "generators_reset": generators_reset,
        "hint": "Beim naechsten echten GPS-Telegramm aus MQTT/Pi-Ingest wird die korrekte Position pro Geraet neu geschrieben.",
    }
