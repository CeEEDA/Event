from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/energy-monitoring", tags=["energy-monitoring"])
security = HTTPBearer()

db = None
decode_jwt_token = None


def init_energy_monitoring_routes(_db, _decode_jwt_token):
    global db, decode_jwt_token
    db = _db
    decode_jwt_token = _decode_jwt_token


# ============== Models ==============

class MeterCreate(BaseModel):
    device_id: str
    meter_ip: str
    meter_name: str
    description: Optional[str] = ""


class MeterUpdate(BaseModel):
    meter_ip: Optional[str] = None
    meter_name: Optional[str] = None
    description: Optional[str] = None


# ============== Helpers ==============

async def get_authenticated_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_jwt_token(credentials.credentials)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    return user


async def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await get_authenticated_user(credentials)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin-Berechtigung erforderlich")
    return user


async def require_staff(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await get_authenticated_user(credentials)
    if user["role"] not in ("admin", "mitarbeiter"):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    return user


def check_energy_monitoring_access(user: dict) -> bool:
    """Check if user has active energy monitoring access."""
    if user["role"] == "admin":
        return True

    apps = user.get("apps", {})
    em = apps.get("energy_monitoring", {})
    if not em.get("enabled", False):
        return False

    # For Kunde: check time-based access
    if user["role"] == "kunde":
        access_type = em.get("access_type", "permanent")
        if access_type == "temporary":
            now = datetime.now(timezone.utc)
            access_start = em.get("access_start")
            access_end = em.get("access_end")
            if access_start:
                start = datetime.fromisoformat(access_start)
                if now < start:
                    return False
            if access_end:
                end = datetime.fromisoformat(access_end)
                if now > end:
                    return False

    return True


def get_allowed_device_ids(user: dict) -> Optional[List[str]]:
    """Return list of allowed device IDs or None for all access."""
    if user["role"] == "admin":
        return None  # All access

    apps = user.get("apps", {})
    em = apps.get("energy_monitoring", {})

    if em.get("access_all", False):
        return None  # All access

    return em.get("device_ids", [])


# ============== Device Endpoints ==============

@router.get("/devices")
async def list_energy_devices(user: dict = Depends(get_authenticated_user)):
    """List Messkoffer devices the user has access to."""
    if not check_energy_monitoring_access(user):
        raise HTTPException(status_code=403, detail="Energy Monitoring nicht freigeschaltet")

    # Get all Messkoffer devices
    query = {"device_type": "messkoffer"}
    devices = await db.devices.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)

    # Filter by allowed device IDs
    allowed_ids = get_allowed_device_ids(user)
    if allowed_ids is not None:
        devices = [d for d in devices if d["id"] in allowed_ids]

    # Enrich with meter count and latest data
    for device in devices:
        meter_count = await db.emu_meters.count_documents({"device_id": device["id"]})
        device["meter_count"] = meter_count

        # Get latest telemetry summary
        latest = await db.emu_data.find_one(
            {"device_id": device["id"]},
            {"_id": 0},
            sort=[("ts_utc", -1)]
        )
        device["latest_data"] = latest

        if "image_gridfs_id" in device and device["image_gridfs_id"]:
            device["image_gridfs_id"] = str(device["image_gridfs_id"])

    return devices


@router.get("/devices/{device_id}")
async def get_energy_device(device_id: str, user: dict = Depends(get_authenticated_user)):
    """Get details of a specific Messkoffer device."""
    if not check_energy_monitoring_access(user):
        raise HTTPException(status_code=403, detail="Energy Monitoring nicht freigeschaltet")

    allowed_ids = get_allowed_device_ids(user)
    if allowed_ids is not None and device_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Gerät")

    device = await db.devices.find_one({"id": device_id, "device_type": "messkoffer"}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Messkoffer nicht gefunden")

    # Get meters
    meters = await db.emu_meters.find({"device_id": device_id}, {"_id": 0}).to_list(100)
    device["meters"] = meters

    if "image_gridfs_id" in device and device["image_gridfs_id"]:
        device["image_gridfs_id"] = str(device["image_gridfs_id"])

    return device


# ============== Meter Endpoints ==============

@router.get("/devices/{device_id}/meters")
async def list_meters(device_id: str, user: dict = Depends(get_authenticated_user)):
    """List EMU meters for a Messkoffer."""
    if not check_energy_monitoring_access(user):
        raise HTTPException(status_code=403, detail="Energy Monitoring nicht freigeschaltet")

    allowed_ids = get_allowed_device_ids(user)
    if allowed_ids is not None and device_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Gerät")

    meters = await db.emu_meters.find({"device_id": device_id}, {"_id": 0}).to_list(100)
    return meters


@router.post("/devices/{device_id}/meters")
async def create_meter(device_id: str, data: MeterCreate, admin: dict = Depends(require_admin)):
    """Add an EMU meter to a Messkoffer."""
    device = await db.devices.find_one({"id": device_id, "device_type": "messkoffer"}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Messkoffer nicht gefunden")

    meter_doc = {
        "id": str(uuid.uuid4()),
        "device_id": device_id,
        "meter_ip": data.meter_ip,
        "meter_name": data.meter_name,
        "description": data.description or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.emu_meters.insert_one(meter_doc)
    result = {k: v for k, v in meter_doc.items() if k != "_id"}
    return result


@router.put("/meters/{meter_id}")
async def update_meter(meter_id: str, data: MeterUpdate, admin: dict = Depends(require_admin)):
    """Update an EMU meter."""
    meter = await db.emu_meters.find_one({"id": meter_id}, {"_id": 0})
    if not meter:
        raise HTTPException(status_code=404, detail="Zähler nicht gefunden")

    update_data = {}
    for k, v in data.dict(exclude_unset=True).items():
        if v is not None:
            update_data[k] = v

    if update_data:
        await db.emu_meters.update_one({"id": meter_id}, {"$set": update_data})

    updated = await db.emu_meters.find_one({"id": meter_id}, {"_id": 0})
    return updated


@router.delete("/meters/{meter_id}")
async def delete_meter(meter_id: str, admin: dict = Depends(require_admin)):
    """Delete an EMU meter."""
    result = await db.emu_meters.delete_one({"id": meter_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Zähler nicht gefunden")
    # Delete associated data
    await db.emu_data.delete_many({"meter_id": meter_id})
    return {"message": "Zähler gelöscht"}


# ============== Telemetry Data Endpoints ==============

@router.get("/devices/{device_id}/telemetry")
async def get_device_telemetry(
    device_id: str,
    meter_id: Optional[str] = None,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    limit: int = Query(default=500, le=5000),
    user: dict = Depends(get_authenticated_user)
):
    """Get telemetry data for a Messkoffer device (optionally filtered by meter and time range)."""
    if not check_energy_monitoring_access(user):
        raise HTTPException(status_code=403, detail="Energy Monitoring nicht freigeschaltet")

    allowed_ids = get_allowed_device_ids(user)
    if allowed_ids is not None and device_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Gerät")

    query = {"device_id": device_id}
    if meter_id:
        query["meter_id"] = meter_id

    if from_time or to_time:
        query["ts_utc"] = {}
        if from_time:
            query["ts_utc"]["$gte"] = from_time
        if to_time:
            query["ts_utc"]["$lte"] = to_time

    data = await db.emu_data.find(
        query, {"_id": 0}
    ).sort("ts_utc", -1).limit(limit).to_list(limit)

    # Return in chronological order
    data.reverse()
    return data


@router.get("/devices/{device_id}/telemetry/latest")
async def get_latest_telemetry(device_id: str, user: dict = Depends(get_authenticated_user)):
    """Get latest telemetry data per meter for a device."""
    if not check_energy_monitoring_access(user):
        raise HTTPException(status_code=403, detail="Energy Monitoring nicht freigeschaltet")

    allowed_ids = get_allowed_device_ids(user)
    if allowed_ids is not None and device_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Gerät")

    meters = await db.emu_meters.find({"device_id": device_id}, {"_id": 0}).to_list(100)

    result = []
    for meter in meters:
        latest = await db.emu_data.find_one(
            {"device_id": device_id, "meter_id": meter["id"]},
            {"_id": 0},
            sort=[("ts_utc", -1)]
        )
        result.append({
            "meter": meter,
            "latest": latest
        })

    return result


# ============== Seed Demo Data ==============

@router.post("/seed-demo")
async def seed_demo_data(admin: dict = Depends(require_admin)):
    """Seed demo EMU data for testing. Only works if no emu_data exists."""
    existing = await db.emu_data.count_documents({})
    if existing > 0:
        return {"message": "Demo-Daten bereits vorhanden", "count": existing}

    # Find Messkoffer devices
    messkoffer = await db.devices.find({"device_type": "messkoffer"}, {"_id": 0}).to_list(10)
    if not messkoffer:
        return {"message": "Keine Messkoffer vorhanden. Erstellen Sie zuerst einen Messkoffer in der Geräteverwaltung."}

    device = messkoffer[0]
    device_id = device["id"]

    # Create a demo meter
    meter_id = str(uuid.uuid4())
    meter_doc = {
        "id": meter_id,
        "device_id": device_id,
        "meter_ip": "10.210.11.198",
        "meter_name": "EMU Zähler 1",
        "description": "Hauptzähler",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    existing_meter = await db.emu_meters.find_one({"device_id": device_id, "meter_ip": "10.210.11.198"})
    if not existing_meter:
        await db.emu_meters.insert_one(meter_doc)
    else:
        meter_id = existing_meter["id"]

    # Generate 24h of demo data at 1-minute intervals
    now = datetime.now(timezone.utc)
    import random
    records = []
    for i in range(1440):  # 24 hours * 60 minutes
        ts = now - timedelta(minutes=1440 - i)
        # Simulate realistic values with daily pattern
        hour = ts.hour + ts.minute / 60.0
        # Power follows a daily curve (more usage during day)
        base_load = 2.0 + 8.0 * max(0, 1 - abs(hour - 14) / 10)
        noise = random.uniform(-0.5, 0.5)
        p_sum = max(0, base_load + noise)
        p_l1 = p_sum * random.uniform(0.3, 0.4)
        p_l2 = p_sum * random.uniform(0.28, 0.38)
        p_l3 = p_sum - p_l1 - p_l2

        u_base = 230 + random.uniform(-3, 3)
        f_hz = 50.0 + random.uniform(-0.1, 0.1)

        # Cumulative energy
        e_imp = 150.0 + (i / 1440.0) * 24 * (base_load * 0.8)

        record = {
            "id": str(uuid.uuid4()),
            "device_id": device_id,
            "meter_id": meter_id,
            "ts_utc": ts.isoformat(),
            "meter_ts": int(ts.timestamp()),
            "I_L1": round(p_l1 / (u_base * 0.001), 2) if p_l1 > 0 else 0,
            "I_L2": round(p_l2 / (u_base * 0.001), 2) if p_l2 > 0 else 0,
            "I_L3": round(p_l3 / (u_base * 0.001), 2) if p_l3 > 0 else 0,
            "I_sum": round(p_sum / (u_base * 0.001), 2) if p_sum > 0 else 0,
            "U_L1": round(u_base + random.uniform(-1, 1), 1),
            "U_L2": round(u_base + random.uniform(-1, 1), 1),
            "U_L3": round(u_base + random.uniform(-1, 1), 1),
            "F_Hz": round(f_hz, 1),
            "P_sum_kW": round(p_sum, 3),
            "P_L1_kW": round(p_l1, 3),
            "P_L2_kW": round(p_l2, 3),
            "P_L3_kW": round(p_l3, 3),
            "Q_sum": round(p_sum * random.uniform(0.1, 0.3), 3),
            "Q_L1": round(p_l1 * random.uniform(0.1, 0.3), 3),
            "Q_L2": round(p_l2 * random.uniform(0.1, 0.3), 3),
            "Q_L3": round(p_l3 * random.uniform(0.1, 0.3), 3),
            "PF_L1": round(random.uniform(0.85, 0.99), 2),
            "PF_L2": round(random.uniform(0.85, 0.99), 2),
            "PF_L3": round(random.uniform(0.85, 0.99), 2),
            "E_imp_kWh": round(e_imp, 2),
            "E_exp_kWh": 0.0,
            "http_ok": 1,
            "error": "",
        }
        records.append(record)

    # Bulk insert
    if records:
        await db.emu_data.insert_many(records)

    # Create index for efficient queries
    await db.emu_data.create_index([("device_id", 1), ("ts_utc", -1)])
    await db.emu_data.create_index([("device_id", 1), ("meter_id", 1), ("ts_utc", -1)])

    return {"message": f"Demo-Daten erstellt: {len(records)} Datensätze für {device['serial_number']}", "count": len(records)}
