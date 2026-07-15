"""PDF-Generator fuer die HR-Jahresauswertung aller Mitarbeiter.

Erstellt eine kompakte einseitige PDF mit einer Zeile pro Mitarbeiter:
Name | UEberstunden | Urlaub genommen | Resturlaub | Krankheitstage.
"""
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT


PURPLE = colors.Color(0.52, 0.18, 0.68)
DARK = colors.Color(0.2, 0.2, 0.2)
GRAY = colors.Color(0.4, 0.4, 0.4)


def _fmt_hours(v) -> str:
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        f = 0.0
    return f"{f:+.2f} h" if f else "0,00 h"


def _fmt_days(v) -> str:
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        f = 0.0
    if abs(f - round(f)) < 0.001:
        return f"{int(round(f))}"
    return f"{f:.1f}".replace(".", ",")


def generate_yearly_evaluation_pdf(rows: list[dict], year: int) -> bytes:
    """Erzeugt eine PDF-Uebersicht aller Mitarbeiter fuer das angegebene Jahr.

    Args:
        rows: Liste von Dicts mit Keys: name, overtime_hours,
            vacation_days_used, vacation_days_remaining, sick_days.
        year: Kalenderjahr fuer den Report-Titel.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Mitarbeiter-Auswertung {year}",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("EvTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=DARK))
    styles.add(ParagraphStyle("EvSub", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=GRAY))
    styles.add(ParagraphStyle("EvCell", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=11, textColor=DARK, alignment=TA_LEFT))
    styles.add(ParagraphStyle("EvCellR", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=11, textColor=DARK, alignment=TA_RIGHT))
    styles.add(ParagraphStyle("EvHeadCell", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=colors.white, alignment=TA_LEFT))
    styles.add(ParagraphStyle("EvHeadCellR", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=colors.white, alignment=TA_RIGHT))

    elements = []
    elements.append(Paragraph(f"Mitarbeiter-Auswertung {year}", styles["EvTitle"]))
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    elements.append(Paragraph(
        f"Übersicht aller aktiven Mitarbeiter &ndash; erstellt am {generated_at}.<br/>"
        f"Überstunden = aktueller Saldo (kumuliert). Urlaub &amp; Krankheit beziehen sich auf {year}.",
        styles["EvSub"],
    ))
    elements.append(Spacer(1, 5 * mm))

    header = [
        Paragraph("Name", styles["EvHeadCell"]),
        Paragraph("Überstunden", styles["EvHeadCellR"]),
        Paragraph("Urlaub genommen", styles["EvHeadCellR"]),
        Paragraph("Resturlaub", styles["EvHeadCellR"]),
        Paragraph("Krankheitstage", styles["EvHeadCellR"]),
    ]

    data = [header]
    # Alphabetisch nach Name
    rows_sorted = sorted(rows, key=lambda r: (r.get("name") or "").lower())
    for r in rows_sorted:
        data.append([
            Paragraph(r.get("name") or "-", styles["EvCell"]),
            Paragraph(_fmt_hours(r.get("overtime_hours")), styles["EvCellR"]),
            Paragraph(_fmt_days(r.get("vacation_days_used")), styles["EvCellR"]),
            Paragraph(_fmt_days(r.get("vacation_days_remaining")), styles["EvCellR"]),
            Paragraph(_fmt_days(r.get("sick_days")), styles["EvCellR"]),
        ])

    if len(data) == 1:
        # Keine MA vorhanden
        data.append([Paragraph("Keine aktiven Mitarbeiter gefunden.", styles["EvCell"]), "", "", "", ""])

    col_widths = [60 * mm, 30 * mm, 30 * mm, 26 * mm, 28 * mm]
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, PURPLE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.Color(0.85, 0.85, 0.85)),
        *[
            ("BACKGROUND", (0, i), (-1, i), colors.Color(0.97, 0.95, 0.99))
            for i in range(2, len(data), 2)
        ],
    ]))
    elements.append(tbl)

    # Kompakter Footer
    elements.append(Spacer(1, 6 * mm))
    total_ma = max(0, len(data) - 1)
    total_ot = sum(float(r.get("overtime_hours") or 0) for r in rows_sorted)
    total_vac_used = sum(float(r.get("vacation_days_used") or 0) for r in rows_sorted)
    total_sick = sum(float(r.get("sick_days") or 0) for r in rows_sorted)
    footer_text = (
        f"Summen: {total_ma} Mitarbeiter &nbsp;|&nbsp; "
        f"Überstunden gesamt: {_fmt_hours(total_ot)} &nbsp;|&nbsp; "
        f"Urlaub {year}: {_fmt_days(total_vac_used)} Tage &nbsp;|&nbsp; "
        f"Krank {year}: {_fmt_days(total_sick)} Tage"
    )
    elements.append(Paragraph(footer_text, styles["EvSub"]))

    doc.build(elements)
    return buf.getvalue()
