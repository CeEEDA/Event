"""Verbandsbuch (Workplace first-aid logbook).

Pflicht nach DGUV Vorschrift 1 / §24 Abs. 6 SGB VII: Arbeitgeber muss jede Erste-Hilfe-
Leistung dokumentieren. Das Verbandsbuch muss 5 Jahre aufbewahrt werden.

Datenschutz: Nur Admins dürfen alle Einträge lesen. Mitarbeiter dürfen eigene Einträge
anlegen (als Betroffener ODER Meldender).
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/api/verbandsbuch", tags=["verbandsbuch"])
security = HTTPBearer()

_db = None
_decode_jwt_token = None


def init_verbandsbuch_routes(db, decode_jwt_token):
    global _db, _decode_jwt_token
    _db = db
    _decode_jwt_token = decode_jwt_token


async def _auth_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")
    return user


async def _require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await _auth_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Administratoren dürfen das Verbandsbuch einsehen")
    return user


async def _next_lfd_nr() -> int:
    """Get next consecutive Lfd. Nr. (starts at 1)."""
    pipeline = [
        {"$group": {"_id": None, "max": {"$max": "$lfd_nr"}}},
    ]
    results = await _db.verbandsbuch.aggregate(pipeline).to_list(1)
    if results and results[0].get("max"):
        return int(results[0]["max"]) + 1
    return 1


class VerbandsbuchCreate(BaseModel):
    injured_name: str  # Vorname, Name
    injured_address: Optional[str] = ""  # Anschrift
    event_date: str  # YYYY-MM-DD
    event_time: str  # HH:MM
    location: str  # Ort (Raum/Bereich)
    hergang: str  # Hergang des Unfalls
    injury_type: str  # Art und Umfang der Verletzung
    witnesses: Optional[str] = ""  # freies Zeugen-Feld
    first_aider: Optional[str] = ""  # Ersthelfer
    notes: Optional[str] = ""


class VerbandsbuchUpdate(BaseModel):
    injured_name: Optional[str] = None
    injured_address: Optional[str] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    location: Optional[str] = None
    hergang: Optional[str] = None
    injury_type: Optional[str] = None
    witnesses: Optional[str] = None
    first_aider: Optional[str] = None
    notes: Optional[str] = None


@router.post("")
async def create_entry(payload: VerbandsbuchCreate, user=Depends(_auth_user)):
    """Any authenticated user can create an entry (self or colleague)."""
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": str(uuid.uuid4()),
        "lfd_nr": await _next_lfd_nr(),
        "injured_name": payload.injured_name.strip(),
        "injured_address": (payload.injured_address or "").strip(),
        "event_date": payload.event_date,
        "event_time": payload.event_time,
        "location": payload.location.strip(),
        "hergang": payload.hergang.strip(),
        "injury_type": payload.injury_type.strip(),
        "witnesses": (payload.witnesses or "").strip(),
        "first_aider": (payload.first_aider or "").strip(),
        "notes": (payload.notes or "").strip(),
        "reporter_user_id": user["id"],
        "reporter_name": user.get("name") or user.get("email"),
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
    }
    await _db.verbandsbuch.insert_one(entry)
    return {k: v for k, v in entry.items() if k != "_id"}


@router.get("")
async def list_entries(user=Depends(_require_admin)):
    """Admin only: list all entries sorted by lfd_nr desc (newest first)."""
    items = []
    async for doc in _db.verbandsbuch.find({"is_deleted": False}, {"_id": 0}).sort("lfd_nr", -1):
        items.append(doc)
    return {"entries": items, "total": len(items)}


@router.get("/{entry_id}")
async def get_entry(entry_id: str, user=Depends(_require_admin)):
    entry = await _db.verbandsbuch.find_one({"id": entry_id, "is_deleted": False}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return entry


@router.patch("/{entry_id}")
async def update_entry(entry_id: str, payload: VerbandsbuchUpdate, user=Depends(_require_admin)):
    update = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Keine Änderungen")
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await _db.verbandsbuch.update_one({"id": entry_id, "is_deleted": False}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    entry = await _db.verbandsbuch.find_one({"id": entry_id}, {"_id": 0})
    return entry


@router.delete("/{entry_id}")
async def delete_entry(entry_id: str, user=Depends(_require_admin)):
    """Soft delete (Verbandsbuch muss 5 Jahre aufbewahrt werden, aber Admin darf fehlerhafte Einträge ausblenden)."""
    result = await _db.verbandsbuch.update_one(
        {"id": entry_id, "is_deleted": False},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc).isoformat(), "deleted_by": user["id"]}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return {"success": True}
