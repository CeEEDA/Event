"""
FinTS/HBCI Banking Integration - Kreissparkasse Mayen
Liest Kontobewegungen und gleicht sie mit offenen Rechnungen ab.
"""
import base64
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

logger = logging.getLogger("fints_banking")

# FinTS-Konfiguration (konfigurierbar via .env)
# Defaults: Kreissparkasse Mayen (fuer Eventenergie Deutschland).
# Ueber die Umgebungsvariablen FINTS_URL und FINTS_BLZ ueberschreibbar.
FINTS_URL = os.environ.get("FINTS_URL", "https://banking-rp1.s-fints-pt-rp.de/fints30")
FINTS_BLZ = os.environ.get("FINTS_BLZ", "57650010")

# WICHTIG: Sparkassen verlangen ZWINGEND eine registrierte Produkt-ID + Version.
# Ohne diese gibt's 9340 "Ungueltige Signatur" auch bei korrekten Credentials.
# Die folgende ID ist die offizielle Test-ID die python-fints bei FinTS registriert
# hat und die von Sparkassen akzeptiert wird (Quelle: python-fints README).
# Kann via FINTS_PRODUCT_ID/FINTS_PRODUCT_VERSION in der .env ueberschrieben werden.
DEFAULT_FINTS_PRODUCT_ID = "9FA6681DEC0CF3046BFC2F8A6"
DEFAULT_FINTS_PRODUCT_VERSION = "1.0"
FINTS_PRODUCT_ID = os.environ.get("FINTS_PRODUCT_ID", "") or DEFAULT_FINTS_PRODUCT_ID
FINTS_PRODUCT_VERSION = os.environ.get("FINTS_PRODUCT_VERSION", "") or DEFAULT_FINTS_PRODUCT_VERSION


# ─────────────────────────────────────────────────────────────────────────────
# Credentials + Client-Setup
# ─────────────────────────────────────────────────────────────────────────────

def get_fints_credentials():
    """Liest FinTS-Zugangsdaten aus Umgebungsvariablen."""
    user = os.environ.get("FINTS_USER", "")
    pin = os.environ.get("FINTS_PIN", "")
    if not user or not pin:
        return None
    return {"user": user, "pin": pin}


def _resolve_decoupled_tan(client, response, max_wait_seconds=120, poll_interval=2.0):
    """Behandelt decoupled pushTAN: pollt die Bank, bis der User in der pushTAN-App bestaetigt hat.
    Gibt die finale Response zurueck (oder hebt Exception bei Timeout/klassischer TAN)."""
    from fints.client import NeedRetryResponse
    waited = 0.0
    while isinstance(response, NeedRetryResponse):
        if not getattr(response, "decoupled", False):
            raise RuntimeError(
                "Bank verlangt klassische TAN-Eingabe (z.B. chipTAN). "
                "Dieser Endpunkt unterstuetzt nur decoupled pushTAN."
            )
        if waited >= max_wait_seconds:
            raise TimeoutError(
                f"Timeout: pushTAN nicht innerhalb von {max_wait_seconds}s bestaetigt. "
                "Bitte schneller in der pushTAN-App bestaetigen oder erneut versuchen."
            )
        logger.info(f"FinTS pushTAN: warte auf Bestaetigung (decoupled, {waited:.0f}s)...")
        time.sleep(poll_interval)
        waited += poll_interval
        response = client.send_tan(response, "")
    return response


def _resolve_sca_after_dialog_start(client, max_wait_seconds=120, poll_interval=2.0):
    """Resolver fuer die PSD2-SCA, die python-fints 5.x beim Dialog-Aufbau triggert.
    Bei Sparkassen mit pushTAN wird die TAN schon im Init-Dialog angefordert
    (client.init_tan_response). Diese Funktion muss DIREKT nach 'with client:'
    aufgerufen werden, BEVOR irgendeine Geschaeftsfunktion (get_sepa_accounts etc.)
    ausgefuehrt wird."""
    init_resp = getattr(client, "init_tan_response", None)
    if init_resp is None:
        return False  # Keine SCA noetig
    try:
        from fints.client import NeedRetryResponse
    except Exception:
        return False
    if not isinstance(init_resp, NeedRetryResponse):
        return False
    logger.info("FinTS: PSD2-SCA beim Dialog-Aufbau erkannt, starte Polling...")
    _resolve_decoupled_tan(client, init_resp, max_wait_seconds=max_wait_seconds, poll_interval=poll_interval)
    logger.info("FinTS: PSD2-SCA erfolgreich abgeschlossen")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Persistenter Client-State (PSD2 90-Tage-Regel, MoneyMoney-Style)
# ─────────────────────────────────────────────────────────────────────────────

async def _load_fints_state(db) -> bytes | None:
    """Laedt den persistierten FinTS-Client-State aus der DB (Bytes)."""
    doc = await db.system_settings.find_one({"key": "fints_client_state"}, {"_id": 0})
    if not doc:
        return None
    raw = doc.get("value")
    if not raw:
        return None
    try:
        return base64.b64decode(raw)
    except Exception:
        return None


async def _save_fints_state(db, state_bytes: bytes):
    """Speichert den FinTS-Client-State in der DB (Base64)."""
    encoded = base64.b64encode(state_bytes).decode("ascii") if state_bytes else ""
    await db.system_settings.update_one(
        {"key": "fints_client_state"},
        {"$set": {
            "key": "fints_client_state",
            "value": encoded,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


async def _build_client(db, force_fresh: bool = False):
    """Erzeugt einen FinTS3PinTanClient mit (optional) wiederhergestelltem Bank-State.
    Bei wiederhergestelltem State entfaellt die SCA-Bestaetigung fuer 90 Tage."""
    from fints.client import FinTS3PinTanClient
    creds = get_fints_credentials()
    if not creds:
        return None, None
    state = None if force_fresh else await _load_fints_state(db)
    client = FinTS3PinTanClient(
        FINTS_BLZ,
        creds["user"],
        creds["pin"],
        FINTS_URL,
        product_id=FINTS_PRODUCT_ID,
        product_version=FINTS_PRODUCT_VERSION,
    )
    # State (falls vorhanden) per Methode setzen – seit python-fints 5.x
    if state:
        try:
            client.set_data(state)
            logger.info(f"FinTS: Client-State wiederhergestellt ({len(state)} Bytes)")
        except Exception as e:
            logger.warning(f"FinTS: set_data fehlgeschlagen, starte mit frischem State: {e}")
            state = None
    return client, bool(state)


# ─────────────────────────────────────────────────────────────────────────────
# Transaktions-Parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_tx_data(t) -> dict:
    """Normalisiert eine fints-Transaction (`t.data`) in ein flaches Dict.
    Verschiedene fints-Versionen liefern amount entweder als money.Money-Objekt,
    als dict oder als Plain-Number — alle Faelle hier zentral behandelt."""
    data = t.data
    amount = data.get("amount", {})
    if hasattr(amount, "amount"):
        amt = float(amount.amount)
        cur = str(amount.currency)
    elif hasattr(amount, "get"):
        amt = float(amount.get("amount", 0))
        cur = str(amount.get("currency", "EUR"))
    else:
        amt = float(amount) if amount else 0
        cur = "EUR"
    return {
        "date": str(data.get("date", "")),
        "amount": amt,
        "currency": cur,
        "applicant_name": data.get("applicant_name", "") or "",
        "purpose": data.get("purpose", "") or "",
        "applicant_iban": data.get("applicant_iban", "") or "",
        "posting_text": data.get("posting_text", "") or "",
        "entry_date": str(data.get("entry_date", "")),
    }


async def fetch_transactions_persisted(db, days_back: int = 14) -> dict:
    """Holt Transaktionen mit persistiertem Client-State (MoneyMoney-Stil).
    - Erstanmeldung: pushTAN-Bestaetigung erforderlich, danach State gespeichert
    - Folgeabrufe (90 Tage): voll automatisch ohne TAN
    Liefert dict mit transactions + meta-Info."""
    creds = get_fints_credentials()
    if not creds:
        logger.warning("FinTS: Keine Zugangsdaten konfiguriert")
        return {"transactions": [], "ok": False, "error": "Keine Zugangsdaten"}

    client, restored = await _build_client(db)
    if not client:
        return {"transactions": [], "ok": False, "error": "Keine Zugangsdaten"}

    sca_required = False
    try:
        with client:
            # PSD2-SCA: Bei Sparkassen mit pushTAN wird die TAN bereits
            # beim Dialog-Aufbau angefordert. Zuerst aufloesen!
            sca_required = _resolve_sca_after_dialog_start(client)

            from fints.client import NeedRetryResponse
            accounts_resp = client.get_sepa_accounts()
            if isinstance(accounts_resp, NeedRetryResponse):
                sca_required = True
            accounts = _resolve_decoupled_tan(client, accounts_resp)
            if not accounts:
                return {"transactions": [], "ok": False, "error": "Keine Konten gefunden"}

            target_iban = os.environ.get("FINTS_IBAN", "DE28576500100098066756")
            account = next((a for a in accounts if a.iban == target_iban), accounts[0])

            start_date = datetime.now() - timedelta(days=days_back)
            end_date = datetime.now()
            tx_resp = client.get_transactions(account, start_date=start_date, end_date=end_date)
            if isinstance(tx_resp, NeedRetryResponse):
                sca_required = True
            transactions = _resolve_decoupled_tan(client, tx_resp)

        # State NACH erfolgreicher Anmeldung sichern
        try:
            new_state = client.deconstruct(including_private=True)
            if new_state:
                await _save_fints_state(db, new_state)
                logger.info(f"FinTS: Client-State gespeichert ({len(new_state)} Bytes)")
        except Exception as e:
            logger.warning(f"FinTS: State konnte nicht gespeichert werden: {e}")

        results = [_parse_tx_data(t) for t in transactions]
        logger.info(f"FinTS: {len(results)} Transaktionen (state_restored={restored}, sca_required={sca_required})")
        return {
            "transactions": results,
            "ok": True,
            "state_restored": restored,
            "sca_required": sca_required,
            "iban": account.iban,
        }
    except Exception as e:
        logger.error(f"FinTS Fehler: {e}")
        return {"transactions": [], "ok": False, "error": str(e)[:500]}


# ─────────────────────────────────────────────────────────────────────────────
# Rechnungs-Matching: Text-Normalisierung + Fuzzy-Search
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Entfernt Sonderzeichen und normalisiert Text fuer Vergleich."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _numeric_suffix(s: str) -> str:
    """Extrahiert die letzten Zahlenblock-Ziffern (auch fuehrende Nullen).
    "R26-K-0033" -> "0033",  "K-0014" -> "0014",  "260243" -> "260243"."""
    m = re.search(r"(\d+)\s*$", s or "")
    return m.group(1) if m else ""


def _digit_variants(num_str: str) -> list:
    """Liefert die Ziffer-Varianten fuer einen numerischen Suffix:
    "0033" -> ["0033", "33"],  "0014" -> ["0014", "14"],  "260243" -> ["260243"]."""
    if not num_str:
        return []
    stripped = num_str.lstrip("0") or "0"
    variants = [num_str]
    if stripped != num_str:
        variants.append(stripped)
    return variants


def _find_invoice_number_in_text(text: str, invoice_numbers: list) -> tuple:
    """Sucht eine Rechnungsnummer im Text - auch mit Tippfehlern oder wenn der
    Kunde nur die Ziffern ohne Praefix schreibt.
    Returns: (invoice_number, confidence, match_type)
    """
    text_clean = _normalize(text)

    for inv_nr in invoice_numbers:
        inv_clean = _normalize(inv_nr)

        # Exakter Treffer (normalisiert) - "R26-K-0033" in "kundennummer14rechnungsnummer33..."
        if inv_clean in text_clean:
            return inv_nr, 100, "exakt"

    # ─── ZIFFER-SUFFIX-MATCH: Kunde schreibt oft nur "33" statt "R26-K-0033"
    # Vor der Fuzzy-Suche pruefen wir, ob der numerische Suffix (mit/ohne
    # fuehrende Nullen) im DIRECTEN Umfeld eines Kontext-Wortes steht
    # (Rechnungsnummer/Rg-Nr etc.). "Stromabrechnung 33 kWh" darf NICHT
    # als "R26-K-0033" gematcht werden.
    # Pattern: "Rechnung(snr|Nr|-Nr):? 0033" ODER "Rg-Nr 33" - mit max 20
    # Zeichen Abstand zwischen Keyword und Ziffernblock.
    ctx_pattern = (
        r"(?:rechnungs?[-\s]?(?:nummer|nr|no|number)|rg[-.\s]?nr|beleg[-\s]?nr|invoice\s*(?:no|number|nr))"
        r"[:\s.\-#]*(\d{2,10})"
    )
    for cm in re.finditer(ctx_pattern, (text or ""), re.IGNORECASE):
        num_in_text = cm.group(1)
        for inv_nr in invoice_numbers:
            suffix = _numeric_suffix(inv_nr)
            for variant in _digit_variants(suffix):
                if variant and variant == num_in_text:
                    return inv_nr, 92, "digit_suffix_with_context"

    # Fuzzy-Suche: Zahlendreher, Buchstabendreher
    words = re.split(r"[\s,;./\-]+", text)
    for inv_nr in invoice_numbers:
        inv_clean = _normalize(inv_nr)
        for word in words:
            word_clean = _normalize(word)
            if not word_clean or len(word_clean) < 4:
                continue

            # Levenshtein-aehnliche Pruefung via SequenceMatcher
            ratio = SequenceMatcher(None, inv_clean, word_clean).ratio()
            if ratio >= 0.75 and len(inv_clean) >= 6:
                return inv_nr, int(ratio * 100), "fuzzy"

        # Auch zusammenhaengende Substrings pruefen (wenn jemand z.B. "R26K0001" schreibt)
        for i in range(len(text_clean) - len(inv_clean) + 2):
            chunk = text_clean[i:i + len(inv_clean)]
            if len(chunk) >= len(inv_clean) - 2:
                ratio = SequenceMatcher(None, inv_clean, chunk).ratio()
                if ratio >= 0.80:
                    return inv_nr, int(ratio * 100), "substring_fuzzy"

    return None, 0, "none"


def match_transactions_to_invoices(transactions: list, invoices: list) -> list:
    """Intelligenter Abgleich: Kontobewegungen mit offenen Rechnungen.

    Regeln:
    1. Rechnungsnr. (exakt oder Tippfehler) + Betrag passt → automatisch bezahlt
    2. Rechnungsnr. gefunden aber Betrag weicht ab → Admin-Aufgabe
    3. Nur Betrag + Firmenname → Vorschlag
    """
    matches = []
    inv_numbers = [inv.get("invoice_number", "") for inv in invoices]
    inv_by_number = {inv.get("invoice_number", ""): inv for inv in invoices}

    for tx in transactions:
        if tx["amount"] <= 0:
            continue  # Nur Gutschriften (Eingaenge)

        purpose = tx.get("purpose", "")
        name = tx.get("applicant_name", "")
        amount = tx["amount"]
        search_text = f"{purpose} {name}"

        # Schritt 1: Rechnungsnummer im Verwendungszweck suchen (exakt + fuzzy)
        found_nr, confidence, match_type = _find_invoice_number_in_text(search_text, inv_numbers)

        if found_nr and found_nr in inv_by_number:
            inv = inv_by_number[found_nr]
            brutto = float(inv.get("brutto", 0) or 0)
            deposit_applied = float(inv.get("deposit_applied", 0) or 0)
            # Der Kunde ueberweist typisch den RESTBETRAG (brutto - bereits
            # verrechnete Kaution/Anzahlung). Manche Kunden zahlen aber auch
            # den vollen Brutto-Betrag. Beides gilt als vollstaendige Zahlung.
            open_amount = round(max(0.0, brutto - deposit_applied), 2)
            diff_open = abs(amount - open_amount)
            diff_brutto = abs(amount - brutto)
            amount_diff = min(diff_open, diff_brutto)
            match_target = "restbetrag" if diff_open <= diff_brutto else "brutto"
            expected_str = (
                f"Restbetrag {open_amount:.2f} EUR (Brutto {brutto:.2f} - Kaution {deposit_applied:.2f})"
                if deposit_applied > 0 else f"Brutto {brutto:.2f} EUR"
            )

            if amount_diff <= 0.05:
                # Rechnungsnr. + Betrag stimmt → automatisch bezahlt
                matches.append({
                    "invoice_id": inv["id"],
                    "invoice_number": found_nr,
                    "transaction": tx,
                    "confidence": confidence,
                    "match_type": match_type,
                    "match_reason": f"Rechnungsnr. {found_nr} ({match_type}) + Betrag {amount:.2f} EUR = {match_target}",
                    "action": "auto_paid",
                    "brutto": brutto,
                    "open_amount": open_amount,
                    "deposit_applied": deposit_applied,
                    "matched_against": match_target,
                })
            else:
                # Rechnungsnr. gefunden aber Betrag weicht ab → Admin-Aufgabe
                matches.append({
                    "invoice_id": inv["id"],
                    "invoice_number": found_nr,
                    "transaction": tx,
                    "confidence": confidence,
                    "match_type": match_type,
                    "match_reason": (
                        f"Rechnungsnr. {found_nr} gefunden, aber Betrag weicht ab: "
                        f"erwartet {expected_str}, erhalten {amount:.2f} EUR "
                        f"(Differenz zu Restbetrag: {amount - open_amount:+.2f} EUR)"
                    ),
                    "action": "admin_task",
                    "brutto": brutto,
                    "open_amount": open_amount,
                    "deposit_applied": deposit_applied,
                    "amount_diff": amount - open_amount,
                })
            continue  # Naechste Transaktion

        # Schritt 2: Kein Rechnungsnummer-Match → Betrag + Firmenname als Fallback
        for inv in invoices:
            brutto = float(inv.get("brutto", 0) or 0)
            deposit_applied = float(inv.get("deposit_applied", 0) or 0)
            open_amount = round(max(0.0, brutto - deposit_applied), 2)
            # Erlaubt sowohl Zahlung des Restbetrags als auch des Vollbetrags
            if abs(amount - brutto) > 0.05 and abs(amount - open_amount) > 0.05:
                continue

            firma = (inv.get("schausteller_firma") or "").lower()
            kd_nr = (inv.get("schausteller_kundennummer") or "").lower()
            name_lower = name.lower()
            purpose_lower = purpose.lower()

            # Kundennummer sowohl komplett ("k-0014") als auch nur Ziffern ("0014"/"14") pruefen
            kd_variants = []
            if kd_nr:
                kd_variants.append(kd_nr)
                suffix = _numeric_suffix(kd_nr)
                kd_variants.extend(v for v in _digit_variants(suffix) if v and len(v) >= 2)

            kd_hit = None
            if any(v in purpose_lower for v in kd_variants):
                # Falls nur die Ziffern getroffen wurden, verlangen wir zusaetzlich
                # das Wort "kunde/kd" im Verwendungszweck, damit z.B. "14 kWh"
                # nicht faelschlich als Kundennummer erkannt wird.
                exact_hit = kd_nr and kd_nr in purpose_lower
                context_hit = any(kw in purpose_lower for kw in ("kunde", "kdnr", "kd-nr", "kd.nr", "kundennummer"))
                if exact_hit or context_hit:
                    kd_hit = kd_nr

            if kd_hit:
                matches.append({
                    "invoice_id": inv["id"],
                    "invoice_number": inv["invoice_number"],
                    "transaction": tx,
                    "confidence": 75,
                    "match_type": "kundennummer",
                    "match_reason": f"Kundennr. {inv.get('schausteller_kundennummer')} + Betrag {amount:.2f} EUR",
                    "action": "auto_paid",
                    "brutto": brutto,
                })
                break
            elif firma and (firma in name_lower or firma in purpose_lower):
                matches.append({
                    "invoice_id": inv["id"],
                    "invoice_number": inv["invoice_number"],
                    "transaction": tx,
                    "confidence": 60,
                    "match_type": "firmenname",
                    "match_reason": f"Firmenname '{inv.get('schausteller_firma')}' + Betrag {amount:.2f} EUR (ohne Rechnungsnr.)",
                    "action": "suggestion",
                    "brutto": brutto,
                })
                break

    logger.info(f"FinTS: {len(matches)} Zuordnungen ({sum(1 for m in matches if m['action']=='auto_paid')} auto, "
                f"{sum(1 for m in matches if m['action']=='admin_task')} Admin-Tasks, "
                f"{sum(1 for m in matches if m['action']=='suggestion')} Vorschlaege)")
    return matches


# ─────────────────────────────────────────────────────────────────────────────
# Auto-Match: DB-Updates + Task-Erstellung
# ─────────────────────────────────────────────────────────────────────────────

async def _close_mahnung_tasks(db, invoice_id, reason):
    """Schliesst offene Tasks fuer eine Rechnung (Mahnungen + FinTS-Betrag-
    Mismatch-Tasks). Wird aufgerufen wenn eine Rechnung bezahlt wurde."""
    # Zwei Task-Typen koennen fuer eine Rechnung offen sein:
    # 1. payment_reminder (Mahnung) - verknuepft ueber payment_reminder_invoice_id
    # 2. fints_amount_mismatch - verknuepft ueber fints_invoice_id (Betrag stimmte
    #    nicht, Task fordert manuelle Pruefung an - wenn spaeter doch bezahlt
    #    wurde, muss diese Task auch geschlossen werden)
    now_iso = datetime.now(timezone.utc).isoformat()
    result_mahnung = await db.tasks.update_many(
        {"payment_reminder_invoice_id": invoice_id,
         "completed": False, "is_deleted": {"$ne": True}},
        {"$set": {
            "completed": True,
            "completed_at": now_iso,
            "completed_by_name": reason,
        }}
    )
    result_mismatch = await db.tasks.update_many(
        {"fints_invoice_id": invoice_id,
         "task_type": "fints_amount_mismatch",
         "completed": False, "is_deleted": {"$ne": True}},
        {"$set": {
            "completed": True,
            "completed_at": now_iso,
            "completed_by_name": reason,
        }}
    )
    # Kombiniertes ModifiedCount-Objekt fuer Backwards-Compat mit Callern
    class _CombinedResult:
        def __init__(self, a, b):
            self.modified_count = (a or 0) + (b or 0)
    return _CombinedResult(result_mahnung.modified_count, result_mismatch.modified_count)


async def _sweep_paid_invoices(db) -> int:
    """Sweep: Offene Tasks (Mahnung + Betrag-Mismatch) fuer Rechnungen, die
    bereits als 'bezahlt' markiert sind, automatisch schliessen (Aufraeumen
    falls Tasks vor dem Bezahlt-Status erstellt wurden).
    Returns: Anzahl geschlossener Tasks."""
    # Sammle alle Rechnungs-IDs aus offenen Tasks (beide Task-Typen)
    ids_mahnung = await db.tasks.distinct(
        "payment_reminder_invoice_id",
        {"task_type": "payment_reminder", "completed": False, "is_deleted": {"$ne": True}}
    )
    ids_mismatch = await db.tasks.distinct(
        "fints_invoice_id",
        {"task_type": "fints_amount_mismatch", "completed": False, "is_deleted": {"$ne": True}}
    )
    invoice_ids = list({*(ids_mahnung or []), *(ids_mismatch or [])})
    if not invoice_ids:
        return 0
    paid_invoices = await db.kirmes_invoices.find(
        {"id": {"$in": invoice_ids}, "payment_status": "bezahlt"},
        {"_id": 0, "id": 1}
    ).to_list(5000)
    swept_closed = 0
    for pinv in paid_invoices:
        tc = await _close_mahnung_tasks(db, pinv["id"], "Auto-Cleanup (Rechnung bereits bezahlt)")
        swept_closed += tc.modified_count or 0
    if swept_closed:
        logger.info(f"FinTS Sweep: {swept_closed} offene Task(s) fuer bereits bezahlte Rechnungen geschlossen")
    return swept_closed


async def _resolve_billing_assignees(db) -> tuple[list, dict]:
    """Liefert (ids, name_map) fuer alle Admins + Mitarbeiter mit Abrechnungs-Recht."""
    users = await db.users.find(
        {"$or": [
            {"role": "admin"},
            {"role": "mitarbeiter", "permissions.can_billing": True},
        ], "is_active": {"$ne": False}},
        {"_id": 0, "id": 1, "name": 1}
    ).to_list(50)
    ids = [u["id"] for u in users]
    name_map = {u["id"]: u["name"] for u in users}
    return ids, name_map


async def _mark_invoice_paid(db, m: dict):
    """Markiert eine Rechnung als bezahlt und schliesst offene Mahnungs-Tasks."""
    await db.kirmes_invoices.update_one(
        {"id": m["invoice_id"]},
        {"$set": {
            "payment_status": "bezahlt",
            "paid_at": datetime.now(timezone.utc).isoformat(),
            "paid_amount": m["transaction"]["amount"],
            "payment_note": f"Auto-Zuordnung: {m['match_reason']}",
            "payment_matched_tx": m["transaction"],
            "payment_updated_by": "FinTS Auto-Match",
        }}
    )
    tc = await _close_mahnung_tasks(db, m["invoice_id"], "FinTS Auto-Match (Zahlung eingegangen)")
    if tc.modified_count:
        logger.info(f"FinTS: {tc.modified_count} offene Mahnungs-Task(s) fuer {m['invoice_number']} automatisch geschlossen (Zahlung eingegangen)")
    logger.info(f"FinTS: {m['invoice_number']} → BEZAHLT ({m['match_type']}: {m['match_reason']})")


async def _create_amount_mismatch_task(db, m: dict) -> bool:
    """Erstellt eine Admin-Aufgabe wegen Betragsabweichung (idempotent: skippt
    wenn bereits eine offene Task fuer die Rechnung existiert). Returns: True
    wenn neue Task erstellt wurde."""
    existing = await db.tasks.find_one({
        "fints_invoice_id": m["invoice_id"],
        "task_type": "fints_amount_mismatch",
        "completed": False,
    })
    if existing:
        return False

    admin_ids, admin_names = await _resolve_billing_assignees(db)
    diff = m.get("amount_diff", 0)
    diff_str = f"{diff:+.2f}".replace(".", ",")
    now_iso = datetime.now(timezone.utc).isoformat()

    await db.tasks.insert_one({
        "id": str(uuid.uuid4()),
        "title": f"Zahlung {m['invoice_number']}: Betrag weicht ab ({diff_str} EUR)",
        "description": (
            f"Rechnung {m['invoice_number']} (Soll: {m['brutto']:.2f} EUR) - "
            f"Eingang: {m['transaction']['amount']:.2f} EUR von {m['transaction'].get('applicant_name', '?')}. "
            f"Differenz: {diff_str} EUR. Bitte manuell prüfen."
        ),
        "priority": "high",
        "priority_order": 0,
        "due_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "completed": False,
        "completed_at": None,
        "completed_by": None,
        "completed_by_name": None,
        "created_by": "system",
        "created_by_name": "FinTS Banking",
        "assigned_to": admin_ids,
        "assigned_to_names": admin_names,
        "attachment": None,
        "comment_count": 0,
        "is_deleted": False,
        "created_at": now_iso,
        "updated_at": now_iso,
        "task_type": "fints_amount_mismatch",
        "fints_invoice_id": m["invoice_id"],
        "fints_invoice_number": m["invoice_number"],
        "fints_transaction": m["transaction"],
        "fints_expected": m["brutto"],
        "fints_received": m["transaction"]["amount"],
    })
    logger.info(f"FinTS: {m['invoice_number']} → ADMIN-AUFGABE (Betrag weicht ab: {diff_str} EUR)")
    return True


async def _save_payment_suggestion(db, m: dict):
    """Speichert einen Zahlungs-Vorschlag (Firmenname-Match ohne Rechnungsnr.) an der Rechnung."""
    await db.kirmes_invoices.update_one(
        {"id": m["invoice_id"]},
        {"$set": {
            "payment_suggestion": {
                "transaction": m["transaction"],
                "confidence": m["confidence"],
                "match_reason": m["match_reason"],
                "suggested_at": datetime.now(timezone.utc).isoformat(),
            }
        }}
    )


async def auto_match_and_mark(db, create_admin_tasks=True):
    """Hauptfunktion: Transaktionen holen, abgleichen, automatisch verarbeiten."""
    # 1. Aufraeumen: Mahnungs-Tasks fuer schon-bezahlte Rechnungen schliessen
    swept_closed = await _sweep_paid_invoices(db)

    # 2. Transaktionen abholen (90-Tage-State, ohne pushTAN nach Erstanmeldung)
    result = await fetch_transactions_persisted(db, days_back=30)
    transactions = result.get("transactions", [])
    if not transactions:
        return {"checked": 0, "matched": 0, "auto_marked": 0, "admin_tasks": 0, "suggestions": 0,
                "swept_closed": swept_closed,
                "ok": result.get("ok", False), "error": result.get("error")}

    # 3. Offene Rechnungen laden + abgleichen
    invoices = await db.kirmes_invoices.find(
        {"payment_status": {"$ne": "bezahlt"}},
        {"_id": 0, "id": 1, "invoice_number": 1, "brutto": 1,
         "deposit_applied": 1,  # WICHTIG fuer Restbetrag-Match (Brutto - Kaution)
         "schausteller_firma": 1, "schausteller_kundennummer": 1, "schausteller_name": 1}
    ).to_list(5000)
    matches = match_transactions_to_invoices(transactions, invoices)

    # 4. Jeden Match verarbeiten
    auto_marked = 0
    admin_tasks = 0
    suggestions = 0
    for m in matches:
        if m["action"] == "auto_paid":
            await _mark_invoice_paid(db, m)
            auto_marked += 1
        elif m["action"] == "admin_task" and create_admin_tasks:
            if await _create_amount_mismatch_task(db, m):
                admin_tasks += 1
        elif m["action"] == "suggestion":
            await _save_payment_suggestion(db, m)
            suggestions += 1

    return {
        "checked": len(transactions),
        "matched": len(matches),
        "auto_marked": auto_marked,
        "admin_tasks": admin_tasks,
        "suggestions": suggestions,
        "swept_closed": swept_closed,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Eingangsrechnungen: Ausgehende Buchungen gegen Eingangsrechnungen matchen
# (Sammelüberweisungen ausdrücklich ausgeschlossen — jede Buchung = 1 Rechnung)
# ─────────────────────────────────────────────────────────────────────────────

def _match_outgoing_to_incoming(transactions: list, invoices: list) -> list:
    """Matcht ausgehende Bankbuchungen (amount < 0) gegen offene Eingangsrechnungen.

    Regeln (analog Kirmes-Match, aber invertiert):
    1. Rechnungsnr. im Verwendungszweck + Betrag passt (±0.05) → auto_paid
    2. Rechnungsnr. gefunden aber Betrag weicht ab → admin_task
    3. Kein Rechnungsnr.-Match aber Absender-Name + Betrag eindeutig → auto_paid (confidence 70)
    4. Absender-Name + Betrag, aber mehrere Kandidaten → admin_task (ambig)
    """
    matches = []
    inv_numbers = [inv.get("invoice_number", "") for inv in invoices if inv.get("invoice_number")]
    inv_by_number = {inv.get("invoice_number", ""): inv for inv in invoices if inv.get("invoice_number")}

    for tx in transactions:
        amt = tx.get("amount", 0)
        if amt >= 0:
            continue  # Nur Belastungen (Ausgänge)
        paid_amount = abs(amt)

        purpose = tx.get("purpose", "") or ""
        recipient = tx.get("applicant_name", "") or ""  # Bei Belastungen = Empfänger
        search_text = f"{purpose} {recipient}"

        # Schritt 1: Rechnungsnummer im Verwendungszweck?
        found_nr, confidence, match_type = _find_invoice_number_in_text(search_text, inv_numbers)

        if found_nr and found_nr in inv_by_number:
            inv = inv_by_number[found_nr]
            expected = float(inv.get("amount", 0) or 0)
            diff = paid_amount - expected

            if abs(diff) <= 0.05:
                matches.append({
                    "invoice_id": inv["id"],
                    "invoice_number": found_nr,
                    "sender": inv.get("sender", ""),
                    "transaction": tx,
                    "paid_amount": paid_amount,
                    "expected": expected,
                    "confidence": confidence,
                    "match_type": match_type,
                    "match_reason": f"Rechnungsnr. {found_nr} ({match_type}) + Betrag {paid_amount:.2f} EUR",
                    "action": "auto_paid",
                })
            else:
                matches.append({
                    "invoice_id": inv["id"],
                    "invoice_number": found_nr,
                    "sender": inv.get("sender", ""),
                    "transaction": tx,
                    "paid_amount": paid_amount,
                    "expected": expected,
                    "amount_diff": diff,
                    "confidence": confidence,
                    "match_type": match_type,
                    "match_reason": (
                        f"Rechnungsnr. {found_nr} gefunden, Betrag weicht ab: "
                        f"erwartet {expected:.2f}, gezahlt {paid_amount:.2f} EUR "
                        f"(Differenz: {diff:+.2f} EUR)"
                    ),
                    "action": "admin_task",
                })
            continue

        # Schritt 2: Kein Rechnungsnr.-Match → Absender + Betrag prüfen
        candidates = []
        recipient_norm = _normalize(recipient)
        purpose_norm = _normalize(purpose)
        for inv in invoices:
            expected = float(inv.get("amount", 0) or 0)
            if abs(paid_amount - expected) > 0.05:
                continue
            sender = inv.get("sender", "") or ""
            if not sender:
                continue
            sender_norm = _normalize(sender)
            # Wort-basierter Vergleich: mindestens ein aussagekräftiges Sender-Wort
            # (>=4 Zeichen) muss im Empfänger oder Verwendungszweck stehen.
            sender_words = [w for w in re.split(r"\s+", sender_norm) if len(w) >= 4]
            hit = any(w in recipient_norm or w in purpose_norm for w in sender_words)
            if not hit:
                # Fallback: SequenceMatcher gegen den kompletten Empfänger-Namen
                if recipient_norm and SequenceMatcher(None, sender_norm, recipient_norm).ratio() >= 0.7:
                    hit = True
            if hit:
                candidates.append(inv)

        if len(candidates) == 1:
            inv = candidates[0]
            matches.append({
                "invoice_id": inv["id"],
                "invoice_number": inv.get("invoice_number", ""),
                "sender": inv.get("sender", ""),
                "transaction": tx,
                "paid_amount": paid_amount,
                "expected": float(inv.get("amount", 0) or 0),
                "confidence": 70,
                "match_type": "sender_amount",
                "match_reason": f"Absender '{inv.get('sender', '')}' + Betrag {paid_amount:.2f} EUR",
                "action": "auto_paid",
            })
        elif len(candidates) > 1:
            matches.append({
                "invoice_id": None,
                "invoice_number": None,
                "sender": recipient,
                "transaction": tx,
                "paid_amount": paid_amount,
                "candidate_ids": [c["id"] for c in candidates],
                "candidate_numbers": [c.get("invoice_number", "") for c in candidates],
                "confidence": 40,
                "match_type": "ambiguous",
                "match_reason": (
                    f"{len(candidates)} Rechnungen mit gleichem Betrag {paid_amount:.2f} EUR "
                    f"und Absender '{recipient}' - bitte manuell zuordnen: "
                    + ", ".join(c.get("invoice_number", "?") for c in candidates)
                ),
                "action": "admin_task_ambiguous",
            })

    logger.info(
        f"FinTS Eingangsrechnungen: {len(matches)} Zuordnungen "
        f"({sum(1 for m in matches if m['action']=='auto_paid')} auto, "
        f"{sum(1 for m in matches if m['action'].startswith('admin_task'))} Admin-Tasks)"
    )
    return matches


async def _mark_incoming_invoice_paid(db, m: dict):
    """Markiert eine Eingangsrechnung als bezahlt (FinTS Auto-Match, final)."""
    await db.documents.update_one(
        {"id": m["invoice_id"]},
        {"$set": {
            "eingang_paid": True,
            "eingang_paid_at": datetime.now(timezone.utc).isoformat(),
            "eingang_paid_source": f"FinTS Auto-Match ({m['match_type']}): {m['match_reason']}",
            "eingang_paid_tx": m["transaction"],
        }}
    )
    logger.info(f"FinTS Eingangsrechnung: {m['invoice_number']} → BEZAHLT ({m['match_type']})")


async def _create_incoming_amount_mismatch_task(db, m: dict) -> bool:
    """Admin-Task bei Betragsabweichung einer Eingangsrechnung (idempotent)."""
    existing = await db.tasks.find_one({
        "fints_incoming_invoice_id": m["invoice_id"],
        "task_type": "fints_incoming_amount_mismatch",
        "completed": False,
    })
    if existing:
        return False
    admin_ids, admin_names = await _resolve_billing_assignees(db)
    diff = m.get("amount_diff", 0)
    diff_str = f"{diff:+.2f}".replace(".", ",")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.tasks.insert_one({
        "id": str(uuid.uuid4()),
        "title": f"Eingangsrechnung {m['invoice_number']}: Betrag weicht ab ({diff_str} EUR)",
        "description": (
            f"Eingangsrechnung {m['invoice_number']} von {m.get('sender', '?')} "
            f"(Soll: {m['expected']:.2f} EUR) - Bezahlt: {m['paid_amount']:.2f} EUR. "
            f"Differenz: {diff_str} EUR. Bitte manuell prüfen."
        ),
        "priority": "high", "priority_order": 0,
        "due_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "completed": False, "completed_at": None,
        "completed_by": None, "completed_by_name": None,
        "created_by": "system", "created_by_name": "FinTS Banking (Eingang)",
        "assigned_to": admin_ids, "assigned_to_names": admin_names,
        "attachment": None, "comment_count": 0, "is_deleted": False,
        "created_at": now_iso, "updated_at": now_iso,
        "task_type": "fints_incoming_amount_mismatch",
        "fints_incoming_invoice_id": m["invoice_id"],
        "fints_incoming_invoice_number": m["invoice_number"],
        "fints_transaction": m["transaction"],
        "fints_expected": m["expected"],
        "fints_paid": m["paid_amount"],
    })
    logger.info(f"FinTS Eingang: {m['invoice_number']} → ADMIN-AUFGABE (Diff {diff_str})")
    return True


async def _create_incoming_ambiguous_task(db, m: dict) -> bool:
    """Admin-Task bei mehreren Kandidaten (gleiche Summe + Absender)."""
    tx = m["transaction"]
    # Idempotenz: gleiche Buchung + gleiche Kandidaten
    tx_key = f"{tx.get('date')}_{tx.get('amount')}_{tx.get('applicant_name')}"
    existing = await db.tasks.find_one({
        "task_type": "fints_incoming_ambiguous",
        "fints_tx_key": tx_key,
        "completed": False,
    })
    if existing:
        return False
    admin_ids, admin_names = await _resolve_billing_assignees(db)
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.tasks.insert_one({
        "id": str(uuid.uuid4()),
        "title": f"Zahlung {m['paid_amount']:.2f} EUR: {len(m['candidate_ids'])} passende Eingangsrechnungen",
        "description": (
            f"Buchung {m['paid_amount']:.2f} EUR an '{m.get('sender', '?')}' passt zu mehreren "
            f"offenen Eingangsrechnungen mit gleichem Betrag und Absender:\n"
            f"→ {', '.join(m['candidate_numbers'])}\n"
            "Bitte in den Eingangsrechnungen manuell die richtige Rechnung als bezahlt markieren."
        ),
        "priority": "high", "priority_order": 0,
        "due_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "completed": False, "completed_at": None,
        "completed_by": None, "completed_by_name": None,
        "created_by": "system", "created_by_name": "FinTS Banking (Eingang)",
        "assigned_to": admin_ids, "assigned_to_names": admin_names,
        "attachment": None, "comment_count": 0, "is_deleted": False,
        "created_at": now_iso, "updated_at": now_iso,
        "task_type": "fints_incoming_ambiguous",
        "fints_tx_key": tx_key,
        "fints_transaction": tx,
        "fints_candidate_ids": m["candidate_ids"],
        "fints_candidate_numbers": m["candidate_numbers"],
    })
    logger.info(f"FinTS Eingang: AMBIG → Admin-Task ({len(m['candidate_ids'])} Kandidaten, {m['paid_amount']:.2f} EUR)")
    return True


async def auto_match_incoming_invoices(db, create_admin_tasks=True, days_back: int = 60):
    """Hauptfunktion Eingangsrechnungen: FinTS-Transaktionen (Sparkasse) gegen
    offene Eingangsrechnungen aus rechnungseingang_*-Ordnern abgleichen."""
    result = await fetch_transactions_persisted(db, days_back=days_back)
    transactions = result.get("transactions", [])
    if not transactions:
        return {"checked": 0, "matched": 0, "auto_marked": 0, "admin_tasks": 0,
                "ambiguous": 0, "ok": result.get("ok", False), "error": result.get("error")}

    # Offene Eingangsrechnungen laden
    docs = await db.documents.find(
        {"folder_id": {"$regex": "^rechnungseingang_"},
         "is_deleted": {"$ne": True},
         "eingang_paid": {"$ne": True}},
        {"_id": 0, "id": 1, "ai_metadata": 1}
    ).to_list(5000)
    invoices = []
    for d in docs:
        meta = d.get("ai_metadata") or {}
        try:
            amount = float(meta.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount <= 0:
            continue  # ohne Betrag kein Auto-Match
        invoices.append({
            "id": d["id"],
            "invoice_number": (meta.get("invoice_number") or "").strip(),
            "amount": amount,
            "sender": (meta.get("sender") or "").strip(),
        })

    matches = _match_outgoing_to_incoming(transactions, invoices)

    auto_marked = 0
    admin_tasks = 0
    ambiguous = 0
    for m in matches:
        if m["action"] == "auto_paid":
            await _mark_incoming_invoice_paid(db, m)
            auto_marked += 1
        elif m["action"] == "admin_task" and create_admin_tasks:
            if await _create_incoming_amount_mismatch_task(db, m):
                admin_tasks += 1
        elif m["action"] == "admin_task_ambiguous" and create_admin_tasks:
            if await _create_incoming_ambiguous_task(db, m):
                ambiguous += 1

    return {
        "checked": len(transactions),
        "matched": len(matches),
        "auto_marked": auto_marked,
        "admin_tasks": admin_tasks,
        "ambiguous": ambiguous,
        "ok": True,
    }
