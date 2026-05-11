"""Einsatztagebuch (Order Diary):
Stoerungsmeldungen zu einem Auftrag protokollieren.

Endpunkte:
  GET    /api/orders/{order_pk}/diary
  POST   /api/orders/{order_pk}/diary
  POST   /api/orders/{order_pk}/diary/{entry_id}/resolve
  POST   /api/orders/{order_pk}/diary/{entry_id}/reopen
  PUT    /api/orders/{order_pk}/diary/{entry_id}
  DELETE /api/orders/{order_pk}/diary/{entry_id}

Schema mqtt-ueberlagerungsfrei: collection `order_diary_entries`
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import logging

router = APIRouter(prefix="/api/orders", tags=["order-diary"])
security = HTTPBearer()
logger = logging.getLogger("order_diary")

_db = None
_decode_jwt_token = None


def init_order_diary_routes(db, decode_jwt_token):
    global _db, _decode_jwt_token
    _db = db
    _decode_jwt_token = decode_jwt_token


async def _auth_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")
    return user


def _is_freelancer(user: dict) -> bool:
    return (user.get("role") or "").lower() == "freelancer"


def _freelancer_can_see(user: dict, order_pk: str) -> bool:
    assigned = [str(x) for x in (user.get("freelancer_orders") or [])]
    return str(order_pk) in assigned


class DiaryEntryCreate(BaseModel):
    caller_name: Optional[str] = ""
    caller_phone: Optional[str] = ""
    reason: str = Field(..., min_length=1)
    location: Optional[str] = ""


class DiaryEntryUpdate(BaseModel):
    caller_name: Optional[str] = None
    caller_phone: Optional[str] = None
    reason: Optional[str] = None
    location: Optional[str] = None


def _doc_to_response(d: dict) -> dict:
    return {
        "id": d["id"],
        "order_pk": d["order_pk"],
        "caller_name": d.get("caller_name") or "",
        "caller_phone": d.get("caller_phone") or "",
        "reason": d.get("reason") or "",
        "location": d.get("location") or "",
        "status": d.get("status") or "open",
        "created_at": d.get("created_at"),
        "created_by_user_id": d.get("created_by_user_id"),
        "created_by_name": d.get("created_by_name") or "",
        "resolved_at": d.get("resolved_at"),
        "resolved_by_user_id": d.get("resolved_by_user_id"),
        "resolved_by_name": d.get("resolved_by_name") or "",
    }


def _user_display(user: dict) -> str:
    return (user.get("full_name") or user.get("name") or user.get("email") or "").strip()


@router.get("/{order_pk}/diary")
async def list_diary(order_pk: str, user: dict = Depends(_auth_user)):
    """Liste aller Tagebuch-Eintraege zu einem Auftrag (chronologisch, neueste oben)."""
    if _is_freelancer(user) and not _freelancer_can_see(user, order_pk):
        raise HTTPException(status_code=403, detail="Keine Berechtigung fuer diesen Auftrag")
    rows = await _db.order_diary_entries.find(
        {"order_pk": str(order_pk)}, {"_id": 0}
    ).sort([("created_at", -1)]).to_list(500)
    open_count = sum(1 for r in rows if (r.get("status") or "open") == "open")
    resolved_count = sum(1 for r in rows if r.get("status") == "resolved")
    return {
        "total": len(rows),
        "open": open_count,
        "resolved": resolved_count,
        "entries": [_doc_to_response(r) for r in rows],
    }


@router.post("/{order_pk}/diary")
async def create_diary_entry(order_pk: str,
                              payload: DiaryEntryCreate,
                              user: dict = Depends(_auth_user)):
    """Neue Stoerungsmeldung anlegen."""
    if _is_freelancer(user) and not _freelancer_can_see(user, order_pk):
        raise HTTPException(status_code=403, detail="Keine Berechtigung fuer diesen Auftrag")
    if not (payload.reason or "").strip():
        raise HTTPException(status_code=400, detail="Grund/Beschreibung ist erforderlich")

    entry = {
        "id": str(uuid.uuid4()),
        "order_pk": str(order_pk),
        "caller_name": (payload.caller_name or "").strip(),
        "caller_phone": (payload.caller_phone or "").strip(),
        "reason": payload.reason.strip(),
        "location": (payload.location or "").strip(),
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by_user_id": user["id"],
        "created_by_name": _user_display(user),
        "resolved_at": None,
        "resolved_by_user_id": None,
        "resolved_by_name": "",
    }
    await _db.order_diary_entries.insert_one(entry)
    logger.info(
        f"Diary entry created order={order_pk} by {user.get('email')} reason='{entry['reason'][:60]}'"
    )
    return _doc_to_response(entry)


@router.post("/{order_pk}/diary/{entry_id}/resolve")
async def resolve_diary_entry(order_pk: str, entry_id: str,
                               user: dict = Depends(_auth_user)):
    """Markiere einen Eintrag als behoben."""
    if _is_freelancer(user) and not _freelancer_can_see(user, order_pk):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    entry = await _db.order_diary_entries.find_one(
        {"id": entry_id, "order_pk": str(order_pk)}, {"_id": 0}
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    if entry.get("status") == "resolved":
        return _doc_to_response(entry)
    now = datetime.now(timezone.utc).isoformat()
    await _db.order_diary_entries.update_one(
        {"id": entry_id, "order_pk": str(order_pk)},
        {"$set": {
            "status": "resolved",
            "resolved_at": now,
            "resolved_by_user_id": user["id"],
            "resolved_by_name": _user_display(user),
        }}
    )
    entry.update({
        "status": "resolved",
        "resolved_at": now,
        "resolved_by_user_id": user["id"],
        "resolved_by_name": _user_display(user),
    })
    return _doc_to_response(entry)


@router.post("/{order_pk}/diary/{entry_id}/reopen")
async def reopen_diary_entry(order_pk: str, entry_id: str,
                              user: dict = Depends(_auth_user)):
    """Markiere einen behobenen Eintrag wieder als offen."""
    if _is_freelancer(user) and not _freelancer_can_see(user, order_pk):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    entry = await _db.order_diary_entries.find_one(
        {"id": entry_id, "order_pk": str(order_pk)}, {"_id": 0}
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    await _db.order_diary_entries.update_one(
        {"id": entry_id, "order_pk": str(order_pk)},
        {"$set": {"status": "open"},
         "$unset": {"resolved_at": "", "resolved_by_user_id": "", "resolved_by_name": ""}}
    )
    entry.update({
        "status": "open",
        "resolved_at": None,
        "resolved_by_user_id": None,
        "resolved_by_name": "",
    })
    return _doc_to_response(entry)


@router.put("/{order_pk}/diary/{entry_id}")
async def update_diary_entry(order_pk: str, entry_id: str,
                              payload: DiaryEntryUpdate,
                              user: dict = Depends(_auth_user)):
    """Bearbeite Felder eines Eintrags (Name/Tel/Grund/Ort)."""
    if _is_freelancer(user) and not _freelancer_can_see(user, order_pk):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    upd = {}
    for k in ("caller_name", "caller_phone", "reason", "location"):
        v = getattr(payload, k)
        if v is not None:
            upd[k] = v.strip() if isinstance(v, str) else v
    if not upd:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")
    if "reason" in upd and not upd["reason"]:
        raise HTTPException(status_code=400, detail="Grund darf nicht leer sein")
    res = await _db.order_diary_entries.update_one(
        {"id": entry_id, "order_pk": str(order_pk)},
        {"$set": upd}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    entry = await _db.order_diary_entries.find_one(
        {"id": entry_id, "order_pk": str(order_pk)}, {"_id": 0}
    )
    return _doc_to_response(entry)


@router.delete("/{order_pk}/diary/{entry_id}")
async def delete_diary_entry(order_pk: str, entry_id: str,
                              user: dict = Depends(_auth_user)):
    """Loesche einen Eintrag (nur Admin oder Ersteller)."""
    entry = await _db.order_diary_entries.find_one(
        {"id": entry_id, "order_pk": str(order_pk)}, {"_id": 0}
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    is_admin = (user.get("role") or "").lower() == "admin"
    is_owner = entry.get("created_by_user_id") == user["id"]
    if not (is_admin or is_owner):
        raise HTTPException(status_code=403, detail="Nur Admin oder Ersteller darf loeschen")
    await _db.order_diary_entries.delete_one(
        {"id": entry_id, "order_pk": str(order_pk)}
    )
    return {"message": "Eintrag geloescht", "id": entry_id}
