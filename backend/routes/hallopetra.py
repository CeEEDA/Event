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


async def _match_local_customer(digits_tail: str) -> dict | None:
    """Sucht in unseren Kundencollections (kunden + kirmes_schausteller) nach dem
    Phone-Tail. Erste Treffer gewinnt."""
    if not digits_tail:
        return None
    # Direkte Kunden (klassisch)
    doc = await db.kunden.find_one(
        {"$or": [
            {"telefon": {"$regex": digits_tail + "$"}},
            {"mobil": {"$regex": digits_tail + "$"}},
            {"phone": {"$regex": digits_tail + "$"}},
        ]},
        {"_id": 0, "id": 1, "name": 1, "firma": 1},
    )
    if doc:
        return {"id": doc.get("id"), "name": doc.get("firma") or doc.get("name"), "source": "kunden"}
    # Kirmes-Schausteller (Kundenstamm im Kirmes-Modul)
    schau = await db.kirmes_schausteller.find_one(
        {"$or": [
            {"telefon": {"$regex": digits_tail + "$"}},
            {"mobil": {"$regex": digits_tail + "$"}},
        ]},
        {"_id": 0, "id": 1, "name": 1, "firma": 1, "kundennummer": 1},
    )
    if schau:
        return {"id": schau.get("id"),
                "name": schau.get("firma") or schau.get("name"),
                "kundennummer": schau.get("kundennummer"),
                "source": "kirmes_schausteller"}
    return None


async def _find_customer_by_phone(phone: str) -> dict | None:
    """Sucht Kontakt per Telefonnummer. Priorisiert unsere Kunden-Collections,
    fallback auf importierte hallopetra_contacts."""
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 6:
        return None
    tail = digits[-8:]
    local = await _match_local_customer(tail)
    if local:
        return {"id": local.get("id"), "name": local.get("name"),
                "firma": local.get("name"), "source": local.get("source")}
    # HalloPetra-Kontakte
    petra_contact = await db.hallopetra_contacts.find_one(
        {"phone_digits": {"$regex": tail + "$"}},
        {"_id": 0, "id": 1, "name": 1, "petra_contact_id": 1, "linked_kunde_id": 1, "linked_kunde_name": 1},
    )
    if petra_contact:
        return {
            "id": petra_contact.get("linked_kunde_id"),
            "name": petra_contact.get("linked_kunde_name") or petra_contact.get("name"),
            "petra_contact_id": petra_contact.get("petra_contact_id"),
            "source": "petra_contact",
        }
    return None


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


async def _auto_sync_loop(interval_seconds: int = 1800):
    """Poll-Loop: holt alle 30min die neuesten Anrufe von Petra.
    Alle 24h zusätzlich: Kontakt-Import + Enrich der bestehenden Anrufe."""
    await _asyncio.sleep(30)  # Startup-Delay damit DB/Router bereit sind
    last_contact_sync = 0.0
    contact_interval = 24 * 3600  # 24h
    import time as _time
    while True:
        try:
            cfg = _config()
            headers = _auth_headers(cfg)
            if headers:
                # 1) Anrufe pullen (alle 30 Min)
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
                        # Yield to event loop, entlastet den DB-Pool
                        await _asyncio.sleep(0.05)
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

                # 2) Kontakte + Enrich (alle 24h)
                now = _time.time()
                if now - last_contact_sync >= contact_interval:
                    try:
                        contact_stats = await _import_all_contacts(cfg, headers)
                        enrich_stats = await _enrich_calls_backfill()
                        logger.info(f"HalloPetra nightly contacts: {contact_stats} | enrich: {enrich_stats}")
                        last_contact_sync = now
                    except Exception as _ce:
                        logger.warning(f"HalloPetra nightly Kontakt-Sync Fehler: {_ce}")
        except Exception as e:
            logger.warning(f"HalloPetra auto-sync Fehler: {e}")
        await _asyncio.sleep(interval_seconds)


async def _import_all_contacts(cfg: dict, headers: dict) -> dict:
    """Interne Hilfsfunktion: importiert alle Kontakte paginiert."""
    stats = {"total_fetched": 0, "created": 0, "updated": 0, "linked_to_kunde": 0, "pages": 0}
    cursor = None
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            resp = await client.get(cfg["base_url"] + "/v1/contacts",
                                    headers=headers, params=params)
            if resp.status_code >= 400:
                stats["error"] = f"{resp.status_code}: {resp.text[:200]}"
                return stats
            data = resp.json()
            items = data.get("items", [])
            stats["pages"] += 1
            stats["total_fetched"] += len(items)
            for pc in items:
                res = await _upsert_petra_contact(pc)
                if res["action"] == "created":
                    stats["created"] += 1
                else:
                    stats["updated"] += 1
                if res["linked"]:
                    stats["linked_to_kunde"] += 1
                # Yield to event loop, entlastet den DB-Pool bei grossen Batches
                await _asyncio.sleep(0.05)
            cursor = data.get("nextCursor")
            if not cursor or stats["pages"] > 100:
                break
    await db.system_settings.update_one(
        {"key": "hallopetra_contacts_last_import"},
        {"$set": {"key": "hallopetra_contacts_last_import",
                  "value": datetime.now(timezone.utc).isoformat(),
                  "stats": stats}},
        upsert=True,
    )
    return stats


async def _enrich_calls_backfill() -> dict:
    """Interne Hilfsfunktion: reichert bestehende Anruf-Tasks mit Namen
    aus dem Petra-Telefonbuch an."""
    tasks = await db.tasks.find(
        {"source": "hallopetra", "caller_name": {"$in": ["Anrufer", "Unbekannt", "", None]}},
        {"_id": 0, "id": 1, "caller_phone": 1, "caller_name": 1, "customer_id": 1}
    ).to_list(2000)
    stats = {"checked": len(tasks), "enriched": 0}
    for t in tasks:
        phone = t.get("caller_phone") or ""
        if not phone:
            continue
        digits = _normalize_phone(phone)
        tail = digits[-8:] if len(digits) >= 8 else digits
        if not tail:
            continue
        local = await _match_local_customer(tail)
        contact = None if local else await db.hallopetra_contacts.find_one(
            {"phone_digits": {"$regex": tail + "$"}},
            {"_id": 0, "name": 1, "petra_contact_id": 1,
             "linked_kunde_id": 1, "linked_kunde_name": 1, "standort": 1},
        )
        update = {}
        if local:
            update["caller_name"] = local.get("name")
            update["customer_id"] = local.get("id")
            update["customer_name"] = local.get("name")
        elif contact and contact.get("name"):
            update["caller_name"] = contact.get("name")
            update["petra_contact_id"] = contact.get("petra_contact_id")
            if contact.get("linked_kunde_id"):
                update["customer_id"] = contact.get("linked_kunde_id")
                update["customer_name"] = contact.get("linked_kunde_name")
            if contact.get("standort"):
                update["caller_standort"] = contact.get("standort")
        if update:
            await db.tasks.update_one({"id": t["id"]}, {"$set": update})
            stats["enriched"] += 1
        # Yield to event loop, entlastet den DB-Pool bei grossen Enrich-Batches
        await _asyncio.sleep(0.05)
    return stats


def start_hallopetra_sync():
    """Startet den Auto-Sync-Loop (wird von server.py aufgerufen)."""
    global _sync_task
    if _sync_task is None or _sync_task.done():
        _sync_task = _asyncio.create_task(_auto_sync_loop())
        logger.info("HalloPetra Auto-Sync-Loop gestartet (Intervall 30 Min)")


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


# ─────────────────────────────────────────────────────────────────────────────
# HalloPetra Telefonbuch (Kontakte)
# ─────────────────────────────────────────────────────────────────────────────
def _normalize_phone(phone: str) -> str:
    """Nur Ziffern (fuer robustes Matching)."""
    return "".join(ch for ch in (phone or "") if ch.isdigit())


async def _upsert_petra_contact(pc: dict) -> dict:
    """Speichert einen Petra-Kontakt in hallopetra_contacts.
    Versucht Verknuepfung mit unseren Kundencollections per Telefonnummer.
    Return: {'action': 'created'|'updated', 'linked': bool}"""
    petra_id = pc.get("id")
    phone = pc.get("phone") or ""
    digits = _normalize_phone(phone)
    tail = digits[-8:] if len(digits) >= 8 else digits

    # Match mit Kunden-Collections (kunden + kirmes_schausteller)
    local = await _match_local_customer(tail) if tail else None
    linked_kunde_id = (local or {}).get("id")
    linked_kunde_name = (local or {}).get("name")
    linked_source = (local or {}).get("source")

    existing = await db.hallopetra_contacts.find_one({"petra_contact_id": petra_id}, {"_id": 0, "id": 1})
    doc = {
        "petra_contact_id": petra_id,
        "name": pc.get("name") or "",
        "first_name": pc.get("firstName") or "",
        "last_name": pc.get("lastName") or "",
        "salutation": pc.get("salutation") or "",
        "phone": phone,
        "phone_digits": digits,
        "email": pc.get("email") or "",
        "contact_group_ids": pc.get("contactGroupIds") or [],
        "fields": pc.get("fields") or {},
        "standort": (pc.get("fields") or {}).get("standort") or "",
        "notes": (pc.get("fields") or {}).get("notes") or "",
        "linked_kunde_id": linked_kunde_id,
        "linked_kunde_name": linked_kunde_name,
        "linked_source": linked_source,
        "petra_created_at": pc.get("createdAt"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if existing:
        await db.hallopetra_contacts.update_one(
            {"petra_contact_id": petra_id}, {"$set": doc}
        )
        return {"action": "updated", "linked": bool(linked_kunde_id)}
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.hallopetra_contacts.insert_one(doc)
    return {"action": "created", "linked": bool(linked_kunde_id)}


@router.post("/import-contacts")
async def import_contacts(token: str = Query(...)):
    """Importiert das komplette HalloPetra-Telefonbuch (alle Seiten via Cursor)
    in unsere hallopetra_contacts-Collection und verknuepft mit vorhandenen
    Kunden per Telefonnummer."""
    await _require_admin(token)
    cfg = _config()
    headers = _auth_headers(cfg)
    if not headers:
        raise HTTPException(status_code=400, detail="HalloPetra-Token nicht konfiguriert")

    stats = {"total_fetched": 0, "created": 0, "updated": 0, "linked_to_kunde": 0, "pages": 0}
    cursor = None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                params = {"limit": 100}
                if cursor:
                    params["cursor"] = cursor
                resp = await client.get(cfg["base_url"] + "/v1/contacts",
                                        headers=headers, params=params)
                if resp.status_code >= 400:
                    return {"ok": False, "status_code": resp.status_code,
                            "body": resp.text[:500], "stats": stats}
                data = resp.json()
                items = data.get("items", [])
                stats["pages"] += 1
                stats["total_fetched"] += len(items)
                for pc in items:
                    res = await _upsert_petra_contact(pc)
                    if res["action"] == "created":
                        stats["created"] += 1
                    else:
                        stats["updated"] += 1
                    if res["linked"]:
                        stats["linked_to_kunde"] += 1
                cursor = data.get("nextCursor")
                if not cursor or stats["pages"] > 100:  # Safety-Limit
                    break
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Petra-API Fehler: {e}")

    await db.system_settings.update_one(
        {"key": "hallopetra_contacts_last_import"},
        {"$set": {"key": "hallopetra_contacts_last_import",
                  "value": datetime.now(timezone.utc).isoformat(),
                  "stats": stats}},
        upsert=True,
    )
    logger.info(f"HalloPetra Kontakte-Import: {stats}")
    return {"ok": True, **stats}


@router.get("/contacts")
async def list_contacts(token: str = Query(...), search: str = "", limit: int = 100,
                        only_linked: bool = False, only_unlinked: bool = False):
    """Liste der importierten Petra-Kontakte. Sichtbar fuer alle Staff mit Telefon-Modul."""
    caller = await _get_user(token)
    if not _can_view_telefon(caller):
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    q = {}
    if search:
        s = search.strip()
        digits = _normalize_phone(s)
        or_conds = [
            {"name": {"$regex": s, "$options": "i"}},
            {"linked_kunde_name": {"$regex": s, "$options": "i"}},
            {"standort": {"$regex": s, "$options": "i"}},
        ]
        if digits:
            or_conds.append({"phone_digits": {"$regex": digits}})
        q["$or"] = or_conds
    if only_linked:
        q["linked_kunde_id"] = {"$ne": None}
    elif only_unlinked:
        q["linked_kunde_id"] = None

    contacts = await db.hallopetra_contacts.find(q, {"_id": 0, "fields": 0}).sort("name", 1).limit(limit).to_list(limit)
    total = await db.hallopetra_contacts.count_documents({})
    linked = await db.hallopetra_contacts.count_documents({"linked_kunde_id": {"$ne": None}})
    return {"contacts": contacts, "count": len(contacts),
            "total": total, "linked": linked, "unlinked": total - linked}


@router.post("/enrich-calls")
async def enrich_calls(token: str = Query(...)):
    """Backfill: Setzt caller_name/customer_id fuer bestehende Anruf-Tasks
    anhand des importierten Petra-Telefonbuchs.
    Nuetzlich nach dem Erst-Import der Kontakte."""
    await _require_admin(token)
    tasks = await db.tasks.find(
        {"source": "hallopetra"},
        {"_id": 0, "id": 1, "caller_phone": 1, "caller_name": 1, "customer_id": 1}
    ).to_list(2000)
    stats = {"total": len(tasks), "enriched": 0, "skipped_no_phone": 0, "skipped_no_match": 0}
    for t in tasks:
        phone = t.get("caller_phone") or ""
        if not phone:
            stats["skipped_no_phone"] += 1
            continue
        digits = _normalize_phone(phone)
        tail = digits[-8:] if len(digits) >= 8 else digits
        if not tail:
            stats["skipped_no_phone"] += 1
            continue
        # Priorisiere Kunden-DB, dann Petra-Kontakt
        local = await _match_local_customer(tail)
        contact = None if local else await db.hallopetra_contacts.find_one(
            {"phone_digits": {"$regex": tail + "$"}},
            {"_id": 0, "name": 1, "first_name": 1, "last_name": 1,
             "petra_contact_id": 1, "linked_kunde_id": 1, "linked_kunde_name": 1,
             "standort": 1, "fields": 1},
        )
        update = {}
        if local:
            if not t.get("customer_id"):
                update["customer_id"] = local.get("id")
            update["customer_name"] = local.get("name")
            if t.get("caller_name") in ("Anrufer", "Unbekannt", "", None):
                update["caller_name"] = local.get("name")
        elif contact and contact.get("name"):
            if t.get("caller_name") in ("Anrufer", "Unbekannt", "", None):
                update["caller_name"] = contact.get("name")
            update["petra_contact_id"] = contact.get("petra_contact_id")
            if contact.get("linked_kunde_id") and not t.get("customer_id"):
                update["customer_id"] = contact.get("linked_kunde_id")
                update["customer_name"] = contact.get("linked_kunde_name")
            if contact.get("standort"):
                update["caller_standort"] = contact.get("standort")
        else:
            stats["skipped_no_match"] += 1
            continue
        if update:
            await db.tasks.update_one({"id": t["id"]}, {"$set": update})
            stats["enriched"] += 1
    logger.info(f"HalloPetra enrich-calls: {stats}")
    return {"ok": True, **stats}


@router.get("/contacts/{contact_id}")
async def contact_detail(contact_id: str, token: str = Query(...)):
    """Volle Details eines Petra-Kontakts inkl. aller `fields`."""
    caller = await _get_user(token)
    if not _can_view_telefon(caller):
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    c = await db.hallopetra_contacts.find_one({"id": contact_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden")
    return c


class LinkContactPayload(BaseModel):
    kunde_id: str | None = None  # None = unlink


@router.post("/contacts/{contact_id}/link")
async def link_contact(contact_id: str, data: LinkContactPayload, token: str = Query(...)):
    """Verknuepft einen Petra-Kontakt manuell mit einem unserer Kunden (oder unlinkt)."""
    caller = await _get_user(token)
    if not _can_view_telefon(caller):
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    linked_name = None
    if data.kunde_id:
        kunde = await db.kunden.find_one({"id": data.kunde_id}, {"_id": 0, "id": 1, "name": 1, "firma": 1})
        if not kunde:
            raise HTTPException(status_code=404, detail="Kunde nicht gefunden")
        linked_name = kunde.get("firma") or kunde.get("name")
    result = await db.hallopetra_contacts.update_one(
        {"id": contact_id},
        {"$set": {
            "linked_kunde_id": data.kunde_id,
            "linked_kunde_name": linked_name,
            "linked_at": datetime.now(timezone.utc).isoformat(),
            "linked_by": caller.get("name") or caller.get("email"),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden")
    return {"ok": True, "linked_kunde_id": data.kunde_id, "linked_kunde_name": linked_name}


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
async def list_calls(token: str = Query(...), limit: int = 100, only_open: bool = False,
                     search: str = ""):
    """Liste aller Petra-Anrufe fuer die Telefon-Kachel im Hub.
    Jeder Staff-User mit Telefon-Modul-Toggle darf sehen.
    `search` durchsucht Titel, Beschreibung, Anrufer-Name, Telefonnummer, Standort
    UND den kompletten Gespraechsverlauf (Volltext ueber `petra_transcript.text`)."""
    caller = await _get_user(token)
    if not _can_view_telefon(caller):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf Telefon-Uebersicht")
    query: dict = {"source": "hallopetra"}
    if only_open:
        query["status"] = "open"
    if search and search.strip():
        s = search.strip()
        # Escape MongoDB-Regex-Metazeichen (Nutzer koennte "." oder "(" eingeben)
        import re
        s_esc = re.escape(s)
        digits = _normalize_phone(s)
        or_conds = [
            {"title": {"$regex": s_esc, "$options": "i"}},
            {"description": {"$regex": s_esc, "$options": "i"}},
            {"caller_name": {"$regex": s_esc, "$options": "i"}},
            {"customer_name": {"$regex": s_esc, "$options": "i"}},
            {"caller_standort": {"$regex": s_esc, "$options": "i"}},
            {"category": {"$regex": s_esc, "$options": "i"}},
            {"petra_transcript.text": {"$regex": s_esc, "$options": "i"}},
        ]
        if digits:
            or_conds.append({"caller_phone": {"$regex": digits}})
        query["$or"] = or_conds
    tasks = await db.tasks.find(
        query,
        {"_id": 0, "petra_full_payload": 0},
    ).sort("created_at", -1).limit(limit).to_list(limit)
    # Statistik (immer ohne search, damit Kacheln stabil bleiben)
    total = await db.tasks.count_documents({"source": "hallopetra"})
    open_count = await db.tasks.count_documents({"source": "hallopetra", "status": "open"})
    urgent_count = await db.tasks.count_documents({"source": "hallopetra", "status": "open", "priority": "urgent"})
    return {"calls": tasks, "count": len(tasks), "total": total,
            "open": open_count, "urgent_open": urgent_count,
            "search_active": bool(search and search.strip())}


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
