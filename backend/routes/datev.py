"""DATEV Scheduler admin endpoints."""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from services import datev_scheduler

router = APIRouter(prefix="/api/datev", tags=["datev"])


@router.get("/status")
async def status():
    """Zeigt Scheduler-Konfig (Versandzeit, letzte Ausfuehrung, Statistik)."""
    from server import db
    pending_count = await db.documents.count_documents({"datev_pending": True, "is_deleted": False})
    # Unmarkierte Rechnungen (weder pending noch forwarded) - werden ohne Backfill vergessen
    from routes.documents import DATEV_ROUTING
    prefixes = list(DATEV_ROUTING.keys())
    or_clauses = []
    for p in prefixes:
        or_clauses.append({"folder_id": p})
        or_clauses.append({"folder_id": {"$regex": f"^{p}_"}})
    unmarked_count = 0
    if or_clauses:
        unmarked_count = await db.documents.count_documents({
            "$or": or_clauses,
            "is_deleted": False,
            "datev_forwarded": {"$ne": True},
            "datev_pending": {"$ne": True},
        })
    data = datev_scheduler.get_status()
    data["pending_count"] = pending_count
    data["unmarked_count"] = unmarked_count
    return data


@router.post("/run-now")
async def run_now():
    """Batch manuell ausloesen (alle pending Rechnungen jetzt an DATEV)."""
    try:
        stats = await datev_scheduler.trigger_now()
        return {"ok": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backfill-pending")
async def backfill_pending(days: int = 90):
    """Findet Dokumente in DATEV-Rechnungs-Ordnern, die weder als 'forwarded'
    noch als 'pending' markiert sind, und setzt datev_pending=True. Standard:
    letzte 90 Tage. Nach Ausfuehrung greift der Abend-Batch (oder /run-now).
    """
    from server import db
    from routes.documents import DATEV_ROUTING

    prefixes = list(DATEV_ROUTING.keys())
    or_clauses = []
    for p in prefixes:
        or_clauses.append({"folder_id": p})
        or_clauses.append({"folder_id": {"$regex": f"^{p}_"}})

    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))).isoformat()

    query = {
        "$or": or_clauses,
        "is_deleted": False,
        "datev_forwarded": {"$ne": True},
        "datev_pending": {"$ne": True},
        "created_at": {"$gte": cutoff},
    }
    found = await db.documents.count_documents(query)
    if found == 0:
        return {"ok": True, "marked": 0, "message": "Keine ungetaggten Rechnungen gefunden."}

    result = await db.documents.update_many(query, {"$set": {
        "datev_pending": True,
        "datev_pending_since": datetime.now(timezone.utc).isoformat(),
        "datev_backfilled": True,
    }})
    return {"ok": True, "marked": result.modified_count, "message": f"{result.modified_count} Rechnungen als datev_pending markiert."}
