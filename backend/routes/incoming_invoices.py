"""Eingangsrechnungen-Modul.

Aggregiert alle Dokumente aus Rechnungseingang-Ordnern (rechnungseingang_*)
mit den KI/Heuristik-extrahierten Metadaten (Absender, Rechnungsnummer, Betrag,
Datum, Faelligkeit) und einem eigenen Bezahlt-Status.

Statuslogik:
- paid: manuell auf bezahlt gesetzt (oder via FinTS-Match)
- overdue: due_date liegt in der Vergangenheit und nicht bezahlt
- open: sonst
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Query
from server import db
from routes.employee import _get_user, _has_verwaltung

router = APIRouter(prefix="/api/incoming-invoices", tags=["incoming-invoices"])


def _parse_date(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


@router.get("")
async def list_incoming_invoices(token: str = Query(...)):
    """Liste aller Eingangsrechnungen aus allen rechnungseingang_*-Ordnern."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")

    docs = await db.documents.find(
        {"folder_id": {"$regex": "^rechnungseingang_"}, "is_deleted": False},
        {"_id": 0, "id": 1, "original_filename": 1, "folder_id": 1,
         "ai_metadata": 1, "created_at": 1,
         "eingang_paid": 1, "eingang_paid_at": 1, "eingang_paid_source": 1,
         "eingang_due_date_override": 1, "eingang_notes": 1}
    ).sort("created_at", -1).to_list(2000)

    today = datetime.now(timezone.utc).date()
    result = []
    for d in docs:
        meta = d.get("ai_metadata") or {}
        inv_date = _parse_date(meta.get("date"))
        # Faelligkeit: 1. Override, 2. AI due_date, 3. Rechnungsdatum + 14 Tage
        due_date = _parse_date(d.get("eingang_due_date_override")) or _parse_date(meta.get("due_date"))
        if not due_date and inv_date:
            due_date = inv_date + timedelta(days=14)

        paid = bool(d.get("eingang_paid"))
        if paid:
            status = "paid"
        elif due_date and due_date < today:
            status = "overdue"
        else:
            status = "open"

        try:
            amount = float(meta.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0

        result.append({
            "id": d["id"],
            "filename": d.get("original_filename") or "",
            "folder_id": d.get("folder_id"),
            "sender": meta.get("sender") or "",
            "invoice_number": meta.get("invoice_number") or "",
            "invoice_date": inv_date.isoformat() if inv_date else None,
            "due_date": due_date.isoformat() if due_date else None,
            "amount": amount,
            "currency": meta.get("currency") or "EUR",
            "iban": meta.get("iban") or "",
            "status": status,
            "paid": paid,
            "paid_at": d.get("eingang_paid_at"),
            "paid_source": d.get("eingang_paid_source"),
            "notes": d.get("eingang_notes") or "",
            "created_at": d.get("created_at"),
        })

    # Sortierung: overdue zuerst, dann open (mit naechster Faelligkeit), dann paid
    def _sort_key(r):
        st_order = {"overdue": 0, "open": 1, "paid": 2}.get(r["status"], 3)
        due = r.get("due_date") or "9999-12-31"
        return (st_order, due)

    result.sort(key=_sort_key)

    # Summary
    open_amount = sum(r["amount"] for r in result if r["status"] == "open")
    overdue_amount = sum(r["amount"] for r in result if r["status"] == "overdue")
    paid_amount = sum(r["amount"] for r in result if r["status"] == "paid")

    return {
        "invoices": result,
        "summary": {
            "total_count": len(result),
            "open_count": sum(1 for r in result if r["status"] == "open"),
            "overdue_count": sum(1 for r in result if r["status"] == "overdue"),
            "paid_count": sum(1 for r in result if r["status"] == "paid"),
            "open_amount": round(open_amount, 2),
            "overdue_amount": round(overdue_amount, 2),
            "paid_amount": round(paid_amount, 2),
        }
    }


@router.post("/{doc_id}/mark-paid")
async def mark_paid(doc_id: str, token: str = Query(...), paid: bool = Query(True)):
    """Markiert eine Eingangsrechnung manuell als bezahlt (oder revert)."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    now = datetime.now(timezone.utc).isoformat()
    update = {"eingang_paid": paid}
    if paid:
        update["eingang_paid_at"] = now
        update["eingang_paid_source"] = f"manuell ({caller.get('name', 'admin')})"
    else:
        update["eingang_paid_at"] = None
        update["eingang_paid_source"] = None
    res = await db.documents.update_one({"id": doc_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    return {"ok": True, "paid": paid}


@router.patch("/{doc_id}")
async def update_incoming(doc_id: str, token: str = Query(...),
                           due_date: str = Query(None), notes: str = Query(None)):
    """Manuelles Anpassen von Faelligkeit oder Notiz."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    update = {}
    if due_date is not None:
        update["eingang_due_date_override"] = due_date or None
    if notes is not None:
        update["eingang_notes"] = notes
    if not update:
        return {"ok": True, "no_changes": True}
    await db.documents.update_one({"id": doc_id}, {"$set": update})
    return {"ok": True}
