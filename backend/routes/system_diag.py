"""System-Diagnose fuer Slow-Drift-Debugging.

Endpoint: GET /api/system/health-diag  (Admin-only)
Log-Loop: alle 15 Min ein INFO-Log mit den wichtigsten Kennzahlen,
so dass ein Slow-Drift ueber Stunden sichtbar wird.

Wir messen bewusst nur was ohne Zusatz-Deps geht (stdlib + Motor):
- Prozess-RSS/VSZ (aus /proc/self/status)
- Anzahl offener File-Descriptors (/proc/self/fd)
- Prozess-Uptime
- asyncio-Tasks (Gesamtzahl + Gruppierung nach Name)
- MongoDB Ping-Latenz (ms) — steigt bei Pool-Erschoepfung deutlich
- MongoDB Pool-Config (maxPoolSize, waitQueueTimeoutMS)
- Anzahl bekannter MongoDB-Server + deren Health
"""
import asyncio
import logging
import os
import time
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from server import client, db, require_admin

logger = logging.getLogger("system_diag")
router = APIRouter(prefix="/api/system", tags=["system-diag"])

_START_TS = time.time()


def _read_proc_status() -> dict:
    """RSS/VSZ aus /proc/self/status (kein psutil noetig)."""
    out = {"rss_mb": None, "vsz_mb": None}
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    out["rss_mb"] = int(line.split()[1]) / 1024
                elif line.startswith("VmSize:"):
                    out["vsz_mb"] = int(line.split()[1]) / 1024
    except Exception:
        pass
    return out


def _count_fds() -> int | None:
    try:
        return len(os.listdir("/proc/self/fd"))
    except Exception:
        return None


def _task_stats() -> dict:
    """asyncio-Tasks aggregieren nach Name (erste 60 Zeichen)."""
    tasks = asyncio.all_tasks()
    by_name = Counter()
    for t in tasks:
        try:
            name = t.get_name()[:60]
        except Exception:
            name = "unknown"
        by_name[name] += 1
    top = by_name.most_common(15)
    return {
        "total": len(tasks),
        "top": [{"name": n, "count": c} for n, c in top],
    }


async def _mongo_ping_ms() -> float | None:
    try:
        t0 = time.perf_counter()
        await db.command("ping")
        return round((time.perf_counter() - t0) * 1000, 2)
    except Exception as e:
        logger.warning(f"mongo ping failed: {e}")
        return None


def _mongo_pool_config() -> dict:
    try:
        opts = client.options
        return {
            "maxPoolSize": opts.pool_options.max_pool_size,
            "minPoolSize": opts.pool_options.min_pool_size,
            "waitQueueTimeoutMS": opts.pool_options.wait_queue_timeout * 1000
                if opts.pool_options.wait_queue_timeout else None,
            "serverSelectionTimeoutMS": opts.server_selection_timeout * 1000
                if opts.server_selection_timeout else None,
        }
    except Exception as e:
        return {"error": str(e)}


def _mongo_topology() -> dict:
    try:
        td = client.topology_description
        servers = []
        for s in td.server_descriptions().values():
            servers.append({
                "address": f"{s.address[0]}:{s.address[1]}",
                "server_type": str(s.server_type_name),
                "rtt_ms": round(s.round_trip_time * 1000, 2) if s.round_trip_time else None,
            })
        return {"servers": servers}
    except Exception as e:
        return {"error": str(e)}


def _uptime_seconds() -> int:
    return int(time.time() - _START_TS)


async def _collect() -> dict:
    proc = _read_proc_status()
    ping_ms = await _mongo_ping_ms()
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": _uptime_seconds(),
        "process": {
            "rss_mb": proc["rss_mb"],
            "vsz_mb": proc["vsz_mb"],
            "fd_count": _count_fds(),
        },
        "asyncio": _task_stats(),
        "mongo": {
            "ping_ms": ping_ms,
            "pool_config": _mongo_pool_config(),
            "topology": _mongo_topology(),
        },
    }


@router.get("/health-diag")
async def health_diag(admin: dict = Depends(require_admin)):
    """Live-Diagnose fuer Slow-Drift-Analyse (Admin-only)."""
    return await _collect()


# ─────────────────────────────────────────────────────────────────────────────
# Log-Loop (alle 15 Min)
# ─────────────────────────────────────────────────────────────────────────────
_LOG_INTERVAL_SECONDS = 900  # 15 Min
_log_task: asyncio.Task | None = None


async def _log_loop():
    # Startup-Delay: erst 60 s nach App-Start loggen
    await asyncio.sleep(60)
    while True:
        try:
            snap = await _collect()
            proc = snap["process"]
            tasks = snap["asyncio"]
            mongo = snap["mongo"]
            logger.info(
                "[health-diag] rss=%sMB fd=%s tasks=%s mongo_ping=%sms uptime=%ss",
                round(proc["rss_mb"], 1) if proc["rss_mb"] else "?",
                proc["fd_count"],
                tasks["total"],
                mongo["ping_ms"],
                snap["uptime_seconds"],
            )
        except Exception as e:
            logger.warning(f"[health-diag] snapshot fehlgeschlagen: {e}")
        await asyncio.sleep(_LOG_INTERVAL_SECONDS)


def start_health_diag_logger():
    """Startet den 15-Min Log-Loop (wird von server.py aufgerufen)."""
    global _log_task
    if _log_task is None or _log_task.done():
        _log_task = asyncio.create_task(_log_loop(), name="health-diag-logger")
        logger.info("[health-diag] Log-Loop gestartet (alle 15 Min)")
