"""HalloPetra-Integration (KI-Telefonassistent fuer Handwerksbetriebe).

Empfaengt Webhooks von Petra (call.completed etc.), verifiziert die HMAC-Signatur
und wandelt qualifizierte Anrufe in Tasks in unserer Aufgabenliste um. Notruf-
Weiterleitung bleibt bei Petra (existiert dort schon), wir spiegeln den Notfall
nur zur Nachverfolgung als Hoch-Priority-Task.

Docs (Stand 2026-02, offiziell noch in Arbeit):
- Base-URL: https://api.hallopetra.de/api/v1
- Auth: konfigurierbar via HALLOPETRA_AUTH_HEADER + HALLOPETRA_API_TOKEN
- Webhook-Signatur: HMAC-SHA256 ueber den Raw-Body, Header X-Petra-Signature.
"""
import hashlib
import hmac
import logging
import os
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from server import db
from routes.employee import _get_user, _has_verwaltung

logger = logging.getLogger("hallopetra")

router = APIRouter(prefix="/api/hallopetra", tags=["hallopetra"])


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
def _config() -> dict:
    return {
        "client_id": os.environ.get("HALLOPETRA_CLIENT_ID", ""),
        "client_secret": os.environ.get("HALLOPETRA_CLIENT_SECRET", ""),
        "api_token": os.environ.get("HALLOPETRA_API_TOKEN", ""),
        "auth_header": os.environ.get("HALLOPETRA_AUTH_HEADER", "Authorization"),
        "auth_scheme": os.environ.get("HALLOPETRA_AUTH_SCHEME", "Bearer"),
        "webhook_secret": os.environ.get("HALLOPETRA_WEBHOOK_SECRET", ""),
        "base_url": os.environ.get("HALLOPETRA_BASE_URL", "https://api.hallopetra.de/api/v1"),
    }


def _is_configured(cfg: dict | None = None) -> bool:
    cfg = cfg or _config()
    # Fuer den Webhook-Empfang reicht das Webhook-Secret. Fuer Outbound-Aufrufe
    # brauchen wir ein API-Token ODER Client-ID+Secret.
    has_inbound = bool(cfg["webhook_secret"])
    has_outbound = bool(cfg["api_token"]) or bool(cfg["client_id"] and cfg["client_secret"])
    return has_inbound or has_outbound


async def _require_admin(token: str):
    caller = await _get_user(token)
    if not _has_verwaltung(caller) or caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    return caller


# ─────────────────────────────────────────────────────────────────────────────
# HMAC-Signaturpruefung (Webhook)
# ─────────────────────────────────────────────────────────────────────────────
def _verify_signature(body: bytes, signature_header: str | None, secret: str) -> bool:
    """Vergleicht X-Petra-Signature (HMAC-SHA256 hex) gegen erwartete Signatur.
    Konstante-Zeit-Vergleich, kein Timing-Leak."""
    if not signature_header or not secret:
        return False
    # Petra sendet moeglicherweise als "sha256=<hex>" (Github/Stripe-Style).
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature_header.strip()
    if provided.lower().startswith("sha256="):
        provided = provided.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


# ─────────────────────────────────────────────────────────────────────────────
# Task-Erzeugung aus qualifiziertem Anruf
# ─────────────────────────────────────────────────────────────────────────────
def _map_priority(qualification: dict) -> str:
    """Uebersetzt Petras Qualifikation in unser task.priority-Schema.
    Rueckgabe: 'urgent' | 'high' | 'normal' | 'low'."""
    if not qualification:
        return "normal"
    if qualification.get("is_emergency") or qualification.get("category") == "notfall":
        return "urgent"
    if qualification.get("urgency") in ("high", "hoch"):
        return "high"
    if qualification.get("urgency") in ("low", "niedrig"):
        return "low"
    return "normal"


def _is_qualified(call: dict) -> bool:
    """User-Vorgabe: NUR qualifizierte Anrufe werden zu Tasks.
    Kriterium: Petra hat ein 'qualification'-Objekt gesetzt UND category ist nicht 'spam'/'unqualified'."""
    q = call.get("qualification") or {}
    if not q:
        return False
    if q.get("category") in ("spam", "unqualified", "hangup", "wrong_number"):
        return False
    return True


async def _find_customer_by_phone(phone: str) -> dict | None:
    """Sucht Kunde per Telefonnummer in kunden-Collection (loose match)."""
    if not phone:
        return None
    # Normalize: nur Ziffern, letzte 8+ Stellen
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 6:
        return None
    tail = digits[-8:]
    # Suche via Regex am Ende
    doc = await db.kunden.find_one(
        {"$or": [
            {"telefon": {"$regex": tail + "$"}},
            {"mobil": {"$regex": tail + "$"}},
            {"phone": {"$regex": tail + "$"}},
        ]},
        {"_id": 0, "id": 1, "name": 1, "firma": 1},
    )
    return doc


async def _create_task_from_call(call: dict) -> dict:
    """Erzeugt eine Aufgabe in `tasks` aus einem Petra-Anruf-Event.
    Idempotent via petra_call_id: doppelte Webhooks fuegen keinen neuen Task an."""
    petra_call_id = call.get("id") or call.get("call_id")
    if not petra_call_id:
        raise ValueError("call.id / call_id fehlt")

    # Idempotenz-Check
    existing = await db.tasks.find_one({"petra_call_id": petra_call_id}, {"_id": 0})
    if existing:
        return {"created": False, "task_id": existing.get("id"), "reason": "duplicate"}

    q = call.get("qualification") or {}
    caller = call.get("caller") or {}
    caller_phone = caller.get("phone") or call.get("from")
    caller_name = caller.get("name") or "Unbekannt"

    customer = await _find_customer_by_phone(caller_phone) if caller_phone else None
    priority = _map_priority(q)
    is_emergency = priority == "urgent"

    subject = q.get("summary") or q.get("subject") or f"Anruf von {caller_name}"
    if is_emergency:
        subject = "🚨 NOTFALL: " + subject

    task = {
        "id": str(uuid.uuid4()),
        "type": "hallopetra_call",
        "petra_call_id": petra_call_id,
        "title": subject[:200],
        "description": (call.get("transcript_summary") or q.get("description") or "")[:2000],
        "priority": priority,
        "status": "open",
        "source": "hallopetra",
        "caller_name": caller_name,
        "caller_phone": caller_phone or "",
        "customer_id": (customer or {}).get("id"),
        "customer_name": (customer or {}).get("name") or (customer or {}).get("firma"),
        "category": q.get("category") or "call",
        "is_emergency": is_emergency,
        "petra_call_started_at": call.get("started_at"),
        "petra_call_ended_at": call.get("ended_at"),
        "petra_duration_seconds": call.get("duration_seconds"),
        "petra_recording_url": call.get("recording_url"),
        "petra_transcript_url": call.get("transcript_url"),
        "petra_full_payload": call,  # Full raw payload fuer spaetere Auswertung
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tasks.insert_one(task)
    logger.info(f"HalloPetra: Task {task['id']} erstellt "
                f"(petra_call={petra_call_id}, priority={priority}, customer={task['customer_id']})")
    return {"created": True, "task_id": task["id"], "priority": priority,
            "customer_matched": bool(customer)}


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint: Webhook (Petra → uns)
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/webhook")
async def receive_webhook(request: Request):
    """Empfaengt Petra-Events. Signatur wird per HMAC-SHA256 gegen
    HALLOPETRA_WEBHOOK_SECRET verifiziert."""
    body = await request.body()
    signature = (request.headers.get("X-Petra-Signature")
                 or request.headers.get("X-Hallopetra-Signature")
                 or request.headers.get("X-Signature"))
    cfg = _config()

    # Signatur-Check (skippen falls kein Secret gesetzt -> nur fuer Dev/Tests!)
    if cfg["webhook_secret"]:
        if not _verify_signature(body, signature, cfg["webhook_secret"]):
            logger.warning("HalloPetra Webhook: ungueltige Signatur")
            raise HTTPException(status_code=401, detail="invalid signature")
    else:
        logger.warning("HalloPetra Webhook: KEIN Secret konfiguriert - Signatur NICHT geprueft!")

    try:
        import json
        payload = json.loads(body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid json: {e}")

    event = payload.get("event") or payload.get("type") or "unknown"
    logger.info(f"HalloPetra Webhook empfangen: event={event}")

    # Rohes Event immer loggen (fuer Audit + spaeter Analyse)
    await db.hallopetra_events.insert_one({
        "id": str(uuid.uuid4()),
        "event": event,
        "payload": payload,
        "signature_ok": bool(cfg["webhook_secret"] and _verify_signature(body, signature, cfg["webhook_secret"])),
        "received_at": datetime.now(timezone.utc).isoformat(),
    })

    result = {"ok": True, "event": event}
    if event in ("call.completed", "call.qualified"):
        call = payload.get("call") or payload.get("data") or payload
        # User-Vorgabe: Nur qualifizierte Anrufe → Task. Notruf laeuft weiter bei Petra.
        if _is_qualified(call):
            task_res = await _create_task_from_call(call)
            result["task"] = task_res
        else:
            result["skipped"] = "not qualified"
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint: Admin-Panel Status + Test
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/status")
async def status(token: str = Query(...)):
    await _require_admin(token)
    cfg = _config()
    # Statistik letzte 7 Tage
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    events_count = await db.hallopetra_events.count_documents({"received_at": {"$gte": since}})
    tasks_count = await db.tasks.count_documents(
        {"source": "hallopetra", "created_at": {"$gte": since}}
    )
    emergency_count = await db.tasks.count_documents(
        {"source": "hallopetra", "is_emergency": True, "created_at": {"$gte": since}}
    )
    last_event = await db.hallopetra_events.find_one({}, sort=[("received_at", -1)])
    return {
        "configured": _is_configured(cfg),
        "webhook_secret_set": bool(cfg["webhook_secret"]),
        "api_token_set": bool(cfg["api_token"] or cfg["client_secret"]),
        "auth_header": cfg["auth_header"],
        "auth_scheme": cfg["auth_scheme"],
        "base_url": cfg["base_url"],
        "webhook_url": (os.environ.get("PUBLIC_URL", "").rstrip("/") + "/api/hallopetra/webhook") if os.environ.get("PUBLIC_URL") else "/api/hallopetra/webhook",
        "last_7d": {
            "events_received": events_count,
            "tasks_created": tasks_count,
            "emergencies": emergency_count,
        },
        "last_event_at": (last_event or {}).get("received_at"),
    }


@router.post("/test-outbound")
async def test_outbound(token: str = Query(...)):
    """Testet den Ausgehend-Aufruf gegen HalloPetra. Ruft base_url/ auf und
    liefert den HTTP-Status + Body zurueck."""
    await _require_admin(token)
    cfg = _config()
    if not (cfg["api_token"] or cfg["client_secret"]):
        return {"ok": False, "error": "Kein Token/Secret gesetzt. HALLOPETRA_API_TOKEN oder HALLOPETRA_CLIENT_SECRET in .env eintragen."}
    token_value = cfg["api_token"] or cfg["client_secret"]
    header_val = f"{cfg['auth_scheme']} {token_value}".strip() if cfg["auth_scheme"] else token_value
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(cfg["base_url"] + "/", headers={cfg["auth_header"]: header_val})
        return {
            "ok": resp.status_code < 400,
            "status_code": resp.status_code,
            "body_preview": resp.text[:500],
            "url": str(resp.url),
            "auth_header_used": cfg["auth_header"],
            "auth_scheme_used": cfg["auth_scheme"],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:500]}


class SimulateEvent(BaseModel):
    is_emergency: bool = False
    caller_name: str = "Max Mustermann"
    caller_phone: str = "+49 30 12345678"
    summary: str = "Testanruf - Heizung ausgefallen"


@router.post("/simulate-call")
async def simulate_call(data: SimulateEvent, token: str = Query(...)):
    """Simuliert einen qualifizierten Anruf-Webhook lokal (ohne Signatur-Check).
    Nuetzlich zum End-to-End-Test bevor Petra live geschaltet ist."""
    await _require_admin(token)
    fake_call = {
        "id": f"test-{uuid.uuid4()}",
        "caller": {"name": data.caller_name, "phone": data.caller_phone},
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": 42,
        "qualification": {
            "category": "notfall" if data.is_emergency else "auftrag",
            "is_emergency": data.is_emergency,
            "urgency": "high" if data.is_emergency else "normal",
            "summary": data.summary,
        },
        "transcript_summary": f"Petra hat mit {data.caller_name} gesprochen. Anliegen: {data.summary}",
    }
    task_res = await _create_task_from_call(fake_call)
    return {"ok": True, "task": task_res, "call_id": fake_call["id"]}


@router.get("/recent-calls")
async def recent_calls(token: str = Query(...), limit: int = 20):
    """Letzte Anruf-Tasks aus HalloPetra (fuer Admin-Panel-Uebersicht)."""
    await _require_admin(token)
    tasks = await db.tasks.find(
        {"source": "hallopetra"},
        {"_id": 0, "petra_full_payload": 0},
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return {"tasks": tasks, "count": len(tasks)}
