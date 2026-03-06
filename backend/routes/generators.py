from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
import uuid
import secrets
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generators", tags=["generators"])
security = HTTPBearer()

# Will be set from server.py
db = None
decode_jwt_token = None
get_current_user = None
require_admin = None


def init_generator_routes(_db, _decode_jwt_token, _get_current_user, _require_admin):
    global db, decode_jwt_token, get_current_user, require_admin
    db = _db
    decode_jwt_token = _decode_jwt_token
    get_current_user = _get_current_user
    require_admin = _require_admin


# ============== Models ==============

class GeneratorCreate(BaseModel):
    name: str
    serial_number: str
    model: str = "DSE8610MK2"
    location_name: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    dse_module_type: str = "DSE890"
    assigned_customer_id: Optional[str] = None
    notes: str = ""


class GeneratorUpdate(BaseModel):
    name: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    assigned_customer_id: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class TelemetryPayload(BaseModel):
    api_key: str
    timestamp: Optional[str] = None
    voltage_l1: Optional[float] = None
    voltage_l2: Optional[float] = None
    voltage_l3: Optional[float] = None
    current_l1: Optional[float] = None
    current_l2: Optional[float] = None
    current_l3: Optional[float] = None
    frequency: Optional[float] = None
    power_kw: Optional[float] = None
    power_kva: Optional[float] = None
    power_kvar: Optional[float] = None
    power_factor: Optional[float] = None
    load_percent: Optional[float] = None
    rpm: Optional[float] = None
    oil_pressure: Optional[float] = None
    coolant_temp: Optional[float] = None
    fuel_level: Optional[float] = None
    battery_voltage: Optional[float] = None
    hours_run: Optional[float] = None
    engine_running: Optional[bool] = None
    mode: Optional[str] = None
    alarms: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None


class AlarmAcknowledge(BaseModel):
    pass


# ============== Helper ==============

async def get_user_from_credentials(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_jwt_token(credentials.credentials)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    return user


async def require_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await get_user_from_credentials(credentials)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin-Berechtigung erforderlich")
    return user


async def get_authenticated_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return await get_user_from_credentials(credentials)


# ============== Generator CRUD (Admin) ==============

@router.post("")
async def create_generator(data: GeneratorCreate, admin: dict = Depends(require_admin_user)):
    existing = await db.generators.find_one({"serial_number": data.serial_number}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Seriennummer bereits vorhanden")

    gen_id = str(uuid.uuid4())
    api_key = f"dse_{secrets.token_hex(24)}"

    gen_doc = {
        "id": gen_id,
        "name": data.name,
        "serial_number": data.serial_number,
        "model": data.model,
        "location_name": data.location_name,
        "latitude": data.latitude,
        "longitude": data.longitude,
        "dse_module_type": data.dse_module_type,
        "assigned_customer_id": data.assigned_customer_id,
        "notes": data.notes,
        "api_key": api_key,
        "status": "offline",
        "is_active": True,
        "last_seen": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.generators.insert_one(gen_doc)

    result = {k: v for k, v in gen_doc.items() if k != "_id"}
    return result


@router.get("")
async def list_generators(user: dict = Depends(get_authenticated_user)):
    if user["role"] == "admin":
        generators = await db.generators.find({}, {"_id": 0}).to_list(1000)
    else:
        # Check generator_monitoring permissions
        apps = user.get("apps", {})
        gm = apps.get("generator_monitoring", {})

        if not gm.get("enabled", False):
            # Fallback: check if user has assigned generators
            generators = await db.generators.find(
                {"assigned_customer_id": user["id"], "is_active": True}, {"_id": 0}
            ).to_list(1000)
        elif gm.get("access_all", False):
            generators = await db.generators.find({"is_active": True}, {"_id": 0}).to_list(1000)
        else:
            # Only specific generators
            allowed_ids = gm.get("generator_ids", [])
            if allowed_ids:
                generators = await db.generators.find(
                    {"id": {"$in": allowed_ids}, "is_active": True}, {"_id": 0}
                ).to_list(1000)
            else:
                generators = []

    # P1: Filter out generators whose matching device is "ausser_betrieb"
    out_of_service_serials = set()
    oos_devices = await db.devices.find(
        {"status": "ausser_betrieb"}, {"_id": 0, "serial_number": 1}
    ).to_list(2000)
    for d in oos_devices:
        out_of_service_serials.add(d.get("serial_number", ""))
    if out_of_service_serials:
        generators = [g for g in generators if g.get("serial_number") not in out_of_service_serials]

    # Strip api_key for non-admins
    if user["role"] != "admin":
        for g in generators:
            g.pop("api_key", None)

    # Attach latest telemetry and service warning for each generator
    for g in generators:
        latest = await db.generator_telemetry.find_one(
            {"generator_id": g["id"]},
            {"_id": 0},
            sort=[("timestamp", -1)]
        )
        g["latest_telemetry"] = latest

        # P4: Check for upcoming maintenance via device cross-reference
        device = await db.devices.find_one(
            {"serial_number": g.get("serial_number")}, {"_id": 0}
        )
        if device and device.get("next_maintenance"):
            from datetime import datetime as dt
            try:
                next_maint = dt.fromisoformat(device["next_maintenance"])
                days_until = (next_maint - dt.now(timezone.utc).replace(tzinfo=None)).days
                if days_until <= 30:
                    g["maintenance_warning"] = True
                    g["maintenance_due_days"] = days_until
                    g["next_maintenance_date"] = device["next_maintenance"]
            except (ValueError, TypeError):
                pass

    return generators


@router.get("/{generator_id}")
async def get_generator(generator_id: str, user: dict = Depends(get_authenticated_user)):
    gen = await db.generators.find_one({"id": generator_id}, {"_id": 0})
    if not gen:
        raise HTTPException(status_code=404, detail="Generator nicht gefunden")

    # Check access for non-admins
    if user["role"] != "admin":
        apps = user.get("apps", {})
        gm = apps.get("generator_monitoring", {})
        if gm.get("enabled") and (gm.get("access_all") or generator_id in gm.get("generator_ids", [])):
            pass  # allowed
        elif gen.get("assigned_customer_id") == user["id"]:
            pass  # allowed via assignment
        else:
            raise HTTPException(status_code=403, detail="Keine Berechtigung")

    if user["role"] != "admin":
        gen.pop("api_key", None)

    # Attach latest telemetry
    latest = await db.generator_telemetry.find_one(
        {"generator_id": generator_id},
        {"_id": 0},
        sort=[("timestamp", -1)]
    )
    gen["latest_telemetry"] = latest

    # Attach recent alarms
    alarms = await db.generator_alarms.find(
        {"generator_id": generator_id, "resolved_at": None},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(50)
    gen["active_alarms"] = alarms

    return gen


@router.put("/{generator_id}")
async def update_generator(generator_id: str, data: GeneratorUpdate, admin: dict = Depends(require_admin_user)):
    gen = await db.generators.find_one({"id": generator_id}, {"_id": 0})
    if not gen:
        raise HTTPException(status_code=404, detail="Generator nicht gefunden")

    update_data = {k: v for k, v in data.dict(exclude_unset=True).items() if v is not None}
    if update_data:
        await db.generators.update_one({"id": generator_id}, {"$set": update_data})

    updated = await db.generators.find_one({"id": generator_id}, {"_id": 0})
    return updated


@router.delete("/{generator_id}")
async def delete_generator(generator_id: str, admin: dict = Depends(require_admin_user)):
    result = await db.generators.delete_one({"id": generator_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Generator nicht gefunden")

    await db.generator_telemetry.delete_many({"generator_id": generator_id})
    await db.generator_alarms.delete_many({"generator_id": generator_id})

    return {"message": "Generator gelöscht"}


# ============== Telemetry Ingestion (API Key Auth) ==============

@router.post("/{generator_id}/telemetry")
async def ingest_telemetry(generator_id: str, data: TelemetryPayload):
    gen = await db.generators.find_one({"id": generator_id}, {"_id": 0})
    if not gen:
        raise HTTPException(status_code=404, detail="Generator nicht gefunden")

    if gen.get("api_key") != data.api_key:
        raise HTTPException(status_code=401, detail="Ungültiger API-Key")

    ts = data.timestamp or datetime.now(timezone.utc).isoformat()

    telemetry_doc = {
        "id": str(uuid.uuid4()),
        "generator_id": generator_id,
        "timestamp": ts,
        "voltage_l1": data.voltage_l1,
        "voltage_l2": data.voltage_l2,
        "voltage_l3": data.voltage_l3,
        "current_l1": data.current_l1,
        "current_l2": data.current_l2,
        "current_l3": data.current_l3,
        "frequency": data.frequency,
        "power_kw": data.power_kw,
        "power_kva": data.power_kva,
        "power_kvar": data.power_kvar,
        "power_factor": data.power_factor,
        "load_percent": data.load_percent,
        "rpm": data.rpm,
        "oil_pressure": data.oil_pressure,
        "coolant_temp": data.coolant_temp,
        "fuel_level": data.fuel_level,
        "battery_voltage": data.battery_voltage,
        "hours_run": data.hours_run,
        "engine_running": data.engine_running,
        "mode": data.mode,
        "gps_lat": data.gps_lat,
        "gps_lng": data.gps_lng,
    }

    await db.generator_telemetry.insert_one(telemetry_doc)

    # Update generator status
    status_update = {"last_seen": ts}
    if data.engine_running is not None:
        status_update["status"] = "running" if data.engine_running else "standby"

    # Check for alarms
    if data.alarms:
        status_update["status"] = "alarm"
        for alarm_text in data.alarms:
            alarm_doc = {
                "id": str(uuid.uuid4()),
                "generator_id": generator_id,
                "alarm_text": alarm_text,
                "severity": "alarm",
                "timestamp": ts,
                "acknowledged": False,
                "acknowledged_by": None,
                "resolved_at": None,
            }
            await db.generator_alarms.insert_one(alarm_doc)

    if data.warnings:
        if status_update.get("status") != "alarm":
            status_update["status"] = "warning"
        for warn_text in data.warnings:
            alarm_doc = {
                "id": str(uuid.uuid4()),
                "generator_id": generator_id,
                "alarm_text": warn_text,
                "severity": "warning",
                "timestamp": ts,
                "acknowledged": False,
                "acknowledged_by": None,
                "resolved_at": None,
            }
            await db.generator_alarms.insert_one(alarm_doc)

    await db.generators.update_one({"id": generator_id}, {"$set": status_update})

    return {"message": "Telemetrie empfangen", "id": telemetry_doc["id"]}


# ============== Telemetry Query ==============

@router.get("/{generator_id}/telemetry")
async def get_telemetry(
    generator_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(get_authenticated_user),
):
    gen = await db.generators.find_one({"id": generator_id}, {"_id": 0})
    if not gen:
        raise HTTPException(status_code=404, detail="Generator nicht gefunden")

    if user["role"] == "kunde" and gen.get("assigned_customer_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    telemetry = await db.generator_telemetry.find(
        {"generator_id": generator_id, "timestamp": {"$gte": since}},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(limit)

    return telemetry


# ============== Alarms ==============

@router.get("/{generator_id}/alarms")
async def get_alarms(
    generator_id: str,
    active_only: bool = Query(default=True),
    user: dict = Depends(get_authenticated_user),
):
    gen = await db.generators.find_one({"id": generator_id}, {"_id": 0})
    if not gen:
        raise HTTPException(status_code=404, detail="Generator nicht gefunden")

    if user["role"] == "kunde" and gen.get("assigned_customer_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    query = {"generator_id": generator_id}
    if active_only:
        query["resolved_at"] = None

    alarms = await db.generator_alarms.find(query, {"_id": 0}).sort("timestamp", -1).to_list(200)
    return alarms


@router.post("/{generator_id}/alarms/{alarm_id}/acknowledge")
async def acknowledge_alarm(
    generator_id: str,
    alarm_id: str,
    user: dict = Depends(get_authenticated_user),
):
    if user["role"] == "kunde":
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    result = await db.generator_alarms.update_one(
        {"id": alarm_id, "generator_id": generator_id},
        {"$set": {"acknowledged": True, "acknowledged_by": user["id"]}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alarm nicht gefunden")

    return {"message": "Alarm quittiert"}


@router.post("/{generator_id}/alarms/{alarm_id}/resolve")
async def resolve_alarm(
    generator_id: str,
    alarm_id: str,
    user: dict = Depends(get_authenticated_user),
):
    if user["role"] == "kunde":
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    result = await db.generator_alarms.update_one(
        {"id": alarm_id, "generator_id": generator_id},
        {"$set": {"resolved_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alarm nicht gefunden")

    # Check if there are still active alarms
    active_alarms = await db.generator_alarms.count_documents(
        {"generator_id": generator_id, "resolved_at": None, "severity": "alarm"}
    )
    active_warnings = await db.generator_alarms.count_documents(
        {"generator_id": generator_id, "resolved_at": None, "severity": "warning"}
    )

    if active_alarms == 0 and active_warnings == 0:
        gen = await db.generators.find_one({"id": generator_id}, {"_id": 0})
        if gen and gen.get("status") in ("alarm", "warning"):
            await db.generators.update_one(
                {"id": generator_id}, {"$set": {"status": "standby"}}
            )

    return {"message": "Alarm behoben"}


# ============== Simulate Data (for testing) ==============

@router.post("/simulate")
async def simulate_generator_data(admin: dict = Depends(require_admin_user)):
    """Create demo generators with simulated telemetry data for testing"""
    import random

    demo_generators = [
        {"name": "Generator Baustelle Hauptbahnhof", "serial": "DSE-HBF-001", "model": "DSE8610MK2", "location": "Frankfurt Hbf", "lat": 50.1109, "lng": 8.6821},
        {"name": "Generator Event Arena", "serial": "DSE-EVT-002", "model": "L0401MK2", "location": "Messe Frankfurt", "lat": 50.1117, "lng": 8.6449},
        {"name": "Generator Notstrom Klinik", "serial": "DSE-KLN-003", "model": "DSE8610MK2", "location": "Universitätsklinikum", "lat": 50.0937, "lng": 8.6591},
        {"name": "Generator Rechenzentrum", "serial": "DSE-RZ-004", "model": "DSE8610MK2", "location": "Rechenzentrum Süd", "lat": 50.0833, "lng": 8.6761},
        {"name": "Generator Festival Gelände", "serial": "DSE-FST-005", "model": "L0401MK2", "location": "Festivalpark", "lat": 50.1205, "lng": 8.7102},
    ]

    created = []
    for dg in demo_generators:
        existing = await db.generators.find_one({"serial_number": dg["serial"]}, {"_id": 0})
        if existing:
            gen_id = existing["id"]
            api_key = existing.get("api_key", f"dse_{secrets.token_hex(24)}")
        else:
            gen_id = str(uuid.uuid4())
            api_key = f"dse_{secrets.token_hex(24)}"
            gen_doc = {
                "id": gen_id,
                "name": dg["name"],
                "serial_number": dg["serial"],
                "model": dg["model"],
                "location_name": dg["location"],
                "latitude": dg["lat"],
                "longitude": dg["lng"],
                "dse_module_type": "DSE890",
                "assigned_customer_id": None,
                "notes": "Demo-Generator",
                "api_key": api_key,
                "status": "offline",
                "is_active": True,
                "last_seen": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.generators.insert_one(gen_doc)

        # Generate 24h of telemetry data (every 5 min = 288 points)
        statuses = ["running", "standby", "running", "running", "warning"]
        status = random.choice(statuses)
        now = datetime.now(timezone.utc)

        telemetry_batch = []
        for i in range(288):
            ts = (now - timedelta(minutes=i * 5)).isoformat()
            is_running = status == "running" or (status == "warning" and random.random() > 0.3)

            base_voltage = random.uniform(225, 235)
            doc = {
                "id": str(uuid.uuid4()),
                "generator_id": gen_id,
                "timestamp": ts,
                "voltage_l1": round(base_voltage + random.uniform(-3, 3), 1) if is_running else 0,
                "voltage_l2": round(base_voltage + random.uniform(-3, 3), 1) if is_running else 0,
                "voltage_l3": round(base_voltage + random.uniform(-3, 3), 1) if is_running else 0,
                "current_l1": round(random.uniform(50, 200), 1) if is_running else 0,
                "current_l2": round(random.uniform(50, 200), 1) if is_running else 0,
                "current_l3": round(random.uniform(50, 200), 1) if is_running else 0,
                "frequency": round(random.uniform(49.8, 50.2), 2) if is_running else 0,
                "power_kw": round(random.uniform(80, 350), 1) if is_running else 0,
                "power_kva": round(random.uniform(90, 400), 1) if is_running else 0,
                "power_kvar": round(random.uniform(10, 80), 1) if is_running else 0,
                "power_factor": round(random.uniform(0.85, 0.99), 2) if is_running else 0,
                "load_percent": round(random.uniform(30, 95), 1) if is_running else 0,
                "rpm": round(random.uniform(1480, 1520), 0) if is_running else 0,
                "oil_pressure": round(random.uniform(3.5, 5.5), 1) if is_running else 0,
                "coolant_temp": round(random.uniform(75, 95), 1) if is_running else round(random.uniform(18, 25), 1),
                "fuel_level": round(random.uniform(20, 95), 1),
                "battery_voltage": round(random.uniform(12.0, 14.2), 1),
                "hours_run": round(random.uniform(1000, 9000) + i * 0.08, 1),
                "engine_running": is_running,
                "mode": "auto" if is_running else "standby",
                "gps_lat": dg["lat"],
                "gps_lng": dg["lng"],
            }
            telemetry_batch.append(doc)

        # Clear old demo telemetry and insert new
        await db.generator_telemetry.delete_many({"generator_id": gen_id})
        if telemetry_batch:
            await db.generator_telemetry.insert_many(telemetry_batch)

        # Update generator status
        await db.generators.update_one(
            {"id": gen_id},
            {"$set": {"status": status, "last_seen": now.isoformat()}}
        )

        # Add a demo alarm for the "warning" generator
        if status == "warning":
            await db.generator_alarms.delete_many({"generator_id": gen_id})
            await db.generator_alarms.insert_one({
                "id": str(uuid.uuid4()),
                "generator_id": gen_id,
                "alarm_text": "Kühlmitteltemperatur erhöht",
                "severity": "warning",
                "timestamp": now.isoformat(),
                "acknowledged": False,
                "acknowledged_by": None,
                "resolved_at": None,
            })

        created.append({"id": gen_id, "name": dg["name"], "status": status})

    return {"message": f"{len(created)} Demo-Generatoren erstellt", "generators": created}


# ============== Dashboard Stats ==============

@router.get("/stats/overview")
async def get_generator_stats(user: dict = Depends(get_authenticated_user)):
    if user["role"] == "admin":
        query = {}
    else:
        apps = user.get("apps", {})
        gm = apps.get("generator_monitoring", {})
        if gm.get("enabled") and gm.get("access_all"):
            query = {"is_active": True}
        elif gm.get("enabled") and gm.get("generator_ids"):
            query = {"id": {"$in": gm.get("generator_ids", [])}}
        else:
            query = {"assigned_customer_id": user["id"]}

    total = await db.generators.count_documents(query)
    running = await db.generators.count_documents({**query, "status": "running"})
    standby = await db.generators.count_documents({**query, "status": "standby"})
    alarm = await db.generators.count_documents({**query, "status": {"$in": ["alarm", "warning"]}})
    offline = await db.generators.count_documents({**query, "status": "offline"})

    active_alarms = await db.generator_alarms.count_documents({"resolved_at": None, "severity": "alarm"})
    active_warnings = await db.generator_alarms.count_documents({"resolved_at": None, "severity": "warning"})

    return {
        "total": total,
        "running": running,
        "standby": standby,
        "alarm": alarm,
        "offline": offline,
        "active_alarms": active_alarms,
        "active_warnings": active_warnings,
    }
