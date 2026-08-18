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
        "base_url": os.environ.get("HALLOPETRA_BASE_URL", "https://hallopetra-api.vercel.app"),
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
def _verify_signature(body: bytes, signature_header: str | None, secret: str, tolerance_seconds: int = 300) -> bool:
    """Verifiziert X-HalloPetra-Signature (Format: 't=<unixSeconds>,v1=<hex>').
    HMAC ueber "t.body". Timestamp aelter als tolerance -> abgelehnt (Replay-Schutz).
    Konstante-Zeit-Vergleich, kein Timing-Leak."""
    import re
    import time
    if not signature_header or not secret:
        return False
    m = re.match(r"^t=(\d+),v1=([0-9a-f]{64})$", signature_header.strip())
    if not m:
        return False
    ts_str, provided = m.group(1), m.group(2)
    ts = int(ts_str)
    if abs(int(time.time()) - ts) > tolerance_seconds:
        return False
    signed = f"{ts_str}.{body.decode('utf-8', errors='replace')}"
    expected = hmac.new(secret.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).hexdigest()
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


def _map_priority_from_petra_call(call: dict) -> str:
    """Uebersetzt Petras Call-Payload in unser Priority-Schema.
    Notfall wird via executedTasks erkannt (z.B. 'Störung Stromausfall').
    Ansonsten normal."""
    tasks = call.get("executedTasks") or []
    tasks_lower = " ".join(str(t).lower() for t in tasks)
    if any(kw in tasks_lower for kw in ("stör", "notfall", "notruf", "ausfall", "stromausfall")):
        return "urgent"
    return "normal"


def _is_qualified_petra_call(call: dict) -> bool:
    """User-Vorgabe: NUR qualifizierte Anrufe werden zu Tasks.
    Kriterium: executedTasks nicht leer (Petra hat einen echten Ablauf durchlaufen)
    UND es gibt eine Zusammenfassung."""
    if not call.get("executedTasks"):
        return False
    if not (call.get("summary") or "").strip():
        return False
    return True


async def _create_task_from_petra_call(call: dict) -> dict:
    """Erzeugt eine Aufgabe aus einer Petra-Call-Response (echtes API-Schema).
    Idempotent via petra_call_id."""
    petra_call_id = call.get("id")
    if not petra_call_id:
        raise ValueError("call.id fehlt")

    existing = await db.tasks.find_one({"petra_call_id": petra_call_id}, {"_id": 0})
    if existing:
        return {"created": False, "task_id": existing.get("id"), "reason": "duplicate"}

    caller_phone = call.get("callerNumber") or ""
    tasks_list = call.get("executedTasks") or []
    priority = _map_priority_from_petra_call(call)
    is_emergency = priority == "urgent"

    # Kunde per Telefonnummer matchen
    customer = await _find_customer_by_phone(caller_phone)
    caller_name = (customer or {}).get("name") or (customer or {}).get("firma") or "Anrufer"

    subject_base = tasks_list[0] if tasks_list else (call.get("summary") or "Anruf")[:80]
    subject = f"🚨 NOTFALL: {subject_base}" if is_emergency else subject_base

    task = {
        "id": str(uuid.uuid4()),
        "type": "hallopetra_call",
        "petra_call_id": petra_call_id,
        "title": subject[:200],
        "description": (call.get("summary") or "")[:2000],
        "priority": priority,
        "status": "open",
        "source": "hallopetra",
        "caller_name": caller_name,
        "caller_phone": caller_phone,
        "customer_id": (customer or {}).get("id"),
        "customer_name": (customer or {}).get("name") or (customer or {}).get("firma"),
        "category": tasks_list[0] if tasks_list else "call",
        "executed_tasks": tasks_list,
        "is_emergency": is_emergency,
        "petra_call_started_at": call.get("startedAt"),
        "petra_duration_seconds": call.get("durationSeconds"),
        "petra_call_type": call.get("callType"),
        "petra_contact_id": call.get("contactId"),
        "petra_transcript": call.get("transcript") or [],
        "petra_full_payload": call,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tasks.insert_one(task)
    logger.info(f"HalloPetra: Task {task['id']} erstellt "
                f"(petra_call={petra_call_id}, priority={priority}, tasks={tasks_list})")
    return {"created": True, "task_id": task["id"], "priority": priority,
            "customer_matched": bool(customer)}


# Backward compatible alias (fuer Webhook der schon deployed war):
async def _create_task_from_call(call: dict) -> dict:
    """Alter Webhook-Payload-Style. Delegiert an neuen Handler wenn moeglich."""
    if "callerNumber" in call or "executedTasks" in call or "durationSeconds" in call:
        return await _create_task_from_petra_call(call)
    # Fallback fuer simulate-call / alten Payload
    petra_call_id = call.get("id") or call.get("call_id")
    if not petra_call_id:
        raise ValueError("call.id fehlt")
    existing = await db.tasks.find_one({"petra_call_id": petra_call_id}, {"_id": 0})
    if existing:
        return {"created": False, "task_id": existing.get("id"), "reason": "duplicate"}
    q = call.get("qualification") or {}
    caller = call.get("caller") or {}
    caller_phone = caller.get("phone") or call.get("from") or ""
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
        "priority": priority, "status": "open", "source": "hallopetra",
        "caller_name": caller_name, "caller_phone": caller_phone or "",
        "customer_id": (customer or {}).get("id"),
        "customer_name": (customer or {}).get("name") or (customer or {}).get("firma"),
        "category": q.get("category") or "call", "is_emergency": is_emergency,
        "petra_full_payload": call,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tasks.insert_one(task)
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
    last_sync = await db.system_settings.find_one({"key": "hallopetra_last_sync"}, {"_id": 0})
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
        "last_sync_at": (last_sync or {}).get("value"),
        "last_sync_stats": (last_sync or {}).get("stats"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Auto-Sync Scheduler (5-Minuten-Poll)
# ─────────────────────────────────────────────────────────────────────────────
import asyncio as _asyncio

_sync_task = None


async def _auto_sync_loop(interval_seconds: int = 300):
    """Poll-Loop: holt alle 5min die neuesten Anrufe von Petra."""
    await _asyncio.sleep(30)  # Startup-Delay damit DB/Router bereit sind
    while True:
        try:
            cfg = _config()
            headers = _auth_headers(cfg)
            if headers:
                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.get(cfg["base_url"] + "/v1/calls",
                                            headers=headers, params={"limit": 50})
                if resp.status_code < 400:
                    data = resp.json()
                    items = data.get("items", [])
                    created = 0
                    for call in items:
                        if not _is_qualified_petra_call(call):
                            continue
                        res = await _create_task_from_petra_call(call)
                        if res.get("created"):
                            created += 1
                    if created:
                        logger.info(f"HalloPetra auto-sync: {created} neue Anrufe importiert")
                    await db.system_settings.update_one(
                        {"key": "hallopetra_last_sync"},
                        {"$set": {"key": "hallopetra_last_sync",
                                  "value": datetime.now(timezone.utc).isoformat(),
                                  "stats": {"created": created, "total_fetched": len(items),
                                            "source": "auto"}}},
                        upsert=True,
                    )
        except Exception as e:
            logger.warning(f"HalloPetra auto-sync Fehler: {e}")
        await _asyncio.sleep(interval_seconds)


def start_hallopetra_sync():
    """Startet den Auto-Sync-Loop (wird von server.py aufgerufen)."""
    global _sync_task
    if _sync_task is None or _sync_task.done():
        _sync_task = _asyncio.create_task(_auto_sync_loop())
        logger.info("HalloPetra Auto-Sync-Loop gestartet (Intervall 5 Min)")


def _auth_headers(cfg: dict) -> dict:
    """Baut den Auth-Header laut Petra-Doku (Bearer hp_ck_...)."""
    token_value = cfg["api_token"] or cfg["client_secret"] or cfg["client_id"]
    if not token_value:
        return {}
    header_val = f"{cfg['auth_scheme']} {token_value}".strip() if cfg["auth_scheme"] else token_value
    return {cfg["auth_header"]: header_val, "Accept": "application/json"}


@router.post("/test-outbound")
async def test_outbound(token: str = Query(...)):
    """Testet den Ausgehend-Aufruf gegen HalloPetra (GET /v1/webhooks)."""
    await _require_admin(token)
    cfg = _config()
    headers = _auth_headers(cfg)
    if not headers:
        return {"ok": False, "error": "Kein Token gesetzt (HALLOPETRA_CLIENT_ID/CLIENT_SECRET/API_TOKEN)."}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(cfg["base_url"] + "/v1/webhooks", headers=headers)
        return {
            "ok": resp.status_code < 400,
            "status_code": resp.status_code,
            "body_preview": resp.text[:500],
            "url": str(resp.url),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:500]}


@router.post("/sync-calls")
async def sync_calls(token: str = Query(...), limit: int = 50):
    """Zieht die letzten N Anrufe aktiv von Petra ab und legt Tasks an
    fuer alle qualifizierten Anrufe (idempotent, doppelte werden geskippt)."""
    await _require_admin(token)
    cfg = _config()
    headers = _auth_headers(cfg)
    if not headers:
        raise HTTPException(status_code=400, detail="HalloPetra-Token nicht konfiguriert")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                cfg["base_url"] + "/v1/calls",
                headers=headers,
                params={"limit": limit},
            )
        if resp.status_code >= 400:
            return {"ok": False, "status_code": resp.status_code, "body": resp.text[:500]}
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Petra-API Fehler: {e}")

    items = data.get("items", [])
    stats = {"total": len(items), "created": 0, "skipped_duplicate": 0, "skipped_unqualified": 0}
    for call in items:
        if not _is_qualified_petra_call(call):
            stats["skipped_unqualified"] += 1
            continue
        res = await _create_task_from_petra_call(call)
        if res.get("created"):
            stats["created"] += 1
        else:
            stats["skipped_duplicate"] += 1
    logger.info(f"HalloPetra sync: {stats}")
    # Letzten Sync-Zeitpunkt merken
    await db.system_settings.update_one(
        {"key": "hallopetra_last_sync"},
        {"$set": {"key": "hallopetra_last_sync",
                  "value": datetime.now(timezone.utc).isoformat(),
                  "stats": stats}},
        upsert=True,
    )
    return {"ok": True, **stats, "next_cursor": data.get("nextCursor")}


@router.post("/register-webhook")
async def register_webhook(token: str = Query(...), event: str = Query("call.finished")):
    """Registriert unseren Webhook-Endpoint bei Petra (POST /v1/webhooks).
    Speichert den zurueckgegebenen whsec fuer die HMAC-Verifikation."""
    await _require_admin(token)
    cfg = _config()
    headers = _auth_headers(cfg)
    if not headers:
        raise HTTPException(status_code=400, detail="HalloPetra-Token nicht konfiguriert")
    public_url = os.environ.get("PUBLIC_URL") or os.environ.get("REACT_APP_BACKEND_URL", "")
    if not public_url:
        raise HTTPException(status_code=400, detail="PUBLIC_URL nicht gesetzt")
    webhook_url = public_url.rstrip("/") + "/api/hallopetra/webhook"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                cfg["base_url"] + "/v1/webhooks",
                headers={**headers, "Content-Type": "application/json"},
                json={"event": event, "url": webhook_url},
            )
        if resp.status_code >= 400:
            return {"ok": False, "status_code": resp.status_code, "body": resp.text[:500]}
        data = resp.json()
        # Secret speichern
        secret = data.get("secret") or data.get("signingSecret")
        if secret:
            await db.system_settings.update_one(
                {"key": "hallopetra_webhook_secret_db"},
                {"$set": {"key": "hallopetra_webhook_secret_db", "value": secret,
                          "webhook_id": data.get("id"),
                          "updated_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
        return {"ok": True, "webhook_id": data.get("id"),
                "secret_stored": bool(secret),
                "url_registered": webhook_url, "event": event}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Petra-API Fehler: {e}")


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


# ─────────────────────────────────────────────────────────────────────────────
# Telefon-Uebersicht fuer Mitarbeiter (Hub-Kachel "Telefon")
# ─────────────────────────────────────────────────────────────────────────────
def _can_view_telefon(caller: dict) -> bool:
    """Admin oder Mitarbeiter mit aktivem 'telefon'-Modul."""
    if not caller:
        return False
    if caller.get("role") == "admin":
        return True
    if caller.get("role") == "mitarbeiter":
        modules = (caller.get("apps") or {}).get("modules") or {}
        return bool(modules.get("telefon"))
    return False


@router.get("/calls")
async def list_calls(token: str = Query(...), limit: int = 100, only_open: bool = False):
    """Liste aller Petra-Anrufe fuer die Telefon-Kachel im Hub.
    Jeder Staff-User mit Telefon-Modul-Toggle darf sehen."""
    caller = await _get_user(token)
    if not _can_view_telefon(caller):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf Telefon-Uebersicht")
    query = {"source": "hallopetra"}
    if only_open:
        query["status"] = "open"
    tasks = await db.tasks.find(
        query,
        {"_id": 0, "petra_full_payload": 0},
    ).sort("created_at", -1).limit(limit).to_list(limit)
    # Statistik
    total = await db.tasks.count_documents({"source": "hallopetra"})
    open_count = await db.tasks.count_documents({"source": "hallopetra", "status": "open"})
    urgent_count = await db.tasks.count_documents({"source": "hallopetra", "status": "open", "priority": "urgent"})
    return {"calls": tasks, "count": len(tasks), "total": total, "open": open_count, "urgent_open": urgent_count}


@router.get("/calls/{task_id}")
async def call_detail(task_id: str, token: str = Query(...)):
    """Volle Anruf-Details inkl. Petra-Payload (Transkript, Recording-URL)."""
    caller = await _get_user(token)
    if not _can_view_telefon(caller):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf Telefon-Uebersicht")
    task = await db.tasks.find_one({"id": task_id, "source": "hallopetra"}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Anruf nicht gefunden")
    return task


@router.post("/calls/{task_id}/mark-done")
async def mark_call_done(task_id: str, token: str = Query(...)):
    """Markiert einen Anruf-Task als erledigt."""
    caller = await _get_user(token)
    if not _can_view_telefon(caller):
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    result = await db.tasks.update_one(
        {"id": task_id, "source": "hallopetra"},
        {"$set": {
            "status": "done",
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "closed_by": caller.get("name") or caller.get("email"),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Anruf nicht gefunden")
    return {"ok": True}
