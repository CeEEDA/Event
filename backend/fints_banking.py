"""
FinTS/HBCI Banking Integration - Kreissparkasse Mayen
Liest Kontobewegungen und gleicht sie mit offenen Rechnungen ab.
"""
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

logger = logging.getLogger("fints_banking")

# FinTS-Konfiguration (konfigurierbar via .env)
# Defaults: Kreissparkasse Mayen (fuer Eventenergie Deutschland).
# Ueber die Umgebungsvariablen FINTS_URL und FINTS_BLZ ueberschreibbar.
FINTS_URL = os.environ.get("FINTS_URL", "https://banking-rp1.s-fints-pt-rp.de/fints30")
FINTS_BLZ = os.environ.get("FINTS_BLZ", "57650010")


def get_fints_credentials():
    """Liest FinTS-Zugangsdaten aus Umgebungsvariablen."""
    user = os.environ.get("FINTS_USER", "")
    pin = os.environ.get("FINTS_PIN", "")
    if not user or not pin:
        return None
    return {"user": user, "pin": pin}


def fetch_transactions(days_back: int = 14) -> list:
    """Holt Kontobewegungen der letzten X Tage via FinTS."""
    creds = get_fints_credentials()
    if not creds:
        logger.warning("FinTS: Keine Zugangsdaten konfiguriert")
        return []

    try:
        from fints.client import FinTS3PinTanClient

        client = FinTS3PinTanClient(
            FINTS_BLZ,
            creds["user"],
            creds["pin"],
            FINTS_URL,
            product_id=os.environ.get("FINTS_PRODUCT_ID", ""),
        )

        accounts = client.get_sepa_accounts()
        if not accounts:
            logger.warning("FinTS: Keine Konten gefunden")
            return []

        target_iban = os.environ.get("FINTS_IBAN", "DE28576500100098066756")
        account = None
        for a in accounts:
            if a.iban == target_iban:
                account = a
                break
        if not account:
            account = accounts[0]
            logger.info(f"FinTS: Ziel-IBAN nicht gefunden, nutze {account.iban}")

        start_date = datetime.now() - timedelta(days=days_back)
        end_date = datetime.now()

        with client:
            transactions = client.get_transactions(account, start_date=start_date, end_date=end_date)

        results = []
        for t in transactions:
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

            results.append({
                "date": str(data.get("date", "")),
                "amount": amt,
                "currency": cur,
                "applicant_name": data.get("applicant_name", "") or "",
                "purpose": data.get("purpose", "") or "",
                "applicant_iban": data.get("applicant_iban", "") or "",
                "posting_text": data.get("posting_text", "") or "",
                "entry_date": str(data.get("entry_date", "")),
            })

        logger.info(f"FinTS: {len(results)} Transaktionen geladen ({days_back} Tage)")
        return results

    except Exception as e:
        logger.error(f"FinTS Fehler: {e}")
        return []


def _normalize(text: str) -> str:
    """Entfernt Sonderzeichen und normalisiert Text fuer Vergleich."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _find_invoice_number_in_text(text: str, invoice_numbers: list) -> tuple:
    """Sucht eine Rechnungsnummer im Text - auch mit Tippfehlern.
    Returns: (invoice_number, confidence, match_type)
    """
    text_clean = _normalize(text)

    for inv_nr in invoice_numbers:
        inv_clean = _normalize(inv_nr)

        # Exakter Treffer (normalisiert)
        if inv_clean in text_clean:
            return inv_nr, 100, "exakt"

    # Fuzzy-Suche: Zahlendreher, Buchstabendreher
    # Zerlege den Text in Woerter und pruefe Aehnlichkeit
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
            brutto = inv.get("brutto", 0)
            amount_diff = abs(amount - brutto)

            if amount_diff <= 0.05:
                # Rechnungsnr. + Betrag stimmt → automatisch bezahlt
                matches.append({
                    "invoice_id": inv["id"],
                    "invoice_number": found_nr,
                    "transaction": tx,
                    "confidence": confidence,
                    "match_type": match_type,
                    "match_reason": f"Rechnungsnr. {found_nr} ({match_type}) + Betrag {amount:.2f} EUR stimmt",
                    "action": "auto_paid",
                    "brutto": brutto,
                })
            else:
                # Rechnungsnr. gefunden aber Betrag weicht ab → Admin-Aufgabe
                matches.append({
                    "invoice_id": inv["id"],
                    "invoice_number": found_nr,
                    "transaction": tx,
                    "confidence": confidence,
                    "match_type": match_type,
                    "match_reason": f"Rechnungsnr. {found_nr} gefunden, aber Betrag weicht ab: erwartet {brutto:.2f} EUR, erhalten {amount:.2f} EUR (Differenz: {amount - brutto:+.2f} EUR)",
                    "action": "admin_task",
                    "brutto": brutto,
                    "amount_diff": amount - brutto,
                })
            continue  # Naechste Transaktion

        # Schritt 2: Kein Rechnungsnummer-Match → Betrag + Firmenname als Fallback
        for inv in invoices:
            brutto = inv.get("brutto", 0)
            if abs(amount - brutto) > 0.05:
                continue

            firma = (inv.get("schausteller_firma") or "").lower()
            kd_nr = (inv.get("schausteller_kundennummer") or "").lower()
            name_lower = name.lower()
            purpose_lower = purpose.lower()

            if kd_nr and kd_nr in purpose_lower:
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


async def auto_match_and_mark(db, create_admin_tasks=True):
    """Hauptfunktion: Transaktionen holen, abgleichen, automatisch verarbeiten."""
    import uuid

    transactions = fetch_transactions(days_back=30)
    if not transactions:
        return {"checked": 0, "matched": 0, "auto_marked": 0, "admin_tasks": 0, "suggestions": 0}

    # Offene Rechnungen laden
    invoices = await db.kirmes_invoices.find(
        {"payment_status": {"$ne": "bezahlt"}},
        {"_id": 0, "id": 1, "invoice_number": 1, "brutto": 1,
         "schausteller_firma": 1, "schausteller_kundennummer": 1, "schausteller_name": 1}
    ).to_list(5000)

    matches = match_transactions_to_invoices(transactions, invoices)

    auto_marked = 0
    admin_tasks = 0
    suggestions = 0

    for m in matches:
        if m["action"] == "auto_paid":
            # Automatisch als bezahlt markieren
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
            auto_marked += 1
            logger.info(f"FinTS: {m['invoice_number']} → BEZAHLT ({m['match_type']}: {m['match_reason']})")

        elif m["action"] == "admin_task" and create_admin_tasks:
            # Betrag weicht ab → Admin-Aufgabe erstellen
            existing = await db.tasks.find_one({
                "fints_invoice_id": m["invoice_id"],
                "task_type": "fints_amount_mismatch",
                "completed": False,
            })
            if not existing:
                admins = await db.users.find({"role": "admin"}, {"_id": 0, "id": 1, "name": 1}).to_list(50)
                admin_ids = [a["id"] for a in admins]
                admin_names = {a["id"]: a["name"] for a in admins}
                diff = m.get("amount_diff", 0)
                diff_str = f"{diff:+.2f}".replace(".", ",")

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
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "task_type": "fints_amount_mismatch",
                    "fints_invoice_id": m["invoice_id"],
                    "fints_invoice_number": m["invoice_number"],
                    "fints_transaction": m["transaction"],
                    "fints_expected": m["brutto"],
                    "fints_received": m["transaction"]["amount"],
                })
                admin_tasks += 1
                logger.info(f"FinTS: {m['invoice_number']} → ADMIN-AUFGABE (Betrag weicht ab: {diff_str} EUR)")

        elif m["action"] == "suggestion":
            # Nur Vorschlag speichern
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
            suggestions += 1

    return {
        "checked": len(transactions),
        "matched": len(matches),
        "auto_marked": auto_marked,
        "admin_tasks": admin_tasks,
        "suggestions": suggestions,
    }
