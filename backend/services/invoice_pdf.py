"""Invoice PDF generation for Kirmes billing - ZUGFeRD e-invoice with company letterhead."""
import io
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_RIGHT
from pdfrw import PdfReader as PdfrwReader, PageMerge
from facturx import generate_from_binary

LETTERHEAD_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "briefpapier.pdf")

PURPLE = colors.Color(0.52, 0.18, 0.68)
DARK = colors.Color(0.2, 0.2, 0.2)
GRAY = colors.Color(0.4, 0.4, 0.4)

PAGE_W, PAGE_H = A4
MARGIN_LEFT = 25 * mm
MARGIN_RIGHT = 20 * mm


class LetterheadCanvas(canvas.Canvas):
    """Canvas that merges the letterhead PDF as background after content is drawn."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pages_data = []

    def showPage(self):
        self._pages_data.append(dict(self.__dict__))
        super().showPage()

    def save(self):
        for ps in self._pages_data:
            self.__dict__.update(ps)
            super().showPage()
        super().save()


def _merge_letterhead(content_pdf_bytes: bytes) -> bytes:
    """Merge letterhead background with content overlay."""
    letterhead = PdfrwReader(LETTERHEAD_PATH)
    content = PdfrwReader(fdata=content_pdf_bytes)
    bg_page = letterhead.pages[0]

    for i, page in enumerate(content.pages):
        merger = PageMerge(page)
        merger.add(bg_page, prepend=True)
        merger.render()

    writer = io.BytesIO()
    from pdfrw import PdfWriter
    w = PdfWriter()
    w.addpages(content.pages)
    w.write(writer)
    return writer.getvalue()


def generate_invoice_pdf(invoice: dict) -> bytes:
    """Generate a PDF invoice with letterhead background. Returns PDF bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN_LEFT, rightMargin=MARGIN_RIGHT,
        topMargin=55 * mm,
        bottomMargin=30 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("InvNormal", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=DARK))
    styles.add(ParagraphStyle("InvBold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=DARK))
    styles.add(ParagraphStyle("InvSmall", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5, leading=10, textColor=GRAY))
    styles.add(ParagraphStyle("InvTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=DARK))
    styles.add(ParagraphStyle("InvRight", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=DARK, alignment=TA_RIGHT))

    elements = []
    sch = invoice.get("schausteller", {})
    event = invoice.get("event", {})

    # Recipient address block
    elements.append(Paragraph(sch.get("firma", ""), styles["InvBold"]))
    if sch.get("name"):
        elements.append(Paragraph(sch["name"], styles["InvNormal"]))
    if sch.get("strasse"):
        elements.append(Paragraph(sch["strasse"], styles["InvNormal"]))
    if sch.get("plz") or sch.get("ort"):
        elements.append(Paragraph(f"{sch.get('plz', '')} {sch.get('ort', '')}", styles["InvNormal"]))
    elements.append(Spacer(1, 8 * mm))

    # Invoice metadata (right-aligned table)
    inv_date = invoice.get("invoice_date", datetime.now().strftime("%d.%m.%Y"))
    meta_data = [
        ["Rechnungsnummer:", invoice.get("invoice_number", "")],
        ["Rechnungsdatum:", inv_date],
        ["Veranstaltung:", event.get("name", "")],
        ["Kundennummer:", sch.get("id", "")[:8].upper()],
    ]
    if sch.get("steuernummer"):
        meta_data.append(["Steuernummer Kunde:", sch["steuernummer"]])

    meta_table = Table(meta_data, colWidths=[38 * mm, 52 * mm])
    meta_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    usable_w = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT
    table_w = 90 * mm
    spacer_w = usable_w - table_w
    meta_wrapper = Table([["", meta_table]], colWidths=[spacer_w, table_w])
    meta_wrapper.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(meta_wrapper)
    elements.append(Spacer(1, 5 * mm))

    # Title
    elements.append(Paragraph("Rechnung", styles["InvTitle"]))
    elements.append(Spacer(1, 3 * mm))

    # Introduction
    event_name = event.get("name", "")
    elements.append(Paragraph(
        f"Sehr geehrte Damen und Herren,<br/>"
        f"nachfolgend berechnen wir Ihnen die Energieversorgung für die Veranstaltung "
        f"<b>{event_name}</b>:",
        styles["InvNormal"]
    ))
    elements.append(Spacer(1, 4 * mm))

    # Line items table
    items = invoice.get("line_items", [])
    styles.add(ParagraphStyle("CellText", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=DARK))
    table_data = [["Pos.", "Beschreibung", "Menge", "Einheit", "Einzelpreis", "Gesamt"]]
    for item in items:
        desc = item.get("description", "").replace("\n", "<br/>")
        table_data.append([
            str(item.get("pos", "")),
            Paragraph(desc, styles["CellText"]),
            item.get("quantity", ""),
            item.get("unit", ""),
            f"{item.get('unit_price', 0):.2f} \u20ac" if item.get("unit_price") is not None else "",
            f"{item.get('total', 0):.2f} \u20ac",
        ])

    col_widths = [12 * mm, 62 * mm, 18 * mm, 18 * mm, 24 * mm, 26 * mm]
    inv_table = Table(table_data, colWidths=col_widths)
    inv_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("ALIGN", (4, 0), (4, -1), "RIGHT"),
        ("ALIGN", (5, 0), (5, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, PURPLE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, colors.Color(0.85, 0.85, 0.85)),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        *[("BACKGROUND", (0, i), (-1, i), colors.Color(0.97, 0.97, 0.97))
          for i in range(2, len(table_data), 2)],
    ]))
    elements.append(inv_table)
    elements.append(Spacer(1, 4 * mm))

    # Totals
    netto = invoice.get("netto", 0)
    mwst_rate = invoice.get("mwst_rate", 19)
    mwst_amount = invoice.get("mwst_amount", 0)
    brutto = invoice.get("brutto", 0)

    totals_data = [
        ["", "Nettobetrag:", f"{netto:.2f} \u20ac"],
        ["", f"zzgl. {mwst_rate}% MwSt:", f"{mwst_amount:.2f} \u20ac"],
        ["", "Rechnungsbetrag:", f"{brutto:.2f} \u20ac"],
    ]
    totals_table = Table(totals_data, colWidths=[100 * mm, 35 * mm, 25 * mm])
    totals_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 1), "Helvetica"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEABOVE", (1, 2), (2, 2), 0.7, DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 5 * mm))

    # Payment info
    elements.append(Paragraph(
        "Bitte überweisen Sie den Rechnungsbetrag innerhalb von 14 Tagen unter Angabe "
        f"der Rechnungsnummer <b>{invoice.get('invoice_number', '')}</b> auf das im Briefkopf "
        "angegebene Konto.",
        styles["InvNormal"]
    ))
    elements.append(Spacer(1, 3 * mm))

    # GiroCode (EPC QR Code) for bank transfer + optional Stripe payment link
    girocode_img = _generate_girocode(invoice)
    stripe_url = invoice.get("stripe_payment_url")
    if girocode_img or stripe_url:
        qr_row = []
        if girocode_img:
            from reportlab.platypus import Image as RLImage
            qr_image = RLImage(girocode_img, width=30*mm, height=30*mm)
            qr_left = Table(
                [[qr_image], [Paragraph("GiroCode scannen", styles["InvSmall"])]],
                colWidths=[32*mm],
            )
            qr_left.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]))
            qr_row.append(qr_left)
        
        if stripe_url:
            qr_row.append(Paragraph(
                f'<b>Online bezahlen:</b><br/><font color="blue"><u>{stripe_url[:60]}...</u></font>',
                styles["InvSmall"]
            ))
        elif girocode_img:
            qr_row.append(Paragraph(
                "Scannen Sie den QR-Code mit Ihrer Banking-App,<br/>um die Überweisung automatisch auszufüllen.",
                styles["InvSmall"]
            ))
        
        if qr_row:
            qr_table = Table([qr_row], colWidths=[34*mm, usable_w - 36*mm])
            qr_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            elements.append(qr_table)
    
    elements.append(Spacer(1, 5 * mm))

    # Closing
    elements.append(Paragraph("Bei Rückfragen stehen wir Ihnen gerne zur Verfügung.", styles["InvNormal"]))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph("Mit freundlichen Grüßen", styles["InvNormal"]))
    elements.append(Paragraph("<b>Eventenergie Deutschland GmbH &amp; Co. KG</b>", styles["InvNormal"]))

    doc.build(elements)
    content_bytes = buf.getvalue()

    # Merge with letterhead background
    pdf_with_letterhead = _merge_letterhead(content_bytes)

    # Generate ZUGFeRD XML and embed into PDF
    zugferd_xml = _build_zugferd_xml(invoice)
    try:
        return generate_from_binary(
            pdf_with_letterhead,
            zugferd_xml,
            flavor="factur-x",
            level="basic",
            check_xsd=True,
        )
    except Exception:
        # Fallback: return PDF without ZUGFeRD if XML fails validation
        return pdf_with_letterhead


def _xml_escape(text):
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _build_zugferd_xml(invoice: dict) -> bytes:
    """Build Factur-X/ZUGFeRD Basic XML for an invoice."""
    sch = invoice.get("schausteller", {})
    event = invoice.get("event", {})
    items = invoice.get("items", [])
    inv_number = invoice.get("invoice_number", "")
    inv_date_str = invoice.get("invoice_date", datetime.now().strftime("%d.%m.%Y"))

    # Parse date to YYYYMMDD
    try:
        dt = datetime.strptime(inv_date_str, "%d.%m.%Y")
        date_102 = dt.strftime("%Y%m%d")
    except Exception:
        date_102 = datetime.now().strftime("%Y%m%d")

    netto = invoice.get("netto", 0)
    mwst = invoice.get("mwst", 0)
    brutto = invoice.get("brutto", 0)

    seller_name = _xml_escape("Eventenergie Deutschland GmbH & Co. KG")
    seller_street = _xml_escape("Thyssenstraße 10")
    seller_city = _xml_escape("Andernach")
    seller_plz = "56626"
    seller_tax_id = "DE123456789"

    buyer_name = _xml_escape(sch.get("firma") or sch.get("name", ""))
    buyer_street = _xml_escape(sch.get("strasse", ""))
    buyer_city = _xml_escape(sch.get("ort", ""))
    buyer_plz = _xml_escape(sch.get("plz", ""))
    buyer_tax = sch.get("steuernummer", "")

    # Build line items XML
    line_items_xml = ""
    for i, item in enumerate(items, 1):
        qty = item.get("menge", 1)
        unit = item.get("einheit", "pauschal")
        unit_code = "KWH" if "kwh" in unit.lower() else "C62"
        price = item.get("einzelpreis", 0)
        total = item.get("gesamt", 0)
        desc = _xml_escape(item.get("beschreibung", ""))

        line_items_xml += f"""
        <ram:IncludedSupplyChainTradeLineItem>
            <ram:AssociatedDocumentLineDocument>
                <ram:LineID>{i}</ram:LineID>
            </ram:AssociatedDocumentLineDocument>
            <ram:SpecifiedTradeProduct>
                <ram:Name>{desc}</ram:Name>
            </ram:SpecifiedTradeProduct>
            <ram:SpecifiedLineTradeAgreement>
                <ram:NetPriceProductTradePrice>
                    <ram:ChargeAmount>{price:.2f}</ram:ChargeAmount>
                </ram:NetPriceProductTradePrice>
            </ram:SpecifiedLineTradeAgreement>
            <ram:SpecifiedLineTradeDelivery>
                <ram:BilledQuantity unitCode="{unit_code}">{qty}</ram:BilledQuantity>
            </ram:SpecifiedLineTradeDelivery>
            <ram:SpecifiedLineTradeSettlement>
                <ram:ApplicableTradeTax>
                    <ram:TypeCode>VAT</ram:TypeCode>
                    <ram:CategoryCode>S</ram:CategoryCode>
                    <ram:RateApplicablePercent>19.00</ram:RateApplicablePercent>
                </ram:ApplicableTradeTax>
                <ram:SpecifiedTradeSettlementLineMonetarySummation>
                    <ram:LineTotalAmount>{total:.2f}</ram:LineTotalAmount>
                </ram:SpecifiedTradeSettlementLineMonetarySummation>
            </ram:SpecifiedLineTradeSettlement>
        </ram:IncludedSupplyChainTradeLineItem>"""

    # If no items, add a single fallback line
    if not line_items_xml:
        line_items_xml = f"""
        <ram:IncludedSupplyChainTradeLineItem>
            <ram:AssociatedDocumentLineDocument>
                <ram:LineID>1</ram:LineID>
            </ram:AssociatedDocumentLineDocument>
            <ram:SpecifiedTradeProduct>
                <ram:Name>Energieversorgung {_xml_escape(event.get('name', ''))}</ram:Name>
            </ram:SpecifiedTradeProduct>
            <ram:SpecifiedLineTradeAgreement>
                <ram:NetPriceProductTradePrice>
                    <ram:ChargeAmount>{netto:.2f}</ram:ChargeAmount>
                </ram:NetPriceProductTradePrice>
            </ram:SpecifiedLineTradeAgreement>
            <ram:SpecifiedLineTradeDelivery>
                <ram:BilledQuantity unitCode="C62">1</ram:BilledQuantity>
            </ram:SpecifiedLineTradeDelivery>
            <ram:SpecifiedLineTradeSettlement>
                <ram:ApplicableTradeTax>
                    <ram:TypeCode>VAT</ram:TypeCode>
                    <ram:CategoryCode>S</ram:CategoryCode>
                    <ram:RateApplicablePercent>19.00</ram:RateApplicablePercent>
                </ram:ApplicableTradeTax>
                <ram:SpecifiedTradeSettlementLineMonetarySummation>
                    <ram:LineTotalAmount>{netto:.2f}</ram:LineTotalAmount>
                </ram:SpecifiedTradeSettlementLineMonetarySummation>
            </ram:SpecifiedLineTradeSettlement>
        </ram:IncludedSupplyChainTradeLineItem>"""

    buyer_tax_xml = ""
    if buyer_tax:
        buyer_tax_xml = f"""
                <ram:SpecifiedTaxRegistration>
                    <ram:ID schemeID="VA">{_xml_escape(buyer_tax)}</ram:ID>
                </ram:SpecifiedTaxRegistration>"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
    xmlns:qdt="urn:un:unece:uncefact:data:standard:QualifiedDataType:100">
    <rsm:ExchangedDocumentContext>
        <ram:GuidelineSpecifiedDocumentContextParameter>
            <ram:ID>urn:factur-x.eu:1p0:basic</ram:ID>
        </ram:GuidelineSpecifiedDocumentContextParameter>
    </rsm:ExchangedDocumentContext>
    <rsm:ExchangedDocument>
        <ram:ID>{_xml_escape(inv_number)}</ram:ID>
        <ram:TypeCode>380</ram:TypeCode>
        <ram:IssueDateTime>
            <udt:DateTimeString format="102">{date_102}</udt:DateTimeString>
        </ram:IssueDateTime>
    </rsm:ExchangedDocument>
    <rsm:SupplyChainTradeTransaction>{line_items_xml}
        <ram:ApplicableHeaderTradeAgreement>
            <ram:SellerTradeParty>
                <ram:Name>{seller_name}</ram:Name>
                <ram:PostalTradeAddress>
                    <ram:PostcodeCode>{seller_plz}</ram:PostcodeCode>
                    <ram:LineOne>{seller_street}</ram:LineOne>
                    <ram:CityName>{seller_city}</ram:CityName>
                    <ram:CountryID>DE</ram:CountryID>
                </ram:PostalTradeAddress>
                <ram:SpecifiedTaxRegistration>
                    <ram:ID schemeID="VA">{seller_tax_id}</ram:ID>
                </ram:SpecifiedTaxRegistration>
            </ram:SellerTradeParty>
            <ram:BuyerTradeParty>
                <ram:Name>{buyer_name}</ram:Name>
                <ram:PostalTradeAddress>
                    <ram:PostcodeCode>{buyer_plz}</ram:PostcodeCode>
                    <ram:LineOne>{buyer_street}</ram:LineOne>
                    <ram:CityName>{buyer_city}</ram:CityName>
                    <ram:CountryID>DE</ram:CountryID>
                </ram:PostalTradeAddress>{buyer_tax_xml}
            </ram:BuyerTradeParty>
        </ram:ApplicableHeaderTradeAgreement>
        <ram:ApplicableHeaderTradeDelivery/>
        <ram:ApplicableHeaderTradeSettlement>
            <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
            <ram:ApplicableTradeTax>
                <ram:CalculatedAmount>{mwst:.2f}</ram:CalculatedAmount>
                <ram:TypeCode>VAT</ram:TypeCode>
                <ram:BasisAmount>{netto:.2f}</ram:BasisAmount>
                <ram:CategoryCode>S</ram:CategoryCode>
                <ram:RateApplicablePercent>19.00</ram:RateApplicablePercent>
            </ram:ApplicableTradeTax>
            <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
                <ram:LineTotalAmount>{netto:.2f}</ram:LineTotalAmount>
                <ram:TaxBasisTotalAmount>{netto:.2f}</ram:TaxBasisTotalAmount>
                <ram:TaxTotalAmount currencyID="EUR">{mwst:.2f}</ram:TaxTotalAmount>
                <ram:GrandTotalAmount>{brutto:.2f}</ram:GrandTotalAmount>
                <ram:DuePayableAmount>{brutto:.2f}</ram:DuePayableAmount>
            </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        </ram:ApplicableHeaderTradeSettlement>
    </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""

    return xml.encode("utf-8")


def _generate_girocode(invoice: dict):
    """Generate an EPC QR code (GiroCode) for SEPA bank transfer.
    
    Returns BytesIO with PNG image, or None if IBAN not configured.
    """
    import qrcode
    
    # Company bank details - from environment or invoice settings
    iban = os.environ.get("COMPANY_IBAN", "")
    bic = os.environ.get("COMPANY_BIC", "")
    company_name = "Eventenergie Deutschland GmbH"
    
    if not iban:
        return None
    
    amount = float(invoice.get("brutto", invoice.get("total_gross", invoice.get("total_amount", 0))))
    reference = invoice.get("invoice_number", "")
    
    # EPC QR Code format (GiroCode v002)
    # See: https://www.europeanpaymentscouncil.eu/sites/default/files/KB/files/EPC069-12%20v2.1%20Quick%20Response%20Code%20-%20Guidelines%20to%20Enable%20the%20Data%20Capture%20for%20the%20Initiation%20of%20a%20SCT.pdf
    epc_data = "\n".join([
        "BCD",                          # Service Tag
        "002",                          # Version
        "1",                            # Encoding (UTF-8)
        "SCT",                          # Identification
        bic,                            # BIC
        company_name[:70],              # Beneficiary Name (max 70)
        iban.replace(" ", ""),           # IBAN
        f"EUR{amount:.2f}",             # Amount
        "",                             # Purpose (empty)
        reference[:35],                 # Remittance Reference (max 35)
        f"Rechnung {reference}",        # Remittance Text (max 140)
        "",                             # Information (empty)
    ])
    
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=2)
    qr.add_data(epc_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
