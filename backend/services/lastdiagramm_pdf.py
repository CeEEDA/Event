"""Lastdiagramm PDF generation - Cover page + daily load diagrams."""
import io
import os
from datetime import datetime, timezone
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from pdfrw import PdfReader as PdfrwReader, PageMerge, PdfWriter

LETTERHEAD_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "briefpapier.pdf")

PURPLE = colors.Color(0.52, 0.18, 0.68)
DARK = colors.Color(0.2, 0.2, 0.2)
GRAY = colors.Color(0.4, 0.4, 0.4)
LIGHT_GRAY = colors.Color(0.95, 0.95, 0.95)

PAGE_W, PAGE_H = A4
MARGIN_LEFT = 25 * mm
MARGIN_RIGHT = 20 * mm


def _merge_letterhead(content_pdf_bytes: bytes) -> bytes:
    """Merge letterhead background with content overlay (first page only)."""
    if not os.path.exists(LETTERHEAD_PATH):
        return content_pdf_bytes
    letterhead = PdfrwReader(LETTERHEAD_PATH)
    content = PdfrwReader(fdata=content_pdf_bytes)
    bg_page = letterhead.pages[0]

    # Only merge letterhead on first page
    if content.pages:
        merger = PageMerge(content.pages[0])
        merger.add(bg_page, prepend=True)
        merger.render()

    writer_buf = io.BytesIO()
    w = PdfWriter()
    w.addpages(content.pages)
    w.write(writer_buf)
    return writer_buf.getvalue()


def _parse_ts(ts_str):
    """Parse ISO timestamp string to datetime."""
    if not ts_str:
        return None
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.fromisoformat(ts_str)
    except Exception:
        return None


def _analyze_data(measurements):
    """Analyze measurements for cover page stats."""
    max_i_l1 = {"value": 0, "ts": None}
    max_i_l2 = {"value": 0, "ts": None}
    max_i_l3 = {"value": 0, "ts": None}
    max_power = {"value": 0, "ts": None}

    for m in measurements:
        ts = m.get("ts_utc")

        i1 = m.get("I_L1") or 0
        if i1 > max_i_l1["value"]:
            max_i_l1 = {"value": round(i1, 2), "ts": ts}

        i2 = m.get("I_L2") or 0
        if i2 > max_i_l2["value"]:
            max_i_l2 = {"value": round(i2, 2), "ts": ts}

        i3 = m.get("I_L3") or 0
        if i3 > max_i_l3["value"]:
            max_i_l3 = {"value": round(i3, 2), "ts": ts}

        p = m.get("P_sum_kW") or 0
        if p > max_power["value"]:
            max_power = {"value": round(p, 3), "ts": ts}

    return {
        "max_i_l1": max_i_l1,
        "max_i_l2": max_i_l2,
        "max_i_l3": max_i_l3,
        "max_power": max_power,
    }


def _group_by_day(measurements):
    """Group measurements by calendar day."""
    days = defaultdict(list)
    for m in measurements:
        ts = _parse_ts(m.get("ts_utc"))
        if ts:
            day_key = ts.strftime("%Y-%m-%d")
            days[day_key].append(m)
    return dict(sorted(days.items()))


def _fmt_ts(ts_str):
    """Format timestamp for display."""
    ts = _parse_ts(ts_str)
    if not ts:
        return "–"
    return ts.strftime("%d.%m.%Y %H:%M:%S")


def _fmt_date(date_str):
    """Format date string."""
    if not date_str:
        return "–"
    try:
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return date_str


def _generate_daily_chart(day_key, day_data):
    """Generate a chart image (PNG bytes) for a single day showing power and current per phase."""
    timestamps = []
    p_values = []
    i_l1 = []
    i_l2 = []
    i_l3 = []

    for m in sorted(day_data, key=lambda x: x.get("ts_utc", "")):
        ts = _parse_ts(m.get("ts_utc"))
        if not ts:
            continue
        timestamps.append(ts)
        p_values.append(m.get("P_sum_kW") or 0)
        i_l1.append(m.get("I_L1") or 0)
        i_l2.append(m.get("I_L2") or 0)
        i_l3.append(m.get("I_L3") or 0)

    if not timestamps:
        return None

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.5), dpi=120)
    fig.suptitle(f"Lastdiagramm – {datetime.strptime(day_key, '%Y-%m-%d').strftime('%d.%m.%Y')}",
                 fontsize=13, fontweight="bold", color="#333")

    # Chart 1: Power (kW)
    ax1.fill_between(timestamps, p_values, alpha=0.15, color="#8B2FC9")
    ax1.plot(timestamps, p_values, color="#8B2FC9", linewidth=1.2, label="Leistung (kW)")
    ax1.set_ylabel("Leistung (kW)", fontsize=9, color="#555")
    ax1.legend(loc="upper right", fontsize=8)
    ax1.grid(True, alpha=0.3, linestyle="--")
    ax1.tick_params(axis="both", labelsize=8)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    # Chart 2: Current per Phase (A)
    ax2.plot(timestamps, i_l1, color="#e74c3c", linewidth=1.0, label="L1 (A)", alpha=0.85)
    ax2.plot(timestamps, i_l2, color="#2ecc71", linewidth=1.0, label="L2 (A)", alpha=0.85)
    ax2.plot(timestamps, i_l3, color="#3498db", linewidth=1.0, label="L3 (A)", alpha=0.85)
    ax2.set_ylabel("Strom (A)", fontsize=9, color="#555")
    ax2.set_xlabel("Uhrzeit", fontsize=9, color="#555")
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(True, alpha=0.3, linestyle="--")
    ax2.tick_params(axis="both", labelsize=8)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_lastdiagramm_pdf(order: dict, measurements: list) -> bytes:
    """Generate a complete Lastdiagramm PDF with cover page and daily charts."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN_LEFT, rightMargin=MARGIN_RIGHT,
        topMargin=55 * mm,
        bottomMargin=30 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("LDNormal", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=DARK))
    styles.add(ParagraphStyle("LDBold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=DARK))
    styles.add(ParagraphStyle("LDTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=DARK))
    styles.add(ParagraphStyle("LDSubTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=PURPLE))
    styles.add(ParagraphStyle("LDSmall", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=GRAY))
    styles.add(ParagraphStyle("LDCenter", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=DARK, alignment=TA_CENTER))

    elements = []
    signup = order.get("signup", {})
    event = order.get("event", {})
    sch = order.get("schausteller", {})

    # ====== COVER PAGE ======
    elements.append(Paragraph("Lastdiagramm", styles["LDTitle"]))
    elements.append(Spacer(1, 5 * mm))

    # Recipient
    if sch.get("firma"):
        elements.append(Paragraph(sch["firma"], styles["LDBold"]))
    if sch.get("name"):
        elements.append(Paragraph(sch["name"], styles["LDNormal"]))
    if sch.get("strasse"):
        elements.append(Paragraph(sch["strasse"], styles["LDNormal"]))
    if sch.get("plz") or sch.get("ort"):
        elements.append(Paragraph(f"{sch.get('plz', '')} {sch.get('ort', '')}", styles["LDNormal"]))
    elements.append(Spacer(1, 8 * mm))

    # Event info table
    start = _fmt_date(event.get("start_date"))
    end = _fmt_date(event.get("end_date"))
    kwh_used = signup.get("kwh_used") or 0

    info_data = [
        ["Kirmes:", event.get("name", "–")],
        ["Fahrgeschäft:", signup.get("fahrgeschaeft", "–")],
        ["Gebuchter Netzanschluss:", signup.get("connection_type", "–")],
        ["Zeitraum:", f"{start} – {end}"],
        ["Verbrauchte kWh:", f"{kwh_used:.2f} kWh"],
    ]
    info_table = Table(info_data, colWidths=[55 * mm, 105 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.Color(0.8, 0.8, 0.8)),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 8 * mm))

    # Analyze data for max values
    stats = _analyze_data(measurements)

    # Max Current per Phase
    elements.append(Paragraph("Maximaler Strom pro Phase", styles["LDSubTitle"]))
    elements.append(Spacer(1, 2 * mm))

    phase_data = [
        ["Phase", "Max. Strom", "Datum / Uhrzeit"],
        ["L1", f"{stats['max_i_l1']['value']:.2f} A", _fmt_ts(stats["max_i_l1"]["ts"])],
        ["L2", f"{stats['max_i_l2']['value']:.2f} A", _fmt_ts(stats["max_i_l2"]["ts"])],
        ["L3", f"{stats['max_i_l3']['value']:.2f} A", _fmt_ts(stats["max_i_l3"]["ts"])],
    ]
    phase_table = Table(phase_data, colWidths=[30 * mm, 40 * mm, 90 * mm])
    phase_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.Color(0.8, 0.8, 0.8)),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        *[("BACKGROUND", (0, i), (-1, i), LIGHT_GRAY) for i in range(2, len(phase_data), 2)],
    ]))
    elements.append(phase_table)
    elements.append(Spacer(1, 8 * mm))

    # Max Power
    elements.append(Paragraph("Maximale Leistung", styles["LDSubTitle"]))
    elements.append(Spacer(1, 2 * mm))

    power_data = [
        ["Max. Leistung", "Datum / Uhrzeit"],
        [f"{stats['max_power']['value']:.3f} kW", _fmt_ts(stats["max_power"]["ts"])],
    ]
    power_table = Table(power_data, colWidths=[50 * mm, 110 * mm])
    power_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        ("ALIGN", (0, 1), (0, 1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.Color(0.8, 0.8, 0.8)),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(power_table)

    # ====== DAILY CHARTS ======
    daily = _group_by_day(measurements)
    for day_key, day_data in daily.items():
        chart_buf = _generate_daily_chart(day_key, day_data)
        if chart_buf:
            elements.append(PageBreak())
            chart_img = Image(chart_buf, width=165 * mm, height=108 * mm)
            elements.append(Spacer(1, 5 * mm))
            elements.append(chart_img)
            # Small summary below chart
            day_stats = _analyze_data(day_data)
            day_dt = datetime.strptime(day_key, "%Y-%m-%d").strftime("%d.%m.%Y")
            summary = (
                f"<b>{day_dt}</b> — "
                f"Max Leistung: {day_stats['max_power']['value']:.3f} kW | "
                f"Max L1: {day_stats['max_i_l1']['value']:.2f} A | "
                f"Max L2: {day_stats['max_i_l2']['value']:.2f} A | "
                f"Max L3: {day_stats['max_i_l3']['value']:.2f} A"
            )
            elements.append(Spacer(1, 3 * mm))
            elements.append(Paragraph(summary, styles["LDSmall"]))

    doc.build(elements)
    content_bytes = buf.getvalue()

    # Merge letterhead on cover page
    try:
        final_bytes = _merge_letterhead(content_bytes)
    except Exception:
        final_bytes = content_bytes

    return final_bytes
