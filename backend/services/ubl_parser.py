"""UBL / XRechnung XML Parser.

XRechnung ist der deutsche E-Rechnungsstandard fuer Rechnungen an oeffentliche
Auftraggeber (§4a EGovG). Sie basiert auf CEN-Norm EN 16931 und existiert in
zwei technischen Auspraegungen:

  1. UBL (OASIS Universal Business Language) - dieser Parser
  2. CII (UN/CEFACT Cross Industry Invoice) - siehe zugferd_parser.py

Diese Datei erkennt und parst eigenstaendige UBL-XML-Dateien (nicht in PDF
eingebettet) und liefert die selben Felder wie zugferd_parser.parse_zugferd_xml,
sodass beide Formate im Downstream-Code identisch behandelt werden.
"""
import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional

logger = logging.getLogger(__name__)

# UBL 2.1 Namespaces
UBL_NS = {
    "ubl": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}

# CII / ZUGFeRD Namespace (fuer die Format-Erkennung)
CII_ROOT_NS = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"


def _t(el) -> str:
    """Get element text safely."""
    if el is None:
        return ""
    return (el.text or "").strip()


def _find(root, path: str):
    return root.find(path, UBL_NS)


def _findall(root, path: str):
    return root.findall(path, UBL_NS)


def is_ubl_invoice_xml(xml_content: str) -> bool:
    """Return True if xml_content is a UBL Invoice."""
    try:
        head = xml_content[:1500].lower()
        return (
            "urn:oasis:names:specification:ubl:schema:xsd:invoice-2" in head
            and "<ubl:invoice" in head
        )
    except Exception:
        return False


def is_cii_invoice_xml(xml_content: str) -> bool:
    """Return True if xml_content is a CII / ZUGFeRD XML (as standalone file)."""
    try:
        head = xml_content[:1500].lower()
        return CII_ROOT_NS.lower() in head or "crossindustryinvoice" in head
    except Exception:
        return False


def parse_ubl_invoice(xml_content: str) -> dict:
    """Parst UBL 2.1 Invoice XML und liefert dieselben Felder wie
    services.zugferd_parser.parse_zugferd_xml zurueck.

    Felder (nur wenn im XML vorhanden):
        sender, sender_address, sender_vat
        recipient, recipient_id
        invoice_number, date, due_date
        amount (brutto), tax_amount, currency
        iban, bic, reference
        document_type ("rechnung" oder "gutschrift")
        subject, full_text (grober Text-Dump aller UBL-Zellen)
    """
    result: dict = {}
    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        logger.warning(f"[ubl] XML parse failed: {e}")
        return result

    # ── Rechnungsnr, Datum ──────────────────────────────────────────
    inv_id = _t(_find(root, "cbc:ID"))
    if inv_id:
        result["invoice_number"] = inv_id

    date_str = _t(_find(root, "cbc:IssueDate"))
    if date_str:
        result["date"] = date_str  # UBL nutzt bereits YYYY-MM-DD

    due_str = _t(_find(root, "cbc:DueDate"))
    if due_str:
        result["due_date"] = due_str

    # UBL InvoiceTypeCode: 380 = Standard, 381 = Credit, 384 = Correction
    tc = _t(_find(root, "cbc:InvoiceTypeCode"))
    if tc == "381":
        result["document_type"] = "gutschrift"
    else:
        result["document_type"] = "rechnung"

    # Waehrung
    cur = _t(_find(root, "cbc:DocumentCurrencyCode"))
    if cur:
        result["currency"] = cur

    # Referenz / BuyerReference
    buyer_ref = _t(_find(root, "cbc:BuyerReference"))
    if buyer_ref:
        result["reference"] = buyer_ref

    # ── Absender (AccountingSupplierParty) ──────────────────────────
    sup = _find(root, "cac:AccountingSupplierParty/cac:Party")
    if sup is not None:
        # Name
        name = _t(_find(sup, "cac:PartyName/cbc:Name")) or _t(_find(sup, "cac:PartyLegalEntity/cbc:RegistrationName"))
        if name:
            result["sender"] = name
        # Adresse
        addr = _find(sup, "cac:PostalAddress")
        if addr is not None:
            street = _t(_find(addr, "cbc:StreetName"))
            postal = _t(_find(addr, "cbc:PostalZone"))
            city = _t(_find(addr, "cbc:CityName"))
            country = _t(_find(addr, "cac:Country/cbc:IdentificationCode"))
            parts = [p for p in (street, f"{postal} {city}".strip(), country) if p.strip()]
            if parts:
                result["sender_address"] = ", ".join(parts)
        # VAT-ID
        for ts in _findall(sup, "cac:PartyTaxScheme"):
            vat = _t(_find(ts, "cbc:CompanyID"))
            scheme = _t(_find(ts, "cac:TaxScheme/cbc:ID"))
            if vat and (not scheme or scheme.upper() == "VAT"):
                result["sender_vat"] = vat
                break

    # ── Empfaenger (AccountingCustomerParty) ────────────────────────
    cus = _find(root, "cac:AccountingCustomerParty/cac:Party")
    if cus is not None:
        name = _t(_find(cus, "cac:PartyName/cbc:Name")) or _t(_find(cus, "cac:PartyLegalEntity/cbc:RegistrationName"))
        if name:
            result["recipient"] = name
        rid = _t(_find(cus, "cac:PartyIdentification/cbc:ID"))
        if rid:
            result["recipient_id"] = rid

    # ── Zahlungsinfos (IBAN, BIC) ───────────────────────────────────
    pm = _find(root, "cac:PaymentMeans")
    if pm is not None:
        acct = _find(pm, "cac:PayeeFinancialAccount")
        if acct is not None:
            iban = _t(_find(acct, "cbc:ID"))
            if iban:
                iban_clean = re.sub(r"\s+", "", iban)
                result["iban"] = " ".join(iban_clean[i:i+4] for i in range(0, len(iban_clean), 4))
            bic = _t(_find(acct, "cac:FinancialInstitutionBranch/cbc:ID"))
            if bic:
                result["bic"] = bic

    # ── Betraege ─────────────────────────────────────────────────────
    lm = _find(root, "cac:LegalMonetaryTotal")
    if lm is not None:
        grand = _t(_find(lm, "cbc:PayableAmount")) or _t(_find(lm, "cbc:TaxInclusiveAmount"))
        if grand:
            try:
                result["amount"] = float(grand)
            except Exception:
                pass
        net = _t(_find(lm, "cbc:LineExtensionAmount")) or _t(_find(lm, "cbc:TaxExclusiveAmount"))
        if net:
            try:
                result["net_amount"] = float(net)
            except Exception:
                pass

    # Steuerbetrag
    tax_total = _find(root, "cac:TaxTotal")
    if tax_total is not None:
        tax_amount = _t(_find(tax_total, "cbc:TaxAmount"))
        if tax_amount:
            try:
                result["tax_amount"] = float(tax_amount)
            except Exception:
                pass

    # ── Betreff aus erster Position ─────────────────────────────────
    lines = []
    for line in _findall(root, "cac:InvoiceLine"):
        item_name = _t(_find(line, "cac:Item/cbc:Name"))
        if item_name:
            lines.append(item_name)
    if lines:
        result["subject"] = " | ".join(lines[:3])[:200]

    # ── Grober Full-Text-Dump fuer Suche/Anzeige ────────────────────
    text_bits = []
    for elem in root.iter():
        txt = (elem.text or "").strip()
        if txt and len(txt) < 500 and not txt.startswith("<"):
            text_bits.append(txt)
    if text_bits:
        result["full_text"] = "\n".join(text_bits)

    return result
