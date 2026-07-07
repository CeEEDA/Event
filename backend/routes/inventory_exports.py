"""Inventar-Auswertungen: XLSX (Excel mit Sheets pro Gruppe) und PDF (3 Detaillierungsgrade).

Aufgerufen von routes/inventory.py.
"""
import io
import logging
from datetime import datetime
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage,
    KeepTogether,
)
from reportlab.pdfgen import canvas as pdfcanvas

logger = logging.getLogger(__name__)

FIRMA_NAME = "Eventenergie Deutschland GmbH & Co. KG"
# Logo path resolved relative to THIS file so it works on both Linux (Docker /app)
# and Windows (C:\Eventenergie\backend). Absolute /app/... breaks on Windows.
import os as _pdf_os
_STATIC_DIR = _pdf_os.path.join(_pdf_os.path.dirname(_pdf_os.path.abspath(__file__)), "..", "static")
LOGO_PATH = _pdf_os.path.normpath(_pdf_os.path.join(_STATIC_DIR, "logo.png"))
FUCHSIA = colors.HexColor("#c026d3")
FUCHSIA_LIGHT = colors.HexColor("#fce7f3")
EMERALD = colors.HexColor("#059669")
EMERALD_LIGHT = colors.HexColor("#d1fae5")
GRAY_DARK = colors.HexColor("#374151")
GRAY_LIGHT = colors.HexColor("#f3f4f6")


# Umlaute wandeln (ae/oe/ue/ss). Der User will keine echten Umlaute im PDF
# damit auch bei alten Windows-Fonts nichts an Encoding-Problemen scheitert.
_UMLAUT_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
    "ß": "ss", "\u00A0": " ",
})


def _no_umlaut(v) -> str:
    if v is None:
        return "-"
    return str(v).translate(_UMLAUT_MAP)


def _esc(v) -> str:
    """Escape user-provided text for ReportLab ``Paragraph`` – which interprets
    its content as XML. Ohne diesen Fix crasht ein literales ``&`` (z.B. in
    ``Eventenergie Deutschland GmbH & Co. KG``) den gesamten PDF-Build.
    Zusätzlich werden Umlaute nach ae/oe/ue/ss ersetzt."""
    if v is None:
        return "-"
    s = _no_umlaut(v)
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def _fmt_eur(v) -> str:
    try:
        return f"{float(v or 0):,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def _fmt_monat_jahr(m, j) -> str:
    if not m or not j:
        return "-"
    monate = ["", "Jan", "Feb", "Mrz", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
    try:
        return f"{monate[int(m)]} {int(j)}"
    except Exception:
        return "-"


def _val(item):
    """Liefert den best-passenden Aktivwert (Bilanz oder Markt) fuer die Summenrechnung."""
    b = float(item.get("aktueller_bilanzwert") or 0)
    m = float(item.get("marktschaetzwert") or 0)
    return b if b > 0 else m


def _wertquelle(item) -> str:
    """Kurz: 'Bilanzwert' oder 'Marktschaetzwert' oder 'beide'."""
    b = float(item.get("aktueller_bilanzwert") or 0)
    m = float(item.get("marktschaetzwert") or 0)
    if b > 0 and m > 0:
        return "beide"
    if b > 0:
        return "Bilanz"
    if m > 0:
        return "Markt"
    return "-"


# ═══════════════ XLSX EXPORT ═══════════════════════════════════════
def build_xlsx(items: list, groups_by_id: dict) -> bytes:
    """XLSX mit Deckblatt-Sheet + je 1 Sheet pro Gruppe."""
    wb = Workbook()

    # ─── Sheet 1: Deckblatt / Uebersicht ──────────────────────
    ws0 = wb.active
    ws0.title = "Deckblatt"

    ws0["A1"] = f"Inventar-Auswertung {FIRMA_NAME}"
    ws0["A1"].font = Font(size=16, bold=True, color="C026D3")
    ws0.merge_cells("A1:E1")

    ws0["A2"] = f"Erstellt am: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    ws0["A2"].font = Font(size=10, italic=True, color="6B7280")
    ws0.merge_cells("A2:E2")

    ws0["A4"] = "Zusammenfassung"
    ws0["A4"].font = Font(size=12, bold=True)

    total_items = len(items)
    total_stueck = sum(int(i.get("stueckzahl") or 1) for i in items)
    total_einkauf = sum(float(i.get("einkaufspreis") or 0) * int(i.get("stueckzahl") or 1) for i in items)
    total_bilanz = sum(float(i.get("aktueller_bilanzwert") or 0) * int(i.get("stueckzahl") or 1) for i in items)
    total_markt = sum(float(i.get("marktschaetzwert") or 0) * int(i.get("stueckzahl") or 1) for i in items)
    total_aktiv = sum(_val(i) * int(i.get("stueckzahl") or 1) for i in items)

    ws0["A5"] = "Anzahl Positionen:"
    ws0["B5"] = total_items
    ws0["A6"] = "Anzahl Stueck gesamt:"
    ws0["B6"] = total_stueck
    ws0["A7"] = "Einkaufspreis gesamt:"
    ws0["B7"] = _fmt_eur(total_einkauf)
    ws0["A8"] = "Bilanzwert gesamt:"
    ws0["B8"] = _fmt_eur(total_bilanz)
    ws0["A9"] = "Marktschaetzwert gesamt:"
    ws0["B9"] = _fmt_eur(total_markt)
    ws0["A10"] = "Aktivwert (Bilanz > Markt):"
    ws0["B10"] = _fmt_eur(total_aktiv)
    ws0["A10"].font = Font(bold=True)
    ws0["B10"].font = Font(bold=True, color="C026D3")

    ws0["A12"] = "Pro Gruppe"
    ws0["A12"].font = Font(size=12, bold=True)

    header_row = 13
    ws0.append([]) if False else None  # placeholder
    headers = ["Gruppe", "Positionen", "Einkauf gesamt", "Bilanz gesamt", "Markt gesamt", "Aktivwert"]
    for i, h in enumerate(headers, 1):
        cell = ws0.cell(row=header_row, column=i, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="C026D3")
        cell.alignment = Alignment(horizontal="center")

    from collections import defaultdict
    per_group = defaultdict(lambda: {"count": 0, "einkauf": 0, "bilanz": 0, "markt": 0, "aktiv": 0})
    for it in items:
        gid = it.get("group_id") or "sonstiges"
        stk = int(it.get("stueckzahl") or 1)
        per_group[gid]["count"] += 1
        per_group[gid]["einkauf"] += float(it.get("einkaufspreis") or 0) * stk
        per_group[gid]["bilanz"] += float(it.get("aktueller_bilanzwert") or 0) * stk
        per_group[gid]["markt"] += float(it.get("marktschaetzwert") or 0) * stk
        per_group[gid]["aktiv"] += _val(it) * stk

    r = header_row + 1
    for gid, agg in sorted(per_group.items(), key=lambda kv: groups_by_id.get(kv[0], {}).get("name", kv[0])):
        gname = groups_by_id.get(gid, {}).get("name", gid)
        ws0.cell(row=r, column=1, value=gname)
        ws0.cell(row=r, column=2, value=agg["count"])
        ws0.cell(row=r, column=3, value=_fmt_eur(agg["einkauf"]))
        ws0.cell(row=r, column=4, value=_fmt_eur(agg["bilanz"]))
        ws0.cell(row=r, column=5, value=_fmt_eur(agg["markt"]))
        ws0.cell(row=r, column=6, value=_fmt_eur(agg["aktiv"]))
        ws0.cell(row=r, column=6).font = Font(bold=True, color="C026D3")
        r += 1

    for col in range(1, 7):
        ws0.column_dimensions[get_column_letter(col)].width = 22

    # ─── Sheet 2..N: pro Gruppe ────────────────────────────────
    by_group = defaultdict(list)
    for it in items:
        by_group[it.get("group_id") or "sonstiges"].append(it)

    for gid, group_items in sorted(by_group.items(), key=lambda kv: groups_by_id.get(kv[0], {}).get("name", kv[0])):
        gname = groups_by_id.get(gid, {}).get("name", gid) or "Sonstiges"
        # Sheet-Name: max 31 Zeichen, keine Sonderzeichen
        safe = "".join(c for c in gname if c.isalnum() or c in " -_")[:31] or "Gruppe"
        ws = wb.create_sheet(title=safe)

        ws["A1"] = f"Gruppe: {gname}"
        ws["A1"].font = Font(size=14, bold=True, color="C026D3")
        ws.merge_cells("A1:I1")

        cols = [
            "Bezeichnung", "Anlagenr.", "Besitzer", "Stueckzahl",
            "Einkaufspreis", "Bilanzwert", "Marktschaetzwert",
            "Anschaffung", "Notiz",
        ]
        for i, h in enumerate(cols, 1):
            cell = ws.cell(row=3, column=i, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="7C3AED")
            cell.alignment = Alignment(horizontal="center")

        for idx, it in enumerate(group_items, start=4):
            ws.cell(row=idx, column=1, value=it.get("bezeichnung", ""))
            ws.cell(row=idx, column=2, value=it.get("anlagevermoegensnummer", ""))
            ws.cell(row=idx, column=3, value=it.get("besitzer", ""))
            ws.cell(row=idx, column=4, value=int(it.get("stueckzahl") or 1))
            ws.cell(row=idx, column=5, value=_fmt_eur(it.get("einkaufspreis")))
            ws.cell(row=idx, column=6, value=_fmt_eur(it.get("aktueller_bilanzwert")))
            ws.cell(row=idx, column=7, value=_fmt_eur(it.get("marktschaetzwert")))
            ws.cell(row=idx, column=8, value=_fmt_monat_jahr(it.get("anschaffung_monat"), it.get("anschaffung_jahr")))
            ws.cell(row=idx, column=9, value=it.get("notiz", ""))

        # Summenzeile
        last = len(group_items) + 4
        ws.cell(row=last, column=1, value="SUMME").font = Font(bold=True)
        stk_sum = sum(int(i.get("stueckzahl") or 1) for i in group_items)
        einkauf_sum = sum(float(i.get("einkaufspreis") or 0) * int(i.get("stueckzahl") or 1) for i in group_items)
        bilanz_sum = sum(float(i.get("aktueller_bilanzwert") or 0) * int(i.get("stueckzahl") or 1) for i in group_items)
        markt_sum = sum(float(i.get("marktschaetzwert") or 0) * int(i.get("stueckzahl") or 1) for i in group_items)
        ws.cell(row=last, column=4, value=stk_sum).font = Font(bold=True)
        ws.cell(row=last, column=5, value=_fmt_eur(einkauf_sum)).font = Font(bold=True)
        ws.cell(row=last, column=6, value=_fmt_eur(bilanz_sum)).font = Font(bold=True)
        ws.cell(row=last, column=7, value=_fmt_eur(markt_sum)).font = Font(bold=True)

        widths = [30, 15, 32, 10, 15, 15, 18, 12, 40]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ═══════════════ PDF EXPORT ════════════════════════════════════════
def _pdf_footer(canv, doc):
    canv.saveState()
    canv.setFont("Helvetica", 8)
    canv.setFillColor(colors.grey)
    canv.drawString(2 * cm, 1 * cm, _no_umlaut(f"Inventar-Auswertung  ·  {FIRMA_NAME}"))
    canv.drawRightString(A4[0] - 2 * cm, 1 * cm, f"Seite {doc.page}")
    canv.restoreState()


def _deckblatt(items, groups_by_id, styles, info_text: str = "") -> list:
    """Deckblatt-Elemente fuer alle 3 Detail-Modi.

    ``info_text`` optional – wird zwischen Gesamtsumme und "Werte pro Gruppe"
    eingefuegt (freies Textfeld aus dem Auswertung-Modal).
    """
    import os as _os
    story = []

    # ─── Logo oben zentriert ───────────────────────────────────
    if _os.path.exists(LOGO_PATH):
        try:
            logo = RLImage(LOGO_PATH)
            # Original 460x107 -> Zielbreite 8 cm, Hoehe proportional
            target_w = 8 * cm
            ratio = 107 / 460
            logo.drawWidth = target_w
            logo.drawHeight = target_w * ratio
            logo.hAlign = "CENTER"
            story.append(logo)
            story.append(Spacer(1, 14))
        except Exception as e:
            logger.warning(f"[pdf] Logo konnte nicht eingebettet werden: {e}")

    title_style = ParagraphStyle(
        "Title", parent=styles["Title"], fontSize=22, textColor=FUCHSIA,
        alignment=TA_CENTER, spaceAfter=12, fontName="Helvetica-Bold",
    )
    story.append(Paragraph("Inventar-Auswertung", title_style))

    sub_style = ParagraphStyle(
        "Sub", parent=styles["Normal"], fontSize=13, textColor=GRAY_DARK,
        alignment=TA_CENTER, spaceAfter=6, fontName="Helvetica",
    )
    story.append(Paragraph(_esc(FIRMA_NAME), sub_style))
    story.append(Paragraph(
        f"Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        ParagraphStyle("Date", parent=styles["Normal"], fontSize=10, textColor=GRAY_DARK, alignment=TA_CENTER, spaceAfter=24),
    ))

    # Gesamtsummen
    total_items = len(items)
    total_stueck = sum(int(i.get("stueckzahl") or 1) for i in items)
    total_einkauf = sum(float(i.get("einkaufspreis") or 0) * int(i.get("stueckzahl") or 1) for i in items)
    total_bilanz = sum(float(i.get("aktueller_bilanzwert") or 0) * int(i.get("stueckzahl") or 1) for i in items)
    total_markt = sum(float(i.get("marktschaetzwert") or 0) * int(i.get("stueckzahl") or 1) for i in items)
    total_aktiv = sum(_val(i) * int(i.get("stueckzahl") or 1) for i in items)

    summary_data = [
        ["Positionen", str(total_items)],
        ["Stueck gesamt", str(total_stueck)],
        ["Einkaufspreis (Anschaffung)", _fmt_eur(total_einkauf)],
        ["Bilanzwert", _fmt_eur(total_bilanz)],
        ["Marktschaetzwert", _fmt_eur(total_markt)],
        ["Aktivwert (Bilanz > Markt)", _fmt_eur(total_aktiv)],
    ]
    t = Table(summary_data, colWidths=[7 * cm, 6 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), FUCHSIA_LIGHT),
        ("TEXTCOLOR", (0, 0), (0, -1), GRAY_DARK),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("BACKGROUND", (0, -1), (-1, -1), FUCHSIA),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    # ── Optionales Info-Textfeld (zwischen Gesamtsumme und Werte pro Gruppe) ──
    if info_text and info_text.strip():
        info_style = ParagraphStyle(
            "Info", parent=styles["Normal"], fontSize=10, textColor=GRAY_DARK,
            leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=4, leading=14,
        )
        info_box = Table(
            [[Paragraph(_esc(info_text.strip()).replace("\n", "<br/>"), info_style)]],
            colWidths=[17 * cm],
        )
        info_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),  # sanftes Blau
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#3b82f6")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(info_box)
        story.append(Spacer(1, 14))

    # Pro Gruppe Uebersicht
    story.append(Paragraph("Werte pro Gruppe", ParagraphStyle("H2", parent=styles["Heading2"], textColor=FUCHSIA, fontSize=13, spaceBefore=6, spaceAfter=8)))

    from collections import defaultdict
    per_group = defaultdict(lambda: {"count": 0, "einkauf": 0, "bilanz": 0, "markt": 0, "aktiv": 0})
    for it in items:
        gid = it.get("group_id") or "sonstiges"
        stk = int(it.get("stueckzahl") or 1)
        per_group[gid]["count"] += 1
        per_group[gid]["einkauf"] += float(it.get("einkaufspreis") or 0) * stk
        per_group[gid]["bilanz"] += float(it.get("aktueller_bilanzwert") or 0) * stk
        per_group[gid]["markt"] += float(it.get("marktschaetzwert") or 0) * stk
        per_group[gid]["aktiv"] += _val(it) * stk

    rows = [["Gruppe", "Pos.", "Einkauf", "Bilanz", "Markt", "Aktiv"]]
    for gid, agg in sorted(per_group.items(), key=lambda kv: groups_by_id.get(kv[0], {}).get("name", kv[0])):
        rows.append([
            _no_umlaut(groups_by_id.get(gid, {}).get("name", gid)),
            str(agg["count"]),
            _fmt_eur(agg["einkauf"]),
            _fmt_eur(agg["bilanz"]),
            _fmt_eur(agg["markt"]),
            _fmt_eur(agg["aktiv"]),
        ])
    gt = Table(rows, colWidths=[4 * cm, 1.4 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm])
    gt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), FUCHSIA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRAY_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(gt)

    # ── Marktwert prominent ganz unten auf dem Deckblatt ─────────────
    # Der User hat gewuenscht, dass der Marktschaetzwert der "wichtige Wert"
    # ist und fett hervorgehoben ganz unten auf dem Deckblatt erscheint.
    story.append(Spacer(1, 22))
    markt_box = Table(
        [[
            Paragraph(
                "MARKTSCHAETZWERT GESAMT",
                ParagraphStyle("MktL", parent=styles["Normal"], fontSize=11, textColor=colors.white,
                               fontName="Helvetica-Bold", alignment=TA_LEFT, leading=14),
            ),
            Paragraph(
                _fmt_eur(total_markt),
                ParagraphStyle("MktV", parent=styles["Normal"], fontSize=22, textColor=colors.white,
                               fontName="Helvetica-Bold", alignment=TA_RIGHT, leading=26),
            ),
        ]],
        colWidths=[8 * cm, 9 * cm],
    )
    markt_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), EMERALD),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(markt_box)
    return story


def _decode_image_for_pdf(item_id: str, img_meta: dict, get_object_fn, max_size_mm: float = 60):
    """Laedt ein Bild und liefert ein reportlab-Image-Element (max 60mm breit)."""
    from PIL import Image as PILImage
    try:
        storage_path = img_meta.get("storage_path", "")
        if storage_path.startswith("local://"):
            # local
            import os
            local_rel = storage_path.replace("local://", "", 1).rsplit("/", 1)[-1]
            local_path = f"/app/data/inventory/{item_id}/{local_rel}"
            if not os.path.exists(local_path):
                return None
            data = open(local_path, "rb").read()
        else:
            data, _ct = get_object_fn(storage_path)
        # Skalieren zur Preview
        pil = PILImage.open(io.BytesIO(data))
        pil.thumbnail((800, 800))
        buf = io.BytesIO()
        pil.convert("RGB").save(buf, format="JPEG", quality=80)
        buf.seek(0)
        img = RLImage(buf)
        # Auf max_size_mm skalieren
        ratio = pil.height / max(1, pil.width)
        img.drawWidth = max_size_mm * mm
        img.drawHeight = max_size_mm * mm * ratio
        return img
    except Exception as e:
        logger.warning(f"[pdf] Bild-Decode fehlgeschlagen: {e}")
        return None


def build_pdf(items: list, groups_by_id: dict, mode: str = "smart", get_object_fn=None, info_text: str = "") -> bytes:
    """PDF-Auswertung mit 3 Detaillierungsgraden.
    mode: 'smart' = nur Deckblatt + einfache Tabelle
          'mittel' = zusaetzlich pro Gruppe Deckblatt + je Item eine Seite mit Bild
          'gross' = wie mittel + auch die Dokumente aus der Dokumentenablage referenzieren
    info_text: optionaler Freitext, wird auf dem Deckblatt eingefuegt.
    """
    if mode not in {"smart", "mittel", "gross"}:
        mode = "smart"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=f"Inventar-Auswertung ({mode})",
    )
    styles = getSampleStyleSheet()
    story = []

    # ── Seite 1: Deckblatt ─────────────────────────────────────
    story += _deckblatt(items, groups_by_id, styles, info_text=info_text)

    # ── SMART: einfache Tabelle aller Positionen ──────────────
    if mode == "smart":
        story.append(PageBreak())
        story.append(Paragraph("Alle Inventar-Positionen", ParagraphStyle("H1", parent=styles["Heading1"], textColor=FUCHSIA, fontSize=15, spaceAfter=8)))
        rows = [["Gruppe", "Bezeichnung", "Anlagenr.", "Stk.", "Einkauf", "Bilanz", "Markt"]]
        # sortiert nach Gruppe -> Bezeichnung
        for it in sorted(items, key=lambda x: (groups_by_id.get(x.get("group_id",""), {}).get("name",""), x.get("bezeichnung",""))):
            rows.append([
                _no_umlaut(groups_by_id.get(it.get("group_id",""), {}).get("name", "-")),
                _no_umlaut(it.get("bezeichnung", ""))[:35],
                _no_umlaut(it.get("anlagevermoegensnummer", "")),
                str(it.get("stueckzahl") or 1),
                _fmt_eur(it.get("einkaufspreis")),
                _fmt_eur(it.get("aktueller_bilanzwert")),
                _fmt_eur(it.get("marktschaetzwert")),
            ])
        t = Table(rows, colWidths=[2.8*cm, 4.2*cm, 2.2*cm, 1*cm, 2.4*cm, 2.4*cm, 2.4*cm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), FUCHSIA),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRAY_LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    # ── MITTEL / GROSS: pro Gruppe Zwischen-Deckblatt + Item-Seiten ─
    if mode in {"mittel", "gross"}:
        from collections import defaultdict
        by_group = defaultdict(list)
        for it in items:
            by_group[it.get("group_id") or "sonstiges"].append(it)

        for gid, group_items in sorted(by_group.items(), key=lambda kv: groups_by_id.get(kv[0], {}).get("name", kv[0])):
            gname = groups_by_id.get(gid, {}).get("name", gid) or "Sonstiges"
            # Gruppen-Deckblatt mit Logo
            story.append(PageBreak())
            import os as _os
            if _os.path.exists(LOGO_PATH):
                try:
                    logo = RLImage(LOGO_PATH)
                    target_w = 5 * cm
                    ratio = 107 / 460
                    logo.drawWidth = target_w
                    logo.drawHeight = target_w * ratio
                    logo.hAlign = "CENTER"
                    story.append(logo)
                    story.append(Spacer(1, 8))
                except Exception:
                    pass
            story.append(Paragraph(f"Gruppe: {_esc(gname)}", ParagraphStyle("GT", parent=styles["Title"], fontSize=20, textColor=FUCHSIA, spaceAfter=16)))

            g_stk = sum(int(i.get("stueckzahl") or 1) for i in group_items)
            g_ein = sum(float(i.get("einkaufspreis") or 0) * int(i.get("stueckzahl") or 1) for i in group_items)
            g_bil = sum(float(i.get("aktueller_bilanzwert") or 0) * int(i.get("stueckzahl") or 1) for i in group_items)
            g_mkt = sum(float(i.get("marktschaetzwert") or 0) * int(i.get("stueckzahl") or 1) for i in group_items)
            g_akt = sum(_val(i) * int(i.get("stueckzahl") or 1) for i in group_items)

            s_data = [
                ["Positionen", str(len(group_items))],
                ["Stueck gesamt", str(g_stk)],
                ["Einkauf gesamt", _fmt_eur(g_ein)],
                ["Bilanz gesamt", _fmt_eur(g_bil)],
                ["Markt gesamt", _fmt_eur(g_mkt)],
                ["Aktivwert", _fmt_eur(g_akt)],
            ]
            s_t = Table(s_data, colWidths=[7 * cm, 6 * cm])
            s_t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), FUCHSIA_LIGHT),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BACKGROUND", (0, -1), (-1, -1), FUCHSIA),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ]))
            story.append(s_t)

            # Je Item eine Seite (nur wenn genug fuer eigene Seite)
            for it in sorted(group_items, key=lambda x: x.get("bezeichnung", "")):
                story.append(PageBreak())
                story.append(Paragraph(_esc(it.get("bezeichnung", "-")), ParagraphStyle("IT", parent=styles["Title"], fontSize=16, textColor=FUCHSIA, spaceAfter=12)))

                if it.get("anlagevermoegensnummer"):
                    story.append(Paragraph(f"<b>Anlagevermoegensnummer:</b> {_esc(it['anlagevermoegensnummer'])}", styles["Normal"]))
                story.append(Paragraph(f"<b>Gruppe:</b> {_esc(gname)}", styles["Normal"]))
                story.append(Paragraph(f"<b>Besitzer:</b> {_esc(it.get('besitzer','-'))}", styles["Normal"]))
                story.append(Paragraph(f"<b>Anschaffung:</b> {_esc(_fmt_monat_jahr(it.get('anschaffung_monat'), it.get('anschaffung_jahr')))}", styles["Normal"]))
                story.append(Paragraph(f"<b>Stueckzahl:</b> {_esc(it.get('stueckzahl') or 1)}", styles["Normal"]))
                story.append(Spacer(1, 8))

                stk = int(it.get("stueckzahl") or 1)
                werte = [
                    ["Wert", "pro Stueck", f"x {stk}"],
                    ["Einkaufspreis", _fmt_eur(it.get("einkaufspreis")), _fmt_eur(float(it.get("einkaufspreis") or 0) * stk)],
                    ["Bilanzwert", _fmt_eur(it.get("aktueller_bilanzwert")), _fmt_eur(float(it.get("aktueller_bilanzwert") or 0) * stk)],
                    ["Marktschaetzwert", _fmt_eur(it.get("marktschaetzwert")), _fmt_eur(float(it.get("marktschaetzwert") or 0) * stk)],
                ]
                wt = Table(werte, colWidths=[5.5*cm, 4*cm, 4*cm])
                wt.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), FUCHSIA),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]))
                story.append(wt)
                story.append(Spacer(1, 10))

                # Bild
                imgs = it.get("images") or []
                if imgs and get_object_fn:
                    first = imgs[0]
                    rl_img = _decode_image_for_pdf(it["id"], first, get_object_fn, max_size_mm=90)
                    if rl_img is not None:
                        story.append(rl_img)
                        story.append(Spacer(1, 6))

                if it.get("notiz"):
                    story.append(Paragraph(f"<b>Notiz:</b> {_esc(it['notiz'])}", styles["Normal"]))

                # GROSS: Dokumente-Liste anhaengen
                if mode == "gross":
                    docs = it.get("documents") or []
                    if docs:
                        story.append(Spacer(1, 8))
                        story.append(Paragraph("<b>Angehaengte Dokumente:</b>", styles["Normal"]))
                        for d in docs:
                            size_kb = int((d.get("size", 0) or 0) / 1024)
                            story.append(Paragraph(
                                f"&#8226; {_esc(d.get('filename','?'))} ({_esc(d.get('content_type','-'))}, {size_kb} KB)",
                                ParagraphStyle("Doc", parent=styles["Normal"], leftIndent=12, textColor=GRAY_DARK),
                            ))

    doc.build(story, onFirstPage=_pdf_footer, onLaterPages=_pdf_footer)
    return buf.getvalue()
