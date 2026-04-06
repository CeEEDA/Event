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

    # Store file
    put_obj, _ = _get_storage_fns()
    put_obj(storage_path, file_bytes, file.content_type or "application/pdf")

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
    """Download a document file."""
    caller = await _get_user(token)
    doc = await db.employee_documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if caller.get("role") != "admin" and caller["id"] != doc["user_id"]:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    try:
        _, get_obj = _get_storage_fns()
        result = get_obj(doc["storage_path"])
        data = result[0] if isinstance(result, tuple) else result
        return Response(
            content=data,
            media_type=doc.get("content_type", "application/pdf"),
            headers={"Content-Disposition": f'inline; filename="{doc["filename"]}"'}
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")


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
    """Admin: get all currently clocked-in employees."""
    caller = await _get_user(token)
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    entries = await db.time_entries.find({"clock_out": None}, {"_id": 0}).to_list(500)
    return [{"user_id": e["user_id"], "user_name": e.get("user_name", ""), "clock_in": e["clock_in"]} for e in entries]


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
    """Clock out with GPS coordinates."""
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

    return list(by_user.values())



# ─── HR Data (Overtime / Vacation) ──────────────────────────────

@router.get("/hr-data/{user_id}")
async def get_hr_data(user_id: str, token: str = Query(...)):
    """Get HR data (overtime, vacation) for a user. Admins get full data, employees only their own."""
    caller = await _get_user(token)
    if caller.get("role") != "admin" and caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    year = datetime.now(timezone.utc).year
    doc = await db.hr_data.find_one({"user_id": user_id, "year": year}, {"_id": 0})
    if not doc:
        doc = {"user_id": user_id, "year": year, "overtime_hours": 0, "vacation_days_total": 0, "vacation_days_used": 0}

    remaining = (doc.get("vacation_days_total") or 0) - (doc.get("vacation_days_used") or 0)
    doc["vacation_days_remaining"] = remaining
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

    doc = await db.hr_data.find_one({"user_id": user_id, "year": year}, {"_id": 0})
    remaining = (doc.get("vacation_days_total") or 0) - (doc.get("vacation_days_used") or 0)
    doc["vacation_days_remaining"] = remaining
    return doc



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



# ─── Time Off Requests ──────────────────────────────

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
    if caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")

    status = data.get("status")  # approved, rejected
    if status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Status muss 'approved' oder 'rejected' sein")

    req = await db.time_off_requests.find_one({"id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="Antrag nicht gefunden")

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
        status_label = "Genehmigt" if status == "approved" else "Abgelehnt"
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

    year = entry.get("year", datetime.now(timezone.utc).year)
    await db.vacation_entries.delete_one({"id": entry_id})
    await _recalc_vacation_used(user_id, year)
    return {"ok": True}
