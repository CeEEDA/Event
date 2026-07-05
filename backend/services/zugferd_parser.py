"""
ZUGFeRD / Factur-X XML Parser.

ZUGFeRD (Zentraler User Guide des Forums elektronische Rechnung Deutschland)
ist ein deutsches E-Rechnungsformat. Das PDF/A-3 hat eine strukturierte XML
(factur-x.xml, zugferd-invoice.xml oder xrechnung.xml) eingebettet, die
authoritative Rechnungsdaten enthaelt - Sender, Empfaenger, IBAN, Datum,
Betraege - unabhaengig davon, wie der visuelle PDF-Text aussieht.

Wenn ein Upload ZUGFeRD-XML enthaelt, sind DIESE Daten die Wahrheit -
NICHT die LLM-Extraktion aus dem gerenderten PDF-Text.

Referenz: https://www.ferd-net.de/standards/was-ist-zugferd/index.html
"""
import logging
import re
from typing import Optional

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# UN/CEFACT ZUGFeRD Namespaces (fuer XML-Parsing via lokale Namespace-Map)
NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}

_ZUGFERD_XML_FILENAMES = (
    "factur-x.xml",
    "zugferd-invoice.xml",
    "zugferd-invoice.xml",
    "xrechnung.xml",
)


def is_zugferd_pdf(pdf_path: str) -> bool:
    """Schnell-Check: Enthaelt das PDF eine ZUGFeRD-XML?"""
    try:
        doc = fitz.open(pdf_path)
        try:
            for name in doc.embfile_names():
                info = doc.embfile_info(name) or {}
                fname = (info.get("ufilename") or info.get("filename") or name or "").lower()
                if any(z in fname for z in _ZUGFERD_XML_FILENAMES):
                    return True
        finally:
            doc.close()
    except Exception as e:
        logger.debug(f"[zugferd] is_zugferd_pdf failed: {e}")
    return False


def extract_zugferd_xml(pdf_path: str) -> Optional[str]:
    """Extrahiert die factur-x.xml aus einer ZUGFeRD-PDF. Gibt XML-String oder None."""
    try:
        doc = fitz.open(pdf_path)
        try:
            for name in doc.embfile_names():
                info = doc.embfile_info(name) or {}
                fname = (info.get("ufilename") or info.get("filename") or name or "").lower()
                if any(z in fname for z in _ZUGFERD_XML_FILENAMES):
                    data = doc.embfile_get(name)
                    if data:
                        return data.decode("utf-8", errors="ignore")
        finally:
            doc.close()
    except Exception as e:
        logger.warning(f"[zugferd] extract_zugferd_xml failed: {e}")
    return None


def _text(elem) -> str:
    """Nimmt element.text sauber - '' bei None, gestripped."""
    if elem is None:
        return ""
    return (elem.text or "").strip()


def _find(root, path: str):
    """Findet ELEMENT via qualified path. Erlaubt Muster wie 'ram:X/ram:Y'."""
    return root.find(path, NS)


def _find_all(root, path: str):
    return root.findall(path, NS)


def parse_zugferd_xml(xml_content: str) -> dict:
    """Parst ZUGFeRD-XML und liefert die Kernfelder als flaches dict.

    Rueckgabe (nur Felder die tatsaechlich vorhanden waren):
        sender:            String - SellerTradeParty/Name
        sender_address:    String - "Strasse, PLZ Ort" der SellerTradeParty
        sender_vat:        String - Umsatzsteuer-ID des Absenders
        recipient:         String - BuyerTradeParty/Name
        recipient_id:      String - Kundennummer beim Absender
        invoice_number:    String - ExchangedDocument/ID
        date:              String YYYY-MM-DD
        due_date:          String YYYY-MM-DD (falls DueDateDateTime da)
        amount:            float  - GrandTotalAmount (brutto)
        tax_amount:        float  - TaxTotalAmount (falls vorhanden)
        currency:          String - meist EUR
        iban:              String - PayeePartyCreditorFinancialAccount/IBANID
        bic:               String - PayeeSpecifiedCreditorFinancialInstitution/BICID
        reference:         String - PaymentReference oder BuyerReference
        document_type:     'rechnung' (bei TypeCode 380/381) oder 'gutschrift' (Type 381)
        subject:           Kurzsummary aus Positionen (max 200 chars)
        raw_positions:     Liste der Positionen (List[str])
    """
    import xml.etree.ElementTree as ET
    result = {}
    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        logger.warning(f"[zugferd] XML parse failed: {e}")
        return result

    # Rechnungsnr
    doc_id = _find(root, "rsm:ExchangedDocument/ram:ID")
    if _text(doc_id):
        result["invoice_number"] = _text(doc_id)

    # Type: 380 = Standard-Rechnung, 381 = Gutschrift, 384 = Korrektur
    type_code = _text(_find(root, "rsm:ExchangedDocument/ram:TypeCode"))
    if type_code == "381":
        result["document_type"] = "gutschrift"
    else:
        result["document_type"] = "rechnung"

    # Ausstellungsdatum
    date_str = _text(_find(root, "rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString"))
    if date_str and len(date_str) == 8:
        result["date"] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    # Faelligkeit (falls vorhanden)
    due_str = _text(_find(root,
        "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/"
        "ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime/udt:DateTimeString"))
    if due_str and len(due_str) == 8:
        result["due_date"] = f"{due_str[:4]}-{due_str[4:6]}-{due_str[6:8]}"

    # Verkaeufer / Sender
    seller_root = _find(root, "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty")
    if seller_root is not None:
        seller_name = _text(_find(seller_root, "ram:Name"))
        if seller_name:
            result["sender"] = seller_name
        # Adresse zusammenbauen
        street = _text(_find(seller_root, "ram:PostalTradeAddress/ram:LineOne"))
        postcode = _text(_find(seller_root, "ram:PostalTradeAddress/ram:PostcodeCode"))
        city = _text(_find(seller_root, "ram:PostalTradeAddress/ram:CityName"))
        addr_parts = [p for p in (street, f"{postcode} {city}".strip()) if p]
        if addr_parts:
            result["sender_address"] = ", ".join(addr_parts)
        # VAT
        for reg in _find_all(seller_root, "ram:SpecifiedTaxRegistration/ram:ID"):
            if _text(reg):
                result["sender_vat"] = _text(reg)
                break

    # Kaeufer / Empfaenger
    buyer_root = _find(root, "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:BuyerTradeParty")
    if buyer_root is not None:
        buyer_name = _text(_find(buyer_root, "ram:Name"))
        if buyer_name:
            result["recipient"] = buyer_name
        buyer_id = _text(_find(buyer_root, "ram:ID"))
        if buyer_id:
            result["recipient_id"] = buyer_id

    # Referenz / BuyerReference (oft die Kundennr beim Rechnungssteller)
    buyer_ref = _text(_find(root, "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:BuyerReference"))
    if buyer_ref:
        result.setdefault("reference", buyer_ref)

    # Payment (IBAN, BIC)
    payment_root = _find(root,
        "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementPaymentMeans")
    if payment_root is not None:
        iban = _text(_find(payment_root, "ram:PayeePartyCreditorFinancialAccount/ram:IBANID"))
        if iban:
            # Nach DIN formatieren: alle 4 Zeichen ein Leerzeichen
            iban_clean = re.sub(r"\s+", "", iban)
            result["iban"] = " ".join(iban_clean[i:i+4] for i in range(0, len(iban_clean), 4))
        bic = _text(_find(payment_root, "ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID"))
        if bic:
            result["bic"] = bic

    # Waehrung + Betrag (netto/mwst/brutto)
    sett_root = _find(root, "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement")
    if sett_root is not None:
        cur = _text(_find(sett_root, "ram:InvoiceCurrencyCode"))
        if cur:
            result["currency"] = cur
        sum_root = _find(sett_root, "ram:SpecifiedTradeSettlementHeaderMonetarySummation")
        if sum_root is not None:
            grand = _text(_find(sum_root, "ram:GrandTotalAmount"))
            if grand:
                try:
                    result["amount"] = float(grand)
                except ValueError:
                    pass
            tax = _text(_find(sum_root, "ram:TaxTotalAmount"))
            if tax:
                try:
                    result["tax_amount"] = float(tax)
                except ValueError:
                    pass

    # Positionen (fuer subject / Suchbarkeit)
    positions = []
    for line in _find_all(root, "rsm:SupplyChainTradeTransaction/ram:IncludedSupplyChainTradeLineItem"):
        prod_name = _text(_find(line, "ram:SpecifiedTradeProduct/ram:Name"))
        if prod_name:
            positions.append(prod_name)
    if positions:
        result["raw_positions"] = positions
        result.setdefault("subject", "ZUGFeRD-Rechnung: " + ", ".join(positions)[:200])

    return result


def merge_zugferd_into_ai_result(ai_result: dict, zugferd_data: dict) -> dict:
    """Merged ZUGFeRD-Daten in ein AI-Result-Dict.

    Regel: ZUGFeRD hat Vorrang bei Kernfeldern (sender, recipient, date, amount,
    iban, invoice_number). Wenn ZUGFeRD ein Feld nicht hat, bleibt das
    Ollama-Ergebnis bestehen.

    Zusaetzlich wird der full_text um die ZUGFeRD-Rohdaten angereichert -
    damit die Volltextsuche 'Normann' & Co. findet.
    """
    if not zugferd_data:
        return ai_result

    authoritative_fields = (
        "sender", "recipient", "date", "amount", "iban",
        "invoice_number", "currency", "due_date", "tax_amount",
        "document_type", "reference",
    )
    for field in authoritative_fields:
        if zugferd_data.get(field) is not None:
            ai_result[field] = zugferd_data[field]

    # Metadaten die's im AI-Result nicht gab: einfach ergaenzen
    for extra in ("sender_address", "sender_vat", "recipient_id", "bic", "subject"):
        if zugferd_data.get(extra) and not ai_result.get(extra):
            ai_result[extra] = zugferd_data[extra]

    # Full-Text um XML-Kern anreichern - damit Volltextsuche funktioniert
    zug_text_parts = [
        f"[ZUGFeRD] Absender: {zugferd_data.get('sender','')}",
        f"Absender-Adresse: {zugferd_data.get('sender_address','')}",
        f"Absender-USt-Id: {zugferd_data.get('sender_vat','')}",
        f"Empfaenger: {zugferd_data.get('recipient','')}",
        f"Kundennr: {zugferd_data.get('recipient_id','')}",
        f"Rechnungsnr: {zugferd_data.get('invoice_number','')}",
        f"Datum: {zugferd_data.get('date','')}",
        f"Betrag: {zugferd_data.get('amount','')} {zugferd_data.get('currency','')}",
        f"IBAN: {zugferd_data.get('iban','')}",
    ]
    if zugferd_data.get("raw_positions"):
        zug_text_parts.append("Positionen: " + " | ".join(zugferd_data["raw_positions"]))
    zug_text_block = "\n".join(zug_text_parts)

    existing = ai_result.get("full_text") or ""
    ai_result["full_text"] = zug_text_block + "\n\n" + existing

    # Keywords um Absendername + VAT + Rechnungsnr ergaenzen (Suche)
    kw = ai_result.get("keywords") or []
    if not isinstance(kw, list):
        kw = []
    for extra_kw in (zugferd_data.get("sender"), zugferd_data.get("sender_vat"),
                     zugferd_data.get("invoice_number"), zugferd_data.get("recipient_id")):
        if extra_kw and extra_kw not in kw:
            kw.append(extra_kw)
    ai_result["keywords"] = kw

    return ai_result


def try_zugferd_parse(pdf_path: str) -> dict:
    """Convenience: prueft ob PDF ZUGFeRD ist und parst die XML.

    Gibt dict mit Kernfeldern oder leer bei Non-ZUGFeRD / Parse-Fehler.
    """
    xml = extract_zugferd_xml(pdf_path)
    if not xml:
        return {}
    return parse_zugferd_xml(xml)
