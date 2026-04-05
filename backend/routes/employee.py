from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
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
    try:
        from emergentintegrations.llm.chat import Chat, ChatMessage
        emergent_api_key = os.environ.get("EMERGENT_API_KEY", "")
        if not emergent_api_key:
            return

        b64 = base64.b64encode(file_bytes).decode("utf-8")
        label = DOCUMENT_LABELS.get(doc_type, doc_type)

        prompt = f"""Analysiere dieses Dokument ({label}).
Suche nach einem Ablaufdatum, Gültigkeitsdatum, "gültig bis" oder ähnlichem.
Antworte NUR im Format: YYYY-MM-DD
Falls kein Ablaufdatum gefunden wird, antworte NUR: KEINS
Keine weiteren Erklärungen."""

        chat = Chat(
            api_key=emergent_api_key,
            model="gemini-2.5-flash",
        )
        chat.history = [ChatMessage(role="user", text=prompt, images=[b64])]
        response = await chat.send_message_async("")
        text = response.text.strip()

        if text != "KEINS" and len(text) == 10 and text[4] == "-":
            await db.employee_documents.update_one(
                {"id": doc_id},
                {"$set": {"ai_expiry_date": text, "expiry_date": text}}
            )
            logger.info(f"AI detected expiry for {doc_id}: {text}")
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
