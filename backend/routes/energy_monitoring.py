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
sudo "$INSTALL_DIR/venv/bin/pip" install --quiet "pymodbus>=3.7" requests gpsd-py3

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


# ============== DSE 5510 Setup ==============

class DSE5510SetupRequest(BaseModel):
    serial_port: str = "/dev/ttyUSB0"
    baud_rate: int = 19200
    slave_id: int = 10
    enable_lte: bool = False
    lte_apn: str = "internet.m2mportal.de"
    lte_port: str = "/dev/ttyAMA0"

@router.post("/devices/{device_id}/dse5510-setup")
async def generate_dse5510_setup(device_id: str, request: Request, body: DSE5510SetupRequest = None, admin: dict = Depends(require_admin)):
    """Generate an all-in-one bash installer for DSE 5510 via RS232 + Pi."""
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

    # Read the dse5510_sync.py template
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "dse5510_sync.py")
    with open(script_path, "r") as f:
        sync_script = f.read()

    # Dynamic step count based on LTE
    total_steps = 8 if body.enable_lte else 7
    lte_port = body.lte_port if body.enable_lte else ""

    # Build LTE setup block (only if enabled)
    lte_setup_block = ""
    lte_verify_block = ""
    if body.enable_lte:
        lte_setup_block = f"""
# ===== SCHRITT 3: LTE MODEM (SIM7600E-H) =====
echo ""
echo "[3/{total_steps}] LTE-Modem konfigurieren (SIM7600E-H)..."

# --- 3a: Netzwerk-Prioritaeten konfigurieren (dhcpcd) ---
echo "  Netzwerk-Routing konfigurieren (LAN Prio, LTE Fallback)..."

# dhcpcd.conf: LAN bekommt niedrige metric (= hohe Prio), LTE hohe metric
# Wenn kein LAN-Gateway vorhanden → LTE uebernimmt automatisch
DHCPCD_CONF="/etc/dhcpcd.conf"
if [ -f "$DHCPCD_CONF" ]; then
    # Alte Eintraege entfernen falls vorhanden
    sudo sed -i '/^# --- Eventenergie Netzwerk ---/,/^# --- Ende Eventenergie ---/d' "$DHCPCD_CONF"
fi

sudo tee -a "$DHCPCD_CONF" > /dev/null << 'DHCPCD_NET'

# --- Eventenergie Netzwerk ---
# LAN (eth0) hat hoechste Prioritaet wenn verfuegbar
interface eth0
metric 100
static domain_name_servers=8.8.8.8 8.8.4.4

# WLAN als zweite Wahl
interface wlan0
metric 200
static domain_name_servers=8.8.8.8 8.8.4.4

# DNS Fallback global
static domain_name_servers=8.8.8.8 8.8.4.4
# --- Ende Eventenergie ---
DHCPCD_NET

echo "  dhcpcd.conf: eth0 metric=100, wlan0 metric=200 (LTE=700)"

# --- 3b: DNS dauerhaft sicherstellen ---
echo "  DNS-Fallback konfigurieren..."
# resolv.conf direkt setzen (sofort wirksam)
if ! grep -q "8.8.8.8" /etc/resolv.conf 2>/dev/null; then
    echo "nameserver 8.8.8.8" | sudo tee -a /etc/resolv.conf > /dev/null
fi

# dhcpcd-Hook: nach jedem DHCP-Event DNS sicherstellen
sudo tee /lib/dhcpcd/dhcpcd-hooks/99-dns-fallback > /dev/null << 'DNSHOOK'
# Eventenergie: DNS-Fallback sicherstellen
if ! grep -q "8.8.8.8" /etc/resolv.conf 2>/dev/null; then
    echo "nameserver 8.8.8.8" >> /etc/resolv.conf
fi
DNSHOOK

# --- 3c: Network-Watchdog (entfernt tote eth0-Routen) ---
echo "  Network-Watchdog installieren..."
sudo tee /usr/local/bin/network-watchdog.sh > /dev/null << 'WATCHDOG'
#!/bin/bash
# Eventenergie Network-Watchdog
# Prueft ob die Default-Route ueber eth0 tatsaechlich Internet hat.
# Falls nicht (eth0 DOWN oder kein Gateway), wird die Route entfernt
# damit LTE (ppp0) uebernehmen kann.

ETH_ROUTE=$(ip route show default dev eth0 2>/dev/null)
if [ -n "$ETH_ROUTE" ]; then
    # eth0 hat eine Default-Route - pruefe ob sie funktioniert
    ETH_STATE=$(cat /sys/class/net/eth0/carrier 2>/dev/null || echo "0")
    if [ "$ETH_STATE" != "1" ]; then
        # eth0 hat keinen Link (Kabel nicht gesteckt oder kein Carrier)
        ip route del default dev eth0 2>/dev/null
        logger -t network-watchdog "eth0 Default-Route entfernt (kein Carrier)"
    else
        # eth0 hat Link - teste ob Internet erreichbar
        if ! ping -c 1 -W 3 -I eth0 8.8.8.8 &>/dev/null; then
            # eth0 hat zwar Link aber kein Internet (z.B. lokales Netz ohne Gateway)
            ip route del default dev eth0 2>/dev/null
            logger -t network-watchdog "eth0 Default-Route entfernt (kein Internet)"
        fi
    fi
fi

# DNS Fallback sicherstellen
if ! grep -q "8.8.8.8" /etc/resolv.conf 2>/dev/null; then
    echo "nameserver 8.8.8.8" >> /etc/resolv.conf
fi
WATCHDOG
sudo chmod +x /usr/local/bin/network-watchdog.sh

# Watchdog als systemd-Timer (alle 30 Sekunden)
sudo tee /etc/systemd/system/network-watchdog.service > /dev/null << 'WDSERVICE'
[Unit]
Description=Eventenergie Network Watchdog
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/network-watchdog.sh
WDSERVICE

sudo tee /etc/systemd/system/network-watchdog.timer > /dev/null << 'WDTIMER'
[Unit]
Description=Eventenergie Network Watchdog Timer

[Timer]
OnBootSec=30
OnUnitActiveSec=30
AccuracySec=5

[Install]
WantedBy=timers.target
WDTIMER

sudo systemctl daemon-reload
sudo systemctl enable network-watchdog.timer
sudo systemctl start network-watchdog.timer
echo "  Network-Watchdog aktiv (prueft alle 30s)"

# --- 3d: UART aktivieren ---
echo "  UART aktivieren..."
BOOT_CFG="/boot/firmware/config.txt"
if [ ! -f "$BOOT_CFG" ]; then
    BOOT_CFG="/boot/config.txt"
fi

# dtoverlay fuer UART hinzufuegen falls nicht vorhanden
if ! grep -q "enable_uart=1" "$BOOT_CFG" 2>/dev/null; then
    echo "enable_uart=1" | sudo tee -a "$BOOT_CFG" > /dev/null
fi

# Serial Console deaktivieren (damit der Modem-Port frei ist)
sudo raspi-config nonint do_serial_hw 0 2>/dev/null || true
sudo raspi-config nonint do_serial_cons 1 2>/dev/null || true
# cmdline.txt bereinigen
if [ -f /boot/firmware/cmdline.txt ]; then
    sudo sed -i 's/console=serial0,[0-9]* //g' /boot/firmware/cmdline.txt
    sudo sed -i 's/console=ttyAMA0,[0-9]* //g' /boot/firmware/cmdline.txt
elif [ -f /boot/cmdline.txt ]; then
    sudo sed -i 's/console=serial0,[0-9]* //g' /boot/cmdline.txt
    sudo sed -i 's/console=ttyAMA0,[0-9]* //g' /boot/cmdline.txt
fi
echo "  UART aktiviert, Serial Console deaktiviert."

# PPP und GPIO-Tools installieren
wait_for_apt
sudo apt-get install -y -qq ppp gpiod

# Kleines AT-Command Helper-Skript fuer Modem-Test (nutzt pyserial statt socat)
sudo tee /tmp/at_test.py > /dev/null << 'ATTEST'
import serial, sys, time
port, cmd = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "AT"
try:
    s = serial.Serial(port, 115200, timeout=3)
    s.write((cmd + "\r\n").encode())
    time.sleep(1.5)
    resp = s.read(s.in_waiting or 256).decode(errors="ignore").strip()
    s.close()
    print(resp)
    sys.exit(0 if "OK" in resp or "READY" in resp else 1)
except Exception as e:
    print(f"Fehler: {{e}}")
    sys.exit(1)
ATTEST

# SIM7600E-H einschalten via GPIO 6 (Waveshare HAT Power Key)
echo "  SIM7600E-H einschalten (GPIO 6)..."

# Pi 5: pinctrl verwenden (nativ verfuegbar)
if command -v pinctrl &> /dev/null; then
    pinctrl set 6 op dh
    sleep 1
    pinctrl set 6 op dl
    echo "  Power-Puls gesendet (pinctrl GPIO 6)"
    sleep 5
# Fallback: gpioset (libgpiod)
elif command -v gpioset &> /dev/null; then
    gpioset -t 1000ms gpiochip0 6=1 2>/dev/null || gpioset -t 1000ms gpiochip4 6=1 2>/dev/null || true
    echo "  Power-Puls gesendet (gpioset GPIO 6)"
    sleep 5
else
    echo "  WARNUNG: Kein GPIO-Tool gefunden. SIM7600E evtl. manuell einschalten."
    echo "  Alternativ: PWR-Jumper auf 3V3 setzen fuer Auto-Power-On."
fi

# pyserial fuer AT-Tests installieren (in System-Python)
sudo pip3 install --quiet --break-system-packages pyserial 2>/dev/null || sudo pip3 install --quiet pyserial 2>/dev/null || true

# Warten bis Modem antwortet - AUTO-ERKENNUNG des richtigen Ports
echo "  Modem-Port automatisch erkennen..."

# Alle verfuegbaren Ports sammeln (UART + USB)
ALL_PORTS="{body.lte_port}"
for p in /dev/ttyUSB1 /dev/ttyUSB2 /dev/ttyUSB3 /dev/ttyUSB4 /dev/ttyUSB5 /dev/ttyAMA0 /dev/ttyAMA10; do
    if [ -e "$p" ] && [[ "$ALL_PORTS" != *"$p"* ]]; then
        ALL_PORTS="$ALL_PORTS $p"
    fi
done

# AT-Port finden (fuer PPP/Steuerung)
MODEM_PORT=""
GPS_PORT=""
MODEM_OK=0

for attempt in $(seq 1 3); do
    echo "  Scan-Versuch $attempt/3..."
    for p in $ALL_PORTS; do
        [ ! -e "$p" ] && continue
        # Teste ob Port AT-Kommandos akzeptiert
        RESPONSE=$(sudo timeout 3 python3 -c "
import serial, time
try:
    s = serial.Serial('$p', 115200, timeout=2)
    s.reset_input_buffer()
    s.write(b'AT\r\n')
    time.sleep(1)
    r = s.read(s.in_waiting or 256).decode(errors='ignore')
    s.close()
    if 'OK' in r:
        print('AT_OK')
    elif 'GPGGA' in r or 'GPRMC' in r or 'GNSS' in r:
        print('GPS_NMEA')
    else:
        print('NONE')
except:
    print('NONE')
" 2>/dev/null)

        if [ "$RESPONSE" = "AT_OK" ] && [ -z "$MODEM_PORT" ]; then
            MODEM_PORT="$p"
            MODEM_OK=1
            echo "    AT-Port gefunden: $p"
        elif [ "$RESPONSE" = "GPS_NMEA" ] && [ -z "$GPS_PORT" ]; then
            GPS_PORT="$p"
            echo "    GPS-Port gefunden: $p (NMEA)"
        fi
    done

    if [ "$MODEM_OK" -eq 1 ]; then
        break
    fi
    sleep 3
done

# GPS-Port auch ueber AT+CGPSINFO suchen falls noch nicht gefunden
if [ -z "$GPS_PORT" ]; then
    for p in $ALL_PORTS; do
        [ ! -e "$p" ] && continue
        [ "$p" = "$MODEM_PORT" ] && continue
        GPS_RESP=$(sudo timeout 5 python3 -c "
import serial, time
try:
    s = serial.Serial('$p', 115200, timeout=3)
    s.write(b'AT+CGPSINFO\r\n')
    time.sleep(2)
    r = s.read(s.in_waiting or 256).decode(errors='ignore')
    s.close()
    if 'CGPSINFO' in r:
        print('GPS_AT')
except:
    pass
" 2>/dev/null)
        if [ "$GPS_RESP" = "GPS_AT" ]; then
            GPS_PORT="$p"
            echo "    GPS-Port gefunden: $p (AT)"
            break
        fi
    done
fi

if [ "$MODEM_OK" -eq 0 ]; then
    MODEM_PORT="{body.lte_port}"
    echo "  WARNUNG: Kein AT-Port gefunden. Verwende Standard: $MODEM_PORT"
    echo "  Nach Neustart pruefen: sudo python3 /tmp/at_test.py $MODEM_PORT AT"
else
    echo "  Modem: $MODEM_PORT"
    echo "  GPS:   ${{GPS_PORT:-nicht gefunden}}"
fi

# Gefundene Ports in Config speichern
if [ -n "$GPS_PORT" ]; then
    echo "gps_port = $GPS_PORT" >> /etc/dse5510.conf
fi

# SIM-Status pruefen (kein PIN)
if [ "$MODEM_OK" -eq 1 ]; then
    echo "  SIM-Status:"
    sudo python3 /tmp/at_test.py "$MODEM_PORT" "AT+CPIN?" 2>/dev/null || true
    echo "  Signalstaerke:"
    sudo python3 /tmp/at_test.py "$MODEM_PORT" "AT+CSQ" 2>/dev/null || true
    echo "  Netzwerk-Info:"
    sudo python3 /tmp/at_test.py "$MODEM_PORT" "AT+CPSI?" 2>/dev/null || true
fi

# PPP Chatscript erstellen
echo "  PPP konfigurieren..."
sudo mkdir -p /etc/chatscripts
sudo tee /etc/chatscripts/sim7600 > /dev/null << 'CHATSCRIPT'
ABORT 'BUSY'
ABORT 'NO CARRIER'
ABORT 'NO DIALTONE'
ABORT 'NO ANSWER'
ABORT 'DELAYED'
TIMEOUT 30
'' AT
OK ATE0
OK 'AT+CGDCONT=1,"IP","{body.lte_apn}"'
OK ATD*99#
CONNECT ''
CHATSCRIPT

# PPP Peer-Konfiguration (nutzt automatisch erkannten Port)
sudo tee /etc/ppp/peers/sim7600 > /dev/null << PPPCONF
$MODEM_PORT
115200
connect '/usr/sbin/chat -v -f /etc/chatscripts/sim7600'
noauth
nodefaultroute
persist
maxfail 0
holdoff 15
noipdefault
novj
novjccomp
noccp
ipcp-accept-local
ipcp-accept-remote
local
lock
nodetach
PPPCONF

# Routing-Skript: LTE nur als Fallback wenn LAN ausfaellt
sudo tee /etc/ppp/ip-up.d/99-lte-fallback > /dev/null << 'LTEFALLBACK'
#!/bin/bash
# LTE-Route mit niedriger Prioritaet (metric 700) hinzufuegen
# LAN bleibt bevorzugt (metric ~100)
ip route add default via $IPREMOTE dev $IFNAME metric 700 2>/dev/null || true
LTEFALLBACK
sudo chmod +x /etc/ppp/ip-up.d/99-lte-fallback

sudo tee /etc/ppp/ip-down.d/99-lte-fallback > /dev/null << 'LTEFALLBACKDOWN'
#!/bin/bash
# LTE-Fallback-Route entfernen wenn PPP disconnected
ip route del default via $IPREMOTE dev $IFNAME metric 700 2>/dev/null || true
LTEFALLBACKDOWN
sudo chmod +x /etc/ppp/ip-down.d/99-lte-fallback

# DNS bereits in Schritt 3a/3b konfiguriert (dhcpcd.conf + Hook + Watchdog)

# AT-Test Skript persistent ablegen (nicht in /tmp)
sudo tee /usr/local/bin/at_test.py > /dev/null << 'ATTEST'
import serial, sys, time
port, cmd = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "AT"
try:
    s = serial.Serial(port, 115200, timeout=3)
    s.write((cmd + "\r\n").encode())
    time.sleep(1.5)
    resp = s.read(s.in_waiting or 256).decode(errors="ignore").strip()
    s.close()
    print(resp)
    sys.exit(0 if "OK" in resp or "READY" in resp else 1)
except Exception as e:
    print(f"Fehler: {{e}}")
    sys.exit(1)
ATTEST
sudo chmod +x /usr/local/bin/at_test.py

# Systemd-Service fuer LTE Auto-Reconnect
sudo tee /etc/systemd/system/lte-connection.service > /dev/null << 'LTESERVICE'
[Unit]
Description=LTE Datenverbindung (SIM7600E-H)
After=network-online.target
Wants=network-online.target
Before=dse5510_sync.service

[Service]
Type=simple
ExecStartPre=/bin/sleep 30
ExecStart=/usr/sbin/pppd call sim7600
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
LTESERVICE

sudo systemctl daemon-reload
sudo systemctl enable lte-connection
sudo systemctl start lte-connection

echo "  LTE-Verbindung wird aufgebaut..."
echo "  APN: {body.lte_apn}"
echo "  Port: {body.lte_port}"

# Warte kurz auf PPP-Verbindung
sleep 10
if ip link show ppp0 &>/dev/null; then
    PPP_IP=$(ip -4 addr show ppp0 2>/dev/null | grep inet | awk '{{print $2}}')
    echo "  LTE verbunden! IP: $PPP_IP"
else
    echo "  LTE wird noch aufgebaut (kann bis zu 30s dauern)"
    echo "  Pruefen mit: ip addr show ppp0"
fi
"""

        lte_verify_block = f"""
# LTE Status pruefen
echo ""
echo "  LTE Status:"
if ip link show ppp0 &>/dev/null; then
    PPP_IP=$(ip -4 addr show ppp0 2>/dev/null | grep inet | awk '{{print $2}}')
    echo "    LTE verbunden - IP: $PPP_IP"
else
    echo "    LTE: Verbindung wird aufgebaut..."
    echo "    Pruefen: sudo journalctl -u lte-connection -n 20"
fi

# Netzwerk-Routing pruefen
echo ""
echo "  Netzwerk-Routing:"
ip route show default 2>/dev/null | while read line; do
    echo "    $line"
done
echo "  Network-Watchdog: $(systemctl is-active network-watchdog.timer 2>/dev/null || echo 'nicht aktiv')"

# Internet-Test
echo ""
echo "  Internet-Test:"
if ping -c 1 -W 3 8.8.8.8 &>/dev/null; then
    echo "    Ping 8.8.8.8: OK"
else
    echo "    Ping 8.8.8.8: FEHLT - Routing pruefen!"
fi
if ping -c 1 -W 3 google.de &>/dev/null; then
    echo "    DNS google.de: OK"
else
    echo "    DNS google.de: FEHLT - DNS pruefen!"
fi
"""

    lte_after_line = "\nAfter=lte-connection.service" if body.enable_lte else ""

    # Pre-build conditional echo lines (backslashes not allowed in f-string expressions)
    lte_header_echo = f'echo "  LTE: SIM7600E-H ({body.lte_apn})"' if body.enable_lte else ""
    lte_apn_echo = f'echo "  LTE APN:      {body.lte_apn}"' if body.enable_lte else ""
    lte_port_echo = f'echo "  LTE Port:     {body.lte_port}"' if body.enable_lte else ""
    lte_check_echo = ('echo ""\necho "  LTE pruefen:"\n'
                      'echo "    sudo systemctl status lte-connection"\n'
                      'echo "    ip addr show ppp0"\n'
                      'echo "    sudo journalctl -u lte-connection -f"') if body.enable_lte else ""

    bash_script = f"""#!/bin/bash
# ==============================================================
#  DSE 5510 Auto-Setup - {device.get('serial_number', device_id[:12])}
#  Generiert am {datetime.now().strftime('%d.%m.%Y %H:%M')}
#  RS232 Modbus RTU + GPS{" + LTE (SIM7600E-H)" if body.enable_lte else ""}
# ==============================================================
set -e

# Auto-Root: Falls nicht als root gestartet, automatisch mit sudo neu starten
if [ "$(id -u)" -ne 0 ]; then
    echo "Starte als root..."
    exec sudo bash "$0" "$@"
fi

echo "========================================================"
echo "  DSE 5510 Auto-Setup"
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

sudo pkill -f "dse5510_sync" 2>/dev/null || true
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
sudo apt-get install -y -qq python3-pip python3-venv gpsd
wait_for_apt
sudo apt-get install -y -qq gpsd-clients 2>/dev/null || echo "  gpsd-clients nicht verfuegbar (optional, Debug-Tools)"

# ===== SCHRITT 2: GPS KONFIGURIEREN =====
echo "[2/{total_steps}] GPS-Antenne konfigurieren..."

GPS_DEV=""
for dev in /dev/ttyACM0 /dev/ttyACM1 /dev/ttyUSB1 /dev/ttyUSB2 /dev/ttyAMA0; do
    if [ -e "$dev" ]; then
        if [ "$dev" != "{body.serial_port}" ] && [ "$dev" != "{lte_port}" ]; then
            GPS_DEV="$dev"
            echo "  GPS-Geraet gefunden: $GPS_DEV"
            break
        fi
    fi
done

if [ -z "$GPS_DEV" ]; then
    echo "  WARNUNG: Kein GPS-Geraet erkannt."
    echo "  Nach Anschluss: sudo dpkg-reconfigure gpsd"
    GPS_DEV="/dev/ttyACM0"
fi

sudo tee /etc/default/gpsd > /dev/null << GPSD_CONF
START_DAEMON="true"
USBAUTO="true"
DEVICES="$GPS_DEV"
GPSD_OPTIONS="-n"
GPSD_SOCKET="/var/run/gpsd.sock"
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
sudo "$INSTALL_DIR/venv/bin/pip" install --quiet pyserial requests gpsd-py3

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

    # Kirmeskiste EMU Professional II: Modbus-Register liefern Watt statt kW
    # -> Backend rechnet um, damit die Pi-Skripte nicht aktualisiert werden muessen
    is_kirmeskiste = device.get("device_type") == "kirmeskiste"

    # Prepare records for insertion
    docs = []
    for r in data.records:
        p_sum = r.get("P_sum_kW", 0)
        p_l1 = r.get("P_L1_kW", 0)
        p_l2 = r.get("P_L2_kW", 0)
        p_l3 = r.get("P_L3_kW", 0)

        # Kirmeskiste: Watt -> kW (nur wenn Wert plausibel in Watt, d.h. > 1)
        if is_kirmeskiste:
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
