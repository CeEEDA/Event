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

    # Enrich with meter count and latest data
    result = []
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
#  Messkoffer Setup - Eventenergie Portal
#  Geraet: {device_name}
#  Erstellt: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
# ================================================================
#
#  Nutzung:  sudo bash setup_messkoffer.sh
#
#  Was passiert:
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
echo -e "${{CYAN}}==========================================${{NC}}"
echo -e "${{CYAN}}  Messkoffer Setup - Eventenergie Portal${{NC}}"
echo -e "${{CYAN}}==========================================${{NC}}"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo -e "${{RED}}Fehler: Bitte mit sudo ausfuehren:${{NC}}"
    echo "  sudo bash $0"
    exit 1
fi

# ---- 1. Abhaengigkeiten ----
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
    # Sicherstellen dass python3-gps da ist
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

# ---- 2. Logger-Skript installieren ----
echo -e "${{YELLOW}}[2/5] Installiere Messkoffer-Logger...${{NC}}"
mkdir -p /var/lib/messkoffer
cat > /opt/messkoffer_logger.py << 'LOGGER_EOF'
{logger_py_content}
LOGGER_EOF
chmod +x /opt/messkoffer_logger.py
echo "  /opt/messkoffer_logger.py erstellt"

# ---- 3. Konfiguration ----
echo -e "${{YELLOW}}[3/5] Schreibe Konfiguration...${{NC}}"
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

# ---- 4. Systemd-Dienst ----
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

# ---- 5. Starten ----
echo -e "${{YELLOW}}[5/5] Starte Dienste...${{NC}}"

# Alten emu_sync stoppen falls vorhanden
systemctl stop emu_sync 2>/dev/null || true
systemctl disable emu_sync 2>/dev/null || true

systemctl restart messkoffer
sleep 3

if systemctl is-active --quiet messkoffer; then
    echo ""
    echo -e "${{GREEN}}==========================================${{NC}}"
    echo -e "${{GREEN}}  Setup erfolgreich!${{NC}}"
    echo -e "${{GREEN}}==========================================${{NC}}"
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
echo "  Kirmeskiste Auto-Setup"
echo "  Geraet: {device.get('serial_number', device_id[:12])}"
echo "========================================================"

# ----- System aktualisieren -----
echo "[1/5] System aktualisieren..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv gpsd gpsd-clients

# ----- Python-Umgebung -----
echo "[2/5] Python-Umgebung einrichten..."
INSTALL_DIR="/opt/kirmeskiste"
sudo mkdir -p "$INSTALL_DIR"
sudo python3 -m venv "$INSTALL_DIR/venv"
sudo "$INSTALL_DIR/venv/bin/pip" install --quiet "pymodbus>=3.7" requests gpsd-py3

# ----- Sync-Skript installieren -----
echo "[3/5] Sync-Skript installieren..."
sudo tee "$INSTALL_DIR/kirmeskiste_sync.py" > /dev/null << 'SYNC_SCRIPT'
{sync_script}
SYNC_SCRIPT
sudo chmod +x "$INSTALL_DIR/kirmeskiste_sync.py"

# ----- Konfiguration -----
echo "[4/5] Konfiguration schreiben..."
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

# ----- Systemd Service -----
echo "[5/5] Systemd-Service einrichten..."
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
sudo systemctl start kirmeskiste_sync

echo ""
echo "========================================================"
echo "  Setup abgeschlossen!"
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


# ============== Ingest API (Pi Push) ==============

@router.post("/ingest")
async def ingest_data(data: IngestBatch):
    """Receive batch of EMU data from Pi sync script. Authenticated via per-device key."""
    # First try per-device key authentication
    device = await db.devices.find_one({"id": data.device_id, "device_type": {"$in": ["messkoffer", "kirmeskiste"]}})
    if not device:
        logger.warning(f"Ingest 404: device_id={data.device_id}, meter_id={data.meter_id} - Geraet nicht in DB")
        raise HTTPException(status_code=404, detail=f"Geraet nicht gefunden (device_id: {data.device_id})")

    # Verify device key
    key_hash = device.get("device_key_hash")
    if not key_hash:
        # Fallback: check legacy global key
        settings = await db.emu_settings.find_one({"key": "ingest_api_key"}, {"_id": 0})
        if not settings or settings.get("value") != data.api_key:
            raise HTTPException(status_code=401, detail="Kein Geräteschlüssel konfiguriert")
    else:
        if not _verify_key(data.api_key, key_hash):
            raise HTTPException(status_code=401, detail="Ungültiger Geräteschlüssel")

    meter = await db.emu_meters.find_one({"id": data.meter_id, "device_id": data.device_id}, {"_id": 0})
    if not meter:
        # Auto-register meter when device is authenticated but meter is unknown
        device_name = device.get("serial_number", data.device_id)
        meter_doc = {
            "id": data.meter_id,
            "device_id": data.device_id,
            "meter_name": f"Auto-registriert ({device_name})",
            "meter_ip": "",
            "description": "Automatisch beim ersten Datenempfang erstellt",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.emu_meters.insert_one(meter_doc)
        logger.info(f"Auto-registered meter {data.meter_id} for device {data.device_id} ({device_name})")
        meter = {k: v for k, v in meter_doc.items() if k != "_id"}

    if not data.records:
        return {"inserted": 0, "message": "Keine Datensätze"}

    # Prepare records for insertion
    docs = []
    for r in data.records:
        doc = {
            "id": str(uuid.uuid4()),
            "device_id": data.device_id,
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
            "P_sum_kW": r.get("P_sum_kW", 0),
            "P_L1_kW": r.get("P_L1_kW", 0),
            "P_L2_kW": r.get("P_L2_kW", 0),
            "P_L3_kW": r.get("P_L3_kW", 0),
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
            "source_id": r.get("id"),  # Original SQLite row ID for dedup
        }
        docs.append(doc)

    await db.emu_data.insert_many(docs)

    # Update sync state
    if data.last_sync_id:
        await db.emu_sync_state.update_one(
            {"device_id": data.device_id, "meter_id": data.meter_id},
            {"$set": {"last_sync_id": data.last_sync_id, "last_sync_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )

    # Update device last_seen for online status tracking
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.devices.update_one(
        {"id": data.device_id},
        {"$set": {"last_seen": now_iso}}
    )

    logger.info(f"Ingest: {len(docs)} records for device={data.device_id} meter={data.meter_id}")
    return {"inserted": len(docs), "message": f"{len(docs)} Datensätze empfangen"}


@router.get("/ingest/sync-state")
async def get_sync_state(device_id: str, meter_id: str, api_key: str):
    """Get the last synced ID for a device/meter pair."""
    # Verify per-device key
    device = await db.devices.find_one({"id": device_id})
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
        {"device_id": device_id, "meter_id": meter_id},
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
