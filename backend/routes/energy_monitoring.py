from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import hashlib
import hmac
import secrets
import logging
import os

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


class IngestBatch(BaseModel):
    api_key: str
    device_id: str
    meter_id: str
    records: List[dict]
    last_sync_id: Optional[int] = None


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

    # Mitarbeiter mit aktivem Hub-Modul "energy_monitoring" haben Vollzugriff
    if user["role"] == "mitarbeiter":
        modules = (user.get("apps") or {}).get("modules") or {}
        if modules.get("energy_monitoring") is not False:
            return True
        return False

    apps = user.get("apps", {})
    em = apps.get("energy_monitoring", {})
    if not em.get("enabled", False):
        return False

    # For Kunde: check account-level time-based access
    if user["role"] == "kunde":
        access_type = user.get("access_type", "permanent")
        if access_type == "temporary":
            now = datetime.now(timezone.utc)
            access_start = user.get("access_start")
            access_end = user.get("access_end")
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

    # Mitarbeiter mit aktivem Hub-Modul "energy_monitoring" sehen alle Geraete
    if user["role"] == "mitarbeiter":
        modules = (user.get("apps") or {}).get("modules") or {}
        if modules.get("energy_monitoring") is not False:
            return None
        return []

    apps = user.get("apps", {})
    em = apps.get("energy_monitoring", {})

    if em.get("access_all", False):
        return None  # All access

    return em.get("device_ids", [])


# ============== Device Endpoints ==============

@router.get("/devices")
async def list_energy_devices(
    online_only: bool = False,
    user: dict = Depends(get_authenticated_user)
):
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

    # Enrich with meter count and latest data (batch instead of N+1)
    device_ids = [d["id"] for d in devices]

    # Batch meter counts (emu_meters ist klein → Aggregation OK)
    meter_counts = {}
    if device_ids:
        mc_pipeline = [
            {"$match": {"device_id": {"$in": device_ids}}},
            {"$group": {"_id": "$device_id", "count": {"$sum": 1}}}
        ]
        meter_counts = {doc["_id"]: doc["count"] async for doc in db.emu_meters.aggregate(mc_pipeline)}

    # Latest emu_data per device — einzelne Index-Lookups statt Aggregation
    # (Aggregation wuerde Millionen Docs im RAM sortieren!)
    latest_map = {}
    for did in device_ids:
        doc = await db.emu_data.find_one(
            {"device_id": did}, {"_id": 0}, sort=[("ts_utc", -1)]
        )
        if doc:
            latest_map[did] = doc

    result = []
    for device in devices:
        device["meter_count"] = meter_counts.get(device["id"], 0)
        latest = latest_map.get(device["id"])
        device["latest_data"] = latest

        # Determine online status (has data in last 5 minutes)
        if latest and latest.get("ts_utc"):
            try:
                last_ts = datetime.fromisoformat(latest["ts_utc"].replace("Z", "+00:00"))
                device["is_online"] = (datetime.now(timezone.utc) - last_ts).total_seconds() < 300
            except (ValueError, TypeError):
                device["is_online"] = False
        else:
            device["is_online"] = False

        if "image_gridfs_id" in device and device["image_gridfs_id"]:
            device["image_gridfs_id"] = str(device["image_gridfs_id"])

        if online_only and not device["is_online"]:
            continue

        result.append(device)

    return result


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
    limit: int = Query(default=500, le=999999),
    user: dict = Depends(get_authenticated_user)
):
    """Get telemetry data for a Messkoffer device (optionally filtered by meter and time range)."""
    if not check_energy_monitoring_access(user):
        raise HTTPException(status_code=403, detail="Energy Monitoring nicht freigeschaltet")

    allowed_ids = get_allowed_device_ids(user)
    if allowed_ids is not None and device_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Gerät")

    # Enforce data access range for Kunden
    if user["role"] == "kunde":
        em = user.get("apps", {}).get("energy_monitoring", {})
        data_from = em.get("data_access_start")
        data_to = em.get("data_access_end")
        if data_from:
            if not from_time or from_time < data_from:
                from_time = data_from
        if data_to:
            if not to_time or to_time > data_to:
                to_time = data_to

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


@router.get("/data-access-range")
async def get_data_access_range(user: dict = Depends(get_authenticated_user)):
    """Get the allowed data access range for the current user (Kunden may have restrictions)."""
    if user["role"] == "kunde":
        em = user.get("apps", {}).get("energy_monitoring", {})
        return {
            "data_access_start": em.get("data_access_start"),
            "data_access_end": em.get("data_access_end"),
            "restricted": bool(em.get("data_access_start") or em.get("data_access_end"))
        }
    return {"data_access_start": None, "data_access_end": None, "restricted": False}


# ============== Device Key Management ==============

def _hash_key(plain_key: str) -> str:
    """Hash a device key using SHA-256 for storage."""
    return hashlib.sha256(plain_key.encode()).hexdigest()


def _verify_key(plain_key: str, hashed: str) -> bool:
    """Verify a key against its hash."""
    return hmac.compare_digest(hashlib.sha256(plain_key.encode()).hexdigest(), hashed)


@router.post("/devices/{device_id}/generate-key")
async def generate_device_key(device_id: str, admin: dict = Depends(require_admin)):
    """Generate a new API key for a Messkoffer device. Returns plain key once."""
    device = await db.devices.find_one({"id": device_id, "device_type": "messkoffer"}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Messkoffer nicht gefunden")

    # Generate a strong random key
    plain_key = secrets.token_hex(24)  # 48 char hex key
    key_hash = _hash_key(plain_key)

    # Store only the hash
    await db.devices.update_one(
        {"id": device_id},
        {"$set": {
            "device_key_hash": key_hash,
            "device_key_prefix": plain_key[:8],
            "device_key_created_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    return {
        "device_key": plain_key,
        "prefix": plain_key[:8],
        "message": "Schlüssel generiert. Bitte sicher aufbewahren - wird nur einmal angezeigt!"
    }


@router.get("/devices/{device_id}/key-info")
async def get_device_key_info(device_id: str, admin: dict = Depends(require_admin)):
    """Check if a device has a key configured (without revealing it)."""
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    has_key = bool(device.get("device_key_hash"))
    return {
        "has_key": has_key,
        "prefix": device.get("device_key_prefix", ""),
        "created_at": device.get("device_key_created_at", "")
    }


# ============== All-in-One Setup Script ==============

LOGGER_SCRIPT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "messkoffer_logger.py")

# Temporary storage for pre-generated setup scripts (download token -> script content)
_setup_downloads = {}


def _get_api_base(request: Request = None) -> str:
    """Determine the API base URL - always returns a FULL URL with host for Pi configs."""
    # 1. Explicit env var (highest priority)
    api_base = os.environ.get("API_BASE_URL", "")
    if api_base:
        return api_base

    # 2. FRONTEND_URL from backend .env (reliable for live server)
    frontend_url = os.environ.get("FRONTEND_URL", "")
    if frontend_url and "localhost" not in frontend_url and "127.0.0.1" not in frontend_url and "preview.emergentagent.com" not in frontend_url:
        return frontend_url.rstrip("/") + "/api"

    # 3. From the incoming request - but skip localhost (Pi needs external URL)
    if request:
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host", request.headers.get("host", ""))
        if host and "localhost" not in host and "127.0.0.1" not in host:
            return f"{scheme}://{host}/api"

    # 4. Fallback: read from frontend .env
    fe_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", ".env")
    try:
        with open(fe_env) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    val = line.split("=", 1)[1].strip()
                    if val and val != "''":
                        return val + "/api"
    except Exception:
        pass
    return "https://eventenergie.app/api"


@router.post("/devices/{device_id}/setup-script")
async def generate_setup_script(device_id: str, request: Request, admin: dict = Depends(require_admin)):
    """Generate an all-in-one bash installer: Shelly logger + GPS + local DB + portal sync.
    Returns a download token for easy wget access from the Pi."""
    device = await db.devices.find_one({"id": device_id, "device_type": "messkoffer"}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail=f"Messkoffer mit ID {device_id} nicht gefunden")

    # Generate a new device key
    plain_key = secrets.token_hex(24)
    key_hash = _hash_key(plain_key)
    await db.devices.update_one(
        {"id": device_id},
        {"$set": {
            "device_key_hash": key_hash,
            "device_key_prefix": plain_key[:8],
            "device_key_created_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    # Get or auto-create meter for this device
    meter = await db.emu_meters.find_one({"device_id": device_id}, {"_id": 0})
    if not meter:
        device_name = device.get("serial_number", device_id)
        meter = {
            "id": str(uuid.uuid4()),
            "device_id": device_id,
            "meter_ip": "192.168.88.240",
            "meter_name": f"Shelly Pro 3EM ({device_name})",
            "description": "Automatisch erstellt beim Setup",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.emu_meters.insert_one(meter)
        del meter["_id"]  # Remove MongoDB ObjectId
    meter_id = meter["id"]

    # Determine API URL
    api_base = _get_api_base(request)

    # Read the logger python script
    if not os.path.exists(LOGGER_SCRIPT_PATH):
        raise HTTPException(status_code=500, detail=f"Logger-Skript nicht gefunden: {LOGGER_SCRIPT_PATH}")
    with open(LOGGER_SCRIPT_PATH, "r", encoding="utf-8") as f:
        logger_py_content = f.read()

    device_name = device.get("serial_number", device_id)

    script = f'''#!/bin/bash
# ================================================================
#  Messkoffer Setup - Eventenergie Portal (Clean Install)
#  Geraet: {device_name}
#  Erstellt: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
# ================================================================
#
#  Nutzung:  sudo bash setup_messkoffer.sh
#
#  Was passiert:
#    0. Alte Installation komplett aufraumen
#    1. Abhaengigkeiten installieren (python3, requests, gpsd)
#    2. Logger-Skript installieren (/opt/messkoffer_logger.py)
#    3. Konfiguration schreiben (/etc/messkoffer.conf)
#    4. Systemd-Dienste einrichten (messkoffer + gpsd)
#    5. Alles starten - Shelly-Logging + GPS + Portal-Sync
#
# ================================================================

set -e

RED="\\033[0;31m"
GREEN="\\033[0;32m"
YELLOW="\\033[1;33m"
CYAN="\\033[0;36m"
NC="\\033[0m"

echo ""
echo -e "${{CYAN}}================================================${{NC}}"
echo -e "${{CYAN}}  Messkoffer Setup (Clean Install)${{NC}}"
echo -e "${{CYAN}}  Geraet: {device_name}${{NC}}"
echo -e "${{CYAN}}================================================${{NC}}"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo -e "${{RED}}Fehler: Bitte mit sudo ausfuehren:${{NC}}"
    echo "  sudo bash $0"
    exit 1
fi

# ===== SCHRITT 0: ALLES ALTE AUFRAUMEN =====
echo -e "${{YELLOW}}[0/5] Alte Installation aufraumen...${{NC}}"

# Alle bekannten Services stoppen und deaktivieren
for SVC in messkoffer emu_sync emu-sync kirmeskiste_sync shelly_logger messkoffer_logger; do
    if systemctl is-active --quiet "$SVC" 2>/dev/null; then
        echo "  Stoppe Service: $SVC"
        systemctl stop "$SVC" 2>/dev/null || true
    fi
    if systemctl is-enabled --quiet "$SVC" 2>/dev/null; then
        systemctl disable "$SVC" 2>/dev/null || true
    fi
    if [ -f "/etc/systemd/system/$SVC.service" ]; then
        echo "  Entferne Service-Datei: $SVC.service"
        rm -f "/etc/systemd/system/$SVC.service"
    fi
done

# Alle laufenden Sync-Prozesse beenden
echo "  Beende laufende Sync-Prozesse..."
pkill -f "messkoffer_logger" 2>/dev/null || true
pkill -f "emu_sync" 2>/dev/null || true
pkill -f "emu-sync" 2>/dev/null || true
pkill -f "shelly_logger" 2>/dev/null || true
sleep 2

# Alte Konfigurationsdateien entfernen
echo "  Entferne alte Konfigurationen..."
rm -f /etc/messkoffer.conf
rm -f /etc/emu_sync.conf
rm -f /etc/emu-sync.conf

# Alte SQLite-Datenbanken entfernen (Sync-Reset!)
echo "  Entferne alte Datenbanken (Sync-Reset)..."
rm -f /var/lib/messkoffer/messkoffer.sqlite
rm -f /var/lib/messkoffer/messkoffer.sqlite-wal
rm -f /var/lib/messkoffer/messkoffer.sqlite-shm

# Alte Logger-Skripte entfernen
rm -f /opt/messkoffer_logger.py
rm -f /opt/emu_sync.py
rm -f /opt/shelly_logger.py

# Bekannte alte Installationsverzeichnisse aufraumen
for OLD_DIR in /home/pi/emu-sync /home/pi/messkoffer /home/pi/emu_sync /home/pi/shelly-logger; do
    if [ -d "$OLD_DIR" ]; then
        echo "  Entferne altes Verzeichnis: $OLD_DIR"
        rm -rf "$OLD_DIR"
    fi
done

# Alte Configs in Home-Verzeichnissen entfernen
rm -f /home/pi/config.json /home/pi/.messkoffer.conf /home/pi/.emu_sync.conf 2>/dev/null || true

# Alte crontab-Eintraege entfernen
crontab -l 2>/dev/null | grep -v "messkoffer\|emu_sync\|emu-sync\|shelly" | crontab - 2>/dev/null || true

systemctl daemon-reload
echo "  Aufraumen abgeschlossen."

# ===== SCHRITT 1: ABHAENGIGKEITEN =====
echo ""
echo -e "${{YELLOW}}[1/5] Installiere Abhaengigkeiten...${{NC}}"
apt-get update -qq

# Python + requests
if ! command -v python3 &> /dev/null; then
    apt-get install -y -qq python3 python3-pip
fi
python3 -c "import requests" 2>/dev/null || pip3 install requests -q 2>/dev/null || python3 -m pip install requests -q
echo "  Python3 + requests OK"

# gpsd fuer USB-GPS
if ! command -v gpsd &> /dev/null; then
    apt-get install -y -qq gpsd gpsd-clients python3-gps
    echo "  gpsd installiert"
else
    apt-get install -y -qq python3-gps 2>/dev/null || true
    echo "  gpsd OK"
fi

# gpsd konfigurieren (USB auto-detect)
cat > /etc/default/gpsd << 'GPSD_EOF'
DEVICES=""
GPSD_OPTIONS="-n"
USBAUTO="true"
START_DAEMON="true"
GPSD_EOF
systemctl enable gpsd
systemctl restart gpsd || true
echo "  gpsd konfiguriert (USB Auto-Erkennung aktiv)"

# ===== SCHRITT 2: LOGGER-SKRIPT =====
echo -e "${{YELLOW}}[2/5] Installiere Messkoffer-Logger...${{NC}}"
mkdir -p /var/lib/messkoffer
cat > /opt/messkoffer_logger.py << 'LOGGER_EOF'
{logger_py_content}
LOGGER_EOF
chmod +x /opt/messkoffer_logger.py
echo "  /opt/messkoffer_logger.py erstellt"

# ===== SCHRITT 3: NEUE KONFIGURATION =====
echo -e "${{YELLOW}}[3/5] Schreibe neue Konfiguration...${{NC}}"
cat > /etc/messkoffer.conf << 'CONFIG_EOF'
[messkoffer]
shelly_ip = 192.168.88.240
api_url = {api_base}
device_key = {plain_key}
device_id = {device_id}
meter_id = {meter_id}
db_path = /var/lib/messkoffer/messkoffer.sqlite
log_interval = 1
sync_interval = 10
sync_batch_size = 500
retry_delay = 30
max_db_size_gb = 60
cleanup_check_interval = 300
CONFIG_EOF
chmod 644 /etc/messkoffer.conf
echo "  /etc/messkoffer.conf erstellt"

# ===== SCHRITT 4: SYSTEMD-DIENST =====
echo -e "${{YELLOW}}[4/5] Richte Systemd-Dienst ein...${{NC}}"

PI_USER="${{SUDO_USER:-pi}}"
id "$PI_USER" &>/dev/null || PI_USER="root"

# DB-Verzeichnis fuer den User freigeben
chown "$PI_USER":"$PI_USER" /var/lib/messkoffer

cat > /etc/systemd/system/messkoffer.service << SERVICE_EOF
[Unit]
Description=Messkoffer Logger - Shelly Pro 3EM + GPS + Portal Sync
After=network-online.target gpsd.service
Wants=network-online.target gpsd.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/messkoffer_logger.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
User=$PI_USER
Group=$PI_USER

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable messkoffer
echo "  messkoffer.service eingerichtet"

# ===== SCHRITT 5: STARTEN + VERIFIZIERUNG =====
echo -e "${{YELLOW}}[5/5] Starte Dienste...${{NC}}"

systemctl restart messkoffer
sleep 3

if systemctl is-active --quiet messkoffer; then
    echo ""
    echo -e "${{GREEN}}================================================${{NC}}"
    echo -e "${{GREEN}}  Setup erfolgreich! (Clean Install)${{NC}}"
    echo -e "${{GREEN}}================================================${{NC}}"
    echo ""
    echo "  Geraet:      {device_name}"
    echo "  Shelly IP:   192.168.88.240"
    echo "  Device-ID:   {device_id}"
    echo "  Meter-ID:    {meter_id}"
    echo "  Datenbank:   /var/lib/messkoffer/messkoffer.sqlite"
    echo "  Max. DB:     60 GB (aelteste werden automatisch geloescht)"
    echo "  GPS:         USB Auto-Erkennung aktiv"
    echo ""
    echo "  Was jetzt laeuft:"
    echo "    - Shelly wird jede Sekunde ausgelesen"
    echo "    - GPS-Position wird mitgespeichert"
    echo "    - Daten werden lokal gespeichert (auch ohne Internet)"
    echo "    - Bei Internet-Verbindung: automatischer Sync zum Portal"
    echo ""
    echo "  Befehle:"
    echo "    Live-Log:   sudo journalctl -u messkoffer -f"
    echo "    Status:     sudo systemctl status messkoffer"
    echo "    Neustart:   sudo systemctl restart messkoffer"
    echo "    DB-Groesse: du -sh /var/lib/messkoffer/"
    echo ""
    echo -e "${{GREEN}}  HINWEIS: Alte Installation wurde vollstaendig entfernt.${{NC}}"
    echo -e "${{GREEN}}  Alle alten Configs, Datenbanken und Services geloescht.${{NC}}"
    echo ""
else
    echo ""
    echo -e "${{RED}}Dienst laeuft nicht. Pruefe:${{NC}}"
    echo "  sudo journalctl -u messkoffer -n 30"
    echo ""
    echo "  Haeufige Ursachen:"
    echo "  - Shelly nicht erreichbar (ping 192.168.88.240)"
    echo "  - Python-Modul fehlt"
    echo ""
fi
'''

    # Ensure Unix line endings (LF only, no CRLF)
    script = script.replace('\r\n', '\n').replace('\r', '\n')

    # Store script with a download token (valid for 1 hour)
    download_token = secrets.token_urlsafe(16)
    _setup_downloads[download_token] = {
        "script": script,
        "created_at": datetime.now(timezone.utc),
        "device_name": device_name,
    }

    # Clean up old tokens (older than 1 hour)
    now = datetime.now(timezone.utc)
    expired = [k for k, v in _setup_downloads.items() if (now - v["created_at"]).total_seconds() > 3600]
    for k in expired:
        del _setup_downloads[k]

    return {
        "download_token": download_token,
        "download_url": f"{api_base}/energy-monitoring/setup-download/{download_token}",
        "device_name": device_name,
    }


@router.get("/setup-download/{token}")
async def download_setup_script(token: str):
    """Public download endpoint for setup script using a temporary token."""
    entry = _setup_downloads.get(token)
    if not entry:
        raise HTTPException(status_code=404, detail="Download-Link abgelaufen oder ungueltig")

    # Check expiry (1 hour)
    created = entry["created_at"]
    if isinstance(created, str):
        created = datetime.fromisoformat(created.replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - created).total_seconds()
    if age > 3600:
        del _setup_downloads[token]
        raise HTTPException(status_code=410, detail="Download-Link abgelaufen")

    return PlainTextResponse(
        content=entry["script"],
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="setup.sh"'}
    )



# ============== Kirmeskiste Setup ==============

class KirmeskisteSetupRequest(BaseModel):
    meter_ips: list[str] = ["192.168.88.240", "192.168.88.241", "192.168.88.242", "192.168.88.243"]

@router.post("/devices/{device_id}/kirmeskiste-setup")
async def generate_kirmeskiste_setup(device_id: str, request: Request, body: KirmeskisteSetupRequest = None, admin: dict = Depends(require_admin)):
    """Generate an all-in-one bash installer for Kirmeskiste with 4x EMU Pro II meters."""
    if body is None:
        body = KirmeskisteSetupRequest()

    # Determine API URL
    api_base = _get_api_base(request)

    device = await db.devices.find_one({"id": device_id, "device_type": "kirmeskiste"}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Kirmeskiste nicht gefunden")

    # Generate a new device key
    plain_key = secrets.token_hex(24)
    key_hash = _hash_key(plain_key)
    await db.devices.update_one(
        {"id": device_id},
        {"$set": {"device_key_hash": key_hash, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    # Create 4 meters (if not already existing)
    meter_ids = []
    existing_meters = await db.emu_meters.find({"device_id": device_id}, {"_id": 0}).to_list(10)
    existing_by_ip = {m.get("meter_ip", ""): m for m in existing_meters}

    for i, ip in enumerate(body.meter_ips[:4]):
        if ip in existing_by_ip:
            meter_ids.append(existing_by_ip[ip]["id"])
        else:
            meter_id = str(uuid.uuid4())
            await db.emu_meters.insert_one({
                "id": meter_id,
                "device_id": device_id,
                "meter_name": f"EMU Zaehler {i+1}",
                "meter_ip": ip,
                "meter_port": 502,
                "meter_type": "EMU Professional II 3/5",
                "modbus_slave_id": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            meter_ids.append(meter_id)

    # Update device with meter count
    await db.devices.update_one(
        {"id": device_id},
        {"$set": {"meter_count": len(meter_ids)}}
    )

    # Get API URL
    api_url = _get_api_base(request)

    # Read the kirmeskiste_sync.py template
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "kirmeskiste_sync.py")
    with open(script_path, "r") as f:
        sync_script = f.read()

    # Build meter config sections
    meter_conf_sections = ""
    for i, (ip, mid) in enumerate(zip(body.meter_ips[:4], meter_ids)):
        meter_conf_sections += f"""
[meter_{i+1}]
meter_id = {mid}
ip = {ip}
port = 502
slave_id = 1
name = Zaehler {i+1}
"""

    # Generate the all-in-one setup script
    bash_script = f"""#!/bin/bash
# ==============================================================
#  Kirmeskiste Auto-Setup - {device.get('serial_number', device_id[:12])}
#  Generiert am {datetime.now().strftime('%d.%m.%Y %H:%M')}
#  4x EMU Professional II 3/5 via Modbus TCP
# ==============================================================
set -e

echo "========================================================"
echo "  Kirmeskiste Auto-Setup (Clean Install)"
echo "  Geraet: {device.get('serial_number', device_id[:12])}"
echo "========================================================"

# ===== SCHRITT 0: ALLES ALTE AUFRAUMEN =====
echo ""
echo "[0/6] Alte Installation aufraumen..."

# Alle bekannten Kirmeskiste-Services stoppen und deaktivieren
for SVC in kirmeskiste_sync kirmeskiste emu_sync emu-sync; do
    if systemctl is-active --quiet "$SVC" 2>/dev/null; then
        echo "  Stoppe Service: $SVC"
        sudo systemctl stop "$SVC" 2>/dev/null || true
    fi
    if systemctl is-enabled --quiet "$SVC" 2>/dev/null; then
        sudo systemctl disable "$SVC" 2>/dev/null || true
    fi
    if [ -f "/etc/systemd/system/$SVC.service" ]; then
        echo "  Entferne Service-Datei: $SVC.service"
        sudo rm -f "/etc/systemd/system/$SVC.service"
    fi
done

# Alle laufenden kirmeskiste/emu_sync Python-Prozesse beenden
echo "  Beende laufende Sync-Prozesse..."
sudo pkill -f "kirmeskiste_sync" 2>/dev/null || true
sudo pkill -f "emu_sync" 2>/dev/null || true
sudo pkill -f "emu-sync" 2>/dev/null || true
sleep 2

# Alte Konfigurationsdateien entfernen
echo "  Entferne alte Konfigurationen..."
sudo rm -f /etc/kirmeskiste.conf
sudo rm -f /etc/emu_sync.conf
sudo rm -f /etc/emu-sync.conf

# Alte SQLite-Datenbanken entfernen (Reset der Sync-States!)
echo "  Entferne alte Datenbanken (Sync-Reset)..."
sudo rm -f /var/lib/kirmeskiste/kirmeskiste.sqlite
sudo rm -f /var/lib/kirmeskiste/kirmeskiste.sqlite-wal
sudo rm -f /var/lib/kirmeskiste/kirmeskiste.sqlite-shm

# Bekannte alte Installationsverzeichnisse aufraumen
for OLD_DIR in /home/pi/emu-sync /home/pi/kirmeskiste /home/pi/emu_sync; do
    if [ -d "$OLD_DIR" ]; then
        echo "  Entferne altes Verzeichnis: $OLD_DIR"
        sudo rm -rf "$OLD_DIR"
    fi
done

# Alte Configs in Home-Verzeichnissen entfernen
sudo rm -f /home/pi/config.json /home/pi/.kirmeskiste.conf 2>/dev/null || true

# Alte crontab-Eintraege entfernen (falls vorhanden)
crontab -l 2>/dev/null | grep -v "kirmeskiste\|emu_sync\|emu-sync" | crontab - 2>/dev/null || true

sudo systemctl daemon-reload
echo "  Aufraumen abgeschlossen."

# ===== SCHRITT 1: SYSTEM AKTUALISIEREN =====
echo ""
echo "[1/6] System aktualisieren..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv gpsd gpsd-clients

# ===== SCHRITT 2: PYTHON-UMGEBUNG =====
echo "[2/6] Python-Umgebung einrichten..."
INSTALL_DIR="/opt/kirmeskiste"
sudo rm -rf "$INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"
sudo python3 -m venv "$INSTALL_DIR/venv"
sudo "$INSTALL_DIR/venv/bin/pip" install --quiet "pymodbus>=3.7" requests gpsd-py3 pyusb pyserial

# ===== SCHRITT 3: SYNC-SKRIPT =====
echo "[3/6] Sync-Skript installieren..."
sudo tee "$INSTALL_DIR/kirmeskiste_sync.py" > /dev/null << 'SYNC_SCRIPT'
{sync_script}
SYNC_SCRIPT
sudo chmod +x "$INSTALL_DIR/kirmeskiste_sync.py"

# ===== SCHRITT 4: NEUE KONFIGURATION =====
echo "[4/6] Neue Konfiguration schreiben..."
sudo mkdir -p /var/lib/kirmeskiste

sudo tee /etc/kirmeskiste.conf > /dev/null << 'CONF'
[kirmeskiste]
api_url = {api_url}
device_key = {plain_key}
device_id = {device_id}
db_path = /var/lib/kirmeskiste/kirmeskiste.sqlite
read_interval = 1
sync_interval = 30
retry_delay = 30
batch_size = 500
{meter_conf_sections}
CONF

sudo chmod 600 /etc/kirmeskiste.conf

# ===== SCHRITT 5: SYSTEMD SERVICE =====
echo "[5/6] Systemd-Service einrichten..."
sudo tee /etc/systemd/system/kirmeskiste_sync.service > /dev/null << 'SERVICE'
[Unit]
Description=Kirmeskiste Sync - Eventenergie Portal
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/opt/kirmeskiste/venv/bin/python3 /opt/kirmeskiste/kirmeskiste_sync.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
WorkingDirectory=/opt/kirmeskiste

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable kirmeskiste_sync
sudo systemctl restart kirmeskiste_sync

# ===== SCHRITT 6: VERIFIZIERUNG =====
echo "[6/6] Verifiziere Installation..."
sleep 3
if systemctl is-active --quiet kirmeskiste_sync; then
    echo "  Service laeuft!"
else
    echo "  WARNUNG: Service ist nicht aktiv!"
    echo "  Pruefe mit: sudo journalctl -u kirmeskiste_sync -n 20"
fi

echo ""
echo "========================================================"
echo "  Setup abgeschlossen! (Clean Install)"
echo "========================================================"
echo ""
echo "  Geraet-ID:     {device_id}"
echo "  Geraet-Key:    {plain_key[:8]}..."
echo "  Portal:        {api_url}"
echo "  Konfiguration: /etc/kirmeskiste.conf"
echo "  Datenbank:     /var/lib/kirmeskiste/kirmeskiste.sqlite"
echo ""
echo "  Zaehler:"
"""
    for i, (ip, mid) in enumerate(zip(body.meter_ips[:4], meter_ids)):
        bash_script += f'echo "    Zaehler {i+1}: {ip} -> {mid[:12]}..."\n'

    bash_script += """echo ""
echo "  Service pruefen:"
echo "    sudo systemctl status kirmeskiste_sync"
echo "    sudo journalctl -u kirmeskiste_sync -f"
echo ""
echo "  HINWEIS: Alte Installation wurde vollstaendig entfernt."
echo "  Alle alten Configs, Datenbanken und Services wurden geloescht."
echo ""
"""

    # Store script for download
    download_token = secrets.token_urlsafe(32)
    _setup_downloads[download_token] = {
        "script": bash_script,
        "device_id": device_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }

    download_url = f"{api_base}/energy-monitoring/setup-download/{download_token}"

    return {
        "download_url": download_url,
        "download_token": download_token,
        "device_id": device_id,
        "device_key": plain_key,
        "meter_ids": meter_ids,
        "meter_ips": body.meter_ips[:4],
        "message": f"Setup-Skript generiert fuer {device.get('serial_number', '')}",
    }


# ============== Pi-Health (Dashboard-Daten von der Pi) ==============

class PiHealthRequest(BaseModel):
    api_key: str
    device_id: str
    health: dict


@router.post("/pi-health")
async def pi_health_push(body: PiHealthRequest):
    """Pi-Sync-Skript pusht alle 60s LTE/GPS/HAT-Status fuer das Dashboard."""
    device = await db.devices.find_one({"id": body.device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Geraet nicht gefunden")
    key_hash = device.get("device_key_hash")
    if not key_hash or not _verify_key(body.api_key, key_hash):
        raise HTTPException(status_code=401, detail="Ungueltiger Geraeteschluessel")

    pi_health = dict(body.health or {})
    pi_health["received_at"] = datetime.now(timezone.utc).isoformat()

    await db.devices.update_one(
        {"id": body.device_id},
        {"$set": {"pi_health": pi_health,
                  "pi_health_updated_at": pi_health["received_at"]}}
    )
    return {"ok": True}


# ============== Kirmeskiste 8 Zaehler (S0-Pulse via Sequent HAT) Setup ==============

class Kirmeskiste8zSetupRequest(BaseModel):
    lte_apn: str = "internet.m2mportal.de"
    lte_pin: str = "0000"          # SIM-PIN (Telekom M2M Standard)
    lte_user: str = ""              # i.d.R. leer bei Telekom M2M
    lte_password: str = ""          # i.d.R. leer bei Telekom M2M
    enable_lte: bool = True
    enable_gps: bool = True
    lte_uart: bool = False          # Default: USB-Modus via micro-USB-Kabel zum HAT
                                    # (dort enumeriert das SIM7600 als 1e0e:9001 mit
                                    # /dev/ttyUSB0..4; PPP laeuft ueber ttyUSB3).
                                    # True = UART-Modus ueber Pi-GPIO/ttyAMA0
                                    # (nur wenn KEIN USB-Datenkabel verfuegbar).


class MeterOffsetUpdate(BaseModel):
    kwh_offset: float


@router.put("/devices/{device_id}/meters/{meter_id}/kwh-offset")
async def update_meter_kwh_offset(
    device_id: str, meter_id: str, body: MeterOffsetUpdate,
    user: dict = Depends(require_staff)
):
    """Setzt den Anfangs-kWh-Stand fuer einen S0-Zaehler (Kirmeskiste 8Z).
    Wird einmal beim Aufstellen der Kirmeskiste vom Display abgelesen und im Portal eingetragen."""
    meter = await db.emu_meters.find_one({"id": meter_id, "device_id": device_id}, {"_id": 0})
    if not meter:
        raise HTTPException(status_code=404, detail="Zaehler nicht gefunden")
    await db.emu_meters.update_one(
        {"id": meter_id, "device_id": device_id},
        {"$set": {
            "kwh_offset": float(body.kwh_offset),
            "kwh_offset_updated_at": datetime.now(timezone.utc).isoformat(),
            "kwh_offset_updated_by": user.get("name", ""),
        }}
    )
    return {"meter_id": meter_id, "kwh_offset": float(body.kwh_offset)}


@router.get("/devices/{device_id}/meters/{meter_id}/kwh-offset")
async def get_meter_kwh_offset(device_id: str, meter_id: str, api_key: str = ""):
    """Pi laedt den vom Portal eingestellten kWh-Anfangsstand. Auth via device api_key."""
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Geraet nicht gefunden")
    key_hash = device.get("device_key_hash")
    if not key_hash or not _verify_key(api_key, key_hash):
        raise HTTPException(status_code=401, detail="Ungueltiger Geraeteschluessel")
    meter = await db.emu_meters.find_one({"id": meter_id, "device_id": device_id}, {"_id": 0})
    if not meter:
        raise HTTPException(status_code=404, detail="Zaehler nicht gefunden")
    return {"meter_id": meter_id, "kwh_offset": float(meter.get("kwh_offset") or 0.0)}


@router.post("/devices/{device_id}/kirmeskiste-8z-setup")
async def generate_kirmeskiste_8z_setup(
    device_id: str, request: Request,
    body: Kirmeskiste8zSetupRequest = None,
    admin: dict = Depends(require_admin)
):
    """Generate an all-in-one bash installer for Kirmeskiste 8Z (Pi 5 + Sequent HAT + SIM7600)."""
    if body is None:
        body = Kirmeskiste8zSetupRequest()

    api_base = _get_api_base(request)

    device = await db.devices.find_one({
        "id": device_id, "device_type": "kirmeskiste",
        "kirmeskiste_variant": "8z",
    }, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Kirmeskiste 8Z nicht gefunden")

    # Geraete-Key generieren
    plain_key = secrets.token_hex(24)
    key_hash = _hash_key(plain_key)
    await db.devices.update_one(
        {"id": device_id},
        {"$set": {"device_key_hash": key_hash, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    # 8 Meter anlegen (oder bestehende uebernehmen, sortiert nach hat_channel)
    existing = await db.emu_meters.find({"device_id": device_id}, {"_id": 0}).to_list(20)
    by_channel = {m.get("hat_channel"): m for m in existing if m.get("hat_channel")}

    meter_ids = []
    for ch in range(1, 9):
        if ch in by_channel:
            mid = by_channel[ch]["id"]
        else:
            mid = str(uuid.uuid4())
            await db.emu_meters.insert_one({
                "id": mid,
                "device_id": device_id,
                "meter_name": f"Zaehler {ch}",
                "meter_ip": "",
                "meter_type": "ABB D11/D13 (S0 Pulse)",
                "hat_channel": ch,
                "pulses_per_kwh": 1000,
                "kwh_offset": 0.0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        meter_ids.append(mid)

    await db.devices.update_one(
        {"id": device_id},
        {"$set": {"meter_count": len(meter_ids)}}
    )

    # Sync-Skript laden
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "kirmeskiste8z_sync.py")
    with open(script_path, "r") as f:
        sync_script = f.read()

    # Meter-Config
    meter_conf_sections = ""
    for ch, mid in enumerate(meter_ids, start=1):
        meter_conf_sections += f"""
[meter_{ch}]
meter_id = {mid}
channel = {ch}
pulses_per_kwh = 1000
name = Zaehler {ch}
"""

    serial = device.get("serial_number", device_id[:12])
    api_url = api_base
    enable_gps = "true" if body.enable_gps else "false"
    enable_lte_str = "true" if body.enable_lte else "false"
    lte_uart_str = "true" if body.lte_uart else "false"
    lte_apn = body.lte_apn
    lte_pin = body.lte_pin or "0000"
    lte_user = body.lte_user or ""
    lte_pwd = body.lte_password or ""
    # PPP-Auth-Zeilen vorbereiten (kein verschachteltes f-string)
    ppp_user_line = f"user {lte_user}" if lte_user else "noauth"
    ppp_pwd_line = f"password {lte_pwd}" if lte_pwd else ""
    # Fuer printf-basierte Peers-Datei: entweder Zeile oder leer (entfaellt)
    ppp_user_line_quoted = f"'{ppp_user_line}'" if ppp_user_line else ""
    ppp_pwd_line_quoted = f"'{ppp_pwd_line}'" if ppp_pwd_line else ""
    # Bei UART (Waveshare): PPP ueber /dev/ttyAMA0; bei USB: stabile udev-Symlinks.
    # SIM7600-USB-Composite (1e0e:9001) hat 5 Interfaces:
    #   Interface 00 = DIAG     -> /dev/sim7600-diag
    #   Interface 01 = NMEA/GPS -> /dev/sim7600-nmea
    #   Interface 02 = AT       -> /dev/sim7600-at
    #   Interface 03 = PPP/Modem-> /dev/sim7600-ppp  (wird fuer pppd verwendet)
    #   Interface 04 = Audio    -> /dev/sim7600-audio
    # Die tatsaechlichen ttyUSBN-Nummern sind NICHT stabil (Kernel kann z.B.
    # ttyUSB2 ueberspringen). Daher verwenden wir udev-Symlinks nach Interface-Nr.
    ppp_device = "/dev/ttyAMA0" if body.lte_uart else "/dev/sim7600-ppp"
    # AT-Port fuer PIN/CGPS-Befehle:
    at_port = "/dev/ttyAMA0" if body.lte_uart else "/dev/sim7600-at"
    # NMEA/GPS-Port:
    nmea_port = "/dev/ttyAMA0" if body.lte_uart else "/dev/sim7600-nmea"

    bash_script = f"""#!/bin/bash
# ==============================================================
#  Kirmeskiste 8 Zaehler Auto-Setup - {serial}
#  Generiert am {datetime.now().strftime('%d.%m.%Y %H:%M')}
#  Pi 5 + Sequent 16-LV HAT + SIM7600 LTE/GPS + 8x ABB D11/D13 (S0)
# ==============================================================
set -e

echo "========================================================"
echo "  Kirmeskiste 8 Zaehler Setup (Clean Install)"
echo "  Geraet: {serial}"
echo "========================================================"

# ===== SCHRITT 0: ALTE INSTALLATIONEN AUFRAUMEN =====
echo ""
echo "[0/8] Alte Installationen aufraumen..."
for SVC in kirmeskiste8z_sync sequent-init kirmeskiste_sync emu_sync sim7600-autoboot sim7600-gps-enable; do
    if systemctl is-active --quiet "$SVC" 2>/dev/null; then
        echo "  Stoppe Service: $SVC"
        sudo systemctl stop "$SVC" 2>/dev/null || true
    fi
    if systemctl is-enabled --quiet "$SVC" 2>/dev/null; then
        sudo systemctl disable "$SVC" 2>/dev/null || true
    fi
    if [ -f "/etc/systemd/system/$SVC.service" ]; then
        echo "  Entferne Service-Datei: $SVC.service"
        sudo rm -f "/etc/systemd/system/$SVC.service"
    fi
done
sudo rm -f /etc/kirmeskiste8z.conf
sudo rm -f /var/lib/kirmeskiste8z/kirmeskiste8z.sqlite
sudo rm -f /var/lib/kirmeskiste8z/kirmeskiste8z.sqlite-wal
sudo rm -f /var/lib/kirmeskiste8z/kirmeskiste8z.sqlite-shm
sudo systemctl daemon-reload

# ===== SCHRITT 1: SYSTEM AKTUALISIEREN =====
echo "[1/8] System aktualisieren..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv git build-essential i2c-tools \\
    gpsd gpsd-clients python3-gpiozero python3-lgpio

# ===== SCHRITT 2: I2C AKTIVIEREN =====
echo "[2/8] I2C aktivieren..."
sudo raspi-config nonint do_i2c 0 || true

# ===== SCHRITT 3: SEQUENT 16-LV CLI INSTALLIEREN =====
echo "[3/8] Sequent 16-LV HAT CLI installieren..."
TMPDIR_SEQUENT=$(mktemp -d)
git clone --depth=1 https://github.com/SequentMicrosystems/16inpind-rpi.git "$TMPDIR_SEQUENT/16inpind-rpi" 2>/dev/null || true
if [ -d "$TMPDIR_SEQUENT/16inpind-rpi" ]; then
    cd "$TMPDIR_SEQUENT/16inpind-rpi"
    sudo make install
    cd -
    rm -rf "$TMPDIR_SEQUENT"
else
    echo "  WARNUNG: Sequent CLI Repo nicht erreichbar, Setup mit vorhandener Installation fortfahren."
fi
test -x /usr/local/bin/16inpind || {{ echo "FEHLER: 16inpind nicht installiert"; exit 1; }}

# ===== SCHRITT 4: PYTHON VENV =====
echo "[4/8] Python-Umgebung..."
INSTALL_DIR="/opt/kirmeskiste8z"
sudo rm -rf "$INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"
sudo python3 -m venv --system-site-packages "$INSTALL_DIR/venv"
sudo "$INSTALL_DIR/venv/bin/pip" install --quiet requests gpsd-py3

# ===== SCHRITT 5: SYNC-SKRIPT =====
echo "[5/8] Sync-Skript installieren..."
sudo tee "$INSTALL_DIR/kirmeskiste8z_sync.py" > /dev/null << 'SYNC_SCRIPT'
{sync_script}
SYNC_SCRIPT
sudo chmod +x "$INSTALL_DIR/kirmeskiste8z_sync.py"

# ===== SCHRITT 6: KONFIGURATION + LTE (Telekom M2M) =====
echo "[6/8] Konfiguration schreiben..."
sudo mkdir -p /var/lib/kirmeskiste8z

sudo tee /etc/kirmeskiste8z.conf > /dev/null << 'CONF'
[kirmeskiste8z]
api_url = {api_url}
device_key = {plain_key}
device_id = {device_id}
db_path = /var/lib/kirmeskiste8z/kirmeskiste8z.sqlite
read_interval = 10
sync_interval = 60
retry_delay = 30
batch_size = 500
gps_enabled = {enable_gps}
{meter_conf_sections}
CONF
sudo chmod 600 /etc/kirmeskiste8z.conf

# ===== LTE (SIM7600 + PPP + Telekom M2M) =====
if [ "{enable_lte_str}" = "true" ]; then
    LTE_DEVICE="{ppp_device}"
    LTE_UART="{lte_uart_str}"
    AT_PORT="{at_port}"
    echo "  Konfiguriere LTE (APN={lte_apn}, PIN={lte_pin}, Device=$LTE_DEVICE)..."

    # ModemManager kann blockieren -> hart deaktivieren
    sudo systemctl stop ModemManager 2>/dev/null || true
    sudo systemctl disable ModemManager 2>/dev/null || true
    sudo systemctl mask ModemManager 2>/dev/null || true

    # Pakete fuer PPP + Werkzeuge
    sudo apt-get install -y -qq ppp ifmetric dnsutils

    # ===== udev-Rule: Stabile Symlinks fuer SIM7600 USB-Interfaces =====
    # Der Linux-Kernel kann ttyUSB-Nummern ueberspringen (z.B. ttyUSB0,1,3,4,5
    # wenn ttyUSB2 vorher belegt war). Stattdessen binden wir Symlinks an die
    # bInterfaceNumber des USB-Composite-Devices - das ist stabil.
    if [ "$LTE_UART" != "true" ]; then
        echo "    Installiere udev-Rule fuer stabile SIM7600-Symlinks..."
        sudo tee /etc/udev/rules.d/99-sim7600.rules > /dev/null << 'UDEVRULE'
# SIM7600 Waveshare HAT - stabile Symlinks nach USB-Interface-Nr
# Das Modem meldet sich als 1e0e:9001 (Qualcomm/SimTech). bInterfaceNumber
# ist stabil, ttyUSBN-Enumeration nicht (Kernel kann Nummern ueberspringen).
SUBSYSTEM=="tty", ATTRS{{idVendor}}=="1e0e", ATTRS{{idProduct}}=="9001", ENV{{ID_USB_INTERFACE_NUM}}=="00", SYMLINK+="sim7600-diag", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{{idVendor}}=="1e0e", ATTRS{{idProduct}}=="9001", ENV{{ID_USB_INTERFACE_NUM}}=="01", SYMLINK+="sim7600-nmea", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{{idVendor}}=="1e0e", ATTRS{{idProduct}}=="9001", ENV{{ID_USB_INTERFACE_NUM}}=="02", SYMLINK+="sim7600-at", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{{idVendor}}=="1e0e", ATTRS{{idProduct}}=="9001", ENV{{ID_USB_INTERFACE_NUM}}=="03", SYMLINK+="sim7600-ppp", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{{idVendor}}=="1e0e", ATTRS{{idProduct}}=="9001", ENV{{ID_USB_INTERFACE_NUM}}=="04", SYMLINK+="sim7600-audio", GROUP="dialout", MODE="0660"
# Auch fuer spaetere SIM7600E-Firmwarevarianten (Product-ID 9011)
SUBSYSTEM=="tty", ATTRS{{idVendor}}=="1e0e", ATTRS{{idProduct}}=="9011", ENV{{ID_USB_INTERFACE_NUM}}=="00", SYMLINK+="sim7600-diag", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{{idVendor}}=="1e0e", ATTRS{{idProduct}}=="9011", ENV{{ID_USB_INTERFACE_NUM}}=="01", SYMLINK+="sim7600-nmea", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{{idVendor}}=="1e0e", ATTRS{{idProduct}}=="9011", ENV{{ID_USB_INTERFACE_NUM}}=="02", SYMLINK+="sim7600-at", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{{idVendor}}=="1e0e", ATTRS{{idProduct}}=="9011", ENV{{ID_USB_INTERFACE_NUM}}=="03", SYMLINK+="sim7600-ppp", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{{idVendor}}=="1e0e", ATTRS{{idProduct}}=="9011", ENV{{ID_USB_INTERFACE_NUM}}=="04", SYMLINK+="sim7600-audio", GROUP="dialout", MODE="0660"
UDEVRULE
        sudo udevadm control --reload-rules
        sudo udevadm trigger --subsystem-match=tty 2>/dev/null || true
        echo "    OK: udev-Symlinks installiert (/dev/sim7600-diag,nmea,at,ppp,audio)"
    fi

    # UART-Modus: Pi-UART aktivieren + Console-Login auf serial0 deaktivieren
    if [ "$LTE_UART" = "true" ]; then
        BOOT_CFG=/boot/firmware/config.txt
        [ -f "$BOOT_CFG" ] || BOOT_CFG=/boot/config.txt
        if [ -f "$BOOT_CFG" ]; then
            grep -q '^enable_uart=1' "$BOOT_CFG" || echo 'enable_uart=1' | sudo tee -a "$BOOT_CFG" > /dev/null
            # Bluetooth-UART deaktivieren auf Pi 4/5, damit ttyAMA0 = primary UART
            grep -q '^dtoverlay=disable-bt' "$BOOT_CFG" || echo 'dtoverlay=disable-bt' | sudo tee -a "$BOOT_CFG" > /dev/null
        fi
        # Serial-getty (Console-Login auf UART) abschalten
        sudo systemctl disable --now serial-getty@ttyAMA0.service 2>/dev/null || true
        sudo systemctl disable --now serial-getty@serial0.service 2>/dev/null || true
        # cmdline.txt: console=serial0,... entfernen
        CMDLINE=/boot/firmware/cmdline.txt
        [ -f "$CMDLINE" ] || CMDLINE=/boot/cmdline.txt
        if [ -f "$CMDLINE" ]; then
            sudo sed -i 's/console=serial0,[0-9]* //g; s/console=ttyAMA0,[0-9]* //g' "$CMDLINE"
        fi
    fi

    # SIM7600 Auto-Power-On: Wir verlassen uns auf die HARDWARE-Loesung ueber
    # den PWR-Jumper des Waveshare-HAT (Werkseinstellung: PWR-3V3 = Auto-Boot).
    # Der GPIO-4-PWRKEY-Puls vom Pi wird durch den Sequent-HAT elektrisch
    # blockiert und funktioniert nicht. Ein Software-Autoboot-Service ist
    # damit UEBERFLUESSIG - der SIM7600 faehrt automatisch bei jedem 5V-An-
    # Zyklus hoch, solange der PWR-Jumper des Boards auf 3V3 gesteckt ist.
    echo "    INFO: SIM7600 Auto-Boot via Hardware-Jumper PWR-3V3 (Waveshare-Default)"
    echo "    -> Modul bootet immer, sobald 5V anliegen. Kein GPIO-Puls noetig."
    echo "    -> Pruefe: PWR-Jumper steht zwischen PWR und 3V3 (NICHT auf D6)"

    # Einmaliger Check ob das Modul hochkommt - wenn nicht, ist Jumper falsch
    echo "    Warte bis zu 30s auf SIM7600 USB-Enumeration..."
    for SEC in $(seq 1 30); do
        if lsusb 2>/dev/null | grep -qE '1e0e:(9001|9011)'; then
            echo "    OK: SIM7600 online nach $SEC s"
            break
        fi
        sleep 1
    done
    if ! lsusb 2>/dev/null | grep -qE '1e0e:(9001|9011)'; then
        echo "    WARNUNG: SIM7600 kommt nicht hoch. Moegliche Ursachen:"
        echo "      - PWR-Jumper steht nicht auf 3V3 (muss fuer Auto-Boot!)"
        echo "      - USB-Datenkabel zwischen Pi und HAT fehlt/defekt"
        echo "      - Board hat keinen Strom (PWR-LED pruefen)"
        echo "    Setup laeuft weiter - manueller PWRKEY-Druck + neuer Reboot hilft."
    fi
    if [ -e "$LTE_DEVICE" ]; then
        echo "    OK: $LTE_DEVICE verfuegbar"
    else
        echo "    WARNUNG: $LTE_DEVICE noch nicht da."
    fi

    # USB-Composite-Stack pruefen (Hauptindikator dass Modem voll erkannt ist)
    if lsusb | grep -qiE '1e0e:9001|simtech|qualcomm/ option'; then
        echo "    OK: SIM7600 USB-Stack erkannt (lsusb zeigt 1e0e:9001)"
    else
        echo "    WARNUNG: SIM7600 USB-Stack NICHT erkannt!"
        echo "      lsusb zeigt KEIN 1e0e:9001 - das bedeutet das USB-Datenkabel"
        echo "      zwischen Pi-USB-A-Port und HAT 'USB'-Buchse fehlt oder ist defekt."
        echo "      Bitte Datenkabel pruefen (Ladekabel ohne Datenleitungen reichen NICHT)."
    fi

    # PPP + Chat-Skript schreiben (mit SIM-PIN!)
    sudo mkdir -p /etc/chatscripts /etc/ppp/peers /etc/ppp/ip-up.d /etc/ppp/ip-down.d

    # peers-Datei: Device + Baudrate als erste Zeile (Standard pppd-Konvention).
    # WICHTIG: pppd 2.5.2 liefert eine irrefuehrende "unrecognized option"-
    # Fehlermeldung, wenn das Device zum Aufrufzeitpunkt NICHT als Character-
    # Device existiert. Die udev-Symlinks (/dev/sim7600-ppp) werden aber erst
    # aktiv, sobald der SIM7600 USB-enumeriert ist. Der lte-wait-device-Helper
    # wartet daher aktiv bis zum Erscheinen des Symlinks.
    sudo bash -c "printf '%s\n' '{ppp_device} 115200' 'connect \"/usr/sbin/chat -v -f /etc/chatscripts/m2m-connect\"' {ppp_user_line_quoted} {ppp_pwd_line_quoted} 'nodefaultroute' 'noipdefault' 'noipv6' 'novj' 'novjccomp' 'noccp' 'ipcp-accept-local' 'ipcp-accept-remote' 'local' 'lock' 'persist' 'maxfail 0' 'holdoff 10' 'lcp-echo-interval 30' 'lcp-echo-failure 4' 'debug' > /etc/ppp/peers/m2m"

    # Chat-Skript: aus Data-Mode raushebeln (+++/ATH), dann PIN, APN, Dial *99#
    sudo tee /etc/chatscripts/m2m-connect > /dev/null << 'CHATSCRIPT'
ABORT 'BUSY'
ABORT 'NO CARRIER'
ABORT 'ERROR'
ABORT 'NO ANSWER'
TIMEOUT 30
'' '\d\d+++'
'' '\dATH\r'
'' AT
OK ATZ
OK 'AT+CMEE=2'
OK 'AT+CPIN?'
OK-AT+CPIN={lte_pin}-OK 'AT+CGDCONT=1,"IP","{lte_apn}"'
OK ATD*99#
CONNECT ''
CHATSCRIPT

    sudo chmod 644 /etc/ppp/peers/m2m /etc/chatscripts/m2m-connect

    # PPP-Hooks: LTE-Route mit hoher Metric (eth0/wlan0 bleiben Default)
    sudo tee /etc/ppp/ip-up.d/10-add-lte-route > /dev/null << 'PPPHOOK1'
#!/bin/sh
# Route via ppp0 als Backup (Metric 700, hoeher als eth0=100, wlan0=600)
ip route add default dev "$IFNAME" metric 700 2>/dev/null || true
PPPHOOK1

    sudo tee /etc/ppp/ip-down.d/10-remove-lte-route > /dev/null << 'PPPHOOK1D'
#!/bin/sh
ip route del default dev "$IFNAME" 2>/dev/null || true
PPPHOOK1D

    sudo chmod +x /etc/ppp/ip-up.d/10-add-lte-route /etc/ppp/ip-down.d/10-remove-lte-route

    # Wait-Helper, der vor pon m2m auf das Device wartet (max 30s)
    sudo tee /usr/local/sbin/lte-wait-device > /dev/null << WAITSCRIPT
#!/bin/bash
DEV="\$1"
[ -z "\$DEV" ] && DEV="$LTE_DEVICE"
for i in \$(seq 1 30); do
    if [ -e "\$DEV" ]; then
        # Pingt das Modem mit AT, gibt OK wenn antwortet
        ANS=\$(timeout 3 bash -c "exec 3<>\$DEV; echo -e 'AT\\r' >&3; sleep 1; cat <&3" 2>/dev/null | tr -d '\\r' | grep -c OK)
        [ "\$ANS" -ge 1 ] && exit 0
    fi
    sleep 1
done
exit 1
WAITSCRIPT
    sudo chmod +x /usr/local/sbin/lte-wait-device

    # Systemd-Service fuer LTE
    sudo tee /etc/systemd/system/lte-connection.service > /dev/null << 'LTESVC'
[Unit]
Description=LTE PPP Connection (SIM7600 - Telekom M2M)
After=multi-user.target
Wants=network-online.target

[Service]
Type=forking
TimeoutStartSec=120
ExecStartPre=/bin/sleep 8
ExecStartPre=-/usr/local/sbin/lte-wait-device
ExecStart=/usr/bin/pon m2m
ExecStop=/usr/bin/poff m2m
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
LTESVC

    sudo systemctl daemon-reload
    sudo systemctl enable lte-connection
    # Service nicht-blockierend starten (--no-block), damit Setup nicht haengt
    # falls das Modem gerade nicht da ist - der Service versucht es ohnehin
    # alle 60s neu, sobald /dev/sim7600-ppp (udev-Symlink) auftaucht.
    sudo systemctl start --no-block lte-connection || true
fi

# ===== GPS (SIM7600 GNSS via AT+CGPS=1, NMEA auf /dev/sim7600-nmea) =====
if [ "{enable_gps}" = "true" ]; then
    echo "  GPS-Enable-Service einrichten (AT+CGPS=1 bei jedem Boot)..."

    # Standalone Script: wartet bis SIM7600 da ist, sendet AT+CGPS=1 auf
    # ttyUSB3 (ttyUSB2 wird von pppd belegt waehrend LTE aktiv ist)
    sudo tee /usr/local/sbin/sim7600-gps-enable > /dev/null << 'GPSENABLE'
#!/bin/bash
# GPS auf dem SIM7600 bei jedem Boot aktivieren.
# Nutzt /dev/sim7600-at (udev-Symlink, Interface 02), damit Port-Nummern
# stabil bleiben - unabhaengig von ttyUSBN-Enumerierung.
set -e
PORT=/dev/sim7600-at
# Warte bis USB enumeriert ist (max 60s)
for SEC in $(seq 1 60); do
    [ -e "$PORT" ] && break
    sleep 1
done
if [ ! -e "$PORT" ]; then
    logger -t sim7600-gps-enable "AT-Port $PORT nicht gefunden - Abbruch"
    exit 1
fi
# Port frei? (lsof-Check, sonst skippen)
if lsof -t "$PORT" 2>/dev/null | head -1 | grep -q .; then
    logger -t sim7600-gps-enable "$PORT ist belegt - skip"
    exit 0
fi
# Serial-Port konfigurieren
stty -F "$PORT" 115200 raw -echo 2>/dev/null || true
# GPS einschalten (AT+CGPS=1: standalone GPS)
printf 'AT+CGPS=1\r' > "$PORT" 2>/dev/null || true
sleep 1
logger -t sim7600-gps-enable "GPS auf $PORT aktiviert (AT+CGPS=1)"
exit 0
GPSENABLE
    sudo chmod +x /usr/local/sbin/sim7600-gps-enable

    sudo tee /etc/systemd/system/sim7600-gps-enable.service > /dev/null << 'GPSSVC'
[Unit]
Description=SIM7600 GPS Aktivierung (AT+CGPS=1 bei jedem Boot)
After=local-fs.target
# Wartet NICHT auf pppd - GPS geht ueber eigenen AT-Port /dev/sim7600-at

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/sim7600-gps-enable
RemainAfterExit=yes
TimeoutStartSec=120
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
GPSSVC
    sudo systemctl daemon-reload
    sudo systemctl enable sim7600-gps-enable.service

    # Einmaliger Start jetzt im Setup (damit GPS sofort laeuft)
    /usr/local/sbin/sim7600-gps-enable || true

    # gpsd: NMEA-Stream von /dev/sim7600-nmea (stabiler udev-Symlink)
    if [ -e /dev/sim7600-nmea ]; then
        GPS_DEV=/dev/sim7600-nmea
    elif [ -e /dev/ttyAMA0 ]; then
        GPS_DEV=/dev/ttyAMA0
    else
        GPS_DEV=/dev/sim7600-nmea
    fi
    sudo tee /etc/default/gpsd > /dev/null << EOF
START_DAEMON="true"
GPSD_OPTIONS="-n"
DEVICES="$GPS_DEV"
USBAUTO="false"
EOF
    sudo systemctl enable gpsd
    sudo systemctl restart gpsd 2>/dev/null || true
fi

# ===== SCHRITT 7: SEQUENT-INIT-SERVICE (Edge+Counter-Interrupt nach Boot) =====
echo "[7/8] Sequent-Init-Service einrichten..."
sudo tee /etc/systemd/system/sequent-init.service > /dev/null << 'SEQUENTINIT'
[Unit]
Description=Sequent HAT Counter Init (Edge + Interrupt, Stack auto-discover)
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'STACK=0; for s in 0 1 2 3 4 5 6 7; do if /usr/local/bin/16inpind $s optcntrd 1 >/dev/null 2>&1; then STACK=$s; break; fi; done; echo "Sequent HAT auf Stack $STACK"; for ch in 1 2 3 4 5 6 7 8; do /usr/local/bin/16inpind $STACK optedgewr $ch 1; /usr/local/bin/16inpind $STACK optintwr $ch 1; done'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
SEQUENTINIT

sudo systemctl daemon-reload
sudo systemctl enable sequent-init
sudo systemctl start sequent-init

# ===== SCHRITT 8: SYSTEMD SERVICE =====
echo "[8/8] Systemd-Service..."
sudo tee /etc/systemd/system/kirmeskiste8z_sync.service > /dev/null << 'SERVICE'
[Unit]
Description=Kirmeskiste 8Z Sync - Eventenergie Portal
# Keine harten Abhaengigkeiten: 
# - network-online.target ist auf LTE-Pi nie erreichbar -> Deadlock
# - sequent-init ist "Nice-To-Have" (Counter-Interrupts), aber Script
#   initialisiert den HAT notfalls selbst. Failure dort darf uns nicht blockieren.
After=local-fs.target
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=/opt/kirmeskiste8z/venv/bin/python3 /opt/kirmeskiste8z/kirmeskiste8z_sync.py
Restart=always
RestartSec=10
TimeoutStartSec=120
StandardOutput=journal
StandardError=journal
WorkingDirectory=/opt/kirmeskiste8z

[Install]
WantedBy=multi-user.target
SERVICE

# Persistentes Journal aktivieren (sonst sind Logs nach Reboot weg)
sudo mkdir -p /var/log/journal
sudo systemd-tmpfiles --create --prefix /var/log/journal 2>/dev/null || true
sudo systemctl restart systemd-journald 2>/dev/null || true

sudo systemctl daemon-reload
sudo systemctl enable kirmeskiste8z_sync
sudo systemctl restart kirmeskiste8z_sync

sleep 3
if systemctl is-active --quiet kirmeskiste8z_sync; then
    echo "  Service laeuft!"
else
    echo "  WARNUNG: Service nicht aktiv. Pruefen mit:"
    echo "    sudo journalctl -u kirmeskiste8z_sync -n 30"
fi

echo ""
echo "========================================================"
echo "  Setup abgeschlossen!"
echo "========================================================"
echo ""
echo "  Geraet-ID:     {device_id}"
echo "  Geraet-Key:    {plain_key[:8]}..."
echo "  Portal:        {api_url}"
echo "  Konfiguration: /etc/kirmeskiste8z.conf"
echo "  Datenbank:     /var/lib/kirmeskiste8z/kirmeskiste8z.sqlite"
echo "  Pi-ID-File:    /var/lib/kirmeskiste8z/pi_id"
echo ""
echo "  HAT-Diagnose: i2cdetect -y 1   (sollte 0x20 zeigen)"
echo ""
echo "  Service pruefen:"
echo "    sudo systemctl status kirmeskiste8z_sync"
echo "    sudo systemctl status sim7600-autoboot   (SIM7600 Auto-Power-On)"
echo "    sudo journalctl -u kirmeskiste8z_sync -f"
echo "    sudo journalctl -t sim7600-autoboot -f   (Auto-Boot Log)"
echo ""
echo "  WICHTIG: Anfangs-Zaehlerstaende im Portal eintragen!"
echo "  (Geraet bearbeiten -> Bereich 'Zaehler' -> kWh eintragen)"
echo ""
echo "  SIM7600 Auto-Boot: Nach jedem Pi-Start pulst der Service"
echo "  automatisch den PWRKEY -> Modul bootet ohne manuellen Druck."
echo ""
echo "  System wird in 10 Sekunden neu gestartet (finale Aktivierung)..."
echo "  (Abbrechen mit Strg+C)"
# WAL-Flushes vor Reboot sicherstellen (sonst SystemD-Service-Race moeglich)
sync
sleep 10
sudo systemctl daemon-reload
sudo reboot
"""

    download_token = secrets.token_urlsafe(32)
    _setup_downloads[download_token] = {
        "script": bash_script,
        "device_id": device_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }

    download_url = f"{api_base}/energy-monitoring/setup-download/{download_token}"

    return {
        "download_url": download_url,
        "download_token": download_token,
        "device_id": device_id,
        "device_key": plain_key,
        "meter_ids": meter_ids,
        "message": f"Kirmeskiste 8Z Setup-Skript fuer {serial} generiert",
    }


# ============== DSE 5510 Setup ==============

class DSE5510SetupRequest(BaseModel):
    serial_port: str = "/dev/ttyUSB0"
    baud_rate: int = 19200
    slave_id: int = 10
    enable_lte: bool = False
    lte_apn: str = "internet.m2mportal.de"
    lte_port: str = "/dev/ttyAMA0"
    controller_type: str = "DSE 5510"
    connection_type: str = ""  # "pi_usb", "pi_rs232", or ""

@router.post("/devices/{device_id}/dse5510-setup")
async def generate_dse5510_setup(device_id: str, request: Request, body: DSE5510SetupRequest = None, admin: dict = Depends(require_admin)):
    """Generate an all-in-one bash installer for DSE controllers via USB/RS232 + Pi."""
    if body is None:
        body = DSE5510SetupRequest()

    api_base = _get_api_base(request)

    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Geraet nicht gefunden")

    # Generate a new device key
    plain_key = secrets.token_hex(24)
    key_hash = _hash_key(plain_key)
    await db.devices.update_one(
        {"id": device_id},
        {"$set": {"device_key_hash": key_hash, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    api_url = _get_api_base(request)

    # Read the sync script template - USB or Serial depending on connection
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

    # Check if this is a USB-direct DSE device (L401, 8610 etc. without RS232 adapter)
    is_usb_direct = body.connection_type == "pi_usb" or body.serial_port.lower() in ("usb", "auto", "/dev/dse-usb")

    if is_usb_direct:
        script_path = os.path.join(static_dir, "dse_usb_sync.py")
    else:
        script_path = os.path.join(static_dir, "dse5510_sync.py")

    with open(script_path, "r") as f:
        sync_script = f.read()

    # Dynamic step count based on LTE
    total_steps = 9 if body.enable_lte else 7
    lte_port = body.lte_port if body.enable_lte else ""

    # Build LTE setup block (only if enabled)
    lte_setup_block = ""
    lte_verify_block = ""
    if body.enable_lte:
        lte_setup_block = f"""
# ===== SCHRITT 3: LTE+GPS SETUP (SIM7600E-H) =====
# Basiert auf getesteter Konfiguration: PPP + NetworkManager + gpsd
echo ""
echo "[3/{total_steps}] LTE+GPS konfigurieren (SIM7600E-H)..."

# --- 3a: Zusaetzliche Pakete (ppp, ifmetric, dnsutils - gpsd bereits in Schritt 1) ---
echo "  Pakete installieren..."
wait_for_apt
sudo apt-get install -y -qq ppp ifmetric dnsutils lsof

# --- 3b: ModemManager deaktivieren (blockiert ttyUSB-Ports!) ---
echo "  ModemManager deaktivieren..."
sudo systemctl stop ModemManager 2>/dev/null || true
sudo systemctl disable ModemManager 2>/dev/null || true

# --- 3c: SIM7600 einschalten (PWRKEY GPIO4) ---
echo "  SIM7600 einschalten (PWRKEY)..."
# Pi 5: pinctrl verwenden
if command -v pinctrl &> /dev/null; then
    if ! ls /dev/ttyUSB* &>/dev/null; then
        pinctrl set 4 op dl
        sleep 0.1
        pinctrl set 4 op dh
        sleep 2
        pinctrl set 4 op dl
        echo "    PWRKEY-Puls gesendet (pinctrl GPIO4), warte 15s..."
        sleep 15
    else
        echo "    Modul bereits aktiv (ttyUSB-Ports vorhanden)"
    fi
else
    echo "    WARNUNG: pinctrl nicht gefunden. SIM7600 ggf. manuell einschalten."
fi

# Auf USB-Ports warten
echo "    Warte auf /dev/ttyUSB3..."
for i in $(seq 1 30); do
    [ -e /dev/ttyUSB3 ] && break
    sleep 1
done

if [ ! -e /dev/ttyUSB3 ]; then
    echo "    WARNUNG: /dev/ttyUSB3 nicht gefunden. USB-Kabel pruefen!"
fi

# --- 3d: PPP-Konfiguration ---
echo "  PPP konfigurieren..."
sudo mkdir -p /etc/chatscripts /etc/ppp/peers /etc/ppp/ip-up.d

sudo tee /etc/ppp/peers/m2m > /dev/null << 'PPPCONF'
/dev/ttyUSB3
115200
connect "/usr/sbin/chat -v -f /etc/chatscripts/m2m-connect"
noauth
nodefaultroute
noipdefault
novj
novjccomp
noccp
ipcp-accept-local
ipcp-accept-remote
local
lock
persist
maxfail 0
holdoff 10
debug
PPPCONF

sudo tee /etc/chatscripts/m2m-connect > /dev/null << 'CHATSCRIPT'
ABORT 'BUSY'
ABORT 'NO CARRIER'
ABORT 'ERROR'
ABORT 'NO ANSWER'
TIMEOUT 30
'' AT
OK ATZ
OK 'AT+CMEE=2'
OK-AT-OK 'AT+CPIN?'
OK 'AT+CGDCONT=1,"IP","{body.lte_apn}"'
OK ATD*99#
CONNECT ''
CHATSCRIPT

sudo chmod 644 /etc/ppp/peers/m2m /etc/chatscripts/m2m-connect

# --- 3e: PPP-Hooks: Route HINZUFUEGEN mit Metric 700 (eth0 bleibt intakt!) ---
echo "  PPP-Hooks anlegen..."

sudo mkdir -p /etc/ppp/ip-up.d /etc/ppp/ip-down.d

sudo tee /etc/ppp/ip-up.d/10-add-lte-route > /dev/null << 'PPPHOOK1'
#!/bin/bash
# LTE-Route mit Metric 700 HINZUFUEGEN - eth0 Route wird NICHT angefasst!
# $PPP_IFACE = ppp0, $IPREMOTE = Gateway-IP vom Provider
if [ -n "$PPP_IFACE" ] && [ -n "$IPREMOTE" ]; then
    ip route add default via "$IPREMOTE" dev "$PPP_IFACE" metric 700 2>/dev/null || true
    logger -t lte-failover "$PPP_IFACE up - Default-Route Metric 700 hinzugefuegt (via $IPREMOTE)"
fi
PPPHOOK1

sudo tee /etc/ppp/ip-down.d/10-remove-lte-route > /dev/null << 'PPPHOOK1D'
#!/bin/bash
# LTE-Route wieder entfernen wenn PPP disconnected
if [ -n "$PPP_IFACE" ]; then
    ip route del default dev "$PPP_IFACE" 2>/dev/null || true
    logger -t lte-failover "$PPP_IFACE down - Default-Route entfernt"
fi
PPPHOOK1D

sudo tee /etc/ppp/ip-up.d/20-set-dns > /dev/null << 'PPPHOOK2'
#!/bin/bash
if [ -n "$PPP_IFACE" ]; then
    grep -q "1.1.1.1" /etc/resolv.conf || echo "nameserver 1.1.1.1" >> /etc/resolv.conf
    grep -q "8.8.8.8" /etc/resolv.conf || echo "nameserver 8.8.8.8" >> /etc/resolv.conf
    logger -t lte-failover "DNS-Fallback gesichert"
fi
PPPHOOK2

sudo chmod +x /etc/ppp/ip-up.d/10-add-lte-route /etc/ppp/ip-down.d/10-remove-lte-route /etc/ppp/ip-up.d/20-set-dns

# --- 3f: NetworkManager Metriken + DNS ---
echo "  NetworkManager-Metriken setzen..."
nmcli -t -f NAME,TYPE connection show 2>/dev/null | while IFS=: read -r name type; do
    case "$type" in
        802-3-ethernet|ethernet)
            nmcli connection modify "$name" ipv4.route-metric 100 ipv4.dns "1.1.1.1 8.8.8.8 1.0.0.1" 2>/dev/null || true
            echo "    eth: $name -> Metric 100"
            ;;
        802-11-wireless|wifi)
            nmcli connection modify "$name" ipv4.route-metric 600 ipv4.dns "1.1.1.1 8.8.8.8 1.0.0.1" 2>/dev/null || true
            echo "    wifi: $name -> Metric 600"
            ;;
    esac
done
nmcli connection reload 2>/dev/null || true

# --- 3g: GPS aktivieren + gpsd neu konfigurieren mit LTE-GPS ---
echo "  GPS + gpsd fuer SIM7600 konfigurieren..."

# GPS-Port per NMEA-Verifikation erneut suchen (SIM7600 USB-Ports jetzt aktiv)
LTE_GPS_PORT=""
for port in /dev/ttyUSB1 /dev/ttyUSB2 /dev/ttyUSB3 /dev/ttyUSB4; do
    [ -e "$port" ] || continue
    if timeout 3 cat "$port" 2>/dev/null | grep -qE '^\$(GP|GN|GL|BD)' ; then
        LTE_GPS_PORT="$port"
        break
    fi
done
[ -z "$LTE_GPS_PORT" ] && LTE_GPS_PORT="$GPS_DEV"  # Fallback auf Schritt-2-Ergebnis
echo "  GPS-NMEA verifiziert auf: $LTE_GPS_PORT"

sudo tee /usr/local/sbin/sim7600-gps-enable > /dev/null << 'GPSENABLE'
#!/bin/bash
# AT-Port suchen (der erste der AT OK antwortet)
for AT_PORT in /dev/ttyUSB3 /dev/ttyUSB4 /dev/ttyUSB2; do
    [ -e "$AT_PORT" ] || continue
    /usr/bin/lsof "$AT_PORT" >/dev/null 2>&1 && continue
    stty -F "$AT_PORT" 115200 raw -echo 2>/dev/null
    echo -e "AT\r" > "$AT_PORT"
    sleep 1
    if timeout 2 cat "$AT_PORT" 2>/dev/null | grep -q "OK"; then
        echo -e "AT+CGPS=1\r" > "$AT_PORT"
        sleep 2
        logger -t gps-enable "AT+CGPS=1 gesendet via $AT_PORT"
        exit 0
    fi
done
logger -t gps-enable "Kein freier AT-Port gefunden"
exit 1
GPSENABLE
sudo chmod +x /usr/local/sbin/sim7600-gps-enable

sudo tee /etc/systemd/system/sim7600-gps-enable.service > /dev/null << 'GPSSERVICE'
[Unit]
Description=Aktiviere GPS im SIM7600 Modul
After=systemd-udev-settle.service
Before=gpsd.service lte-failover.service
Wants=systemd-udev-settle.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/sim7600-gps-enable
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
GPSSERVICE

sudo tee /etc/default/gpsd > /dev/null << GPSDCONF
START_DAEMON="true"
USBAUTO="false"
DEVICES="$LTE_GPS_PORT"
GPSD_OPTIONS="-n"
GPSDCONF

sudo usermod -aG dialout gpsd 2>/dev/null || true
sudo systemctl daemon-reload
sudo systemctl enable sim7600-gps-enable.service gpsd.socket gpsd.service

# --- 3h: LTE-Service ---
echo "  LTE-Service anlegen..."
sudo tee /etc/systemd/system/lte-failover.service > /dev/null << 'LTESERVICE'
[Unit]
Description=LTE Failover Connection (Telekom M2M)
After=network-online.target sim7600-gps-enable.service
Wants=network-online.target
Requires=sim7600-gps-enable.service

[Service]
Type=forking
ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/pon m2m
ExecStop=/usr/bin/poff m2m
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
LTESERVICE

sudo systemctl daemon-reload
sudo systemctl enable lte-failover.service

# --- 3i: Status-Tools installieren ---
echo "  Status-Tools installieren..."

sudo tee /usr/local/bin/lte-status > /dev/null << 'LTESTATUS'
#!/bin/bash
echo "========== Network Status $(date '+%Y-%m-%d %H:%M:%S') =========="
echo ""
echo "--- Default-Routen ---"
ip route | grep default
echo ""
echo "--- Aktiver Pfad zu 8.8.8.8 ---"
ip route get 8.8.8.8 | head -1
echo ""
echo "--- LTE-Interface ---"
if ip link show ppp0 &>/dev/null; then
    ip -4 addr show ppp0 | grep inet
    echo "ppp0: UP"
else
    echo "ppp0: DOWN"
fi
echo ""
echo "--- DNS ---"
grep -v '^#' /etc/resolv.conf
LTESTATUS

sudo tee /usr/local/bin/gps-status > /dev/null << 'GPSSTATUS'
#!/bin/bash
echo "========== GPS Status $(date '+%Y-%m-%d %H:%M:%S') =========="
if ! systemctl is-active --quiet gpsd; then
    echo "gpsd laeuft nicht! -> sudo systemctl start gpsd"
    exit 1
fi
RESULT=$(timeout 5 gpspipe -w -n 10 2>/dev/null | grep -m1 '"class":"TPV"' || echo "")
if [ -z "$RESULT" ]; then
    echo "Noch keine GPS-Daten (Cold-Start kann 1-5 Min dauern)"
    exit 0
fi
LAT=$(echo "$RESULT" | grep -oP '"lat":\K[-0-9.]+' || echo "?")
LON=$(echo "$RESULT" | grep -oP '"lon":\K[-0-9.]+' || echo "?")
echo "Position: $LAT, $LON"
echo "Maps: https://www.google.com/maps?q=$LAT,$LON"
GPSSTATUS

sudo chmod +x /usr/local/bin/lte-status /usr/local/bin/gps-status

echo "  APN: {body.lte_apn}"
echo "  GPS-Port: $LTE_GPS_PORT"
echo "  Routing: eth0=100, wlan0=600, ppp0=700"
echo "  Tools: lte-status, gps-status"
"""

        lte_verify_block = f"""
# LTE + GPS Vorab-Test (SICHER: eth0-Route bleibt intakt)
echo ""
echo "  LTE Vorab-Test (vor Reboot)..."

# Aktuelle eth0 Default-Route merken (Sicherheit)
ETH0_GW=$(ip route show default dev eth0 2>/dev/null | awk '{{print $3}}' | head -1)

sudo pon m2m &>/dev/null
sleep 20
if ip link show ppp0 &>/dev/null; then
    PPP_IP=$(ip -4 addr show ppp0 2>/dev/null | grep inet | awk '{{print $2}}')
    echo "    ppp0 UP - IP: $PPP_IP"
    if sudo ping -c 2 -W 3 -I ppp0 8.8.8.8 &>/dev/null; then
        echo "    LTE-Internet: OK"
    else
        echo "    LTE-Internet: KEIN Ping ueber ppp0"
    fi
    sudo poff m2m 2>/dev/null
    sleep 3
else
    echo "    ppp0 nicht hochgekommen - nach Reboot syslog pruefen"
    sudo poff m2m 2>/dev/null || true
fi

# eth0-Route wiederherstellen falls verschwunden (Sicherheitsnetz)
if [ -n "$ETH0_GW" ]; then
    if ! ip route show default dev eth0 &>/dev/null; then
        ip route add default via "$ETH0_GW" dev eth0 metric 100 2>/dev/null || true
        echo "    eth0-Route wiederhergestellt: via $ETH0_GW metric 100"
    fi
fi

# GPS pruefen
echo ""
echo "  GPS Status:"
if systemctl is-active --quiet gpsd; then
    GPS_DATA=$(timeout 5 gpspipe -w -n 5 2>/dev/null | grep -m1 '"class":"TPV"' || echo "")
    if [ -n "$GPS_DATA" ]; then
        LAT=$(echo "$GPS_DATA" | grep -oP '"lat":\K[-0-9.]+' || echo "?")
        LON=$(echo "$GPS_DATA" | grep -oP '"lon":\K[-0-9.]+' || echo "?")
        echo "    GPS Fix: $LAT, $LON"
    else
        echo "    GPS: Noch kein Fix (Cold-Start kann 1-5 Min dauern)"
    fi
else
    echo "    gpsd laeuft nicht"
fi
echo ""
echo "  Nach Reboot pruefen:"
echo "    lte-status    # Netzwerk + LTE"
echo "    gps-status    # GPS-Position"
echo "    ip route      # Routing-Tabelle"
"""

    lte_after_line = "\nAfter=lte-failover.service" if body.enable_lte else ""

    # Pre-build conditional echo lines (backslashes not allowed in f-string expressions)
    lte_header_echo = f'echo "  LTE: SIM7600E-H ({body.lte_apn})"' if body.enable_lte else ""
    lte_apn_echo = f'echo "  LTE APN:      {body.lte_apn}"' if body.enable_lte else ""
    lte_port_echo = f'echo "  LTE Port:     PPP auto-detect, GPS auto-detect (NMEA)"' if body.enable_lte else ""
    lte_check_echo = ('echo ""\necho "  LTE pruefen:"\n'
                      'echo "    lte-status"\n'
                      'echo "    gps-status"\n'
                      'echo "    ip route"') if body.enable_lte else ""

    controller_label = body.controller_type or "DSE"

    bash_script = f"""#!/bin/bash
# ==============================================================
#  {controller_label} Pi Auto-Setup - {device.get('serial_number', device_id[:12])}
#  Generiert am {datetime.now().strftime('%d.%m.%Y %H:%M')}
#  USB Modbus RTU + GPS{" + LTE (SIM7600E-H)" if body.enable_lte else ""}
# ==============================================================
set -e

# Auto-Root: Falls nicht als root gestartet, automatisch mit sudo neu starten
if [ "$(id -u)" -ne 0 ]; then
    echo "Starte als root..."
    exec sudo bash "$0" "$@"
fi

echo "========================================================"
echo "  {controller_label} Pi Auto-Setup"
echo "  Geraet: {device.get('serial_number', device_id[:12])}"
{lte_header_echo}
echo "========================================================"

# Helper: Warte bis apt/dpkg-Lock frei ist
wait_for_apt() {{
    while fuser /var/lib/dpkg/lock-frontend &>/dev/null 2>&1; do
        echo "  Warte auf apt-Lock..."
        sleep 3
    done
}}

# ===== SCHRITT 0: ALTE INSTALLATION AUFRAUMEN =====
echo ""
echo "[0/{total_steps}] Alte Installation aufraumen..."

for SVC in dse5510_sync dse5510 lte-connection; do
    if systemctl is-active --quiet "$SVC" 2>/dev/null; then
        sudo systemctl stop "$SVC" 2>/dev/null || true
    fi
    if systemctl is-enabled --quiet "$SVC" 2>/dev/null; then
        sudo systemctl disable "$SVC" 2>/dev/null || true
    fi
    sudo rm -f "/etc/systemd/system/$SVC.service"
done

sudo pkill -f "dse5510_sync\|dse_usb_sync" 2>/dev/null || true
sleep 2
sudo rm -f /etc/dse5510.conf
sudo rm -f /var/lib/dse5510/dse5510.sqlite
sudo rm -f /var/lib/dse5510/dse5510.sqlite-wal
sudo rm -f /var/lib/dse5510/dse5510.sqlite-shm
sudo systemctl daemon-reload
echo "  Aufraumen abgeschlossen."

# ===== SCHRITT 1: SYSTEM AKTUALISIEREN =====
echo ""
echo "[1/{total_steps}] System aktualisieren..."
wait_for_apt
sudo apt-get update -qq
wait_for_apt
sudo apt-get install -y -qq python3-pip python3-venv gpsd libusb-1.0-0
wait_for_apt
sudo apt-get install -y -qq gpsd-clients 2>/dev/null || echo "  gpsd-clients nicht verfuegbar (optional)"

# Python-Pakete
sudo pip3 install --break-system-packages --quiet pymodbus pyserial pyusb requests 2>/dev/null || \
sudo pip3 install --quiet pymodbus pyserial pyusb requests 2>/dev/null || true

# DSE USB-Geraet binden (falls vorhanden)
if lsusb | grep -q "1b90:0001"; then
    echo "  DSE USB-Geraet erkannt - Treiber binden..."
    sudo modprobe usbserial vendor=0x1b90 product=0x0001 2>/dev/null || true
    sudo sh -c 'echo "1b90 0001" > /sys/bus/usb-serial/drivers/generic/new_id' 2>/dev/null || true

    # Persistent: udev-Regel fuer automatische Bindung nach Reboot
    sudo tee /etc/udev/rules.d/99-dse-usb.rules > /dev/null << 'UDEVRULE'
# DSE plc. USB Controller - automatisch generischen Serial-Treiber binden
ACTION=="add", ATTRS{{idVendor}}=="1b90", ATTRS{{idProduct}}=="0001", RUN+="/sbin/modprobe usbserial vendor=0x1b90 product=0x0001"
UDEVRULE
    sudo udevadm control --reload-rules
    echo "  udev-Regel angelegt (persistent nach Reboot)"
fi

# ===== SCHRITT 2: GPS KONFIGURIEREN =====
echo "[2/{total_steps}] GPS-Antenne konfigurieren..."

# Auto-Detect: NMEA-Verifikation statt nur Port-Existenz pruefen
detect_gps_port() {{
    for port in /dev/ttyUSB1 /dev/ttyUSB2 /dev/ttyUSB3 /dev/ttyACM0 /dev/ttyACM1; do
        [ -e "$port" ] || continue
        # Nicht den Modbus-Port oder LTE-Port nehmen
        [ "$port" = "{body.serial_port}" ] && continue
        [ "$port" = "{lte_port}" ] && continue
        # 3 Sekunden lauschen, nach echtem NMEA-Pattern suchen
        if timeout 3 cat "$port" 2>/dev/null | grep -qE '^\$(GP|GN|GL|BD)' ; then
            echo "$port"
            return 0
        fi
    done
    return 1
}}

GPS_DEV=$(detect_gps_port) || true
if [ -n "$GPS_DEV" ]; then
    echo "  GPS-NMEA-Stream verifiziert auf: $GPS_DEV"
else
    echo "  WARNUNG: Kein NMEA-Stream gefunden. Fallback: /dev/ttyUSB2"
    echo "  Nach Anschluss: sudo dpkg-reconfigure gpsd"
    GPS_DEV="/dev/ttyUSB2"
fi

sudo tee /etc/default/gpsd > /dev/null << GPSD_CONF
START_DAEMON="true"
USBAUTO="false"
DEVICES="$GPS_DEV"
GPSD_OPTIONS="-n"
GPSD_CONF

sudo systemctl enable gpsd
sudo systemctl restart gpsd
echo "  gpsd konfiguriert fuer: $GPS_DEV"
{lte_setup_block}
# ===== SCHRITT {"4" if body.enable_lte else "3"}: PYTHON-UMGEBUNG =====
echo "[{"4" if body.enable_lte else "3"}/{total_steps}] Python-Umgebung einrichten..."
INSTALL_DIR="/opt/dse5510"
sudo rm -rf "$INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"
sudo python3 -m venv "$INSTALL_DIR/venv"
sudo "$INSTALL_DIR/venv/bin/pip" install --quiet pyserial requests gpsd-py3 pyusb

# ===== SCHRITT {"5" if body.enable_lte else "4"}: SYNC-SKRIPT =====
echo "[{"5" if body.enable_lte else "4"}/{total_steps}] Sync-Skript installieren..."
sudo tee "$INSTALL_DIR/dse5510_sync.py" > /dev/null << 'SYNC_SCRIPT'
{sync_script}
SYNC_SCRIPT
sudo chmod +x "$INSTALL_DIR/dse5510_sync.py"

# ===== SCHRITT {"6" if body.enable_lte else "5"}: KONFIGURATION =====
echo "[{"6" if body.enable_lte else "5"}/{total_steps}] Konfiguration schreiben..."
sudo mkdir -p /var/lib/dse5510

sudo tee /etc/dse5510.conf > /dev/null << 'CONF'
[dse5510]
api_url = {api_url}
device_key = {plain_key}
device_id = {device_id}
controller_type = {body.controller_type}
generator_id =
db_path = /var/lib/dse5510/dse5510.sqlite
serial_port = {body.serial_port}
baud_rate = {body.baud_rate}
slave_id = {body.slave_id}
read_interval = 1
sync_interval = 30
retry_delay = 30
batch_size = 500
max_disk_gb = 60
CONF

sudo chmod 600 /etc/dse5510.conf

# ===== SCHRITT {"7" if body.enable_lte else "6"}: SYSTEMD SERVICE =====
echo "[{"7" if body.enable_lte else "6"}/{total_steps}] Systemd-Service einrichten..."
sudo tee /etc/systemd/system/dse5510_sync.service > /dev/null << 'SERVICE'
[Unit]
Description=DSE 5510 Sync - Eventenergie Portal
After=network-online.target{lte_after_line}
Wants=network-online.target

[Service]
Type=simple
ExecStart=/opt/dse5510/venv/bin/python3 /opt/dse5510/dse5510_sync.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
WorkingDirectory=/opt/dse5510

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable dse5510_sync
sudo systemctl restart dse5510_sync

# ===== SCHRITT {total_steps}: VERIFIZIERUNG =====
echo "[{total_steps}/{total_steps}] Verifiziere Installation..."
sleep 3

# GPS Status pruefen
echo ""
echo "  GPS Status:"
if systemctl is-active --quiet gpsd; then
    echo "    gpsd laeuft"
    timeout 5 gpspipe -w -n 3 2>/dev/null | head -3 || echo "    GPS wartet auf Fix (kann ein paar Minuten dauern)"
else
    echo "    gpsd ist NICHT aktiv"
fi

# Sync-Service pruefen
echo ""
if systemctl is-active --quiet dse5510_sync; then
    echo "  Sync-Service laeuft!"
else
    echo "  WARNUNG: Sync-Service ist nicht aktiv!"
    echo "  Pruefe mit: sudo journalctl -u dse5510_sync -n 20"
fi
{lte_verify_block}
echo ""
echo "========================================================"
echo "  Setup abgeschlossen!"
echo "========================================================"
echo ""
echo "  Geraet-ID:     {device_id}"
echo "  Geraet-Key:    {plain_key[:8]}..."
echo "  Portal:        {api_url}"
echo "  Serial Port:   {body.serial_port}"
echo "  Baud Rate:     {body.baud_rate}"
echo "  Slave ID:      {body.slave_id}"
{lte_apn_echo}
{lte_port_echo}
echo "  Konfiguration: /etc/dse5510.conf"
echo "  Datenbank:     /var/lib/dse5510/dse5510.sqlite"
echo ""
echo "  Service pruefen:"
echo "    sudo systemctl status dse5510_sync"
echo "    sudo journalctl -u dse5510_sync -f"
{lte_check_echo}
echo ""
echo "  Serielle Ports auflisten:"
echo "    ls -la /dev/ttyUSB* /dev/ttyAMA* /dev/ttyACM* 2>/dev/null"
echo ""
echo "  GPS Status pruefen:"
echo "    sudo gpsmon"
echo "    sudo systemctl status gpsd"
echo ""
echo "  Falls der Port nicht stimmt, anpassen in:"
echo "    sudo nano /etc/dse5510.conf"
echo "    sudo systemctl restart dse5510_sync"
echo ""
echo "  System wird in 10 Sekunden neu gestartet..."
echo "  (Abbrechen mit Strg+C)"
sleep 10
sudo reboot
"""

    download_token = secrets.token_urlsafe(32)
    _setup_downloads[download_token] = {
        "script": bash_script,
        "device_id": device_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }

    download_url = f"{api_base}/energy-monitoring/setup-download/{download_token}"

    return {
        "download_url": download_url,
        "download_token": download_token,
        "device_id": device_id,
        "device_key": plain_key,
        "serial_port": body.serial_port,
        "baud_rate": body.baud_rate,
        "slave_id": body.slave_id,
        "message": f"Setup-Skript generiert fuer {device.get('serial_number', '')}",
    }



# ============== Ingest API (Pi Push) ==============

@router.post("/ingest")
async def ingest_data(data: IngestBatch):
    """Receive batch of EMU data from Pi sync script. Authenticated via per-device key."""
    # 1) Direkt per device_id suchen
    device = await db.devices.find_one({"id": data.device_id, "device_type": {"$in": ["messkoffer", "kirmeskiste"]}})
    actual_device_id = data.device_id

    # 2) Fallback: per api_key suchen
    if not device and data.api_key:
        key_hash_check = hashlib.sha256(data.api_key.encode()).hexdigest()
        device = await db.devices.find_one({
            "device_type": {"$in": ["messkoffer", "kirmeskiste"]},
            "device_key_hash": key_hash_check
        })
        if device:
            actual_device_id = device["id"]
            logger.info(f"Ingest: Fallback via Key! Pi={data.device_id} -> {device['serial_number']} ({actual_device_id})")

    # 4) Fallback: per meter_id suchen
    if not device:
        meter_ref = await db.emu_meters.find_one({"id": data.meter_id}, {"_id": 0})
        if meter_ref:
            parent_device = await db.devices.find_one({
                "id": meter_ref["device_id"],
                "device_type": {"$in": ["messkoffer", "kirmeskiste"]}
            })
            if parent_device:
                device = parent_device
                actual_device_id = device["id"]
                logger.info(f"Ingest: Fallback via Meter! Pi={data.device_id} -> {device['serial_number']} ({actual_device_id}) via meter={data.meter_id}")

    if not device:
        logger.warning(f"Ingest 404: device_id={data.device_id}, meter_id={data.meter_id} - Geraet nicht in DB (alle Fallbacks fehlgeschlagen)")
        raise HTTPException(status_code=404, detail=f"Geraet nicht gefunden (device_id: {data.device_id})")

    # Verify device key
    key_hash = device.get("device_key_hash")
    matched_via_fallback = (actual_device_id != data.device_id)

    if key_hash and not matched_via_fallback:
        # Nur bei direktem device_id Match streng pruefen
        if not _verify_key(data.api_key, key_hash):
            raise HTTPException(status_code=401, detail="Ungültiger Geräteschlüssel")
    elif key_hash and matched_via_fallback:
        # Bei Fallback: Key pruefen aber bei Mismatch trotzdem akzeptieren (mit Warnung)
        if not _verify_key(data.api_key, key_hash):
            logger.warning(f"Ingest: Key mismatch fuer {device.get('serial_number')} ({actual_device_id}) - akzeptiere via Fallback (Pi={data.device_id})")
    elif not key_hash:
        # Kein device_key_hash -> check legacy global key
        settings = await db.emu_settings.find_one({"key": "ingest_api_key"}, {"_id": 0})
        if settings and settings.get("value") == data.api_key:
            pass  # Legacy key matches
        elif matched_via_fallback:
            logger.info(f"Ingest: Akzeptiere ohne Key (Fallback) fuer {actual_device_id}")
        else:
            raise HTTPException(status_code=401, detail="Kein Geräteschlüssel konfiguriert")

    meter = await db.emu_meters.find_one({"id": data.meter_id, "device_id": actual_device_id}, {"_id": 0})
    if not meter:
        # Also check if meter exists under the old device_id (Pi sends old ID)
        if actual_device_id != data.device_id:
            meter = await db.emu_meters.find_one({"id": data.meter_id, "device_id": data.device_id}, {"_id": 0})
            if meter:
                # Update meter to point to the correct device
                await db.emu_meters.update_one({"id": data.meter_id}, {"$set": {"device_id": actual_device_id}})
                logger.info(f"Meter {data.meter_id} umgehaengt von {data.device_id} -> {actual_device_id}")
    if not meter:
        # Auto-register meter when device is authenticated but meter is unknown
        device_name = device.get("serial_number", actual_device_id)
        meter_doc = {
            "id": data.meter_id,
            "device_id": actual_device_id,
            "meter_name": f"Auto-registriert ({device_name})",
            "meter_ip": "",
            "description": "Automatisch beim ersten Datenempfang erstellt",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.emu_meters.insert_one(meter_doc)
        logger.info(f"Auto-registered meter {data.meter_id} for device {actual_device_id} ({device_name})")
        meter = {k: v for k, v in meter_doc.items() if k != "_id"}

    if not data.records:
        return {"inserted": 0, "message": "Keine Datensätze"}

    # Kirmeskiste EMU Professional II (alte 4-Meter Variante "standard"):
    # Modbus-Register liefern Watt statt kW -> Backend rechnet um.
    # Die neue 8Z-Variante (Sequent S0-Pulse) berechnet Leistung lokal in
    # echten kW -> KEINE Umrechnung!
    is_kirmeskiste_legacy = (
        device.get("device_type") == "kirmeskiste"
        and device.get("kirmeskiste_variant") != "8z"
    )

    # Prepare records for insertion
    docs = []
    for r in data.records:
        p_sum = r.get("P_sum_kW", 0)
        p_l1 = r.get("P_L1_kW", 0)
        p_l2 = r.get("P_L2_kW", 0)
        p_l3 = r.get("P_L3_kW", 0)

        # Kirmeskiste: Watt -> kW (nur wenn Wert plausibel in Watt, d.h. > 1)
        if is_kirmeskiste_legacy:
            if abs(p_sum) > 1:
                p_sum = round(p_sum / 1000, 4)
            if abs(p_l1) > 1:
                p_l1 = round(p_l1 / 1000, 4)
            if abs(p_l2) > 1:
                p_l2 = round(p_l2 / 1000, 4)
            if abs(p_l3) > 1:
                p_l3 = round(p_l3 / 1000, 4)

        doc = {
            "id": str(uuid.uuid4()),
            "device_id": actual_device_id,
            "meter_id": data.meter_id,
            "ts_utc": r.get("ts_utc"),
            "meter_ts": r.get("meter_ts"),
            "I_L1": r.get("I_L1", 0),
            "I_L2": r.get("I_L2", 0),
            "I_L3": r.get("I_L3", 0),
            "I_sum": r.get("I_sum", 0),
            "U_L1": r.get("U_L1", 0),
            "U_L2": r.get("U_L2", 0),
            "U_L3": r.get("U_L3", 0),
            "F_Hz": r.get("F_Hz", 0),
            "P_sum_kW": p_sum,
            "P_L1_kW": p_l1,
            "P_L2_kW": p_l2,
            "P_L3_kW": p_l3,
            "Q_sum": r.get("Q_sum", 0),
            "Q_L1": r.get("Q_L1", 0),
            "Q_L2": r.get("Q_L2", 0),
            "Q_L3": r.get("Q_L3", 0),
            "PF_L1": r.get("PF_L1", 0),
            "PF_L2": r.get("PF_L2", 0),
            "PF_L3": r.get("PF_L3", 0),
            "E_imp_kWh": r.get("E_imp_kWh", 0),
            "E_exp_kWh": r.get("E_exp_kWh", 0),
            "gps_lat": r.get("gps_lat"),
            "gps_lon": r.get("gps_lon"),
            "gps_alt_m": r.get("gps_alt_m"),
            "gps_speed_mps": r.get("gps_speed_mps"),
            "gps_mode": r.get("gps_mode"),
            "http_ok": r.get("http_ok", 1),
            "error": r.get("error", ""),
            "source_id": r.get("id"),
        }
        docs.append(doc)

    await db.emu_data.insert_many(docs)

    # Update sync state
    if data.last_sync_id:
        await db.emu_sync_state.update_one(
            {"device_id": actual_device_id, "meter_id": data.meter_id},
            {"$set": {"last_sync_id": data.last_sync_id, "last_sync_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )

    # Update device last_seen for online status tracking
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.devices.update_one(
        {"id": actual_device_id},
        {"$set": {"last_seen": now_iso}}
    )

    logger.info(f"Ingest: {len(docs)} records for device={actual_device_id} meter={data.meter_id}")
    return {"inserted": len(docs), "message": f"{len(docs)} Datensätze empfangen"}


@router.get("/ingest/sync-state")
async def get_sync_state(device_id: str, meter_id: str, api_key: str):
    """Get the last synced ID for a device/meter pair."""
    # Verify per-device key
    device = await db.devices.find_one({"id": device_id})
    actual_device_id = device_id

    # Fallback: suche per api_key wenn device_id nicht gefunden
    if not device and api_key:
        key_hash_check = hashlib.sha256(api_key.encode()).hexdigest()
        device = await db.devices.find_one({
            "device_type": {"$in": ["messkoffer", "kirmeskiste"]},
            "device_key_hash": key_hash_check
        })
        if device:
            actual_device_id = device["id"]

    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    key_hash = device.get("device_key_hash")
    if key_hash:
        if not _verify_key(api_key, key_hash):
            raise HTTPException(status_code=401, detail="Ungültiger Geräteschlüssel")
    else:
        # Fallback: legacy global key
        settings = await db.emu_settings.find_one({"key": "ingest_api_key"}, {"_id": 0})
        if not settings or settings.get("value") != api_key:
            raise HTTPException(status_code=401, detail="Ungültiger Schlüssel")

    state = await db.emu_sync_state.find_one(
        {"device_id": actual_device_id, "meter_id": meter_id},
        {"_id": 0}
    )
    return {"last_sync_id": state.get("last_sync_id", 0) if state else 0}


@router.post("/ingest/generate-key")
async def generate_ingest_key(admin: dict = Depends(require_admin)):
    """Generate or regenerate the ingest API key."""
    key = str(uuid.uuid4()).replace("-", "")
    await db.emu_settings.update_one(
        {"key": "ingest_api_key"},
        {"$set": {"key": "ingest_api_key", "value": key, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    return {"api_key": key}


@router.get("/ingest/api-key")
async def get_ingest_key(admin: dict = Depends(require_admin)):
    """Get the current ingest API key."""
    settings = await db.emu_settings.find_one({"key": "ingest_api_key"}, {"_id": 0})
    if not settings:
        return {"api_key": None}
    return {"api_key": settings.get("value")}


# ============== GPS/Location ==============

@router.get("/devices/{device_id}/location")
async def get_device_location(device_id: str, user: dict = Depends(get_authenticated_user)):
    """Get latest GPS location for a device."""
    if not check_energy_monitoring_access(user):
        raise HTTPException(status_code=403, detail="Energy Monitoring nicht freigeschaltet")

    allowed_ids = get_allowed_device_ids(user)
    if allowed_ids is not None and device_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Gerät")

    # Find latest record with GPS data
    location = await db.emu_data.find_one(
        {"device_id": device_id, "gps_lat": {"$ne": None}, "gps_lon": {"$ne": None}},
        {"_id": 0, "gps_lat": 1, "gps_lon": 1, "gps_alt_m": 1, "gps_speed_mps": 1, "gps_mode": 1, "ts_utc": 1},
        sort=[("ts_utc", -1)]
    )
    return location or {}


@router.get("/locations")
async def get_all_device_locations(user: dict = Depends(get_authenticated_user)):
    """Get latest GPS location for all accessible devices."""
    if not check_energy_monitoring_access(user):
        raise HTTPException(status_code=403, detail="Energy Monitoring nicht freigeschaltet")

    devices = await db.devices.find({"device_type": "messkoffer"}, {"_id": 0}).to_list(500)
    allowed_ids = get_allowed_device_ids(user)
    if allowed_ids is not None:
        devices = [d for d in devices if d["id"] in allowed_ids]

    locations = []
    for device in devices:
        loc = await db.emu_data.find_one(
            {"device_id": device["id"], "gps_lat": {"$ne": None}, "gps_lon": {"$ne": None}},
            {"_id": 0, "gps_lat": 1, "gps_lon": 1, "gps_alt_m": 1, "ts_utc": 1, "P_sum_kW": 1},
            sort=[("ts_utc", -1)]
        )
        if loc:
            locations.append({
                "device_id": device["id"],
                "name": device.get("user_field") or device.get("serial_number"),
                "serial_number": device.get("serial_number"),
                "gps_lat": loc["gps_lat"],
                "gps_lon": loc["gps_lon"],
                "gps_alt_m": loc.get("gps_alt_m"),
                "ts_utc": loc.get("ts_utc"),
                "P_sum_kW": loc.get("P_sum_kW"),
            })

    return locations


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



@router.post("/migrate/kirmeskiste-power-fix")
async def migrate_kirmeskiste_power(admin: dict = Depends(require_admin)):
    """Einmalige Migration: Korrigiert P_sum_kW/P_L*_kW Werte fuer Kirmeskiste-Geraete.
    EMU Professional II Modbus-Register liefern Watt, wurden aber als kW gespeichert.
    Diese Migration teilt alle Werte > 1 durch 1000."""
    
    # Finde alle Kirmeskiste-Geraete
    kirmeskisten = await db.devices.find({"device_type": "kirmeskiste"}, {"_id": 0, "id": 1, "serial_number": 1}).to_list(50)
    if not kirmeskisten:
        return {"message": "Keine Kirmeskiste-Geraete gefunden", "fixed": 0}
    
    kirm_ids = [k["id"] for k in kirmeskisten]
    total_fixed = 0
    
    for dev_id in kirm_ids:
        # Finde alle Datensaetze mit P_sum_kW > 1 (= in Watt statt kW)
        power_fields = ["P_sum_kW", "P_L1_kW", "P_L2_kW", "P_L3_kW"]
        
        cursor = db.emu_data.find(
            {"device_id": dev_id, "$or": [{f: {"$gt": 1}} for f in power_fields]},
            {"_id": 1, **{f: 1 for f in power_fields}}
        )
        
        batch = []
        async for doc in cursor:
            update = {}
            for f in power_fields:
                val = doc.get(f, 0)
                if val and abs(val) > 1:
                    update[f] = round(val / 1000, 4)
            if update:
                batch.append({"_id": doc["_id"], "update": update})
            
            if len(batch) >= 500:
                for item in batch:
                    await db.emu_data.update_one({"_id": item["_id"]}, {"$set": item["update"]})
                total_fixed += len(batch)
                batch = []
        
        if batch:
            for item in batch:
                await db.emu_data.update_one({"_id": item["_id"]}, {"$set": item["update"]})
            total_fixed += len(batch)
    
    device_names = ", ".join(k["serial_number"] for k in kirmeskisten)
    return {
        "message": f"Migration abgeschlossen: {total_fixed} Datensaetze korrigiert",
        "devices": device_names,
        "fixed": total_fixed,
    }
