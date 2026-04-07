"""
Kirmeskiste OTA (Over-the-Air) Update System
=============================================
Backend endpoints for managing Kirmeskiste Raspberry Pi updates.
- Version check endpoint (called by Pis on every sync cycle)
- Script download endpoint
- Admin upload endpoint for new versions
"""

import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import Response

logger = logging.getLogger("ota_updates")
router = APIRouter(prefix="/api/system/ota", tags=["OTA Updates"])


def _get_db():
    from server import db
    return db


async def _auth_admin(request: Request):
    """Require admin auth for upload endpoints."""
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
    except jwt.PyJWTError:
        raise HTTPException(401, "Ungültiger Token")


async def _auth_device(request: Request):
    """Authenticate device by api_key (device_key from kirmeskiste.conf)."""
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
    """Pi calls this to check if an update is available."""
    db = _get_db()
    current_hash = request.query_params.get("hash", "")
    current_version = request.query_params.get("version", "")

    # Get latest published version
    latest = await db.ota_versions.find_one(
        {"target": "kirmeskiste", "published": True},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not latest:
        return {"update_available": False, "message": "Keine Version veröffentlicht"}

    # Compare hashes
    needs_update = current_hash != latest.get("file_hash", "")

    # Log the check-in
    await db.ota_checkins.update_one(
        {"device_id": device["id"]},
        {"$set": {
            "device_id": device["id"],
            "device_name": device.get("name", ""),
            "serial": device.get("serial_number", ""),
            "current_version": current_version,
            "current_hash": current_hash,
            "needs_update": needs_update,
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    return {
        "update_available": needs_update,
        "version": latest.get("version", ""),
        "file_hash": latest.get("file_hash", ""),
        "changelog": latest.get("changelog", ""),
        "download_url": "/api/system/ota/download",
    }


@router.get("/download")
async def download_update(request: Request, device=Depends(_auth_device)):
    """Pi downloads the latest script."""
    db = _get_db()
    latest = await db.ota_versions.find_one(
        {"target": "kirmeskiste", "published": True},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not latest or "file_content" not in latest:
        raise HTTPException(404, "Kein Update verfügbar")

    # Log the download
    await db.ota_checkins.update_one(
        {"device_id": device["id"]},
        {"$set": {"last_download": datetime.now(timezone.utc).isoformat()}},
    )

    return Response(
        content=latest["file_content"].encode("utf-8") if isinstance(latest["file_content"], str) else latest["file_content"],
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": "attachment; filename=kirmeskiste_sync.py",
            "X-Version": latest.get("version", ""),
            "X-Hash": latest.get("file_hash", ""),
        },
    )


@router.post("/upload")
async def upload_version(
    version: str,
    changelog: str = "",
    publish: bool = True,
    file: UploadFile = File(...),
    admin=Depends(_auth_admin),
):
    """Admin uploads a new kirmeskiste_sync.py version."""
    db = _get_db()
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    # Check for duplicate
    existing = await db.ota_versions.find_one({"file_hash": file_hash, "target": "kirmeskiste"})
    if existing:
        raise HTTPException(409, "Diese Version existiert bereits (gleicher Hash)")

    await db.ota_versions.insert_one({
        "target": "kirmeskiste",
        "version": version,
        "changelog": changelog,
        "file_hash": file_hash,
        "file_content": content.decode("utf-8"),
        "file_size": len(content),
        "published": publish,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "uploaded_by": admin.get("email", ""),
    })

    # Also update the static file for new deployments
    try:
        import shutil
        from pathlib import Path
        static_path = Path("/app/backend/static/kirmeskiste_sync.py")
        static_path.write_bytes(content)
    except Exception:
        pass

    return {
        "success": True,
        "version": version,
        "file_hash": file_hash,
        "file_size": len(content),
        "published": publish,
    }


@router.get("/versions")
async def list_versions(admin=Depends(_auth_admin)):
    """Admin lists all uploaded versions."""
    db = _get_db()
    versions = []
    async for v in db.ota_versions.find(
        {"target": "kirmeskiste"},
        {"_id": 0, "file_content": 0},
    ).sort("created_at", -1).limit(20):
        versions.append(v)
    return {"versions": versions}


@router.get("/devices")
async def list_device_status(admin=Depends(_auth_admin)):
    """Admin sees which Pis checked in, their version, and update status."""
    db = _get_db()
    devices = []
    async for d in db.ota_checkins.find({}, {"_id": 0}).sort("last_seen", -1):
        devices.append(d)
    return {"devices": devices}


@router.post("/publish/{version}")
async def toggle_publish(version: str, admin=Depends(_auth_admin)):
    """Toggle publish status of a version."""
    db = _get_db()
    doc = await db.ota_versions.find_one({"target": "kirmeskiste", "version": version})
    if not doc:
        raise HTTPException(404, "Version nicht gefunden")
    new_state = not doc.get("published", False)
    await db.ota_versions.update_one(
        {"target": "kirmeskiste", "version": version},
        {"$set": {"published": new_state}},
    )
    return {"version": version, "published": new_state}
