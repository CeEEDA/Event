"""Mailbridge admin endpoints: status view + manual trigger for testing."""
import os
from fastapi import APIRouter, HTTPException
from services import mailbridge

router = APIRouter(prefix="/api/mailbridge", tags=["mailbridge"])


@router.get("/status")
async def status():
    """Return current Mailbridge configuration + last run info."""
    return mailbridge.get_status()


@router.post("/run-now")
async def run_now():
    """Trigger a single IMAP poll cycle immediately.
    Does nothing if IMAP_PASSWORD is not configured."""
    if not os.environ.get("IMAP_PASSWORD"):
        raise HTTPException(status_code=400, detail="IMAP_PASSWORD nicht gesetzt (.env)")
    stats = await mailbridge.trigger_now()
    return {"ok": True, "stats": stats}
