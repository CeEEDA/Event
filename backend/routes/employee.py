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
    "adr_karte",
    "kranschein",
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
    "adr_karte": "ADR-Karte",
    "kranschein": "Kranschein",
}


def _has_verwaltung(caller: dict) -> bool:
    """Admin oder Mitarbeiter mit aktivem Hub-Kachel-Toggle 'verwaltung'.
    Wird fuer admin-aehnliche Read-Endpoints in der Verwaltung verwendet."""
    if not caller:
        return False
    if caller.get("role") == "admin":
        return True
    if caller.get("role") == "mitarbeiter":
        modules = (caller.get("apps") or {}).get("modules") or {}
        return modules.get("verwaltung") is not False
    return False


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


# ==================== AUDIT LOG ====================
# Protokolliert manuelle Aenderungen an HR-/Zeit-/Urlaubsdaten eines
# Mitarbeiters. Wird in der Zeiterfassungs-Detailansicht angezeigt.

async def _log_audit(
    target_user_id: str,
    action: str,
    caller: dict,
    *,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    summary: str = "",
    details: Optional[dict] = None,
):
    """Schreibt einen Audit-Eintrag ins time_audit_log.

    action: kurzer Identifier wie 'time_manual_create', 'time_edit',
            'time_delete', 'vacation_add', 'vacation_delete',
            'time_off_admin_create', 'time_off_delete', 'hr_data_update',
            'work_schedule_update', 'deduction_add', 'deduction_delete',
            'payroll_release'
    summary: menschenlesbarer Text fuer die Liste (z.B. "Urlaub 01.06.-05.06. hinzugefuegt")
    """
    try:
        entry = {
            "id": str(uuid.uuid4()),
            "target_user_id": target_user_id,
            "action": action,
            "performed_by_user_id": (caller or {}).get("id"),
            "performed_by_name": (caller or {}).get("name") or (caller or {}).get("email") or "?",
            "performed_by_role": (caller or {}).get("role"),
            "summary": summary,
            "before": before,
            "after": after,
            "details": details or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.time_audit_log.insert_one(entry)
    except Exception as ex:
        # Audit-Fehler nicht weiterreichen - der eigentliche Schreibvorgang soll
        # nicht scheitern nur weil Logging klemmt.
        logger.warning(f"Audit-Log Fehler: {ex}")


@router.get("/audit-log/{user_id}")
async def get_audit_log(user_id: str, token: str = Query(...), limit: int = 200):
    """Liefert das Audit-Log eines Mitarbeiters (manuelle Aenderungen an Zeit/HR/Urlaub).

    Nur fuer Verwaltung sichtbar (Admin oder Mitarbeiter mit Verwaltungs-App).
    """
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    rows = await db.time_audit_log.find(
        {"target_user_id": user_id}, {"_id": 0}
    ).sort([("created_at", -1)]).to_list(int(limit))
    return {"total": len(rows), "entries": rows}



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
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")

    users = await db.users.find({}, {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1}).to_list(500)
    result = []
    for u in users:
        # Freelancer gehoeren nicht in die Mitarbeiter-Liste (eigene Vertragsart).
        if (u.get("role") or "").lower() == "freelancer":
            continue
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
    if not _has_verwaltung(caller) and caller["id"] != user_id:
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
async def change_password(token: str = Query(...), body: dict | None = None):
    """Change own password."""
    body = body or {}
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
    if not _has_verwaltung(caller):
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
    """Get all documents for a user. Admins/Verwaltung can view other users' docs."""
    caller = await _get_user(token)
    target_id = user_id if user_id and _has_verwaltung(caller) else caller["id"]

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
    target_id = user_id if user_id and _has_verwaltung(caller) else caller["id"]

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
async def update_document(doc_id: str, token: str = Query(...), body: dict | None = None):
    """Update expiry date manually."""
    body = body or {}
    caller = await _get_user(token)
    doc = await db.employee_documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if not _has_verwaltung(caller) and caller["id"] != doc["user_id"]:
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
    if not _has_verwaltung(caller) and caller["id"] != doc["user_id"]:
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
        headers={"Content-Disposition": content_disposition(doc["filename"], "inline")}
    )


@router.get("/document-types")
async def get_document_types(token: str = Query(...)):
    """Get list of all document types with labels."""
    await _get_user(token)
    return [{"key": k, "label": v} for k, v in DOCUMENT_LABELS.items()]


@router.get("/report/expiry")
async def get_expiry_report(token: str = Query(...)):
    """Admin/Verwaltung: Get report of all document expiry dates across all employees."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Verwaltungs-Berechtigung erforderlich")

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
    """Admin/Verwaltung: get all employees with their current clock-in status (anwesend / abwesend)."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Verwaltungs-Berechtigung erforderlich")
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
async def clock_in(token: str = Query(...), body: dict | None = None):
    """Clock in with GPS coordinates."""
    body = body or {}
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
    # Offday-Konto: Sonntag oder RLP-Feiertag automatisch +1 (idempotent
    # pro user_id + date, siehe routes/offdays.py).
    try:
        from routes.offdays import grant_offday_for_work
        await grant_offday_for_work(user["id"], user.get("name", ""), entry["date"])
    except Exception as _e:
        logger.warning(f"Offday-Accrual fehlgeschlagen fuer {user.get('email')}: {_e}")
    created = await db.time_entries.find_one({"id": entry["id"]}, {"_id": 0})
    return created


# ── Pausen-Helper: subtract configured break from raw duration ──
_WEEKDAY_MAP = {0: "montag", 1: "dienstag", 2: "mittwoch", 3: "donnerstag", 4: "freitag", 5: "samstag", 6: "sonntag"}


async def _get_break_min_for_date(user_id: str, date_str: str) -> int:
    """Return configured break_min for the user's weekday schedule, 0 if none."""
    if not date_str:
        return 0
    try:
        from datetime import date as _date
        wd = _date.fromisoformat(date_str).weekday()
    except Exception:
        return 0
    day_name = _WEEKDAY_MAP.get(wd)
    if not day_name:
        return 0
    schedule = await db.work_schedules.find_one({"user_id": user_id}, {"_id": 0})
    day_sched = (schedule or {}).get("days", {}).get(day_name, {}) or {}
    try:
        return int(day_sched.get("break_min") or 0)
    except Exception:
        return 0


def _apply_break_deduction(raw_minutes: float, break_min: int) -> float:
    """Subtract break only if the worked duration is longer than the break itself
    (prevents negative durations for very short shifts)."""
    if break_min and break_min > 0 and raw_minutes > break_min:
        return raw_minutes - break_min
    return raw_minutes


def _legal_minimum_break(raw_minutes: float) -> int:
    """Gesetzliche Mindestpause nach §4 ArbZG basierend auf Anwesenheit.
    - Anwesenheit <= 6h:        0 min  (keine Pflichtpause)
    - 6h < Anwesenheit <= 9h30m: 30 min (Arbeitszeit > 6h, <= 9h)
    - Anwesenheit > 9h30m:       45 min (Arbeitszeit > 9h)
    Die Schwelle 9h30m ergibt sich aus 9h Arbeit + 30 min Mindestpause.
    """
    if raw_minutes is None or raw_minutes <= 360:    # <= 6h
        return 0
    if raw_minutes <= 570:                            # <= 9h30m
        return 30
    return 45


def _enforce_legal_break_minimum(raw_minutes: float, planned_break_min: int) -> int:
    """Pausen-Logik nach §4 ArbZG + Wochenplan:
    - Anwesenheit <= 6h: KEINE Pause abziehen, auch wenn der Wochenplan
      eine Pause vorsieht. (Bei einem kurzen Dienst von z.B. 5h wird die
      geplante Mittagspause typisch nicht genommen, daher kein Abzug.)
    - Anwesenheit > 6h:  max(geplante Pause, gesetzliche Mindestpause).
      Laengere Pausen aus dem Wochenplan (z.B. 60 min Mittag) bleiben
      unangetastet, kuerzere werden auf 30/45 hochgesetzt."""
    legal = _legal_minimum_break(raw_minutes)
    if legal == 0:
        # Kurzer Dienst (<= 6h) -> keine Pflichtpause + kein Plan-Abzug
        return 0
    try:
        planned = int(planned_break_min or 0)
    except (TypeError, ValueError):
        planned = 0
    return max(planned, legal)


async def _soll_minutes_for_weekday(user_id: str, weekday: int) -> int:
    """Berechne die Sollarbeitszeit (Minuten) eines Wochentags aus dem Wochenplan.
    Bevorzugt 'soll_hours', faellt zurueck auf start/end-Spanne minus break."""
    day_name = _WEEKDAY_MAP.get(weekday)
    if not day_name:
        return 0
    schedule = await db.work_schedules.find_one({"user_id": user_id}, {"_id": 0})
    day_sched = (schedule or {}).get("days", {}).get(day_name, {}) or {}
    if not day_sched:
        return 0
    try:
        sh_field = day_sched.get("soll_hours")
        if sh_field not in (None, ""):
            return int(round(float(sh_field) * 60))
        if day_sched.get("start") and day_sched.get("end"):
            sh, sm = map(int, day_sched["start"].split(":"))
            eh, em = map(int, day_sched["end"].split(":"))
            sched_break = int(day_sched.get("break_min") or 0)
            return max(0, (eh * 60 + em) - (sh * 60 + sm) - sched_break)
    except (ValueError, TypeError):
        return 0
    return 0


def _soll_minutes_from_schedule(schedule: dict, weekday: int) -> int:
    """Synchrone Variante von _soll_minutes_for_weekday — nimmt schedule als Param.
    Sinn: bei Tag-fuer-Tag-Bilanzierung soll der Wochenplan NICHT in jeder
    Iteration aus der DB nachgeladen werden."""
    day_name = _WEEKDAY_MAP.get(weekday)
    if not day_name or not schedule:
        return 0
    day_sched = (schedule.get("days") or {}).get(day_name, {}) or {}
    if not day_sched:
        return 0
    try:
        sh_field = day_sched.get("soll_hours")
        if sh_field not in (None, ""):
            return int(round(float(sh_field) * 60))
        if day_sched.get("start") and day_sched.get("end"):
            sh, sm = map(int, day_sched["start"].split(":"))
            eh, em = map(int, day_sched["end"].split(":"))
            sched_break = int(day_sched.get("break_min") or 0)
            return max(0, (eh * 60 + em) - (sh * 60 + sm) - sched_break)
    except (ValueError, TypeError):
        return 0
    return 0


async def _recompute_overtime_for_year(user_id: str, year: int, *, audit_caller: Optional[dict] = None) -> float:
    """Berechne Ueberstunden eines Jahres aus Baseline + Tag-fuer-Tag-Bilanz.

    Pattern:
      overtime_hours = overtime_baseline + sum(ist_tag - soll_tag fuer alle vergangenen Plan-Tage)
                       - sum(hours_deducted aus genehmigten ueberstundenabbau-Antraegen)

    WICHTIG: Tag-fuer-Tag, NICHT pro time_entry. Soll wird PRO TAG einmal abgezogen,
    Ist ist die SUMME aller Stempel-Eintraege des Tages. Damit funktioniert auch
    der Fall „8-18 Uhr + 20:30-21:45" korrekt (Soll 8.5h einmal, Ist 9.25+1.25=10.5h,
    Diff = +2.0h und nicht -7.25h).

    Tage GANZ OHNE Stempel werden mit Ist=0 verrechnet -> Minus, sofern es ein
    Plan-Arbeitstag ohne Feiertag/Urlaub/Krank/Ueberstundenabbau ist.

    Audit-Log:
      - Jeder NEU automatisch verbuchte Tag wird einmalig detailliert geloggt
        (action='auto_balance_day') und beim naechsten Recompute uebersprungen.
      - Am Ende jedes Recompute eine Zusammenfassung (action='auto_balance_recompute').
    """
    from datetime import date as _date, timedelta
    hr = await db.hr_data.find_one({"user_id": user_id, "year": year}, {"_id": 0}) or {}

    today = datetime.now(timezone.utc).date()
    year_start = _date(year, 1, 1)
    year_end = _date(year, 12, 31)
    end_day = min(today, year_end)

    # Wenn Admin die Ueberstunden manuell gesetzt hat, ist alles VOR diesem
    # Datum bereits in der baseline enthalten. Der Recompute darf ausschliesslich
    # Tage AB diesem Datum ein weiteres Mal in die diff-Berechnung einbeziehen -
    # sonst werden bereits gebuchte Stunden ein zweites Mal aufaddiert.
    range_start = year_start
    reason = (hr.get("overtime_baseline_reason") or "").lower()
    if reason.startswith("admin-manuell") and hr.get("overtime_baseline_set_at"):
        try:
            _bset = datetime.fromisoformat(hr["overtime_baseline_set_at"])
            if _bset.tzinfo is None:
                _bset = _bset.replace(tzinfo=timezone.utc)
            # Ab Folge-Tag rechnen - der Tag der Baseline-Setzung ist mit
            # inbegriffen, damit die manuelle Korrektur bis Ende dieses Tages gilt
            _bset_date = _bset.astimezone(timezone.utc).date()
            if _bset_date > year_start:
                range_start = _bset_date + timedelta(days=1)
        except (ValueError, TypeError):
            pass

    # 1) Feiertage (RLP)
    holidays = set(_get_holidays(year).keys())

    # 2) Urlaub/Krank/Abbau-Tage aus time_off_requests
    off_days: set = set()
    abbau_days: set = set()
    offday_days: set = set()  # Ausgleichstage aus shift_assignments (is_offday)
    off_cursor = db.time_off_requests.find({
        "user_id": user_id, "status": "approved",
        "type": {"$in": ["urlaub", "krank", "ueberstundenabbau"]},
    }, {"_id": 0, "type": 1, "start_date": 1, "end_date": 1, "all_day": 1})
    async for r in off_cursor:
        try:
            s = _date.fromisoformat(r["start_date"])
            e = _date.fromisoformat(r["end_date"])
        except (KeyError, ValueError, TypeError):
            continue
        target = abbau_days if (r.get("type") or "").lower() == "ueberstundenabbau" else off_days
        cur = s
        while cur <= e:
            if cur.year == year:
                target.add(cur.isoformat())
            cur += timedelta(days=1)

    # 2b) Offdays aus der Einsatzplanung (shift_assignments mit is_offday=True).
    # Ein Offday ist ein bezahlter Ersatzruhetag - der MA arbeitet nicht,
    # aber das Soll fuer diesen Tag entfaellt komplett (genauso wie Urlaub).
    off_cur2 = db.shift_assignments.find({
        "user_id": user_id, "is_offday": True,
        "date": {"$regex": f"^{year}-"},
    }, {"_id": 0, "date": 1})
    async for r in off_cur2:
        d = r.get("date")
        if d:
            offday_days.add(d)

    # 3) time_entries aggregiert pro Tag (Echtarbeit, keine Urlaub-Pseudo-Eintraege)
    #    + Erkennung von Nachtschicht-Folgetagen (Schicht über Mitternacht).
    import zoneinfo as _zi
    _berlin = _zi.ZoneInfo("Europe/Berlin")
    ist_by_day: dict = {}
    night_followup_days: set = set()  # Tage, an denen eine Nachtschicht vom Vortag endet
    cursor = db.time_entries.find(
        {"user_id": user_id, "date": {"$regex": f"^{year}-"}, "duration_minutes": {"$ne": None}},
        {"_id": 0, "date": 1, "duration_minutes": 1, "type": 1, "clock_in": 1, "clock_out": 1}
    )
    async for e in cursor:
        if (e.get("type") or "").lower() in ("urlaub", "krank", "ueberstundenabbau", "feiertag"):
            continue
        d = e.get("date")
        if not d:
            continue
        ist_by_day[d] = ist_by_day.get(d, 0.0) + float(e.get("duration_minutes") or 0)
        # Schicht über Mitternacht?
        ci_str, co_str = e.get("clock_in"), e.get("clock_out")
        if ci_str and co_str:
            try:
                ci_dt = datetime.fromisoformat(ci_str); co_dt = datetime.fromisoformat(co_str)
                if ci_dt.tzinfo is None: ci_dt = ci_dt.replace(tzinfo=timezone.utc)
                if co_dt.tzinfo is None: co_dt = co_dt.replace(tzinfo=timezone.utc)
                ci_date = ci_dt.astimezone(_berlin).date()
                co_date = co_dt.astimezone(_berlin).date()
                if ci_date < co_date:
                    cur_d = ci_date + timedelta(days=1)
                    while cur_d <= co_date:
                        if cur_d.year == year:
                            night_followup_days.add(cur_d.isoformat())
                        cur_d += timedelta(days=1)
            except (ValueError, TypeError):
                pass

    # 4) Wochenplan einmal laden
    schedule = await db.work_schedules.find_one({"user_id": user_id}, {"_id": 0})
    has_schedule = bool(schedule and (schedule.get("days") or {}))

    # 5) Tag-fuer-Tag-Bilanz
    total_diff_minutes = 0.0
    plus_days = 0
    minus_days = 0
    plus_minutes = 0.0
    minus_minutes = 0.0
    new_detail_logs: list = []  # NEU zu loggende Tage
    cur = range_start
    while cur <= end_day:
        date_str = cur.isoformat()
        ist = ist_by_day.get(date_str, 0.0)
        soll = 0
        reason = ""
        if date_str in holidays:
            reason = "Feiertag (" + _get_holidays(year).get(date_str, "?") + ")"
        elif date_str in off_days:
            reason = "Urlaub/Krank"
        elif date_str in abbau_days:
            reason = "Überstundenabbau"
        elif date_str in offday_days:
            # Ersatzruhetag (Offday) - bezahlter freier Tag, KEIN Soll abziehen.
            reason = "Offday (Ausgleichstag)"
        elif date_str in night_followup_days and ist == 0:
            # Tag X+1 nach einer Nachtschicht (Vortag 22:30 -> 08:10 heute).
            # Die Arbeitszeit wurde bereits auf den Schicht-Start-Tag gebucht.
            # Daher hier KEIN Soll abziehen, sonst gibt's Minus für nicht geleistete Arbeit.
            reason = "Nachtschicht-Folgetag"
        elif has_schedule:
            soll = _soll_minutes_from_schedule(schedule, cur.weekday())
        diff = ist - soll
        if diff > 0.5:
            plus_days += 1; plus_minutes += diff
        elif diff < -0.5:
            minus_days += 1; minus_minutes += abs(diff)
            # Detail-Eintrag fuer Minus-Tage merken (Plus-Tage logge ich nicht
            # einzeln — sonst Spam)
            new_detail_logs.append({
                "date": date_str, "soll_min": soll, "ist_min": ist, "diff_min": diff,
                "reason": reason or ("Kein Stempel" if soll > 0 else "")
            })
        total_diff_minutes += diff
        cur += timedelta(days=1)

    diff_hours = round(total_diff_minutes / 60.0, 2)

    # 6) Genehmigte ueberstundenabbau-Antraege (alt: aus absences-Collection)
    # WICHTIG: ab range_start filtern - alles davor ist bereits in der baseline
    _abs_query = {
        "user_id": user_id, "type": "ueberstundenabbau", "status": "approved",
        "date": {"$regex": f"^{year}-"},
    }
    if range_start > _date(year, 1, 1):
        _abs_query["date"] = {"$gte": range_start.isoformat(), "$regex": f"^{year}-"}
    abs_cursor = db.absences.find(_abs_query, {"_id": 0, "hours_deducted": 1, "date": 1})
    deduction = 0.0
    async for a in abs_cursor:
        # Doppelter Sicherheitsfilter falls Regex+gte kombiniert nicht wirkt
        try:
            d = a.get("date")
            if d and _date.fromisoformat(d) < range_start:
                continue
            deduction += float(a.get("hours_deducted") or 0)
        except (TypeError, ValueError):
            continue

    # 7) Baseline – falls noch nicht gesetzt, rueckwaerts so berechnen dass
    # der aktuell angezeigte Wert ERHALTEN bleibt (Migration ohne Sprung).
    # ZUSAETZLICHE V2-MIGRATION: Der Recompute war frueher pro-time_entry und
    # hat Tage ohne Stempel nicht beruecksichtigt. Mit dem neuen Tag-fuer-Tag-
    # Algorithmus aendert sich diff_hours u.U. massiv (Minus-Tage tauchen auf).
    # Damit existierende Konten KEINEN ploetzlichen Sprung erhalten, setzen wir
    # die Baseline beim ersten Recompute nach dem Update so neu, dass der
    # angezeigte Saldo gleich bleibt. Ab dann werden NEUE Tage normal verbucht.
    baseline = hr.get("overtime_baseline")
    needs_v2_migration = bool(hr) and not hr.get("overtime_baseline_v2_migrated")
    if baseline is None:
        current_total = float(hr.get("overtime_hours") or 0)
        baseline = round(current_total - diff_hours + deduction, 2)
        await db.hr_data.update_one(
            {"user_id": user_id, "year": year},
            {"$set": {"overtime_baseline": baseline,
                       "overtime_baseline_set_at": datetime.now(timezone.utc).isoformat(),
                       "overtime_baseline_reason": "auto-migration: erhalten was vorher im overtime_hours stand",
                       "overtime_baseline_v2_migrated": True}},
            upsert=True,
        )
        logger.info(f"Overtime baseline AUTO-SET: user={user_id} year={year} baseline={baseline}h (preserves displayed {current_total}h)")
    elif needs_v2_migration:
        current_total = float(hr.get("overtime_hours") or baseline)
        old_baseline = baseline
        baseline = round(current_total - diff_hours + deduction, 2)
        await db.hr_data.update_one(
            {"user_id": user_id, "year": year},
            {"$set": {"overtime_baseline": baseline,
                       "overtime_baseline_set_at": datetime.now(timezone.utc).isoformat(),
                       "overtime_baseline_reason": f"v2-migration: alte baseline {old_baseline}h -> {baseline}h, damit Saldo {current_total}h ohne Sprung erhalten bleibt (neue Tag-fuer-Tag-Logik)",
                       "overtime_baseline_v2_migrated": True}}
        )
        logger.info(f"Overtime V2-MIGRATION: user={user_id} year={year} baseline {old_baseline}h -> {baseline}h (preserves {current_total}h)")

    new_overtime = round(float(baseline) + diff_hours - deduction, 2)
    update = {"overtime_hours": new_overtime, "updated_at": datetime.now(timezone.utc).isoformat()}
    if not hr:
        await db.hr_data.insert_one({
            "user_id": user_id, "year": year,
            "overtime_hours": new_overtime,
            "overtime_baseline": baseline,
            "vacation_days_total": 0, "vacation_days_used": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **update,
        })
    else:
        await db.hr_data.update_one(
            {"user_id": user_id, "year": year},
            {"$set": update},
        )
    logger.info(f"Overtime recompute: user={user_id} year={year} baseline={baseline}h + diff={diff_hours}h - deduction={deduction}h = {new_overtime}h (plus={plus_days}d/+{round(plus_minutes/60.0,2)}h, minus={minus_days}d/-{round(minus_minutes/60.0,2)}h)")

    # 8) Audit-Log: Detail-Eintraege fuer NEU automatisch gebuchte Minus-Tage
    sys_caller = audit_caller or {"id": None, "name": "System (Auto-Bilanz)", "role": "system"}
    if new_detail_logs:
        # Schon geloggte Tage (per action+date+user) NICHT erneut loggen
        existing = set()
        existing_cursor = db.time_audit_log.find(
            {"target_user_id": user_id, "action": "auto_balance_day"},
            {"_id": 0, "details.date": 1}
        )
        async for ex in existing_cursor:
            d = (ex.get("details") or {}).get("date")
            if d: existing.add(d)
        for entry in new_detail_logs:
            if entry["date"] in existing:
                continue
            diff_h = round(entry["diff_min"] / 60.0, 2)
            soll_h = round(entry["soll_min"] / 60.0, 2)
            ist_h = round(entry["ist_min"] / 60.0, 2)
            try:
                d_de = datetime.fromisoformat(entry["date"]).strftime("%d.%m.%Y")
            except Exception:
                d_de = entry["date"]
            summary = f"{d_de}: {diff_h:+.2f}h (Soll {soll_h}h, Ist {ist_h}h{', ' + entry['reason'] if entry['reason'] else ''})"
            await _log_audit(user_id, "auto_balance_day", sys_caller,
                             summary=summary, details=entry)

    # 9) Audit-Log: Zusammenfassung (aggregiert) – nur wenn was passiert ist
    if plus_days or minus_days or deduction > 0:
        summary_text = (
            f"Recompute Stundenkonto {year}: "
            f"+{round(plus_minutes/60.0,2)}h an {plus_days} Tag(en), "
            f"-{round(minus_minutes/60.0,2)}h an {minus_days} Tag(en), "
            f"Abbau {round(deduction,2)}h, "
            f"Saldo: {new_overtime:+.2f}h"
        )
        await _log_audit(user_id, "auto_balance_recompute", sys_caller,
                         before={"overtime_hours": float(hr.get("overtime_hours") or 0)} if hr else None,
                         after={"overtime_hours": new_overtime},
                         summary=summary_text,
                         details={
                             "year": year,
                             "baseline_h": float(baseline),
                             "diff_h": diff_hours,
                             "deduction_h": round(deduction, 2),
                             "plus_days": plus_days, "plus_h": round(plus_minutes/60.0, 2),
                             "minus_days": minus_days, "minus_h": round(minus_minutes/60.0, 2),
                             "new_overtime_h": new_overtime,
                         })

    return new_overtime


@router.post("/time/clock-out")
async def clock_out(token: str = Query(...), body: dict | None = None):
    """Clock out with GPS coordinates. Auto-calculates overtime vs. schedule."""
    body = body or {}
    user = await _get_user(token)
    entry = await db.time_entries.find_one({"user_id": user["id"], "clock_out": None})
    if not entry:
        raise HTTPException(status_code=400, detail="Nicht eingestempelt")

    now = datetime.now(timezone.utc)
    clock_in_time = datetime.fromisoformat(entry["clock_in"])
    if clock_in_time.tzinfo is None:
        clock_in_time = clock_in_time.replace(tzinfo=timezone.utc)
    raw_duration = (now - clock_in_time).total_seconds() / 60.0

    # Pausen-Abzug: konfigurierte Pause aus dem Wochenplan abziehen
    # Aber nur BEIM ERSTEN Einsatz des Tages - fuer weitere Einsaetze am gleichen
    # Tag (z.B. Abendeinsatz nach normaler Schicht) laeuft die Zeit ohne
    # zusaetzliche Pause weiter, es sei denn der neue Einsatz alleine schon
    # die 6h-Grenze reisst (dann greift die gesetzliche Mindestpause auf ihn).
    entry_date = entry.get("date") or now.strftime("%Y-%m-%d")
    previous_break_today = 0.0
    async for prev in db.time_entries.find(
        {"user_id": user["id"], "date": entry_date, "id": {"$ne": entry["id"]},
         "clock_out": {"$ne": None}},
        {"_id": 0, "break_min": 1}
    ):
        previous_break_today += float(prev.get("break_min") or 0)
    scheduled_break = await _get_break_min_for_date(user["id"], entry_date)
    remaining_scheduled = max(0.0, scheduled_break - previous_break_today)
    # Fuer diesen Entry: Pflichtpause aus Wochenplan (soweit noch nicht am Tag
    # bereits abgezogen) ODER gesetzliche Mindestpause fuer DIESEN Entry allein
    break_min = _enforce_legal_break_minimum(raw_duration, remaining_scheduled)
    duration = _apply_break_deduction(raw_duration, break_min)

    await db.time_entries.update_one(
        {"id": entry["id"]},
        {"$set": {
            "clock_out": now.isoformat(),
            "clock_out_lat": body.get("lat"),
            "clock_out_lng": body.get("lng"),
            "duration_minutes": round(duration, 1),
            "break_min": break_min,
        }}
    )

    # ── Overtime calculation: REKONSTRUIERE den Jahresstand komplett neu
    # damit auch manuelle Edits/Deletes konsistent sind.
    try:
        import zoneinfo
        berlin = zoneinfo.ZoneInfo("Europe/Berlin")
        local_now = now.astimezone(berlin)
        await _recompute_overtime_for_year(user["id"], local_now.year)
    except Exception as e:
        logger.error(f"Overtime recompute error: {e}")

    updated = await db.time_entries.find_one({"id": entry["id"]}, {"_id": 0})
    return updated


@router.get("/time/entries")
async def get_time_entries(token: str = Query(...), user_id: Optional[str] = None,
                            date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Get time entries. Admin OR Verwaltung kann andere User einsehen."""
    caller = await _get_user(token)
    # v25.05 Fix: Vorher hat hier nur role=="admin" gegriffen - User mit
    # Verwaltungs-Permission sahen daher in der Mitarbeiter-Stundenansicht
    # immer ihre eigenen Stunden. Jetzt korrekt ueber _has_verwaltung().
    target_id = user_id if user_id and _has_verwaltung(caller) else caller["id"]

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


@router.get("/time/overview")
async def get_time_overview(token: str = Query(...)):
    """Soll/Ist-Uebersicht fuer den aktuellen User.
    Liefert taegliche Soll/Ist + woechentliche Soll/Ist + 7-Tage-Vorschau +
    Stundenkonto-Saldo + Feiertags-Info. Wird auf HubPage (kompakt) und
    ArbeitszeitPage (ausfuehrlich) angezeigt damit Mitarbeiter beim Stempeln
    direkt sehen ob sie schon das Soll erreicht haben.
    """
    from datetime import date as _date, timedelta
    import zoneinfo as _zi

    user = await _get_user(token)
    user_id = user["id"]

    _berlin = _zi.ZoneInfo("Europe/Berlin")
    now_berlin = datetime.now(timezone.utc).astimezone(_berlin)
    today = now_berlin.date()
    year = today.year

    # Wochenplan einmal laden (synchroner Helper braucht das Dict)
    schedule = await db.work_schedules.find_one({"user_id": user_id}, {"_id": 0})

    # Feiertage des Jahres und des Folgejahres (fuer 7-Tage-Vorschau ueber
    # Jahreswechsel)
    holidays = _get_holidays(year)
    if (today + timedelta(days=7)).year != year:
        holidays = {**holidays, **_get_holidays(year + 1)}

    # Wochenstart (Montag) ... Sonntag
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # Ist-Minuten pro Datum dieser Woche (aus time_entries)
    week_from = week_start.isoformat()
    week_to = (week_end + timedelta(days=1)).isoformat()  # exklusiv
    ist_by_date: dict = {}
    cursor = db.time_entries.find(
        {"user_id": user_id, "date": {"$gte": week_from, "$lt": week_to}},
        {"_id": 0, "date": 1, "duration_minutes": 1, "clock_in": 1, "clock_out": 1, "type": 1}
    )
    async for e in cursor:
        if (e.get("type") or "").lower() in ("urlaub", "krank", "ueberstundenabbau", "feiertag"):
            continue
        d = e.get("date")
        if not d:
            continue
        # Aktive (noch offene) Stempelungen: Differenz bis JETZT live mitrechnen,
        # sonst sieht der MA beim Einstempeln immer 0h "Ist" obwohl er bereits
        # einige Zeit eingestempelt ist.
        if e.get("duration_minutes") is None and e.get("clock_in") and not e.get("clock_out"):
            try:
                ci = datetime.fromisoformat(e["clock_in"])
                if ci.tzinfo is None:
                    ci = ci.replace(tzinfo=timezone.utc)
                live_mins = max(0, (datetime.now(timezone.utc) - ci).total_seconds() / 60.0)
                # Pause vom Wochenplan abziehen - nur wenn live_mins die Pause
                # bereits ueberschritten hat (konsistent mit _apply_break_deduction).
                wd_now = ci.astimezone(_berlin).weekday()
                day_sched = (schedule or {}).get("days", {}).get(_WEEKDAY_MAP.get(wd_now, ""), {}) or {}
                break_min = int(day_sched.get("break_min") or 0)
                effective = live_mins - break_min if live_mins > break_min else live_mins
                ist_by_date[d] = ist_by_date.get(d, 0.0) + max(0, effective)
            except (ValueError, TypeError):
                pass
        else:
            ist_by_date[d] = ist_by_date.get(d, 0.0) + float(e.get("duration_minutes") or 0)

    def _day_info(d: _date) -> dict:
        ds = d.isoformat()
        weekday = d.weekday()
        is_holiday = ds in holidays
        # Soll: 0 bei Feiertag, sonst aus Wochenplan
        soll = 0 if is_holiday else _soll_minutes_from_schedule(schedule, weekday)
        ist = int(round(ist_by_date.get(ds, 0.0)))
        weekday_label = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][weekday]
        return {
            "date": ds,
            "weekday": weekday_label,
            "weekday_short": weekday_label[:2],
            "is_holiday": is_holiday,
            "holiday_name": holidays.get(ds) if is_holiday else None,
            "soll_minutes": int(soll),
            "ist_minutes": ist,
            "diff_minutes": ist - int(soll),
        }

    # Wochenstruktur
    week_days = []
    week_soll = 0
    week_ist = 0
    cur = week_start
    while cur <= week_end:
        info = _day_info(cur)
        week_days.append(info)
        week_soll += info["soll_minutes"]
        week_ist += info["ist_minutes"]
        cur += timedelta(days=1)

    today_info = next((d for d in week_days if d["date"] == today.isoformat()), _day_info(today))

    # 7-Tage-Vorschau ab morgen
    next_7 = []
    for i in range(1, 8):
        d = today + timedelta(days=i)
        info = _day_info(d)
        # Vorschau: ist_minutes irrelevant, nur Soll/Feiertag
        next_7.append({
            "date": info["date"],
            "weekday": info["weekday"],
            "weekday_short": info["weekday_short"],
            "is_holiday": info["is_holiday"],
            "holiday_name": info["holiday_name"],
            "soll_minutes": info["soll_minutes"],
        })

    # Stundenkonto-Saldo (ueberstunden) aus hr_data
    hr = await db.hr_data.find_one({"user_id": user_id, "year": year}, {"_id": 0}) or {}
    overtime_hours = float(hr.get("overtime_hours") or 0)

    return {
        "today": today_info,
        "week": {
            "start": week_start.isoformat(),
            "end": week_end.isoformat(),
            "soll_minutes": week_soll,
            "ist_minutes": week_ist,
            "diff_minutes": week_ist - week_soll,
            "days": week_days,
        },
        "next_7_days": next_7,
        "overtime_hours": overtime_hours,
        "has_schedule": bool(schedule and (schedule.get("days") or {})),
    }


def _parse_local_time_to_utc(date_str: str, time_str: str) -> datetime:
    """Parse a German local wall-clock (Europe/Berlin) date+time string into
    a TRUE UTC datetime. Eingaben wie '2026-02-15' + '10:00' (= 10 Uhr MEZ)
    werden korrekt zu 09:00 UTC, im Sommer (MESZ) zu 08:00 UTC.

    Frueher wurde die Zeit nur 'als UTC etikettiert' (replace(tzinfo=utc))
    was zu einem 1-/2-Stunden-Drift fuehrte, da der Live-Stempel (UTC) und
    die manuelle Korrektur (UTC-etikettiert) verschiedene Zeitsemantik
    hatten. Mit dieser Funktion ist die Speicherung einheitlich.
    """
    if not date_str or not time_str:
        raise HTTPException(status_code=400, detail="Datum und Uhrzeit erforderlich")
    try:
        try:
            from zoneinfo import ZoneInfo
        except ImportError:  # pragma: no cover
            from backports.zoneinfo import ZoneInfo  # type: ignore
        local = datetime.fromisoformat(f"{date_str}T{time_str}:00").replace(
            tzinfo=ZoneInfo("Europe/Berlin")
        )
        return local.astimezone(timezone.utc)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail=f"Ungueltiges Datum/Uhrzeit: {date_str} {time_str}")


@router.post("/time/manual")
async def create_manual_time_entry(token: str = Query(...), body: dict = Body(...)):
    """Admin: create a time entry manually for any user (e.g. employee 'verstempelt' himself)."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
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

    # Pausen-Abzug: konfigurierte Pause aus dem Wochenplan abziehen
    raw_duration = round((clock_out - clock_in).total_seconds() / 60.0, 1) if clock_out else None
    if raw_duration is not None:
        # Pausen-Override aus Body, sonst aus Wochenplan
        if body.get("break_min") is not None:
            try:
                override_break = max(0, int(body.get("break_min") or 0))
            except (TypeError, ValueError):
                override_break = 0
            legal_min = _legal_minimum_break(raw_duration)
            break_min = max(override_break, legal_min)
        else:
            break_min = await _get_break_min_for_date(target_user_id, date_str)
            break_min = _enforce_legal_break_minimum(raw_duration, break_min)
        duration = round(_apply_break_deduction(raw_duration, break_min), 1)
    else:
        break_min = 0
        duration = None

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
        "break_min": break_min,
        "date": date_str,
        "manual": True,
        "manual_by": caller.get("id"),
        "manual_by_name": caller.get("name", ""),
        "manual_note": body.get("note") or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.time_entries.insert_one(entry)
    # Audit-Log
    await _log_audit(
        target_user_id, "time_manual_create", caller,
        after={"date": date_str, "clock_in": start_str, "clock_out": end_str,
               "duration_minutes": duration, "note": entry.get("manual_note")},
        summary=f"Arbeitszeit {date_str} {start_str or '?'}–{end_str or 'offen'} manuell angelegt"
                + (f" ({duration/60:.2f} h)" if duration else "")
    )
    # Ueberstunden neu berechnen damit der manuell erfasste Eintrag sofort
    # im hr_data.overtime_hours-Konto sichtbar wird.
    try:
        from datetime import date as _date
        year = _date.fromisoformat(date_str).year
        await _recompute_overtime_for_year(target_user_id, year)
    except Exception as e:
        logger.error(f"Overtime recompute (manual create) error: {e}")
    return await db.time_entries.find_one({"id": entry["id"]}, {"_id": 0})


@router.put("/time/entries/{entry_id}")
async def update_time_entry(entry_id: str, token: str = Query(...), body: dict = Body(...)):
    """Admin: edit an existing time entry (clock_in / clock_out)."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
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
    raw_duration = round((clock_out - clock_in).total_seconds() / 60.0, 1) if clock_out else None
    # Pausen-Abzug: konfigurierte Pause aus dem Wochenplan abziehen
    if raw_duration is not None:
        # Pausen-Override aus Body, sonst aus Wochenplan
        if body.get("break_min") is not None:
            try:
                override_break = max(0, int(body.get("break_min") or 0))
            except (TypeError, ValueError):
                override_break = 0
            # Override: gesetzliche Mindestpause nur ALS UNTERGRENZE bei >6h
            # erzwingen, sonst genau das nehmen was der Admin eingibt.
            legal_min = _legal_minimum_break(raw_duration)
            break_min = max(override_break, legal_min)
        else:
            break_min = await _get_break_min_for_date(entry.get("user_id"), date_str)
            break_min = _enforce_legal_break_minimum(raw_duration, break_min)
        duration = round(_apply_break_deduction(raw_duration, break_min), 1)
    else:
        break_min = 0
        duration = None

    update = {
        "clock_in": clock_in.isoformat(),
        "clock_out": clock_out.isoformat() if clock_out else None,
        "duration_minutes": duration,
        "break_min": break_min,
        "date": date_str,
        "edited_by": caller.get("id"),
        "edited_by_name": caller.get("name", ""),
        "edited_at": datetime.now(timezone.utc).isoformat(),
    }
    if "note" in body:
        update["manual_note"] = body.get("note") or ""
    await db.time_entries.update_one({"id": entry_id}, {"$set": update})
    # Audit-Log: was hat sich geaendert?
    await _log_audit(
        entry.get("user_id"), "time_edit", caller,
        before={"date": entry.get("date"),
                "clock_in": entry.get("clock_in"),
                "clock_out": entry.get("clock_out"),
                "duration_minutes": entry.get("duration_minutes")},
        after={"date": date_str, "clock_in_time": start_str, "clock_out_time": end_str,
               "duration_minutes": duration, "note": update.get("manual_note")},
        summary=f"Arbeitszeit {date_str} {start_str or '?'}–{end_str or 'offen'} korrigiert"
                + (f" ({duration/60:.2f} h)" if duration else "")
    )
    # Ueberstunden neu berechnen - falls Datum geaendert wurde auch fuer das alte Jahr.
    try:
        from datetime import date as _date
        new_year = _date.fromisoformat(date_str).year
        old_year = _date.fromisoformat(entry.get("date") or date_str).year if entry.get("date") else new_year
        for y in {new_year, old_year}:
            await _recompute_overtime_for_year(entry.get("user_id"), y)
    except Exception as e:
        logger.error(f"Overtime recompute (edit) error: {e}")
    return await db.time_entries.find_one({"id": entry_id}, {"_id": 0})


@router.delete("/time/entries/{entry_id}")
async def delete_time_entry(entry_id: str, token: str = Query(...)):
    """Admin: delete a time entry."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    # Vor Loeschen Datum + user_id merken, damit wir die Ueberstunden danach
    # neu rechnen koennen (sonst bleibt der Diff im hr_data-Konto stehen).
    entry = await db.time_entries.find_one({"id": entry_id}, {"_id": 0, "date": 1, "user_id": 1, "clock_in": 1, "clock_out": 1, "duration_minutes": 1})
    res = await db.time_entries.delete_one({"id": entry_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    if entry:
        await _log_audit(
            entry.get("user_id"), "time_delete", caller,
            before={"date": entry.get("date"),
                    "clock_in": entry.get("clock_in"),
                    "clock_out": entry.get("clock_out"),
                    "duration_minutes": entry.get("duration_minutes")},
            summary=f"Arbeitszeit {entry.get('date') or '?'} gelöscht"
        )
        try:
            from datetime import date as _date
            year = _date.fromisoformat(entry.get("date") or "").year
            await _recompute_overtime_for_year(entry.get("user_id"), year)
        except Exception as e:
            logger.error(f"Overtime recompute (delete) error: {e}")
    return {"ok": True}


@router.get("/time/report")
async def get_time_report(token: str = Query(...),
                           date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Admin/Verwaltung: get time report for all employees."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Verwaltungs-Berechtigung erforderlich")

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
    if not _has_verwaltung(caller) and caller["id"] != user_id:
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
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")

    year = datetime.now(timezone.utc).year
    update = {}
    # Wenn der Admin overtime_hours direkt setzt, muessen wir gleichzeitig die
    # overtime_baseline so anpassen, dass der gesetzte Wert auch nach dem naechsten
    # Recompute erhalten bleibt. Ohne diesen Schritt wuerde der Recompute den
    # Wert beim naechsten Time-Edit ueberschreiben (baseline+diff-deduction).
    if "overtime_hours" in data:
        new_value = float(data["overtime_hours"])
        update["overtime_hours"] = new_value
        # Bei manuellem Admin-Set ist der neue Wert die neue "Wahrheit" fuer
        # heute. Der Recompute wird ab morgen wieder Tag-fuer-Tag rechnen -
        # deshalb speichern wir baseline = new_value und markieren den Zeitpunkt.
        update["overtime_baseline"] = new_value
        update["overtime_baseline_set_at"] = datetime.now(timezone.utc).isoformat()
        update["overtime_baseline_reason"] = "admin-manuell gesetzt"
        update["overtime_baseline_v2_migrated"] = True  # keine erneute V2-Migration ausloesen
    if "vacation_days_total" in data:
        update["vacation_days_total"] = int(data["vacation_days_total"])
    if "vacation_days_used" in data:
        update["vacation_days_used"] = int(data["vacation_days_used"])

    if update:
        # Vorzustand fuer Audit-Log
        before_doc = await db.hr_data.find_one(
            {"user_id": user_id, "year": year},
            {"_id": 0, "overtime_hours": 1, "vacation_days_total": 1, "vacation_days_used": 1}
        ) or {}
        update["user_id"] = user_id
        update["year"] = year
        await db.hr_data.update_one(
            {"user_id": user_id, "year": year},
            {"$set": update},
            upsert=True,
        )
        # Audit-Log
        changed = []
        if "overtime_hours" in data:
            changed.append(f"Überstunden: {before_doc.get('overtime_hours', 0)} → {data['overtime_hours']} h")
        if "vacation_days_total" in data:
            changed.append(f"Urlaubsanspruch: {before_doc.get('vacation_days_total', 0)} → {data['vacation_days_total']} Tage")
        if "vacation_days_used" in data:
            changed.append(f"Urlaub genommen: {before_doc.get('vacation_days_used', 0)} → {data['vacation_days_used']} Tage")
        await _log_audit(
            user_id, "hr_data_update", caller,
            before=before_doc,
            after={k: v for k, v in data.items() if k in ("overtime_hours", "vacation_days_total", "vacation_days_used")},
            summary="HR-Daten geändert: " + ("; ".join(changed) if changed else "(keine sichtbaren Felder)")
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


@router.get("/overtime/debug-all")
async def overtime_debug_all(token: str = Query(...), year: Optional[int] = None):
    """Diagnose-Endpoint: zeigt die ROHDATEN aller hr_data-Eintraege eines
    Jahres als lesbare Tabelle. Zum direkten Aufruf im Browser gedacht
    (Admin-Session per token). Hilft bei der Fehlersuche bei falschen
    Ueberstunden-Berechnungen.
    """
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")

    yr = int(year) if year else datetime.now(timezone.utc).year
    users = await db.users.find(
        {"is_active": {"$ne": False}, "role": {"$in": ["admin", "mitarbeiter"]}},
        {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).to_list(500)
    users_by_id = {u["id"]: u for u in users}

    rows = []
    cur = db.hr_data.find({"year": yr}, {"_id": 0})
    async for hr in cur:
        uid = hr.get("user_id")
        u = users_by_id.get(uid) or {}
        rows.append({
            "user_id": uid,
            "user_name": u.get("name") or "?",
            "email": u.get("email") or "",
            "overtime_hours": hr.get("overtime_hours"),
            "overtime_baseline": hr.get("overtime_baseline"),
            "overtime_baseline_reason": hr.get("overtime_baseline_reason"),
            "overtime_baseline_set_at": hr.get("overtime_baseline_set_at"),
            "overtime_baseline_v2_migrated": hr.get("overtime_baseline_v2_migrated"),
            "vacation_days_total": hr.get("vacation_days_total"),
            "vacation_days_used": hr.get("vacation_days_used"),
            "updated_at": hr.get("updated_at"),
        })
    rows.sort(key=lambda r: (r.get("user_name") or "").lower())

    return {
        "year": yr,
        "total_users": len(users),
        "total_hr_records": len(rows),
        "rows": rows,
    }


@router.post("/overtime/set-value")
async def overtime_set_value(token: str = Query(...), user_id: str = Query(...),
                              year: int = Query(...), value: float = Query(...)):
    """Setzt Ueberstunden fuer EINEN User auf einen exakten Wert und markiert
    sauber als 'admin-manuell', sodass der naechste Recompute das respektiert.

    Einfacher als der Emergency-Reset - fuer schnelle Einzelkorrekturen.
    """
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.hr_data.update_one(
        {"user_id": user_id, "year": year},
        {"$set": {
            "overtime_hours": float(value),
            "overtime_baseline": float(value),
            "overtime_baseline_set_at": now_iso,
            "overtime_baseline_reason": "admin-manuell gesetzt (via debug-endpoint)",
            "overtime_baseline_v2_migrated": True,
            "updated_at": now_iso,
        }},
        upsert=True,
    )
    return {"ok": True, "user_id": user_id, "year": year, "new_value": value}


@router.post("/overtime/emergency-reset")
async def emergency_reset_overtime(token: str = Query(...), year: int = Query(...),
                                    dry_run: bool = Query(True), reset_to_zero: bool = Query(False)):
    """NOTFALL: Setzt Ueberstunden-Baseline aller Mitarbeiter zurueck, falls die
    V2-Migration falsche Werte errechnet hat.

    - dry_run=True (default): Zeigt nur was gemacht wuerde, ohne DB-Aenderung
    - dry_run=False: Setzt tatsaechlich zurueck
    - reset_to_zero=False: Setzt baseline = overtime_hours der letzten manuellen
      Admin-Setzung (falls vorhanden) oder 0
    - reset_to_zero=True: Setzt baseline UND overtime_hours = 0 fuer alle User
      (nuklear - danach muessen alle Werte wieder manuell gesetzt werden)

    Zusaetzlich: entfernt das overtime_baseline_v2_migrated Flag, damit die
    naechste Recompute mit sauberen Daten neu startet.
    """
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")

    affected = []
    cur = db.hr_data.find({"year": year}, {"_id": 0})
    async for hr in cur:
        uid = hr.get("user_id")
        current_overtime = float(hr.get("overtime_hours") or 0)
        current_baseline = hr.get("overtime_baseline")
        reason = hr.get("overtime_baseline_reason") or ""
        v2_migrated = bool(hr.get("overtime_baseline_v2_migrated"))

        # Nur User in Frage kommen, deren baseline durch V2-Migration gesetzt wurde
        # (Reason enthaelt "v2-migration" oder "auto-migration")
        # Manuell gesetzte Admin-Baselines werden NICHT angetastet.
        was_migrated_baseline = "v2-migration" in reason.lower() or "auto-migration" in reason.lower()
        if not v2_migrated and not was_migrated_baseline:
            continue

        if reset_to_zero:
            new_overtime = 0.0
            new_baseline = 0.0
            action = "nuclear_reset"
        else:
            # Behalte den angezeigten Saldo, aber setze baseline auf overtime_hours
            # damit der naechste Recompute mit sauberer Basis startet
            new_overtime = current_overtime
            new_baseline = current_overtime
            action = "preserve_display_reset_baseline"

        user = await db.users.find_one({"id": uid}, {"_id": 0, "name": 1})
        affected.append({
            "user_id": uid,
            "user_name": (user or {}).get("name") or "?",
            "old_overtime": current_overtime,
            "old_baseline": current_baseline,
            "old_reason": reason,
            "new_overtime": new_overtime,
            "new_baseline": new_baseline,
            "action": action,
        })

        if not dry_run:
            await db.hr_data.update_one(
                {"user_id": uid, "year": year},
                {"$set": {
                    "overtime_hours": new_overtime,
                    "overtime_baseline": new_baseline,
                    "overtime_baseline_v2_migrated": False,
                    "overtime_baseline_reason": f"emergency-reset ({'nuclear' if reset_to_zero else 'preserve'}) am {datetime.now(timezone.utc).date().isoformat()}",
                    "overtime_baseline_set_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }}
            )

    return {
        "dry_run": dry_run,
        "reset_to_zero": reset_to_zero,
        "affected_count": len(affected),
        "affected": affected[:50],  # cap output
        "message": (
            f"DRY RUN: {len(affected)} User waeren betroffen. Setze dry_run=false zum Ausfuehren."
            if dry_run else f"{len(affected)} User zurueckgesetzt."
        ),
    }


@router.get("/reports/yearly-evaluation/pdf")
async def yearly_evaluation_pdf(token: str = Query(...), year: Optional[int] = None):
    """Erzeugt eine einseitige PDF-Uebersicht aller aktiven Mitarbeiter fuer
    das laufende Kalenderjahr: Name, UEberstunden-Saldo, Urlaub genommen,
    Resturlaub und Krankheitstage."""
    from utils.http_headers import content_disposition
    from services.hr_evaluation_pdf import generate_yearly_evaluation_pdf
    from datetime import date as _date, timedelta as _td

    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")

    now = datetime.now(timezone.utc)
    yr = int(year) if year else now.year
    year_start = f"{yr}-01-01"
    year_end = f"{yr}-12-31"

    # Nur aktive Mitarbeiter + Admins (mit Rolle im HR-System)
    users = await db.users.find(
        {"is_active": {"$ne": False}, "role": {"$in": ["admin", "mitarbeiter"]}},
        {"_id": 0, "id": 1, "name": 1},
    ).to_list(1000)

    rows: list[dict] = []
    for u in users:
        uid = u["id"]
        # HR-Daten fuer das Jahr (Ueberstunden, Urlaub)
        hr = await db.hr_data.find_one(
            {"user_id": uid, "year": yr},
            {"_id": 0, "overtime_hours": 1, "vacation_days_total": 1, "vacation_days_used": 1},
        ) or {}
        overtime = float(hr.get("overtime_hours") or 0)
        vac_total = float(hr.get("vacation_days_total") or 0)
        vac_used = float(hr.get("vacation_days_used") or 0)
        vac_remaining = vac_total - vac_used

        # Krankheitstage: approved time_off_requests type=krank im Jahr, Werktage zaehlen
        sick_days = 0
        sick_cur = db.time_off_requests.find(
            {"user_id": uid, "status": "approved", "type": "krank"},
            {"_id": 0, "start_date": 1, "end_date": 1},
        )
        async for r in sick_cur:
            try:
                s = _date.fromisoformat(r["start_date"])
                e = _date.fromisoformat(r["end_date"])
            except (KeyError, ValueError, TypeError):
                continue
            # Auf Jahr begrenzen
            js = max(s, _date(yr, 1, 1))
            je = min(e, _date(yr, 12, 31))
            if js > je:
                continue
            cur = js
            while cur <= je:
                if cur.weekday() < 5:  # Mo-Fr
                    sick_days += 1
                cur += _td(days=1)

        rows.append({
            "name": u.get("name") or "",
            "overtime_hours": round(overtime, 2),
            "vacation_days_used": vac_used,
            "vacation_days_remaining": vac_remaining,
            "sick_days": sick_days,
        })

    pdf_bytes = generate_yearly_evaluation_pdf(rows, yr)
    filename = f"Mitarbeiter-Auswertung-{yr}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition(filename, "inline")},
    )


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
    if not _has_verwaltung(caller):
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
        headers={"Content-Disposition": content_disposition(att["filename"], "inline")}
    )


@router.delete("/info-posts/{post_id}")
async def delete_info_post(post_id: str, token: str = Query(...)):
    """Admin: Info-Post loeschen (Soft-Delete)."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
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
    if not _has_verwaltung(caller) and caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    year = datetime.now(timezone.utc).year
    entries = await db.vacation_entries.find(
        {"user_id": user_id, "year": year}, {"_id": 0}
    ).sort("start_date", 1).to_list(500)
    return entries


@router.post("/vacation/{user_id}")
async def add_vacation_entry(user_id: str, token: str = Query(...), data: dict = Body(...)):
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
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
    await _log_audit(
        user_id, "vacation_add", caller,
        after={"start_date": start_date, "end_date": end_date, "days": days},
        summary=f"Urlaub {start_date} – {end_date} hinzugefügt ({days} Tage)"
    )
    return {"id": entry["id"], "days": days}


@router.delete("/vacation/{user_id}/{entry_id}")
async def delete_vacation_entry(user_id: str, entry_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")

    entry = await db.vacation_entries.find_one({"id": entry_id, "user_id": user_id})
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")

    year = entry.get("year", datetime.now(timezone.utc).year)
    await db.vacation_entries.delete_one({"id": entry_id, "user_id": user_id})
    await _recalc_vacation_used(user_id, year)
    await _log_audit(
        user_id, "vacation_delete", caller,
        before={"start_date": entry.get("start_date"), "end_date": entry.get("end_date"), "days": entry.get("days")},
        summary=f"Urlaub {entry.get('start_date')} – {entry.get('end_date')} gelöscht ({entry.get('days')} Tage)"
    )
    return {"ok": True}


# ─── Time Off Requests ──────────────────────────────

@router.post("/time-off/admin-create")
async def admin_create_time_off(token: str = Query(...), data: dict = Body(...)):
    """Admin: directly create an approved time-off entry for a user (e.g. Überstundenabbau).
    Skips the request/approval flow – the entry lands as 'approved' immediately.
    For 'ueberstundenabbau' the overtime account is reduced by 8h per weekday."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")

    target_user_id = data.get("user_id")
    req_type = data.get("type", "ueberstundenabbau")
    start_date = data.get("start_date")
    end_date = data.get("end_date") or start_date
    # Optional: Stundengenauer Ueberstundenabbau (Admin kann zwischen Tagen
    # und Stunden waehlen). Wenn `hours` gesetzt, wird das Konto exakt um
    # diese Stundenzahl belastet (kein days*8 mehr).
    hours_input = data.get("hours")
    try:
        hours = float(hours_input) if hours_input not in (None, "") else None
    except (TypeError, ValueError):
        hours = None

    if not target_user_id or not start_date:
        raise HTTPException(status_code=400, detail="user_id und start_date erforderlich")
    if req_type not in ("ueberstundenabbau", "urlaub", "krank"):
        raise HTTPException(status_code=400, detail="Ungueltiger Typ")
    if hours is not None and req_type != "ueberstundenabbau":
        raise HTTPException(status_code=400, detail="Stunden-Eingabe nur fuer Ueberstundenabbau erlaubt")
    if hours is not None and hours <= 0:
        raise HTTPException(status_code=400, detail="Stunden muss > 0 sein")

    target = await db.users.find_one({"id": target_user_id}, {"_id": 0, "id": 1, "name": 1, "email": 1})
    if not target:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    # Wenn Stundenmodus: only 1 Tag, days=0; sonst: weekday-count.
    if hours is not None:
        days = 0
        end_date = start_date  # Stundenabbau immer auf 1 Tag
    else:
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
        "all_day": hours is None,
        "start_time": None,
        "end_time": None,
        "days": days,
        "hours_deducted": hours,  # None oder konkrete Stundenzahl
        "status": "approved",
        "created_at": now_iso,
        "resolved_at": now_iso,
        "resolved_by": caller.get("id"),
        "resolved_by_name": caller.get("name", "Admin"),
        "admin_created": True,
    }
    await db.time_off_requests.insert_one(entry)

    # Ueberstundenabbau: Konto belasten - exakte Stunden oder days*8.
    if req_type == "ueberstundenabbau":
        if hours is not None:
            hours_to_deduct = hours
        elif days > 0:
            hours_to_deduct = days * 8.0
        else:
            hours_to_deduct = 0
        if hours_to_deduct > 0:
            hr = await db.hr_data.find_one({"user_id": target_user_id}, {"_id": 0})
            current = float(hr.get("overtime_hours", 0)) if hr else 0.0
            new_val = round(current - hours_to_deduct, 2)
            await db.hr_data.update_one(
                {"user_id": target_user_id},
                {"$set": {"overtime_hours": new_val, "updated_at": now_iso}},
                upsert=True,
            )

    _typ_lbl_c = {"krank": "Krankmeldung", "urlaub": "Urlaub", "ueberstundenabbau": "Überstundenabbau"}.get(req_type, req_type)
    _detail = f"({hours}h)" if hours is not None else f"({days} Tage)"
    await _log_audit(
        target_user_id, "time_off_admin_create", caller,
        after={"type": req_type, "start_date": start_date, "end_date": end_date, "days": days, "hours": hours},
        summary=f"{_typ_lbl_c} {start_date} – {end_date} eingetragen {_detail}"
    )
    return {k: v for k, v in entry.items() if k != "_id"}


@router.delete("/time-off/{request_id}")
async def admin_delete_time_off(request_id: str, token: str = Query(...)):
    """Admin: delete a time-off entry. If approved 'ueberstundenabbau', refund the hours."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    req = await db.time_off_requests.find_one({"id": request_id}, {"_id": 0})
    if not req:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")

    # Refund overtime if it was an approved Überstundenabbau
    if req.get("status") == "approved" and req.get("type") == "ueberstundenabbau":
        # Exakte Stunden ueberschreiben days*8 (Stunden-Modus, siehe
        # admin_create_time_off).
        hours_to_refund = req.get("hours_deducted")
        if hours_to_refund is None:
            days = req.get("days", 0) or 0
            hours_to_refund = days * 8.0
        try:
            hours_to_refund = float(hours_to_refund or 0)
        except (TypeError, ValueError):
            hours_to_refund = 0
        if hours_to_refund > 0:
            hr = await db.hr_data.find_one({"user_id": req["user_id"]}, {"_id": 0})
            current = float(hr.get("overtime_hours", 0)) if hr else 0.0
            new_val = round(current + hours_to_refund, 2)
            await db.hr_data.update_one(
                {"user_id": req["user_id"]},
                {"$set": {"overtime_hours": new_val, "updated_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )

    await db.time_off_requests.delete_one({"id": request_id})
    _typ_lbl = {"krank": "Krankmeldung", "urlaub": "Urlaub", "ueberstundenabbau": "Überstundenabbau"}.get(req.get("type"), req.get("type") or "Antrag")
    await _log_audit(
        req.get("user_id"), "time_off_delete", caller,
        before={"type": req.get("type"), "status": req.get("status"),
                "start_date": req.get("start_date"), "end_date": req.get("end_date"),
                "days": req.get("days")},
        summary=f"{_typ_lbl} {req.get('start_date')} – {req.get('end_date')} gelöscht"
    )
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
    """Get time-off requests. Employees see their own, admins/verwaltung can filter by user_id or see all."""
    caller = await _get_user(token)
    query = {}
    if _has_verwaltung(caller):
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
        if not _has_verwaltung(caller):
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

    # If approved and type is ueberstundenabbau, deduct from overtime account.
    # Wenn Admin-Eintrag den Stundenmodus genutzt hat (hours_deducted gesetzt)
    # ODER der Antrag nicht ganztaegig war (Uhrzeit-Spanne): exakte Stunden
    # belasten. Sonst days*8 (ganztaegig).
    if status == "approved" and req.get("type") == "ueberstundenabbau":
        if req.get("hours_deducted") is not None:
            try:
                hours_to_deduct = float(req.get("hours_deducted") or 0)
            except (TypeError, ValueError):
                hours_to_deduct = 0
        elif not req.get("all_day") and req.get("start_time") and req.get("end_time"):
            # Halbtags-Antrag: Uhrzeit-Spanne als Stundenzahl interpretieren.
            try:
                sh, sm = [int(x) for x in str(req["start_time"]).split(":")[:2]]
                eh, em = [int(x) for x in str(req["end_time"]).split(":")[:2]]
                hours_to_deduct = max(0, ((eh * 60 + em) - (sh * 60 + sm)) / 60.0)
            except (TypeError, ValueError):
                hours_to_deduct = 0
        else:
            days = req.get("days", 0) or 0
            hours_to_deduct = days * 8 if days > 0 else 8
        year = int(req["start_date"][:4])
        hr = await db.hr_data.find_one({"user_id": req["user_id"], "year": year})
        current_overtime = float(hr.get("overtime_hours", 0)) if hr else 0
        new_overtime = round(current_overtime - hours_to_deduct, 2)
        await db.hr_data.update_one(
            {"user_id": req["user_id"], "year": year},
            {"$set": {"overtime_hours": new_overtime, "hours_deducted_last": hours_to_deduct}},
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
    if not _has_verwaltung(caller) and caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    doc = await db.work_schedules.find_one({"user_id": user_id}, {"_id": 0})
    if not doc:
        doc = {"user_id": user_id, "days": {}}
    return doc

@router.put("/work-schedule/{user_id}")
async def update_work_schedule(user_id: str, token: str = Query(...), data: dict = Body(...)):
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    before = await db.work_schedules.find_one({"user_id": user_id}, {"_id": 0}) or {}
    update_fields = {"user_id": user_id, "updated_at": datetime.now(timezone.utc).isoformat()}
    changed_parts = []
    if "days" in data:
        update_fields["days"] = data["days"]
        changed_parts.append("Arbeitszeiten-Wochenplan")
    if "hourly_wage" in data:
        update_fields["hourly_wage"] = float(data["hourly_wage"])
        old_w = before.get("hourly_wage", "?")
        changed_parts.append(f"Stundenlohn {old_w} → {data['hourly_wage']} €")
    if "surcharges" in data:
        # Sonn-/Feiertags-/Sonderfeiertagszuschläge werden nicht mehr gezahlt
        # (siehe Lohnabrechnungs-Logik). Nur 'night' wird persistiert.
        incoming = data["surcharges"] or {}
        cleaned = {"night": float(incoming.get("night", 25))}
        update_fields["surcharges"] = cleaned
        changed_parts.append("Nachtzuschlag")
    await db.work_schedules.update_one(
        {"user_id": user_id},
        {"$set": update_fields},
        upsert=True,
    )
    await _log_audit(
        user_id, "work_schedule_update", caller,
        before={k: before.get(k) for k in ("days", "hourly_wage", "surcharges") if k in before},
        after={k: update_fields.get(k) for k in ("days", "hourly_wage", "surcharges") if k in update_fields},
        summary="Regelarbeitszeit/Lohn geändert: " + ", ".join(changed_parts) if changed_parts else "Regelarbeitszeit aktualisiert"
    )
    return {"ok": True}


# ── Payroll Calculation ──────────────────────────────────

import zoneinfo
from calendar import monthrange
import csv
import io
from utils.http_headers import content_disposition

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
    if not _has_verwaltung(caller):
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
    if not _has_verwaltung(caller) and caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    year_num, month_num = int(month[:4]), int(month[5:7])
    _, days_in_month = monthrange(year_num, month_num)
    date_from = f"{month}-01"
    date_to = f"{month}-{days_in_month:02d}"

    # Get config
    ws = await db.work_schedules.find_one({"user_id": user_id}, {"_id": 0})
    hourly_wage = (ws or {}).get("hourly_wage", 0)
    surcharges = (ws or {}).get("surcharges", {})
    # Rechtlich nicht zwingend: Sonn-/Feiertags-/Sonderfeiertagszuschläge werden
    # NICHT gezahlt (per Entscheidung Geschäftsleitung). Nur Nachtzuschlag bleibt.
    # Sonntag/Feiertag/Sonderfeiertag werden weiterhin als Typ angezeigt, ohne
    # Aufschlag. Ausgleich für Sonn-/Feiertagsarbeit erfolgt über das
    # Offday-System (Ersatzruhetag).
    sunday_pct = 0.0
    holiday_pct = 0.0
    special_pct = 0.0
    night_pct = float(surcharges.get("night", 25))

    holidays = _get_holidays(year_num)

    # Get time entries for the month
    entries = await db.time_entries.find(
        {"user_id": user_id, "date": {"$gte": date_from, "$lte": date_to}, "clock_out": {"$ne": None}},
        {"_id": 0}
    ).sort("clock_in", 1).to_list(500)

    rows = []
    totals = {"regular_min": 0, "sunday_min": 0, "holiday_min": 0, "special_min": 0, "night_min": 0, "offday_min": 0,
              "regular_wage": 0, "sunday_wage": 0, "holiday_wage": 0, "special_wage": 0, "night_wage": 0, "offday_wage": 0}

    # Offdays im Monat: bezahlte Ersatzruhetage (kein Stempel, aber Sollstunden
    # werden zum normalen Stundenlohn verguetet - ohne Zuschlag).
    offday_assignments = await db.shift_assignments.find(
        {"user_id": user_id, "is_offday": True, "date": {"$gte": date_from, "$lte": date_to}},
        {"_id": 0, "date": 1}
    ).to_list(200)
    for off in offday_assignments:
        d_str = off.get("date")
        if not d_str:
            continue
        try:
            d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        soll_min = _soll_minutes_from_schedule(ws or {}, d_obj.weekday())
        if soll_min <= 0:
            # Kein Soll im Wochenplan -> Default 8h ansetzen (sonst keine Verguetung).
            soll_min = 8 * 60
        hours = soll_min / 60
        base_wage = round(hours * hourly_wage, 2)
        rows.append({
            "date": d_str,
            "weekday": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][d_obj.weekday()],
            "clock_in": "",
            "clock_out": "",
            "total_min": soll_min,
            "total_hours": round(hours, 2),
            "surcharge_type": "offday",
            "surcharge_pct": 0,
            "night_min": 0,
            "base_wage": base_wage,
            "surcharge_wage": 0,
            "night_wage": 0,
            "total_wage": base_wage,
            "holiday_name": "Offday (Ersatzruhetag)",
        })
        totals["offday_min"] += soll_min
        totals["offday_wage"] += base_wage

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
    total_gross = round(totals["regular_wage"] + totals["sunday_wage"] + totals["holiday_wage"] + totals["special_wage"] + totals["night_wage"] + totals["offday_wage"], 2)
    total_net = round(total_gross - total_deductions, 2)

    # Reisekosten (Verpflegungsmehraufwand + KM + Übernachtung) für den Monat aggregieren.
    # Nur GENEHMIGTE Reisen werden in die Lohnabrechnung übernommen (steuerfrei!).
    travel_docs = await db.travel_expenses.find(
        {"user_id": user_id, "month": month, "status": "approved"}, {"_id": 0}
    ).sort("departure_at", 1).to_list(500)
    travel_per_diem = 0.0
    travel_km_eur = 0.0
    travel_accommodation = 0.0
    travel_other = 0.0
    travel_km = 0.0
    travel_list = []
    for t in travel_docs:
        c = t.get("computed", {}) or {}
        travel_per_diem += float(c.get("per_diem_net", 0) or 0)
        travel_km_eur += float(c.get("km_eur", 0) or 0)
        travel_accommodation += float(c.get("accommodation_eur", 0) or 0)
        travel_other += float(c.get("other_eur", 0) or 0)
        travel_km += float(c.get("km", 0) or 0)
        travel_list.append({
            "id": t.get("id"),
            "trip_purpose": t.get("trip_purpose", ""),
            "country_name": c.get("country_name", ""),
            "departure_at": t.get("departure_at"),
            "arrival_at": t.get("arrival_at"),
            "per_diem_net": round(float(c.get("per_diem_net", 0) or 0), 2),
            "km_eur": round(float(c.get("km_eur", 0) or 0), 2),
            "accommodation_eur": round(float(c.get("accommodation_eur", 0) or 0), 2),
            "other_eur": round(float(c.get("other_eur", 0) or 0), 2),
            "total_eur": round(float(c.get("total_eur", 0) or 0), 2),
        })
    travel_total = round(travel_per_diem + travel_km_eur + travel_accommodation + travel_other, 2)
    # Auszahlbetrag inklusive steuerfreier Reisekosten (zusätzlich zum Netto-Lohn)
    total_payout = round(total_net + travel_total, 2)

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
        "travel_expenses": {
            "trip_count": len(travel_list),
            "per_diem_total": round(travel_per_diem, 2),
            "km_total": round(travel_km, 2),
            "km_total_eur": round(travel_km_eur, 2),
            "accommodation_total": round(travel_accommodation, 2),
            "other_total": round(travel_other, 2),
            "grand_total": travel_total,
            "trips": travel_list,
        },
        "total_payout": total_payout,
    }


@router.get("/payroll/{user_id}/csv")
async def get_payroll_csv(user_id: str, month: str = Query(...), token: str = Query(...)):
    """Export payroll as CSV."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
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

    # ── Reisekosten (steuerfrei nach §3 Nr. 13/16 EStG) ──
    tx = payroll.get("travel_expenses") or {}
    if tx.get("trip_count", 0) > 0:
        writer.writerow([])
        writer.writerow(["Reisekosten (steuerfrei)"])
        writer.writerow(["Datum", "Zweck", "Land", "VMA netto", "KM-Pauschale", "Übernachtung", "Sonstige", "Gesamt"])
        for tr in tx.get("trips", []):
            dep = (tr.get("departure_at") or "")[:10]
            writer.writerow([
                dep, tr.get("trip_purpose", ""), tr.get("country_name", ""),
                f"{tr['per_diem_net']:.2f}", f"{tr['km_eur']:.2f}",
                f"{tr['accommodation_eur']:.2f}", f"{tr['other_eur']:.2f}",
                f"{tr['total_eur']:.2f}",
            ])
        writer.writerow([])
        writer.writerow(["Verpflegungsmehraufwand", f"{tx['per_diem_total']:.2f} EUR"])
        writer.writerow(["KM-Pauschale", f"{tx['km_total_eur']:.2f} EUR ({tx['km_total']:.0f} km)"])
        writer.writerow(["Übernachtungskosten", f"{tx['accommodation_total']:.2f} EUR"])
        writer.writerow(["Sonstige Reisekosten", f"{tx['other_total']:.2f} EUR"])
        writer.writerow(["REISEKOSTEN GESAMT", f"{tx['grand_total']:.2f} EUR"])

    if (payroll.get("total_payout") or 0) != payroll.get("total_net", 0):
        writer.writerow([])
        writer.writerow(["AUSZAHLBETRAG (Netto + Reisekosten)", f"{payroll['total_payout']:.2f} EUR"])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=lohn_{name}_{month}.csv"}
    )


# ── Payroll Deductions (Abzüge) ──────────────────────────

@router.get("/deductions/{user_id}")
async def get_deductions(user_id: str, month: str = Query(...), token: str = Query(...)):
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    items = await db.payroll_deductions.find({"user_id": user_id, "month": month}, {"_id": 0}).to_list(100)
    return items

@router.post("/deductions/{user_id}")
async def add_deduction(user_id: str, token: str = Query(...), data: dict = Body(...)):
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
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
    await _log_audit(
        user_id, "deduction_add", caller,
        after={"month": entry["month"], "text": entry["text"], "amount": entry["amount"]},
        summary=f"Abzug {entry['month']}: „{entry['text']}\" −{entry['amount']:.2f} €"
    )
    return {"id": entry["id"], "ok": True}

@router.delete("/deductions/entry/{deduction_id}")
async def delete_deduction(deduction_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    item = await db.payroll_deductions.find_one({"id": deduction_id}, {"_id": 0})
    await db.payroll_deductions.delete_one({"id": deduction_id})
    if item:
        await _log_audit(
            item.get("user_id"), "deduction_delete", caller,
            before={"month": item.get("month"), "text": item.get("text"), "amount": item.get("amount")},
            summary=f"Abzug {item.get('month')}: „{item.get('text', '')}\" gelöscht"
        )
    return {"ok": True}


# ── Payroll Releases (Freigabe) ─────────────────

@router.post("/payroll/{user_id}/release")
async def release_payroll(user_id: str, month: str = Query(...), token: str = Query(...)):
    """Admin releases (saves) a payroll for a specific month."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
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
    await _log_audit(
        user_id, "payroll_release", caller,
        after={"month": month, "total_gross": (payroll_data or {}).get("total_gross"),
               "total_net": (payroll_data or {}).get("total_net")},
        summary=f"Lohnabrechnung {month} freigegeben"
                + (f" (brutto {(payroll_data or {}).get('total_gross', 0):.2f} €)" if payroll_data else "")
    )
    return {"ok": True, "month": month}


@router.get("/payroll/{user_id}/releases")
async def get_payroll_releases(user_id: str, token: str = Query(...)):
    """Get all released payrolls for a user. Admin/Verwaltung sehen alle,
    Mitarbeiter nur die eigenen."""
    caller = await _get_user(token)
    target_id = user_id if _has_verwaltung(caller) else caller["id"]
    releases = await db.payroll_releases.find({"user_id": target_id}, {"_id": 0}).sort("month", -1).to_list(200)
    return releases


# ── Employee Notes (Mitarbeiter-Notizen) ─────────────────

@router.get("/notes/{user_id}")
async def get_notes(user_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    notes = await db.employee_notes.find({"user_id": user_id, "deleted": {"$ne": True}}, {"_id": 0}).sort("date", -1).to_list(500)
    return notes

@router.post("/notes/{user_id}")
async def create_note(user_id: str, token: str = Query(...), data: dict = Body(...)):
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
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
    if not _has_verwaltung(caller):
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
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    await db.employee_notes.update_one({"id": note_id}, {"$set": {"deleted": True}})
    return {"ok": True}

@router.post("/notes/entry/{note_id}/upload")
async def upload_note_file(note_id: str, token: str = Query(...), file: UploadFile = File(...)):
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
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
    if not _has_verwaltung(caller):
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
                    headers={"Content-Disposition": content_disposition(file_meta['filename'], "inline")})

@router.delete("/notes/files/{note_id}/{file_id}")
async def delete_note_file(note_id: str, file_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
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
    if not _has_verwaltung(caller):
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
    if not _has_verwaltung(caller):
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
    if not _has_verwaltung(caller):
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
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    res = await db.faqs.update_one(
        {"id": faq_id},
        {"$set": {"deleted": True, "deleted_at": datetime.now(timezone.utc).isoformat()}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="FAQ nicht gefunden")
    return {"ok": True}



# ── Einsatzplanung (Shift Planning) ─────────────────

def _iso_week_key(d) -> str:
    """Erzeugt 'YYYY-WXX' fuer ein date-Objekt."""
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


@router.get("/shift-plan")
async def get_shift_plan(week: str = Query(...), token: str = Query(...)):
    """Admin: Get all assignments for a week (e.g. '2026-W15')."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
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
        from datetime import timedelta, date as _date
        # WICHTIG: ISO-Woche verwenden (Frontend nutzt ISO).
        # strptime mit %W ergibt einen 1-Wochen-Offset!
        try:
            monday = _date.fromisocalendar(year, wk, 1)
        except Exception:
            monday = datetime.strptime(f"{year}-W{wk:02d}-1", "%Y-W%W-%w").date()
        sunday = monday + timedelta(days=6)
        mon_str = monday.isoformat()
        sun_str = sunday.isoformat()
        # 1) Genehmigte Antraege (Urlaub/Krank/Ueberstundenabbau)
        reqs = await db.time_off_requests.find({
            "status": "approved",
            "start_date": {"$lte": sun_str},
            "end_date": {"$gte": mon_str},
        }, {"_id": 0}).to_list(500)
        absences = list(reqs)

        # 2) Direkt vom Admin eingetragene Urlaube (vacation_entries) -
        # diese haben keinen status, gelten implizit als 'approved'. Wir
        # normalisieren sie hier in das gleiche Format wie time_off_requests,
        # damit das Frontend sie ueber den bestehenden Render-Pfad
        # (absenceLabel('urlaub')) anzeigen kann.
        vac_cursor = db.vacation_entries.find({
            "start_date": {"$lte": sun_str},
            "end_date": {"$gte": mon_str},
        }, {"_id": 0})
        # User-Namen aus DB laden (vacation_entries enthaelt nur user_id)
        vac_docs = await vac_cursor.to_list(500)
        if vac_docs:
            user_ids = list({v["user_id"] for v in vac_docs if v.get("user_id")})
            users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
            name_by_id = {u["id"]: u.get("name", "") for u in users}
            # Duplikat-Erkennung: time_off_request -> vacation_entry Verkettung
            # ueber 'from_request' Feld (siehe update_time_off_status).
            existing_req_ids = {r.get("id") for r in absences}
            for v in vac_docs:
                # Wenn der vacation_entry aus einem approved time_off_request
                # entstanden ist, ueberspringen (sonst doppelte Anzeige).
                if v.get("from_request") and v["from_request"] in existing_req_ids:
                    continue
                absences.append({
                    "id": v.get("id"),
                    "user_id": v.get("user_id"),
                    "user_name": name_by_id.get(v.get("user_id"), ""),
                    "type": "urlaub",
                    "type_label": "Urlaub",
                    "start_date": v.get("start_date"),
                    "end_date": v.get("end_date"),
                    "days": v.get("days"),
                    "status": "approved",
                    "source": "vacation_entry",  # Hinweis fuer Frontend (read-only)
                })
    return {
        "assignments": assignments,
        "released": bool(release),
        "released_at": release.get("released_at") if release else None,
        "absences": absences,
    }


@router.post("/shift-plan")
async def upsert_shift_assignment(data: dict = Body(...), token: str = Query(...)):
    """Verwaltung: Create or update a shift assignment.
    Bei 'date_range' (date_from + date_to) werden mehrere Assignments in einem
    Rutsch angelegt (z.B. 7 Tage fuer ein ADAC 24h-Rennen).

    Regeln Offday:
    - Pro (user_id, date) ist maximal 1 Offday erlaubt (Doppel-Block).
    - Wenn an einem Tag ein Offday existiert, sind KEINE weiteren Eintraege
      (Einsatz/Offday) erlaubt - der Tag ist exklusiv geblockt.
    """
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    assignment_id = data.get("id")

    async def _check_day_conflict(user_id: str, date_iso: str, is_offday: bool, exclude_id: str | None = None):
        """Wirft 409 wenn Tag bereits durch Offday/Einsatz blockiert ist."""
        if not user_id or not date_iso:
            return
        q = {"user_id": user_id, "date": date_iso}
        if exclude_id:
            q["id"] = {"$ne": exclude_id}
        existing = await db.shift_assignments.find(q, {"_id": 0, "is_offday": 1}).to_list(50)
        if not existing:
            return
        has_offday = any(e.get("is_offday") for e in existing)
        if has_offday:
            raise HTTPException(status_code=409,
                detail=f"Am {date_iso} ist bereits ein Offday eingetragen. Bitte den Offday zuerst loeschen, bevor weitere Eintraege moeglich sind.")
        if is_offday:
            raise HTTPException(status_code=409,
                detail=f"Am {date_iso} sind bereits {len(existing)} Eintrag(e) vorhanden. Bitte erst alle Einsaetze loeschen, bevor ein Offday vergeben wird.")

    # ── Mehrtages-Modus: date_range statt einzelnem date ──
    date_from = data.get("date_from")
    date_to = data.get("date_to")
    if not assignment_id and date_from and date_to:
        from datetime import date as _date
        try:
            d0 = _date.fromisoformat(date_from)
            d1 = _date.fromisoformat(date_to)
        except Exception:
            raise HTTPException(status_code=400, detail="Ungueltige Datumsangaben")
        if d1 < d0:
            raise HTTPException(status_code=400, detail="date_to < date_from")
        created_ids = []
        from datetime import timedelta as _td
        cur = d0
        user_id = data.get("user_id")
        order_pk = data.get("order_pk")
        # Verhindere Doppel-Eintraege: pruefe existierende
        existing = await db.shift_assignments.find(
            {"user_id": user_id, "order_pk": order_pk,
             "date": {"$gte": d0.isoformat(), "$lte": d1.isoformat()}},
            {"_id": 0, "date": 1}
        ).to_list(100)
        existing_dates = {e.get("date") for e in existing}
        while cur <= d1:
            cur_iso = cur.isoformat()
            if cur_iso not in existing_dates:
                # Offday/Mix-Konflikt-Pruefung pro Tag
                await _check_day_conflict(user_id, cur_iso, bool(data.get("is_offday")))
                new_id = str(uuid.uuid4())
                week_key = _iso_week_key(cur)
                await db.shift_assignments.insert_one({
                    "id": new_id,
                    "user_id": user_id,
                    "date": cur_iso,
                    "order_pk": order_pk,
                    "order_name": data.get("order_name", ""),
                    "role": data.get("role", ""),
                    "note": data.get("note", ""),
                    "start_time": data.get("start_time", ""),
                    "end_time": data.get("end_time", ""),
                    "is_offday": bool(data.get("is_offday")),
                    "week_key": week_key,
                    "created_by": caller["id"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                created_ids.append(new_id)
                # Offday-Konto belasten falls Mehrtages-Offday
                if data.get("is_offday"):
                    try:
                        from routes.offdays import consume_offday_for_assignment
                        target = await db.users.find_one({"id": user_id}, {"_id": 0, "name": 1})
                        await consume_offday_for_assignment(
                            user_id, (target or {}).get("name", ""), cur_iso, new_id,
                            caller.get("name") or caller.get("email") or "admin",
                        )
                    except Exception as _e:
                        logger.warning(f"Offday consume fehlgeschlagen: {_e}")
            cur = cur + _td(days=1)
        return {"ok": True, "created": len(created_ids), "skipped_existing": len(existing_dates), "ids": created_ids}

    if assignment_id:
        # Bei Update: vorhandenen Eintrag holen, um is_offday Flip
        # (war-Offday -> wird-normal oder umgekehrt) korrekt zu behandeln.
        prev = await db.shift_assignments.find_one({"id": assignment_id}, {"_id": 0})
        # Konflikt-Pruefung beim Update auch (z.B. wenn Datum geaendert wird)
        await _check_day_conflict(data.get("user_id"), data.get("date"),
                                  bool(data.get("is_offday")), exclude_id=assignment_id)
        await db.shift_assignments.update_one({"id": assignment_id}, {"$set": {
            "user_id": data.get("user_id"),
            "date": data.get("date"),
            "order_pk": data.get("order_pk"),
            "order_name": data.get("order_name", ""),
            "role": data.get("role", ""),
            "note": data.get("note", ""),
            "start_time": data.get("start_time", ""),
            "end_time": data.get("end_time", ""),
            "is_offday": bool(data.get("is_offday")),
            "week_key": data.get("week_key"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})
        # Offday-Konto-Update bei Statuswechsel
        try:
            from routes.offdays import consume_offday_for_assignment, release_offday_for_assignment
            was_off = bool((prev or {}).get("is_offday"))
            now_off = bool(data.get("is_offday"))
            if was_off and not now_off:
                await release_offday_for_assignment(assignment_id)
            elif now_off and not was_off:
                target = await db.users.find_one({"id": data.get("user_id")}, {"_id": 0, "name": 1})
                await consume_offday_for_assignment(
                    data.get("user_id"), (target or {}).get("name", ""),
                    data.get("date"), assignment_id,
                    caller.get("name") or caller.get("email") or "admin",
                )
        except Exception as _e:
            logger.warning(f"Offday-Update fehlgeschlagen: {_e}")
    else:
        # Neuer Einzel-Eintrag - Konflikt-Pruefung
        await _check_day_conflict(data.get("user_id"), data.get("date"),
                                  bool(data.get("is_offday")))
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
            "is_offday": bool(data.get("is_offday")),
            "week_key": data.get("week_key"),
            "created_by": caller["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        # Offday-Konto belasten
        if data.get("is_offday"):
            try:
                from routes.offdays import consume_offday_for_assignment
                target = await db.users.find_one({"id": data.get("user_id")}, {"_id": 0, "name": 1})
                await consume_offday_for_assignment(
                    data.get("user_id"), (target or {}).get("name", ""),
                    data.get("date"), assignment_id,
                    caller.get("name") or caller.get("email") or "admin",
                )
            except Exception as _e:
                logger.warning(f"Offday consume fehlgeschlagen: {_e}")
            # Stundenkonto neu rechnen, da Offday den Soll-Abzug aufhebt.
            try:
                y = int(str(data.get("date") or "")[:4])
                await _recompute_overtime_for_year(data.get("user_id"), y)
            except Exception as _e:
                logger.warning(f"Overtime-Recompute nach Offday fehlgeschlagen: {_e}")
    return {"ok": True, "id": assignment_id}


@router.delete("/shift-plan/{assignment_id}")
async def delete_shift_assignment(assignment_id: str, token: str = Query(...)):
    """Admin: Delete a shift assignment.
    Wenn das Assignment ein Offday war, wird der Tag automatisch wieder
    auf das Offday-Konto zurueckgebucht (release) UND das Stundenkonto neu
    berechnet (weil Offday-Status wegfaellt -> Soll wird wieder abgezogen)."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    # Vor dem Loeschen: Eintrag laden, um Offday-Status zu erkennen
    prev = await db.shift_assignments.find_one({"id": assignment_id}, {"_id": 0})
    await db.shift_assignments.delete_one({"id": assignment_id})
    if prev and prev.get("is_offday"):
        try:
            from routes.offdays import release_offday_for_assignment
            await release_offday_for_assignment(assignment_id)
        except Exception as _e:
            logger.warning(f"Offday release fehlgeschlagen: {_e}")
        try:
            y = int(str(prev.get("date") or "")[:4])
            await _recompute_overtime_for_year(prev.get("user_id"), y)
        except Exception as _e:
            logger.warning(f"Overtime-Recompute nach Offday-Delete fehlgeschlagen: {_e}")
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
    if not _has_verwaltung(caller):
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
    if not _has_verwaltung(caller):
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



@router.get("/shift-plan/debug-user-plan/{user_id}")
async def debug_user_plan(user_id: str, token: str = Query(...)):
    """Admin-only: Diagnose-Endpoint. Simuliert was ein bestimmter Mitarbeiter
    in seiner my-plan-Ansicht sehen wuerde - ohne Mitarbeiter-Passwort.
    Zeigt zusaetzlich ALLE Assignments (auch nicht released, auch ausserhalb
    aktuelle/naechste Woche), damit Bug-Diagnose moeglich ist."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")

    from datetime import timedelta
    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())
    current_week = monday.strftime("%G-W%V")
    next_week = (monday + timedelta(days=7)).strftime("%G-W%V")

    released = []
    async for r in db.shift_releases.find({}, {"_id": 0}).sort("week_key", -1):
        released.append(r)

    all_assignments = await db.shift_assignments.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("date", -1).to_list(500)

    released_keys_current_and_next = [
        r["week_key"] for r in released
        if r.get("week_key") in (current_week, next_week)
    ]
    visible = [a for a in all_assignments if a.get("week_key") in released_keys_current_and_next]

    return {
        "user": {"id": user.get("id"), "name": user.get("name"), "email": user.get("email")},
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
        "server_today_date": today.isoformat(),
        "current_week_key": current_week,
        "next_week_key": next_week,
        "all_releases": released,
        "all_assignments_for_user": all_assignments,
        "would_be_visible_in_my_plan": visible,
        "diagnostics": {
            "total_assignments": len(all_assignments),
            "visible_count": len(visible),
            "released_current_or_next": released_keys_current_and_next,
            "assignments_without_week_key": [a.get("id") for a in all_assignments if not a.get("week_key")],
        },
    }
