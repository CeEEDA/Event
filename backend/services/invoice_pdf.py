"""Invoice PDF generation for Kirmes billing - uses company letterhead PDF as background."""
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
        topMargin=58 * mm,   # Below letterhead header + sender line
        bottomMargin=42 * mm,  # Above letterhead footer
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("InvNormal", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=13, textColor=DARK))
    styles.add(ParagraphStyle("InvBold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=13, textColor=DARK))
    styles.add(ParagraphStyle("InvSmall", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=11, textColor=GRAY))
    styles.add(ParagraphStyle("InvTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=DARK))
    styles.add(ParagraphStyle("InvRight", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=13, textColor=DARK, alignment=TA_RIGHT))

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
    elements.append(Spacer(1, 12 * mm))

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

    meta_table = Table(meta_data, colWidths=[40 * mm, 55 * mm])
    meta_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    usable_w = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT
    table_w = 95 * mm
    spacer_w = usable_w - table_w
    meta_wrapper = Table([[None, meta_table]], colWidths=[spacer_w, table_w])
    meta_wrapper.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(meta_wrapper)
    elements.append(Spacer(1, 8 * mm))

    # Title
    elements.append(Paragraph("Rechnung", styles["InvTitle"]))
    elements.append(Spacer(1, 4 * mm))

    # Introduction
    event_name = event.get("name", "")
    elements.append(Paragraph(
        f"Sehr geehrte Damen und Herren,<br/>"
        f"nachfolgend berechnen wir Ihnen die Energieversorgung für die Veranstaltung "
        f"<b>{event_name}</b>:",
        styles["InvNormal"]
    ))
    elements.append(Spacer(1, 6 * mm))

    # Line items table
    items = invoice.get("line_items", [])
    table_data = [["Pos.", "Beschreibung", "Menge", "Einheit", "Einzelpreis", "Gesamt"]]
    for item in items:
        table_data.append([
            str(item.get("pos", "")),
            item.get("description", ""),
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
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEABOVE", (1, 2), (2, 2), 0.7, DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 8 * mm))

    # Payment info
    elements.append(Paragraph(
        "Bitte überweisen Sie den Rechnungsbetrag innerhalb von 14 Tagen unter Angabe "
        f"der Rechnungsnummer <b>{invoice.get('invoice_number', '')}</b> auf das im Briefkopf "
        "angegebene Konto.",
        styles["InvNormal"]
    ))
    elements.append(Spacer(1, 8 * mm))

    # Closing
    elements.append(Paragraph("Bei Rückfragen stehen wir Ihnen gerne zur Verfügung.", styles["InvNormal"]))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph("Mit freundlichen Grüßen", styles["InvNormal"]))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph("<b>Eventenergie Deutschland GmbH &amp; Co. KG</b>", styles["InvNormal"]))

    doc.build(elements, canvasmaker=LetterheadCanvas)
    content_bytes = buf.getvalue()

    # Merge with letterhead background
    return _merge_letterhead(content_bytes)
