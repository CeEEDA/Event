"""
FinTS/HBCI Banking Integration - Kreissparkasse Mayen
Liest Kontobewegungen und gleicht sie mit offenen Rechnungen ab.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("fints_banking")

# Sparkasse Mayen FinTS Konfiguration
FINTS_URL = "https://banking-rp1.s-fints-pt-rp.de/fints30"
FINTS_BLZ = "57650010"


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
            product_id=None,
        )

        accounts = client.get_sepa_accounts()
        if not accounts:
            logger.warning("FinTS: Keine Konten gefunden")
            return []

        # IBAN DE28576500100098066756 suchen
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
            results.append({
                "date": str(data.get("date", "")),
                "amount": float(data.get("amount", {}).get("amount", 0)) if hasattr(data.get("amount", {}), "get") else float(data.get("amount", 0)),
                "currency": str(data.get("amount", {}).get("currency", "EUR")) if hasattr(data.get("amount", {}), "get") else "EUR",
                "applicant_name": data.get("applicant_name", ""),
                "purpose": data.get("purpose", ""),
                "applicant_iban": data.get("applicant_iban", ""),
                "posting_text": data.get("posting_text", ""),
                "entry_date": str(data.get("entry_date", "")),
            })

        logger.info(f"FinTS: {len(results)} Transaktionen geladen ({days_back} Tage)")
        return results

    except Exception as e:
        logger.error(f"FinTS Fehler: {e}")
        return []


def match_transactions_to_invoices(transactions: list, invoices: list) -> list:
    """Gleicht Kontobewegungen mit offenen Rechnungen ab.
    Matching-Kriterien (Prioritaet):
    1. Rechnungsnummer im Verwendungszweck + Betrag stimmt
    2. Kundennummer im Verwendungszweck + Betrag stimmt
    3. Firmenname + Betrag stimmt
    """
    matches = []

    for tx in transactions:
        if tx["amount"] <= 0:
            continue  # Nur Gutschriften (Eingaenge)

        purpose = (tx.get("purpose") or "").lower()
        name = (tx.get("applicant_name") or "").lower()
        amount = tx["amount"]

        for inv in invoices:
            inv_nr = (inv.get("invoice_number") or "").lower()
            kd_nr = (inv.get("schausteller_kundennummer") or "").lower()
            firma = (inv.get("schausteller_firma") or "").lower()
            brutto = inv.get("brutto", 0)

            # Betrag muss ungefaehr stimmen (+-0.05 EUR Toleranz)
            if abs(amount - brutto) > 0.05:
                continue

            confidence = 0
            match_reason = ""

            # Rechnungsnummer im Verwendungszweck
            if inv_nr and inv_nr.replace("-", "") in purpose.replace("-", "").replace(" ", ""):
                confidence = 95
                match_reason = f"Rechnungsnummer {inv['invoice_number']} im Verwendungszweck"

            # Kundennummer im Verwendungszweck
            elif kd_nr and kd_nr in purpose:
                confidence = 80
                match_reason = f"Kundennummer {inv.get('schausteller_kundennummer')} im Verwendungszweck"

            # Firmenname + Betrag
            elif firma and (firma in name or firma in purpose):
                confidence = 70
                match_reason = f"Firmenname '{inv.get('schausteller_firma')}' + Betrag {brutto:.2f} EUR"

            if confidence > 0:
                matches.append({
                    "invoice_id": inv["id"],
                    "invoice_number": inv["invoice_number"],
                    "transaction": tx,
                    "confidence": confidence,
                    "match_reason": match_reason,
                    "brutto": brutto,
                })
                break  # Eine Transaktion pro Rechnung

    logger.info(f"FinTS: {len(matches)} Zuordnungen gefunden")
    return matches


async def auto_match_and_mark(db, auto_confirm_threshold: int = 90):
    """Hauptfunktion: Transaktionen holen, abgleichen, bei hoher Konfidenz automatisch als bezahlt markieren."""
    transactions = fetch_transactions(days_back=30)
    if not transactions:
        return {"checked": 0, "matched": 0, "auto_marked": 0}

    # Offene Rechnungen laden
    invoices = await db.kirmes_invoices.find(
        {"payment_status": {"$ne": "bezahlt"}},
        {"_id": 0, "id": 1, "invoice_number": 1, "brutto": 1,
         "schausteller_firma": 1, "schausteller_kundennummer": 1, "schausteller_name": 1}
    ).to_list(5000)

    matches = match_transactions_to_invoices(transactions, invoices)

    auto_marked = 0
    for m in matches:
        # Hohe Konfidenz → automatisch als bezahlt markieren
        if m["confidence"] >= auto_confirm_threshold:
            await db.kirmes_invoices.update_one(
                {"id": m["invoice_id"]},
                {"$set": {
                    "payment_status": "bezahlt",
                    "paid_at": datetime.now(timezone.utc).isoformat(),
                    "paid_amount": m["transaction"]["amount"],
                    "payment_note": f"Automatisch zugeordnet: {m['match_reason']}",
                    "payment_matched_tx": m["transaction"],
                    "payment_updated_by": "FinTS Auto-Match",
                }}
            )
            auto_marked += 1
            logger.info(f"FinTS: {m['invoice_number']} automatisch als bezahlt markiert ({m['confidence']}% Konfidenz)")
        else:
            # Niedrige Konfidenz → als Vorschlag speichern (Admin prueft)
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
            logger.info(f"FinTS: {m['invoice_number']} Vorschlag gespeichert ({m['confidence']}% Konfidenz)")

    return {
        "checked": len(transactions),
        "matched": len(matches),
        "auto_marked": auto_marked,
        "suggestions": len(matches) - auto_marked,
    }
