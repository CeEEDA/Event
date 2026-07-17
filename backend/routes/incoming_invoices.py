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
from fints_banking import auto_match_incoming_invoices, _bank_configs


def _normalize_sender(name: str) -> str:
    """Sender-Namen normalisieren fuer Vergleich (Case-insensitive, ohne Sonderzeichen)."""
    import re
    s = (name or "").lower().strip()
    s = re.sub(r"\s+(gmbh|ag|kg|ug|se|co|kgaa|e\.k\.|ohg|inc|ltd|llc|corp)\.?", "", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

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
    """Liste aller Eingangsrechnungen aus allen rechnungseingang_*-Ordnern.
    Fehl-Klassifizierte Bestellungen/Angebote/Lieferscheine werden ausgeblendet."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")

    docs = await db.documents.find(
        {"folder_id": {"$regex": "^rechnungseingang_"}, "is_deleted": {"$ne": True}},
        {"_id": 0, "id": 1, "original_filename": 1, "folder_id": 1,
         "content_type": 1, "ai_metadata": 1, "created_at": 1,
         "eingang_paid": 1, "eingang_paid_at": 1, "eingang_paid_source": 1,
         "eingang_due_date_override": 1, "eingang_notes": 1,
         "eingang_not_invoice": 1,
         "eingang_paid_by_creditcard": 1, "eingang_paid_by_creditcard_at": 1,
         "eingang_paid_by_sepa": 1, "eingang_paid_by_sepa_at": 1}
    ).sort("created_at", -1).to_list(2000)

    # Sender-Merker fuer wiederkehrende Kreditkarten-/SEPA-Rechnungen
    ignore_doc = await db.system_settings.find_one(
        {"key": "eingang_ignore_senders"}, {"_id": 0, "value": 1}) or {}
    ignore_senders = {}
    for k, v in ((ignore_doc.get("value") or {}) or {}).items():
        ignore_senders[_normalize_sender(k)] = v  # v ist "creditcard" oder "sepa"

    today = datetime.now(timezone.utc).date()
    result = []
    for d in docs:
        if d.get("eingang_not_invoice"):
            continue  # manuell als "keine Rechnung" markiert
        meta = d.get("ai_metadata") or {}
        # Schutz: Bestellung/Angebot/Lieferschein rausfiltern, auch wenn KI-Ordner falsch
        dtype = (meta.get("document_type") or "").lower()
        if dtype in ("bestellung", "angebot", "lieferschein", "auftragsbestaetigung"):
            continue
        # Schutz: Ausgangsrechnungen (eigene Firma als Absender) rausfiltern
        sug = (meta.get("suggested_folder") or "").lower()
        if sug.startswith("rechnungsausgang"):
            continue
        fn = (d.get("original_filename") or "").lower()
        subj = (meta.get("subject") or "").lower()
        ref = (meta.get("reference") or "").lower()
        if any(kw in fn for kw in ("bestellung", "angebot", "lieferschein")):
            continue
        if subj.startswith("bestellung") or subj.startswith("angebot") or subj.startswith("lieferschein"):
            continue
        if "bestellnummer" in ref and "rechnungsnummer" not in subj and "rechnung" not in fn:
            continue

        inv_date = _parse_date(meta.get("date"))
        # Faelligkeit: 1. Override, 2. AI due_date, 3. Rechnungsdatum + 14 Tage
        due_date = _parse_date(d.get("eingang_due_date_override")) or _parse_date(meta.get("due_date"))
        if not due_date and inv_date:
            due_date = inv_date + timedelta(days=14)

        paid = bool(d.get("eingang_paid"))
        paid_by_cc = bool(d.get("eingang_paid_by_creditcard"))
        paid_by_sepa = bool(d.get("eingang_paid_by_sepa"))

        # Sender-basierter Merker: wenn Absender bekannt als CC/SEPA gezahlt,
        # kuenftige Rechnungen automatisch entsprechend markieren
        sender_name = meta.get("sender") or ""
        sender_norm = _normalize_sender(sender_name)
        auto_source = ignore_senders.get(sender_norm) if sender_norm else None
        if not paid_by_cc and not paid_by_sepa and auto_source:
            if auto_source == "creditcard":
                paid_by_cc = True
            elif auto_source == "sepa":
                paid_by_sepa = True

        if paid_by_cc:
            status = "creditcard"
        elif paid_by_sepa:
            status = "sepa"
        elif paid:
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
            "content_type": d.get("content_type") or "",
            "folder_id": d.get("folder_id"),
            "sender": sender_name,
            "invoice_number": meta.get("invoice_number") or "",
            "invoice_date": inv_date.isoformat() if inv_date else None,
            "due_date": due_date.isoformat() if due_date else None,
            "payment_term_days": meta.get("payment_term_days"),
            "payment_terms": meta.get("payment_terms") or "",
            "amount": amount,
            "currency": meta.get("currency") or "EUR",
            "iban": meta.get("iban") or "",
            "status": status,
            "paid": paid,
            "paid_at": d.get("eingang_paid_at"),
            "paid_source": d.get("eingang_paid_source"),
            "paid_by_creditcard": paid_by_cc,
            "paid_by_creditcard_at": d.get("eingang_paid_by_creditcard_at"),
            "paid_by_sepa": paid_by_sepa,
            "paid_by_sepa_at": d.get("eingang_paid_by_sepa_at"),
            "auto_flagged_by_sender": bool(auto_source) and not d.get("eingang_paid_by_creditcard") and not d.get("eingang_paid_by_sepa"),
            "notes": d.get("eingang_notes") or "",
            "created_at": d.get("created_at"),
        })

    # Sortierung: overdue → open → paid → creditcard → sepa
    def _sort_key(r):
        st_order = {"overdue": 0, "open": 1, "paid": 2, "creditcard": 3, "sepa": 4}.get(r["status"], 5)
        due = r.get("due_date") or "9999-12-31"
        return (st_order, due)

    result.sort(key=_sort_key)

    # Summary (Kreditkarte + SEPA separat)
    open_amount = sum(r["amount"] for r in result if r["status"] == "open")
    overdue_amount = sum(r["amount"] for r in result if r["status"] == "overdue")
    paid_amount = sum(r["amount"] for r in result if r["status"] == "paid")
    cc_amount = sum(r["amount"] for r in result if r["status"] == "creditcard")
    sepa_amount = sum(r["amount"] for r in result if r["status"] == "sepa")

    return {
        "invoices": result,
        "summary": {
            "total_count": len(result),
            "open_count": sum(1 for r in result if r["status"] == "open"),
            "overdue_count": sum(1 for r in result if r["status"] == "overdue"),
            "paid_count": sum(1 for r in result if r["status"] == "paid"),
            "creditcard_count": sum(1 for r in result if r["status"] == "creditcard"),
            "sepa_count": sum(1 for r in result if r["status"] == "sepa"),
            "open_amount": round(open_amount, 2),
            "overdue_amount": round(overdue_amount, 2),
            "paid_amount": round(paid_amount, 2),
            "creditcard_amount": round(cc_amount, 2),
            "sepa_amount": round(sepa_amount, 2),
        }
    }


async def _remember_sender(sender: str, method: str, admin_name: str):
    """Merkt sich einen Absender als Kreditkarten- oder SEPA-Zahler.
    Alle künftigen Rechnungen dieses Absenders werden automatisch aus der Liste
    ausgeblendet. method ∈ {'creditcard', 'sepa'} oder '' zum Vergessen."""
    doc = await db.system_settings.find_one({"key": "eingang_ignore_senders"}, {"_id": 0, "value": 1})
    current = (doc.get("value") if doc else None) or {}
    norm = _normalize_sender(sender)
    if not norm:
        return
    if method:
        current[norm] = method
    else:
        current.pop(norm, None)
    await db.system_settings.update_one(
        {"key": "eingang_ignore_senders"},
        {"$set": {"key": "eingang_ignore_senders", "value": current,
                  "updated_at": datetime.now(timezone.utc).isoformat(),
                  "updated_by": admin_name}},
        upsert=True,
    )


@router.post("/{doc_id}/mark-creditcard")
async def mark_creditcard(doc_id: str, token: str = Query(...), remember_sender: bool = Query(True)):
    """Markiert eine Rechnung als per Kreditkarte bezahlt. Blendet sie aus der
    Aktiv-Liste aus. Wenn remember_sender=True, werden künftige Rechnungen desselben
    Absenders automatisch ebenfalls als Kreditkarten-Zahlung erkannt."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0, "id": 1, "ai_metadata": 1})
    if doc is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    now = datetime.now(timezone.utc).isoformat()
    await db.documents.update_one({"id": doc_id}, {"$set": {
        "eingang_paid_by_creditcard": True,
        "eingang_paid_by_creditcard_at": now,
        "eingang_paid_by_creditcard_by": caller.get("name", "admin"),
    }})
    if remember_sender:
        sender = ((doc.get("ai_metadata") or {}).get("sender") or "").strip()
        if sender:
            await _remember_sender(sender, "creditcard", caller.get("name", "admin"))
    return {"ok": True}


@router.post("/{doc_id}/mark-sepa")
async def mark_sepa(doc_id: str, token: str = Query(...), remember_sender: bool = Query(True)):
    """Markiert eine Rechnung als per SEPA-Lastschrift eingezogen. Blendet sie aus
    der Aktiv-Liste aus. Wenn remember_sender=True (Standard), werden künftige
    Rechnungen desselben Absenders automatisch erkannt."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0, "id": 1, "ai_metadata": 1})
    if doc is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    now = datetime.now(timezone.utc).isoformat()
    await db.documents.update_one({"id": doc_id}, {"$set": {
        "eingang_paid_by_sepa": True,
        "eingang_paid_by_sepa_at": now,
        "eingang_paid_by_sepa_by": caller.get("name", "admin"),
    }})
    if remember_sender:
        sender = ((doc.get("ai_metadata") or {}).get("sender") or "").strip()
        if sender:
            await _remember_sender(sender, "sepa", caller.get("name", "admin"))
    return {"ok": True}


@router.get("/ignored-senders")
async def list_ignored_senders(token: str = Query(...)):
    """Liste aller gemerkten Kreditkarten-/SEPA-Absender."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    doc = await db.system_settings.find_one({"key": "eingang_ignore_senders"}, {"_id": 0, "value": 1})
    return {"senders": (doc.get("value") if doc else None) or {}}


@router.delete("/ignored-senders/{sender_key}")
async def remove_ignored_sender(sender_key: str, token: str = Query(...)):
    """Entfernt einen Absender aus der Ignore-Liste (künftige Rechnungen erscheinen wieder)."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    await _remember_sender(sender_key, "", caller.get("name", "admin"))
    return {"ok": True}


@router.post("/{doc_id}/mark-paid")
async def mark_paid(doc_id: str, token: str = Query(...)):
    """Markiert eine Eingangsrechnung als bezahlt (final; keine Rücknahme über UI)."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    existing = await db.documents.find_one({"id": doc_id}, {"_id": 0, "id": 1, "eingang_paid": 1})
    if existing is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    if existing.get("eingang_paid"):
        return {"ok": True, "paid": True, "already": True}
    now = datetime.now(timezone.utc).isoformat()
    await db.documents.update_one({"id": doc_id}, {"$set": {
        "eingang_paid": True,
        "eingang_paid_at": now,
        "eingang_paid_source": f"manuell ({caller.get('name', 'admin')})",
    }})
    return {"ok": True, "paid": True}


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


@router.post("/{doc_id}/not-invoice")
async def mark_not_invoice(doc_id: str, token: str = Query(...)):
    """Markiert ein Dokument als 'keine Eingangsrechnung' (Fehl-Klassifizierung durch KI).
    Wird aus der Eingangsrechnungen-Liste entfernt; Dokument bleibt im Ordner für
    manuelle Verschiebung im Dokumentenmanagement."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    res = await db.documents.update_one(
        {"id": doc_id},
        {"$set": {
            "eingang_not_invoice": True,
            "eingang_not_invoice_at": datetime.now(timezone.utc).isoformat(),
            "eingang_not_invoice_by": caller.get("name", "admin"),
        }}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return {"ok": True}


@router.post("/reanalyze-legacy")
async def reanalyze_legacy(token: str = Query(...), dry_run: bool = Query(True), limit: int = Query(500, ge=1, le=5000)):
    """Jagd alle alten Dokumente (ohne aktuellen OCR-Analyse-Stempel) durch den
    Heuristic-Analyzer und aktualisiert Metadata + verschiebt gegebenenfalls
    zwischen Rechnungseingang und Rechnungsausgang.

    ``dry_run=true`` (Standard): nur Report ohne DB-Aenderungen.
    ``dry_run=false``: schreibt Aenderungen in die DB.
    """
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")

    from services.heuristic_analyzer import analyze_document_fallback
    from routes.documents import get_object

    # Kandidaten: alle Docs in rechnungseingang_*/rechnungsausgang_* Ordnern
    # mit alter/fehlender Metadata (ai_source != 'heuristic')
    docs = await db.documents.find(
        {"folder_id": {"$regex": "^(rechnungseingang_|rechnungsausgang_)"},
         "is_deleted": {"$ne": True},
         "ai_source": {"$ne": "heuristic"}},
        {"_id": 0, "id": 1, "original_filename": 1, "folder_id": 1,
         "storage_path": 1, "ai_metadata": 1, "ai_source": 1}
    ).limit(limit).to_list(limit)

    changes = []
    moved_to_eingang = 0
    moved_to_ausgang = 0
    metadata_updated = 0
    errors = 0

    for d in docs:
        try:
            if not d.get("storage_path"):
                continue
            data, _ct = get_object(d["storage_path"])
            result = analyze_document_fallback(data, d.get("original_filename") or "")
            new_sug = (result.get("suggested_folder") or "").lower()
            old_folder = (d.get("folder_id") or "").lower()

            current_direction = "rechnungseingang" if old_folder.startswith("rechnungseingang") else "rechnungsausgang"
            new_direction = None
            if new_sug.startswith("rechnungseingang"):
                new_direction = "rechnungseingang"
            elif new_sug.startswith("rechnungsausgang"):
                new_direction = "rechnungsausgang"

            change = {
                "id": d["id"],
                "filename": d.get("original_filename"),
                "old_folder": d.get("folder_id"),
                "old_meta_sender": (d.get("ai_metadata") or {}).get("sender"),
                "old_meta_type": (d.get("ai_metadata") or {}).get("document_type"),
                "new_meta_sender": result.get("sender"),
                "new_meta_type": result.get("document_type"),
                "new_suggested_folder": result.get("suggested_folder"),
                "current_direction": current_direction,
                "new_direction": new_direction,
                "will_move": bool(new_direction and new_direction != current_direction),
            }
            changes.append(change)

            if not dry_run:
                update = {
                    "ai_source": "heuristic",
                    "ai_analyzed_at": datetime.now(timezone.utc).isoformat(),
                    "ai_metadata.document_type": result.get("document_type"),
                    "ai_metadata.sender": result.get("sender"),
                    "ai_metadata.recipient": result.get("recipient"),
                    "ai_metadata.invoice_number": result.get("invoice_number"),
                    "ai_metadata.amount": result.get("amount"),
                    "ai_metadata.date": result.get("date"),
                    "ai_metadata.due_date": result.get("due_date"),
                    "ai_metadata.payment_term_days": result.get("payment_term_days"),
                    "ai_metadata.payment_terms": result.get("payment_terms"),
                    "ai_metadata.currency": result.get("currency"),
                    "ai_metadata.iban": result.get("iban"),
                    "ai_metadata.subject": result.get("subject"),
                    "ai_metadata.suggested_folder": result.get("suggested_folder"),
                }
                # Ordner-Verschiebung: neuen Ziel-Ordner suchen (existierender Ordner
                # mit passendem Praefix + gleichem Datums-Suffix wie der alte)
                if change["will_move"]:
                    # Datum-Suffix aus altem Ordner extrahieren (z.B. "_2026_07")
                    import re as _re
                    m = _re.search(r"(_\d{4}_\d{2})$", d.get("folder_id") or "")
                    date_suffix = m.group(1) if m else ""
                    # Existierenden Ziel-Ordner finden
                    target = await db.folders.find_one(
                        {"id": {"$regex": f"^{new_direction}_.*{date_suffix}$"}},
                        {"_id": 0, "id": 1}
                    )
                    if target:
                        update["folder_id"] = target["id"]
                        if new_direction == "rechnungseingang":
                            moved_to_eingang += 1
                        else:
                            moved_to_ausgang += 1
                await db.documents.update_one({"id": d["id"]}, {"$set": update})
                metadata_updated += 1
        except Exception as e:
            errors += 1
            changes.append({"id": d.get("id"), "error": str(e)[:200]})

    return {
        "dry_run": dry_run,
        "scanned": len(docs),
        "metadata_updated": metadata_updated,
        "moved_to_eingang": moved_to_eingang,
        "moved_to_ausgang": moved_to_ausgang,
        "errors": errors,
        "would_move_count": sum(1 for c in changes if c.get("will_move")),
        "changes_preview": changes[:50],
        "changes_total": len(changes),
    }


@router.post("/fints/auto-match")
async def fints_auto_match(token: str = Query(...), days_back: int = Query(60, ge=1, le=365)):
    """Startet den FinTS-Abgleich (Sparkasse): ausgehende Buchungen ↔ offene Eingangsrechnungen.
    Sammelüberweisungen werden nicht behandelt (jede Buchung = 1 Rechnung).
    """
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    result = await auto_match_incoming_invoices(db, create_admin_tasks=True, days_back=days_back)
    return result


@router.get("/bank-status")
async def bank_status(token: str = Query(...)):
    """Liefert Übersicht aller konfigurierten Banken + letzter Sync-Zeitpunkt +
    Alter des persistierten Client-States (fuer Statuszeile in der UI)."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    from datetime import datetime as _dt, timezone as _tz

    banks_out = []
    for bank in _bank_configs():
        key = bank["key"]
        # Persistierter Client-State
        state_key = "fints_client_state" if key == "sparkasse" else f"fints_client_state_{key}"
        state_doc = await db.system_settings.find_one({"key": state_key}, {"_id": 0})
        has_state = bool(state_doc and state_doc.get("value"))
        state_updated = state_doc.get("updated_at") if state_doc else None
        state_age_days = None
        if state_updated:
            try:
                d = _dt.fromisoformat(state_updated.replace("Z", "+00:00"))
                state_age_days = (_dt.now(_tz.utc) - d).days
            except Exception:
                pass
        # Letzter Abrufversuch
        last_check_key = "fints_last_check" if key == "sparkasse" else f"fints_last_check_{key}"
        last_check = await db.system_settings.find_one({"key": last_check_key}, {"_id": 0})
        # Toggle enabled?
        enabled_key = "fints_enabled" if key == "sparkasse" else f"fints_enabled_{key}"
        en_doc = await db.system_settings.find_one({"key": enabled_key}, {"_id": 0})
        enabled = en_doc.get("value", True) if en_doc else True

        banks_out.append({
            "key": key,
            "name": bank.get("name", key),
            "iban": bank.get("iban", ""),
            "enabled": bool(enabled),
            "has_state": has_state,
            "state_updated_at": state_updated,
            "state_age_days": state_age_days,
            "sca_renewal_in_days": max(0, 90 - state_age_days) if state_age_days is not None else None,
            "last_check_at": last_check.get("value") if last_check else None,
            "last_check_result": last_check.get("result") if last_check else None,
        })

    return {"banks": banks_out, "count": len(banks_out)}


@router.post("/bulk-mark-paid")
async def bulk_mark_paid(payload: dict, token: str = Query(...)):
    """Markiert mehrere Rechnungen gleichzeitig als bezahlt.
    Body: ``{"ids": ["doc1", "doc2", ...]}``. Nur nicht-bereits-bezahlte
    Rechnungen werden aktualisiert. Kreditkarten/SEPA-Flags bleiben unangetastet.
    """
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Admins")
    ids = payload.get("ids") if isinstance(payload, dict) else None
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail="ids-Liste ist leer")
    if len(ids) > 500:
        raise HTTPException(status_code=400, detail="max. 500 Rechnungen pro Batch")
    now = datetime.now(timezone.utc).isoformat()
    src = f"bulk-manuell ({caller.get('name', 'admin')})"
    res = await db.documents.update_many(
        {"id": {"$in": ids},
         "eingang_paid": {"$ne": True},
         "eingang_paid_by_creditcard": {"$ne": True},
         "eingang_paid_by_sepa": {"$ne": True}},
        {"$set": {
            "eingang_paid": True,
            "eingang_paid_at": now,
            "eingang_paid_source": src,
        }}
    )
    return {"ok": True, "requested": len(ids), "updated": res.modified_count}
