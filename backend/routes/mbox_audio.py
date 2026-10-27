"""Auftrags-Durchsagen: Kunden laden Sprachdateien hoch, ffmpeg prueft Rauschen und
normalisiert auf 0 dBFS, Dateien gehen auf alle M-Boxen des Auftrags, Gruppenstart zeitgleich."""
import asyncio
import hashlib
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response
import tempfile
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from routes import mbox_pi
from routes.mbox import get_user, _audit, _rate_check

router = APIRouter(prefix="/api/mbox", tags=["mbox-audio"])
db = None
decode_jwt_token = None

# Fertige Durchsagen liegen in MongoDB (GridFS, Bucket "mbox_audio"); ffmpeg arbeitet nur mit temporaeren Dateien.
fs = None
MAX_UPLOAD = 25 * 1024 * 1024
ALLOWED_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac"}
GROUP_START_LEAD_SEC = 6  # Pi pollt alle 3 s -> alle Masten haben den Befehl vor dem Startzeitpunkt
NOISE_FLOOR_LIMIT_DB = -50.0


def init_mbox_audio_routes(_db, _decode):
    global db, decode_jwt_token, fs
    db, decode_jwt_token = _db, _decode
    fs = AsyncIOMotorGridFSBucket(_db, bucket_name="mbox_audio")


async def store_bytes(stored: str, data: bytes) -> None:
    async for old in fs.find({"filename": stored}):
        await fs.delete(old._id)
    await fs.upload_from_stream(stored, data, metadata={"content_type": "audio/mpeg"})


async def load_bytes(stored: str) -> Optional[bytes]:
    try:
        stream = await fs.open_download_stream_by_name(stored)
    except Exception:
        return None
    return await stream.read()


async def delete_stored(stored: str) -> None:
    async for old in fs.find({"filename": stored}):
        await fs.delete(old._id)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _sha_size(path: Path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest(), path.stat().st_size


def _analyze(path: Path) -> dict:
    """volumedetect + astats: Spitzenpegel, Mittelwert, Rauschteppich, Dauer."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect,astats=measure_overall=Noise_floor+Peak_level+RMS_level:measure_perchannel=none",
                        "-f", "null", "-"], capture_output=True, text=True, timeout=300)
    out = r.stderr
    def grab(pattern):
        m = re.search(pattern, out)
        if not m:
            return None
        v = m.group(1)
        return None if "inf" in v or "nan" in v else float(v)
    dur = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", out)
    return {
        "max_volume_db": grab(r"max_volume: (-?[\d.]+) dB"),
        "mean_volume_db": grab(r"mean_volume: (-?[\d.]+) dB"),
        "noise_floor_db": grab(r"Noise floor dB: (-?[\w.]+)"),
        "duration_sec": round(int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3)), 1) if dur else None,
    }


def process_audio(src: Path, dst: Path) -> dict:
    """Pass 1: Rauschen pruefen und ggf. entfernen (afftdn). Pass 2: Spitzenpegel auf 0 dBFS, MP3 192k."""
    before = _analyze(src)
    noisy = before["noise_floor_db"] is not None and before["noise_floor_db"] > NOISE_FLOOR_LIMIT_DB
    stage = src
    tmp_wav = dst.with_suffix(".denoised.wav")
    if noisy:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", str(src), "-af", "afftdn=nf=-25", str(tmp_wav)], capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or "ffmpeg afftdn Fehler")[-300:])
        stage = tmp_wav
    mid = _analyze(stage) if noisy else before
    filters = []
    gain = -(mid["max_volume_db"] or 0.0)
    if abs(gain) > 0.1:
        filters.append(f"volume={gain:.2f}dB")
    filters.append("alimiter=limit=0.999")
    cmd = ["ffmpeg", "-hide_banner", "-y", "-i", str(stage), "-af", ",".join(filters), "-codec:a", "libmp3lame", "-b:a", "192k", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    tmp_wav.unlink(missing_ok=True)
    if r.returncode != 0 or not dst.exists():
        raise RuntimeError((r.stderr or "ffmpeg Fehler")[-300:])
    after = _analyze(dst)
    return {"before": before, "after": after, "noise_reduction": noisy, "gain_db": round(gain, 2),
            "filters": (["afftdn=nf=-25"] if noisy else []) + filters}


async def _process_job(fid: str, src: Path, stored: str):
    dst = src.with_suffix(".out.mp3")
    try:
        if not ffmpeg_available():
            shutil.copyfile(src, dst)
            sha, size = _sha_size(dst)
            await store_bytes(stored, dst.read_bytes())
            await db.mbox_order_audio.update_one({"id": fid}, {"$set": {"status": "ready_unprocessed", "sha256": sha, "size": size,
                                                                        "warning": "ffmpeg fehlt auf dem Server - Datei unveraendert uebernommen"}})
        else:
            analysis = await asyncio.to_thread(process_audio, src, dst)
            sha, size = _sha_size(dst)
            await store_bytes(stored, dst.read_bytes())
            await db.mbox_order_audio.update_one({"id": fid}, {"$set": {"status": "ready", "sha256": sha, "size": size, "analysis": analysis,
                                                                        "duration_sec": analysis["after"].get("duration_sec")}})
    except Exception as e:
        await db.mbox_order_audio.update_one({"id": fid}, {"$set": {"status": "failed", "error": str(e)[:300]}})
    finally:
        for tmp in (src, dst):
            try:
                tmp.unlink()
            except Exception:
                pass
        mbox_pi.invalidate_manifest_cache()
        # betroffene Masten sofort zum Dateiabgleich anstossen
        doc = await db.mbox_order_audio.find_one({"id": fid}, {"_id": 0, "order_pk": 1})
        if doc:
            await _enqueue_order(doc["order_pk"], None, "sync_files", {})


def _is_staff(user) -> bool:
    return user.get("role") in ("admin", "mitarbeiter")


async def _order_access(user: dict, order_pk: int):
    if _is_staff(user):
        return
    if user.get("role") == "kunde" and any(str(o["primary_key"]) == str(order_pk) for o in await mbox_pi.customer_orders(db, user)):
        return
    raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Auftrag")


def _public_file(f: dict) -> dict:
    return {k: v for k, v in f.items() if k != "_id"}


async def _enqueue_order(order_pk, user: Optional[dict], command: str, params: dict) -> list:
    res = await mbox_pi.compute_order_mboxes(db, int(order_pk))
    now = datetime.now(timezone.utc).isoformat()
    docs = []
    for d in res["devices"]:
        docs.append({"id": str(uuid.uuid4()), "device_id": d["id"], "command": command, "params": params, "status": "pending",
                     "order_pk": str(order_pk), "user_id": (user or {}).get("id"), "user_name": (user or {}).get("name", "System"), "created_at": now})
    if docs:
        await db.mbox_pi_commands.insert_many(docs)
    return [{"device_id": d["device_id"], "command_id": d["id"]} for d in docs]


# ---------------- Kunden & Freigabe ----------------

@router.get("/customers")
async def list_customers(user: dict = Depends(get_user)):
    if not _is_staff(user):
        raise HTTPException(status_code=403, detail="Nur Mitarbeiter")
    rows = await db.users.find({"role": "kunde", "is_active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "email": 1, "customer_no": 1}).sort("name", 1).to_list(1000)
    return rows

@router.put("/orders/{order_pk}/customers")
async def set_order_customers(order_pk: int, body: dict, user: dict = Depends(get_user)):
    if not _is_staff(user):
        raise HTTPException(status_code=403, detail="Nur Mitarbeiter")
    ids = [str(x) for x in (body.get("user_ids") or [])][:200]
    await db.mbox_order_config.update_one({"order_pk": str(order_pk)}, {"$set": {"order_pk": str(order_pk), "customer_user_ids": ids,
                                                                                "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": user.get("name")}}, upsert=True)
    return {"ok": True, "user_ids": ids}

@router.get("/orders/{order_pk}/customers")
async def get_order_customers(order_pk: int, user: dict = Depends(get_user)):
    if not _is_staff(user):
        raise HTTPException(status_code=403, detail="Nur Mitarbeiter")
    cfg = await db.mbox_order_config.find_one({"order_pk": str(order_pk)}, {"_id": 0, "customer_user_ids": 1}) or {}
    order = await db.orders_cache.find_one({"primary_key": int(order_pk)}, {"_id": 0, "customer_no": 1})
    auto = []
    if order and order.get("customer_no") is not None:
        auto = await db.users.find({"role": "kunde", "customer_no": str(order["customer_no"]).strip()}, {"_id": 0, "id": 1, "name": 1, "email": 1}).to_list(50)
    return {"user_ids": cfg.get("customer_user_ids") or [], "auto_by_customer_no": auto}

@router.get("/my/orders")
async def my_orders(user: dict = Depends(get_user)):
    if user.get("role") != "kunde":
        raise HTTPException(status_code=403, detail="Nur Kunden")
    orders = await mbox_pi.customer_orders(db, user)
    return [{"order_pk": o["primary_key"], "event": o.get("event"), "address": o.get("address"),
             "dispo_start": o.get("dispo_start"), "dispo_end": o.get("dispo_end")} for o in orders]

# ---------------- Durchsagen ----------------

@router.get("/orders/{order_pk}/audio")
async def list_order_audio(order_pk: int, user: dict = Depends(get_user)):
    await _order_access(user, order_pk)
    files = await db.mbox_order_audio.find({"order_pk": str(order_pk)}, {"_id": 0}).sort("uploaded_at", -1).to_list(200)
    res = await mbox_pi.compute_order_mboxes(db, int(order_pk))
    cmds = await db.mbox_pi_commands.find({"order_pk": str(order_pk)}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return {"files": files, "devices": res["devices"], "ffmpeg": ffmpeg_available(), "recent_commands": cmds,
            "kunde": user.get("role") == "kunde"}

@router.post("/orders/{order_pk}/audio")
async def upload_order_audio(order_pk: int, file: UploadFile = File(...), name: str = Form(""), user: dict = Depends(get_user)):
    await _order_access(user, order_pk)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Dateityp {ext or '?'} nicht erlaubt (MP3, WAV, M4A, OGG, AAC, FLAC)")
    fid = str(uuid.uuid4())
    src = Path(tempfile.gettempdir()) / f"mbox_upload_{fid}{ext}"  # nur Zwischenablage fuer ffmpeg
    size = 0
    with open(src, "wb") as out:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD:
                out.close(); src.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Datei groesser als 25 MB")
            out.write(chunk)
    label = (name or os.path.splitext(file.filename or "Durchsage")[0]).strip()[:80] or "Durchsage"
    stored = f"order{order_pk}_{fid[:8]}.mp3"
    doc = {"id": fid, "order_pk": str(order_pk), "name": label, "original_name": file.filename, "stored": stored,
           "status": "processing", "size": size, "sha256": None, "uploaded_by": user.get("name"), "uploaded_by_id": user["id"],
           "uploaded_by_role": user.get("role"), "uploaded_at": datetime.now(timezone.utc).isoformat()}
    await db.mbox_order_audio.insert_one(doc)
    asyncio.create_task(_process_job(fid, src, stored))
    return _public_file(doc)

@router.patch("/orders/{order_pk}/audio/{fid}")
async def rename_order_audio(order_pk: int, fid: str, body: dict, user: dict = Depends(get_user)):
    await _order_access(user, order_pk)
    label = str(body.get("name") or "").strip()[:80]
    if not label:
        raise HTTPException(status_code=400, detail="Name fehlt")
    r = await db.mbox_order_audio.update_one({"id": fid, "order_pk": str(order_pk)}, {"$set": {"name": label}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    mbox_pi.invalidate_manifest_cache()
    return {"ok": True, "name": label}

@router.delete("/orders/{order_pk}/audio/{fid}")
async def delete_order_audio(order_pk: int, fid: str, user: dict = Depends(get_user)):
    await _order_access(user, order_pk)
    f = await db.mbox_order_audio.find_one({"id": fid, "order_pk": str(order_pk)}, {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    if not _is_staff(user) and f.get("uploaded_by_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Nur eigene Dateien loeschbar")
    await db.mbox_order_audio.delete_one({"id": fid})
    await delete_stored(f["stored"])
    mbox_pi.invalidate_manifest_cache()
    await _enqueue_order(order_pk, user, "sync_files", {})
    return {"ok": True}

@router.get("/orders/{order_pk}/audio/{fid}/stream")
async def stream_order_audio(order_pk: int, fid: str, token: str = Query(...)):
    payload = decode_jwt_token(token)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Ungueltig")
    await _order_access(user, order_pk)
    f = await db.mbox_order_audio.find_one({"id": fid, "order_pk": str(order_pk)}, {"_id": 0})
    data = await load_bytes(f["stored"]) if f else None
    if data is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return Response(content=data, media_type="audio/mpeg",
                    headers={"Content-Disposition": f'inline; filename="{f["name"]}.mp3"', "Accept-Ranges": "bytes"})

@router.post("/orders/{order_pk}/audio/{fid}/play")
async def play_order_audio(order_pk: int, fid: str, user: dict = Depends(get_user)):
    """Gruppenstart: alle Masten des Auftrags starten zeitgleich (start_at = jetzt + Vorlauf)."""
    await _order_access(user, order_pk)
    f = await db.mbox_order_audio.find_one({"id": fid, "order_pk": str(order_pk)}, {"_id": 0})
    if not f or f.get("status") not in ("ready", "ready_unprocessed"):
        raise HTTPException(status_code=409, detail="Datei ist noch nicht bereit")
    _rate_check(user["id"], f"order-{order_pk}")
    start_at = (datetime.now(timezone.utc) + timedelta(seconds=GROUP_START_LEAD_SEC)).isoformat()
    sent = await _enqueue_order(order_pk, user, "play", {"file": f["stored"], "loop": False, "start_at": start_at, "label": f["name"]})
    if not sent:
        raise HTTPException(status_code=409, detail="Diesem Auftrag ist aktuell kein Mast zugewiesen")
    devices = await db.devices.find({"id": {"$in": [s["device_id"] for s in sent]}}, {"_id": 0}).to_list(100)
    for d in devices:
        await _audit(d, user, "audio/play-group", {"file": f["name"], "start_at": start_at}, {"ok": mbox_pi.pi_state(d)["online"]})
    offline = [d.get("user_field") or d.get("serial_number") for d in devices if not mbox_pi.pi_state(d)["online"]]
    return {"ok": True, "start_at": start_at, "lead_sec": GROUP_START_LEAD_SEC, "devices": len(sent), "offline": offline}

@router.post("/orders/{order_pk}/audio/stop")
async def stop_order_audio(order_pk: int, user: dict = Depends(get_user)):
    await _order_access(user, order_pk)
    _rate_check(user["id"], f"order-{order_pk}")
    sent = await _enqueue_order(order_pk, user, "stop", {})
    devices = await db.devices.find({"id": {"$in": [s["device_id"] for s in sent]}}, {"_id": 0}).to_list(100)
    for d in devices:
        await _audit(d, user, "audio/stop-group", None, {"ok": True})
    return {"ok": True, "devices": len(sent)}
