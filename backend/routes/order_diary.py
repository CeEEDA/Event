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
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import csv
import io
import re
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
    is_nachtrag: Optional[bool] = False
    assigned_trupp_ids: Optional[List[str]] = None


class DiaryEntryUpdate(BaseModel):
    caller_name: Optional[str] = None
    caller_phone: Optional[str] = None
    reason: Optional[str] = None
    location: Optional[str] = None
    is_nachtrag: Optional[bool] = None
    assigned_trupp_ids: Optional[List[str]] = None


def _doc_to_response(d: dict) -> dict:
    return {
        "id": d["id"],
        "order_pk": d["order_pk"],
        "caller_name": d.get("caller_name") or "",
        "caller_phone": d.get("caller_phone") or "",
        "reason": d.get("reason") or "",
        "location": d.get("location") or "",
        "status": d.get("status") or "open",
        "is_nachtrag": bool(d.get("is_nachtrag", False)),
        "assigned_trupp_ids": list(d.get("assigned_trupp_ids") or []),
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
        "is_nachtrag": bool(payload.is_nachtrag),
        "assigned_trupp_ids": [str(t) for t in (payload.assigned_trupp_ids or []) if t],
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
    if payload.is_nachtrag is not None:
        upd["is_nachtrag"] = bool(payload.is_nachtrag)
    if payload.assigned_trupp_ids is not None:
        upd["assigned_trupp_ids"] = [str(t) for t in payload.assigned_trupp_ids if t]
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


# ----------------------------------------------------------------------------
# Search & Export
# ----------------------------------------------------------------------------

# WICHTIG: Diese Routes liegen UNTER /api/orders/{order_pk}/diary/... -> Konflikt-frei
# durch eindeutige sub-paths "search-all" und "export.csv"

@router.get("/diary/search-all")
async def search_diary_global(q: str = Query(..., min_length=2),
                               limit: int = Query(50, ge=1, le=200),
                               user: dict = Depends(_auth_user)):
    """Volltextsuche ueber ALLE Einsatztagebuch-Eintraege (alle Auftraege).
    Sucht in: caller_name, caller_phone, reason, location, order_pk.
    Nur Admin & Disponent (Freelancer sehen nur eigene)."""
    q = q.strip()
    if not q:
        return {"q": q, "count": 0, "results": []}
    pattern = re.escape(q)
    base_filter = {
        "$or": [
            {"caller_name": {"$regex": pattern, "$options": "i"}},
            {"caller_phone": {"$regex": pattern, "$options": "i"}},
            {"reason": {"$regex": pattern, "$options": "i"}},
            {"location": {"$regex": pattern, "$options": "i"}},
            {"order_pk": {"$regex": pattern, "$options": "i"}},
        ]
    }
    if _is_freelancer(user):
        allowed = [str(x) for x in (user.get("freelancer_orders") or [])]
        if not allowed:
            return {"q": q, "count": 0, "results": []}
        base_filter = {"$and": [base_filter, {"order_pk": {"$in": allowed}}]}
    rows = await _db.order_diary_entries.find(
        base_filter, {"_id": 0}
    ).sort([("created_at", -1)]).to_list(limit)

    # Reichere mit Auftrags-Namen an
    order_pks = list(set(r["order_pk"] for r in rows))
    orders_map = {}
    if order_pks:
        # Probiere primary_key Schluessel; einige sind int, manche string
        try:
            order_pks_int = [int(p) for p in order_pks if str(p).isdigit()]
        except Exception:
            order_pks_int = []
        order_docs = await _db.orders_cache.find(
            {"$or": [
                {"primary_key": {"$in": order_pks}},
                {"primary_key": {"$in": order_pks_int}} if order_pks_int else {},
            ]},
            {"_id": 0, "primary_key": 1, "order_no": 1, "address": 1, "contact_name": 1}
        ).to_list(500)
        for o in order_docs:
            orders_map[str(o.get("primary_key"))] = {
                "order_no": o.get("order_no") or "",
                "address": o.get("address") or "",
                "contact_name": o.get("contact_name") or "",
            }
    results = []
    for r in rows:
        d = _doc_to_response(r)
        info = orders_map.get(str(r["order_pk"]), {})
        d["order_no"] = info.get("order_no", "")
        d["order_address"] = info.get("address", "")
        d["order_contact"] = info.get("contact_name", "")
        results.append(d)
    return {"q": q, "count": len(results), "results": results}


@router.get("/{order_pk}/diary/export.csv")
async def export_diary_csv(order_pk: str, user: dict = Depends(_auth_user)):
    """Exportiere alle Eintraege eines Auftrags als CSV (UTF-8 BOM, Semikolon-Trenner)."""
    if _is_freelancer(user) and not _freelancer_can_see(user, order_pk):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    rows = await _db.order_diary_entries.find(
        {"order_pk": str(order_pk)}, {"_id": 0}
    ).sort([("created_at", 1)]).to_list(2000)

    buf = io.StringIO()
    buf.write("\ufeff")  # UTF-8 BOM fuer Excel
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "Datum", "Uhrzeit", "Status", "Nachtrag",
        "Anrufer", "Telefon", "Standort", "Grund",
        "Erfasst von", "Behoben am", "Behoben durch", "Eintrag-ID"
    ])
    for r in rows:
        try:
            dt = datetime.fromisoformat((r.get("created_at") or "").replace("Z", "+00:00"))
            date_str = dt.strftime("%d.%m.%Y")
            time_str = dt.strftime("%H:%M:%S")
        except Exception:
            date_str = r.get("created_at", "")
            time_str = ""
        resolved_at = ""
        if r.get("resolved_at"):
            try:
                dt2 = datetime.fromisoformat(r["resolved_at"].replace("Z", "+00:00"))
                resolved_at = dt2.strftime("%d.%m.%Y %H:%M")
            except Exception:
                resolved_at = r["resolved_at"]
        writer.writerow([
            date_str, time_str,
            "Behoben" if r.get("status") == "resolved" else "Offen",
            "Ja" if r.get("is_nachtrag") else "Nein",
            r.get("caller_name", ""),
            r.get("caller_phone", ""),
            r.get("location", ""),
            (r.get("reason", "") or "").replace("\n", " "),
            r.get("created_by_name", ""),
            resolved_at,
            r.get("resolved_by_name", ""),
            r.get("id", ""),
        ])
    csv_bytes = buf.getvalue().encode("utf-8")
    filename = f"einsatztagebuch_auftrag_{order_pk}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================================================
# TRUPPS (Teams) - pro Auftrag
# ============================================================================
# Collection: `order_trupps`
# Schema: { id, order_pk, name, members: [str x <=4], created_at, created_by_user_id }
# Status (unterwegs/verfuegbar) ist ABGELEITET aus offenen Diary-Eintraegen.

class TruppPayload(BaseModel):
    name: Optional[str] = None
    members: Optional[List[str]] = None  # max 4


def _trupp_doc_to_response(d: dict, busy_ids: set) -> dict:
    return {
        "id": d["id"],
        "order_pk": d["order_pk"],
        "name": d.get("name") or "",
        "members": [(m or "").strip() for m in (d.get("members") or [])],
        "is_busy": d["id"] in busy_ids,
        "created_at": d.get("created_at"),
    }


async def _compute_busy_trupps(order_pk: str) -> set:
    """Welche Trupp-IDs sind aktuell auf einer offenen Stoerung gebunden?"""
    cursor = _db.order_diary_entries.find(
        {"order_pk": str(order_pk), "status": "open"},
        {"_id": 0, "assigned_trupp_ids": 1}
    )
    busy = set()
    async for row in cursor:
        for tid in (row.get("assigned_trupp_ids") or []):
            busy.add(str(tid))
    return busy


@router.get("/{order_pk}/trupps")
async def list_trupps(order_pk: str, user: dict = Depends(_auth_user)):
    """Liste aller Trupps zu einem Auftrag (inkl. aktueller Status: verfuegbar/unterwegs)."""
    if _is_freelancer(user) and not _freelancer_can_see(user, order_pk):
        raise HTTPException(status_code=403, detail="Keine Berechtigung fuer diesen Auftrag")
    rows = await _db.order_trupps.find(
        {"order_pk": str(order_pk)}, {"_id": 0}
    ).sort([("created_at", 1)]).to_list(200)
    busy = await _compute_busy_trupps(order_pk)
    return {
        "total": len(rows),
        "trupps": [_trupp_doc_to_response(r, busy) for r in rows],
    }


@router.post("/{order_pk}/trupps")
async def create_trupp(order_pk: str,
                        payload: TruppPayload,
                        user: dict = Depends(_auth_user)):
    """Neuen Trupp anlegen. Wenn kein Name angegeben, wird 'Trupp N' automatisch vergeben."""
    if _is_freelancer(user) and not _freelancer_can_see(user, order_pk):
        raise HTTPException(status_code=403, detail="Keine Berechtigung fuer diesen Auftrag")
    name = (payload.name or "").strip()
    if not name:
        # Auto-Nummerierung: zaehle bestehende Trupps zu diesem Auftrag
        existing_count = await _db.order_trupps.count_documents({"order_pk": str(order_pk)})
        name = f"Trupp {existing_count + 1}"
    members = [(m or "").strip() for m in (payload.members or [])][:4]
    trupp = {
        "id": str(uuid.uuid4()),
        "order_pk": str(order_pk),
        "name": name,
        "members": members,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by_user_id": user["id"],
    }
    await _db.order_trupps.insert_one(trupp)
    logger.info(f"Trupp created order={order_pk} name='{name}' by {user.get('email')}")
    return _trupp_doc_to_response(trupp, set())


@router.put("/{order_pk}/trupps/{trupp_id}")
async def update_trupp(order_pk: str, trupp_id: str,
                        payload: TruppPayload,
                        user: dict = Depends(_auth_user)):
    """Trupp-Name oder Mitglieder bearbeiten."""
    if _is_freelancer(user) and not _freelancer_can_see(user, order_pk):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    upd = {}
    if payload.name is not None:
        n = payload.name.strip()
        if not n:
            raise HTTPException(status_code=400, detail="Name darf nicht leer sein")
        upd["name"] = n
    if payload.members is not None:
        upd["members"] = [(m or "").strip() for m in payload.members][:4]
    if not upd:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")
    res = await _db.order_trupps.update_one(
        {"id": trupp_id, "order_pk": str(order_pk)},
        {"$set": upd}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Trupp nicht gefunden")
    doc = await _db.order_trupps.find_one(
        {"id": trupp_id, "order_pk": str(order_pk)}, {"_id": 0}
    )
    busy = await _compute_busy_trupps(order_pk)
    return _trupp_doc_to_response(doc, busy)


@router.delete("/{order_pk}/trupps/{trupp_id}")
async def delete_trupp(order_pk: str, trupp_id: str,
                        user: dict = Depends(_auth_user)):
    """Trupp loeschen (entfernt ihn auch aus allen Diary-Eintraegen)."""
    if _is_freelancer(user) and not _freelancer_can_see(user, order_pk):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    res = await _db.order_trupps.delete_one(
        {"id": trupp_id, "order_pk": str(order_pk)}
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Trupp nicht gefunden")
    # Aus allen Diary-Eintraegen entfernen
    await _db.order_diary_entries.update_many(
        {"order_pk": str(order_pk), "assigned_trupp_ids": trupp_id},
        {"$pull": {"assigned_trupp_ids": trupp_id}}
    )
    return {"message": "Trupp geloescht", "id": trupp_id}
