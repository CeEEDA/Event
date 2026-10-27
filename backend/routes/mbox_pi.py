"""M-Box Erweiterungen: Pi im Lichtmast (Audio + GPS) und Auftrags-Zuweisung fuer Kunden.

Pi-Anbindung nach DSE-5510-Muster: Setup-Skript mit eingebettetem Geraeteschluessel,
Pi pollt das Portal (POST /pi/{id}/sync), bekommt Befehle und Audio-Manifest zurueck.
"""
import hashlib
import hmac
import math
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse

AUDIO_DIR = Path(__file__).resolve().parent.parent / "mbox_service" / "audio"
PI_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "static" / "mbox_pi_sync.py"
PI_ONLINE_SEC = 20
DEFAULT_RADIUS_KM = 1.0
RADIUS_STEP_KM = 0.5
MAX_RADIUS_KM = 10.0
# Was ein Kunde an seinen zugewiesenen Masten schalten darf ("Nur Licht und Audio")
KUNDE_BEFEHLE = {"Lampen_Ein", "Lampen_Aus", "Lampe_Umschalten", "Schnellstart", "Schnellstop", "Quittieren"}

_setup_downloads: dict = {}


def _hash(k: str) -> str:
    return hashlib.sha256(k.encode()).hexdigest()


def verify_pi_key(device: dict, api_key: str):
    h = device.get("mbox_pi_key_hash")
    if not h or not api_key or not hmac.compare_digest(_hash(api_key), h):
        raise HTTPException(status_code=401, detail="Ungueltiger Geraeteschluessel")


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def api_base(request: Request) -> str:
    explicit = os.environ.get("API_BASE_URL", "")
    if explicit:
        return explicit.rstrip("/")
    fe = os.environ.get("FRONTEND_URL", "")
    if fe and "localhost" not in fe and "preview.emergentagent.com" not in fe:
        return fe.rstrip("/") + "/api"
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", ""))
    return f"{scheme}://{host}/api"


# ---------------- Audio-Dateien ----------------

def audio_manifest() -> list:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(AUDIO_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in (".mp3", ".wav", ".ogg"):
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            out.append({"name": p.name, "sha256": h.hexdigest(), "size": p.stat().st_size})
    return out


def audio_file_response(name: str) -> FileResponse:
    safe = os.path.basename(name)
    p = AUDIO_DIR / safe
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Audiodatei nicht gefunden")
    return FileResponse(str(p), filename=safe)


def pi_state(device: dict) -> dict:
    last = device.get("mbox_pi_last_seen")
    online = False
    if last:
        try:
            online = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() < PI_ONLINE_SEC
        except Exception:
            pass
    return {
        "configured": bool(device.get("mbox_pi_key_hash")),
        "online": online,
        "last_seen": last,
        "playing": device.get("mbox_pi_playing") if online else None,
        "gps": device.get("mbox_pi_gps"),
        "gps_status": device.get("mbox_pi_gps_status"),
        "files": device.get("mbox_pi_files") or [],
        "volume": device.get("mbox_pi_volume"),
        "audio_device": device.get("mbox_pi_audio_device") or "",
        "audio_cards": device.get("mbox_pi_audio_cards") or [],
        "last_error": device.get("mbox_pi_last_error"),
        "version": device.get("mbox_pi_version"),
        "hostname": device.get("mbox_pi_hostname"),
        "script_current": device.get("mbox_pi_version") == pi_script_version(),
    }


def pi_script_bytes() -> bytes:
    return PI_SCRIPT_PATH.read_bytes()


def pi_script_sha() -> str:
    return hashlib.sha256(pi_script_bytes()).hexdigest()


def pi_script_version() -> str:
    m = re.search(r'^VERSION = "([^"]+)"', PI_SCRIPT_PATH.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else ""


# ---------------- Setup-Skript ----------------

def embedded_audio_block() -> str:
    """Alle Standard-Audiodateien (z.B. Testansage) base64 ins Setup einbetten,
    damit sie sofort nach der Installation auf dem Pi liegen - auch ohne ersten Sync."""
    import base64
    parts = []
    for m in audio_manifest():
        data = base64.b64encode((AUDIO_DIR / m["name"]).read_bytes()).decode("ascii")
        parts.append(f'''echo "  -> {m['name']} ({m['size'] // 1024} KB)"
base64 -d > "/opt/mbox_audio/{m['name']}" <<'B64EOF'
{data}
B64EOF
if [ "$(sha256sum "/opt/mbox_audio/{m['name']}" | cut -d' ' -f1)" != "{m['sha256']}" ]; then
  echo "  WARNUNG: Pruefsumme von {m['name']} stimmt nicht - Datei wird beim ersten Sync neu geladen"
  rm -f "/opt/mbox_audio/{m['name']}"
fi''')
    return "\n".join(parts) if parts else 'echo "  (keine Standard-Audiodateien auf dem Server)"'


def build_setup_script(device: dict, plain_key: str, base: str, volume: int) -> str:
    name = device.get("user_field") or device.get("serial_number") or device["id"]
    py = PI_SCRIPT_PATH.read_text(encoding="utf-8")
    return f'''#!/bin/bash
# ================================================================
#  M-Box Pi Setup - Eventenergie Portal
#  Lichtmast: {name}
#  Erstellt:  {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
# ================================================================
#  Nutzung:  sudo bash setup.sh
#  Richtet ein: mpg123 (Audio), DAC als ALSA-Standard, gpsd (USB-GPS),
#               /opt/mbox_pi_sync.py, Testansage in /opt/mbox_audio,
#               /etc/mbox_pi.conf, systemd-Dienst "mbox_pi"
# ================================================================
set -e
if [ "$EUID" -ne 0 ]; then echo "Bitte mit sudo ausfuehren: sudo bash $0"; exit 1; fi

echo "[1/7] Pakete installieren..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-requests mpg123 alsa-utils gpsd gpsd-clients >/dev/null

echo "[2/7] DAC als Standard-Audioausgabe setzen..."
# Bevorzugt: DAC / USB-Soundkarte; HDMI und Onboard-Headphones nur als Rueckfall
CARDS="$(aplay -l 2>/dev/null | grep -E '^card [0-9]+:' || true)"
DAC_CARD="$(echo "$CARDS" | grep -iE 'dac|usb|codec|hifiberry|iqaudio|pcm5|wm8' | grep -viE 'hdmi|vc4' | head -n1 | sed -E 's/^card ([0-9]+):.*/\\1/')"
if [ -z "$DAC_CARD" ]; then
  DAC_CARD="$(echo "$CARDS" | grep -viE 'hdmi|vc4' | head -n1 | sed -E 's/^card ([0-9]+):.*/\\1/')"
fi
if [ -n "$DAC_CARD" ]; then
  DAC_NAME="$(echo "$CARDS" | grep -E "^card $DAC_CARD:" | head -n1 | sed -E 's/^card [0-9]+: [^[]*\\[([^]]+)\\].*/\\1/')"
  cat > /etc/asound.conf <<EOF
# Eventenergie M-Box: Standardausgabe = $DAC_NAME (card $DAC_CARD)
defaults.pcm.card $DAC_CARD
defaults.ctl.card $DAC_CARD
EOF
  echo "  Standardausgabe: card $DAC_CARD ($DAC_NAME)"
  for CTL in PCM Master Speaker Headphone Digital; do amixer -c "$DAC_CARD" sset "$CTL" "{volume}%" unmute >/dev/null 2>&1 || true; done
else
  echo "  WARNUNG: keine Soundkarte gefunden (aplay -l leer) - DAC anschliessen und Setup erneut ausfuehren"
fi

echo "[3/7] gpsd fuer USB-GPS konfigurieren..."
# GPS-Empfaenger finden: stabiler by-id-Pfad bevorzugt (u-blox etc.), sonst ttyACM/ttyUSB
GPS_DEV=""
for CAND in /dev/serial/by-id/*u-blox* /dev/serial/by-id/*GPS* /dev/serial/by-id/*GNSS* /dev/serial/by-id/*Prolific* /dev/serial/by-id/*; do
  if [ -e "$CAND" ]; then GPS_DEV="$CAND"; break; fi
done
if [ -z "$GPS_DEV" ]; then
  for CAND in /dev/ttyACM0 /dev/ttyACM1 /dev/ttyUSB0 /dev/ttyUSB1; do
    if [ -e "$CAND" ]; then GPS_DEV="$CAND"; break; fi
  done
fi
# Mit leerem DEVICES findet gpsd einen BEREITS gesteckten Empfaenger nicht (nur per USB-Hotplug) -> fest eintragen
cat > /etc/default/gpsd <<EOF
START_DAEMON="true"
USBAUTO="true"
DEVICES="$GPS_DEV"
GPSD_OPTIONS="-n"
EOF
systemctl enable gpsd >/dev/null 2>&1 || true
systemctl restart gpsd || true
sleep 2
if [ -n "$GPS_DEV" ]; then
  gpsdctl add "$GPS_DEV" >/dev/null 2>&1 || true   # laufendem gpsd das Geraet sofort anhaengen
  echo "  GPS-Empfaenger: $GPS_DEV"
else
  echo "  WARNUNG: kein GPS-Empfaenger gefunden - Stick anschliessen; gpsd uebernimmt ihn dann per USB-Hotplug"
fi

echo "[4/7] Sync-Skript installieren..."
mkdir -p /opt/mbox_audio
cat > /opt/mbox_pi_sync.py <<'PYEOF'
{py}
PYEOF
chmod +x /opt/mbox_pi_sync.py

echo "[5/7] Standard-Audiodateien (Testansage) ablegen..."
{embedded_audio_block()}

echo "[6/7] Konfiguration schreiben..."
cat > /etc/mbox_pi.conf <<EOF
[mbox_pi]
api_url = {base}
device_id = {device["id"]}
device_key = {plain_key}
audio_device =
volume = {volume}
EOF
chmod 600 /etc/mbox_pi.conf

echo "[7/7] Systemd-Dienst einrichten..."
cat > /etc/systemd/system/mbox_pi.service <<'EOF'
[Unit]
Description=M-Box Pi Sync (Audio + GPS) - Eventenergie Portal
After=network-online.target sound.target gpsd.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/mbox_pi_sync.py
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable mbox_pi >/dev/null 2>&1
systemctl restart mbox_pi

echo ""
echo "Fertig. Status: sudo systemctl status mbox_pi   Log: sudo journalctl -u mbox_pi -f"
echo "Soundkarten:    aplay -l      Soundtest: speaker-test -c2 -t wav -l1      GPS-Test: gpspipe -w -n 10"
'''.replace("\r\n", "\n")


def store_setup(script: str, device_name: str) -> str:
    token = secrets.token_urlsafe(16)
    now = datetime.now(timezone.utc)
    for k in [k for k, v in _setup_downloads.items() if (now - v["created_at"]).total_seconds() > 3600]:
        _setup_downloads.pop(k, None)
    _setup_downloads[token] = {"script": script, "created_at": now, "device_name": device_name}
    return token


def setup_download(token: str) -> PlainTextResponse:
    e = _setup_downloads.get(token)
    if not e or (datetime.now(timezone.utc) - e["created_at"]).total_seconds() > 3600:
        _setup_downloads.pop(token, None)
        raise HTTPException(status_code=410, detail="Download-Link abgelaufen oder ungueltig")
    return PlainTextResponse(e["script"], media_type="text/plain",
                             headers={"Content-Disposition": 'attachment; filename="setup_mbox_pi.sh"'})


def new_pi_key() -> tuple[str, str]:
    k = secrets.token_hex(24)
    return k, _hash(k)


# ---------------- Auftrags-Zuweisung ----------------

def device_position(device: dict) -> Optional[tuple]:
    """GPS vom Pi (USB-Antenne) hat Vorrang, sonst manuell gepflegte Koordinaten."""
    gps = device.get("mbox_pi_gps") or {}
    if gps.get("fix") and gps.get("lat") is not None:
        return float(gps["lat"]), float(gps["lon"])
    if device.get("latitude") is not None and device.get("longitude") is not None:
        return float(device["latitude"]), float(device["longitude"])
    return None


def today_str() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


def order_active(order: dict, day: Optional[str] = None) -> bool:
    """Von Lieferung (Dispo-Start) bis Abholung (Dispo-Ende) laut Auftrag."""
    day = day or today_str()
    s = order.get("dispo_start") or order.get("event_start") or ""
    e = order.get("dispo_end") or order.get("event_end") or ""
    if s in ("", "0000-00-00") or e in ("", "0000-00-00"):
        return False
    return s[:10] <= day <= e[:10]


async def compute_order_mboxes(db, order_pk, devices: Optional[list] = None) -> dict:
    """Umkreis-Zuweisung: 1 km, Radius waechst in 500-m-Schritten bis die erwartete
    Mastanzahl erreicht ist (maximal 10 km). Manuelle Overrides haben Vorrang."""
    pk = str(order_pk)
    settings = await db.order_settings.find_one({"order_pk": int(order_pk)}, {"_id": 0}) or {}
    cfg = await db.mbox_order_config.find_one({"order_pk": pk}, {"_id": 0}) or {}
    overrides = await db.mbox_order_overrides.find({"order_pk": pk}, {"_id": 0}).to_list(200)
    forced = {o["device_id"] for o in overrides if o.get("action") == "add"}
    blocked = {o["device_id"] for o in overrides if o.get("action") == "remove"}
    if devices is None:
        devices = await db.devices.find({"device_type": "mbox", "status": {"$ne": "ausser_betrieb"}}, {"_id": 0}).to_list(500)

    center = (settings.get("center_lat"), settings.get("center_lng"))
    has_center = center[0] is not None and center[1] is not None
    expected = int(cfg.get("expected_count") or 0)
    base_radius = float(cfg.get("radius_km") or DEFAULT_RADIUS_KM)

    with_dist = []
    for d in devices:
        pos = device_position(d)
        dist = haversine_km(center[0], center[1], pos[0], pos[1]) if (has_center and pos) else None
        with_dist.append((d, dist))

    radius = base_radius
    if has_center:
        inside = lambda r: [x for x in with_dist if x[1] is not None and x[1] <= r and x[0]["id"] not in blocked]
        while expected and len(inside(radius)) < expected and radius < MAX_RADIUS_KM:
            radius = round(radius + RADIUS_STEP_KM, 2)
        auto_ids = {x[0]["id"] for x in inside(radius)}
    else:
        auto_ids = set()

    result = []
    for d, dist in with_dist:
        if d["id"] in forced:
            mode = "manuell"
        elif d["id"] in auto_ids:
            mode = "auto"
        else:
            continue
        result.append({
            "id": d["id"], "serial_number": d.get("serial_number"), "name": d.get("user_field") or d.get("serial_number"),
            "distance_km": round(dist, 2) if dist is not None else None, "mode": mode,
            "position": device_position(d), "pi": pi_state(d),
        })
    result.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] or 0))
    return {
        "order_pk": pk, "center": {"lat": center[0], "lng": center[1]} if has_center else None,
        "radius_km": base_radius, "radius_used_km": radius if has_center else None,
        "expected_count": expected, "blocked_ids": sorted(blocked), "devices": result,
        "candidates": [{"id": d["id"], "name": d.get("user_field") or d.get("serial_number"), "distance_km": round(dist, 2) if dist is not None else None}
                       for d, dist in sorted(with_dist, key=lambda x: (x[1] is None, x[1] or 0))],
    }


def order_upcoming(order: dict, day: Optional[str] = None) -> bool:
    """Auftrag liegt noch vor uns (Kunde darf schon Durchsagen vorbereiten, aber keine Masten bedienen)."""
    day = day or today_str()
    s = order.get("dispo_start") or order.get("event_start") or ""
    return s not in ("", "0000-00-00") and s[:10] > day


async def customer_orders(db, user: dict, upcoming: bool = False) -> list:
    """Auftraege des Kunden ueber EpiRent-Kundennummer ODER explizite Freigabe in der Auftrags-Kachel.
    Standard: nur heute aktive (Lieferung..Abholung); upcoming=True liefert zusaetzlich kommende Auftraege."""
    cno = str(user.get("customer_no") or "").strip()
    cfgs = await db.mbox_order_config.find({"customer_user_ids": user["id"]}, {"_id": 0, "order_pk": 1}).to_list(500)
    freigegeben = {str(c["order_pk"]) for c in cfgs}
    if not cno and not freigegeben:
        return []
    orders = await db.orders_cache.find({}, {"_id": 0, "primary_key": 1, "customer_no": 1, "event": 1, "address": 1,
                                             "dispo_start": 1, "dispo_end": 1, "event_start": 1, "event_end": 1}).to_list(2000)
    out = []
    for o in orders:
        if not ((cno and str(o.get("customer_no") or "").strip() == cno) or str(o.get("primary_key")) in freigegeben):
            continue
        if order_active(o):
            o["active"] = True
        elif upcoming and order_upcoming(o):
            o["active"] = False
        else:
            continue
        out.append(o)
    out.sort(key=lambda o: (not o["active"], str(o.get("dispo_start") or "")))
    return out


async def customer_device_ids(db, user: dict) -> set:
    """Alle M-Boxen, die dem Kunden ueber heute aktive Auftraege zugewiesen sind."""
    active = await customer_orders(db, user)
    if not active:
        return set()
    devices = await db.devices.find({"device_type": "mbox", "status": {"$ne": "ausser_betrieb"}}, {"_id": 0}).to_list(500)
    ids = set()
    for o in active:
        res = await compute_order_mboxes(db, o["primary_key"], devices)
        ids.update(x["id"] for x in res["devices"])
    return ids


_manifest_cache: dict = {}


async def device_manifest(db, device_id: str) -> list:
    """Standard-Dateien + fertige Auftrags-Durchsagen aller heute aktiven Auftraege, denen der Mast zugewiesen ist (30 s Cache)."""
    import time as _t
    hit = _manifest_cache.get(device_id)
    if hit and _t.monotonic() - hit[0] < 30:
        return hit[1]
    out = list(audio_manifest())
    orders = await db.orders_cache.find({}, {"_id": 0, "primary_key": 1, "dispo_start": 1, "dispo_end": 1,
                                             "event_start": 1, "event_end": 1}).to_list(2000)
    active_pks = [o["primary_key"] for o in orders if order_active(o)]
    if active_pks:
        files = await db.mbox_order_audio.find({"order_pk": {"$in": [str(p) for p in active_pks]}, "status": {"$in": ["ready", "ready_unprocessed"]}},
                                               {"_id": 0}).to_list(1000)
        if files:
            devices = await db.devices.find({"device_type": "mbox", "status": {"$ne": "ausser_betrieb"}}, {"_id": 0}).to_list(500)
            assigned_pks = set()
            for pk in {f["order_pk"] for f in files}:
                res = await compute_order_mboxes(db, int(pk), devices)
                if any(x["id"] == device_id for x in res["devices"]):
                    assigned_pks.add(pk)
            for f in files:
                if f["order_pk"] in assigned_pks:
                    out.append({"name": f["stored"], "sha256": f["sha256"], "size": f["size"], "label": f["name"], "order_pk": f["order_pk"]})
    _manifest_cache[device_id] = (_t.monotonic(), out)
    return out


def invalidate_manifest_cache():
    _manifest_cache.clear()
