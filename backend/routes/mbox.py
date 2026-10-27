"""M-Box Lichtmast-Fernbedienung: Berechtigungs-Gateway + Prozess-Manager.

Pro Geraet (device_type="mbox") laeuft ein eigener, UNVERAENDERTER Node-Dienst
(mbox_service/server.js, OPC UA -> SPS) auf 127.0.0.1:<mbox_port>. Der Browser
spricht nie direkt mit dem Node-Dienst, sondern nur mit diesem Gateway:
JWT-Login, Stufen lesen/bedienen/admin, Rate-Limit, Audit-Log.
"""
import asyncio
import logging
import os
import re
import sys
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from routes import mbox_pi

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mbox", tags=["mbox"])
security = HTTPBearer()

db = None
decode_jwt_token = None

SERVICE_DIR = Path(__file__).resolve().parent.parent / "mbox_service"
PORT_BASE = 8101
# Nur-Admin-Befehle (Empfehlung der SPS-Firma, Abschnitt 5)
ADMIN_BEFEHLE = {"Kundenzaehler_Reset", "Wartung_Reset", "Probelauf_Start"}
RATE_LIMIT_PER_MIN = 30
_rate: dict = defaultdict(deque)


def init_mbox_routes(_db, _decode_jwt_token):
    global db, decode_jwt_token
    db = _db
    decode_jwt_token = _decode_jwt_token


# ===================== Berechtigung =====================

def mbox_level(user: dict) -> str:
    """'admin' | 'bedienen' | 'lesen' | 'kunde' | 'none'"""
    if not user:
        return "none"
    if user.get("role") == "admin":
        return "admin"
    if user.get("role") == "kunde":
        return "kunde" if str(user.get("customer_no") or "").strip() else "none"
    if user.get("role") != "mitarbeiter":
        return "none"
    modules = (user.get("apps") or {}).get("modules") or {}
    if modules.get("mbox_bedienen"):
        return "bedienen"
    if modules.get("mbox_lesen"):
        return "lesen"
    return "none"


async def get_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_jwt_token(credentials.credentials)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    return user


def _require(user: dict, needed: str):
    rank = {"none": 0, "kunde": 0, "lesen": 1, "bedienen": 2, "admin": 3}
    if rank[mbox_level(user)] < rank[needed]:
        msg = {"lesen": "Kein Zugriff auf M-Box", "bedienen": "Keine Bedienberechtigung",
               "admin": "Nur Admin"}[needed]
        raise HTTPException(status_code=403, detail=msg)


async def _allow(user: dict, needed: str, device_id: str, kunde_ok: bool = False):
    """Wie _require, erlaubt aber Kunden den Zugriff auf ihre zugewiesenen Masten
    (Lesen immer, Schalten nur wenn kunde_ok = Licht/Audio)."""
    if mbox_level(user) == "kunde":
        if needed == "admin" or (needed == "bedienen" and not kunde_ok):
            raise HTTPException(status_code=403, detail="Fuer Kunden nicht freigegeben")
        if device_id not in await mbox_pi.customer_device_ids(db, user):
            raise HTTPException(status_code=403, detail="Dieser Lichtmast ist Ihnen aktuell nicht zugewiesen")
        return
    _require(user, needed)


def _rate_check(user_id: str, device_id: str):
    key = f"{user_id}:{device_id}"
    now = time.monotonic()
    q = _rate[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail=f"Zu viele Befehle (max. {RATE_LIMIT_PER_MIN}/min)")
    q.append(now)


# ===================== Prozess-Manager =====================

class _Proc:
    def __init__(self):
        self.process: Optional[asyncio.subprocess.Process] = None
        self.config_sig = None
        self.started_at = None
        self.restarts = 0
        self.last_start_try = 0.0
        self.log_path = None


_procs: dict[str, _Proc] = {}
_lock = asyncio.Lock()


def _log_dir() -> Path:
    d = Path(os.environ.get("MBOX_LOG_DIR") or (SERVICE_DIR / "logs"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _config_sig(device: dict) -> tuple:
    return (device.get("mbox_endpoint"), device.get("mbox_security_mode"), device.get("mbox_security_policy"),
            device.get("mbox_user"), device.get("mbox_password"), device.get("mbox_port"))


def _env_for(device: dict) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OPCUA_") and k not in ("WEB_HOST", "WEB_PORT")}
    env.update({
        "OPCUA_ENDPOINT": device.get("mbox_endpoint") or "opc.tcp://192.168.0.100:4840",
        "OPCUA_SECURITY_MODE": device.get("mbox_security_mode") or "None",
        "OPCUA_SECURITY_POLICY": device.get("mbox_security_policy") or "None",
        "OPCUA_BENUTZER": device.get("mbox_user") or "",
        "OPCUA_PASSWORT": device.get("mbox_password") or "",
        "WEB_HOST": "127.0.0.1",
        "WEB_PORT": str(device.get("mbox_port")),
        "NODE_ENV": "production",
    })
    return env


def _proc_alive(p: _Proc) -> bool:
    return p.process is not None and p.process.returncode is None


async def _spawn(device: dict) -> _Proc:
    p = _procs.setdefault(device["id"], _Proc())
    p.last_start_try = time.monotonic()
    log_path = _log_dir() / f"mbox_{re.sub(r'[^A-Za-z0-9_-]', '_', device.get('serial_number') or device['id'])}.log"
    p.log_path = str(log_path)
    node_bin = os.environ.get("MBOX_NODE_BIN") or "node"
    log_file = open(log_path, "ab")
    log_file.write(f"\n===== Start {datetime.now(timezone.utc).isoformat()} port={device.get('mbox_port')} endpoint={device.get('mbox_endpoint')} =====\n".encode())
    log_file.flush()
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    p.process = await asyncio.create_subprocess_exec(
        node_bin, "server.js", cwd=str(SERVICE_DIR), env=_env_for(device),
        stdout=log_file, stderr=asyncio.subprocess.STDOUT, **kwargs,
    )
    log_file.close()
    p.config_sig = _config_sig(device)
    p.started_at = datetime.now(timezone.utc).isoformat()
    logger.info(f"M-Box Dienst gestartet: {device.get('serial_number')} pid={p.process.pid} port={device.get('mbox_port')}")
    return p


async def _kill(p: _Proc):
    if _proc_alive(p):
        try:
            p.process.terminate()
            await asyncio.wait_for(p.process.wait(), timeout=5)
        except Exception:
            try:
                p.process.kill()
            except Exception:
                pass
    p.process = None


async def ensure_running(device: dict) -> _Proc:
    """Startet den Node-Dienst fuer das Geraet, falls nicht (mehr) aktiv oder Konfig geaendert."""
    async with _lock:
        p = _procs.get(device["id"])
        if p and _proc_alive(p) and p.config_sig == _config_sig(device):
            return p
        crashed = bool(p and p.started_at and not _proc_alive(p))
        if p and _proc_alive(p):
            await _kill(p)  # Konfig geaendert -> sauber neu starten
        if crashed:
            # Prozess ist von selbst gestorben -> Neustart, aber hoechstens alle 5 s
            if time.monotonic() - p.last_start_try < 5:
                raise HTTPException(status_code=503, detail="M-Box Dienst startet gerade neu, bitte kurz warten")
            p.restarts += 1
        return await _spawn(device)


async def stop_device(device_id: str):
    async with _lock:
        p = _procs.pop(device_id, None)
        if p:
            await _kill(p)


async def sync_device(device: Optional[dict]):
    """Hook aus devices.py nach Create/Update/Delete."""
    try:
        if not device or device.get("device_type") != "mbox" or device.get("status") == "ausser_betrieb":
            if device:
                await stop_device(device["id"])
            return
        await ensure_running(device)
    except Exception as e:
        logger.warning(f"M-Box sync fehlgeschlagen: {e}")


async def start_all():
    if not (SERVICE_DIR / "node_modules").exists():
        logger.warning(f"M-Box: node_modules fehlt in {SERVICE_DIR} - bitte 'npm install' ausfuehren")
    devices = await db.devices.find({"device_type": "mbox", "status": {"$ne": "ausser_betrieb"}}, {"_id": 0}).to_list(200)
    for d in devices:
        await sync_device(d)
    logger.info(f"M-Box: {len(devices)} Dienst(e) gestartet")


async def stop_all():
    for did in list(_procs.keys()):
        await stop_device(did)


async def next_free_port() -> int:
    used = {d.get("mbox_port") for d in await db.devices.find({"device_type": "mbox"}, {"_id": 0, "mbox_port": 1}).to_list(500)}
    port = PORT_BASE
    while port in used:
        port += 1
    return port


def runtime_status(device: dict) -> dict:
    p = _procs.get(device["id"])
    return {
        "running": bool(p and _proc_alive(p)),
        "pid": p.process.pid if p and _proc_alive(p) else None,
        "started_at": p.started_at if p else None,
        "restarts": p.restarts if p else 0,
        "port": device.get("mbox_port"),
        "exit_code": (p.process.returncode if p and p.process else None),
    }


# ===================== Gateway-Helfer =====================

async def _device(device_id: str) -> dict:
    d = await db.devices.find_one({"id": device_id, "device_type": "mbox"}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="M-Box Geraet nicht gefunden")
    return d


async def _forward(device: dict, method: str, path: str, json=None, params=None, timeout=25.0):
    await ensure_running(device)
    url = f"http://127.0.0.1:{device['mbox_port']}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.request(method, url, json=json, params=params)
        return r.json()
    except httpx.ConnectError:
        return {"ok": False, "fehler": "M-Box Dienst (noch) nicht erreichbar - startet gerade oder ist abgestuerzt"}
    except httpx.TimeoutException:
        return {"ok": False, "fehler": "keine Antwort vom M-Box Dienst (25 s) - beim ersten Verbinden sucht er noch die Variablen"}
    except ValueError:
        return {"ok": False, "fehler": "ungueltige Antwort vom M-Box Dienst"}


async def _audit(device: dict, user: dict, endpoint: str, params, result: dict):
    try:
        await db.mbox_audit.insert_one({
            "id": str(uuid.uuid4()),
            "device_id": device["id"],
            "device_name": device.get("user_field") or device.get("serial_number"),
            "user_id": user["id"],
            "user_name": user.get("name", ""),
            "endpoint": endpoint,
            "params": params,
            "ok": bool(result.get("ok")),
            "fehler": result.get("fehler"),
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error(f"M-Box Audit-Log fehlgeschlagen: {e}")


def _public(device: dict) -> dict:
    d = {k: v for k, v in device.items() if k not in ("mbox_password", "pi_password", "mqtt_password", "mbox_pi_key_hash")}
    d["pi"] = mbox_pi.pi_state(device)
    d["position"] = mbox_pi.device_position(device)
    return d


async def _write(device_id: str, user: dict, endpoint: str, path: str, json=None, params=None, needed="bedienen", kunde_ok=False):
    await _allow(user, needed, device_id, kunde_ok=kunde_ok)
    device = await _device(device_id)
    _rate_check(user["id"], device_id)
    result = await _forward(device, "POST", path, json=json, params=params)
    await _audit(device, user, endpoint, {**(json or {}), **(params or {})} or None, result)
    return result


# ===================== Endpoints =====================

@router.get("/devices")
async def list_mbox_devices(user: dict = Depends(get_user)):
    level = mbox_level(user)
    if level == "kunde":
        ids = await mbox_pi.customer_device_ids(db, user)
        devices = await db.devices.find({"device_type": "mbox", "id": {"$in": list(ids)}}, {"_id": 0}).to_list(200)
    else:
        _require(user, "lesen")
        devices = await db.devices.find({"device_type": "mbox"}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {
        "level": level,
        "devices": [{**_public(d), "runtime": runtime_status(d)} for d in devices],
    }


@router.get("/{device_id}/status")
async def mbox_status(device_id: str, user: dict = Depends(get_user)):
    await _allow(user, "lesen", device_id)
    device = await _device(device_id)
    return {"level": mbox_level(user), "device": _public(device), "runtime": runtime_status(device),
            "service_installed": (SERVICE_DIR / "node_modules").exists()}


@router.post("/{device_id}/lesen")
async def mbox_lesen(device_id: str, body: dict, user: dict = Depends(get_user)):
    await _allow(user, "lesen", device_id)
    device = await _device(device_id)
    namen = [n for n in (body.get("namen") or []) if isinstance(n, str) and re.match(r"^DB_\w+", n)][:1500]
    return await _forward(device, "POST", "/api/lesen", json={"namen": namen})


@router.post("/{device_id}/befehl/{name}")
async def mbox_befehl(device_id: str, name: str, request: Request, user: dict = Depends(get_user)):
    if not re.match(r"^[A-Za-z0-9_]+$", name):
        raise HTTPException(status_code=400, detail="Ungueltiger Befehlsname")
    params = {"index": request.query_params["index"]} if "index" in request.query_params else None
    needed = "admin" if name in ADMIN_BEFEHLE else "bedienen"
    return await _write(device_id, user, f"befehl/{name}", f"/api/befehl/{name}", params=params, needed=needed,
                        kunde_ok=name in mbox_pi.KUNDE_BEFEHLE)


@router.post("/{device_id}/einstellung")
async def mbox_einstellung(device_id: str, body: dict, user: dict = Depends(get_user)):
    return await _write(device_id, user, "einstellung", "/api/einstellung", json=body)


@router.post("/{device_id}/uhr/woche")
async def mbox_uhr_woche(device_id: str, body: dict, user: dict = Depends(get_user)):
    return await _write(device_id, user, "uhr/woche", "/api/uhr/woche", json=body)


@router.post("/{device_id}/uhr/datum")
async def mbox_uhr_datum(device_id: str, body: dict, user: dict = Depends(get_user)):
    return await _write(device_id, user, "uhr/datum", "/api/uhr/datum", json=body)


@router.post("/{device_id}/uhr/datum_loeschen")
async def mbox_uhr_datum_loeschen(device_id: str, body: dict, user: dict = Depends(get_user)):
    return await _write(device_id, user, "uhr/datum_loeschen", "/api/uhr/datum_loeschen", json=body)


# ---- Nur Admin: Test/Diagnose ----

@router.post("/{device_id}/gps")
async def mbox_gps(device_id: str, request: Request, user: dict = Depends(get_user)):
    params = {k: request.query_params[k] for k in ("breite", "laenge", "fix") if k in request.query_params}
    return await _write(device_id, user, "gps", "/api/gps", params=params, needed="admin")


@router.get("/{device_id}/knoten")
async def mbox_knoten(device_id: str, request: Request, user: dict = Depends(get_user)):
    _require(user, "admin")
    return await _forward(await _device(device_id), "GET", "/api/knoten", params=dict(request.query_params), timeout=130.0)


@router.get("/{device_id}/browse")
async def mbox_browse(device_id: str, request: Request, user: dict = Depends(get_user)):
    _require(user, "admin")
    return await _forward(await _device(device_id), "GET", "/api/browse", params=dict(request.query_params))


@router.get("/{device_id}/suche")
async def mbox_suche(device_id: str, request: Request, user: dict = Depends(get_user)):
    _require(user, "admin")
    return await _forward(await _device(device_id), "GET", "/api/suche", params=dict(request.query_params), timeout=130.0)


@router.post("/{device_id}/neu_verbinden")
async def mbox_neu_verbinden(device_id: str, user: dict = Depends(get_user)):
    _require(user, "admin")
    device = await _device(device_id)
    result = await _forward(device, "POST", "/api/neu_verbinden", timeout=130.0)
    await _audit(device, user, "neu_verbinden", None, result)
    return result


@router.post("/{device_id}/restart")
async def mbox_restart(device_id: str, user: dict = Depends(get_user)):
    """Node-Dienst des Geraets neu starten (z.B. nach npm install oder haengender Verbindung)."""
    _require(user, "admin")
    device = await _device(device_id)
    await stop_device(device_id)
    _procs.pop(device_id, None)
    await ensure_running(device)
    await _audit(device, user, "restart", None, {"ok": True})
    return {"ok": True, "runtime": runtime_status(device)}


@router.get("/{device_id}/log")
async def mbox_log(device_id: str, lines: int = 200, user: dict = Depends(get_user)):
    _require(user, "admin")
    device = await _device(device_id)
    p = _procs.get(device_id)
    if not p or not p.log_path or not Path(p.log_path).exists():
        return {"lines": []}
    data = Path(p.log_path).read_bytes()[-200_000:].decode("utf-8", "replace").splitlines()
    return {"lines": data[-max(1, min(lines, 2000)):]}


@router.get("/{device_id}/audit")
async def mbox_audit(device_id: str, limit: int = 200, user: dict = Depends(get_user)):
    _require(user, "bedienen")
    await _device(device_id)
    rows = await db.mbox_audit.find({"device_id": device_id}, {"_id": 0}).sort("ts", -1).to_list(max(1, min(limit, 1000)))
    return rows


# ===================== Pi im Lichtmast: Setup, Sync, Audio =====================

@router.post("/{device_id}/pi-setup")
async def mbox_pi_setup(device_id: str, request: Request, body: Optional[dict] = None, user: dict = Depends(get_user)):
    """Neuen Geraeteschluessel erzeugen und Setup-Skript fuer den Pi bereitstellen (wie DSE-5510-Setup)."""
    _require(user, "admin")
    device = await _device(device_id)
    body = body or {}
    plain, h = mbox_pi.new_pi_key()
    await db.devices.update_one({"id": device_id}, {"$set": {
        "mbox_pi_key_hash": h, "mbox_pi_key_prefix": plain[:8],
        "mbox_pi_key_created_at": datetime.now(timezone.utc).isoformat(),
        "mbox_pi_audio_device": body.get("audio_device") or "", "mbox_pi_volume": int(body.get("volume") or 85),
    }})
    base = mbox_pi.api_base(request)
    script = mbox_pi.build_setup_script(device, plain, base, body.get("audio_device") or "", int(body.get("volume") or 85))
    token = mbox_pi.store_setup(script, device.get("user_field") or device.get("serial_number") or device_id)
    await _audit(device, user, "pi-setup", None, {"ok": True})
    return {"download_token": token, "download_url": f"{base}/mbox/pi-setup-download/{token}"}


@router.get("/pi-setup-download/{token}")
async def mbox_pi_setup_download(token: str):
    return mbox_pi.setup_download(token)


@router.post("/pi/{device_id}/sync")
async def mbox_pi_sync(device_id: str, body: dict):
    """Vom Pi aufgerufen (alle ~3 s): Status/GPS melden, Befehle + Audio-Manifest abholen."""
    device = await _device(device_id)
    mbox_pi.verify_pi_key(device, body.get("api_key", ""))
    now = datetime.now(timezone.utc).isoformat()
    upd = {"mbox_pi_last_seen": now, "mbox_pi_playing": body.get("playing"), "mbox_pi_files": body.get("files") or [],
           "mbox_pi_version": body.get("version"), "mbox_pi_hostname": body.get("hostname")}
    if body.get("volume") is not None:
        upd["mbox_pi_volume"] = body.get("volume")
    gps = body.get("gps") or {}
    if gps.get("fix") and gps.get("lat") is not None and gps.get("lon") is not None:
        upd["mbox_pi_gps"] = {"lat": float(gps["lat"]), "lon": float(gps["lon"]), "fix": True,
                              "mode": gps.get("mode"), "sats": gps.get("sats"), "ts": now}
        upd["latitude"], upd["longitude"] = float(gps["lat"]), float(gps["lon"])
    await db.devices.update_one({"id": device_id}, {"$set": upd})
    pending = await db.mbox_pi_commands.find({"device_id": device_id, "status": "pending"}, {"_id": 0}).sort("created_at", 1).to_list(20)
    if pending:
        await db.mbox_pi_commands.update_many({"id": {"$in": [c["id"] for c in pending]}}, {"$set": {"status": "sent", "sent_at": now}})
    return {"pending_commands": pending, "audio_manifest": mbox_pi.audio_manifest(), "server_time": now}


@router.post("/pi/{device_id}/command-result")
async def mbox_pi_command_result(device_id: str, body: dict):
    device = await _device(device_id)
    mbox_pi.verify_pi_key(device, body.get("api_key", ""))
    await db.mbox_pi_commands.update_one({"id": body.get("command_id"), "device_id": device_id}, {"$set": {
        "status": "done" if body.get("success") else "failed", "message": body.get("message"),
        "finished_at": datetime.now(timezone.utc).isoformat()}})
    return {"ok": True}


@router.get("/pi/{device_id}/audio/{name}")
async def mbox_pi_audio_download(device_id: str, name: str, api_key: str = ""):
    device = await _device(device_id)
    mbox_pi.verify_pi_key(device, api_key)
    return mbox_pi.audio_file_response(name)


async def _pi_command(device: dict, user: dict, command: str, params: dict) -> dict:
    if not device.get("mbox_pi_key_hash"):
        raise HTTPException(status_code=409, detail="Pi noch nicht eingerichtet - zuerst Pi-Setup in der Geraeteverwaltung")
    doc = {"id": str(uuid.uuid4()), "device_id": device["id"], "command": command, "params": params, "status": "pending",
           "user_id": user["id"], "user_name": user.get("name", ""), "created_at": datetime.now(timezone.utc).isoformat()}
    await db.mbox_pi_commands.insert_one(doc)
    doc.pop("_id", None)
    online = mbox_pi.pi_state(device)["online"]
    await _audit(device, user, f"audio/{command}", params or None, {"ok": online, "fehler": None if online else "Pi offline - Befehl wartet"})
    return {"ok": True, "command_id": doc["id"], "pi_online": online,
            "hinweis": None if online else "Pi ist offline - der Befehl wird ausgefuehrt, sobald er sich wieder meldet"}


@router.get("/{device_id}/audio")
async def mbox_audio_status(device_id: str, user: dict = Depends(get_user)):
    await _allow(user, "lesen", device_id)
    device = await _device(device_id)
    last = await db.mbox_pi_commands.find({"device_id": device_id}, {"_id": 0}).sort("created_at", -1).to_list(10)
    return {"pi": mbox_pi.pi_state(device), "files": mbox_pi.audio_manifest(), "commands": last}


@router.post("/{device_id}/audio/play")
async def mbox_audio_play(device_id: str, body: dict, user: dict = Depends(get_user)):
    await _allow(user, "bedienen", device_id, kunde_ok=True)
    device = await _device(device_id)
    _rate_check(user["id"], device_id)
    name = os.path.basename(str(body.get("file") or ""))
    if name not in {m["name"] for m in mbox_pi.audio_manifest()}:
        raise HTTPException(status_code=404, detail="Audiodatei nicht gefunden")
    return await _pi_command(device, user, "play", {"file": name, "loop": bool(body.get("loop"))})


@router.post("/{device_id}/audio/stop")
async def mbox_audio_stop(device_id: str, user: dict = Depends(get_user)):
    await _allow(user, "bedienen", device_id, kunde_ok=True)
    device = await _device(device_id)
    _rate_check(user["id"], device_id)
    return await _pi_command(device, user, "stop", {})


@router.post("/{device_id}/audio/volume")
async def mbox_audio_volume(device_id: str, body: dict, user: dict = Depends(get_user)):
    await _allow(user, "bedienen", device_id)
    device = await _device(device_id)
    vol = max(0, min(100, int(body.get("volume", 85))))
    await db.devices.update_one({"id": device_id}, {"$set": {"mbox_pi_volume": vol}})
    return await _pi_command(device, user, "volume", {"volume": vol})


# ===================== Auftrags-Zuweisung (Kunden) =====================

@router.get("/orders/{order_pk}")
async def mbox_order_assignment(order_pk: int, user: dict = Depends(get_user)):
    if user.get("role") not in ("admin", "mitarbeiter"):
        raise HTTPException(status_code=403, detail="Nur Mitarbeiter")
    return await mbox_pi.compute_order_mboxes(db, order_pk)


@router.put("/orders/{order_pk}/config")
async def mbox_order_config(order_pk: int, body: dict, user: dict = Depends(get_user)):
    if user.get("role") not in ("admin", "mitarbeiter"):
        raise HTTPException(status_code=403, detail="Nur Mitarbeiter")
    upd = {"order_pk": str(order_pk), "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": user.get("name")}
    if "expected_count" in body:
        upd["expected_count"] = max(0, int(body.get("expected_count") or 0))
    if "radius_km" in body:
        upd["radius_km"] = max(0.1, min(float(body.get("radius_km") or mbox_pi.DEFAULT_RADIUS_KM), mbox_pi.MAX_RADIUS_KM))
    await db.mbox_order_config.update_one({"order_pk": str(order_pk)}, {"$set": upd}, upsert=True)
    return await mbox_pi.compute_order_mboxes(db, order_pk)


@router.post("/orders/{order_pk}/override")
async def mbox_order_override(order_pk: int, body: dict, user: dict = Depends(get_user)):
    """Manuell zuweisen ('add'), ausschliessen ('remove') oder Override loeschen ('reset')."""
    if user.get("role") not in ("admin", "mitarbeiter"):
        raise HTTPException(status_code=403, detail="Nur Mitarbeiter")
    device = await _device(str(body.get("device_id") or ""))
    action = body.get("action")
    if action not in ("add", "remove", "reset"):
        raise HTTPException(status_code=400, detail="action muss add, remove oder reset sein")
    key = {"order_pk": str(order_pk), "device_id": device["id"]}
    if action == "reset":
        await db.mbox_order_overrides.delete_one(key)
    else:
        await db.mbox_order_overrides.update_one(key, {"$set": {**key, "action": action, "by": user.get("name"),
                                                                "at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    await _audit(device, user, f"order/{order_pk}/{action}", None, {"ok": True})
    return await mbox_pi.compute_order_mboxes(db, order_pk)
