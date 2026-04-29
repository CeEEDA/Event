from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Body
from fastapi.responses import Response
from typing import Optional
from datetime import datetime, timezone
import uuid
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/employee", tags=["employee"])
db = None

DOCUMENT_TYPES = [
    "personalausweis",
    "fuehrerschein",
    "fahrerkarte",
    "erste_hilfe",
    "sicherheitsunterweisung",
    "staplerschein",
    "hubarbeitsbuehne",
    "teleskoplader",
    "baumaschine",
]

DOCUMENT_LABELS = {
    "personalausweis": "Personalausweis",
    "fuehrerschein": "Führerschein",
    "fahrerkarte": "Fahrerkarte",
    "erste_hilfe": "Erste Hilfe",
    "sicherheitsunterweisung": "Sicherheitsunterweisung",
    "staplerschein": "Staplerschein",
    "hubarbeitsbuehne": "Hubarbeitsbühne",
    "teleskoplader": "Teleskoplader",
    "baumaschine": "Baumaschine",
}


def _get_storage_fns():
    from routes.documents import put_object, get_object
    return put_object, get_object


async def _get_user(token: str):
    import jwt as pyjwt
    JWT_SECRET = os.environ.get('JWT_SECRET', 'eventenergie-fileshare-secret-key-2024')
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Ungültiger Token")
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    return user


# ==================== PROFILE ====================

@router.get("/profile")
async def get_profile(token: str = Query(...)):
    """Get own profile data."""
    user = await _get_user(token)
    profile = await db.employee_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    return {
        "user_id": user["id"],
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "role": user.get("role", ""),
        "phone": profile.get("phone", "") if profile else "",
        "street": profile.get("street", "") if profile else "",
        "zip_code": profile.get("zip_code", "") if profile else "",
        "city": profile.get("city", "") if profile else "",
        "avatar_path": profile.get("avatar_path") if profile else None,
    }


@router.get("/all")
async def get_all_employees(token: str = Query(...)):
    """Admin only: get all employees with their profile and document summary."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")

    users = await db.users.find({}, {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1}).to_list(500)
    result = []
    for u in users:
        profile = await db.employee_profiles.find_one({"user_id": u["id"]}, {"_id": 0})
        docs = await db.employee_documents.find(
            {"user_id": u["id"], "status": "active"}, {"_id": 0, "doc_type": 1, "expiry_date": 1}
        ).to_list(100)

        doc_summary = {}
        expired_count = 0
        expiring_soon_count = 0
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for d in docs:
            doc_summary[d["doc_type"]] = d.get("expiry_date")
            if d.get("expiry_date"):
                try:
                    exp = datetime.fromisoformat(d["expiry_date"])
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    diff = (exp - now).days
                    if diff < 0:
                        expired_count += 1
                    elif diff <= 60:
                        expiring_soon_count += 1
                except Exception:
                    pass

        result.append({
            "user_id": u["id"],
            "name": u.get("name", ""),
            "email": u.get("email", ""),
            "role": u.get("role", ""),
            "phone": profile.get("phone", "") if profile else "",
            "city": profile.get("city", "") if profile else "",
            "avatar_path": profile.get("avatar_path") if profile else None,
            "doc_count": len(docs),
            "doc_summary": doc_summary,
            "expired_count": expired_count,
            "expiring_soon_count": expiring_soon_count,
        })
    return result


@router.get("/profile/{user_id}")
async def get_profile_by_id(user_id: str, token: str = Query(...)):
    """Admin: get any user's profile."""
    caller = await _get_user(token)
    if caller.get("role") != "admin" and caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="Nur Admins")
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    profile = await db.employee_profiles.find_one({"user_id": user_id}, {"_id": 0})
    return {
        "user_id": user["id"],
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "role": user.get("role", ""),
        "phone": profile.get("phone", "") if profile else "",
        "street": profile.get("street", "") if profile else "",
        "zip_code": profile.get("zip_code", "") if profile else "",
        "city": profile.get("city", "") if profile else "",
        "avatar_path": profile.get("avatar_path") if profile else None,
    }


@router.put("/profile")
async def update_profile(token: str = Query(...),
                          name: str = Form(""),
                          phone: str = Form(""),
                          street: str = Form(""),
                          zip_code: str = Form(""),
                          city: str = Form(""),
                          avatar: Optional[UploadFile] = None):
    """Update own profile (name, address, phone, avatar)."""
    user = await _get_user(token)
    uid = user["id"]

    # Update name in users collection
    if name.strip():
        await db.users.update_one({"id": uid}, {"$set": {"name": name.strip()}})

    # Build profile updates
    updates = {
        "user_id": uid,
        "phone": phone.strip(),
        "street": street.strip(),
        "zip_code": zip_code.strip(),
        "city": city.strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Handle avatar upload
    if avatar and avatar.filename:
        file_bytes = await avatar.read()
        storage_path = f"eventenergie-avatars/{uid}/{avatar.filename}"
        put_obj, _ = _get_storage_fns()
        put_obj(storage_path, file_bytes, avatar.content_type or "image/png")
        updates["avatar_path"] = storage_path

    existing = await db.employee_profiles.find_one({"user_id": uid})
    if existing:
        await db.employee_profiles.update_one({"user_id": uid}, {"$set": updates})
    else:
        updates["created_at"] = datetime.now(timezone.utc).isoformat()
        await db.employee_profiles.insert_one(updates)

    # Return updated profile
    return await get_profile(token=token)


@router.put("/profile/password")
async def change_password(token: str = Query(...), body: dict = {}):
    """Change own password."""
    user = await _get_user(token)
    old_pw = body.get("old_password", "")
    new_pw = body.get("new_password", "")
    if not old_pw or not new_pw:
        raise HTTPException(status_code=400, detail="Altes und neues Passwort erforderlich")
    if len(new_pw) < 6:
        raise HTTPException(status_code=400, detail="Neues Passwort muss mindestens 6 Zeichen lang sein")

    import bcrypt
    full_user = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if not full_user:
        raise HTTPException(status_code=404)
    stored_password = full_user.get("password")
    if not stored_password:
        raise HTTPException(status_code=400, detail="Kein Passwort gesetzt - bitte Administrator kontaktieren")
    if not bcrypt.checkpw(old_pw.encode("utf-8"), stored_password.encode("utf-8")):
        raise HTTPException(status_code=400, detail="Altes Passwort ist falsch")

    hashed = bcrypt.hashpw(new_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password": hashed}})
    return {"status": "ok"}


@router.get("/avatar/{user_id}")
async def get_avatar(user_id: str, token: str = Query(...)):
    """Get user avatar image."""
    await _get_user(token)
    profile = await db.employee_profiles.find_one({"user_id": user_id}, {"_id": 0})
    if not profile or not profile.get("avatar_path"):
        raise HTTPException(status_code=404, detail="Kein Avatar")
    try:
        _, get_obj = _get_storage_fns()
        result = get_obj(profile["avatar_path"])
        data = result[0] if isinstance(result, tuple) else result
        path = profile["avatar_path"]
        ct = "image/png"
        if path.endswith(".jpg") or path.endswith(".jpeg"):
            ct = "image/jpeg"
        elif path.endswith(".webp"):
            ct = "image/webp"
        return Response(content=data, media_type=ct)
    except Exception:
        raise HTTPException(status_code=404, detail="Avatar nicht gefunden")


@router.post("/avatar/{user_id}/upload")
async def admin_upload_avatar(user_id: str, token: str = Query(...), file: UploadFile = File(...)):
    """Admin uploads avatar for any user."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    file_bytes = await file.read()
    storage_path = f"eventenergie-avatars/{user_id}/{file.filename}"
    put_obj, _ = _get_storage_fns()
    put_obj(storage_path, file_bytes, file.content_type or "image/png")
    existing = await db.employee_profiles.find_one({"user_id": user_id})
    if existing:
        await db.employee_profiles.update_one({"user_id": user_id}, {"$set": {"avatar_path": storage_path}})
    else:
        await db.employee_profiles.insert_one({"user_id": user_id, "avatar_path": storage_path, "created_at": datetime.now(timezone.utc).isoformat()})
    return {"ok": True, "avatar_path": storage_path}


# ==================== DOCUMENTS / CERTIFICATES ====================

@router.get("/documents")
async def get_documents(token: str = Query(...), user_id: Optional[str] = None):
    """Get all documents for a user. Admins can view other users' docs."""
    caller = await _get_user(token)
    target_id = user_id if user_id and caller.get("role") == "admin" else caller["id"]

    docs = await db.employee_documents.find(
        {"user_id": target_id},
        {"_id": 0}
    ).sort("uploaded_at", -1).to_list(500)
    return docs


@router.post("/documents")
async def upload_document(token: str = Query(...),
                           doc_type: str = Form(...),
                           user_id: Optional[str] = Form(None),
                           expiry_date: Optional[str] = Form(None),
                           file: UploadFile = File(...)):
    """Upload a document/certificate PDF. AI checks expiry date."""
    caller = await _get_user(token)
    target_id = user_id if user_id and caller.get("role") == "admin" else caller["id"]

    if doc_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Ungültiger Dokumenttyp: {doc_type}")

    file_bytes = await file.read()
    doc_id = str(uuid.uuid4())
    storage_path = f"eventenergie-employee-docs/{target_id}/{doc_type}/{doc_id}_{file.filename}"

    # Store file in cloud (primary)
    put_obj, _ = _get_storage_fns()
    cloud_ok = True
    try:
        put_obj(storage_path, file_bytes, file.content_type or "application/pdf")
    except Exception as e:
        cloud_ok = False
        logger.error(f"Employee doc cloud upload failed (will use local only): {e}")

    # Always also save locally (fallback + redundancy, matches Dokumentenverwaltung)
    try:
        import os as _os
        local_root = _os.environ.get("LOCAL_STORAGE_PATH", r"C:\eventenergie\Dokumentenablage")
        local_file = _os.path.join(local_root, "_mitarbeiter", storage_path.replace("/", _os.sep))
        _os.makedirs(_os.path.dirname(local_file), exist_ok=True)
        with open(local_file, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        logger.warning(f"Employee doc local save failed: {e}")
        if not cloud_ok:
            raise HTTPException(status_code=500, detail=f"Upload fehlgeschlagen (weder Cloud noch lokal): {e}")

    # Mark old documents of same type as "alt"
    await db.employee_documents.update_many(
        {"user_id": target_id, "doc_type": doc_type, "status": "active"},
        {"$set": {"status": "alt", "replaced_at": datetime.now(timezone.utc).isoformat()}}
    )

    # Create new document record
    doc = {
        "id": doc_id,
        "user_id": target_id,
        "doc_type": doc_type,
        "doc_label": DOCUMENT_LABELS.get(doc_type, doc_type),
        "filename": file.filename,
        "content_type": file.content_type or "application/pdf",
        "size": len(file_bytes),
        "storage_path": storage_path,
        "status": "active",
        "expiry_date": expiry_date,
        "ai_expiry_date": None,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "uploaded_by": caller["id"],
    }
    await db.employee_documents.insert_one(doc)

    # AI analysis in background
    try:
        await _ai_check_expiry(doc_id, file_bytes, file.filename, doc_type)
    except Exception as e:
        logger.error(f"AI expiry check failed: {e}")

    # Return without _id
    created = await db.employee_documents.find_one({"id": doc_id}, {"_id": 0})
    return created


async def _ai_check_expiry(doc_id: str, file_bytes: bytes, filename: str, doc_type: str):
    """Use Gemini to detect expiry date from document."""
    import base64
    import tempfile
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
        emergent_api_key = os.environ.get("EMERGENT_LLM_KEY", "") or os.environ.get("EMERGENT_API_KEY", "")
        if not emergent_api_key:
            logger.warning("No EMERGENT_LLM_KEY found, skipping AI expiry check")
            return

        label = DOCUMENT_LABELS.get(doc_type, doc_type)

        # Write temp file for the LLM
        ext = ".pdf" if doc_type else ".pdf"
        if filename:
            ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        # Determine mime type
        mime = "application/pdf"
        lower = filename.lower() if filename else ""
        if lower.endswith((".jpg", ".jpeg")):
            mime = "image/jpeg"
        elif lower.endswith(".png"):
            mime = "image/png"
        elif lower.endswith(".webp"):
            mime = "image/webp"
        elif lower.endswith((".heic", ".heif")):
            mime = "image/heic"

        prompt = f"""Analysiere dieses Dokument. Es handelt sich um einen {label}.

Bei einem Führerschein: Suche das Feld 4b (Ablaufdatum/gültig bis). Das Datum steht meist im Format TT.MM.JJ oder TT.MM.JJJJ.
Bei einem Personalausweis: Suche das Ablaufdatum auf der Rückseite oder im MRZ-Code.
Bei einem Zertifikat: Suche nach "gültig bis", "Ablaufdatum", "valid until" oder ähnlichem.

WICHTIG: Antworte NUR mit dem Datum im Format YYYY-MM-DD.
Wenn das Jahr zweistellig ist (z.B. "30" oder "27"), ergänze es zu vierstellig (2030, 2027).
Falls absolut kein Ablaufdatum erkennbar ist, antworte NUR: KEINS"""

        chat = LlmChat(
            api_key=emergent_api_key,
            session_id=f"expiry-{doc_id}",
            system_message="Du bist ein Dokumenten-Scanner. Extrahiere nur das Ablaufdatum."
        ).with_model("gemini", "gemini-2.5-flash")

        file_content = FileContentWithMimeType(file_path=tmp_path, mime_type=mime)

        user_message = UserMessage(
            text=prompt,
            file_contents=[file_content]
        )

        response = await chat.send_message(user_message)
        text = response.strip()
        logger.info(f"AI raw response for {doc_id}: '{text}'")

        # Clean up temp file
        os.unlink(tmp_path)

        # Parse date - try multiple formats
        import re
        date_str = None
        # Try YYYY-MM-DD directly
        match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
        if match:
            date_str = match.group(1)
        else:
            # Try DD.MM.YYYY
            match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
            if match:
                date_str = f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
            else:
                # Try DD.MM.YY
                match = re.search(r'(\d{2})\.(\d{2})\.(\d{2})', text)
                if match:
                    year = int(match.group(3))
                    year = 2000 + year if year < 80 else 1900 + year
                    date_str = f"{year}-{match.group(2)}-{match.group(1)}"

        if date_str and "KEINS" not in text.upper():
            await db.employee_documents.update_one(
                {"id": doc_id},
                {"$set": {"ai_expiry_date": date_str, "expiry_date": date_str}}
            )
            logger.info(f"AI detected expiry for {doc_id}: {date_str}")
        else:
            logger.info(f"AI could not detect expiry for {doc_id}")
    except Exception as e:
        logger.error(f"AI expiry detection error: {e}")


@router.put("/documents/{doc_id}")
async def update_document(doc_id: str, token: str = Query(...), body: dict = {}):
    """Update expiry date manually."""
    caller = await _get_user(token)
    doc = await db.employee_documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if caller.get("role") != "admin" and caller["id"] != doc["user_id"]:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    updates = {}
    if "expiry_date" in body:
        updates["expiry_date"] = body["expiry_date"]
    if updates:
        await db.employee_documents.update_one({"id": doc_id}, {"$set": updates})

    return await db.employee_documents.find_one({"id": doc_id}, {"_id": 0})


@router.get("/documents/{doc_id}/file")
async def download_document(doc_id: str, token: str = Query(...)):
    """Download a document file. Tries cloud storage first, then local fallback."""
    caller = await _get_user(token)
    doc = await db.employee_documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if caller.get("role") != "admin" and caller["id"] != doc["user_id"]:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    storage_path = doc.get("storage_path", "")
    data = None
    import os as _os
    local_root = _os.environ.get("LOCAL_STORAGE_PATH", r"C:\eventenergie\Dokumentenablage")
    local_file = _os.path.join(local_root, "_mitarbeiter", storage_path.replace("/", _os.sep))

    # 1) Try local filesystem first (fastest, no network)
    if _os.path.exists(local_file):
        try:
            with open(local_file, "rb") as f:
                data = f.read()
        except Exception as e:
            logger.warning(f"Employee doc {doc_id}: Local read failed: {e}")

    # 2) Fall back to cloud storage (and cache locally for next time)
    if not data:
        try:
            _, get_obj = _get_storage_fns()
            result = get_obj(storage_path)
            data = result[0] if isinstance(result, tuple) else result
            # Opportunistic local cache so future requests don't need the cloud
            try:
                _os.makedirs(_os.path.dirname(local_file), exist_ok=True)
                with open(local_file, "wb") as f:
                    f.write(data)
                logger.info(f"Employee doc {doc_id}: cached to local ({local_file})")
            except Exception as e:
                logger.debug(f"Employee doc {doc_id}: Local cache write failed: {e}")
        except Exception as e:
            logger.warning(f"Employee doc {doc_id}: Cloud storage fetch failed: {e}")

    if not data:
        logger.error(f"Employee doc {doc_id} could not be fetched (cloud + local both failed); storage_path={storage_path}")
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    return Response(
        content=data,
        media_type=doc.get("content_type", "application/pdf"),
        headers={"Content-Disposition": f'inline; filename="{doc["filename"]}"'}
    )


@router.get("/document-types")
async def get_document_types(token: str = Query(...)):
    """Get list of all document types with labels."""
    await _get_user(token)
    return [{"key": k, "label": v} for k, v in DOCUMENT_LABELS.items()]


@router.get("/report/expiry")
async def get_expiry_report(token: str = Query(...)):
    """Admin: Get report of all document expiry dates across all employees."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")

    # Get all active documents with expiry dates
    docs = await db.employee_documents.find(
        {"status": "active"},
        {"_id": 0}
    ).sort("expiry_date", 1).to_list(5000)

    # Build user name lookup
    user_ids = list(set(d["user_id"] for d in docs))
    users_map = {}
    for uid in user_ids:
        u = await db.users.find_one({"id": uid}, {"_id": 0, "id": 1, "name": 1})
        if u:
            users_map[uid] = u.get("name", "Unbekannt")

    now = datetime.now(timezone.utc)
    result = []
    for d in docs:
        status = "ok"
        days_left = None
        if d.get("expiry_date"):
            try:
                exp = datetime.fromisoformat(d["expiry_date"])
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                days_left = (exp - now).days
                if days_left < 0:
                    status = "expired"
                elif days_left <= 30:
                    status = "critical"
                elif days_left <= 60:
                    status = "warning"
            except Exception:
                pass
        else:
            status = "no_date"

        result.append({
            "doc_id": d["id"],
            "user_id": d["user_id"],
            "user_name": users_map.get(d["user_id"], "Unbekannt"),
            "doc_type": d["doc_type"],
            "doc_label": d.get("doc_label", DOCUMENT_LABELS.get(d["doc_type"], d["doc_type"])),
            "expiry_date": d.get("expiry_date"),
            "days_left": days_left,
            "status": status,
            "filename": d.get("filename", ""),
        })

    return result


# ==================== TIME TRACKING ====================

@router.get("/time/status")
async def get_time_status(token: str = Query(...)):
    """Get current clock-in status for the user."""
    user = await _get_user(token)
    # Find open entry (clocked in but not out)
    entry = await db.time_entries.find_one(
        {"user_id": user["id"], "clock_out": None},
        {"_id": 0}
    )
    return {
        "clocked_in": entry is not None,
        "entry": entry,
    }


@router.get("/time/presence")
async def get_time_presence(token: str = Query(...)):
    """Admin: get all employees with their current clock-in status (anwesend / abwesend)."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    # Alle aktiven Mitarbeiter und Admins (keine Kunden)
    users = await db.users.find(
        {"is_active": {"$ne": False}, "role": {"$in": ["admin", "mitarbeiter"]}},
        {"_id": 0, "id": 1, "name": 1, "role": 1}
    ).to_list(500)
    # Aktuell offene Time-Entries (eingestempelt)
    open_entries = await db.time_entries.find(
        {"clock_out": None}, {"_id": 0, "user_id": 1, "clock_in": 1}
    ).to_list(500)
    by_user = {e["user_id"]: e["clock_in"] for e in open_entries}
    presence = []
    for u in users:
        clock_in = by_user.get(u["id"])
        presence.append({
            "user_id": u["id"],
            "user_name": u.get("name", ""),
            "role": u.get("role", ""),
            "clocked_in": clock_in is not None,
            "clock_in": clock_in,
        })
    # Sortierung: eingestempelt zuerst, danach Name
    presence.sort(key=lambda p: (not p["clocked_in"], (p["user_name"] or "").lower()))
    return presence


@router.post("/time/clock-in")
async def clock_in(token: str = Query(...), body: dict = {}):
    """Clock in with GPS coordinates."""
    user = await _get_user(token)
    # Check not already clocked in
    existing = await db.time_entries.find_one({"user_id": user["id"], "clock_out": None})
    if existing:
        raise HTTPException(status_code=400, detail="Bereits eingestempelt")

    now = datetime.now(timezone.utc)
    entry = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_name": user.get("name", ""),
        "clock_in": now.isoformat(),
        "clock_in_lat": body.get("lat"),
        "clock_in_lng": body.get("lng"),
        "clock_out": None,
        "clock_out_lat": None,
        "clock_out_lng": None,
        "duration_minutes": None,
        "date": now.strftime("%Y-%m-%d"),
    }
    await db.time_entries.insert_one(entry)
    created = await db.time_entries.find_one({"id": entry["id"]}, {"_id": 0})
    return created


@router.post("/time/clock-out")
async def clock_out(token: str = Query(...), body: dict = {}):
    """Clock out with GPS coordinates. Auto-calculates overtime vs. schedule."""
    user = await _get_user(token)
    entry = await db.time_entries.find_one({"user_id": user["id"], "clock_out": None})
    if not entry:
        raise HTTPException(status_code=400, detail="Nicht eingestempelt")

    now = datetime.now(timezone.utc)
    clock_in_time = datetime.fromisoformat(entry["clock_in"])
    if clock_in_time.tzinfo is None:
        clock_in_time = clock_in_time.replace(tzinfo=timezone.utc)
    duration = (now - clock_in_time).total_seconds() / 60.0

    await db.time_entries.update_one(
        {"id": entry["id"]},
        {"$set": {
            "clock_out": now.isoformat(),
            "clock_out_lat": body.get("lat"),
            "clock_out_lng": body.get("lng"),
            "duration_minutes": round(duration, 1),
        }}
    )

    # ── Overtime calculation based on work schedule ──
    try:
        weekday_map = {0: "montag", 1: "dienstag", 2: "mittwoch", 3: "donnerstag", 4: "freitag", 5: "samstag", 6: "sonntag"}
        # Use local Berlin time for weekday determination
        import zoneinfo
        berlin = zoneinfo.ZoneInfo("Europe/Berlin")
        local_now = now.astimezone(berlin)
        day_name = weekday_map.get(local_now.weekday())

        schedule = await db.work_schedules.find_one({"user_id": user["id"]}, {"_id": 0})
        day_schedule = (schedule or {}).get("days", {}).get(day_name, {})

        if day_schedule and day_schedule.get("start") and day_schedule.get("end"):
            sh, sm = map(int, day_schedule["start"].split(":"))
            eh, em = map(int, day_schedule["end"].split(":"))
            break_min = int(day_schedule.get("break_min") or 0)
            soll_minutes = (eh * 60 + em) - (sh * 60 + sm) - break_min
        else:
            # No schedule for this day → all worked time is overtime
            soll_minutes = 0

        ist_minutes = round(duration)
        diff_minutes = ist_minutes - soll_minutes  # positive = overtime, negative = undertime
        diff_hours = round(diff_minutes / 60, 2)

        if diff_minutes != 0:
            year = local_now.year
            hr = await db.hr_data.find_one({"user_id": user["id"], "year": year})
            current_overtime = hr.get("overtime_hours", 0) if hr else 0
            new_overtime = round(current_overtime + diff_hours, 2)
            await db.hr_data.update_one(
                {"user_id": user["id"], "year": year},
                {"$set": {"overtime_hours": new_overtime}},
                upsert=True,
            )
            logger.info(f"Overtime update: {user.get('name','')} IST={ist_minutes}m SOLL={soll_minutes}m diff={diff_hours}h → new total={new_overtime}h")
    except Exception as e:
        logger.error(f"Overtime calc error: {e}")

    updated = await db.time_entries.find_one({"id": entry["id"]}, {"_id": 0})
    return updated


@router.get("/time/entries")
async def get_time_entries(token: str = Query(...), user_id: Optional[str] = None,
                            date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Get time entries. Admin can view other users."""
    caller = await _get_user(token)
    target_id = user_id if user_id and caller.get("role") == "admin" else caller["id"]

    query = {"user_id": target_id}
    if date_from:
        query["date"] = {"$gte": date_from}
    if date_to:
        query.setdefault("date", {})
        if isinstance(query["date"], dict):
            query["date"]["$lte"] = date_to
        else:
            query["date"] = {"$gte": query["date"], "$lte": date_to}

    entries = await db.time_entries.find(query, {"_id": 0}).sort("clock_in", -1).to_list(1000)
    return entries


def _parse_local_time_to_utc(date_str: str, time_str: str) -> datetime:
    """Parse a local German date+time string ('YYYY-MM-DD' + 'HH:MM') as UTC ISO.
    We store everything in UTC; assume the input is already wall-clock and treat it as UTC for now
    (the rest of the time-tracking does the same – clock_in via datetime.now(timezone.utc).isoformat())."""
    if not date_str or not time_str:
        raise HTTPException(status_code=400, detail="Datum und Uhrzeit erforderlich")
    try:
        # Combine date + time into ISO; assume it represents local clock time stored as UTC tz
        dt = datetime.fromisoformat(f"{date_str}T{time_str}:00").replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        raise HTTPException(status_code=400, detail=f"Ungueltiges Datum/Uhrzeit: {date_str} {time_str}")


@router.post("/time/manual")
async def create_manual_time_entry(token: str = Query(...), body: dict = Body(...)):
    """Admin: create a time entry manually for any user (e.g. employee 'verstempelt' himself)."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    target_user_id = body.get("user_id")
    if not target_user_id:
        raise HTTPException(status_code=400, detail="user_id erforderlich")
    target_user = await db.users.find_one({"id": target_user_id}, {"_id": 0, "name": 1})
    if not target_user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    date_str = body.get("date")
    start_str = body.get("clock_in_time")
    end_str = body.get("clock_out_time")
    clock_in = _parse_local_time_to_utc(date_str, start_str)
    clock_out = _parse_local_time_to_utc(date_str, end_str) if end_str else None

    if clock_out and clock_out <= clock_in:
        raise HTTPException(status_code=400, detail="Endzeit muss nach Startzeit liegen")

    duration = round((clock_out - clock_in).total_seconds() / 60.0, 1) if clock_out else None

    entry = {
        "id": str(uuid.uuid4()),
        "user_id": target_user_id,
        "user_name": target_user.get("name", ""),
        "clock_in": clock_in.isoformat(),
        "clock_in_lat": None,
        "clock_in_lng": None,
        "clock_out": clock_out.isoformat() if clock_out else None,
        "clock_out_lat": None,
        "clock_out_lng": None,
        "duration_minutes": duration,
        "date": date_str,
        "manual": True,
        "manual_by": caller.get("id"),
        "manual_by_name": caller.get("name", ""),
        "manual_note": body.get("note") or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.time_entries.insert_one(entry)
    return await db.time_entries.find_one({"id": entry["id"]}, {"_id": 0})


@router.put("/time/entries/{entry_id}")
async def update_time_entry(entry_id: str, token: str = Query(...), body: dict = Body(...)):
    """Admin: edit an existing time entry (clock_in / clock_out)."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    entry = await db.time_entries.find_one({"id": entry_id}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")

    date_str = body.get("date") or entry.get("date")
    start_str = body.get("clock_in_time")
    end_str = body.get("clock_out_time")

    if not start_str:
        raise HTTPException(status_code=400, detail="Startzeit erforderlich")
    clock_in = _parse_local_time_to_utc(date_str, start_str)
    clock_out = _parse_local_time_to_utc(date_str, end_str) if end_str else None
    if clock_out and clock_out <= clock_in:
        raise HTTPException(status_code=400, detail="Endzeit muss nach Startzeit liegen")
    duration = round((clock_out - clock_in).total_seconds() / 60.0, 1) if clock_out else None

    update = {
        "clock_in": clock_in.isoformat(),
        "clock_out": clock_out.isoformat() if clock_out else None,
        "duration_minutes": duration,
        "date": date_str,
        "edited_by": caller.get("id"),
        "edited_by_name": caller.get("name", ""),
        "edited_at": datetime.now(timezone.utc).isoformat(),
    }
    if "note" in body:
        update["manual_note"] = body.get("note") or ""
    await db.time_entries.update_one({"id": entry_id}, {"$set": update})
    return await db.time_entries.find_one({"id": entry_id}, {"_id": 0})


@router.delete("/time/entries/{entry_id}")
async def delete_time_entry(entry_id: str, token: str = Query(...)):
    """Admin: delete a time entry."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    res = await db.time_entries.delete_one({"id": entry_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return {"ok": True}


@router.get("/time/report")
async def get_time_report(token: str = Query(...),
                           date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Admin: get time report for all employees."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")

    query = {"clock_out": {"$ne": None}}
    if date_from:
        query["date"] = {"$gte": date_from}
    if date_to:
        query.setdefault("date", {})
        if isinstance(query["date"], dict):
            query["date"]["$lte"] = date_to
        else:
            query["date"] = {"$gte": query["date"], "$lte": date_to}

    entries = await db.time_entries.find(query, {"_id": 0}).sort("clock_in", -1).to_list(5000)

    # Group by user
    by_user = {}
    for e in entries:
        uid = e["user_id"]
        if uid not in by_user:
            by_user[uid] = {"user_id": uid, "user_name": e.get("user_name", ""), "total_minutes": 0, "entries": []}
        by_user[uid]["entries"].append(e)
        by_user[uid]["total_minutes"] += e.get("duration_minutes", 0) or 0

    # Include ALL users (even those without time entries)
    async for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1, "role": 1}):
        uid = u["id"]
        if uid not in by_user:
            by_user[uid] = {"user_id": uid, "user_name": u.get("name", ""), "total_minutes": 0, "entries": []}

    return list(by_user.values())



# ─── HR Data (Overtime / Vacation) ──────────────────────────────

@router.get("/hr-data/{user_id}")
async def get_hr_data(user_id: str, token: str = Query(...)):
    """Get HR data (overtime, vacation, birthday) for a user. Admins get full data, employees only their own."""
    caller = await _get_user(token)
    if caller.get("role") != "admin" and caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    year = datetime.now(timezone.utc).year
    doc = await db.hr_data.find_one({"user_id": user_id, "year": year}, {"_id": 0})
    if not doc:
        doc = {"user_id": user_id, "year": year, "overtime_hours": 0, "vacation_days_total": 0, "vacation_days_used": 0}

    remaining = (doc.get("vacation_days_total") or 0) - (doc.get("vacation_days_used") or 0)
    doc["vacation_days_remaining"] = remaining

    # Geburtstag aus User-Dokument
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "date_of_birth": 1})
    doc["date_of_birth"] = (user or {}).get("date_of_birth") or ""
    return doc


@router.put("/hr-data/{user_id}")
async def update_hr_data(user_id: str, token: str = Query(...), data: dict = Body(...)):
    """Admin only: update HR data for a user."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")

    year = datetime.now(timezone.utc).year
    update = {}
    if "overtime_hours" in data:
        update["overtime_hours"] = float(data["overtime_hours"])
    if "vacation_days_total" in data:
        update["vacation_days_total"] = int(data["vacation_days_total"])
    if "vacation_days_used" in data:
        update["vacation_days_used"] = int(data["vacation_days_used"])

    if update:
        update["user_id"] = user_id
        update["year"] = year
        await db.hr_data.update_one(
            {"user_id": user_id, "year": year},
            {"$set": update},
            upsert=True,
        )

    # Geburtstag direkt am User-Dokument speichern (YYYY-MM-DD oder leer)
    if "date_of_birth" in data:
        dob = (data.get("date_of_birth") or "").strip()
        await db.users.update_one({"id": user_id}, {"$set": {"date_of_birth": dob}})

    doc = await db.hr_data.find_one({"user_id": user_id, "year": year}, {"_id": 0})
    if not doc:
        doc = {"user_id": user_id, "year": year, "overtime_hours": 0, "vacation_days_total": 0, "vacation_days_used": 0}
    remaining = (doc.get("vacation_days_total") or 0) - (doc.get("vacation_days_used") or 0)
    doc["vacation_days_remaining"] = remaining
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "date_of_birth": 1})
    doc["date_of_birth"] = (user or {}).get("date_of_birth") or ""
    return doc


@router.get("/birthdays/today")
async def get_birthdays_today(token: str = Query(...)):
    """Liste aller Mitarbeiter, die heute Geburtstag haben."""
    await _get_user(token)  # Authentifizierung
    today = datetime.now(timezone.utc).date()
    today_mmdd = today.strftime("%m-%d")

    users = await db.users.find(
        {"date_of_birth": {"$exists": True, "$ne": ""}},
        {"_id": 0, "id": 1, "name": 1, "date_of_birth": 1}
    ).to_list(1000)

    result = []
    for u in users:
        dob = (u.get("date_of_birth") or "").strip()
        if len(dob) < 10:
            continue
        try:
            dob_date = datetime.strptime(dob[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if dob_date.strftime("%m-%d") != today_mmdd:
            continue
        age = today.year - dob_date.year
        # Falls Geburtstag in der Zukunft des aktuellen Jahres waere (Edge-Fall bei Zeitzone), korrigieren
        if (today.month, today.day) < (dob_date.month, dob_date.day):
            age -= 1
        result.append({
            "user_id": u.get("id"),
            "name": u.get("name", ""),
            "date_of_birth": dob,
            "age": age,
        })
    return result


# ─── Info Posts (Admin → Alle Mitarbeiter) ─────────────────

@router.get("/info-posts")
async def list_info_posts(token: str = Query(...)):
    """Alle aktiven Info-Posts (neueste zuerst, abgelaufene ausgeblendet)."""
    user = await _get_user(token)
    now_iso = datetime.now(timezone.utc).isoformat()
    posts = await db.info_posts.find(
        {
            "deleted": {"$ne": True},
            "$or": [
                {"expires_at": {"$in": [None, ""]}},
                {"expires_at": {"$exists": False}},
                {"expires_at": {"$gte": now_iso}},
            ],
        },
        {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    # is_read_by_me Flag + Leser-Liste (fuer Admins alles sichtbar)
    is_admin = user.get("role") == "admin"
    for p in posts:
        reads = p.get("reads", []) or []
        p["is_read_by_me"] = any(r.get("user_id") == user["id"] for r in reads)
        p["read_count"] = len(reads)
        if not is_admin:
            p.pop("reads", None)
    return posts


@router.post("/info-posts")
async def create_info_post(
    token: str = Query(...),
    text: str = Form(""),
    expires_at: str = Form(""),
    response_deadline: str = Form(""),
    file: Optional[UploadFile] = File(None),
):
    """Admin: neuen Info-Post erstellen (Text und/oder Anhang, optional Ablauf & Deadline)."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins duerfen Info-Posts erstellen")
    text = (text or "").strip()
    if not text and not file:
        raise HTTPException(status_code=400, detail="Text oder Anhang erforderlich")

    post_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    def _parse_date_to_iso_end_of_day(s: str) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        # YYYY-MM-DD -> end of day UTC
        try:
            d = datetime.strptime(s[:10], "%Y-%m-%d")
            return d.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc).isoformat()
        except ValueError:
            return ""

    doc = {
        "id": post_id,
        "text": text,
        "author_id": caller["id"],
        "author_name": caller.get("name", caller.get("email", "")),
        "created_at": now_iso,
        "expires_at": _parse_date_to_iso_end_of_day(expires_at),
        "response_deadline": _parse_date_to_iso_end_of_day(response_deadline),
        "reads": [],
        "deleted": False,
    }

    if file is not None:
        file_bytes = await file.read()
        if len(file_bytes) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Datei zu gross (max 20 MB)")
        storage_path = f"info-posts/{post_id}/{file.filename}"
        put_obj, _ = _get_storage_fns()
        put_obj(storage_path, file_bytes, file.content_type or "application/octet-stream")
        doc["attachment"] = {
            "filename": file.filename,
            "content_type": file.content_type or "application/octet-stream",
            "size": len(file_bytes),
            "storage_path": storage_path,
        }

    await db.info_posts.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.post("/info-posts/{post_id}/read")
async def mark_info_post_read(post_id: str, token: str = Query(...)):
    """Markiert Info-Post als gelesen fuer den aktuellen User (idempotent)."""
    caller = await _get_user(token)
    post = await db.info_posts.find_one({"id": post_id, "deleted": {"$ne": True}}, {"_id": 0, "reads": 1})
    if not post:
        raise HTTPException(status_code=404, detail="Post nicht gefunden")
    reads = post.get("reads", []) or []
    if any(r.get("user_id") == caller["id"] for r in reads):
        return {"ok": True, "already_read": True}
    read_entry = {
        "user_id": caller["id"],
        "user_name": caller.get("name", caller.get("email", "")),
        "read_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.info_posts.update_one({"id": post_id}, {"$push": {"reads": read_entry}})
    return {"ok": True, "already_read": False}


@router.get("/info-posts/{post_id}/attachment")
async def download_info_post_attachment(post_id: str, token: str = Query(...), thumbnail: int = 0, size: int = 200):
    """Anhang eines Info-Posts herunterladen (alle authentifizierten User)."""
    await _get_user(token)
    post = await db.info_posts.find_one({"id": post_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not post or not post.get("attachment"):
        raise HTTPException(status_code=404, detail="Anhang nicht gefunden")
    att = post["attachment"]
    _, get_obj = _get_storage_fns()
    result = get_obj(att["storage_path"])
    if not result:
        raise HTTPException(status_code=404, detail="Datei nicht im Storage")
    data, ct = result
    if thumbnail and (ct or att.get("content_type", "")).startswith("image/"):
        from utils.thumbnails import make_thumbnail_from_bytes
        tdata = make_thumbnail_from_bytes(data, size=min(max(int(size), 16), 1024))
        if tdata is not None:
            return Response(content=tdata, media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=86400"})
    return Response(
        content=data,
        media_type=ct or att.get("content_type", "application/octet-stream"),
        headers={"Content-Disposition": f'inline; filename="{att["filename"]}"'}
    )


@router.delete("/info-posts/{post_id}")
async def delete_info_post(post_id: str, token: str = Query(...)):
    """Admin: Info-Post loeschen (Soft-Delete)."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    res = await db.info_posts.update_one(
        {"id": post_id},
        {"$set": {"deleted": True, "deleted_at": datetime.now(timezone.utc).isoformat()}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Post nicht gefunden")
    return {"ok": True}



# ─── Vacation Entries ──────────────────────────────

def _count_weekdays(start_str: str, end_str: str) -> int:
    """Count weekdays (Mon-Fri) between two dates inclusive."""
    from datetime import date, timedelta
    start = date.fromisoformat(start_str)
    end = date.fromisoformat(end_str)
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon=0 .. Fri=4
            count += 1
        current += timedelta(days=1)
    return count


async def _recalc_vacation_used(user_id: str, year: int):
    """Recalculate vacation_days_used from all vacation entries for the year."""
    entries = await db.vacation_entries.find(
        {"user_id": user_id, "year": year},
        {"_id": 0}
    ).to_list(500)
    total_days = sum(e.get("days", 0) for e in entries)
    await db.hr_data.update_one(
        {"user_id": user_id, "year": year},
        {"$set": {"vacation_days_used": total_days, "user_id": user_id, "year": year}},
        upsert=True,
    )
    return total_days


@router.get("/vacation/{user_id}")
async def get_vacation_entries(user_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin" and caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    year = datetime.now(timezone.utc).year
    entries = await db.vacation_entries.find(
        {"user_id": user_id, "year": year}, {"_id": 0}
    ).sort("start_date", 1).to_list(500)
    return entries


@router.post("/vacation/{user_id}")
async def add_vacation_entry(user_id: str, token: str = Query(...), data: dict = Body(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")

    start_date = data.get("start_date")
    end_date = data.get("end_date")
    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="Start- und Enddatum erforderlich")

    days = _count_weekdays(start_date, end_date)
    if days <= 0:
        raise HTTPException(status_code=400, detail="Ungültiger Zeitraum")

    year = int(start_date[:4])
    entry = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "year": year,
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.vacation_entries.insert_one(entry)
    await _recalc_vacation_used(user_id, year)
    return {"id": entry["id"], "days": days}


@router.delete("/vacation/{user_id}/{entry_id}")
async def delete_vacation_entry(user_id: str, entry_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")

    entry = await db.vacation_entries.find_one({"id": entry_id, "user_id": user_id})
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")

    year = entry.get("year", datetime.now(timezone.utc).year)
    await db.vacation_entries.delete_one({"id": entry_id, "user_id": user_id})
    await _recalc_vacation_used(user_id, year)
    return {"ok": True}


# ─── Time Off Requests ──────────────────────────────

@router.post("/time-off/admin-create")
async def admin_create_time_off(token: str = Query(...), data: dict = Body(...)):
    """Admin: directly create an approved time-off entry for a user (e.g. Überstundenabbau).
    Skips the request/approval flow – the entry lands as 'approved' immediately.
    For 'ueberstundenabbau' the overtime account is reduced by 8h per weekday."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")

    target_user_id = data.get("user_id")
    req_type = data.get("type", "ueberstundenabbau")
    start_date = data.get("start_date")
    end_date = data.get("end_date") or start_date

    if not target_user_id or not start_date:
        raise HTTPException(status_code=400, detail="user_id und start_date erforderlich")
    if req_type not in ("ueberstundenabbau", "urlaub", "krank"):
        raise HTTPException(status_code=400, detail="Ungueltiger Typ")

    target = await db.users.find_one({"id": target_user_id}, {"_id": 0, "id": 1, "name": 1, "email": 1})
    if not target:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    days = _count_weekdays(start_date, end_date)
    type_labels = {"krank": "Krankmeldung", "urlaub": "Urlaubsantrag", "ueberstundenabbau": "Überstundenabbau"}

    now_iso = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": str(uuid.uuid4()),
        "user_id": target_user_id,
        "user_name": target.get("name", target.get("email", "")),
        "type": req_type,
        "type_label": type_labels.get(req_type, req_type),
        "start_date": start_date,
        "end_date": end_date,
        "all_day": True,
        "start_time": None,
        "end_time": None,
        "days": days,
        "status": "approved",
        "created_at": now_iso,
        "resolved_at": now_iso,
        "resolved_by": caller.get("id"),
        "resolved_by_name": caller.get("name", "Admin"),
        "admin_created": True,
    }
    await db.time_off_requests.insert_one(entry)

    # If 'ueberstundenabbau': deduct 8h per weekday from overtime account
    if req_type == "ueberstundenabbau" and days > 0:
        hours_to_deduct = days * 8.0
        hr = await db.hr_data.find_one({"user_id": target_user_id}, {"_id": 0})
        current = float(hr.get("overtime_hours", 0)) if hr else 0.0
        new_val = round(current - hours_to_deduct, 2)
        await db.hr_data.update_one(
            {"user_id": target_user_id},
            {"$set": {"overtime_hours": new_val, "updated_at": now_iso}},
            upsert=True,
        )

    return {k: v for k, v in entry.items() if k != "_id"}


@router.delete("/time-off/{request_id}")
async def admin_delete_time_off(request_id: str, token: str = Query(...)):
    """Admin: delete a time-off entry. If approved 'ueberstundenabbau', refund the hours."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    req = await db.time_off_requests.find_one({"id": request_id}, {"_id": 0})
    if not req:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")

    # Refund overtime if it was an approved Überstundenabbau
    if req.get("status") == "approved" and req.get("type") == "ueberstundenabbau":
        days = req.get("days", 0) or 0
        if days > 0:
            hours_to_refund = days * 8.0
            hr = await db.hr_data.find_one({"user_id": req["user_id"]}, {"_id": 0})
            current = float(hr.get("overtime_hours", 0)) if hr else 0.0
            new_val = round(current + hours_to_refund, 2)
            await db.hr_data.update_one(
                {"user_id": req["user_id"]},
                {"$set": {"overtime_hours": new_val, "updated_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )

    await db.time_off_requests.delete_one({"id": request_id})
    return {"ok": True}


@router.post("/time-off")
async def create_time_off_request(token: str = Query(...), data: dict = Body(...)):
    """Employee creates a time-off request."""
    caller = await _get_user(token)
    req_type = data.get("type")  # krank, urlaub, ueberstundenabbau
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    all_day = data.get("all_day", True)
    start_time = data.get("start_time")
    end_time = data.get("end_time")

    if not req_type or not start_date:
        raise HTTPException(status_code=400, detail="Typ und Startdatum erforderlich")
    if not end_date:
        end_date = start_date

    days = _count_weekdays(start_date, end_date) if all_day else 0

    type_labels = {"krank": "Krankmeldung", "urlaub": "Urlaubsantrag", "ueberstundenabbau": "Überstundenabbau"}
    label = type_labels.get(req_type, req_type)

    entry = {
        "id": str(uuid.uuid4()),
        "user_id": caller["id"],
        "user_name": caller.get("name", caller.get("email", "")),
        "type": req_type,
        "type_label": label,
        "start_date": start_date,
        "end_date": end_date,
        "all_day": all_day,
        "start_time": start_time if not all_day else None,
        "end_time": end_time if not all_day else None,
        "days": days,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
        "resolved_by": None,
    }
    await db.time_off_requests.insert_one(entry)

    # Create a task for all admins
    task_title = f"{label}: {caller.get('name', caller.get('email',''))} ({start_date}"
    if end_date != start_date:
        task_title += f" - {end_date}"
    task_title += ")"
    if not all_day and start_time and end_time:
        task_title += f" {start_time}-{end_time}"

    admins = await db.users.find({"role": "admin"}, {"_id": 0, "id": 1, "name": 1}).to_list(100)
    admin_ids = [a["id"] for a in admins]
    assigned_to_names = {a["id"]: a.get("name", "Admin") for a in admins}

    now = datetime.now(timezone.utc).isoformat()
    task = {
        "id": str(uuid.uuid4()),
        "title": task_title,
        "description": f"Antrag von {caller.get('name', '')} auf {label}.\nZeitraum: {start_date} bis {end_date}" + (f"\nUhrzeit: {start_time} - {end_time}" if not all_day else f"\nGanztägig ({days} Tage)"),
        "priority": "hoch",
        "priority_order": 0,
        "status": "open",
        "created_by": caller["id"],
        "created_by_name": caller.get("name", caller.get("email", "")),
        "assigned_to": admin_ids,
        "assigned_to_names": assigned_to_names,
        "due_date": start_date,
        "created_at": now,
        "updated_at": now,
        "completed": False,
        "completed_at": None,
        "completed_by": None,
        "completed_by_name": None,
        "comment_count": 0,
        "is_deleted": False,
        "time_off_request_id": entry["id"],
    }
    await db.tasks.insert_one(task)

    return {"id": entry["id"], "days": days, "task_id": task["id"]}


@router.get("/time-off")
async def get_time_off_requests(token: str = Query(...), user_id: str = None):
    """Get time-off requests. Employees see their own, admins can filter by user_id or see all."""
    caller = await _get_user(token)
    query = {}
    if caller.get("role") == "admin":
        if user_id:
            query["user_id"] = user_id
    else:
        query["user_id"] = caller["id"]

    entries = await db.time_off_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return entries


@router.put("/time-off/{request_id}")
async def resolve_time_off_request(request_id: str, token: str = Query(...), data: dict = Body(...)):
    """Admin approves or rejects a time-off request."""
    caller = await _get_user(token)

    status = data.get("status")  # approved, rejected, withdrawn
    if status not in ("approved", "rejected", "withdrawn"):
        raise HTTPException(status_code=400, detail="Status muss 'approved', 'rejected' oder 'withdrawn' sein")

    req = await db.time_off_requests.find_one({"id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="Antrag nicht gefunden")

    # Withdrawn: only the request creator can withdraw
    if status == "withdrawn":
        if req["user_id"] != caller["id"]:
            raise HTTPException(status_code=403, detail="Nur der Antragsteller kann zurückziehen")
    else:
        # approved/rejected: only admins
        if caller.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Nur Admins")

    await db.time_off_requests.update_one(
        {"id": request_id},
        {"$set": {"status": status, "resolved_at": datetime.now(timezone.utc).isoformat(), "resolved_by": caller["id"]}}
    )

    # If approved and type is urlaub, add vacation entry
    if status == "approved" and req.get("type") == "urlaub" and req.get("all_day") and req.get("days", 0) > 0:
        year = int(req["start_date"][:4])
        vac_entry = {
            "id": str(uuid.uuid4()),
            "user_id": req["user_id"],
            "year": year,
            "start_date": req["start_date"],
            "end_date": req["end_date"],
            "days": req["days"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "from_request": request_id,
        }
        await db.vacation_entries.insert_one(vac_entry)
        await _recalc_vacation_used(req["user_id"], year)

    # If approved and type is ueberstundenabbau, deduct from overtime account (8h per day)
    if status == "approved" and req.get("type") == "ueberstundenabbau":
        days = req.get("days", 0)
        hours_to_deduct = days * 8 if days > 0 else 8
        year = int(req["start_date"][:4])
        hr = await db.hr_data.find_one({"user_id": req["user_id"], "year": year})
        current_overtime = hr.get("overtime_hours", 0) if hr else 0
        new_overtime = current_overtime - hours_to_deduct
        await db.hr_data.update_one(
            {"user_id": req["user_id"], "year": year},
            {"$set": {"overtime_hours": new_overtime}},
            upsert=True
        )

    # Mark related task as completed
    task = await db.tasks.find_one({"time_off_request_id": request_id})
    if task:
        status_labels = {"approved": "Genehmigt", "rejected": "Abgelehnt", "withdrawn": "Zurückgezogen"}
        status_label = status_labels.get(status, status)
        await db.tasks.update_one(
            {"id": task["id"]},
            {"$set": {
                "status": "done",
                "completed": True,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "completed_by": caller["id"],
                "completed_by_name": caller.get("name", ""),
                "title": f"[{status_label}] {task['title']}",
            }}
        )

    return {"ok": True, "status": status}


# ── Work Schedule (Regelarbeitszeit) ──────────────────────

WEEKDAYS = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"]

@router.get("/work-schedule/{user_id}")
async def get_work_schedule(user_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin" and caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    doc = await db.work_schedules.find_one({"user_id": user_id}, {"_id": 0})
    if not doc:
        doc = {"user_id": user_id, "days": {}}
    return doc

@router.put("/work-schedule/{user_id}")
async def update_work_schedule(user_id: str, token: str = Query(...), data: dict = Body(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    update_fields = {"user_id": user_id, "updated_at": datetime.now(timezone.utc).isoformat()}
    if "days" in data:
        update_fields["days"] = data["days"]
    if "hourly_wage" in data:
        update_fields["hourly_wage"] = float(data["hourly_wage"])
    if "surcharges" in data:
        update_fields["surcharges"] = data["surcharges"]
    await db.work_schedules.update_one(
        {"user_id": user_id},
        {"$set": update_fields},
        upsert=True,
    )
    return {"ok": True}


# ── Payroll Calculation ──────────────────────────────────

import zoneinfo
from calendar import monthrange
import csv
import io

BERLIN = zoneinfo.ZoneInfo("Europe/Berlin")

# German public holidays (fixed dates, nationwide)
def _get_holidays(year):
    """Return dict of date_str -> holiday_name for a given year."""
    from datetime import date, timedelta
    holidays = {}
    # Fixed
    for d, name in [
        (date(year, 1, 1), "Neujahr"),
        (date(year, 5, 1), "Tag der Arbeit"),
        (date(year, 10, 3), "Tag der Deutschen Einheit"),
        (date(year, 12, 25), "1. Weihnachtsfeiertag"),
        (date(year, 12, 26), "2. Weihnachtsfeiertag"),
    ]:
        holidays[d.isoformat()] = name
    # Easter-based (Gauss algorithm)
    a = year % 19
    b = year // 100
    c = year % 100
    d_ = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d_ - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month_e = (h + l - 7 * m + 114) // 31
    day_e = ((h + l - 7 * m + 114) % 31) + 1
    easter = date(year, month_e, day_e)
    for offset, name in [
        (-2, "Karfreitag"), (1, "Ostermontag"),
        (39, "Christi Himmelfahrt"), (50, "Pfingstmontag"),
        (60, "Fronleichnam"),  # RLP (beweglich, Ostern + 60)
    ]:
        d2 = easter + timedelta(days=offset)
        holidays[d2.isoformat()] = name
    # RLP-Landesfeiertag (fest)
    holidays[date(year, 11, 1).isoformat()] = "Allerheiligen"
    return holidays

SPECIAL_HOLIDAY_DATES = ["12-24", "12-25", "12-26", "05-01"]  # 150% dates

def _is_special_holiday(date_str):
    return date_str[5:] in SPECIAL_HOLIDAY_DATES

def _calc_night_minutes(clock_in_local, clock_out_local):
    """Calculate minutes worked between 20:00 and 06:00 (night hours)."""
    from datetime import date as dt_date, timedelta
    night_min = 0
    current = clock_in_local
    while current < clock_out_local:
        hour = current.hour
        if hour >= 20 or hour < 6:
            next_min = min(current + timedelta(minutes=1), clock_out_local)
            night_min += (next_min - current).total_seconds() / 60
            current = next_min
        else:
            # Skip to 20:00 same day or next iteration
            if hour < 20:
                jump_to = current.replace(hour=20, minute=0, second=0, microsecond=0)
                if jump_to > clock_out_local:
                    break
                current = jump_to
            else:
                current += timedelta(minutes=1)
    return round(night_min)


@router.get("/payroll/my-releases")
async def get_my_releases(token: str = Query(...)):
    """Employee gets their own released payrolls."""
    caller = await _get_user(token)
    releases = await db.payroll_releases.find({"user_id": caller["id"]}, {"_id": 0}).sort("month", -1).to_list(200)
    return releases


@router.get("/payroll/my-documents")
async def get_my_payroll_documents(token: str = Query(...)):
    """Employee gets their assigned DATEV payroll PDFs."""
    caller = await _get_user(token)
    docs = await db.documents.find(
        {"assigned_user_id": caller["id"], "folder_id": {"$regex": "^lohnabrechnung"}, "is_deleted": False},
        {"_id": 0, "id": 1, "original_filename": 1, "payroll_month": 1, "payroll_net_amount": 1, "payroll_info": 1, "created_at": 1, "storage_path": 1}
    ).sort("payroll_month", -1).to_list(200)
    return docs


@router.get("/payroll/documents/{user_id}")
async def get_payroll_documents_admin(user_id: str, token: str = Query(...)):
    """Admin gets assigned DATEV payroll PDFs for a user."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    docs = await db.documents.find(
        {"assigned_user_id": user_id, "folder_id": {"$regex": "^lohnabrechnung"}, "is_deleted": False},
        {"_id": 0, "id": 1, "original_filename": 1, "payroll_month": 1, "payroll_net_amount": 1, "payroll_info": 1, "created_at": 1, "storage_path": 1}
    ).sort("payroll_month", -1).to_list(200)
    return docs


@router.get("/payroll/{user_id}")
async def get_payroll(user_id: str, month: str = Query(...), token: str = Query(...)):
    """Calculate payroll for a user for a given month (YYYY-MM)."""
    caller = await _get_user(token)
    if caller.get("role") != "admin" and caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    year_num, month_num = int(month[:4]), int(month[5:7])
    _, days_in_month = monthrange(year_num, month_num)
    date_from = f"{month}-01"
    date_to = f"{month}-{days_in_month:02d}"

    # Get config
    ws = await db.work_schedules.find_one({"user_id": user_id}, {"_id": 0})
    hourly_wage = (ws or {}).get("hourly_wage", 0)
    surcharges = (ws or {}).get("surcharges", {})
    sunday_pct = float(surcharges.get("sunday", 50))
    holiday_pct = float(surcharges.get("holiday", 125))
    special_pct = float(surcharges.get("special_holiday", 150))
    night_pct = float(surcharges.get("night", 25))

    holidays = _get_holidays(year_num)

    # Get time entries for the month
    entries = await db.time_entries.find(
        {"user_id": user_id, "date": {"$gte": date_from, "$lte": date_to}, "clock_out": {"$ne": None}},
        {"_id": 0}
    ).sort("clock_in", 1).to_list(500)

    rows = []
    totals = {"regular_min": 0, "sunday_min": 0, "holiday_min": 0, "special_min": 0, "night_min": 0,
              "regular_wage": 0, "sunday_wage": 0, "holiday_wage": 0, "special_wage": 0, "night_wage": 0}

    for e in entries:
        ci = datetime.fromisoformat(e["clock_in"])
        co = datetime.fromisoformat(e["clock_out"])
        if ci.tzinfo is None:
            ci = ci.replace(tzinfo=timezone.utc)
        if co.tzinfo is None:
            co = co.replace(tzinfo=timezone.utc)
        ci_local = ci.astimezone(BERLIN)
        co_local = co.astimezone(BERLIN)
        total_min = round((co - ci).total_seconds() / 60)
        date_str = ci_local.strftime("%Y-%m-%d")
        weekday = ci_local.weekday()  # 0=Mon, 6=Sun

        night_min = _calc_night_minutes(ci_local, co_local)
        is_holiday = date_str in holidays
        is_special = _is_special_holiday(date_str)
        is_sunday = weekday == 6

        # Determine surcharge category (highest wins for base, night is additive)
        if is_special:
            surcharge_type = "special"
            surcharge_min = total_min
            surcharge_pct = special_pct
        elif is_holiday:
            surcharge_type = "holiday"
            surcharge_min = total_min
            surcharge_pct = holiday_pct
        elif is_sunday:
            surcharge_type = "sunday"
            surcharge_min = total_min
            surcharge_pct = sunday_pct
        else:
            surcharge_type = "regular"
            surcharge_min = total_min
            surcharge_pct = 0

        hours = total_min / 60
        base_wage = round(hours * hourly_wage, 2)
        surcharge_wage = round(base_wage * surcharge_pct / 100, 2)
        night_hours = night_min / 60
        night_wage = round(night_hours * hourly_wage * night_pct / 100, 2)

        row = {
            "date": date_str,
            "weekday": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][weekday],
            "clock_in": ci_local.strftime("%H:%M"),
            "clock_out": co_local.strftime("%H:%M"),
            "total_min": total_min,
            "total_hours": round(hours, 2),
            "surcharge_type": surcharge_type,
            "surcharge_pct": surcharge_pct,
            "night_min": night_min,
            "base_wage": base_wage,
            "surcharge_wage": surcharge_wage,
            "night_wage": night_wage,
            "total_wage": round(base_wage + surcharge_wage + night_wage, 2),
            "holiday_name": holidays.get(date_str, ""),
        }
        rows.append(row)

        totals[f"{surcharge_type}_min"] = totals.get(f"{surcharge_type}_min", 0) + total_min
        totals[f"{surcharge_type}_wage"] = totals.get(f"{surcharge_type}_wage", 0) + surcharge_wage
        totals["regular_min"] += total_min
        totals["regular_wage"] += base_wage
        totals["night_min"] += night_min
        totals["night_wage"] += night_wage

    # Get deductions for the month
    deductions = await db.payroll_deductions.find(
        {"user_id": user_id, "month": month}, {"_id": 0}
    ).to_list(100)
    total_deductions = round(sum(float(d.get("amount", 0)) for d in deductions), 2)

    totals = {k: round(v, 2) for k, v in totals.items()}
    total_gross = round(totals["regular_wage"] + totals["sunday_wage"] + totals["holiday_wage"] + totals["special_wage"] + totals["night_wage"], 2)
    total_net = round(total_gross - total_deductions, 2)

    return {
        "month": month,
        "user_id": user_id,
        "hourly_wage": hourly_wage,
        "surcharges": {"sunday": sunday_pct, "holiday": holiday_pct, "special_holiday": special_pct, "night": night_pct},
        "rows": rows,
        "totals": totals,
        "total_gross": total_gross,
        "deductions": deductions,
        "total_deductions": total_deductions,
        "total_net": total_net,
    }


@router.get("/payroll/{user_id}/csv")
async def get_payroll_csv(user_id: str, month: str = Query(...), token: str = Query(...)):
    """Export payroll as CSV."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")

    payroll = await get_payroll(user_id, month, token)
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "name": 1})
    name = user.get("name", user_id) if user else user_id

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([f"Lohnabrechnung {name} - {month}"])
    writer.writerow([f"Stundenlohn: {payroll['hourly_wage']} EUR"])
    writer.writerow([])
    writer.writerow(["Datum", "Tag", "Beginn", "Ende", "Stunden", "Typ", "Zuschlag %", "Nacht Min.", "Grundlohn", "Zuschlag", "Nachtzuschlag", "Gesamt", "Feiertag"])
    for r in payroll["rows"]:
        writer.writerow([
            r["date"], r["weekday"], r["clock_in"], r["clock_out"],
            f"{r['total_hours']:.2f}", r["surcharge_type"], f"{r['surcharge_pct']}%",
            r["night_min"], f"{r['base_wage']:.2f}", f"{r['surcharge_wage']:.2f}",
            f"{r['night_wage']:.2f}", f"{r['total_wage']:.2f}", r["holiday_name"],
        ])
    writer.writerow([])
    t = payroll["totals"]
    writer.writerow(["Zusammenfassung"])
    writer.writerow(["Grundlohn gesamt", f"{t['regular_wage']:.2f} EUR"])
    writer.writerow(["Sonntagszuschlag", f"{t.get('sunday_wage', 0):.2f} EUR"])
    writer.writerow(["Feiertagszuschlag", f"{t.get('holiday_wage', 0):.2f} EUR"])
    writer.writerow(["Sonderfeiertag", f"{t.get('special_wage', 0):.2f} EUR"])
    writer.writerow(["Nachtzuschlag", f"{t.get('night_wage', 0):.2f} EUR"])
    writer.writerow(["BRUTTO GESAMT", f"{payroll['total_gross']:.2f} EUR"])
    if payroll.get("deductions"):
        writer.writerow([])
        writer.writerow(["Abzüge"])
        for d in payroll["deductions"]:
            writer.writerow([d.get("text", ""), f"-{float(d.get('amount', 0)):.2f} EUR"])
        writer.writerow(["Abzüge gesamt", f"-{payroll['total_deductions']:.2f} EUR"])
    writer.writerow([])
    writer.writerow(["NETTO AUSZAHLUNG", f"{payroll['total_net']:.2f} EUR"])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=lohn_{name}_{month}.csv"}
    )


# ── Payroll Deductions (Abzüge) ──────────────────────────

@router.get("/deductions/{user_id}")
async def get_deductions(user_id: str, month: str = Query(...), token: str = Query(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    items = await db.payroll_deductions.find({"user_id": user_id, "month": month}, {"_id": 0}).to_list(100)
    return items

@router.post("/deductions/{user_id}")
async def add_deduction(user_id: str, token: str = Query(...), data: dict = Body(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    entry = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "month": data.get("month"),
        "text": data.get("text", ""),
        "amount": float(data.get("amount", 0)),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.payroll_deductions.insert_one(entry)
    return {"id": entry["id"], "ok": True}

@router.delete("/deductions/entry/{deduction_id}")
async def delete_deduction(deduction_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    await db.payroll_deductions.delete_one({"id": deduction_id})
    return {"ok": True}


# ── Payroll Releases (Freigabe) ─────────────────

@router.post("/payroll/{user_id}/release")
async def release_payroll(user_id: str, month: str = Query(...), token: str = Query(...)):
    """Admin releases (saves) a payroll for a specific month."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    # Calculate payroll snapshot
    payroll_data = await get_payroll(user_id, month, token)
    # Check if already released
    existing = await db.payroll_releases.find_one({"user_id": user_id, "month": month})
    entry = {
        "user_id": user_id,
        "month": month,
        "payroll_data": payroll_data,
        "released_by": caller["id"],
        "released_by_name": caller.get("name", ""),
        "released_at": datetime.now(timezone.utc).isoformat(),
    }
    if existing:
        await db.payroll_releases.update_one({"user_id": user_id, "month": month}, {"$set": entry})
    else:
        entry["id"] = str(uuid.uuid4())
        await db.payroll_releases.insert_one(entry)
    return {"ok": True, "month": month}


@router.get("/payroll/{user_id}/releases")
async def get_payroll_releases(user_id: str, token: str = Query(...)):
    """Get all released payrolls for a user. Admins see all, employees see own."""
    caller = await _get_user(token)
    target_id = user_id if caller.get("role") == "admin" else caller["id"]
    releases = await db.payroll_releases.find({"user_id": target_id}, {"_id": 0}).sort("month", -1).to_list(200)
    return releases


# ── Employee Notes (Mitarbeiter-Notizen) ─────────────────

@router.get("/notes/{user_id}")
async def get_notes(user_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    notes = await db.employee_notes.find({"user_id": user_id, "deleted": {"$ne": True}}, {"_id": 0}).sort("date", -1).to_list(500)
    return notes

@router.post("/notes/{user_id}")
async def create_note(user_id: str, token: str = Query(...), data: dict = Body(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    note = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": data.get("title", ""),
        "text": data.get("text", ""),
        "date": data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        "created_by": caller["id"],
        "created_by_name": caller.get("name", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "files": [],
    }
    await db.employee_notes.insert_one(note)
    return {"id": note["id"], "ok": True}

@router.put("/notes/entry/{note_id}")
async def update_note(note_id: str, token: str = Query(...), data: dict = Body(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for key in ("title", "text", "date"):
        if key in data:
            updates[key] = data[key]
    await db.employee_notes.update_one({"id": note_id}, {"$set": updates})
    return {"ok": True}

@router.delete("/notes/entry/{note_id}")
async def delete_note(note_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    await db.employee_notes.update_one({"id": note_id}, {"$set": {"deleted": True}})
    return {"ok": True}

@router.post("/notes/entry/{note_id}/upload")
async def upload_note_file(note_id: str, token: str = Query(...), file: UploadFile = File(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    note = await db.employee_notes.find_one({"id": note_id})
    if not note:
        raise HTTPException(status_code=404, detail="Notiz nicht gefunden")

    file_bytes = await file.read()
    file_id = str(uuid.uuid4())
    storage_path = f"employee-notes/{note['user_id']}/{note_id}/{file_id}_{file.filename}"
    put_obj, _ = _get_storage_fns()
    put_obj(storage_path, file_bytes, file.content_type or "application/octet-stream")

    file_meta = {
        "id": file_id,
        "filename": file.filename,
        "content_type": file.content_type or "application/octet-stream",
        "size": len(file_bytes),
        "storage_path": storage_path,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.employee_notes.update_one({"id": note_id}, {"$push": {"files": file_meta}})
    return file_meta

@router.get("/notes/files/{note_id}/{file_id}")
async def download_note_file(note_id: str, file_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    note = await db.employee_notes.find_one({"id": note_id})
    if not note:
        raise HTTPException(status_code=404, detail="Notiz nicht gefunden")
    file_meta = next((f for f in note.get("files", []) if f["id"] == file_id), None)
    if not file_meta:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    _, get_obj = _get_storage_fns()
    result = get_obj(file_meta["storage_path"])
    if not result:
        raise HTTPException(status_code=404, detail="Datei nicht im Storage")
    data, ct = result
    return Response(content=data, media_type=ct or file_meta["content_type"],
                    headers={"Content-Disposition": f"inline; filename=\"{file_meta['filename']}\""})

@router.delete("/notes/files/{note_id}/{file_id}")
async def delete_note_file(note_id: str, file_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    await db.employee_notes.update_one({"id": note_id}, {"$pull": {"files": {"id": file_id}}})
    return {"ok": True}



# ── FAQ ─────────────────

DEFAULT_FAQ_CATEGORIES = ["Allgemein", "Arbeitszeit", "Urlaub & Krankheit", "Abrechnung", "Technik", "Sicherheit"]

FAQ_SEED_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "faqs_seed.json")


async def seed_faqs_from_file(force: bool = False) -> dict:
    """Seed FAQs from /app/backend/data/faqs_seed.json. Idempotent (by id).
    - force=False: only inserts FAQs whose id doesn't exist yet
    - force=True: deletes all non-deleted FAQs first, then inserts seed set
    Returns counts {inserted, skipped, deleted}."""
    import json as _json
    if not os.path.exists(FAQ_SEED_FILE):
        return {"inserted": 0, "skipped": 0, "deleted": 0, "error": "seed_file_missing"}
    try:
        with open(FAQ_SEED_FILE, "r", encoding="utf-8") as f:
            seed = _json.load(f)
    except Exception as e:
        return {"inserted": 0, "skipped": 0, "deleted": 0, "error": f"parse_error: {e}"}

    deleted = 0
    if force:
        res = await db.faqs.delete_many({})
        deleted = res.deleted_count

    inserted = 0
    skipped = 0
    for doc in seed:
        if not isinstance(doc, dict) or not doc.get("id") or not doc.get("question"):
            skipped += 1
            continue
        existing = await db.faqs.find_one({"id": doc["id"]}, {"_id": 0, "id": 1})
        if existing and not force:
            skipped += 1
            continue
        # Ensure required fields
        doc.setdefault("deleted", False)
        doc.setdefault("order", 0)
        doc.setdefault("category", "Allgemein")
        await db.faqs.insert_one(doc)
        inserted += 1
    return {"inserted": inserted, "skipped": skipped, "deleted": deleted}


async def auto_seed_faqs_if_empty():
    """Called on server startup: if faqs collection is empty, seed from file."""
    try:
        count = await db.faqs.count_documents({})
        if count == 0:
            res = await seed_faqs_from_file(force=False)
            import logging as _l
            _l.getLogger(__name__).info(f"[FAQ] Auto-seeded on startup: {res}")
    except Exception as e:
        import logging as _l
        _l.getLogger(__name__).warning(f"[FAQ] Auto-seed failed: {e}")


@router.post("/faq/seed-defaults")
async def trigger_faq_seed(token: str = Query(...), force: int = 0):
    """Admin: Seed FAQs aus /app/backend/data/faqs_seed.json.
    - force=0: nur fehlende hinzufuegen (idempotent)
    - force=1: alle loeschen und neu seeden"""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    res = await seed_faqs_from_file(force=bool(force))
    if res.get("error"):
        raise HTTPException(status_code=500, detail=res["error"])
    return res


@router.get("/faq")
async def list_faqs(token: str = Query(...), q: str = Query("")):
    """Alle FAQs (alle authentifizierten User). Optional Volltextsuche via q."""
    await _get_user(token)
    query = {"deleted": {"$ne": True}}
    if q:
        import re
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"question": rx}, {"answer": rx}, {"category": rx}]
    faqs = await db.faqs.find(query, {"_id": 0}).sort([("category", 1), ("order", 1), ("created_at", 1)]).to_list(500)
    return {"faqs": faqs, "categories": DEFAULT_FAQ_CATEGORIES}


@router.post("/faq")
async def create_faq(token: str = Query(...), data: dict = Body(...)):
    """Admin: Neue FAQ anlegen."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    question = (data.get("question") or "").strip()
    answer = (data.get("answer") or "").strip()
    category = (data.get("category") or "Allgemein").strip() or "Allgemein"
    if not question or not answer:
        raise HTTPException(status_code=400, detail="Frage und Antwort erforderlich")
    now_iso = datetime.now(timezone.utc).isoformat()
    last = await db.faqs.find({"category": category, "deleted": {"$ne": True}}, {"_id": 0, "order": 1}).sort("order", -1).limit(1).to_list(1)
    next_order = (last[0].get("order", 0) + 1) if last else 1
    doc = {
        "id": str(uuid.uuid4()),
        "question": question,
        "answer": answer,
        "category": category,
        "order": next_order,
        "author_id": caller["id"],
        "author_name": caller.get("name", caller.get("email", "")),
        "created_at": now_iso,
        "updated_at": now_iso,
        "deleted": False,
    }
    await db.faqs.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/faq/{faq_id}")
async def update_faq(faq_id: str, token: str = Query(...), data: dict = Body(...)):
    """Admin: FAQ aktualisieren (Frage, Antwort, Kategorie, Reihenfolge)."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for k in ("question", "answer", "category"):
        if k in data:
            v = (data.get(k) or "").strip()
            if not v:
                raise HTTPException(status_code=400, detail=f"{k} darf nicht leer sein")
            update[k] = v
    if "order" in data:
        try:
            update["order"] = int(data["order"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="order muss eine Zahl sein")
    res = await db.faqs.update_one({"id": faq_id, "deleted": {"$ne": True}}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="FAQ nicht gefunden")
    doc = await db.faqs.find_one({"id": faq_id}, {"_id": 0})
    return doc


@router.delete("/faq/{faq_id}")
async def delete_faq(faq_id: str, token: str = Query(...)):
    """Admin: FAQ loeschen (Soft-Delete)."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    res = await db.faqs.update_one(
        {"id": faq_id},
        {"$set": {"deleted": True, "deleted_at": datetime.now(timezone.utc).isoformat()}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="FAQ nicht gefunden")
    return {"ok": True}



# ── Einsatzplanung (Shift Planning) ─────────────────

@router.get("/shift-plan")
async def get_shift_plan(week: str = Query(...), token: str = Query(...)):
    """Admin: Get all assignments for a week (e.g. '2026-W15')."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    assignments = await db.shift_assignments.find({"week_key": week}, {"_id": 0}).to_list(1000)
    # Get release status
    release = await db.shift_releases.find_one({"week_key": week}, {"_id": 0})
    # Get all absences (time_off_requests approved) overlapping this week
    import re
    m = re.match(r"(\d{4})-W(\d{2})", week)
    absences = []
    if m:
        year, wk = int(m.group(1)), int(m.group(2))
        from datetime import timedelta
        monday = datetime.strptime(f"{year}-W{wk:02d}-1", "%Y-W%W-%w").date()
        sunday = monday + timedelta(days=6)
        mon_str = monday.isoformat()
        sun_str = sunday.isoformat()
        reqs = await db.time_off_requests.find({
            "status": "approved",
            "date_from": {"$lte": sun_str},
            "date_to": {"$gte": mon_str},
        }, {"_id": 0}).to_list(500)
        absences = reqs
    return {
        "assignments": assignments,
        "released": bool(release),
        "released_at": release.get("released_at") if release else None,
        "absences": absences,
    }


@router.post("/shift-plan")
async def upsert_shift_assignment(data: dict = Body(...), token: str = Query(...)):
    """Admin: Create or update a shift assignment."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    assignment_id = data.get("id")
    if assignment_id:
        await db.shift_assignments.update_one({"id": assignment_id}, {"$set": {
            "user_id": data.get("user_id"),
            "date": data.get("date"),
            "order_pk": data.get("order_pk"),
            "order_name": data.get("order_name", ""),
            "role": data.get("role", ""),
            "note": data.get("note", ""),
            "start_time": data.get("start_time", ""),
            "end_time": data.get("end_time", ""),
            "week_key": data.get("week_key"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})
    else:
        assignment_id = str(uuid.uuid4())
        await db.shift_assignments.insert_one({
            "id": assignment_id,
            "user_id": data.get("user_id"),
            "date": data.get("date"),
            "order_pk": data.get("order_pk"),
            "order_name": data.get("order_name", ""),
            "role": data.get("role", ""),
            "note": data.get("note", ""),
            "start_time": data.get("start_time", ""),
            "end_time": data.get("end_time", ""),
            "week_key": data.get("week_key"),
            "created_by": caller["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    return {"ok": True, "id": assignment_id}


@router.delete("/shift-plan/{assignment_id}")
async def delete_shift_assignment(assignment_id: str, token: str = Query(...)):
    """Admin: Delete a shift assignment."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    await db.shift_assignments.delete_one({"id": assignment_id})
    return {"ok": True}


@router.get("/shift-plan/job-reqs")
async def get_job_reqs(week: str = Query(...), token: str = Query(...)):
    """Get job personnel requirements for a week."""
    await _get_user(token)
    reqs = await db.shift_job_reqs.find({"week_key": week}, {"_id": 0}).to_list(500)
    return reqs


@router.post("/shift-plan/job-reqs")
async def upsert_job_req(data: dict = Body(...), token: str = Query(...)):
    """Admin: Set personnel requirements for a job in a week."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    order_pk = data.get("order_pk")
    week_key = data.get("week_key")
    existing = await db.shift_job_reqs.find_one({"order_pk": order_pk, "week_key": week_key})
    entry = {
        "order_pk": order_pk, "week_key": week_key,
        "count": data.get("count", 1), "roles": data.get("roles", ""),
    }
    if existing:
        await db.shift_job_reqs.update_one({"order_pk": order_pk, "week_key": week_key}, {"$set": entry})
    else:
        entry["id"] = str(uuid.uuid4())
        await db.shift_job_reqs.insert_one(entry)
    return {"ok": True}


@router.post("/shift-plan/release")
async def release_shift_plan(week: str = Query(...), token: str = Query(...)):
    """Admin: Release a week plan so employees can see it."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    await db.shift_releases.update_one({"week_key": week}, {"$set": {
        "week_key": week,
        "released_by": caller["id"],
        "released_at": datetime.now(timezone.utc).isoformat(),
    }}, upsert=True)
    return {"ok": True}


@router.get("/shift-plan/my-plan")
async def get_my_shift_plan(token: str = Query(...)):
    """Employee: Get own released shift assignments for current + next week."""
    caller = await _get_user(token)
    from datetime import timedelta
    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())
    current_week = monday.strftime("%G-W%V")
    next_monday = monday + timedelta(days=7)
    next_week = next_monday.strftime("%G-W%V")
    # Only show released weeks
    released_weeks = []
    async for r in db.shift_releases.find({"week_key": {"$in": [current_week, next_week]}}, {"_id": 0}):
        released_weeks.append(r["week_key"])
    assignments = await db.shift_assignments.find({
        "user_id": caller["id"],
        "week_key": {"$in": released_weeks},
    }, {"_id": 0}).sort("date", 1).to_list(100)
    return {"assignments": assignments, "released_weeks": released_weeks}
