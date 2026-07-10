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

    Umlaute bleiben erhalten (Helvetica rendert ae/oe/ue/aeoeue nativ).
    Nur XML-Sonderzeichen werden ersetzt.
    """
    if v is None:
        return "-"
    s = str(v)
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
    canv.drawString(2 * cm, 1 * cm, f"Inventar-Auswertung  ·  {FIRMA_NAME}")
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
        ["Stück gesamt", str(total_stueck)],
        ["Einkaufspreis (Anschaffung)", _fmt_eur(total_einkauf)],
        ["Bilanzwert", _fmt_eur(total_bilanz)],
        ["Marktschätzwert", _fmt_eur(total_markt)],
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
            groups_by_id.get(gid, {}).get("name", gid),
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
                "MARKTSCHÄTZWERT GESAMT",
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


def _load_document_bytes(item_id: str, doc_meta: dict, get_object_fn):
    """Laedt ein Dokument aus der Inventar-Ablage. Liefert (bytes, content_type) oder (None, None)."""
    try:
        storage_path = doc_meta.get("storage_path", "") or ""
        content_type = (doc_meta.get("content_type") or "").lower()
        if storage_path.startswith("local://"):
            import os
            local_rel = storage_path.replace("local://", "", 1).rsplit("/", 1)[-1]
            local_path = f"/app/data/inventory/{item_id}/{local_rel}"
            if not os.path.exists(local_path):
                return None, None
            with open(local_path, "rb") as fh:
                return fh.read(), content_type
        if not get_object_fn:
            return None, None
        data, ct = get_object_fn(storage_path)
        return data, (content_type or (ct or "").lower())
    except Exception as e:
        logger.warning(f"[pdf] Doc-Load fehlgeschlagen fuer item={item_id}: {e}")
        return None, None


def _build_image_attachment_page(bezeichnung: str, filename: str, img_bytes: bytes, styles) -> bytes:
    """Baut eine kleine Ein-Seiten-PDF, die ein Bild-Dokument als vollformatige Seite darstellt."""
    from PIL import Image as PILImage
    buf = io.BytesIO()
    d = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    story = [
        Paragraph(f"Anhang: {_esc(filename)}", ParagraphStyle("AT", parent=styles["Title"], fontSize=13, textColor=FUCHSIA, spaceAfter=8)),
        Paragraph(f"zu: {_esc(bezeichnung)}", ParagraphStyle("AS", parent=styles["Normal"], fontSize=10, textColor=GRAY_DARK, spaceAfter=12)),
    ]
    try:
        pil = PILImage.open(io.BytesIO(img_bytes))
        pil.thumbnail((1800, 1800))
        img_buf = io.BytesIO()
        pil.convert("RGB").save(img_buf, format="JPEG", quality=85)
        img_buf.seek(0)
        rli = RLImage(img_buf)
        # Auf max ~16cm Breite skalieren, Aspektverhaeltnis erhalten
        max_w_mm = 160
        ratio = pil.height / max(1, pil.width)
        rli.drawWidth = max_w_mm * mm
        rli.drawHeight = max_w_mm * mm * ratio
        rli.hAlign = "CENTER"
        story.append(rli)
    except Exception as e:
        logger.warning(f"[pdf] Anhang-Bild konnte nicht dargestellt werden: {e}")
        story.append(Paragraph(f"(Bild konnte nicht dargestellt werden: {_esc(str(e))})", styles["Normal"]))
    d.build(story)
    return buf.getvalue()


def _build_separator_page(bezeichnung: str, filename: str, styles, note: str = "") -> bytes:
    """Baut eine Trenner-Seite die ankuendigt, dass jetzt ein PDF-Anhang folgt."""
    buf = io.BytesIO()
    d = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=6 * cm, bottomMargin=2 * cm)
    story = [
        Paragraph("Anhang", ParagraphStyle("AH1", parent=styles["Title"], fontSize=24, textColor=FUCHSIA, alignment=TA_CENTER, spaceAfter=20)),
        Paragraph(_esc(bezeichnung), ParagraphStyle("AH2", parent=styles["Normal"], fontSize=14, textColor=GRAY_DARK, alignment=TA_CENTER, spaceAfter=10)),
        Paragraph(_esc(filename), ParagraphStyle("AH3", parent=styles["Normal"], fontSize=12, textColor=GRAY_DARK, alignment=TA_CENTER, spaceAfter=20)),
    ]
    if note:
        story.append(Paragraph(_esc(note), ParagraphStyle("ANot", parent=styles["Normal"], fontSize=10, textColor=GRAY_DARK, alignment=TA_CENTER)))
    d.build(story)
    return buf.getvalue()


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
    attachments_pending = []  # [(item, docs)] - fuer Merge nach doc.build im gross-Modus

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
                groups_by_id.get(it.get("group_id",""), {}).get("name", "-"),
                (it.get("bezeichnung", "") or "")[:35],
                it.get("anlagevermoegensnummer", ""),
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
                ["Stück gesamt", str(g_stk)],
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
                    story.append(Paragraph(f"<b>Anlagevermögensnummer:</b> {_esc(it['anlagevermoegensnummer'])}", styles["Normal"]))
                story.append(Paragraph(f"<b>Gruppe:</b> {_esc(gname)}", styles["Normal"]))
                story.append(Paragraph(f"<b>Besitzer:</b> {_esc(it.get('besitzer','-'))}", styles["Normal"]))
                story.append(Paragraph(f"<b>Anschaffung:</b> {_esc(_fmt_monat_jahr(it.get('anschaffung_monat'), it.get('anschaffung_jahr')))}", styles["Normal"]))
                story.append(Paragraph(f"<b>Stückzahl:</b> {_esc(it.get('stueckzahl') or 1)}", styles["Normal"]))
                story.append(Spacer(1, 8))

                stk = int(it.get("stueckzahl") or 1)
                werte = [
                    ["Wert", "pro Stück", f"x {stk}"],
                    ["Einkaufspreis", _fmt_eur(it.get("einkaufspreis")), _fmt_eur(float(it.get("einkaufspreis") or 0) * stk)],
                    ["Bilanzwert", _fmt_eur(it.get("aktueller_bilanzwert")), _fmt_eur(float(it.get("aktueller_bilanzwert") or 0) * stk)],
                    ["Marktschätzwert", _fmt_eur(it.get("marktschaetzwert")), _fmt_eur(float(it.get("marktschaetzwert") or 0) * stk)],
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

                # Bilder – ALLE Fotos werden ins PDF eingebettet.
                # 1 Bild -> gross (90mm), 2-4 -> 2er-Grid (je ~85mm), 5+ -> 3er-Grid (je ~55mm)
                imgs = it.get("images") or []
                if imgs and get_object_fn:
                    if len(imgs) == 1:
                        rl_img = _decode_image_for_pdf(it["id"], imgs[0], get_object_fn, max_size_mm=90)
                        if rl_img is not None:
                            story.append(rl_img)
                            story.append(Spacer(1, 6))
                    else:
                        cols = 2 if len(imgs) <= 4 else 3
                        cell_mm = 85 if cols == 2 else 55
                        cell_w = cell_mm * mm
                        rendered = []
                        for m in imgs:
                            r = _decode_image_for_pdf(it["id"], m, get_object_fn, max_size_mm=cell_mm)
                            if r is not None:
                                rendered.append(r)
                        # In Zeilen von `cols` gruppieren
                        rows_grid = []
                        for i in range(0, len(rendered), cols):
                            row = rendered[i:i + cols]
                            # letzte Zeile ggf. mit Leerzellen auffuellen
                            while len(row) < cols:
                                row.append("")
                            rows_grid.append(row)
                        if rows_grid:
                            grid = Table(rows_grid, colWidths=[cell_w] * cols)
                            grid.setStyle(TableStyle([
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                                ("TOPPADDING", (0, 0), (-1, -1), 3),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                            ]))
                            story.append(grid)
                            story.append(Spacer(1, 6))

                if it.get("notiz"):
                    story.append(Paragraph(f"<b>Notiz:</b> {_esc(it['notiz'])}", styles["Normal"]))

                # GROSS: Dokumente-Liste anhaengen (die Dateien selbst werden nach dem Build gemerged)
                if mode == "gross":
                    docs = it.get("documents") or []
                    if docs:
                        story.append(Spacer(1, 8))
                        story.append(Paragraph("<b>Angehängte Dokumente (siehe Anhang):</b>", styles["Normal"]))
                        for d in docs:
                            size_kb = int((d.get("size", 0) or 0) / 1024)
                            story.append(Paragraph(
                                f"&#8226; {_esc(d.get('filename','?'))} ({_esc(d.get('content_type','-'))}, {size_kb} KB)",
                                ParagraphStyle("Doc", parent=styles["Normal"], leftIndent=12, textColor=GRAY_DARK),
                            ))
                        # Merker fuer den Merge-Schritt: Item mit Dokumenten
                        attachments_pending.append((it, docs))

    doc.build(story, onFirstPage=_pdf_footer, onLaterPages=_pdf_footer)
    main_pdf_bytes = buf.getvalue()

    # ── Anhaenge einbetten (nur GROSS) ─────────────────────────────
    if mode == "gross" and attachments_pending:
        try:
            from pypdf import PdfWriter, PdfReader
            writer = PdfWriter()
            # Haupt-PDF laden
            writer.append(fileobj=io.BytesIO(main_pdf_bytes))

            for it, docs in attachments_pending:
                bezeichnung = _no_umlaut(it.get("bezeichnung", "-"))
                for d in docs:
                    filename = _no_umlaut(d.get("filename", "Dokument"))
                    ctype = (d.get("content_type") or "").lower()
                    data, effective_ct = _load_document_bytes(it["id"], d, get_object_fn)
                    if not data:
                        logger.warning(f"[pdf] Anhang '{filename}' konnte nicht geladen werden (item={it.get('id')})")
                        continue
                    used_ct = (effective_ct or ctype or "").lower()

                    # PDF direkt anhaengen
                    if used_ct == "application/pdf" or filename.lower().endswith(".pdf"):
                        try:
                            # Trenner-Seite vor jedem PDF
                            sep = _build_separator_page(bezeichnung, filename, styles)
                            writer.append(fileobj=io.BytesIO(sep))
                            reader = PdfReader(io.BytesIO(data))
                            writer.append(fileobj=io.BytesIO(data))
                            _ = reader.pages  # noqa: F841 - sanity read
                        except Exception as e:
                            logger.warning(f"[pdf] PDF-Anhang '{filename}' konnte nicht gemerged werden: {e}")
                            # Fallback: nur die Trenner-Seite als Hinweis
                            try:
                                sep = _build_separator_page(bezeichnung, filename, styles, note="(Datei konnte nicht eingebettet werden)")
                                writer.append(fileobj=io.BytesIO(sep))
                            except Exception:
                                pass
                    # Bild-Dokument: als Seite darstellen
                    elif used_ct.startswith("image/") or any(filename.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
                        try:
                            img_page = _build_image_attachment_page(bezeichnung, filename, data, styles)
                            writer.append(fileobj=io.BytesIO(img_page))
                        except Exception as e:
                            logger.warning(f"[pdf] Bild-Anhang '{filename}' konnte nicht gerendert werden: {e}")
                    else:
                        # Sonstige Formate (docx, xlsx, txt...) koennen wir nicht direkt einbetten.
                        # Wir fuegen eine Trenner-Seite mit Hinweis ein.
                        try:
                            sep = _build_separator_page(
                                bezeichnung,
                                filename,
                                styles,
                                note=f"(Dieses Dateiformat kann nicht direkt eingebettet werden: {used_ct or 'unbekannt'})",
                            )
                            writer.append(fileobj=io.BytesIO(sep))
                        except Exception:
                            pass

            out = io.BytesIO()
            writer.write(out)
            writer.close()
            return out.getvalue()
        except Exception as e:
            logger.error(f"[pdf] Anhang-Merge fehlgeschlagen, gebe Haupt-PDF ohne Anhaenge zurueck: {e}")
            return main_pdf_bytes

    return main_pdf_bytes
