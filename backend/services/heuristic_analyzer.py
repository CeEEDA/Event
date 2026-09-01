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
    """Extrahiert Volltext aus PDF-Bytes ohne KI.

    `sort=True` sortiert die Text-Bloecke nach Y-dann-X Koordinate. Damit landen
    Firmenkopf/Belegdatum vor der Positionstabelle - viele Layouts (z.B. Anton
    Radosevic Werkstatt-Rechnung) liefern sonst Tabellenspalten wie "Preis \u20ac"
    ganz oben, was Sender-/Datums-Heuristiken korrumpiert.
    """
    if not fitz:
        return ""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
            return "\n".join((p.get_text("text", sort=True) or "") for p in pdf).strip()
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


def _extract_labelled_column(text: str) -> dict:
    """Erkennt Label/Wert-Layouts in denen Labels und Werte auf getrennten Zeilen
    stehen. Deckt zwei Varianten ab:

    Variante A (Spalten-Stapel):
        Rechnungsnr.:
        Kundennr.:
        Datum:

        RE26/020
        10008
        15.06.2026

    Variante B (Interleaved, klassisch NL/international):
        Datum:
        13-06-26
        Factuurnummer:
        2026197
        BTW nummer
        DE 309 259 209

    Returns dict mit normalisierten Schluesseln: invoice_number, customer_number,
    date, service_period, due_date, payment_terms.
    """
    lines = [ln.strip() for ln in text.splitlines()]
    LABEL_MAP = [
        (re.compile(r"^Rechnungs?[- ]?(Nr|Nummer)\.?\s*:?\s*$", re.IGNORECASE), "invoice_number"),
        (re.compile(r"^Factuur(?:[- ]?nummer|[- ]?nr)\.?\s*:?\s*$", re.IGNORECASE), "invoice_number"),
        (re.compile(r"^Invoice\s*(?:no\.?|number|nr\.?)\s*:?\s*$", re.IGNORECASE), "invoice_number"),
        (re.compile(r"^Kunden[- ]?(Nr|Nummer)\.?\s*:?\s*$", re.IGNORECASE), "customer_number"),
        (re.compile(r"^Debiteur(?:[- ]?nummer|[- ]?nr)\.?\s*:?\s*$", re.IGNORECASE), "customer_number"),
        (re.compile(r"^Customer\s*(?:no\.?|number)\s*:?\s*$", re.IGNORECASE), "customer_number"),
        (re.compile(r"^Beleg[- ]?(Nr|Nummer)\.?\s*:?\s*$", re.IGNORECASE), "invoice_number"),
        (re.compile(r"^Datum\s*:?\s*$", re.IGNORECASE), "date"),
        (re.compile(r"^Rechnungsdatum\s*:?\s*$", re.IGNORECASE), "date"),
        (re.compile(r"^Invoice\s+date\s*:?\s*$", re.IGNORECASE), "date"),
        (re.compile(r"^Leistungszeitraum\s*:?\s*$", re.IGNORECASE), "service_period"),
        (re.compile(r"^F(?:ae|\u00e4)lligkeit(?:sdatum)?\s*:?\s*$", re.IGNORECASE), "due_date"),
        (re.compile(r"^Zahlungsziel\s*:?\s*$", re.IGNORECASE), "due_date"),
        (re.compile(r"^Zahlbar\s+bis\s*:?\s*$", re.IGNORECASE), "due_date"),
        (re.compile(r"^Due\s+date\s*:?\s*$", re.IGNORECASE), "due_date"),
        (re.compile(r"^Vervaldatum\s*:?\s*$", re.IGNORECASE), "due_date"),
    ]
    label_re = LABEL_MAP  # alias for internal loop clarity

    def _is_label(ln: str):
        for pat, field in label_re:
            if pat.match(ln):
                return field
        return None

    result = {}
    i = 0
    while i < len(lines):
        # Skip leere Zeilen
        if not lines[i]:
            i += 1
            continue
        first_field = _is_label(lines[i])
        if not first_field:
            i += 1
            continue
        # Sammle konsekutive Label-Zeilen (nur nicht-leere)
        label_block = [first_field]
        j = i + 1
        while j < len(lines):
            ln = lines[j]
            if not ln:
                j += 1
                continue
            f = _is_label(ln)
            if f:
                label_block.append(f)
                j += 1
            else:
                break
        # Sammle die naechsten len(label_block) nicht-leeren Nicht-Label-Zeilen
        values = []
        k = j
        while k < len(lines) and len(values) < len(label_block):
            ln = lines[k]
            if not ln:
                k += 1
                continue
            if _is_label(ln):
                # Wenn wir mitten in Werten wieder ein Label finden, brechen wir ab
                break
            values.append(ln)
            k += 1
        for idx, field in enumerate(label_block):
            if idx >= len(values):
                break
            result.setdefault(field, values[idx])
        i = k if values else j
    return result



def _extract_invoice_number(text: str, filename: str) -> Optional[str]:
    # Zuerst Dateiname: "Rechnung_260257_..." -> 260257
    m = re.search(r"[Rr]echnung[_ ]?(?:[Nn]r\.?[_ ]?)?(\d{4,15})", filename)
    if m:
        return m.group(1)
    # Multiline-Spalten-Layout (Label ueber Werten)
    col = _extract_labelled_column(text)
    if col.get("invoice_number"):
        cand = col["invoice_number"].strip()
        # Sanity: darf kein reines Datum sein
        if not re.fullmatch(r"\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}", cand):
            if re.fullmatch(r"[A-Z0-9][A-Z0-9\-/]{2,24}", cand, re.IGNORECASE):
                return cand
    # Standard-Inline-Patterns (Label + Wert auf gleicher Zeile)
    patterns = [
        r"Rechnungs?[- ]?[Nn]r\.?\s*:?\s*([A-Z0-9][A-Z0-9\-/]{2,24})",
        r"Rechnung\s+[Nn]r\.?\s*:?\s*([A-Z0-9][A-Z0-9\-/]{2,24})",
        r"Invoice\s+No\.?\s*:?\s*([A-Z0-9][A-Z0-9\-/]{2,24})",
        r"Beleg[- ]?[Nn]r\.?\s*:?\s*([A-Z0-9][A-Z0-9\-/]{2,24})",
    ]
    cand = _find_first(patterns, text, group=1)
    # Sanity: darf nicht das Label eines anderen Feldes matchen
    if cand and cand.lower() in ("kundennr", "kundennummer", "beleg", "invoice", "datum", "rechnungsnr", "rechnungsnummer"):
        return None
    return cand


def _extract_date(text: str) -> Optional[str]:
    # Multiline-Spalten-Layout zuerst
    col = _extract_labelled_column(text)
    raw = col.get("date")
    if not raw:
        patterns = [
            # Rechnungsdatum / Belegdatum (hoechste Prioritaet - eindeutig)
            r"Rechnungsdatum\s*:?\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})",
            r"Belegdatum\s*:?\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})",
            r"Belegdatum\s*[:\n\r]+\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})",
            r"Invoice\s+date\s*:?\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})",
            # "vom DD.MM.YYYY" - typisch in Rechnungskoepfen
            r"vom\s+(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})",
            # "Datum" allein - mit negative lookbehind, damit
            # Leistungsdatum/Lieferdatum/Zahldatum/Faelligkeitsdatum NICHT greifen
            r"(?<!leistungs)(?<!liefer)(?<!zahl)(?<!f\u00e4llig)(?<!faellig)"
            r"Datum\s*:?\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})",
            r"(\d{4}-\d{2}-\d{2})",
        ]
        raw = _find_first(patterns, text, group=1)
    if not raw:
        return None
    return _normalize_date(raw)


def _normalize_date(raw: str) -> Optional[str]:
    """Wandelt ein rohes Datum in ISO YYYY-MM-DD um."""
    if not raw:
        return None
    raw = raw.strip()
    # ISO YYYY-MM-DD
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            return raw
    for fmt in (
        "%d.%m.%Y", "%d.%m.%y",
        "%d-%m-%Y", "%d-%m-%y",
        "%d/%m/%Y", "%d/%m/%y",
    ):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def _extract_due_date(text: str, invoice_date_iso: Optional[str]) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """Bestimmt Fälligkeit + Zahlungsziel aus dem Text.
    Returns (due_date_iso, payment_term_days, payment_terms_text).

    Reihenfolge:
    1. Explizites Datum "faellig am DD.MM.YYYY" / Vervaldatum / Due date
    2. Aus Label-Layout ('Faelligkeit' / 'Zahlungsziel')
    3. "Zahlbar innerhalb X Tagen" / "Betaling binnen X dagen" / "net X days"
       ergibt X Tage nach dem Rechnungsdatum
    """
    # 1) Explizites Datum
    m = re.search(
        r"(?:f(?:ae|\u00e4)llig(?:keit)?(?:sdatum)?(?:\s+am)?|"
        r"zahlbar\s+(?:bis|am)|"
        # "Zahlbar sofort netto, spaetestens bis zum 5.8.2026"
        r"zahlbar[^\n\r]{0,60}?(?:sp(?:ae|\u00e4)testens\s+)?bis(?:\s+zum)?|"
        # Standalone "spaetestens bis zum DD.MM.YYYY"
        r"sp(?:ae|\u00e4)testens\s+bis(?:\s+zum)?|"
        r"due\s+date|vervaldatum)"
        r"\s*:?\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|\d{4}-\d{2}-\d{2})",
        text, re.IGNORECASE)
    if m:
        d = _normalize_date(m.group(1))
        if d:
            return d, None, m.group(0).strip()

    # 2) Aus Label-Layout
    col = _extract_labelled_column(text)
    raw_due = col.get("due_date")
    if raw_due:
        # Kann ein Datum sein ("15.07.2026") oder eine Zahl-Angabe ("30 Tage")
        if re.match(r"\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}", raw_due) or re.match(r"\d{4}-\d{2}-\d{2}", raw_due):
            d = _normalize_date(raw_due)
            if d:
                return d, None, "Fälligkeit: " + raw_due
        mt = re.search(r"(\d{1,3})\s*(?:tag|tage|dag|dagen|day|days)", raw_due, re.IGNORECASE)
        if mt:
            days = int(mt.group(1))
            due = _add_days(invoice_date_iso, days)
            return due, days, raw_due

    # 3) Freitext-Zahlungsziel
    tm = re.search(
        r"(?:zahlbar|betaling|betaalbaar|payable|zahlung(?:\s+innerhalb)?|"
        r"payment\s+within|zahlungsziel)"
        r"[^\n\r]{0,60}?"
        r"(?:binnen|innerhalb|within)?\s*(\d{1,3})\s*(?:tage|tagen|tag|dagen|dag|days|day)\b",
        text, re.IGNORECASE)
    if tm:
        days = int(tm.group(1))
        due = _add_days(invoice_date_iso, days)
        # Kontext bis 80 Zeichen fuer 'terms'-Anzeige
        start = max(0, tm.start() - 5)
        end = min(len(text), tm.end() + 15)
        return due, days, text[start:end].strip()

    # 4) Kurzformen: "netto 30 Tage" / "netto 30 dagen" / "30 Tage ohne Abzug"
    tm2 = re.search(
        r"(?:netto\s+(\d{1,3})\s*(?:tage|tagen|tag|dagen|dag|days|day)"
        r"|(\d{1,3})\s*(?:tage|tagen|tag)\s+ohne\s+abzug"
        r"|(\d{1,3})\s*(?:tage|tagen|tag)\s+netto)",
        text, re.IGNORECASE)
    if tm2:
        days = int(next(g for g in tm2.groups() if g))
        due = _add_days(invoice_date_iso, days)
        return due, days, tm2.group(0)

    return None, None, None


def _add_days(iso_date: Optional[str], days: int) -> Optional[str]:
    if not iso_date or days is None:
        return None
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        from datetime import timedelta as _td
        return (dt + _td(days=days)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _extract_amount(text: str) -> Optional[float]:
    # Label-Regexes: DOTALL zwischen Label und Zahl erlauben (bis zu 40 Zeichen
    # Zwischenraum, damit Newlines und Whitespace matchen). Nicht-gierig via
    # ``[^0-9]{0,40}?`` verhindert Ausflug in benachbarte Betraege.
    priority_labels = [
        r"Gesamtbetrag\s+brutto[^0-9]{0,40}?([\d.]+,\d{2})",
        r"Rechnungsbetrag[^0-9]{0,40}?([\d.]+,\d{2})",
        r"Zu\s+zahlen(?:der\s+Betrag)?[^0-9]{0,40}?([\d.]+,\d{2})",
        r"Endbetrag[^0-9]{0,40}?([\d.]+,\d{2})",
        r"Gesamtsumme[^0-9]{0,40}?([\d.]+,\d{2})",
        r"Summe\s+brutto[^0-9]{0,40}?([\d.]+,\d{2})",
        r"Gesamtbetrag[^0-9]{0,40}?([\d.]+,\d{2})",     # ohne "brutto"
        r"Brutto(?:betrag|summe)?[^0-9]{0,40}?([\d.]+,\d{2})",
        r"Total[^0-9]{0,40}?([\d.]+,\d{2})",
    ]
    raw = None
    for pat in priority_labels:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            raw = m.group(1)
            break
    if not raw:
        # Fallback 1: hoechster EUR-Betrag mit Waehrungssuffix
        matches = re.findall(r"([\d.]{1,10},\d{2})\s*(?:EUR|€)", text)
        if matches:
            try:
                return max(float(m.replace(".", "").replace(",", ".")) for m in matches)
            except ValueError:
                pass
        # Fallback 2: rein numerisch neben einem Betrags-Keyword (Spalten-Layout
        # ohne Waehrungssymbol, z.B. Hilsdorf-Rechnung).
        keyword_re = re.compile(
            r"(gesamt|brutto|umsatzsteuer|summe|zwischensumme|zu\s*zahlen|endbetrag)"
            r".{0,120}?([\d]{1,3}(?:\.[\d]{3})*,\d{2})",
            re.IGNORECASE | re.DOTALL,
        )
        candidates = [m.group(2) for m in keyword_re.finditer(text)]
        if candidates:
            try:
                return max(float(m.replace(".", "").replace(",", ".")) for m in candidates)
            except ValueError:
                pass
        return None
    try:
        return float(raw.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _extract_iban(text: str) -> Optional[str]:
    """IBAN-Extraktion mit Land-spezifischen Laengen (SEPA):
    DE=22, NL=18, AT=20, BE=16, CH=21, LU=20, FR=27, IT=27, ES=24, GB=22, DK=18,
    SE=24, FI=18, PL=28, IE=22, PT=25, NO=15, CZ=24, HU=28, SK=24.
    Bevorzugt Kandidaten die direkt hinter dem Label 'IBAN' stehen (99% aller
    echten Rechnungen). BTW/USt-IdNr. (z.B. NL820319739B01) werden per
    Laengen-Check automatisch verworfen.
    """
    IBAN_LEN = {
        "DE": 22, "NL": 18, "AT": 20, "BE": 16, "CH": 21, "LU": 20,
        "FR": 27, "IT": 27, "ES": 24, "GB": 22, "DK": 18, "SE": 24,
        "FI": 18, "PL": 28, "IE": 22, "PT": 25, "NO": 15, "CZ": 24,
        "HU": 28, "SK": 24, "LI": 21, "MT": 31, "SI": 19, "EE": 20,
        "LT": 20, "LV": 21, "GR": 27, "RO": 24, "BG": 22, "HR": 21,
    }

    def _clean_and_validate(raw: str) -> Optional[str]:
        clean = re.sub(r"\s+", "", raw).upper()
        if len(clean) < 4:
            return None
        cc = clean[:2]
        need = IBAN_LEN.get(cc)
        if not need:
            return None
        if len(clean) < need:
            return None
        # Auf exakte Laenge trimmen (falls Suffix wie 'BIC' hinten dran klebte)
        cand = clean[:need]
        # Aufbau: 2 Buchstaben + 2 Ziffern + Rest alphanumerisch
        if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", cand):
            return None
        return cand

    # 1. Bevorzugt: Label 'IBAN' im Text
    for m in re.finditer(r"IBAN[\s:.-]*([A-Z]{2}[\s\d]{2}[\sA-Z0-9]{10,34})", text, re.IGNORECASE):
        found = _clean_and_validate(m.group(1))
        if found:
            return found

    # 2. Fallback: generischer IBAN-Match (max 34 Zeichen incl. Leerzeichen)
    for m in re.finditer(r"\b([A-Z]{2}\s?\d{2}(?:\s?[A-Z0-9]){10,30})\b", text):
        found = _clean_and_validate(m.group(1))
        if found:
            return found
    return None


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


def _extract_sender_from_header(text: str, exclude_self: bool = True) -> Optional[str]:
    """Sender-Erkennung aus dem Briefkopf.

    Strategie (in Prioritaets-Reihenfolge):
    1. **Bevorzugt**: Zeile mit Firmen-Rechtsformkuerzel (GmbH, AG, KG, UG, e.K.,
       Ltd, Inc, LLC, e.V., SE, KGaA). Das ist in fast allen echten Rechnungen der
       Absender-Firmenname.
    2. **Alternative**: Zeile mit Personennamen + "Veranstaltungsdienstleistungen"
       oder "- <Berufsbezeichnung>" (Einzelunternehmer/Freiberufler).
    3. **Fallback**: Erste nicht-leere Header-Zeile die kein generisches Label ist.

    Wenn exclude_self=True (Standard bei Eingangsrechnungen): eigene Firmennamen
    (Eventenergie, Power Factor Engineering) werden aus der Kandidatenliste
    ausgeschlossen, da sie in Empfaengerzeilen stehen.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Zeilen die niemals ein Firmen-Absender sind
    skip_re = re.compile(
        r"^(rechnung|invoice|bestellung|angebot|lieferschein|"
        r"rechnungsnr|rechnungsnummer|kundennr|kundennummer|"
        r"datum|leistungszeitraum|leistungsdatum|belegdatum|"
        r"sehr\s+geehrt|hallo|liebe[rn]?\s|guten\s+tag|"
        # Grussformel-Endungen (deutsch/englisch) - matchen sowohl ß als auch ss
        r"mit\s+freundlichen?\s+gr(?:ue|\u00fc)(?:ssen|\u00dfen)|"
        r"mit\s+freundlichem\s+gru(?:ss|\u00df)|"
        r"(?:freundliche|beste|herzliche|viele|liebe)\s+gr(?:ue|\u00fc)(?:sse|\u00dfe)\b|"
        r"gr(?:ue|\u00fc)(?:sse|\u00dfe)\s+aus\b|"
        r"ihr\s+team|ihre\s+(?:firma|kanzlei|praxis)|"
        r"kind\s+regards|best\s+regards|yours\s+(?:sincerely|truly|faithfully)|"
        r"seite\s|page\s|pos\.|position|"
        r"bezeichnung|menge|einheit|artikel|art\.?[\-\s]?nr|"
        r"preis|einzelpreis|st(?:ck|k|ueck|\u00fcck)|stueck|"
        r"summe|gesamt|zwischensumme|betrag|umsatzsteuer|mwst|"
        # Reine Kontext-Labels alleine in einer Zeile (nicht "Firma Muster GmbH")
        r"firma\s*:?\s*$|absender\s*:?\s*$|empf(?:aenger|\u00e4nger)\s*:?\s*$|"
        r"an\s*:?\s*$|company\s*:?\s*$|from\s*:?\s*$|"
        r"bill[-\s]?to\s*:?\s*$|invoice[-\s]?to\s*:?\s*$|ship[-\s]?to\s*:?\s*$|"
        r"kfz[\-\s]|monteur)",
        re.IGNORECASE,
    )
    # Rechnungsnummer/Codes: z.B. RE26/020, R26-K-0033, 263472, IN123456
    invoice_code_re = re.compile(r"^[A-Z]{1,4}[\d\-\/]{2,20}$", re.IGNORECASE)
    # Rechtsform-Suffixe die einen Firmennamen markieren
    company_re = re.compile(
        r"\b(GmbH|AG|KG|UG|e\.?\s*K\.?|OHG|GbR|SE|Ltd\.?|Inc\.?|LLC|Corp\.?|KGaA|e\.?\s*V\.?|Co\.?\s*KG|B\.?\s*V\.?|N\.?\s*V\.?|S\.?\s*A\.?|S\.?\s*r\.?\s*l\.?|SARL|S\.?\s*p\.?\s*A\.?)\b",
        re.IGNORECASE,
    )
    # Berufsbezeichnungen (Einzelunternehmer / Freiberufler) - kein \b weil
    # deutsche Komposita wie "Veranstaltungsdienstleistungen" sonst nicht greifen
    profession_re = re.compile(
        r"(dienstleist|handwerk|beratung|consulting|fotograf|design|architekt|"
        r"ingenieur|steuerberat|rechtsanwal|freelanc|spedition|logistik|"
        r"hausmeister|elektroinstallation|it[-\s]?services?)",
        re.IGNORECASE,
    )
    # Eigene Firmen die im Kandidaten-Set NICHT als Sender vorkommen sollen
    self_markers = ("eventenergie", "power factor engineering", "powerfactor engineering")

    def _is_self(ln: str) -> bool:
        low = ln.lower()
        return any(m in low for m in self_markers)

    # 1. Zeile mit Rechtsform-Suffix im TOP-Bereich (erste 50 Zeilen, filtere self)
    for ln in lines[:50]:
        if not (3 < len(ln) <= 120):
            continue
        if skip_re.match(ln):
            continue
        if exclude_self and _is_self(ln):
            continue
        if company_re.search(ln):
            m = company_re.search(ln)
            cut = ln[:m.end()].strip(" ,;")
            cut = re.sub(r"^(an\s*:?\s*|firma\s*:?\s*|absender\s*:?\s*|nach\s*:?\s*|von\s*:?\s*)", "", cut, flags=re.IGNORECASE).strip()
            # Falls "von: <XY> <PLZ> <Ort>" - Ort abschneiden
            cut = re.sub(r"\s+\d{5}\s+.*$", "", cut).strip()
            if len(cut) >= 3 and not _is_self(cut if exclude_self else ""):
                return cut

    # 2. Zeile mit Berufsbezeichnung (Einzelunternehmer)
    for i, ln in enumerate(lines[:15]):
        if not (3 < len(ln) <= 120):
            continue
        if skip_re.match(ln):
            continue
        if exclude_self and _is_self(ln):
            continue
        if profession_re.search(ln):
            # Bei "Alexander Hilsdorf - Veranstaltungsdienstleistungen"
            # oder Vorzeile "Alexander Hilsdorf" + naechste Zeile "Veranstaltungsdienstleistungen"
            # Nimm die aktuelle Zeile als vollstaendigen Namen
            if " - " in ln or " – " in ln:
                return ln.split(" - " if " - " in ln else " – ")[0].strip()
            # Sonst: Vorzeile hat den Personennamen
            if i > 0 and 3 < len(lines[i-1]) <= 60 and not skip_re.match(lines[i-1]):
                return lines[i-1]
            return ln

    # 3. Fallback: erste plausible Zeile
    # Woehrungssymbole/Preis-Kandidaten ausschliessen (z.B. "Preis €", "Total $")
    currency_only_re = re.compile(r"[\u20ac$\u00a3\u00a5]|EUR\b|USD\b|GBP\b|CHF\b", re.IGNORECASE)
    # PLZ am Zeilenanfang = Adress-Fortsetzungszeile, kein Firmenname
    postcode_start_re = re.compile(r"^\d{4,5}\s+[A-Za-z\u00c0-\u017e]")
    # VIN-artige / Kennzeichen-artige technische IDs (>=6 Zeichen Mixed alnum)
    technical_id_re = re.compile(r"\b[A-Z]{2,}\d{2,}[A-Z0-9]{4,}\b|\b[A-Z0-9]{10,}\b")
    for ln in lines[:8]:
        if not (3 < len(ln) <= 120):
            continue
        if skip_re.match(ln):
            continue
        if invoice_code_re.match(ln):
            continue
        # Reine Zahlen/Codes ausschließen
        if re.match(r"^[\d\s\-\.\/]+$", ln):
            continue
        # PLZ + Ort am Anfang = Adressfortsetzung
        if postcode_start_re.match(ln):
            continue
        # Zeilen die nur aus Waehrungssymbol/-code + evtl. 1 Wort bestehen
        # ("Preis \u20ac", "Total $", "Netto EUR") sind Tabellenspalten, keine Firmennamen
        if len(ln) < 40 and currency_only_re.search(ln) and len(re.sub(r"[^A-Za-z]", "", ln)) < 20:
            continue
        # Fahrgestellnr., VIN, Bestellnummer u.ae. technische IDs
        if technical_id_re.search(ln):
            continue
        # Muss mind. 2 Woerter mit Buchstaben haben (verhindert "Kfz-Kennzeichen")
        word_count = len([w for w in re.split(r"\s+", ln) if re.search(r"[A-Za-z\u00c0-\u017e]{2,}", w)])
        if word_count < 2:
            continue
        if exclude_self and _is_self(ln):
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
    # ─── ZUGFeRD / Factur-X / XRechnung XML SHORTCUT ──────────────────
    # Wenn das PDF eine strukturierte E-Rechnung eingebettet hat, sind DIESE
    # Daten authoritativ. Wir umgehen dann komplett das Layout-Parsing.
    try:
        from services.zugferd_parser import try_zugferd_parse_bytes
        zug = try_zugferd_parse_bytes(pdf_bytes)
    except Exception:
        zug = {}

    text = _extract_text(pdf_bytes)

    # Wenn nichts extrahierbar (z.B. Scan ohne OCR), fallback auf filename+leer
    if not text and not zug:
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

    # ─── ZUGFeRD-Daten uebernehmen (immer Vorrang vor Text-Heuristik) ───
    zug_used = False
    if zug:
        zug_used = True
        # Absender / Empfaenger direkt aus XML (100% eindeutig)
        zug_sender = (zug.get("sender") or "").strip()
        zug_recipient = (zug.get("recipient") or "").strip()
        if zug_sender:
            sender = zug_sender
        if zug_recipient:
            recipient = zug_recipient
        # Richtung anhand XML-Sender vs. eigene Firmenmarker
        _self_markers = ("eventenergie", "power factor engineering", "powerfactor engineering")
        _sender_low = zug_sender.lower()
        _recipient_low = zug_recipient.lower()
        if _sender_low and any(m in _sender_low for m in _self_markers):
            direction = "rechnungsausgang_eventenergie_deutschland"
        elif _recipient_low and any(m in _recipient_low for m in _self_markers):
            direction = "rechnungseingang_eventenergie_deutschland"
        elif _sender_low:
            # Ein fremder Sender im XML → wir sind Empfaenger
            direction = "rechnungseingang_eventenergie_deutschland"
        # Metadaten uebernehmen (XML gewinnt gegen Text-Heuristik)
        if zug.get("invoice_number"):
            inv_num = zug["invoice_number"]
        if zug.get("date"):
            date = zug["date"]
        if zug.get("amount") is not None:
            try:
                amount = float(zug["amount"])
            except (TypeError, ValueError):
                pass
        if zug.get("iban"):
            iban = str(zug["iban"]).replace(" ", "")

    # Dokumenttyp aus Dateiname/Text-Keywords ableiten
    tlow = text.lower()
    fn_lower = filename.lower()
    if zug and zug.get("document_type"):
        doc_type = zug["document_type"]
    elif "bestellung" in fn_lower or "bestellung" in tlow[:500]:
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
    elif ("rechnung" in fn_lower or "rechnung" in tlow[:2000] or
          "invoice" in tlow[:2000] or "factuur" in tlow[:2000] or
          "factuur" in fn_lower):
        doc_type = "rechnung"
        # Auslands-Rechnungen ohne Firmenmarker im Text: wenn Empfaenger unser Marker
        if direction == "unknown" and any(
                m in tlow for m in ("eventenergie", "power factor engineering")):
            direction = "rechnungseingang_eventenergie_deutschland"
    elif zug_used:
        # ZUGFeRD-XML vorhanden → mit Sicherheit eine Rechnung
        doc_type = "rechnung"
    else:
        doc_type = "unknown"

    if direction == "unknown":
        direction = "unbekannt"

    # Fälligkeit / Zahlungsziel aus Text ermitteln (nach date-Extraktion, damit
    # 'X Tage nach Rechnungsdatum' korrekt aufaddiert werden kann).
    due_date, payment_term_days, payment_terms_text = _extract_due_date(text, date)

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
    if zug_used:
        keywords.append("e-rechnung")
        if zug.get("sender_vat"):
            keywords.append(zug["sender_vat"])
    keywords = [k for k in keywords if k]

    if zug_used and zug.get("due_date"):
        due_date = zug["due_date"]

    return {
        "document_type": doc_type,
        "suggested_folder": direction,
        "sender": sender or "",
        "recipient": recipient or "",
        "invoice_number": inv_num,
        "date": date,
        "due_date": due_date,
        "payment_term_days": payment_term_days,
        "payment_terms": payment_terms_text,
        "amount": amount,
        "currency": (zug.get("currency") if zug_used else None) or "EUR",
        "subject": subject[:200],
        "full_text": text[:20000],  # cap
        "keywords": keywords[:15],
        "iban": iban,
        "_authoritative_source": "zugferd_xml" if zug_used else "fallback_heuristic",
        "_fallback_reason": (
            "ZUGFeRD/Factur-X XML aus PDF extrahiert - strukturierte E-Rechnung"
            if zug_used else
            "Ollama nicht erreichbar - heuristische Text-Analyse verwendet"
        ),
        "_fallback_at": datetime.now(timezone.utc).isoformat(),
        "_zugferd_data": zug if zug_used else None,
    }
