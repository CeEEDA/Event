"""Heuristik-Fallback fuer die Dokumenten-Analyse wenn Ollama nicht verfuegbar
ist. Nutzt PyMuPDF + Regex + Firmen-Signatur-Check um zumindest eine grobe
Klassifikation zu ermoeglichen (Ausgangsrechnung / Eingangsrechnung / Bestellung /
Sonstiges) und die Kern-Metadaten (Rechnungsnummer, Datum, Betrag, Absender) zu
extrahieren. Ergebnis wird mit `_authoritative_source = "fallback_heuristic"`
markiert und bekommt `ai_status = "completed"` mit Hinweis, dass User optional
"KI neu analysieren" klicken kann sobald Ollama wieder laeuft.
"""
import re
from datetime import datetime, timezone
from typing import Optional

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None


# Firma(en) des Systembetreibers - wenn dieser Name als Absender im Text steht,
# ist es eine Ausgangsrechnung. Wenn als Empfaenger, dann Eingangsrechnung.
# Optional ueber ENV SELF_COMPANIES (kommaseparierte Liste) erweiterbar.
import os as _os
_env_companies = [c.strip() for c in _os.environ.get("SELF_COMPANIES", "").split(",") if c.strip()]
SELF_COMPANY_MARKERS = list({
    "Eventenergie Deutschland",
    "eventenergie deutschland",
    "EVENTENERGIE DEUTSCHLAND",
    "Power Factor Engineering",
    "power factor engineering",
    "POWER FACTOR ENGINEERING",
    *_env_companies,
})
SELF_IBAN_PATTERNS = [
    # Firmen-IBAN (kann ueber ENV/Config eingespeist werden)
]


def _extract_text(pdf_bytes: bytes) -> str:
    """Extrahiert Volltext aus PDF-Bytes ohne KI."""
    if not fitz:
        return ""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
            return "\n".join((p.get_text("text") or "") for p in pdf).strip()
    except Exception:
        return ""


def _find_first(patterns: list[str], text: str, group: int = 0) -> Optional[str]:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            try:
                return m.group(group).strip()
            except IndexError:
                return m.group(0).strip()
    return None


def _extract_invoice_number(text: str, filename: str) -> Optional[str]:
    # Zuerst Dateiname: "Rechnung_260257_..." -> 260257
    m = re.search(r"[Rr]echnung[_ ]?(?:[Nn]r\.?[_ ]?)?(\d{4,15})", filename)
    if m:
        return m.group(1)
    # Dann Text
    patterns = [
        r"Rechnungs?[- ]?[Nn]r\.?\s*:?\s*([A-Z0-9\-/]{3,25})",
        r"Rechnung\s+[Nn]r\.?\s*:?\s*([A-Z0-9\-/]{3,25})",
        r"Invoice\s+No\.?\s*:?\s*([A-Z0-9\-/]{3,25})",
        r"Beleg[- ]?[Nn]r\.?\s*:?\s*([A-Z0-9\-/]{3,25})",
    ]
    return _find_first(patterns, text, group=1)


def _extract_date(text: str) -> Optional[str]:
    patterns = [
        r"Rechnungsdatum\s*:?\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})",
        r"Datum\s*:?\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})",
        r"vom\s+(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})",
        r"(\d{4}-\d{2}-\d{2})",
    ]
    raw = _find_first(patterns, text, group=1)
    if not raw:
        return None
    # Normalisieren auf YYYY-MM-DD
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def _extract_amount(text: str) -> Optional[float]:
    # Priorisiere "Gesamtbetrag" / "Zu zahlen" / "Rechnungsbetrag" mit EUR
    priority_labels = [
        r"Gesamtbetrag\s+brutto\s*:?\s*([\d.]+,\d{2})",
        r"Rechnungsbetrag\s*:?\s*([\d.]+,\d{2})",
        r"Zu\s+zahlen(?:der\s+Betrag)?\s*:?\s*([\d.]+,\d{2})",
        r"Endbetrag\s*:?\s*([\d.]+,\d{2})",
        r"Gesamtsumme\s*:?\s*([\d.]+,\d{2})",
        r"Summe\s+brutto\s*:?\s*([\d.]+,\d{2})",
    ]
    raw = _find_first(priority_labels, text, group=1)
    if not raw:
        # Fallback: hoechster EUR-Betrag im Doc
        matches = re.findall(r"([\d.]{1,10},\d{2})\s*(?:EUR|€)", text)
        if not matches:
            return None
        try:
            return max(float(m.replace(".", "").replace(",", ".")) for m in matches)
        except ValueError:
            return None
    try:
        return float(raw.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _extract_iban(text: str) -> Optional[str]:
    m = re.search(r"DE\s?(?:\d\s?){20}", text)
    return m.group(0).replace(" ", "") if m else None


def _detect_direction(text: str, filename: str) -> tuple[str, str, str]:
    """Bestimmt Sender/Empfaenger/Richtung.
    Returns (direction, sender, recipient).

    Kernregel (robust gegen wechselnde deutsche Rechnungs-Layouts):
    1. Eigene E-Mail-Domain/URL im Text → Ausgangsrechnung (wir sind Absender)
    2. Eigener Firmenname irgendwo im Text, ABER OHNE eigene Domain → Eingangsrechnung
       (der Fremdanbieter adressiert uns; er hat nicht unsere E-Mail-Adresse im Header)
    3. Ohne beide Marker → unknown
    """
    tlow = text.lower()

    # 1. Starke Ausgangs-Indikatoren: eigene E-Mail-Adresse ODER www-URL
    # (NICHT: reiner Domain-Name als String — der taucht in Produkt-Rechnungen auf,
    # z.B. wenn wir eine SaaS-Instanz mit Namen "eventenergie.app" kaufen)
    self_domain_markers = [
        "@eventenergie-deutschland.de",
        "@eventenergie.app",
        "@powerfactor-engineering.de",
        "www.eventenergie-deutschland.de",
        "www.powerfactor-engineering.de",
    ]
    has_own_domain = any(m in tlow for m in self_domain_markers)

    # 2. Eigenen Firmennamen erkennen
    self_name_markers = ("eventenergie deutschland", "eventenergie-deutschland",
                         "power factor engineering", "powerfactor engineering")
    has_own_name = any(m in tlow for m in self_name_markers)

    if has_own_domain:
        # Sicherheitsnetz: Wenn zusaetzlich eine FREMDE E-Mail-Adresse im Text steht,
        # ist unsere E-Mail wahrscheinlich die Bill-To-Adresse (Empfaenger), nicht
        # der Absender. Beispiel: Emergent Labs schickt uns Rechnung an accounting@..
        import re as _re
        all_emails = _re.findall(r"[a-zA-Z0-9._+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", tlow)
        foreign_emails = [
            e for e in all_emails
            if not any(dom in e for dom in
                       ("eventenergie-deutschland.de", "eventenergie.app",
                        "powerfactor-engineering.de"))
        ]
        if foreign_emails:
            # Fremde Absender-E-Mail vorhanden → wir sind Empfaenger → Eingangsrechnung
            sender = _extract_sender_from_header(text) or ""
            return (
                "rechnungseingang_eventenergie_deutschland",
                sender,
                "Eventenergie Deutschland GmbH & Co. KG",
            )
        # Keine fremden E-Mail-Adressen im Text: wir sind Absender → Ausgangsrechnung
        recipient = _extract_top_address_recipient(text) or ""
        return (
            "rechnungsausgang_eventenergie_deutschland",
            "Eventenergie Deutschland GmbH & Co. KG",
            recipient,
        )

    if has_own_name:
        # Firmenname da, aber keine eigene Domain → wir sind Empfaenger → Eingangsrechnung
        sender = _extract_sender_from_header(text) or ""
        return (
            "rechnungseingang_eventenergie_deutschland",
            sender,
            "Eventenergie Deutschland GmbH & Co. KG",
        )

    return ("unknown", _extract_sender_from_header(text) or "", "")


def _extract_top_address_recipient(text: str) -> Optional[str]:
    """Empfaenger: erste sinnvolle Zeile des Docs (Firmenname im Adressblock
    oben links). Skipped generic labels wie 'Rechnung' oder 'Datum'."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines[:6]:
        if re.match(r"^(Rechnung|Invoice|Bestellung|Angebot|Datum|Seite|Betreff)\b", ln, re.IGNORECASE):
            continue
        if len(ln) < 3 or len(ln) > 120:
            continue
        # Skip pure Postfach/Straße/PLZ-Zeilen - der Firmenname kommt zuerst
        if re.match(r"^\d{5}\s+", ln) or re.match(r"^[A-Za-zäöüß.\- ]+\s+\d+[a-z]?$", ln):
            continue
        return ln
    return None


def _extract_sender_from_header(text: str) -> Optional[str]:
    """Sender ist meist die erste nicht-leere Zeile (Firmenname) oder auf Briefkopf ganz oben."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines[:8]:
        # Skip generic labels
        if re.match(r"^(Rechnung|Invoice|Bestellung|Angebot|Datum|Seite)\b", ln, re.IGNORECASE):
            continue
        if len(ln) < 3 or len(ln) > 120:
            continue
        return ln
    return None


def _extract_recipient_after_addressline(text: str) -> Optional[str]:
    """Empfaenger ist im Anschreibe-Block, oft nach der Zeile "Rechnung an" oder
    einfach im linken Adressbereich."""
    # Suche nach 'Rechnung an' / 'Kunde:' / 'Empfaenger'
    m = re.search(r"(?:Rechnung\s+an|Kunde|Empf(?:ae|\u00e4)nger|Bill\s+to)\s*:?\s*\n?([A-Z][^\n]{2,80})", text)
    if m:
        return m.group(1).strip()
    return None


def analyze_document_fallback(pdf_bytes: bytes, filename: str) -> dict:
    """Deterministische Ollama-freie Dokumenten-Analyse.

    Returns ein ai_result-Dict, das kompatibel zu dem ist was Ollama sonst
    zurueckliefert (suggested_folder, sender, recipient, invoice_number,
    date, amount, subject, full_text, keywords).
    """
    text = _extract_text(pdf_bytes)

    # Wenn nichts extrahierbar (z.B. Scan ohne OCR), fallback auf filename+leer
    if not text:
        return {
            "document_type": "unknown",
            "suggested_folder": "unbekannt",
            "sender": "",
            "recipient": "",
            "invoice_number": None,
            "date": None,
            "amount": None,
            "currency": "EUR",
            "subject": filename,
            "full_text": "",
            "keywords": [],
            "_authoritative_source": "fallback_heuristic_no_text",
            "_fallback_reason": "PDF enthaelt keinen extrahierbaren Text (evtl. Scan ohne OCR)",
        }

    direction, sender, recipient = _detect_direction(text, filename)
    inv_num = _extract_invoice_number(text, filename)
    date = _extract_date(text)
    amount = _extract_amount(text)
    iban = _extract_iban(text)

    # Dokumenttyp aus Dateiname/Text-Keywords ableiten
    tlow = text.lower()
    fn_lower = filename.lower()
    if "bestellung" in fn_lower or "bestellung" in tlow[:500]:
        doc_type = "bestellung"
        if direction == "unknown":
            direction = "bestellungen_eingang"
    elif "angebot" in fn_lower or "angebot" in tlow[:500]:
        doc_type = "angebot"
    elif "lieferschein" in fn_lower or "lieferschein" in tlow[:500]:
        doc_type = "lieferschein"
    elif "mahnung" in fn_lower or "mahnung" in tlow[:500]:
        doc_type = "mahnung"
        direction = direction if direction != "unknown" else "rechnungseingang_eventenergie_deutschland"
    elif "rechnung" in fn_lower or "rechnung" in tlow[:500] or "invoice" in tlow[:500]:
        doc_type = "rechnung"
    else:
        doc_type = "unknown"

    if direction == "unknown":
        direction = "unbekannt"

    subject = f"{doc_type.title()}"
    if inv_num:
        subject += f" {inv_num}"
    if sender and direction.startswith("rechnungseingang"):
        subject += f" von {sender}"
    elif recipient and direction.startswith("rechnungsausgang"):
        subject += f" an {recipient}"

    # Keywords fuer die Suche
    keywords = []
    if inv_num:
        keywords.append(inv_num)
    if sender:
        keywords.append(sender.split(",")[0].strip()[:60])
    if recipient:
        keywords.append(recipient.split(",")[0].strip()[:60])
    if iban:
        keywords.append(iban)
    keywords = [k for k in keywords if k]

    return {
        "document_type": doc_type,
        "suggested_folder": direction,
        "sender": sender or "",
        "recipient": recipient or "",
        "invoice_number": inv_num,
        "date": date,
        "amount": amount,
        "currency": "EUR",
        "subject": subject[:200],
        "full_text": text[:20000],  # cap
        "keywords": keywords[:15],
        "iban": iban,
        "_authoritative_source": "fallback_heuristic",
        "_fallback_reason": "Ollama nicht erreichbar - heuristische Text-Analyse verwendet",
        "_fallback_at": datetime.now(timezone.utc).isoformat(),
    }
