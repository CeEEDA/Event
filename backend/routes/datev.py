"""DATEV Scheduler admin endpoints."""
from fastapi import APIRouter, HTTPException
from services import datev_scheduler

router = APIRouter(prefix="/api/datev", tags=["datev"])


@router.get("/status")
async def status():
    """Zeigt Scheduler-Konfig (Versandzeit, letzte Ausfuehrung, Statistik)."""
    from server import db
    pending_count = await db.documents.count_documents({"datev_pending": True, "is_deleted": False})
    data = datev_scheduler.get_status()
    data["pending_count"] = pending_count
    return data


@router.post("/run-now")
async def run_now():
    """Batch manuell ausloesen (alle pending Rechnungen jetzt an DATEV)."""
    try:
        stats = await datev_scheduler.trigger_now()
        return {"ok": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
