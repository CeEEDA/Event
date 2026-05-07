"""
Tankwagen Raw Stream
====================
Live-Debug-Helper fuer den Tankwagen-Pi. Der Pi pusht alle empfangenen UND
gesendeten Bytes (RX/TX) inklusive Timestamp + Pi-ID in einen Ringbuffer im
Backend. Eine Frontend-Seite tail't den Stream live und zeigt parallel den
zuletzt geparsten Beleg, sodass man ohne SSH-Session direkt sieht:
  - Welche Polls schickt Sening?
  - Welche Status-Bytes antworten wir?
  - Was hat unser Parser daraus gemacht?

Skalierung:
  - Pro Eintrag wenige Bytes (hex string + meta) -> bei 5 Hz Polls ~30 KB/h
  - TTL-Index sorgt dafuer, dass Eintraege nach 24 h automatisch geloescht werden
  - max 5000 Eintraege pro Pi (Pruning beim Insert)

API:
  POST /api/system/tankwagen/raw-stream/push   (vom Pi, anonym/Pi-ID auth)
  GET  /api/system/tankwagen/raw-stream/tail   (vom Frontend)
  DELETE /api/system/tankwagen/raw-stream      (Frontend - Stream leeren)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("tankwagen_raw_stream")
router = APIRouter(prefix="/api/system/tankwagen/raw-stream", tags=["Tankwagen Raw Stream"])

_db = None
_decode_jwt = None
_index_initialized = False


def init_tankwagen_raw_stream_routes(db, decode_jwt_token):
    """Wird in server.py nach dem Import aufgerufen."""
    global _db, _decode_jwt
    _db = db
    _decode_jwt = decode_jwt_token


async def _ensure_indexes():
    """Erstellt TTL- und Query-Indizes lazy beim ersten Request.
    init_*-Hook ist sync, motor braucht awaitable Calls -> erst zur Laufzeit."""
    global _index_initialized
    if _index_initialized or _db is None:
        return
    try:
        # TTL: nach 24h auto-loeschen
        await _db.tankwagen_raw_stream.create_index("created_at", expireAfterSeconds=86400)
        await _db.tankwagen_raw_stream.create_index([("pi_id", 1), ("ts", -1)])
        _index_initialized = True
        logger.info("tankwagen_raw_stream Indizes ok")
    except Exception as e:
        logger.warning(f"Index-Setup fehlgeschlagen: {e}")


# ===== Models =====

class RawChunk(BaseModel):
    ts: float = Field(..., description="Unix-Timestamp (Sekunden) wann der Chunk aufgenommen wurde")
    direction: str = Field(..., description="'rx' = vom Sening empfangen, 'tx' = vom Pi gesendet")
    hex: str = Field(..., description="Hex-String der Bytes (mit oder ohne Leerzeichen)")
    note: Optional[str] = Field(None, description="Optional: kurze Annotation z.B. 'DLE EOT 4 reply'")


class PushRequest(BaseModel):
    pi_id: str
    hostname: Optional[str] = ""
    chunks: List[RawChunk]


# ===== Endpoints =====

@router.post("/push")
async def push_chunks(req: PushRequest):
    """Pi pushed eine Batch von RX/TX-Chunks.
    Anonym (kein Auth) - nur durch Pi-ID identifiziert. Wir akzeptieren ALLE
    Pi-IDs damit ein neu provisionierter Test-Pi sofort streamen kann.
    """
    if _db is None:
        raise HTTPException(503, "DB not initialized")
    await _ensure_indexes()
    if not req.chunks:
        return {"accepted": 0}

    now = datetime.now(timezone.utc)
    docs = []
    for c in req.chunks:
        # Hex normalisieren (Leerzeichen entfernen, lowercase)
        hex_clean = "".join(c.hex.split()).lower()
        if not hex_clean:
            continue
        docs.append({
            "pi_id": req.pi_id,
            "hostname": req.hostname or "",
            "ts": float(c.ts),
            "direction": c.direction,
            "hex": hex_clean,
            "note": c.note or None,
            "created_at": now,
        })
    if not docs:
        return {"accepted": 0}

    await _db.tankwagen_raw_stream.insert_many(docs)

    # Pruning: pro Pi max 5000 neueste Eintraege behalten (Burst-Schutz,
    # TTL-Index macht den Rest auf laengere Sicht)
    try:
        count = await _db.tankwagen_raw_stream.count_documents({"pi_id": req.pi_id})
        if count > 5000:
            cursor = _db.tankwagen_raw_stream.find(
                {"pi_id": req.pi_id}, {"ts": 1}
            ).sort("ts", -1).limit(5000)
            newest = await cursor.to_list(length=5000)
            if newest:
                cutoff_ts = newest[-1]["ts"]
                await _db.tankwagen_raw_stream.delete_many({
                    "pi_id": req.pi_id,
                    "ts": {"$lt": cutoff_ts},
                })
    except Exception as e:
        logger.debug(f"Pruning fehlgeschlagen (ignoriert): {e}")

    return {"accepted": len(docs)}


@router.get("/tail")
async def tail_stream(
    pi_id: Optional[str] = Query(None, description="Filter auf einen bestimmten Pi"),
    since_ts: Optional[float] = Query(None, description="Nur Eintraege mit ts > since_ts"),
    limit: int = Query(500, ge=1, le=5000),
):
    """Liefert die juengsten N Stream-Eintraege (oder alles seit since_ts).
    Frontend pollt mit dem letzten gesehenen ts -> Long-Polling-Light.
    """
    if _db is None:
        raise HTTPException(503, "DB not initialized")
    await _ensure_indexes()

    q = {}
    if pi_id:
        q["pi_id"] = pi_id
    if since_ts is not None:
        q["ts"] = {"$gt": float(since_ts)}

    cursor = _db.tankwagen_raw_stream.find(q, {"_id": 0}).sort("ts", 1).limit(limit)
    items = await cursor.to_list(length=limit)

    # Liste aller bekannten Pi-IDs (fuer Filter-Dropdown im Frontend)
    pi_cursor = _db.tankwagen_raw_stream.aggregate([
        {"$group": {
            "_id": "$pi_id",
            "hostname": {"$last": "$hostname"},
            "last_seen": {"$max": "$ts"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"last_seen": -1}},
        {"$limit": 20},
    ])
    pis = await pi_cursor.to_list(length=20)
    pi_list = [
        {
            "pi_id": p["_id"],
            "hostname": p.get("hostname") or "",
            "last_seen": p.get("last_seen"),
            "count": p.get("count", 0),
        }
        for p in pis
    ]

    return {
        "items": items,
        "pis": pi_list,
        "server_ts": datetime.now(timezone.utc).timestamp(),
    }


@router.delete("")
async def clear_stream(pi_id: Optional[str] = Query(None)):
    """Stream leeren - fuer Frontend 'Clear'-Button.
    Ohne pi_id: alle Eintraege loeschen.
    """
    if _db is None:
        raise HTTPException(503, "DB not initialized")
    q = {"pi_id": pi_id} if pi_id else {}
    res = await _db.tankwagen_raw_stream.delete_many(q)
    return {"deleted": res.deleted_count}
