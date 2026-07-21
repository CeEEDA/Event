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
# Multi-Bank-Konfiguration
# Bank 1: Sparkasse (Standard, bestehende ENV-Variablen fuer Backward Compat)
# Bank 2: Volksbank (optional, ENV-Variablen mit Praefix FINTS_VB_)
# Weitere Banken koennen durch Ergaenzung dieser Liste einfach hinzugefuegt werden.
# ─────────────────────────────────────────────────────────────────────────────

def _bank_configs() -> list:
    """Liefert die Liste konfigurierter Banken (Sparkasse + optional Volksbank).
    Banken ohne User/PIN in der ENV werden uebersprungen."""
    banks = []
    # Sparkasse (existierend)
    if os.environ.get("FINTS_USER") and os.environ.get("FINTS_PIN"):
        banks.append({
            "key": "sparkasse",
            "name": "Sparkasse",
            "url": FINTS_URL,
            "blz": FINTS_BLZ,
            "user": os.environ.get("FINTS_USER", ""),
            "pin": os.environ.get("FINTS_PIN", ""),
            "iban": os.environ.get("FINTS_IBAN", "DE28576500100098066756"),
            "product_id": FINTS_PRODUCT_ID,
            "product_version": FINTS_PRODUCT_VERSION,
        })
    # Volksbank (neu, optional)
    if os.environ.get("FINTS_VB_USER") and os.environ.get("FINTS_VB_PIN"):
        banks.append({
            "key": "volksbank",
            "name": "Volksbank",
            "url": os.environ.get("FINTS_VB_URL", ""),
            "blz": os.environ.get("FINTS_VB_BLZ", ""),
            "user": os.environ.get("FINTS_VB_USER", ""),
            "pin": os.environ.get("FINTS_VB_PIN", ""),
            "iban": os.environ.get("FINTS_VB_IBAN", ""),
            "product_id": os.environ.get("FINTS_VB_PRODUCT_ID", "") or DEFAULT_FINTS_PRODUCT_ID,
            "product_version": os.environ.get("FINTS_VB_PRODUCT_VERSION", "") or DEFAULT_FINTS_PRODUCT_VERSION,
        })
    return banks


# ─────────────────────────────────────────────────────────────────────────────
# Credentials + Client-Setup
# ─────────────────────────────────────────────────────────────────────────────

def get_fints_credentials():
    """Backward-Compat: gibt die Sparkassen-Zugangsdaten zurueck (aeltere Aufrufer).
    Neue Aufrufer sollten _bank_configs() verwenden."""
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

async def _load_fints_state(db, bank_key: str = "sparkasse") -> bytes | None:
    """Laedt den persistierten FinTS-Client-State aus der DB (Bytes).
    Pro Bank wird ein eigener State-Key verwendet, damit mehrere Banken parallel
    ihre PSD2-90-Tage-Sessions halten koennen."""
    # Backward-Compat: alter Key ohne Bank-Suffix wird fuer 'sparkasse' weiter genutzt
    key = "fints_client_state" if bank_key == "sparkasse" else f"fints_client_state_{bank_key}"
    doc = await db.system_settings.find_one({"key": key}, {"_id": 0})
    if not doc:
        return None
    raw = doc.get("value")
    if not raw:
        return None
    try:
        return base64.b64decode(raw)
    except Exception:
        return None


async def _save_fints_state(db, state_bytes: bytes, bank_key: str = "sparkasse"):
    """Speichert den FinTS-Client-State in der DB (Base64), bank-spezifisch."""
    key = "fints_client_state" if bank_key == "sparkasse" else f"fints_client_state_{bank_key}"
    encoded = base64.b64encode(state_bytes).decode("ascii") if state_bytes else ""
    await db.system_settings.update_one(
        {"key": key},
        {"$set": {
            "key": key,
            "value": encoded,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


async def _build_client(db, force_fresh: bool = False, bank: dict | None = None):
    """Erzeugt einen FinTS3PinTanClient mit (optional) wiederhergestelltem Bank-State.
    Bei wiederhergestelltem State entfaellt die SCA-Bestaetigung fuer 90 Tage.
    Wenn ``bank`` None ist, wird die Sparkasse (Backward-Compat) verwendet."""
    from fints.client import FinTS3PinTanClient
    if bank is None:
        creds = get_fints_credentials()
        if not creds:
            return None, None
        bank = {
            "key": "sparkasse", "url": FINTS_URL, "blz": FINTS_BLZ,
            "user": creds["user"], "pin": creds["pin"],
            "product_id": FINTS_PRODUCT_ID, "product_version": FINTS_PRODUCT_VERSION,
        }
    if not (bank.get("user") and bank.get("pin") and bank.get("url") and bank.get("blz")):
        return None, None
    state = None if force_fresh else await _load_fints_state(db, bank_key=bank["key"])
    client = FinTS3PinTanClient(
        bank["blz"],
        bank["user"],
        bank["pin"],
        bank["url"],
        product_id=bank.get("product_id") or DEFAULT_FINTS_PRODUCT_ID,
        product_version=bank.get("product_version") or DEFAULT_FINTS_PRODUCT_VERSION,
    )
    if state:
        try:
            client.set_data(state)
            logger.info(f"FinTS [{bank['key']}]: Client-State wiederhergestellt ({len(state)} Bytes)")
        except Exception as e:
            logger.warning(f"FinTS [{bank['key']}]: set_data fehlgeschlagen, starte mit frischem State: {e}")
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


async def _fetch_from_bank(db, bank: dict, days_back: int) -> dict:
    """Holt Transaktionen einer einzelnen Bank mit ihrem persistierten State."""
    client, restored = await _build_client(db, bank=bank)
    if not client:
        return {"transactions": [], "ok": False, "error": "Keine Zugangsdaten", "bank": bank["key"]}

    sca_required = False
    try:
        with client:
            sca_required = _resolve_sca_after_dialog_start(client)
            from fints.client import NeedRetryResponse
            accounts_resp = client.get_sepa_accounts()
            if isinstance(accounts_resp, NeedRetryResponse):
                sca_required = True
            accounts = _resolve_decoupled_tan(client, accounts_resp)
            if not accounts:
                return {"transactions": [], "ok": False, "error": "Keine Konten gefunden", "bank": bank["key"]}

            target_iban = bank.get("iban", "")
            account = next((a for a in accounts if a.iban == target_iban), accounts[0])

            start_date = datetime.now() - timedelta(days=days_back)
            end_date = datetime.now()
            tx_resp = client.get_transactions(account, start_date=start_date, end_date=end_date)
            if isinstance(tx_resp, NeedRetryResponse):
                sca_required = True
            transactions = _resolve_decoupled_tan(client, tx_resp)

        try:
            new_state = client.deconstruct(including_private=True)
            if new_state:
                await _save_fints_state(db, new_state, bank_key=bank["key"])
                logger.info(f"FinTS [{bank['key']}]: Client-State gespeichert ({len(new_state)} Bytes)")
        except Exception as e:
            logger.warning(f"FinTS [{bank['key']}]: State konnte nicht gespeichert werden: {e}")

        results = []
        for t in transactions:
            row = _parse_tx_data(t)
            row["bank"] = bank["key"]
            row["bank_name"] = bank.get("name", bank["key"])
            row["bank_iban"] = account.iban
            results.append(row)
        logger.info(f"FinTS [{bank['key']}]: {len(results)} Transaktionen "
                    f"(restored={restored}, sca_required={sca_required})")
        return {
            "transactions": results,
            "ok": True,
            "state_restored": restored,
            "sca_required": sca_required,
            "iban": account.iban,
            "bank": bank["key"],
        }
    except Exception as e:
        logger.error(f"FinTS [{bank['key']}] Fehler: {e}")
        return {"transactions": [], "ok": False, "error": str(e)[:500], "bank": bank["key"]}


async def fetch_transactions_persisted(db, days_back: int = 14) -> dict:
    """Holt Transaktionen mit persistiertem Client-State (MoneyMoney-Stil) ueber
    ALLE konfigurierten Banken (Sparkasse + optional Volksbank). Ergebnis-Format
    bleibt kompatibel zu bisherigen Aufrufern: ``transactions`` ist die aggregierte
    Liste; ``banks`` gibt Detail-Ergebnisse pro Bank zurueck.
    - Erstanmeldung pro Bank: pushTAN erforderlich, State wird bank-spezifisch gespeichert
    - Folgeabrufe (90 Tage): voll automatisch pro Bank
    """
    banks = _bank_configs()
    if not banks:
        logger.warning("FinTS: Keine Bank konfiguriert (weder Sparkasse noch Volksbank)")
        return {"transactions": [], "ok": False, "error": "Keine Zugangsdaten"}

    all_transactions = []
    bank_results = []
    any_ok = False
    errors = []
    for bank in banks:
        res = await _fetch_from_bank(db, bank, days_back)
        bank_results.append(res)
        if res.get("ok"):
            any_ok = True
            all_transactions.extend(res.get("transactions") or [])
        else:
            errors.append(f"{bank['key']}: {res.get('error')}")

    return {
        "transactions": all_transactions,
        "ok": any_ok,
        "banks": bank_results,
        "error": None if any_ok else "; ".join(errors) or "Keine Zugangsdaten",
    }


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

    Match-Typen:
    - ``exakt`` (conf 100): vollstaendige Rechnungsnummer als Substring gefunden
    - ``digit_suffix_with_context`` (conf 92): Kunde schreibt nur den Ziffern-
      Suffix in Zusammenhang mit "Rechnungsnr:" o.ae. Nur bei Suffixen >= 3 Ziffern
      damit "Rechnung 32" nicht faelschlich R26-K-0032 matcht.
    - ``fuzzy`` (conf ~85-95): Tippfehler-tolerantes Match, Ratio >= 0.90
    """
    text_clean = _normalize(text)

    for inv_nr in invoice_numbers:
        inv_clean = _normalize(inv_nr)

        # Exakter Treffer (normalisiert) - "R26-K-0033" in "kundennummer14rechnungsnummer33..."
        if inv_clean in text_clean:
            return inv_nr, 100, "exakt"

    # ─── ZIFFER-SUFFIX-MATCH: Kunde schreibt oft nur "0033" statt "R26-K-0033"
    # Vor der Fuzzy-Suche pruefen wir, ob der numerische Suffix im DIRECTEN
    # Umfeld eines Kontext-Wortes steht (Rechnungsnummer/Rg-Nr etc.).
    # WICHTIG: Suffix muss >= 3 Ziffern haben, sonst kollidieren Zahlen wie
    # "Rechnung 32" fuer irgendeine Rechnungsserie mit R26-K-0032.
    ctx_pattern = (
        r"(?:rechnungs?[-\s]?(?:nummer|nr|no|number)|rg[-.\s]?nr|beleg[-\s]?nr|invoice\s*(?:no|number|nr))"
        r"[:\s.\-#]*(\d{3,10})"
    )
    for cm in re.finditer(ctx_pattern, (text or ""), re.IGNORECASE):
        num_in_text = cm.group(1)
        for inv_nr in invoice_numbers:
            suffix = _numeric_suffix(inv_nr)
            if len(suffix) < 3:
                continue
            for variant in _digit_variants(suffix):
                if len(variant) < 3:
                    continue
                if variant == num_in_text:
                    return inv_nr, 92, "digit_suffix_with_context"

    # Fuzzy-Suche: Zahlendreher, Buchstabendreher. Nur bei sehr hoher Aehnlichkeit
    # (>= 0.90) damit z.B. R26-K-0004 nicht auf R25-K-0004 einer alten Serie
    # matched. Zusaetzlich: der numerische Suffix MUSS identisch sein (letzte
    # Ziffern gleich) damit Zahlendreher kein anderes Konto trifft.
    words = re.split(r"[\s,;./\-]+", text)
    for inv_nr in invoice_numbers:
        inv_clean = _normalize(inv_nr)
        inv_suffix = _numeric_suffix(inv_nr)
        if len(inv_clean) < 6:
            continue
        for word in words:
            word_clean = _normalize(word)
            if len(word_clean) < 6:
                continue
            ratio = SequenceMatcher(None, inv_clean, word_clean).ratio()
            if ratio < 0.90:
                continue
            # Zusatz-Guard: die Ziffern-Endung muss identisch sein
            word_suffix = _numeric_suffix(word)
            if inv_suffix and word_suffix and inv_suffix != word_suffix:
                continue
            return inv_nr, int(ratio * 100), "fuzzy"

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
            elif match_type == "exakt":
                # Rechnungsnr. EXAKT gefunden aber Betrag weicht ab → potenzieller Admin-Task.
                # ABER: Wir pruefen zusaetzliche Guards um False-Positives zu vermeiden,
                # z.B. wenn ein fremder Zahler die Rechnungsnummer nur zitiert oder
                # eine Sammelueberweisung mehrere Rechnungen abdeckt.

                # ─── Guard 1: Sammelueberweisung erkennen ─────────────────
                # Wenn 2+ verschiedene Rechnungsnummern gleichzeitig im Text
                # als Substring vorkommen, pruefen wir ob die SUMME der
                # Rechnungen dem Transaktionsbetrag entspricht → Auto-Split:
                # alle Rechnungen werden als bezahlt markiert.
                text_clean = _normalize(search_text)
                other_hits = [
                    n for n in inv_numbers
                    if n != found_nr and _normalize(n) in text_clean
                ]
                if other_hits:
                    all_hits = [found_nr] + other_hits
                    all_invs = [inv_by_number[n] for n in all_hits if n in inv_by_number]
                    total_open = 0.0
                    total_brutto = 0.0
                    for i in all_invs:
                        b = float(i.get("brutto", 0) or 0)
                        d = float(i.get("deposit_applied", 0) or 0)
                        total_brutto += b
                        total_open += max(0.0, b - d)
                    # Toleranz proportional zur Anzahl der Rechnungen
                    # (jeweils 5 Cent Rundungsdifferenz erlaubt)
                    tol = 0.05 * max(1, len(all_invs))
                    diff_to_open = abs(amount - total_open)
                    diff_to_brutto = abs(amount - total_brutto)
                    if diff_to_open <= tol or diff_to_brutto <= tol:
                        matched_target = "restbetrag" if diff_to_open <= diff_to_brutto else "brutto"
                        logger.info(
                            f"FinTS: Sammelueberweisung AUTO-SPLIT: "
                            f"{len(all_invs)} Rechnungen ({', '.join(all_hits[:5])}), "
                            f"Summe {amount:.2f} EUR = {matched_target} "
                            f"(diff {min(diff_to_open, diff_to_brutto):+.2f} EUR)"
                        )
                        for sub_inv in all_invs:
                            sub_b = float(sub_inv.get("brutto", 0) or 0)
                            sub_d = float(sub_inv.get("deposit_applied", 0) or 0)
                            sub_open = round(max(0.0, sub_b - sub_d), 2)
                            sub_amt = sub_open if matched_target == "restbetrag" else sub_b
                            matches.append({
                                "invoice_id": sub_inv["id"],
                                "invoice_number": sub_inv.get("invoice_number"),
                                "transaction": tx,
                                "confidence": 95,
                                "match_type": "sammel_split",
                                "match_reason": (
                                    f"Sammelueberweisung ({len(all_invs)} Rechnungen: "
                                    f"{', '.join(all_hits)}) - Summe {amount:.2f} EUR = "
                                    f"{matched_target}"
                                ),
                                "action": "auto_paid",
                                "brutto": sub_b,
                                "open_amount": sub_open,
                                "deposit_applied": sub_d,
                                "matched_against": matched_target,
                                "sammel_amount": round(sub_amt, 2),
                                "sammel_group": all_hits,
                            })
                        continue  # Transaktion vollstaendig verarbeitet
                    # Summe passt NICHT → nicht als Task erzeugen (unsicher)
                    logger.info(
                        f"FinTS: Sammelueberweisung erkannt fuer {found_nr} "
                        f"(+{len(other_hits)} weitere: {', '.join(other_hits[:3])}) "
                        f"aber Summen passen nicht (amount {amount:.2f} vs "
                        f"open {total_open:.2f} / brutto {total_brutto:.2f}) - kein Task"
                    )
                    found_nr = None
                    continue

                # ─── Guard 2: Zahler muss zur Rechnung passen ────────────
                # Der Bank-Absender (applicant_name) sollte Ähnlichkeit zum
                # Schausteller-Firma/Nachnamen haben ODER die Kundennummer
                # der Rechnung muss im Purpose auftauchen. Sonst hat vermutlich
                # ein fremder Zahler die Rechnungsnummer nur zufaellig
                # zitiert (z.B. bei OP-Referenz).
                schausteller_firma = (inv.get("schausteller_firma") or "").lower().strip()
                schausteller_name = (inv.get("schausteller_name") or "").lower().strip()
                schausteller_kd = (inv.get("schausteller_kundennummer") or "").lower().strip()
                zahler_lower = name.lower().strip()
                purpose_lower = purpose.lower()

                def _has_name_match():
                    if not zahler_lower:
                        return False
                    # Rechtsform-Woerter sind Trivialmatch → ausschliessen
                    NOISE = {"gmbh", "kg", "ag", "ug", "ohg", "gbr", "co", "se", "ltd",
                             "inc", "llc", "corp", "kgaa", "sarl", "bv", "nv", "sa",
                             "srl", "spa", "&", "und", "der", "die", "das", "the"}
                    def _tokens(s):
                        return [t for t in re.split(r"[\s,.\-/&]+", s or "")
                                if t and len(t) >= 4 and t.lower() not in NOISE]
                    zahler_tokens = _tokens(zahler_lower)
                    for haystack in (schausteller_firma, schausteller_name):
                        if not haystack:
                            continue
                        haystack_tokens = _tokens(haystack)
                        for token in haystack_tokens:
                            if token in zahler_lower:
                                return True
                        for token in zahler_tokens:
                            if token in haystack:
                                return True
                        # Fuzzy als letzter Ausweg
                        if SequenceMatcher(None, zahler_lower[:30], haystack[:30]).ratio() >= 0.55:
                            return True
                    return False

                def _has_customer_number_hit():
                    if not schausteller_kd:
                        return False
                    # Wir betrachten den Purpose OHNE die bereits gefundene
                    # Rechnungsnr. (weil sie typisch die Kundennr. als Suffix
                    # enthaelt und ein "K-0032"-Match sonst redundant waere).
                    inv_norm = _normalize(found_nr)
                    purpose_wo_inv_norm = _normalize(purpose_lower).replace(inv_norm, "", 1)
                    kd_norm = _normalize(schausteller_kd)
                    if kd_norm and kd_norm in purpose_wo_inv_norm:
                        return True
                    suffix = _numeric_suffix(schausteller_kd)
                    if not suffix or len(suffix) < 3:
                        return False
                    if suffix not in purpose_wo_inv_norm:
                        return False
                    # Ziffernsuffix alleine reicht nur mit Kontext-Wort
                    if not any(kw in purpose_lower for kw in ("kunde", "kdnr", "kd-nr", "kd.nr", "kundennummer")):
                        return False
                    return True

                if not (_has_name_match() or _has_customer_number_hit()):
                    logger.info(
                        f"FinTS: Rechnungsnr. {found_nr} im Purpose gefunden, "
                        f"aber Zahler '{name}' passt nicht zu "
                        f"'{schausteller_firma or schausteller_name}' und "
                        f"Kundennr. '{schausteller_kd}' nicht im Purpose. "
                        f"Vermutlich Fremdzitat - kein Task."
                    )
                    found_nr = None
                    continue

                # Alle Guards ueberstanden: echte Betragsabweichung → Admin-Task
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
            else:
                # Fuzzy/Digit-Suffix Match aber Betrag stimmt nicht → wir sind
                # unsicher ob es ueberhaupt diese Rechnung war. Kein Task,
                # aber weiter zum Firmenname-Fallback.
                logger.info(
                    f"FinTS: Unsicherer Match {found_nr} ({match_type}, "
                    f"conf {confidence}) verworfen wegen Betragsabweichung "
                    f"{amount - open_amount:+.2f} EUR"
                )
                # Fallthrough zum naechsten Schritt (Betrag+Firmenname)
                found_nr = None
            if found_nr:
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
    bereits als 'bezahlt' markiert sind, automatisch schliessen. ZUSAETZLICH:
    Re-validiert alle offenen fints_amount_mismatch-Tasks gegen die aktuellen
    Guards - Tasks die die Guards nicht mehr passieren werden auto-geschlossen
    (z.B. Fremdzahler-Zitate, Sammelueberweisungen).
    Returns: Anzahl geschlossener Tasks."""
    now_iso = datetime.now(timezone.utc).isoformat()
    swept_closed = 0

    # ── Schritt 1: Tasks fuer bereits bezahlte Rechnungen schliessen ──
    ids_mahnung = await db.tasks.distinct(
        "payment_reminder_invoice_id",
        {"task_type": "payment_reminder", "completed": False, "is_deleted": {"$ne": True}}
    )
    ids_mismatch = await db.tasks.distinct(
        "fints_invoice_id",
        {"task_type": "fints_amount_mismatch", "completed": False, "is_deleted": {"$ne": True}}
    )
    invoice_ids = list({*(ids_mahnung or []), *(ids_mismatch or [])})
    if invoice_ids:
        paid_invoices = await db.kirmes_invoices.find(
            {"id": {"$in": invoice_ids}, "payment_status": "bezahlt"},
            {"_id": 0, "id": 1}
        ).to_list(5000)
        for pinv in paid_invoices:
            tc = await _close_mahnung_tasks(db, pinv["id"], "Auto-Cleanup (Rechnung bereits bezahlt)")
            swept_closed += tc.modified_count or 0

    # ── Schritt 2: Alle offenen fints_amount_mismatch-Tasks re-validieren ──
    # Bug-Fix: Tasks aus fruehren Match-Laeufen bleiben persistent auch wenn
    # der Matcher inzwischen strengere Guards hat. Wir wenden die Guards
    # jetzt auch auf existierende Tasks an.
    open_mismatch = await db.tasks.find(
        {"task_type": "fints_amount_mismatch", "completed": False, "is_deleted": {"$ne": True}},
        {"_id": 0, "id": 1, "fints_invoice_id": 1, "fints_invoice_number": 1,
         "fints_transaction": 1}
    ).to_list(1000)

    # Alle offenen Kirmes-Rechnungen laden (nur unbezahlte relevant)
    all_open_inv = await db.kirmes_invoices.find(
        {"payment_status": {"$ne": "bezahlt"}},
        {"_id": 0, "id": 1, "invoice_number": 1, "schausteller_firma": 1,
         "schausteller_name": 1, "schausteller_kundennummer": 1}
    ).to_list(5000)
    inv_by_id = {i["id"]: i for i in all_open_inv}
    all_inv_numbers = [i.get("invoice_number", "") for i in all_open_inv if i.get("invoice_number")]

    stale_ids = []
    for t in open_mismatch:
        inv = inv_by_id.get(t.get("fints_invoice_id"))
        if not inv:
            # Rechnung existiert nicht mehr oder ist bereits bezahlt → Task stale
            stale_ids.append(t["id"])
            continue
        tx = t.get("fints_transaction") or {}
        purpose = tx.get("purpose") or ""
        name = tx.get("applicant_name") or ""
        # Guard 1: Sammelueberweisung
        text_clean = _normalize(f"{purpose} {name}")
        found_nr = inv.get("invoice_number", "")
        other_hits = [n for n in all_inv_numbers if n != found_nr and _normalize(n) in text_clean]
        if other_hits:
            stale_ids.append(t["id"])
            continue
        # Guard 2: Zahler-Verifikation
        schausteller_firma = (inv.get("schausteller_firma") or "").lower()
        schausteller_name = (inv.get("schausteller_name") or "").lower()
        schausteller_kd = (inv.get("schausteller_kundennummer") or "").lower()
        zahler_lower = name.lower()
        purpose_lower = purpose.lower()

        NOISE = {"gmbh", "kg", "ag", "ug", "ohg", "gbr", "co", "se", "ltd",
                 "inc", "llc", "corp", "kgaa", "sarl", "bv", "nv", "sa",
                 "srl", "spa", "und", "der", "die", "das", "the"}
        def _tokens(s):
            return [tok for tok in re.split(r"[\s,.\-/&]+", s or "")
                    if tok and len(tok) >= 4 and tok.lower() not in NOISE]
        name_match = False
        zahler_tokens = _tokens(zahler_lower)
        for haystack in (schausteller_firma, schausteller_name):
            if not haystack: continue
            haystack_tokens = _tokens(haystack)
            if any(tok in zahler_lower for tok in haystack_tokens):
                name_match = True; break
            if any(tok in haystack for tok in zahler_tokens):
                name_match = True; break
            if SequenceMatcher(None, zahler_lower[:30], haystack[:30]).ratio() >= 0.55:
                name_match = True; break

        kd_hit = False
        if schausteller_kd:
            inv_norm = _normalize(found_nr)
            p_norm_wo_inv = _normalize(purpose_lower).replace(inv_norm, "", 1)
            kd_norm = _normalize(schausteller_kd)
            if kd_norm and kd_norm in p_norm_wo_inv:
                kd_hit = True
            else:
                suffix = _numeric_suffix(schausteller_kd)
                if suffix and len(suffix) >= 3 and suffix in p_norm_wo_inv:
                    if any(kw in purpose_lower for kw in ("kunde", "kdnr", "kd-nr", "kd.nr", "kundennummer")):
                        kd_hit = True

        if not (name_match or kd_hit):
            stale_ids.append(t["id"])

    if stale_ids:
        res = await db.tasks.update_many(
            {"id": {"$in": stale_ids}},
            {"$set": {
                "completed": True,
                "completed_at": now_iso,
                "completed_by_name": "Auto-Cleanup (Matcher-Guard aktualisiert)",
                "dismissed_reason": "Auto-revalidiert: Fremdzahler/Sammel oder Rechnung nicht mehr offen",
            }}
        )
        swept_closed += res.modified_count or 0
        logger.info(
            f"FinTS Sweep: {res.modified_count} alte False-Positive-Tasks "
            f"automatisch geschlossen (Guard-Revalidation)"
        )

    if swept_closed:
        logger.info(f"FinTS Sweep total: {swept_closed} offene Task(s) geschlossen")
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
    """Markiert eine Rechnung als bezahlt und schliesst offene Mahnungs-Tasks.
    Bei Sammel-Splits wird der anteilige Betrag (`sammel_amount`) statt der
    vollen Transaktions-Summe als paid_amount gespeichert."""
    paid_amount = m.get("sammel_amount", m["transaction"]["amount"])
    note = f"Auto-Zuordnung: {m['match_reason']}"
    await db.kirmes_invoices.update_one(
        {"id": m["invoice_id"]},
        {"$set": {
            "payment_status": "bezahlt",
            "paid_at": datetime.now(timezone.utc).isoformat(),
            "paid_amount": paid_amount,
            "payment_note": note,
            "payment_matched_tx": m["transaction"],
            "payment_updated_by": "FinTS Auto-Match",
            **({"sammel_group": m["sammel_group"]} if m.get("sammel_group") else {}),
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
                    "match_reason": (
                        f"Rechnungsnr. {found_nr} ({match_type}) + Betrag {paid_amount:.2f} EUR"
                        f" [{tx.get('bank_name') or tx.get('bank') or 'Bank'}]"
                    ),
                    "action": "auto_paid",
                })
                continue
            elif match_type == "exakt":
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
            else:
                # Fuzzy/Digit-Suffix mit Betragsabweichung → unsicher, kein Task
                logger.info(
                    f"FinTS (outgoing): Unsicherer Match {found_nr} "
                    f"({match_type}, conf {confidence}) verworfen wegen "
                    f"Betragsabweichung {diff:+.2f} EUR"
                )
                # Kein Match fuer diese Transaktion (weiter zur naechsten)
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
                "match_reason": (
                    f"Absender '{inv.get('sender', '')}' + Betrag {paid_amount:.2f} EUR"
                    f" [{tx.get('bank_name') or tx.get('bank') or 'Bank'}]"
                ),
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
