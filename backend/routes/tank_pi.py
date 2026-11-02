"""Tankgeber (Raspberry Pi + Pico + Geber 0-190 Ohm, optional SIM7600-LTE wie DSE 5510).

Pi meldet /api/tank/ingest (Geraeteschluessel): Fuellstand %, Ohm, GPS, Gesundheit. Portal rechnet linear
Prozent x Tankinhalt in Liter, speichert Verlauf (tank_telemetry) und erzeugt Warnung (<25 %) / Alarm (<10 %)
als generator_alarms (generator_id = dev-<device_id>) -> sichtbar in Power Monitoring."""
import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from routes import energy_monitoring as em

router = APIRouter(prefix="/api/tank", tags=["tank"])
security = HTTPBearer()
logger = logging.getLogger("tank")
db = None
decode_jwt_token = None

OFFLINE_AFTER_SEC = 300
DEFAULT_WARN = 25
DEFAULT_CRIT = 10


def init_tank_routes(_db, _decode):
    global db, decode_jwt_token
    db, decode_jwt_token = _db, _decode


async def get_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    payload = decode_jwt_token(credentials.credentials)
    user = await db.users.find_one({"id": payload.get("user_id") or payload.get("sub")}, {"_id": 0, "password": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    return user


def _staff(user: dict) -> bool:
    if user.get("role") == "admin":
        return True
    if user.get("role") == "mitarbeiter":
        return ((user.get("apps") or {}).get("modules") or {}).get("power_monitoring") is not False
    return False


def _allowed(user: dict) -> bool:
    if _staff(user):
        return True
    gm = (user.get("apps") or {}).get("generator_monitoring") or {}
    return bool(gm.get("enabled") and gm.get("access_all"))


def capacity_liters(device: dict) -> Optional[int]:
    """'3.000 L' / '16.000 L Diesel' -> 3000 / 16000."""
    digits = re.sub(r"[^\d]", "", str(device.get("tank_capacity") or ""))
    return int(digits) if digits else None


def pi_state(device: dict) -> dict:
    last = device.get("tank_pi_last_seen")
    online = False
    if last:
        try:
            online = (datetime.now(timezone.utc) - datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds() < OFFLINE_AFTER_SEC
        except ValueError:
            pass
    return {"online": online, "last_seen": last, "health": device.get("pi_health"), "version": device.get("tank_pi_version")}


def public_tank(device: dict) -> dict:
    snap = device.get("latest_snapshot") or {}
    pi = pi_state(device)
    cap = capacity_liters(device)
    pct = snap.get("fuel_level_pct")
    return {
        "id": device["id"], "serial_number": device.get("serial_number"), "user_field": device.get("user_field"),
        "model": device.get("model"), "status": device.get("status"), "tank_capacity": device.get("tank_capacity"),
        "capacity_l": cap, "warn_pct": device.get("tank_warn_pct") or DEFAULT_WARN, "crit_pct": device.get("tank_crit_pct") or DEFAULT_CRIT,
        "last_inspection_date": device.get("last_inspection_date"), "next_inspection_date": device.get("next_inspection_date"),
        "latitude": device.get("latitude"), "longitude": device.get("longitude"), "gps": device.get("tank_pi_gps"),
        "pi": pi, "alarm_state": device.get("tank_alarm_state") or "ok",
        "fuel_level_pct": pct, "liters": snap.get("liters"), "ohm": snap.get("ohm"), "sensor_error": snap.get("sensor_error"),
        "measured_at": snap.get("timestamp"), "has_key": bool(device.get("device_key_hash")),
    }


# ---------------- Liste / Detail / Verlauf ----------------

@router.get("/devices")
async def list_tanks(user: dict = Depends(get_user)):
    if not _allowed(user):
        return {"devices": []}
    devs = await db.devices.find({"device_type": "tank", "status": {"$ne": "ausser_betrieb"}}, {"_id": 0}).to_list(500)
    return {"devices": [public_tank(d) for d in devs]}


@router.get("/{device_id}")
async def get_tank(device_id: str, user: dict = Depends(get_user)):
    if not _allowed(user):
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    d = await db.devices.find_one({"id": device_id, "device_type": "tank"}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Tank nicht gefunden")
    alarms = await db.generator_alarms.find({"generator_id": f"dev-{device_id}"}, {"_id": 0}).sort("timestamp", -1).to_list(20)
    return {**public_tank(d), "alarms": alarms, "level": "admin" if user.get("role") == "admin" else "lesen"}


@router.get("/{device_id}/telemetry")
async def tank_telemetry(device_id: str, hours: int = 24, user: dict = Depends(get_user)):
    if not _allowed(user):
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    hours = max(1, min(hours, 24 * 60))
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = await db.tank_telemetry.find({"device_id": device_id, "timestamp": {"$gte": since}},
                                        {"_id": 0, "timestamp": 1, "fuel_level_pct": 1, "liters": 1, "ohm": 1}).sort("timestamp", 1).to_list(20000)
    # fuer lange Zeitraeume ausduennen (max ~600 Punkte)
    step = max(1, len(rows) // 600)
    rows = rows[::step]
    trend = None
    if len(rows) >= 2 and rows[0].get("liters") is not None and rows[-1].get("liters") is not None:
        t0 = datetime.fromisoformat(rows[0]["timestamp"]); t1 = datetime.fromisoformat(rows[-1]["timestamp"])
        h = (t1 - t0).total_seconds() / 3600
        if h >= 1:
            lph = (rows[0]["liters"] - rows[-1]["liters"]) / h
            trend = {"liters_per_hour": round(lph, 1), "hours_left": round(rows[-1]["liters"] / lph, 1) if lph > 0.05 else None}
    return {"points": rows, "hours": hours, "trend": trend}


# ---------------- Pi-Ingest ----------------

class TankIngest(BaseModel):
    device_id: str
    api_key: str
    readings: list = []
    gps: Optional[dict] = None
    health: Optional[dict] = None


async def _alarms(device: dict, pct: Optional[float], ts: str):
    """Zustandswechsel ok -> warn -> crit erzeugt je einen Eintrag; zurueck ueber Schwelle+5 loest auf."""
    if pct is None:
        return device.get("tank_alarm_state") or "ok"
    warn = device.get("tank_warn_pct") or DEFAULT_WARN
    crit = device.get("tank_crit_pct") or DEFAULT_CRIT
    prev = device.get("tank_alarm_state") or "ok"
    new = "crit" if pct < crit else "warn" if pct < warn else "ok"
    if new == "ok" and prev != "ok" and pct < warn + 5:
        new = prev  # Hysterese
    if new == prev:
        return prev
    gid = f"dev-{device['id']}"
    name = device.get("user_field") or device.get("serial_number")
    if new in ("warn", "crit") and (prev == "ok" or new == "crit"):
        await db.generator_alarms.insert_one({
            "id": str(uuid.uuid4()), "generator_id": gid, "device_id": device["id"],
            "alarm_text": f"Tank {name}: Fuellstand {pct:.0f} % ({'kritisch, unter ' + str(crit) if new == 'crit' else 'niedrig, unter ' + str(warn)} %)",
            "severity": "alarm" if new == "crit" else "warning", "timestamp": ts, "acknowledged": False,
            "acknowledged_by": None, "resolved_at": None, "source": "tankgeber"})
    if new == "ok":
        await db.generator_alarms.update_many({"generator_id": gid, "resolved_at": None}, {"$set": {"resolved_at": ts}})
    return new


@router.post("/ingest")
async def tank_ingest(body: TankIngest):
    device = await db.devices.find_one({"id": body.device_id, "device_type": "tank"}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Tank nicht gefunden")
    if not device.get("device_key_hash") or not em._verify_key(body.api_key, device["device_key_hash"]):
        raise HTTPException(status_code=401, detail="Ungueltiger Geraeteschluessel")
    now = datetime.now(timezone.utc)
    cap = capacity_liters(device)
    docs = []
    latest = None
    for r in body.readings[-3000:]:
        try:
            ts = datetime.fromtimestamp(float(r.get("ts") or now.timestamp()), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            ts = now
        pct = r.get("fuellstand_pct")
        pct = max(0.0, min(100.0, float(pct))) if pct is not None else None
        liters = round(cap * pct / 100) if (cap and pct is not None) else None
        doc = {"device_id": device["id"], "timestamp": ts.isoformat(), "fuel_level_pct": pct, "liters": liters,
               "ohm": r.get("ohm"), "sensor_error": r.get("fehler"), "samples": r.get("samples")}
        docs.append(doc)
        if latest is None or doc["timestamp"] >= latest["timestamp"]:
            latest = doc
    if docs:
        await db.tank_telemetry.insert_many([dict(d) for d in docs])
    upd = {"tank_pi_last_seen": now.isoformat(), "last_seen": now.isoformat(), "pi_health": body.health,
           "pi_health_updated_at": now.isoformat()}
    if body.readings:
        upd["tank_pi_version"] = (body.readings[-1] or {}).get("pi_version")
    if latest:
        snap = {"fuel_level_pct": latest["fuel_level_pct"], "fuel_level": latest["fuel_level_pct"], "liters": latest["liters"],
                "ohm": latest["ohm"], "sensor_error": latest["sensor_error"], "timestamp": latest["timestamp"], "capacity_l": cap}
        upd["latest_snapshot"] = snap
        upd["tank_alarm_state"] = await _alarms(device, latest["fuel_level_pct"], now.isoformat())
    gps = body.gps or {}
    if gps.get("fix") and gps.get("lat") is not None:
        upd["tank_pi_gps"] = {**gps, "ts": now.isoformat()}
        upd["latitude"], upd["longitude"], upd["last_gps_update"] = gps["lat"], gps["lon"], now.isoformat()
    elif body.gps is not None:
        upd["tank_pi_gps"] = {**gps, "ts": now.isoformat(), "fix": False}
    await db.devices.update_one({"id": device["id"]}, {"$set": upd})
    return {"ok": True, "stored": len(docs), "liters": latest["liters"] if latest else None, "alarm_state": upd.get("tank_alarm_state")}


# ---------------- Pi-Setup-Skript ----------------

class TankSetupRequest(BaseModel):
    enable_lte: bool = True
    lte_apn: str = "internet.m2mportal.de"
    interval: int = 60


@router.post("/{device_id}/pi-setup")
async def tank_pi_setup(device_id: str, request: Request, body: TankSetupRequest = None, user: dict = Depends(get_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    body = body or TankSetupRequest()
    device = await db.devices.find_one({"id": device_id, "device_type": "tank"}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Tank nicht gefunden")
    plain_key = secrets.token_hex(24)
    await db.devices.update_one({"id": device_id}, {"$set": {"device_key_hash": em._hash_key(plain_key), "updated_at": datetime.now(timezone.utc).isoformat()}})
    api_url = em._get_api_base(request)
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
    with open(os.path.join(static_dir, "tank_pi_sync.py"), "r", encoding="utf-8") as f:
        sync_script = f.read()
    total = 7 if body.enable_lte else 6
    lte_setup, lte_verify = em._build_lte_blocks(body.lte_apn, total, step=4) if body.enable_lte else ("", "")
    script = _build_script(device, device_id, plain_key, api_url, sync_script, body, total, lte_setup, lte_verify)
    token = secrets.token_urlsafe(32)
    em._setup_downloads[token] = {"script": script, "device_id": device_id, "created_at": datetime.now(timezone.utc).isoformat(),
                                  "device_name": device.get("serial_number")}
    return {"download_url": f"{api_url}/energy-monitoring/setup-download/{token}", "device_id": device_id,
            "message": f"Tankgeber-Setup generiert fuer {device.get('serial_number', '')}"}


def _build_script(device, device_id, plain_key, api_url, sync_script, body, total, lte_setup, lte_verify) -> str:
    name = device.get("serial_number", device_id[:12])
    lte_after = "\nAfter=lte-failover.service" if body.enable_lte else ""
    lte_echo = f'echo "  LTE: SIM7600E-H ({body.lte_apn}) - Tools: lte-status, gps-status"' if body.enable_lte else ""
    return f"""#!/bin/bash
# ==============================================================
#  Tankgeber Pi Auto-Setup - {name}
#  Generiert am {datetime.now().strftime('%d.%m.%Y %H:%M')}
#  Raspberry Pi + Pico (ADC, Geber 0-190 Ohm) + GPS{" + LTE (SIM7600E-H)" if body.enable_lte else ""}
# ==============================================================
set -e
if [ "$(id -u)" -ne 0 ]; then
    echo "Starte als root..."
    exec sudo bash "$0" "$@"
fi
echo "========================================================"
echo "  Tankgeber Pi Auto-Setup"
echo "  Geraet: {name}"
{lte_echo}
echo "========================================================"
wait_for_apt() {{
    while fuser /var/lib/dpkg/lock-frontend &>/dev/null 2>&1; do echo "  Warte auf apt-Lock..."; sleep 3; done
}}

# ===== SCHRITT 0: ALTE INSTALLATION AUFRAUMEN =====
echo ""
echo "[0/{total}] Alte Installation aufraumen..."
for SVC in tank_pi_sync tankanzeige; do
    systemctl stop "$SVC" 2>/dev/null || true
    systemctl disable "$SVC" 2>/dev/null || true
    rm -f "/etc/systemd/system/$SVC.service"
done
pkill -f "tank_pi_sync|tankanzeige.py" 2>/dev/null || true
systemctl daemon-reload
echo "  Aufraumen abgeschlossen."

# ===== SCHRITT 1: PAKETE =====
echo ""
echo "[1/{total}] System aktualisieren..."
wait_for_apt
apt-get update -qq
wait_for_apt
apt-get install -y -qq python3-pip python3-venv python3-serial gpsd gpsd-clients wget usbutils
pip3 install --break-system-packages --quiet mpremote 2>/dev/null || pip3 install --quiet mpremote 2>/dev/null || true

# Pi 5: USB-Autosuspend aus (SIM7600 + USB-Geraete)
if [ -f /boot/firmware/cmdline.txt ]; then CMDLINE=/boot/firmware/cmdline.txt; elif [ -f /boot/cmdline.txt ]; then CMDLINE=/boot/cmdline.txt; else CMDLINE=""; fi
if [ -n "$CMDLINE" ] && ! grep -q "usbcore.autosuspend=-1" "$CMDLINE"; then
    sed -i 's| *$| usbcore.autosuspend=-1|' "$CMDLINE"
fi

# Stabiler Pfad fuer den Pico (ueberlebt Neu-Nummerierung): /dev/tank-pico
tee /etc/udev/rules.d/99-tank-pico.rules > /dev/null << 'UDEV'
# Raspberry Pi Pico (MicroPython USB-Serial, Vendor 2e8a) -> /dev/tank-pico
SUBSYSTEM=="tty", ATTRS{{idVendor}}=="2e8a", SYMLINK+="tank-pico", MODE="0666"
UDEV
udevadm control --reload-rules
udevadm trigger --subsystem-match=tty 2>/dev/null || true

# ===== SCHRITT 2: PICO (MicroPython + Messprogramm) =====
echo ""
echo "[2/{total}] Pico einrichten..."
INSTALL_DIR="/opt/tank_pi"
mkdir -p "$INSTALL_DIR"
cat > "$INSTALL_DIR/main.py" << 'PICO'
from machine import ADC
import time, json
R_REF = 100.0
R_LEER = 0.0
R_VOLL = 190.0
adc = ADC(26)
def messen(n=64):
    s = 0
    for _ in range(n):
        s += adc.read_u16()
        time.sleep_ms(2)
    return s / n
while True:
    raw = messen()
    if raw > 64000:
        print(json.dumps({{"fehler": "Geber offen / Kabelbruch"}}))
    else:
        r = R_REF * raw / (65535 - raw)
        pct = (r - R_LEER) / (R_VOLL - R_LEER) * 100
        pct = max(0, min(100, pct))
        print(json.dumps({{"ohm": round(r, 1), "fuellstand": round(pct, 1)}}))
    time.sleep(1)
PICO

mp() {{ timeout 30 python3 -m mpremote "$@"; }}
pico_port() {{ [ -e /dev/tank-pico ] && echo /dev/tank-pico || ls /dev/ttyACM* 2>/dev/null | head -1; }}
pico_hat_micropython() {{
    local p; p=$(pico_port); [ -n "$p" ] || return 1
    mp connect "$p" exec "import sys; print(sys.implementation.name)" 2>/dev/null | grep -q micropython
}}
pico_im_bootmodus() {{ lsblk -no LABEL 2>/dev/null | grep -qx "RPI-RP2"; }}

FW_VERSION="20241129-v1.24.1"
if pico_im_bootmodus; then
    BRAUCHT_FLASH=1
elif pico_hat_micropython; then
    echo "  MicroPython ist bereits auf dem Pico."
    BRAUCHT_FLASH=0
else
    BRAUCHT_FLASH=1
    echo ""
    echo "  Auf dem Pico ist noch kein MicroPython."
    echo "  1. Pico vom USB abziehen  2. BOOTSEL gedrueckt halten  3. einstecken, loslassen"
    if [ -t 0 ]; then read -rp "  Danach Enter druecken ... "; fi
fi
if [ "$BRAUCHT_FLASH" = "1" ]; then
    echo -n "  Warte auf Pico im Boot-Modus "
    for i in $(seq 1 60); do pico_im_bootmodus && break; echo -n "."; sleep 1; done; echo
    if ! pico_im_bootmodus; then
        echo "  FEHLER: Pico nicht im Boot-Modus. BOOTSEL-Schritt wiederholen und Skript erneut starten."
        exit 1
    fi
    BOARD="RPI_PICO"
    FW="$INSTALL_DIR/${{BOARD}}-${{FW_VERSION}}.uf2"
    [ -f "$FW" ] || wget -q -O "$FW" "https://micropython.org/resources/firmware/${{BOARD}}-${{FW_VERSION}}.uf2"
    mkdir -p /mnt/pico && mount -L RPI-RP2 /mnt/pico && cp "$FW" /mnt/pico/ && sync && umount /mnt/pico 2>/dev/null || true
    echo "  Firmware geschrieben, Pico startet neu ..."
    for i in $(seq 1 30); do [ -n "$(pico_port)" ] && break; sleep 1; done; sleep 2
fi
PICO_PORT=$(pico_port)
if [ -z "$PICO_PORT" ]; then
    echo "  FEHLER: Pico meldet sich nicht als /dev/ttyACM*. USB-Datenkabel pruefen."
    exit 1
fi
cd "$INSTALL_DIR"
if mp connect "$PICO_PORT" cp main.py :main.py > /dev/null; then
    mp connect "$PICO_PORT" reset > /dev/null 2>&1 || true
    sleep 3
    echo "  Messprogramm auf dem Pico ($PICO_PORT)."
else
    echo "  WARNUNG: Hochladen auf den Pico fehlgeschlagen (python3 -m mpremote connect $PICO_PORT ls)"
fi
TESTDATEN=$(timeout 5 cat "$PICO_PORT" 2>/dev/null | grep "{{" | tail -n 1 || true)
[ -n "$TESTDATEN" ] && echo "  Pico liefert: $TESTDATEN" || echo "  Noch keine Daten (nach Reset normal)."

# ===== SCHRITT 3: GPS (SIM7600 NMEA -> gpsd) =====
echo ""
echo "[3/{total}] GPS konfigurieren..."
if lsusb | grep -q "1e0e:9001"; then
    for at in /dev/ttyUSB2 /dev/ttyUSB3 /dev/ttyUSB1; do
        [ -e "$at" ] || continue
        stty -F "$at" 115200 raw -echo 2>/dev/null || continue
        (echo -ne "AT+CGPS=1\\r\\n" > "$at") &
        if timeout 2 head -c 200 "$at" 2>/dev/null | grep -qE "OK|CGPS|ERROR"; then
            wait; (echo -ne "AT+CGPSAUTO=1\\r\\n" > "$at") & timeout 2 head -c 100 "$at" >/dev/null 2>&1; wait 2>/dev/null
            echo "  SIM7600 GPS aktiviert ueber $at"; break
        fi
        wait 2>/dev/null
    done
    sleep 5
fi
# NMEA-Port suchen (ttyACM = Pico wird ausgelassen)
GPS_DEV=""
for attempt in 1 2 3; do
    for port in /dev/ttyUSB2 /dev/ttyUSB1 /dev/ttyUSB0 /dev/ttyUSB3 /dev/ttyUSB4; do
        [ -e "$port" ] || continue
        for baud in 115200 9600; do
            stty -F "$port" $baud raw -echo 2>/dev/null || continue
            if timeout 4 cat "$port" 2>/dev/null | grep -qE '^\\$(GP|GN|GL|BD)'; then GPS_DEV="$port"; break 2; fi
        done
    done
    [ -n "$GPS_DEV" ] && break
    sleep 4
done
[ -z "$GPS_DEV" ] && GPS_DEV="/dev/ttyUSB2" && echo "  Kein NMEA gefunden - Fallback $GPS_DEV"
tee /etc/default/gpsd > /dev/null << GPSD
START_DAEMON="true"
USBAUTO="false"
DEVICES="$GPS_DEV"
GPSD_OPTIONS="-n -b"
GPSD
systemctl unmask gpsd gpsd.socket 2>/dev/null || true
systemctl enable gpsd
systemctl restart gpsd.socket gpsd
echo "  gpsd: $GPS_DEV"
{lte_setup}
# ===== SCHRITT {5 if body.enable_lte else 4}: SYNC-SKRIPT =====
echo ""
echo "[{5 if body.enable_lte else 4}/{total}] Sync-Skript installieren..."
python3 -m venv --system-site-packages "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet pyserial requests
tee "$INSTALL_DIR/tank_pi_sync.py" > /dev/null << 'SYNC_SCRIPT'
{sync_script}
SYNC_SCRIPT
chmod +x "$INSTALL_DIR/tank_pi_sync.py"
mkdir -p /var/lib/tank_pi
tee /etc/tank_pi.conf > /dev/null << 'CONF'
[tank]
api_url = {api_url}
device_key = {plain_key}
device_id = {device_id}
interval = {body.interval}
serial = /dev/tank-pico
CONF
chmod 600 /etc/tank_pi.conf
[ -e /dev/tank-pico ] || sed -i "s|serial = /dev/tank-pico|serial = $PICO_PORT|" /etc/tank_pi.conf

# ===== SCHRITT {6 if body.enable_lte else 5}: SYSTEMD =====
echo ""
echo "[{6 if body.enable_lte else 5}/{total}] Systemd-Service einrichten..."
tee /etc/systemd/system/tank_pi_sync.service > /dev/null << SERVICE
[Unit]
Description=Tankgeber Sync - Eventenergie Portal
After=network-online.target gpsd.service{lte_after}
Wants=network-online.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/tank_pi_sync.py
Restart=always
RestartSec=10
WorkingDirectory=$INSTALL_DIR

[Install]
WantedBy=multi-user.target
SERVICE
systemctl daemon-reload
systemctl enable tank_pi_sync
systemctl restart tank_pi_sync

# ===== SCHRITT {total}: VERIFIZIERUNG =====
echo ""
echo "[{total}/{total}] Verifiziere..."
sleep 5
systemctl is-active --quiet tank_pi_sync && echo "  Sync-Service laeuft" || echo "  WARNUNG: Sync-Service nicht aktiv (journalctl -u tank_pi_sync -n 30)"
journalctl -u tank_pi_sync -n 5 --no-pager 2>/dev/null || true
{lte_verify}
echo ""
echo "========================================================"
echo "  Setup abgeschlossen!"
echo "========================================================"
echo "  Geraet-ID:     {device_id}"
echo "  Portal:        {api_url}"
echo "  Pico:          $PICO_PORT (Geber 0-190 Ohm, R_REF 100 Ohm)"
echo "  Konfiguration: /etc/tank_pi.conf"
echo "  Logs:          sudo journalctl -u tank_pi_sync -f"
echo "  Rohdaten Pico: sudo systemctl stop tank_pi_sync && cat $PICO_PORT"
echo ""
echo "  System wird in 10 Sekunden neu gestartet (Strg+C bricht ab)..."
sleep 10
reboot
"""
