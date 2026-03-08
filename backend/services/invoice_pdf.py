"""Invoice PDF generation for Kirmes billing with company letterhead."""
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# Company data from letterhead
COMPANY = {
    "name": "Eventenergie Deutschland GmbH & Co. KG",
    "street": "Thyssenstraße 10",
    "city": "56626 Andernach",
    "phone": "+49 (0) 2632 30921-0",
    "hotline": "+49 (0) 800 POWER24",
    "email": "info@eventenergie-deutschland.de",
    "web": "www.eventenergie-deutschland.de",
    "court": "Amtsgericht Koblenz: HRA 22723",
    "tax_office": "Finanzamt Mayen",
    "ust_id": "DE 333489815",
    "ceo": "Christian Ecker",
    "bank": "Teba Landau",
    "iban": "DE86 7413 1000 0002 6260 00",
    "bic": "TEKRDE71",
}

PURPLE = colors.Color(0.52, 0.18, 0.68)
DARK = colors.Color(0.2, 0.2, 0.2)
GRAY = colors.Color(0.4, 0.4, 0.4)
LIGHT_GRAY = colors.Color(0.6, 0.6, 0.6)

PAGE_W, PAGE_H = A4
MARGIN_LEFT = 25 * mm
MARGIN_RIGHT = 20 * mm
MARGIN_TOP = 20 * mm


class LetterheadCanvas(canvas.Canvas):
    """Custom canvas that draws header and footer on every page."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        super().showPage()

    def save(self):
        for page_state in self.pages:
            self.__dict__.update(page_state)
            self._draw_header()
            self._draw_footer()
            super().showPage()
        super().save()

    def _draw_header(self):
        c = self
        # Logo area - draw the grid icon
        x_logo = MARGIN_LEFT
        y_logo = PAGE_H - MARGIN_TOP - 5 * mm

        # Draw 3x3 purple dots (simplified logo)
        dot_r = 1.8 * mm
        dot_spacing = 5.0 * mm
        for row in range(3):
            for col in range(3):
                cx = x_logo + 4 * mm + col * dot_spacing
                cy = y_logo - 2 * mm - row * dot_spacing
                c.setFillColor(PURPLE)
                c.circle(cx, cy, dot_r, fill=1, stroke=0)

        # Company name text
        x_text = x_logo + 22 * mm
        c.setFillColor(DARK)
        c.setFont("Helvetica", 16)
        c.drawString(x_text, y_logo + 2 * mm, "E V E N T E N E R G I E")
        c.setFont("Helvetica", 14)
        c.drawString(x_text, y_logo - 7 * mm, "D E U T S C H L A N D")

        # Purple line under header
        y_line = y_logo - 14 * mm
        c.setStrokeColor(PURPLE)
        c.setLineWidth(0.7)
        c.line(x_text, y_line, PAGE_W - MARGIN_RIGHT, y_line)

        # Sender line (small, underlined)
        y_sender = y_logo - 27 * mm
        c.setFillColor(PURPLE)
        c.setFont("Helvetica-Bold", 7)
        sender = f"{COMPANY['name']}  ·  {COMPANY['street']}  |  {COMPANY['city']}"
        c.drawString(MARGIN_LEFT, y_sender, sender)
        # Underline
        w = c.stringWidth(sender, "Helvetica-Bold", 7)
        c.setStrokeColor(PURPLE)
        c.setLineWidth(0.3)
        c.line(MARGIN_LEFT, y_sender - 1.5, MARGIN_LEFT + w, y_sender - 1.5)

    def _draw_footer(self):
        c = self
        y_base = 28 * mm

        # Purple line above footer
        c.setStrokeColor(PURPLE)
        c.setLineWidth(0.5)
        c.line(MARGIN_LEFT, y_base + 8 * mm, PAGE_W - MARGIN_RIGHT, y_base + 8 * mm)

        fs = 6.5
        lh = 2.8 * mm

        def draw_col(x, lines, bold_first=True):
            for i, line in enumerate(lines):
                if i == 0 and bold_first:
                    c.setFont("Helvetica-Bold", fs)
                else:
                    c.setFont("Helvetica", fs)
                c.setFillColor(DARK)
                c.drawString(x, y_base - i * lh, line)

        # Column 1: Address + Contact
        draw_col(MARGIN_LEFT, [
            COMPANY["name"],
            COMPANY["street"],
            COMPANY["city"],
            f"Tel.: {COMPANY['phone']}",
            f"Hotline: {COMPANY['hotline']}",
            COMPANY["email"],
            COMPANY["web"],
        ])

        # Column 2: Registration + Tax
        x2 = MARGIN_LEFT + 55 * mm
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", fs)
        c.drawString(x2, y_base, COMPANY["court"])
        c.setFont("Helvetica-Bold", fs)
        c.drawString(x2, y_base - 2 * lh, "Finanzamt Mayen")
        c.setFont("Helvetica-Bold", fs)
        c.drawString(x2, y_base - 3 * lh, "Ust.-ID: ")
        c.setFont("Helvetica", fs)
        c.drawString(x2 + c.stringWidth("Ust.-ID: ", "Helvetica-Bold", fs), y_base - 3 * lh, COMPANY["ust_id"])

        # Column 3: Management
        x3 = MARGIN_LEFT + 105 * mm
        c.setFont("Helvetica-Bold", fs)
        c.drawString(x3, y_base, "Geschäftsführung:")
        c.setFont("Helvetica", fs)
        c.drawString(x3, y_base - lh, COMPANY["ceo"])

        # Column 4: Bank
        x4 = MARGIN_LEFT + 140 * mm
        c.setFont("Helvetica", fs)
        c.drawString(x4, y_base, COMPANY["bank"])
        c.setFont("Helvetica-Bold", fs)
        c.drawString(x4, y_base - lh, "IBAN: ")
        c.setFont("Helvetica", fs)
        c.drawString(x4 + c.stringWidth("IBAN: ", "Helvetica-Bold", fs), y_base - lh, COMPANY["iban"])
        c.setFont("Helvetica-Bold", fs)
        c.drawString(x4, y_base - 2 * lh, "BIC: ")
        c.setFont("Helvetica", fs)
        c.drawString(x4 + c.stringWidth("BIC: ", "Helvetica-Bold", fs), y_base - 2 * lh, COMPANY["bic"])


def generate_invoice_pdf(invoice: dict) -> bytes:
    """Generate a PDF invoice with company letterhead. Returns PDF bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN_LEFT, rightMargin=MARGIN_RIGHT,
        topMargin=68 * mm,  # Space for header + sender line
        bottomMargin=42 * mm,  # Space for footer
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("InvNormal", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=13, textColor=DARK))
    styles.add(ParagraphStyle("InvBold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=13, textColor=DARK))
    styles.add(ParagraphStyle("InvSmall", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=11, textColor=GRAY))
    styles.add(ParagraphStyle("InvTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=DARK))
    styles.add(ParagraphStyle("InvRight", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=13, textColor=DARK, alignment=TA_RIGHT))
    styles.add(ParagraphStyle("InvRightBold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=13, textColor=DARK, alignment=TA_RIGHT))

    elements = []
    sch = invoice.get("schausteller", {})
    event = invoice.get("event", {})

    # Recipient address block
    elements.append(Paragraph(f"{sch.get('firma', '')}", styles["InvBold"]))
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
    # Right-align the meta table
    meta_wrapper = Table([[None, meta_table]], colWidths=[65 * mm, 95 * mm])
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
            f"{item.get('unit_price', 0):.2f} €" if item.get("unit_price") is not None else "",
            f"{item.get('total', 0):.2f} €",
        ])

    col_widths = [12 * mm, 62 * mm, 18 * mm, 18 * mm, 24 * mm, 26 * mm]
    inv_table = Table(table_data, colWidths=col_widths)
    inv_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        # Body
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        # Alignment
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("ALIGN", (4, 0), (4, -1), "RIGHT"),
        ("ALIGN", (5, 0), (5, -1), "RIGHT"),
        # Grid
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, PURPLE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, colors.Color(0.85, 0.85, 0.85)),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, DARK),
        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        # Alternate rows
        *[("BACKGROUND", (0, i), (-1, i), colors.Color(0.97, 0.97, 0.97))
          for i in range(2, len(table_data), 2)],
    ]))
    elements.append(inv_table)
    elements.append(Spacer(1, 4 * mm))

    # Totals section
    netto = invoice.get("netto", 0)
    mwst_rate = invoice.get("mwst_rate", 19)
    mwst_amount = invoice.get("mwst_amount", 0)
    brutto = invoice.get("brutto", 0)

    totals_data = [
        ["", "Nettobetrag:", f"{netto:.2f} €"],
        ["", f"zzgl. {mwst_rate}% MwSt:", f"{mwst_amount:.2f} €"],
        ["", "Rechnungsbetrag:", f"{brutto:.2f} €"],
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
        "Bitte überweisen Sie den Rechnungsbetrag innerhalb von 14 Tagen auf folgendes Konto:",
        styles["InvNormal"]
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(f"<b>IBAN:</b> {COMPANY['iban']}", styles["InvNormal"]))
    elements.append(Paragraph(f"<b>BIC:</b> {COMPANY['bic']}", styles["InvNormal"]))
    elements.append(Paragraph(f"<b>Verwendungszweck:</b> {invoice.get('invoice_number', '')}", styles["InvNormal"]))
    elements.append(Spacer(1, 8 * mm))

    # Closing
    elements.append(Paragraph("Bei Rückfragen stehen wir Ihnen gerne zur Verfügung.", styles["InvNormal"]))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph("Mit freundlichen Grüßen", styles["InvNormal"]))
    elements.append(Paragraph(f"<b>{COMPANY['name']}</b>", styles["InvNormal"]))

    doc.build(elements, canvasmaker=LetterheadCanvas)
    return buf.getvalue()
