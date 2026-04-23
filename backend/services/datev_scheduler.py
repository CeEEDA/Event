"""DATEV Daily Batch Scheduler.

Every minute checks whether the configured DATEV_SEND_TIME (default 20:00 Europe/Berlin)
has been reached today. If yes and the daily batch has not yet run today, forwards all
documents flagged as `datev_pending=True` to their configured DATEV mailbox.

Runs as a background asyncio task, started from FastAPI's startup event.
"""
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None
_last_run_date: str | None = None     # YYYY-MM-DD (Europe/Berlin) of last successful batch
_last_run_stats: dict = {}
_last_run_at: datetime | None = None


def _berlin_now() -> datetime:
    """Current time in Europe/Berlin (handles CET/CEST automatically)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Berlin"))
    except Exception:
        # Fallback: UTC+1 (CET). Not perfect across DST, but acceptable for 20:00 trigger.
        return datetime.now(timezone(timedelta(hours=1)))


def _parse_send_time() -> tuple[int, int]:
    raw = os.environ.get("DATEV_SEND_TIME", "20:00").strip()
    try:
        h, m = raw.split(":", 1)
        return int(h), int(m)
    except Exception:
        logger.warning(f"DATEV_SEND_TIME '{raw}' ungueltig - nutze 20:00")
        return 20, 0


async def _run_batch_now() -> dict:
    """Forward all pending DATEV documents. Returns stats dict."""
    global _last_run_at, _last_run_stats
    _last_run_at = datetime.now(timezone.utc)
    stats = {"found": 0, "forwarded": 0, "errors": 0}

    # Late import to avoid circular dependency at module load
    from routes.documents import _forward_to_datev, _resolve_datev_target
    from server import db

    cursor = db.documents.find(
        {"datev_pending": True, "is_deleted": False},
        {"_id": 0, "id": 1, "storage_path": 1, "original_filename": 1, "content_type": 1,
         "ai_metadata": 1, "folder_id": 1}
    )
    docs = await cursor.to_list(length=1000)
    stats["found"] = len(docs)
    logger.info(f"DATEV-Batch: {len(docs)} pending Dokumente gefunden")

    for doc in docs:
        try:
            folder_id = doc.get("folder_id", "")
            if not _resolve_datev_target(folder_id):
                # Ordner nicht mehr routable (manuell verschoben) - pending-Flag entfernen
                await db.documents.update_one({"id": doc["id"]}, {"$set": {
                    "datev_pending": False,
                    "datev_skip_reason": f"Ordner {folder_id} nicht DATEV-routable",
                }})
                continue
            await _forward_to_datev(
                doc["id"],
                doc["storage_path"],
                doc["original_filename"],
                doc.get("content_type", "application/pdf"),
                doc.get("ai_metadata", {}),
                folder_id,
            )
            # _forward_to_datev setzt datev_forwarded=True, wir entfernen pending
            await db.documents.update_one({"id": doc["id"]}, {"$set": {"datev_pending": False}})
            stats["forwarded"] += 1
        except Exception as e:
            logger.error(f"DATEV-Batch: Dokument {doc.get('id')} fehlgeschlagen: {e}")
            stats["errors"] += 1

    _last_run_stats = stats
    return stats


async def _loop():
    """Check every 60 seconds if it is time to run. Runs at most once per day."""
    global _last_run_date
    send_h, send_m = _parse_send_time()
    logger.info(f"DATEV-Scheduler gestartet (Versandzeit: {send_h:02d}:{send_m:02d} Europe/Berlin)")
    while True:
        try:
            now = _berlin_now()
            today = now.strftime("%Y-%m-%d")
            if (now.hour, now.minute) >= (send_h, send_m) and _last_run_date != today:
                logger.info(f"DATEV-Batch wird ausgeloest (Tag {today}, {now:%H:%M} Europe/Berlin)")
                try:
                    await _run_batch_now()
                finally:
                    _last_run_date = today
        except Exception as e:
            logger.error(f"DATEV-Scheduler loop error: {e}")
        await asyncio.sleep(60)


def start_scheduler():
    """Start the daily batch scheduler task. Idempotent."""
    global _task
    if _task and not _task.done():
        return
    loop = asyncio.get_event_loop()
    _task = loop.create_task(_loop())


def get_status() -> dict:
    send_h, send_m = _parse_send_time()
    now = _berlin_now()
    return {
        "running": bool(_task and not _task.done()),
        "send_time": f"{send_h:02d}:{send_m:02d}",
        "timezone": "Europe/Berlin",
        "now_berlin": now.isoformat(),
        "last_run_date": _last_run_date,
        "last_run_at": _last_run_at.isoformat() if _last_run_at else None,
        "last_run_stats": _last_run_stats,
    }


async def trigger_now() -> dict:
    """Manually trigger the batch (admin endpoint)."""
    return await _run_batch_now()
