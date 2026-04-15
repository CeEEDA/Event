from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import secrets
import hashlib
import hmac
import logging
import os

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


# DSE sentinel value thresholds for post-processing cleanup
_TELEMETRY_MAX_THRESHOLDS = {
    "voltage_l1": 2000, "voltage_l2": 2000, "voltage_l3": 2000,
    "voltage_l1_l2": 2000, "voltage_l2_l3": 2000, "voltage_l3_l1": 2000,
    "current_l1": 50000, "current_l2": 50000, "current_l3": 50000,
    "frequency": 200, "power_kw": 100000, "power_kva": 100000,
    "power_l1_w": 100_000_000, "power_l2_w": 100_000_000, "power_l3_w": 100_000_000,
    "oil_pressure": 5000, "coolant_temp": 500, "fuel_level": 200,
    "battery_voltage": 100, "rpm": 50000, "load_percent": 200,
    "power_factor": 10, "hours_run": 100_000,
}


def _sanitize_telemetry(t: dict):
    """Remove obviously invalid values from telemetry dict in-place.
    Catches DSE sentinel values that slipped through parsing (historical data)."""
    for field, max_val in _TELEMETRY_MAX_THRESHOLDS.items():
        val = t.get(field)
        if val is not None and isinstance(val, (int, float)):
            if abs(val) > max_val:
                t[field] = None


async def _resolve_generator(generator_id: str):
    """Find a generator by ID, including virtual generators from devices."""
    gen = await db.generators.find_one({"id": generator_id}, {"_id": 0})
    if gen:
        return gen
    if generator_id.startswith("dev-"):
        device_id = generator_id[4:]
        device = await db.devices.find_one({"id": device_id}, {"_id": 0})
        if device:
            dev_status = device.get("mqtt_status", "standby")
            if dev_status not in ("online", "offline", "running"):
                dev_status = "standby"
            return {
                "id": generator_id,
                "name": device.get("user_field") or device.get("model") or device["serial_number"],
                "serial_number": device["serial_number"],
                "model": device.get("controller") or device.get("model") or "–",
                "location_name": device.get("user_field", ""),
                "latitude": device.get("latitude"),
                "longitude": device.get("longitude"),
                "status": dev_status,
                "is_active": True,
                "device_id": device["id"],
                "from_device": True,
                "notes": device.get("notes", ""),
                "last_seen": device.get("last_seen"),
                "dse_module_uid": device.get("dse_module_uid", ""),
                "last_dse_mode": device.get("last_dse_mode"),
            }
    return None


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


@router.delete("/demo-data")
async def delete_demo_data(admin: dict = Depends(require_admin_user)):
    """Delete all demo generators and their telemetry/alarm data."""
    demo_serials = ["DSE-HBF-001", "DSE-EVT-002", "DSE-KLN-003", "DSE-RZ-004", "DSE-FST-005"]

    # Find demo generator IDs
    demo_gens = await db.generators.find(
        {"serial_number": {"$in": demo_serials}}, {"_id": 0, "id": 1}
    ).to_list(100)
    demo_ids = [g["id"] for g in demo_gens]

    if not demo_ids:
        return {"message": "Keine Demo-Daten gefunden"}

    # Delete telemetry, alarms, and generators
    tel_result = await db.generator_telemetry.delete_many({"generator_id": {"$in": demo_ids}})
    alarm_result = await db.generator_alarms.delete_many({"generator_id": {"$in": demo_ids}})
    gen_result = await db.generators.delete_many({"serial_number": {"$in": demo_serials}})

    return {
        "message": f"{gen_result.deleted_count} Demo-Generatoren gelöscht",
        "deleted_telemetry": tel_result.deleted_count,
        "deleted_alarms": alarm_result.deleted_count,
    }


@router.delete("/cleanup-ghost-generators")
async def cleanup_ghost_generators(user: dict = Depends(get_authenticated_user)):
    """Delete ghost generators: dev- entries without matching device, dse5510_pi duplicates, or entries without serial_number."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    deleted = 0
    # Find all dev- generators without matching device
    gens = await db.generators.find({"id": {"$regex": "^dev-"}}, {"_id": 0, "id": 1, "serial_number": 1}).to_list(500)
    for g in gens:
        device_id = g["id"][4:]
        device = await db.devices.find_one({"id": device_id}, {"_id": 1})
        if not device:
            await db.generators.delete_one({"id": g["id"]})
            deleted += 1
    # Delete mqtt_auto without serial_number
    result = await db.generators.delete_many({"source": "mqtt_auto", "serial_number": {"$exists": False}})
    deleted += result.deleted_count
    # Delete dse5510_pi ghost generators (type=dse5510_pi without serial_number)
    # These are duplicates of virtual dev- generators
    result2 = await db.generators.delete_many({"type": "dse5510_pi", "serial_number": {"$in": [None, ""]}})
    deleted += result2.deleted_count
    return {"message": f"{deleted} Geister-Generatoren geloescht"}

@router.get("")
async def list_generators(user: dict = Depends(get_authenticated_user)):
    if user["role"] == "admin":
        generators = await db.generators.find(
            {},
            {"_id": 0}
        ).to_list(1000)
        # Filter out ghost generators: auto-created without serial_number and no matching device
        real_gens = []
        for g in generators:
            if g.get("source") == "mqtt_auto" and not g.get("serial_number"):
                continue  # Skip ghost
            if g.get("type") == "dse5510_pi" and not g.get("serial_number"):
                continue  # Skip dse5510_pi ghost duplicate
            real_gens.append(g)
        generators = real_gens
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

    # Auto-include Stromerzeuger/Lichtmast devices as generators
    existing_serials = {g.get("serial_number") for g in generators}
    active_devices = await db.devices.find(
        {"device_type": {"$in": ["stromerzeuger", "lichtmast"]}, "status": {"$ne": "ausser_betrieb"}},
        {"_id": 0}
    ).to_list(2000)
    for dev in active_devices:
        if dev.get("serial_number") not in existing_serials:
            # Determine status from device's mqtt_status or last_seen
            dev_status = dev.get("mqtt_status", "offline")
            if dev_status not in ("online", "offline", "running", "standby", "alarm", "verbunden"):
                dev_status = "offline"
            # Create a virtual generator entry from the device
            vg = {
                "id": f"dev-{dev['id']}",
                "name": dev.get("user_field") or dev.get("model") or dev["serial_number"],
                "serial_number": dev["serial_number"],
                "model": dev.get("controller") or dev.get("model") or "–",
                "location_name": dev.get("user_field", ""),
                "latitude": dev.get("latitude"),
                "longitude": dev.get("longitude"),
                "status": dev_status,
                "is_active": True,
                "device_id": dev["id"],
                "from_device": True,
                "last_seen": dev.get("last_seen"),
                "dse_module_uid": dev.get("dse_module_uid", ""),
            }
            generators.append(vg)
            existing_serials.add(dev["serial_number"])

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

    # Attach latest telemetry from snapshot (fast: no extra DB queries)
    for g in generators:
        latest = g.get("latest_snapshot")
        # Fallback: device snapshot for dev- generators
        if not latest and g["id"].startswith("dev-"):
            dev_doc = await db.devices.find_one({"id": g["id"][4:]}, {"_id": 0, "latest_snapshot": 1})
            if dev_doc:
                latest = dev_doc.get("latest_snapshot")
        if not latest:
            latest = await db.generator_telemetry.find_one(
                {"generator_id": g["id"]}, {"_id": 0}, sort=[("timestamp", -1)]
            )
        if latest:
            _sanitize_telemetry(latest)
        g["latest_telemetry"] = latest

    # Batch-load devices by serial_number
    serial_numbers_all = list({g.get("serial_number") for g in generators if g.get("serial_number")})
    dev_map = {}
    if serial_numbers_all:
        devs = await db.devices.find({"serial_number": {"$in": serial_numbers_all}}, {"_id": 0}).to_list(len(serial_numbers_all))
        dev_map = {d["serial_number"]: d for d in devs}

    # Batch-load service plans for those devices
    dev_ids_for_plans = [d["id"] for d in dev_map.values() if d.get("next_maintenance_hours")]
    plan_map = {}
    if dev_ids_for_plans:
        plans = await db.service_plans.find({"device_id": {"$in": dev_ids_for_plans}}, {"_id": 0}).to_list(len(dev_ids_for_plans))
        plan_map = {p["device_id"]: p for p in plans}

    for g in generators:
        latest = g.get("latest_telemetry")
        # Normalize Pi-ingest fields to standard frontend field names
        if latest:
            if "power_total_w" in latest and "power_kw" not in latest:
                latest["power_kw"] = round(latest["power_total_w"] / 1000, 2) if latest["power_total_w"] else 0
            if "coolant_temp_c" in latest and "coolant_temp" not in latest:
                latest["coolant_temp"] = latest["coolant_temp_c"]
            if "oil_pressure_kpa" in latest and "oil_pressure" not in latest:
                latest["oil_pressure"] = round(latest["oil_pressure_kpa"] / 100, 2) if latest["oil_pressure_kpa"] else 0  # kPa -> bar
            if "fuel_level_pct" in latest and "fuel_level" not in latest:
                latest["fuel_level"] = latest["fuel_level_pct"]
            if "engine_run_hours" in latest and "hours_run" not in latest:
                latest["hours_run"] = latest["engine_run_hours"]
            if "power_factor_avg" in latest and "power_factor" not in latest:
                latest["power_factor"] = latest["power_factor_avg"]
        g["latest_telemetry"] = latest

        # P4: Check for upcoming maintenance via device cross-reference
        device = dev_map.get(g.get("serial_number"))
        if device:
            warning = False
            warning_reason = []
            # Check date-based maintenance (< 1 month = 30 days)
            if device.get("next_maintenance"):
                from datetime import datetime as dt
                try:
                    next_maint = dt.fromisoformat(device["next_maintenance"])
                    days_until = (next_maint - dt.now(timezone.utc).replace(tzinfo=None)).days
                    if days_until <= 30:
                        warning = True
                        g["maintenance_due_days"] = days_until
                        g["next_maintenance_date"] = device["next_maintenance"]
                        warning_reason.append(f"{days_until} Tage" if days_until >= 0 else "Überfällig")
                except (ValueError, TypeError):
                    pass
            # Check hours-based maintenance (< 50 hours)
            if device.get("next_maintenance_hours"):
                plan = plan_map.get(device.get("id"))
                current_hrs = plan.get("current_hours", 0) if plan else 0
                hrs_until = device["next_maintenance_hours"] - current_hrs
                if hrs_until <= 50:
                    warning = True
                    g["maintenance_due_hours"] = round(hrs_until)
                    warning_reason.append(f"{round(hrs_until)}h")

            if warning:
                g["maintenance_warning"] = True
                g["maintenance_warning_reason"] = " / ".join(warning_reason)

    return generators


# ============== Diagnose-Tool Download ==============

@router.get("/diagnose-modbus")
async def download_diagnose_script():
    """Download the Modbus RTU diagnostic script for Raspberry Pi."""
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "diagnose_modbus.py")
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="Diagnose-Skript nicht gefunden")
    return FileResponse(script_path, media_type="text/x-python", filename="diagnose_modbus.py")


@router.get("/schnelltest-dse")
async def download_schnelltest_script():
    """Download the DSE 5510 quick-read script for Raspberry Pi."""
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "schnelltest_dse.py")
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="Schnelltest-Skript nicht gefunden")
    return FileResponse(script_path, media_type="text/x-python", filename="schnelltest_dse.py")


@router.get("/diagnose-write")
async def download_diagnose_write_script():
    """Download the DSE 5510 write diagnostic script."""
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "diagnose_write.py")
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="Write-Diagnose-Skript nicht gefunden")
    return FileResponse(script_path, media_type="text/x-python", filename="diagnose_write.py")


@router.get("/dse5510-sync")
async def download_dse5510_sync_script():
    """Download the DSE 5510 sync script for Raspberry Pi."""
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "dse5510_sync.py")
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="DSE5510-Sync-Skript nicht gefunden")
    return FileResponse(script_path, media_type="text/x-python", filename="dse5510_sync.py")


@router.get("/scan-registers")
async def download_register_scanner():
    """Download the DSE register scanner script."""
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "scan_registers.py")
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="Scanner-Skript nicht gefunden")
    return FileResponse(script_path, media_type="text/x-python", filename="scan_registers.py")


@router.get("/scan-full")
async def download_full_scanner():
    """Download the full DSE register scanner script."""
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "scan_full.py")
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="Scanner-Skript nicht gefunden")
    return FileResponse(script_path, media_type="text/x-python", filename="scan_full.py")



@router.get("/{generator_id}")
async def get_generator(generator_id: str, user: dict = Depends(get_authenticated_user)):
    gen = await _resolve_generator(generator_id)
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

    # Attach latest telemetry from snapshot (fast: already merged on write)
    latest = gen.get("latest_snapshot") if gen else None
    # Fallback: check device snapshot (for dev- generators where gen doc may not have snapshot)
    if (not latest or not latest.get("timestamp")) and generator_id.startswith("dev-"):
        dev_id = generator_id[4:]
        dev_doc = await db.devices.find_one({"id": dev_id}, {"_id": 0, "latest_snapshot": 1})
        if dev_doc and dev_doc.get("latest_snapshot"):
            latest = dev_doc["latest_snapshot"]
    # Fallback: fetch from telemetry collection
    if not latest or not latest.get("timestamp"):
        latest = await db.generator_telemetry.find_one(
            {"generator_id": generator_id},
            {"_id": 0},
            sort=[("timestamp", -1)]
        )

    # Sanitize telemetry: remove DSE sentinel values that may have been stored historically
    if latest:
        _sanitize_telemetry(latest)
        if "power_total_w" in latest and "power_kw" not in latest:
            latest["power_kw"] = round(latest["power_total_w"] / 1000, 2) if latest["power_total_w"] else 0
        if "coolant_temp_c" in latest and "coolant_temp" not in latest:
            latest["coolant_temp"] = latest["coolant_temp_c"]
        if "oil_pressure_kpa" in latest and "oil_pressure" not in latest:
            latest["oil_pressure"] = round(latest["oil_pressure_kpa"] / 100, 2) if latest["oil_pressure_kpa"] else 0
        if "fuel_level_pct" in latest and "fuel_level" not in latest:
            latest["fuel_level"] = latest["fuel_level_pct"]
        if "engine_run_hours" in latest and "hours_run" not in latest:
            latest["hours_run"] = latest["engine_run_hours"]
        if "power_factor_avg" in latest and "power_factor" not in latest:
            latest["power_factor"] = latest["power_factor_avg"]
        # DSE-Modus aus letztem Steuerbefehl uebernehmen wenn Register nicht lesbar
        if latest.get("dse_mode") in (None, "unknown", ""):
            last_mode = gen.get("last_dse_mode")
            if last_mode:
                latest["dse_mode"] = last_mode
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
    hours: int = Query(default=24, ge=1, le=8760),
    limit: int = Query(default=5000, ge=1, le=50000),
    from_time: str = Query(default=None),
    to_time: str = Query(default=None),
    user: dict = Depends(get_authenticated_user),
):
    gen = await _resolve_generator(generator_id)
    if not gen:
        raise HTTPException(status_code=404, detail="Generator nicht gefunden")

    if user["role"] == "kunde" and gen.get("assigned_customer_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    # Kunden-Zugriffsbeschraenkung: Zeitraum + Datenkategorien
    user_doc = None
    if user["role"] == "kunde":
        user_doc = await db.users.find_one({"id": user["id"]}, {"_id": 0})
        gen_app = (user_doc or {}).get("apps", {}).get("generator_monitoring", {})
        # Zeitraum-Beschraenkung
        access_start = gen_app.get("data_access_start")
        access_end = gen_app.get("data_access_end")
        if access_start and (not from_time or from_time < access_start):
            from_time = access_start
        if access_end and (not to_time or to_time > access_end):
            to_time = access_end

    # Zeitfilter: from_time/to_time hat Vorrang vor hours
    if from_time:
        since = from_time
    else:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    query = {"generator_id": generator_id, "timestamp": {"$gte": since}}
    if to_time:
        query["timestamp"]["$lte"] = to_time

    telemetry = await db.generator_telemetry.find(
        query, {"_id": 0}
    ).sort("timestamp", 1).to_list(limit)

    # Felder die zu Elektrisch / Mechanisch gehoeren
    ELECTRICAL_FIELDS = {"voltage_l1", "voltage_l2", "voltage_l3", "voltage_l1_l2", "voltage_l2_l3", "voltage_l3_l1",
        "current_l1", "current_l2", "current_l3", "power_total_w", "power_kw", "power_factor", "power_factor_avg",
        "frequency", "energy_kwh"}
    MECHANICAL_FIELDS = {"rpm", "oil_pressure", "oil_pressure_kpa", "coolant_temp", "coolant_temp_c",
        "fuel_level", "fuel_level_pct", "battery_voltage", "charge_alt_voltage",
        "engine_run_hours", "hours_run", "engine_running"}

    # Kunden: Datenfilter nach Freigabe
    share_electrical = True
    share_mechanical = True
    if user_doc:
        gen_app = user_doc.get("apps", {}).get("generator_monitoring", {})
        share_electrical = gen_app.get("share_electrical", True)
        share_mechanical = gen_app.get("share_mechanical", True)

    # Normalize Pi-ingest fields for chart compatibility
    for t in telemetry:
        if "power_total_w" in t and "power_kw" not in t:
            t["power_kw"] = round(t["power_total_w"] / 1000, 2) if t["power_total_w"] else 0
        if "coolant_temp_c" in t and "coolant_temp" not in t:
            t["coolant_temp"] = t["coolant_temp_c"]
        if "oil_pressure_kpa" in t and "oil_pressure" not in t:
            t["oil_pressure"] = round(t["oil_pressure_kpa"] / 100, 2) if t["oil_pressure_kpa"] else 0
        if "fuel_level_pct" in t and "fuel_level" not in t:
            t["fuel_level"] = t["fuel_level_pct"]
        if "engine_run_hours" in t and "hours_run" not in t:
            t["hours_run"] = t["engine_run_hours"]
        if "power_factor_avg" in t and "power_factor" not in t:
            t["power_factor"] = t["power_factor_avg"]

        # Sanitize: remove DSE sentinel values from historical data
        _sanitize_telemetry(t)

        # Nicht freigegebene Felder entfernen
        if not share_electrical:
            for f in ELECTRICAL_FIELDS:
                t.pop(f, None)
        if not share_mechanical:
            for f in MECHANICAL_FIELDS:
                t.pop(f, None)

    return telemetry


# ============== Alarms ==============

@router.get("/{generator_id}/alarms")
async def get_alarms(
    generator_id: str,
    active_only: bool = Query(default=True),
    user: dict = Depends(get_authenticated_user),
):
    gen = await _resolve_generator(generator_id)
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

    # Count from generators collection
    gen_total = await db.generators.count_documents(query)
    gen_running = await db.generators.count_documents({**query, "status": "running"})
    gen_standby = await db.generators.count_documents({**query, "status": "standby"})
    gen_alarm = await db.generators.count_documents({**query, "status": {"$in": ["alarm", "warning"]}})
    gen_online = await db.generators.count_documents({**query, "status": "online"})
    gen_offline = await db.generators.count_documents({**query, "status": "offline"})

    # Count virtual generators from devices (Stromerzeuger/Lichtmast not already in generators)
    existing_serials = set()
    async for g in db.generators.find(query, {"serial_number": 1, "_id": 0}):
        existing_serials.add(g.get("serial_number"))

    virtual_online = 0
    virtual_offline = 0
    virtual_alarm = 0
    active_devices = await db.devices.find(
        {"device_type": {"$in": ["stromerzeuger", "lichtmast"]}, "status": {"$ne": "ausser_betrieb"}},
        {"_id": 0, "serial_number": 1, "mqtt_status": 1, "last_seen": 1}
    ).to_list(2000)
    for dev in active_devices:
        if dev.get("serial_number") not in existing_serials:
            existing_serials.add(dev["serial_number"])
            if dev.get("mqtt_status") == "alarm":
                virtual_alarm += 1
            elif dev.get("mqtt_status") == "online":
                virtual_online += 1
            else:
                virtual_offline += 1

    total = gen_total + virtual_online + virtual_offline + virtual_alarm
    standby = gen_standby + virtual_online
    offline = gen_offline + virtual_offline

    active_alarms = await db.generator_alarms.count_documents({"resolved_at": None, "severity": "alarm"})
    active_warnings = await db.generator_alarms.count_documents({"resolved_at": None, "severity": "warning"})

    return {
        "total": total,
        "running": gen_running,
        "standby": standby,
        "online": gen_online,
        "alarm": gen_alarm + virtual_alarm,
        "offline": offline,
        "active_alarms": active_alarms,
        "active_warnings": active_warnings,
    }


# ============== Pi-based Generator Ingest (DSE 5510 etc.) ==============

class PiIngestPayload(BaseModel):
    api_key: str
    device_id: str
    generator_id: Optional[str] = ""
    records: List[Dict[str, Any]] = []
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    command_results: Optional[List[Dict[str, Any]]] = []
    alarms: Optional[List[Dict[str, Any]]] = []


def _hash_key(plain_key: str) -> str:
    return hashlib.sha256(plain_key.encode()).hexdigest()


def _verify_key(plain_key: str, hashed: str) -> bool:
    return hmac.compare_digest(hashlib.sha256(plain_key.encode()).hexdigest(), hashed)


@router.post("/ingest")
async def ingest_generator_telemetry(payload: PiIngestPayload):
    """Receive telemetry from Pi-based DSE controllers (DSE 5510 etc.).
    Authenticates via device_key, stores in generator_telemetry, returns pending commands."""

    # Authenticate via device_key
    device = await db.devices.find_one({"id": payload.device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Geraet nicht gefunden")

    stored_hash = device.get("device_key_hash", "")
    if not stored_hash or not _verify_key(payload.api_key, stored_hash):
        raise HTTPException(status_code=403, detail="Ungueltiger Geraeteschluessel")

    now_iso = datetime.now(timezone.utc).isoformat()

    # Resolve generator_id: use "dev-{device_id}" pattern for virtual generators
    generator_id = payload.generator_id or f"dev-{payload.device_id}"

    # Check if a generator already exists for this device (by id OR generator_id field)
    existing_gen = await db.generators.find_one(
        {"$or": [{"id": generator_id}, {"generator_id": generator_id}, {"device_id": payload.device_id}]},
        {"_id": 0}
    )
    if existing_gen:
        # Use existing generator's id for consistency
        generator_id = existing_gen.get("id", generator_id)

    # Update device status + latest_snapshot from newest record
    # Nur "online" wenn DSE tatsaechlich Daten liefert
    # Batteriespannung > 5V = DSE Display ist an und kommuniziert
    has_dse_data = False
    if payload.records:
        rec = payload.records[-1]
        batt = rec.get("battery_voltage", 0) or 0
        has_dse_data = batt > 5

    if has_dse_data:
        device_status = "online"
    elif payload.records:
        device_status = "verbunden"
    else:
        # Heartbeat ohne neue Records: vorherigen Status beibehalten
        device_status = device.get("mqtt_status") or "verbunden"
    update_fields = {
        "last_seen": now_iso,
        "mqtt_status": device_status,
        "updated_at": now_iso,
    }
    if payload.latitude is not None and payload.longitude is not None:
        update_fields["latitude"] = payload.latitude
        update_fields["longitude"] = payload.longitude

    # Build latest_snapshot from the most recent record
    if payload.records:
        rec = payload.records[-1]
        snapshot = {"timestamp": rec.get("ts_utc", now_iso)}
        snapshot_map = {
            "oil_pressure": ("oil_pressure_kpa", lambda v: round(v / 100.0, 1) if v else None),
            "coolant_temp": ("coolant_temp_c", None),
            "fuel_level": ("fuel_level_pct", None),
            "battery_voltage": ("battery_voltage", None),
            "rpm": ("rpm", None),
            "frequency": ("frequency", None),
            "voltage_l1": ("voltage_l1", None),
            "voltage_l2": ("voltage_l2", None),
            "voltage_l3": ("voltage_l3", None),
            "current_l1": ("current_l1", None),
            "current_l2": ("current_l2", None),
            "current_l3": ("current_l3", None),
            "power_total_w": ("power_total_w", None),
            "power_kw": ("power_total_w", lambda v: round(v / 1000.0, 2) if v else None),
            "power_factor_avg": ("power_factor_avg", None),
            "hours_run": ("engine_run_hours", None),
            "engine_starts": ("num_starts", None),
            "dse_mode": ("dse_mode", None),
        }
        for snap_key, (rec_key, transform) in snapshot_map.items():
            val = rec.get(rec_key)
            if val is not None:
                snapshot[snap_key] = transform(val) if transform else val
        if rec.get("engine_running") is not None:
            snapshot["engine_running"] = rec["engine_running"]
        for k, v in snapshot.items():
            update_fields[f"latest_snapshot.{k}"] = v

    await db.devices.update_one({"id": payload.device_id}, {"$set": update_fields})

    # Update virtual generator status too
    gen_update = {"last_seen": now_iso, "mqtt_status": device_status, "updated_at": now_iso}
    if payload.latitude is not None and payload.longitude is not None:
        gen_update["latitude"] = payload.latitude
        gen_update["longitude"] = payload.longitude
    await db.generators.update_one(
        {"$or": [{"id": generator_id}, {"generator_id": generator_id}]},
        {"$set": gen_update}
    )

    # Store telemetry records
    inserted = 0
    for record in payload.records:
        telemetry_doc = {
            "id": str(uuid.uuid4()),
            "generator_id": generator_id,
            "timestamp": record.get("ts_utc", now_iso),
            "source": record.get("source", "dse5510_pi"),
            # Basic instrumentation
            "oil_pressure_kpa": record.get("oil_pressure_kpa"),
            "coolant_temp_c": record.get("coolant_temp_c"),
            "oil_temp_c": record.get("oil_temp_c"),
            "fuel_level_pct": record.get("fuel_level_pct"),
            "charge_alt_voltage": record.get("charge_alt_voltage"),
            "battery_voltage": record.get("battery_voltage"),
            "rpm": record.get("rpm"),
            "frequency": record.get("frequency"),
            "engine_running": record.get("engine_running", False),
            # Voltages
            "voltage_l1": record.get("voltage_l1"),
            "voltage_l2": record.get("voltage_l2"),
            "voltage_l3": record.get("voltage_l3"),
            "voltage_l1_l2": record.get("voltage_l1_l2"),
            "voltage_l2_l3": record.get("voltage_l2_l3"),
            "voltage_l3_l1": record.get("voltage_l3_l1"),
            # Currents
            "current_l1": record.get("current_l1"),
            "current_l2": record.get("current_l2"),
            "current_l3": record.get("current_l3"),
            # Power
            "power_l1_w": record.get("power_l1_w"),
            "power_l2_w": record.get("power_l2_w"),
            "power_l3_w": record.get("power_l3_w"),
            "power_total_w": record.get("power_total_w"),
            "power_total_va": record.get("power_total_va"),
            "power_total_var": record.get("power_total_var"),
            # Power factor
            "power_factor_l1": record.get("power_factor_l1"),
            "power_factor_l2": record.get("power_factor_l2"),
            "power_factor_l3": record.get("power_factor_l3"),
            "power_factor_avg": record.get("power_factor_avg"),
            # Accumulated
            "engine_run_time_s": record.get("engine_run_time_s"),
            "engine_run_hours": record.get("engine_run_hours"),
            "energy_kwh": record.get("energy_kwh"),
            "num_starts": record.get("num_starts"),
            # DSE Mode & Status
            "dse_mode": record.get("dse_mode"),
            "dse_mode_raw": record.get("dse_mode_raw"),
            "generator_available": record.get("generator_available"),
            "breaker_closed": record.get("breaker_closed"),
        }
        # Remove None values to keep documents clean
        telemetry_doc = {k: v for k, v in telemetry_doc.items() if v is not None}
        await db.generator_telemetry.insert_one(telemetry_doc)
        inserted += 1

        # DSE-Modus aus Register-Read aktualisieren (hat Prioritaet ueber Portal-Befehle)
        record_dse_mode = record.get("dse_mode")
        if record_dse_mode and record_dse_mode != "unknown":
            await db.generators.update_one(
                {"$or": [{"id": generator_id}, {"generator_id": generator_id}]},
                {"$set": {"last_dse_mode": record_dse_mode, "last_dse_mode_at": now_iso}}
            )
            await db.devices.update_one(
                {"id": payload.device_id},
                {"$set": {"last_dse_mode": record_dse_mode, "last_dse_mode_at": now_iso}}
            )

    # Process command results
    # Modus-Befehle die den DSE-Modus aendern
    MODE_COMMANDS = {
        "stop": "stop",
        "auto_on": "auto",
        "manual": "manual",
    }
    last_mode_from_cmd = None
    for cr in (payload.command_results or []):
        cmd_id = cr.get("command_id", "")
        if cmd_id:
            await db.generator_pending_commands.update_one(
                {"id": cmd_id},
                {"$set": {
                    "status": "completed" if cr.get("success") else "failed",
                    "result_message": cr.get("message", ""),
                    "completed_at": now_iso,
                }}
            )
            # Wenn ein Modus-Befehl erfolgreich war, Modus merken
            if cr.get("success"):
                cmd_doc = await db.generator_pending_commands.find_one({"id": cmd_id}, {"_id": 0})
                if cmd_doc:
                    cmd_name = cmd_doc.get("command", "")
                    if cmd_name in MODE_COMMANDS:
                        last_mode_from_cmd = MODE_COMMANDS[cmd_name]

    # DSE-Modus aus letztem erfolgreichen Befehl aktualisieren
    if last_mode_from_cmd:
        await db.generators.update_one(
            {"$or": [{"id": generator_id}, {"generator_id": generator_id}]},
            {"$set": {"last_dse_mode": last_mode_from_cmd, "last_dse_mode_at": now_iso}}
        )
        await db.devices.update_one(
            {"id": payload.device_id},
            {"$set": {"last_dse_mode": last_mode_from_cmd, "last_dse_mode_at": now_iso}}
        )
        logger.info(f"DSE-Modus aktualisiert: {last_mode_from_cmd} (aus Befehl)")

    # Process alarms from Pi into generator_events log
    for alarm in (payload.alarms or []):
        event_doc = {
            "id": str(uuid.uuid4()),
            "generator_id": generator_id,
            "device_id": payload.device_id,
            "timestamp": alarm.get("ts_utc", now_iso),
            "event_type": alarm.get("alarm_type", "unknown"),
            "event_code": alarm.get("alarm_code"),
            "description": alarm.get("description", ""),
            "active": alarm.get("active", True),
            "cleared_at": alarm.get("cleared_at"),
            "source": "dse5510_pi",
            "latitude": payload.latitude,
            "longitude": payload.longitude,
        }
        await db.generator_events.insert_one(event_doc)

    # Auto-detect state changes from telemetry and log events
    if payload.records:
        latest_rec = payload.records[-1]
        prev_event = await db.generator_events.find_one(
            {"generator_id": generator_id, "event_type": {"$in": ["engine_start", "engine_stop"]}},
            {"_id": 0}, sort=[("timestamp", -1)]
        )
        prev_running = prev_event.get("event_type") == "engine_start" if prev_event else False
        curr_running = latest_rec.get("engine_running", False) or (latest_rec.get("rpm", 0) > 100)

        if curr_running and not prev_running:
            await db.generator_events.insert_one({
                "id": str(uuid.uuid4()), "generator_id": generator_id, "device_id": payload.device_id,
                "timestamp": latest_rec.get("ts_utc", now_iso), "event_type": "engine_start",
                "description": f"Motor gestartet (RPM: {latest_rec.get('rpm', 0)})",
                "source": "auto_detect", "latitude": payload.latitude, "longitude": payload.longitude,
            })
        elif not curr_running and prev_running:
            await db.generator_events.insert_one({
                "id": str(uuid.uuid4()), "generator_id": generator_id, "device_id": payload.device_id,
                "timestamp": latest_rec.get("ts_utc", now_iso), "event_type": "engine_stop",
                "description": "Motor gestoppt",
                "source": "auto_detect", "latitude": payload.latitude, "longitude": payload.longitude,
            })

        # Under-frequency detection
        freq = latest_rec.get("frequency", 0)
        if freq > 0 and freq < 48.0:
            await db.generator_events.insert_one({
                "id": str(uuid.uuid4()), "generator_id": generator_id, "device_id": payload.device_id,
                "timestamp": latest_rec.get("ts_utc", now_iso), "event_type": "under_frequency",
                "description": f"Unterfrequenz: {freq} Hz",
                "source": "auto_detect", "latitude": payload.latitude, "longitude": payload.longitude,
            })

    # Fetch pending commands for this device
    pending = await db.generator_pending_commands.find(
        {"device_id": payload.device_id, "status": "pending"},
        {"_id": 0}
    ).sort("created_at", 1).to_list(10)

    # 2-Minuten TTL: Abgelaufene Befehle als expired markieren
    COMMAND_TTL_SECONDS = 120
    valid_commands = []
    for cmd in pending:
        created = cmd.get("created_at", "")
        try:
            cmd_time = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if cmd_time.tzinfo is None:
                cmd_time = cmd_time.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - cmd_time).total_seconds()
            if age > COMMAND_TTL_SECONDS:
                await db.generator_pending_commands.update_one(
                    {"id": cmd["id"]},
                    {"$set": {"status": "expired", "result_message": f"Abgelaufen nach {int(age)}s (TTL: {COMMAND_TTL_SECONDS}s)"}}
                )
                logger.info(f"Befehl {cmd['command']} abgelaufen ({int(age)}s alt)")
                continue
        except Exception:
            pass
        valid_commands.append(cmd)

    # Mark valid commands as sent
    for cmd in valid_commands:
        await db.generator_pending_commands.update_one(
            {"id": cmd["id"]},
            {"$set": {"status": "sent", "sent_at": now_iso}}
        )

    return {
        "inserted": inserted,
        "generator_id": generator_id,
        "pending_commands": valid_commands,
    }


@router.post("/pi-command/{device_id}")
async def send_pi_command(device_id: str, cmd: Dict[str, str], user: dict = Depends(get_authenticated_user)):
    """Queue a control command for a Pi-based generator (DSE 5510).
    The Pi picks it up on its next ingest call."""
    # Verify admin/operator
    if user.get("role") not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    command = cmd.get("command", "")
    valid_commands = ["stop", "auto_on", "manual", "test_on_load", "auto_manual_restore", "start", "mute", "reset", "gen_switch_on", "gen_switch_off", "reset_mains"]
    if command not in valid_commands:
        raise HTTPException(status_code=400, detail=f"Unbekannter Befehl: {command}. Erlaubt: {valid_commands}")

    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Geraet nicht gefunden")

    DSE_CMD_LABELS = {
        "stop": "Stop-Modus", "auto_on": "Automatikmodus", "manual": "Manueller Modus",
        "test_on_load": "Testlauf unter Last", "auto_manual_restore": "Auto mit manueller Rueckkehr",
        "start": "Motor starten", "mute": "Alarm stumm", "reset": "Alarme zuruecksetzen",
        "gen_switch_on": "Generator zuschalten", "gen_switch_off": "Generator abschalten",
        "reset_mains": "Netzausfall zuruecksetzen",
    }

    cmd_doc = {
        "id": str(uuid.uuid4()),
        "device_id": device_id,
        "generator_id": f"dev-{device_id}",
        "command": command,
        "label": DSE_CMD_LABELS.get(command, command),
        "status": "pending",
        "user_id": user["id"],
        "user_name": user.get("name", user.get("email", "")),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.generator_pending_commands.insert_one(cmd_doc)

    # Also log in control log for history
    await db.generator_control_log.insert_one({
        "id": str(uuid.uuid4()),
        "generator_id": f"dev-{device_id}",
        "generator_name": device.get("serial_number", ""),
        "command": command,
        "command_label": DSE_CMD_LABELS.get(command, command),
        "topic": "pi-http",
        "payload": f"Pending command for Pi: {command}",
        "user_id": user["id"],
        "user_name": user.get("name", user.get("email", "")),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "success": True,
        "command_id": cmd_doc["id"],
        "command": command,
        "label": DSE_CMD_LABELS.get(command, command),
        "status": "pending",
        "message": f"Befehl '{DSE_CMD_LABELS.get(command, command)}' wird beim naechsten Sync an den Pi gesendet.",
    }


@router.get("/poll-commands/{device_id}")
async def poll_commands(device_id: str, request: Request):
    """Lightweight endpoint for Pi to quickly poll for pending commands.
    Authenticated via device_key query param."""
    device_key = request.query_params.get("key", "")
    if not device_key:
        raise HTTPException(status_code=401, detail="Kein Device-Key")

    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Geraet nicht gefunden")

    # Verify device key
    import hashlib
    key_hash = hashlib.sha256(device_key.encode()).hexdigest()
    if device.get("device_key_hash") != key_hash:
        raise HTTPException(status_code=401, detail="Falscher Device-Key")

    now_iso = datetime.now(timezone.utc).isoformat()
    pending = await db.generator_pending_commands.find(
        {"device_id": device_id, "status": "pending"},
        {"_id": 0}
    ).sort("created_at", 1).to_list(10)

    # 2-Minuten TTL: Abgelaufene Befehle als expired markieren
    COMMAND_TTL_SECONDS = 120
    valid_commands = []
    for cmd in pending:
        created = cmd.get("created_at", "")
        try:
            cmd_time = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if cmd_time.tzinfo is None:
                cmd_time = cmd_time.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - cmd_time).total_seconds()
            if age > COMMAND_TTL_SECONDS:
                await db.generator_pending_commands.update_one(
                    {"id": cmd["id"]},
                    {"$set": {"status": "expired", "result_message": f"Abgelaufen nach {int(age)}s"}}
                )
                continue
        except Exception:
            pass
        valid_commands.append(cmd)

    for cmd in valid_commands:
        await db.generator_pending_commands.update_one(
            {"id": cmd["id"]},
            {"$set": {"status": "sent", "sent_at": now_iso}}
        )

    return {"pending_commands": valid_commands}



# ============== Generator Event Log ==============

EVENT_TYPE_LABELS = {
    "engine_start": "Motor gestartet",
    "engine_stop": "Motor gestoppt",
    "overtemp": "Uebertemperatur",
    "low_oil_pressure": "Niedriger Oeldruck",
    "low_battery": "Niedrige Batterie",
    "under_frequency": "Unterfrequenz",
    "over_frequency": "Ueberfrequenz",
    "emergency_stop": "Not-Aus",
    "modbus_disconnect": "Modbus Verbindung verloren",
    "gen_switch_on": "Generator zugeschaltet",
    "gen_switch_off": "Generator abgeschaltet",
    "command_sent": "Steuerbefehl gesendet",
}


@router.get("/events/{generator_id}")
async def get_generator_events(
    generator_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = None,
    user: dict = Depends(get_authenticated_user)
):
    """Get event log for a generator, sorted by timestamp descending."""
    query = {"generator_id": generator_id}
    if event_type:
        query["event_type"] = event_type

    total = await db.generator_events.count_documents(query)
    events = await db.generator_events.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).skip(offset).limit(limit).to_list(limit)

    # Add labels
    for e in events:
        e["event_label"] = EVENT_TYPE_LABELS.get(e.get("event_type", ""), e.get("event_type", ""))

    return {
        "total": total,
        "events": events,
        "limit": limit,
        "offset": offset,
    }


@router.get("/events-by-device/{device_id}")
async def get_device_events(
    device_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_authenticated_user)
):
    """Get event log for a device, sorted by timestamp descending."""
    query = {"device_id": device_id}
    total = await db.generator_events.count_documents(query)
    events = await db.generator_events.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).skip(offset).limit(limit).to_list(limit)

    for e in events:
        e["event_label"] = EVENT_TYPE_LABELS.get(e.get("event_type", ""), e.get("event_type", ""))

    return {
        "total": total,
        "events": events,
        "limit": limit,
        "offset": offset,
    }



# ============== Remote Update for DSE 5510 Pi ==============

@router.get("/remote-update/{device_id}")
async def get_remote_update(device_id: str, api_key: str = Query(...)):
    """Pi polls this endpoint to check for pending config updates or script updates."""
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Geraet nicht gefunden")
    if not _verify_key(api_key, device.get("device_key_hash", "")):
        raise HTTPException(status_code=403, detail="Ungueltiger Schluessel")

    pending = await db.device_remote_updates.find_one(
        {"device_id": device_id, "status": "pending"}, {"_id": 0}
    )
    if not pending:
        return {"has_update": False}

    return {
        "has_update": True,
        "config": pending.get("config"),
        "script_url": pending.get("script_url"),
        "update_id": pending.get("id"),
    }


@router.post("/remote-update/{device_id}/ack")
async def ack_remote_update(device_id: str, api_key: str = Query(...)):
    """Pi acknowledges that it applied the update."""
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Geraet nicht gefunden")
    if not _verify_key(api_key, device.get("device_key_hash", "")):
        raise HTTPException(status_code=403, detail="Ungueltiger Schluessel")

    await db.device_remote_updates.update_many(
        {"device_id": device_id, "status": "pending"},
        {"$set": {"status": "applied", "applied_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Update bestaetigt"}


class RemoteConfigUpdate(BaseModel):
    baud_rate: Optional[int] = None
    slave_id: Optional[int] = None
    serial_port: Optional[str] = None
    read_interval: Optional[int] = None
    sync_interval: Optional[int] = None


@router.post("/remote-update/{device_id}/push")
async def push_remote_update(device_id: str, data: RemoteConfigUpdate, user: dict = Depends(get_authenticated_user)):
    """Admin pushes a config update to a Pi device."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")

    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Geraet nicht gefunden")

    config_changes = {k: v for k, v in data.dict().items() if v is not None}
    if not config_changes:
        raise HTTPException(status_code=400, detail="Keine Aenderungen angegeben")

    # Remove any existing pending updates
    await db.device_remote_updates.delete_many({"device_id": device_id, "status": "pending"})

    update_doc = {
        "id": str(uuid.uuid4()),
        "device_id": device_id,
        "config": config_changes,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.device_remote_updates.insert_one(update_doc)

    return {"message": f"Config-Update fuer {device_id} geplant", "changes": config_changes}
