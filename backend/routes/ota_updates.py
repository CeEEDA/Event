"""
OTA Auto-Update System fuer alle Pi-Geraete
=============================================
Einfacher Flow:
1. Code-Aenderung → GitHub Push → Deploy (Backend Neustart)
2. Pi meldet sich → vergleicht Hash → laed neue Version → Neustart

Unterstuetzte Geraetetypen:
- kirmeskiste  → kirmeskiste_sync.py
- messkoffer   → messkoffer_sync.py
- lkw          → lkw_sync.py
- stromerzeuger → stromerzeuger_sync.py
- dse          → dse_sync.py

Die Scripts liegen in /app/backend/static/ und werden direkt aus dem Repo ausgeliefert.
"""

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

logger = logging.getLogger("ota_updates")
router = APIRouter(prefix="/api/system/ota", tags=["OTA Updates"])

# Script-Dateien pro Geraetetyp (liegen im Repo unter /app/backend/static/).
# Nur Eintraege fuer Skripte aufnehmen, die WIRKLICH existieren UND auf der
# Client-Seite einen OTA-Auto-Update-Mechanismus implementiert haben.
DEVICE_SCRIPTS = {
    "kirmeskiste": "kirmeskiste_sync.py",      # OTA-faehig (eigener Mechanismus)
    "messkoffer": "messkoffer_logger.py",      # OTA-faehig ueber anonymen Endpoint
    "dse": "dse_usb_sync.py",                  # OTA-faehig ueber anonymen Endpoint (ab v2)
    "tankwagen": "tankbeleg_pi.py",            # OTA-faehig ueber anonymen Endpoint
}

STATIC_DIR = Path("/app/backend/static")


def _get_db():
    from server import db
    return db


def _get_script_hash(device_type: str) -> tuple[str, int]:
    """Hash + Groesse der aktuellen Script-Datei im Repo."""
    filename = DEVICE_SCRIPTS.get(device_type)
    if not filename:
        return "", 0
    path = STATIC_DIR / filename
    if not path.exists():
        return "", 0
    content = path.read_bytes()
    return hashlib.sha256(content).hexdigest(), len(content)


async def _auth_admin(request: Request):
    from server import db
    import jwt, os
    token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.query_params.get("token", "")
    if not token:
        raise HTTPException(401, "Kein Token")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user or user.get("role") not in ("admin", "superadmin"):
            raise HTTPException(403, "Nur Admins")
        return user
    except Exception:
        raise HTTPException(401, "Ungültiger Token")


async def _auth_device(request: Request):
    db = _get_db()
    api_key = request.headers.get("X-Device-Key", "") or request.query_params.get("api_key", "")
    device_id = request.headers.get("X-Device-Id", "") or request.query_params.get("device_id", "")
    if not api_key or not device_id:
        raise HTTPException(401, "Device-Key oder Device-ID fehlt")
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(404, "Gerät nicht gefunden")
    if device.get("api_key") != api_key:
        raise HTTPException(403, "Ungültiger Device-Key")
    return device


@router.get("/check")
async def check_update(request: Request, device=Depends(_auth_device)):
    """Pi prueft ob ein Update verfuegbar ist. Vergleicht lokalen Hash mit Repo-Datei."""
    db = _get_db()
    current_hash = request.query_params.get("hash", "")
    current_version = request.query_params.get("version", "")
    device_type = device.get("device_type", "kirmeskiste")

    repo_hash, file_size = _get_script_hash(device_type)
    if not repo_hash:
        return {"update_available": False, "message": f"Kein Script fuer {device_type}"}

    needs_update = current_hash != repo_hash

    # Check-in loggen
    await db.ota_checkins.update_one(
        {"device_id": device["id"]},
        {"$set": {
            "device_id": device["id"],
            "device_name": device.get("name", ""),
            "serial": device.get("serial_number", ""),
            "device_type": device_type,
            "current_version": current_version,
            "current_hash": current_hash,
            "repo_hash": repo_hash,
            "needs_update": needs_update,
            "file_size": file_size,
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    return {
        "update_available": needs_update,
        "file_hash": repo_hash,
        "file_size": file_size,
        "download_url": "/api/system/ota/download",
    }


@router.get("/download")
async def download_update(request: Request, device=Depends(_auth_device)):
    """Pi laed die aktuelle Script-Datei herunter."""
    db = _get_db()
    device_type = device.get("device_type", "kirmeskiste")
    filename = DEVICE_SCRIPTS.get(device_type)
    if not filename:
        raise HTTPException(404, f"Kein Script fuer {device_type}")

    path = STATIC_DIR / filename
    if not path.exists():
        raise HTTPException(404, f"Script {filename} nicht gefunden")

    content = path.read_bytes()
    file_hash = hashlib.sha256(content).hexdigest()

    # Download loggen
    await db.ota_checkins.update_one(
        {"device_id": device["id"]},
        {"$set": {
            "last_download": datetime.now(timezone.utc).isoformat(),
            "needs_update": False,
        }},
    )

    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Hash": file_hash,
        },
    )


@router.get("/devices")
async def list_device_status(admin=Depends(_auth_admin)):
    """Admin sieht alle Geraete mit Update-Status."""
    db = _get_db()

    # Aktuelle Hashes fuer alle Typen berechnen
    repo_hashes = {}
    for dt in DEVICE_SCRIPTS:
        h, s = _get_script_hash(dt)
        if h:
            repo_hashes[dt] = h

    devices = []
    async for d in db.ota_checkins.find({}, {"_id": 0}).sort("last_seen", -1):
        # Aktuellen Status berechnen (falls Repo sich seit letztem Check-in geaendert hat)
        dt = d.get("device_type", "kirmeskiste")
        if dt in repo_hashes:
            d["needs_update"] = d.get("current_hash", "") != repo_hashes[dt]
        devices.append(d)

    # Stats pro Typ
    type_stats = {}
    for d in devices:
        dt = d.get("device_type", "?")
        if dt not in type_stats:
            type_stats[dt] = {"total": 0, "needs_update": 0, "up_to_date": 0}
        type_stats[dt]["total"] += 1
        if d.get("needs_update"):
            type_stats[dt]["needs_update"] += 1
        else:
            type_stats[dt]["up_to_date"] += 1

    return {"devices": devices, "type_stats": type_stats, "script_types": list(DEVICE_SCRIPTS.keys())}


# ====== Anonyme Pi-OTA (generisch fuer alle Geraetetypen) ======
# Skripte sind ohnehin als Download oeffentlich verfuegbar, daher kein Auth.
# Pi authentifiziert sich nur ueber persistente, eindeutige pi_id (UUID).

@router.get("/pi/{device_type}/check")
async def pi_check_update(device_type: str, request: Request):
    """Pi prueft ob ein Update verfuegbar ist.

    Pi sendet:
      - pi_id (Pflicht): persistente UUID die der Pi lokal speichert
      - hostname (optional): zur besseren Identifikation in der Admin-UI
      - hash (Pflicht): sha256 des aktuell laufenden Skripts
      - version (optional): semver oder Git-SHA

    Backend liefert zurueck:
      - update_available: bool (true wenn Hash unterschiedlich ODER force_update)
      - file_hash, file_size, download_url
    """
    if device_type not in DEVICE_SCRIPTS:
        raise HTTPException(404, f"Geraetetyp '{device_type}' nicht unterstuetzt")
    db = _get_db()
    pi_id = request.query_params.get("pi_id", "")
    pi_hostname = request.query_params.get("hostname", "")
    current_hash = request.query_params.get("hash", "")
    current_version = request.query_params.get("version", "")
    if not pi_id:
        raise HTTPException(400, "pi_id Parameter fehlt")

    repo_hash, file_size = _get_script_hash(device_type)
    if not repo_hash:
        raise HTTPException(404, f"Skript fuer '{device_type}' nicht gefunden")

    # Force-Update-Flag pruefen (vom Admin gesetzt)
    existing = await db.ota_checkins.find_one({"device_id": pi_id}, {"_id": 0, "force_update": 1})
    force_update = bool(existing and existing.get("force_update"))
    needs_update = (current_hash != repo_hash) or force_update

    device_label = pi_hostname or f"{device_type.capitalize()} {pi_id[:8]}"
    await db.ota_checkins.update_one(
        {"device_id": pi_id},
        {"$set": {
            "device_id": pi_id,
            "device_name": device_label,
            "serial": pi_hostname or pi_id,
            "device_type": device_type,
            "current_version": current_version,
            "current_hash": current_hash,
            "repo_hash": repo_hash,
            "needs_update": needs_update,
            "file_size": file_size,
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    return {
        "update_available": needs_update,
        "force_update": force_update,
        "file_hash": repo_hash,
        "file_size": file_size,
        "download_url": f"/api/system/ota/pi/{device_type}/download",
    }


@router.get("/pi/{device_type}/download")
async def pi_download_update(device_type: str, request: Request):
    """Pi laed das aktuelle Skript herunter."""
    if device_type not in DEVICE_SCRIPTS:
        raise HTTPException(404, f"Geraetetyp '{device_type}' nicht unterstuetzt")
    db = _get_db()
    pi_id = request.query_params.get("pi_id", "")

    filename = DEVICE_SCRIPTS[device_type]
    path = STATIC_DIR / filename
    if not path.exists():
        raise HTTPException(404, f"{filename} nicht gefunden")
    content = path.read_bytes()
    file_hash = hashlib.sha256(content).hexdigest()

    if pi_id:
        await db.ota_checkins.update_one(
            {"device_id": pi_id},
            {"$set": {
                "last_download": datetime.now(timezone.utc).isoformat(),
                "needs_update": False,
                "force_update": False,  # Force-Flag nach erfolgreichem Download zuruecksetzen
            }},
        )

    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Hash": file_hash,
        },
    )


# ====== Backwards-Compat: alte Tankwagen-Endpoints (delegiert auf generische) ======

@router.get("/tankwagen/check")
async def tankwagen_check_update(request: Request):
    return await pi_check_update("tankwagen", request)


@router.get("/tankwagen/download")
async def tankwagen_download_update(request: Request):
    return await pi_download_update("tankwagen", request)


# ====== Admin-Aktionen: Force-Update ausloesen ======

@router.post("/devices/{device_id}/force-update")
async def force_update_device(device_id: str, admin=Depends(_auth_admin)):
    """Admin erzwingt ein Update fuer ein einzelnes Geraet beim naechsten Check-in.
    Das Geraet sieht beim naechsten OTA-Polling 'update_available=true' und laed
    das Skript neu, auch wenn der Hash identisch waere.
    """
    db = _get_db()
    result = await db.ota_checkins.update_one(
        {"device_id": device_id},
        {"$set": {
            "force_update": True,
            "force_update_at": datetime.now(timezone.utc).isoformat(),
            "force_update_by": admin.get("name") or admin.get("email", ""),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(404, f"Geraet '{device_id}' nicht gefunden")
    return {"status": "force-update gesetzt", "device_id": device_id}


@router.post("/devices/force-update-all")
async def force_update_all_devices(admin=Depends(_auth_admin), request: Request = None):
    """Admin erzwingt Update fuer ALLE Geraete (oder nur eines Typs).
    Optional Body/Query-Param 'device_type' filtert auf einen Typ.
    """
    db = _get_db()
    device_type = ""
    if request:
        try:
            body = await request.json()
            device_type = body.get("device_type", "") if isinstance(body, dict) else ""
        except Exception:
            pass
        if not device_type:
            device_type = request.query_params.get("device_type", "")

    query = {}
    if device_type:
        if device_type not in DEVICE_SCRIPTS:
            raise HTTPException(400, f"Unbekannter Geraetetyp '{device_type}'")
        query["device_type"] = device_type

    result = await db.ota_checkins.update_many(
        query,
        {"$set": {
            "force_update": True,
            "force_update_at": datetime.now(timezone.utc).isoformat(),
            "force_update_by": admin.get("name") or admin.get("email", ""),
        }},
    )
    return {"status": "force-update gesetzt", "matched": result.matched_count, "device_type": device_type or "all"}


@router.post("/devices/{device_id}/cancel-force-update")
async def cancel_force_update(device_id: str, admin=Depends(_auth_admin)):
    """Admin bricht einen pending Force-Update ab (z.B. falls fehlerhaft gesetzt)."""
    db = _get_db()
    result = await db.ota_checkins.update_one(
        {"device_id": device_id},
        {"$set": {"force_update": False}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, f"Geraet '{device_id}' nicht gefunden")
    return {"status": "force-update abgebrochen", "device_id": device_id}
