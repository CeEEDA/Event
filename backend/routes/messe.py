"""Messe-Modul: M-Boxen aus dem Geraetestamm fuer einen Messeauftritt zusammenstellen.
Besucher scannen einen QR-Code am Lichtmast und koennen ohne Login die Lampen schalten
und die hinterlegte Testdurchsage abspielen."""
import asyncio
import logging
import os
import secrets
import tempfile
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.responses import Response

from routes import mbox_pi
from routes.mbox import get_user, _audit, _device, _forward, _pi_command, mbox_level
from routes import mbox_audio

router = APIRouter(prefix="/api/messe", tags=["messe"])
logger = logging.getLogger(__name__)
db = None

PUBLIC_RATE_PER_MIN = 40
PUBLIC_USER = {"id": "messe-besucher", "name": "Messe-Besucher", "role": "public"}
STAFF_ROLES = ["admin", "mitarbeiter"]
COMPANY = {"name": "Eventenergie Deutschland GmbH & Co. KG", "web": "https://www.eventenergie-deutschland.de"}
LAMP_VARS = ["DB_HMI.Status.Lampe", "DB_Parameter.Lampen_Auswahl", "DB_HMI.Status.Licht_Ein", "DB_HMI.Status.Versorgung",
             "DB_HMI.Status.Lampen_Alle_An", "DB_HMI.Status.Lampen_Alle_Aus", "DB_HMI.Status.Gen_Zustand"]
_rate: dict = defaultdict(deque)


def init_messe_routes(_db):
    global db
    db = _db


def _staff(user: dict):
    if user.get("role") not in ("admin", "mitarbeiter"):
        raise HTTPException(status_code=403, detail="Nur Mitarbeiter")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_messe(m: dict) -> dict:
    return {k: v for k, v in m.items() if k != "_id"}


async def _messe(messe_id: str) -> dict:
    m = await db.messen.find_one({"id": messe_id, "deleted_at": None}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Messe nicht gefunden")
    return m


async def _messe_by_token(token: str) -> dict:
    m = await db.messen.find_one({"public_token": token, "deleted_at": None}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Dieser Messe-Link ist nicht (mehr) gueltig")
    if not m.get("active", True):
        raise HTTPException(status_code=410, detail="Diese Messe ist aktuell nicht freigeschaltet")
    return m


async def _audio_list(messe_id: str) -> list:
    rows = await db.messe_audio.find({"messe_id": messe_id}, {"_id": 0}).sort("uploaded_at", 1).to_list(200)
    return rows


async def _devices_of(m: dict) -> list:
    ids = m.get("device_ids") or []
    if not ids:
        return []
    devs = await db.devices.find({"id": {"$in": ids}, "device_type": "mbox"}, {"_id": 0}).to_list(200)
    order = {d: i for i, d in enumerate(ids)}
    devs.sort(key=lambda d: order.get(d["id"], 999))
    return devs


def _device_brief(d: dict) -> dict:
    return {"id": d["id"], "name": d.get("user_field") or d.get("serial_number"), "serial_number": d.get("serial_number"),
            "pi": mbox_pi.pi_state(d)}


def _rate_public(request: Request, device_id: str):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    key = f"{ip}:{device_id}"
    now = time.monotonic()
    q = _rate[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= PUBLIC_RATE_PER_MIN:
        raise HTTPException(status_code=429, detail="Zu viele Befehle - bitte kurz warten")
    q.append(now)


SESSION_MINUTES = 5


async def create_session(m: dict, request: Request) -> dict:
    now = datetime.now(timezone.utc)
    doc = {"id": secrets.token_urlsafe(24), "messe_id": m["id"], "created_at": now.isoformat(),
           "expires_at": (now + timedelta(minutes=SESSION_MINUTES)).isoformat(),
           "ip": request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip(),
           "user_agent": (request.headers.get("user-agent") or "")[:200]}
    await db.messe_sessions.insert_one(dict(doc))
    return {"session_id": doc["id"], "expires_at": doc["expires_at"], "server_time": now.isoformat(), "minutes": SESSION_MINUTES}


async def _require_session(request: Request, m: dict):
    """Bedienung nur mit gueltiger Besucher-Sitzung (5 min nach dem QR-Scan)."""
    sid = request.headers.get("x-messe-session") or ""
    sess = await db.messe_sessions.find_one({"id": sid, "messe_id": m["id"]}, {"_id": 0}) if sid else None
    if not sess:
        raise HTTPException(status_code=403, detail="Keine gueltige Sitzung - bitte QR-Code am Stand scannen")
    if sess["expires_at"] < datetime.now(timezone.utc).isoformat():
        raise HTTPException(status_code=403, detail="Sitzung abgelaufen - bitte QR-Code am Stand erneut scannen")


async def _active_messe_ids_for_device(device_id: str) -> list:
    rows = await db.messen.find({"device_ids": device_id, "deleted_at": None, "active": {"$ne": False}}, {"_id": 0, "id": 1}).to_list(50)
    return [r["id"] for r in rows]


async def messe_manifest_entries(device_id: str) -> list:
    """Fertige Messe-Durchsagen fuer das Audio-Manifest eines Mastes (wird von mbox_pi.device_manifest genutzt)."""
    ids = await _active_messe_ids_for_device(device_id)
    if not ids:
        return []
    files = await db.messe_audio.find({"messe_id": {"$in": ids}, "status": {"$in": ["ready", "ready_unprocessed"]}}, {"_id": 0}).to_list(500)
    return [{"name": f["stored"], "sha256": f["sha256"], "size": f["size"], "label": f["name"], "messe_id": f["messe_id"]} for f in files]


async def _notify_sync(messe_id: str):
    m = await db.messen.find_one({"id": messe_id}, {"_id": 0, "device_ids": 1})
    if not m:
        return
    mbox_pi.invalidate_manifest_cache()
    now = _now()
    docs = [{"id": str(uuid.uuid4()), "device_id": did, "command": "sync_files", "params": {}, "status": "pending",
             "messe_id": messe_id, "user_id": None, "user_name": "Messe", "created_at": now} for did in (m.get("device_ids") or [])]
    if docs:
        await db.mbox_pi_commands.insert_many(docs)


# ===================== Verwaltung (Mitarbeiter) =====================

@router.get("")
async def list_messen(user: dict = Depends(get_user)):
    _staff(user)
    rows = await db.messen.find({"deleted_at": None}, {"_id": 0}).sort("created_at", -1).to_list(200)
    out = []
    for m in rows:
        devs = await _devices_of(m)
        audio = await _audio_list(m["id"])
        out.append({**m, "devices": [_device_brief(d) for d in devs], "audio_count": len(audio)})
    return out


@router.post("")
async def create_messe(body: dict, user: dict = Depends(get_user)):
    _staff(user)
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name fehlt")
    m = {"id": str(uuid.uuid4()), "name": name[:120], "location": (body.get("location") or "").strip()[:160],
         "start_date": body.get("start_date") or None, "end_date": body.get("end_date") or None,
         "note": (body.get("note") or "").strip()[:500], "device_ids": [], "active": True,
         "public_token": secrets.token_urlsafe(18), "created_by": user.get("name"), "created_at": _now(), "updated_at": _now(),
         "deleted_at": None}
    await db.messen.insert_one(dict(m))
    return {**m, "devices": [], "audio_count": 0}


# ===================== Messe-Team: Mitarbeiter, Hub-QR, Kontaktkarte =====================

def _staff_brief(u: dict) -> dict:
    return {"id": u["id"], "name": u.get("name"), "role": u.get("role"), "email": u.get("email")}


@router.get("/staff-options")
async def staff_options(user: dict = Depends(get_user)):
    """Aktive Mitarbeiter/Admins zur Auswahl als Messe-Team."""
    _staff(user)
    rows = await db.users.find({"role": {"$in": STAFF_ROLES}, "is_active": True}, {"_id": 0, "id": 1, "name": 1, "role": 1, "email": 1}).to_list(300)
    return sorted((_staff_brief(u) for u in rows), key=lambda x: (x["name"] or "").lower())


@router.get("/my-active")
async def my_active_messen(user: dict = Depends(get_user)):
    """Messen, bei denen der Aufrufer im Team ist und die heute laufen -> Hub zeigt QR mit Kontaktkarte."""
    _staff(user)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = await db.messen.find({"deleted_at": None, "active": True, "staff_ids": user["id"],
                                 "$or": [{"start_date": None}, {"start_date": {"$lte": today}}],
                                 "$and": [{"$or": [{"end_date": None}, {"end_date": {"$gte": today}}]}]}, {"_id": 0}).to_list(20)
    return [{"id": m["id"], "name": m["name"], "location": m.get("location"), "start_date": m.get("start_date"), "end_date": m.get("end_date"),
             "contact_token": (m.get("staff_tokens") or {}).get(user["id"])} for m in rows if (m.get("staff_tokens") or {}).get(user["id"])]


async def _contact_by_token(token: str) -> tuple:
    m = None
    async for cand in db.messen.find({"deleted_at": None, "active": True, "staff_tokens": {"$exists": True}}, {"_id": 0}):
        for uid, t in (cand.get("staff_tokens") or {}).items():
            if t == token and uid in (cand.get("staff_ids") or []):
                m = cand
                break
        if m:
            break
    if not m:
        raise HTTPException(status_code=404, detail="Kontaktkarte nicht gefunden")
    uid = next(k for k, v in m["staff_tokens"].items() if v == token)
    u = await db.users.find_one({"id": uid, "is_active": True}, {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1, "mobile": 1})
    if not u:
        raise HTTPException(status_code=404, detail="Kontaktkarte nicht gefunden")
    p = await db.employee_profiles.find_one({"user_id": uid}, {"_id": 0}) or {}
    return m, u, p


def _contact_payload(m: dict, u: dict, p: dict) -> dict:
    return {"name": u.get("name"), "email": u.get("email"), "phone": p.get("phone") or "", "mobile": u.get("mobile") or "", "position": p.get("position") or "",
            "company": COMPANY["name"], "web": COMPANY["web"], "avatar": bool(p.get("avatar_path")), "user_id": u["id"],
            "messe": {"name": m["name"], "location": m.get("location"), "start_date": m.get("start_date"), "end_date": m.get("end_date")}}


@router.get("/kontakt/{token}")
async def public_contact(token: str):
    m, u, p = await _contact_by_token(token)
    return _contact_payload(m, u, p)


@router.get("/kontakt/{token}/vcard")
async def public_contact_vcard(token: str):
    m, u, p = await _contact_by_token(token)
    c = _contact_payload(m, u, p)
    parts = (c["name"] or "").split(" ", 1)
    last, first = (parts[1], parts[0]) if len(parts) == 2 else (parts[0], "")
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"N:{last};{first};;;", f"FN:{c['name']}", f"ORG:{c['company']}"]
    if c["position"]:
        lines.append(f"TITLE:{c['position']}")
    if c["mobile"]:
        lines.append(f"TEL;TYPE=CELL,VOICE:{c['mobile']}")
    if c["phone"] and c["phone"] != c["mobile"]:
        lines.append(f"TEL;TYPE=WORK,VOICE:{c['phone']}")
    if c["email"]:
        lines.append(f"EMAIL;TYPE=INTERNET,WORK:{c['email']}")
    lines += [f"URL:{c['web']}", f"NOTE:Kennengelernt auf {m['name']}", "END:VCARD"]
    fname = (c["name"] or "kontakt").replace(" ", "_")
    return Response(content="\r\n".join(lines) + "\r\n", media_type="text/vcard; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{fname}.vcf"'})


@router.get("/{messe_id}")
async def get_messe(messe_id: str, user: dict = Depends(get_user)):
    _staff(user)
    m = await _messe(messe_id)
    return {**m, "devices": [_device_brief(d) for d in await _devices_of(m)], "audio": await _audio_list(messe_id)}


@router.patch("/{messe_id}")
async def update_messe(messe_id: str, body: dict, user: dict = Depends(get_user)):
    _staff(user)
    await _messe(messe_id)
    upd = {"updated_at": _now(), "updated_by": user.get("name")}
    for k in ("name", "location", "note"):
        if k in body:
            upd[k] = (body.get(k) or "").strip()
    for k in ("start_date", "end_date"):
        if k in body:
            upd[k] = body.get(k) or None
    if "active" in body:
        upd["active"] = bool(body["active"])
    if "device_ids" in body:
        ids = [str(x) for x in (body.get("device_ids") or [])]
        found = await db.devices.find({"id": {"$in": ids}, "device_type": "mbox"}, {"_id": 0, "id": 1}).to_list(500)
        ok = {d["id"] for d in found}
        upd["device_ids"] = [i for i in ids if i in ok]
    if "staff_ids" in body:
        ids = [str(x) for x in (body.get("staff_ids") or [])]
        found = await db.users.find({"id": {"$in": ids}, "role": {"$in": STAFF_ROLES}, "is_active": True}, {"_id": 0, "id": 1}).to_list(500)
        ok = {u["id"] for u in found}
        upd["staff_ids"] = [i for i in ids if i in ok]
        cur = (await _messe(messe_id)).get("staff_tokens") or {}
        upd["staff_tokens"] = {uid: cur.get(uid) or secrets.token_urlsafe(16) for uid in upd["staff_ids"]}
    if upd.get("name") == "":
        raise HTTPException(status_code=400, detail="Name darf nicht leer sein")
    await db.messen.update_one({"id": messe_id}, {"$set": upd})
    await _notify_sync(messe_id)
    return await get_messe(messe_id, user)


@router.post("/{messe_id}/new-link")
async def rotate_token(messe_id: str, user: dict = Depends(get_user)):
    """Neuen oeffentlichen Link erzeugen - alte QR-Codes werden ungueltig."""
    _staff(user)
    await _messe(messe_id)
    await db.messen.update_one({"id": messe_id}, {"$set": {"public_token": secrets.token_urlsafe(18), "updated_at": _now()}})
    return await get_messe(messe_id, user)


@router.delete("/{messe_id}")
async def delete_messe(messe_id: str, user: dict = Depends(get_user)):
    """Messe archivieren (Soft-Delete) - QR-Codes werden damit ungueltig."""
    _staff(user)
    await _messe(messe_id)
    await db.messen.update_one({"id": messe_id}, {"$set": {"deleted_at": _now(), "active": False, "deleted_by": user.get("name")}})
    await _notify_sync(messe_id)
    return {"ok": True}


# ---- Testdurchsagen ----

async def _process_messe_audio(fid: str, src: Path, stored: str, messe_id: str, enhance: bool = False, preroll_sec: float = 0.0):
    dst = src.with_suffix(".out.mp3")
    try:
        if not mbox_audio.ffmpeg_available():
            data = src.read_bytes()
            sha, size = mbox_audio._sha_size(src)
            await mbox_audio.store_bytes(stored, data)
            await db.messe_audio.update_one({"id": fid}, {"$set": {"status": "ready_unprocessed", "sha256": sha, "size": size,
                                                                   "warning": "ffmpeg fehlt auf dem Server - Datei unveraendert uebernommen"}})
        else:
            analysis = await asyncio.to_thread(mbox_audio.process_audio, src, dst, enhance, preroll_sec)
            sha, size = mbox_audio._sha_size(dst)
            await mbox_audio.store_bytes(stored, dst.read_bytes())
            await db.messe_audio.update_one({"id": fid}, {"$set": {"status": "ready", "sha256": sha, "size": size, "analysis": analysis,
                                                                   "duration_sec": analysis["after"].get("duration_sec")}})
    except Exception as e:
        await db.messe_audio.update_one({"id": fid}, {"$set": {"status": "failed", "error": str(e)[:300]}})
    finally:
        for tmp in (src, dst):
            try:
                tmp.unlink()
            except Exception:
                pass
        await _notify_sync(messe_id)


GUEST_KEEP_MINUTES = 15


async def _store_upload(messe_id: str, file: UploadFile, name: str, enhance: bool, source: str, uploaded_by: str,
                        temporary: bool = False, keep_minutes: int = GUEST_KEEP_MINUTES, session_id: Optional[str] = None,
                        preroll_sec: float = 0.0) -> dict:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in mbox_audio.ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Dateityp {ext or '?'} nicht erlaubt (MP3, WAV, M4A, OGG, AAC, FLAC)")
    fid = str(uuid.uuid4())
    data = bytearray()
    size = 0
    while chunk := await file.read(1 << 20):
        size += len(chunk)
        if size > mbox_audio.MAX_UPLOAD:
            raise HTTPException(status_code=413, detail="Datei groesser als 25 MB")
        data.extend(chunk)
    tmp = tempfile.NamedTemporaryFile(suffix=ext, prefix="messe_ffmpeg_", delete=False)
    with tmp:
        tmp.write(bytes(data))
    label = (name or os.path.splitext(file.filename or "")[0]).strip()[:80] or ("Aufnahme" if source == "record" else "Testdurchsage")
    stored = f"messe{messe_id[:8]}_{fid[:8]}.mp3"
    doc = {"id": fid, "messe_id": messe_id, "name": label, "original_name": file.filename, "stored": stored, "status": "processing",
           "size": size, "sha256": None, "uploaded_by": uploaded_by, "uploaded_at": _now(),
           "source": "record" if source == "record" else "upload", "enhanced": enhance,
           "temporary": temporary, "session_id": session_id, "preroll_sec": preroll_sec or 0,
           "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=max(1, min(keep_minutes, 240)))).isoformat() if temporary else None}
    await db.messe_audio.insert_one(dict(doc))
    asyncio.create_task(_process_messe_audio(fid, Path(tmp.name), stored, messe_id, enhance, preroll_sec))
    return doc


async def cleanup_expired_audio() -> int:
    """Gast-Aufnahmen (temporary) nach Ablauf entfernen - eng gefiltert, nur Dateien mit gesetztem expires_at."""
    now = _now()
    rows = await db.messe_audio.find({"temporary": True, "expires_at": {"$ne": None, "$lt": now}}, {"_id": 0}).to_list(200)
    for f in rows:
        await db.messe_audio.delete_one({"id": f["id"], "temporary": True})
        await mbox_audio.delete_stored(f["stored"])
        await _notify_sync(f["messe_id"])
    return len(rows)


async def cleanup_loop():
    while True:
        try:
            n = await cleanup_expired_audio()
            if n:
                logger.info(f"Messe: {n} abgelaufene Gast-Aufnahme(n) entfernt")
        except Exception as e:
            logger.warning(f"Messe cleanup: {e}")
        await asyncio.sleep(60)


@router.post("/{messe_id}/audio")
async def upload_messe_audio(messe_id: str, file: UploadFile = File(...), name: str = Form(""), enhance: str = Form(""), source: str = Form("upload"),
                             temporary: str = Form(""), keep_minutes: int = Form(GUEST_KEEP_MINUTES), preroll_sec: float = Form(0.0),
                             user: dict = Depends(get_user)):
    """source='record': Mikrofon-Aufnahme (webm/mp4). enhance='1': Sprach-Optimierung. temporary='1': Gast-Aufnahme, wird nach keep_minutes geloescht."""
    _staff(user)
    await _messe(messe_id)
    flag = lambda v: str(v).lower() in ("1", "true", "on", "yes")
    return await _store_upload(messe_id, file, name, flag(enhance), source, user.get("name"), temporary=flag(temporary), keep_minutes=keep_minutes,
                               preroll_sec=preroll_sec)


@router.patch("/{messe_id}/audio/{fid}")
async def rename_messe_audio(messe_id: str, fid: str, body: dict, user: dict = Depends(get_user)):
    _staff(user)
    name = (body.get("name") or "").strip()[:80]
    if not name:
        raise HTTPException(status_code=400, detail="Name fehlt")
    r = await db.messe_audio.update_one({"id": fid, "messe_id": messe_id}, {"$set": {"name": name}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    mbox_pi.invalidate_manifest_cache()
    return {"ok": True}


@router.delete("/{messe_id}/audio/{fid}")
async def delete_messe_audio(messe_id: str, fid: str, user: dict = Depends(get_user)):
    _staff(user)
    f = await db.messe_audio.find_one({"id": fid, "messe_id": messe_id}, {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    await db.messe_audio.delete_one({"id": fid, "messe_id": messe_id})
    await mbox_audio.delete_stored(f["stored"])
    await _notify_sync(messe_id)
    return {"ok": True}


@router.get("/{messe_id}/audio/{fid}/stream")
async def stream_messe_audio(messe_id: str, fid: str, token: str = Query(...)):
    """Vorhoeren im Browser (Mitarbeiter, Token als Query)."""
    from routes.mbox import decode_jwt_token
    payload = decode_jwt_token(token)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Ungueltig")
    _staff(user)
    f = await db.messe_audio.find_one({"id": fid, "messe_id": messe_id}, {"_id": 0})
    data = await mbox_audio.load_bytes(f["stored"]) if f else None
    if data is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return Response(content=data, media_type="audio/mpeg", headers={"Content-Disposition": f'inline; filename="{f["name"]}.mp3"'})


# ===================== Oeffentlich (QR-Code, ohne Login) =====================

@router.post("/public/{token}/session")
async def public_session(token: str, request: Request):
    m = await _messe_by_token(token)
    _rate_public(request, f"session:{m['id']}")
    return await create_session(m, request)


def _visible_to(f: dict, sid: str) -> bool:
    """Gast-Aufnahmen mit Sitzungsbezug sieht nur die eigene Sitzung; alles andere alle."""
    return not f.get("session_id") or f.get("session_id") == sid


@router.get("/public/{token}")
async def public_messe(token: str, request: Request):
    m = await _messe_by_token(token)
    await cleanup_expired_audio()
    sid = request.headers.get("x-messe-session") or ""
    devs = await _devices_of(m)
    audio = [{"id": f["id"], "name": f["name"], "duration_sec": f.get("duration_sec"), "status": f["status"],
              "temporary": bool(f.get("temporary")), "own": bool(f.get("session_id")) and f.get("session_id") == sid, "expires_at": f.get("expires_at")}
             for f in await _audio_list(m["id"])
             if f.get("status") in ("ready", "ready_unprocessed", "processing") and _visible_to(f, sid)
             and (f["status"] != "processing" or (f.get("session_id") and f.get("session_id") == sid))]
    return {"name": m["name"], "location": m.get("location"), "note": m.get("note"), "session_minutes": SESSION_MINUTES,
            "guest_keep_minutes": GUEST_KEEP_MINUTES,
            "devices": [{"id": d["id"], "name": d.get("user_field") or d.get("serial_number"), "pi_online": mbox_pi.pi_state(d)["online"]} for d in devs],
            "audio": audio}


@router.post("/public/{token}/record")
async def public_record(token: str, request: Request, file: UploadFile = File(...), name: str = Form(""), preroll_sec: float = Form(0.0)):
    """Gast spricht eine eigene Durchsage ein: nur fuer seine Sitzung sichtbar, Sprach-Optimierung, wird nach GUEST_KEEP_MINUTES geloescht."""
    m = await _messe_by_token(token)
    await _require_session(request, m)
    _rate_public(request, f"record:{m['id']}")
    sid = request.headers.get("x-messe-session")
    doc = await _store_upload(m["id"], file, name or "Gast-Durchsage", True, "record", f"Messe-Besucher ({m['name']})",
                              temporary=True, keep_minutes=GUEST_KEEP_MINUTES, session_id=sid, preroll_sec=preroll_sec)
    return {"id": doc["id"], "name": doc["name"], "status": doc["status"], "temporary": True, "own": True, "expires_at": doc["expires_at"]}


@router.get("/public/{token}/audio/{fid}/stream")
async def public_audio_stream(token: str, fid: str, s: str = Query("")):
    """Vorhoeren im Handy-Browser (Sitzung als Query, da <audio> keine Header sendet)."""
    m = await _messe_by_token(token)
    sess = await db.messe_sessions.find_one({"id": s, "messe_id": m["id"]}, {"_id": 0}) if s else None
    if not sess or sess["expires_at"] < _now():
        raise HTTPException(status_code=403, detail="Sitzung abgelaufen - bitte QR-Code am Stand erneut scannen")
    f = await db.messe_audio.find_one({"id": fid, "messe_id": m["id"], "status": {"$in": ["ready", "ready_unprocessed"]}}, {"_id": 0})
    if not f or not _visible_to(f, s):
        raise HTTPException(status_code=404, detail="Durchsage nicht gefunden")
    data = await mbox_audio.load_bytes(f["stored"])
    if data is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return Response(content=data, media_type="audio/mpeg", headers={"Content-Disposition": f'inline; filename="{f["name"]}.mp3"', "Accept-Ranges": "bytes"})


@router.get("/public/{token}/audio/{fid}")
async def public_audio_status(token: str, fid: str, request: Request):
    m = await _messe_by_token(token)
    f = await db.messe_audio.find_one({"id": fid, "messe_id": m["id"]}, {"_id": 0})
    if not f or not _visible_to(f, request.headers.get("x-messe-session") or ""):
        raise HTTPException(status_code=404, detail="Durchsage nicht gefunden")
    return {"id": f["id"], "name": f["name"], "status": f["status"], "duration_sec": f.get("duration_sec"), "error": f.get("error"),
            "temporary": bool(f.get("temporary")), "own": True, "expires_at": f.get("expires_at")}


async def _public_device(token: str, device_id: str) -> tuple[dict, dict]:
    m = await _messe_by_token(token)
    if device_id not in (m.get("device_ids") or []):
        raise HTTPException(status_code=404, detail="Dieser Lichtmast gehoert nicht zur Messe")
    return m, await _device(device_id)


@router.get("/public/{token}/{device_id}/status")
async def public_device_status(token: str, device_id: str):
    m, device = await _public_device(token, device_id)
    try:
        res = await _forward(device, "POST", "/api/lesen", json={"namen": LAMP_VARS}, timeout=15.0)
    except HTTPException as e:
        res = {"ok": False, "fehler": e.detail}
    werte = res.get("werte") or {}

    def val(n):
        x = werte.get(n)
        return None if isinstance(x, dict) else x

    pi = mbox_pi.pi_state(device)
    return {"name": device.get("user_field") or device.get("serial_number"), "sps_ok": bool(res.get("ok")),
            "sps_fehler": None if res.get("ok") else res.get("fehler"),
            "lampen": val("DB_HMI.Status.Lampe") or [], "lampen_auswahl": val("DB_Parameter.Lampen_Auswahl") or [],
            "licht_ein": val("DB_HMI.Status.Licht_Ein"), "versorgung": val("DB_HMI.Status.Versorgung"),
            "pi_online": pi["online"], "playing": pi["playing"]}


@router.post("/public/{token}/{device_id}/lampe")
async def public_lampe(token: str, device_id: str, body: dict, request: Request):
    """index 1..5 = einzelne Lampe umschalten, action 'ein' | 'aus' = alle Lampen."""
    m, device = await _public_device(token, device_id)
    await _require_session(request, m)
    _rate_public(request, device_id)
    action = body.get("action")
    idx = body.get("index")
    if action == "ein":
        name, params = "Lampen_Ein", None
    elif action == "aus":
        name, params = "Lampen_Aus", None
    elif isinstance(idx, int) and 1 <= idx <= 5:
        name, params = "Lampe_Umschalten", {"index": str(idx)}
    else:
        raise HTTPException(status_code=400, detail="index 1-5 oder action ein/aus angeben")
    result = await _forward(device, "POST", f"/api/befehl/{name}", params=params)
    await _audit(device, {**PUBLIC_USER, "name": f"Messe-Besucher ({m['name']})"}, f"messe/befehl/{name}", params, result)
    return result


@router.post("/public/{token}/{device_id}/play")
async def public_play(token: str, device_id: str, body: dict, request: Request):
    m, device = await _public_device(token, device_id)
    await _require_session(request, m)
    _rate_public(request, device_id)
    f = await db.messe_audio.find_one({"id": str(body.get("fid") or ""), "messe_id": m["id"],
                                       "status": {"$in": ["ready", "ready_unprocessed"]}}, {"_id": 0})
    if not f or not _visible_to(f, request.headers.get("x-messe-session") or ""):
        raise HTTPException(status_code=404, detail="Durchsage nicht gefunden")
    return await _pi_command(device, {**PUBLIC_USER, "name": f"Messe-Besucher ({m['name']})"}, "play",
                             {"file": f["stored"], "sha256": f.get("sha256"), "loop": False, "label": f["name"]})


@router.post("/public/{token}/{device_id}/stop")
async def public_stop(token: str, device_id: str, request: Request):
    m, device = await _public_device(token, device_id)
    await _require_session(request, m)
    _rate_public(request, device_id)
    return await _pi_command(device, {**PUBLIC_USER, "name": f"Messe-Besucher ({m['name']})"}, "stop", {})


GROUP_COUNTDOWN_SEC = 5


@router.post("/public/{token}/group-play")
async def public_group_play(token: str, body: dict, request: Request):
    """Durchsage auf mehreren Geraeten zeitgleich starten: Countdown 5 s, Pis starten bei 0 (start_at)."""
    m = await _messe_by_token(token)
    await _require_session(request, m)
    _rate_public(request, f"group:{m['id']}")
    f = await db.messe_audio.find_one({"id": str(body.get("fid") or ""), "messe_id": m["id"],
                                       "status": {"$in": ["ready", "ready_unprocessed"]}}, {"_id": 0})
    if not f or not _visible_to(f, request.headers.get("x-messe-session") or ""):
        raise HTTPException(status_code=404, detail="Durchsage nicht gefunden")
    wanted = [str(x) for x in (body.get("device_ids") or []) if str(x) in (m.get("device_ids") or [])]
    if not wanted:
        raise HTTPException(status_code=400, detail="Mindestens ein Geraet auswaehlen")
    devices = await db.devices.find({"id": {"$in": wanted}, "device_type": "mbox"}, {"_id": 0}).to_list(100)
    now_dt = datetime.now(timezone.utc)
    start_at = (now_dt + timedelta(seconds=GROUP_COUNTDOWN_SEC)).isoformat()
    actor = {**PUBLIC_USER, "name": f"Messe-Besucher ({m['name']})"}
    docs = [{"id": str(uuid.uuid4()), "device_id": d["id"], "command": "play", "status": "pending", "messe_id": m["id"],
             "params": {"file": f["stored"], "sha256": f.get("sha256"), "loop": False, "start_at": start_at, "label": f["name"]},
             "user_id": actor["id"], "user_name": actor["name"], "created_at": now_dt.isoformat()} for d in devices]
    await db.mbox_pi_commands.insert_many(docs)
    offline = []
    for d in devices:
        online = mbox_pi.pi_state(d)["online"]
        if not online:
            offline.append(d.get("user_field") or d.get("serial_number"))
        await _audit(d, actor, "messe/durchsage/start", {"file": f["name"], "start_at": start_at}, {"ok": online, "fehler": None if online else "Pi offline"})
    return {"ok": True, "start_at": start_at, "server_time": now_dt.isoformat(), "countdown_sec": GROUP_COUNTDOWN_SEC,
            "devices": len(devices), "offline": offline, "label": f["name"]}


@router.get("/{messe_id}/sps-check")
async def messe_sps_check(messe_id: str, user: dict = Depends(get_user)):
    """Admin/Mitarbeiter: erreicht der Server die SPS (OPC-UA) der Messe-Geraete? Liefert den technischen Grund."""
    _staff(user)
    m = await db.messen.find_one({"id": messe_id, "deleted_at": None}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Messe nicht gefunden")
    devs = await _devices_of(m)

    async def one(d):
        try:
            res = await _forward(d, "POST", "/api/lesen", json={"namen": LAMP_VARS[:1]}, timeout=15.0)
        except HTTPException as e:
            res = {"ok": False, "fehler": e.detail}
        return {"id": d["id"], "name": d.get("user_field") or d.get("serial_number"), "endpoint": d.get("mbox_endpoint"),
                "sps_ok": bool(res.get("ok")), "sps_fehler": None if res.get("ok") else res.get("fehler"),
                "pi_online": mbox_pi.pi_state(d)["online"]}

    return {"devices": list(await asyncio.gather(*(one(d) for d in devs))), "checked_at": _now()}


@router.get("/public/{token}/group-status")
async def public_group_status(token: str):
    """Lampenzustand aller Messe-Geraete (parallel gelesen) fuer die Beleuchtungs-Seite."""
    m = await _messe_by_token(token)
    devs = await _devices_of(m)

    async def one(d):
        try:
            res = await _forward(d, "POST", "/api/lesen", json={"namen": LAMP_VARS[:2]}, timeout=15.0)
        except HTTPException as e:
            res = {"ok": False, "fehler": e.detail}
        w = res.get("werte") or {}
        v = lambda n: None if isinstance(w.get(n), dict) else w.get(n)
        return {"id": d["id"], "name": d.get("user_field") or d.get("serial_number"), "sps_ok": bool(res.get("ok")),
                "sps_fehler": None if res.get("ok") else res.get("fehler"), "lampen": v("DB_HMI.Status.Lampe") or [],
                "lampen_auswahl": v("DB_Parameter.Lampen_Auswahl") or []}

    return {"devices": list(await asyncio.gather(*(one(d) for d in devs)))}


@router.post("/public/{token}/group-lampe")
async def public_group_lampe(token: str, body: dict, request: Request):
    """Beleuchtung auf mehreren Geraeten: action 'ein'|'aus' oder index 1..5 (umschalten)."""
    m = await _messe_by_token(token)
    await _require_session(request, m)
    _rate_public(request, f"group:{m['id']}")
    wanted = [str(x) for x in (body.get("device_ids") or []) if str(x) in (m.get("device_ids") or [])]
    if not wanted:
        raise HTTPException(status_code=400, detail="Mindestens ein Geraet auswaehlen")
    action, idx = body.get("action"), body.get("index")
    if action == "ein":
        name, params = "Lampen_Ein", None
    elif action == "aus":
        name, params = "Lampen_Aus", None
    elif isinstance(idx, int) and 1 <= idx <= 5:
        name, params = "Lampe_Umschalten", {"index": str(idx)}
    else:
        raise HTTPException(status_code=400, detail="index 1-5 oder action ein/aus angeben")
    devices = await db.devices.find({"id": {"$in": wanted}, "device_type": "mbox"}, {"_id": 0}).to_list(100)
    actor = {**PUBLIC_USER, "name": f"Messe-Besucher ({m['name']})"}

    async def one(d):
        try:
            res = await _forward(d, "POST", f"/api/befehl/{name}", params=params, timeout=15.0)
        except HTTPException as e:
            res = {"ok": False, "fehler": e.detail}
        await _audit(d, actor, f"messe/group-befehl/{name}", params, res)
        return {"device_id": d["id"], "name": d.get("user_field") or d.get("serial_number"), **res}

    results = await asyncio.gather(*(one(d) for d in devices))
    return {"ok": all(r.get("ok") for r in results), "results": list(results)}


@router.post("/public/{token}/group-stop")
async def public_group_stop(token: str, body: dict, request: Request):
    m = await _messe_by_token(token)
    await _require_session(request, m)
    _rate_public(request, f"group:{m['id']}")
    wanted = [str(x) for x in (body.get("device_ids") or [])] or (m.get("device_ids") or [])
    ids = [i for i in wanted if i in (m.get("device_ids") or [])]
    now = _now()
    actor = {**PUBLIC_USER, "name": f"Messe-Besucher ({m['name']})"}
    docs = [{"id": str(uuid.uuid4()), "device_id": did, "command": "stop", "params": {}, "status": "pending", "messe_id": m["id"],
             "user_id": actor["id"], "user_name": actor["name"], "created_at": now} for did in ids]
    if docs:
        await db.mbox_pi_commands.insert_many(docs)
    return {"ok": True, "devices": len(docs)}
