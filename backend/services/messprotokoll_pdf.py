"""PDF-Generator fuer Messprotokoll elektrischer Anlagen (nach DIN VDE 0100-600 / DGUV V3)."""
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, black, white


PRIMARY = HexColor("#8b5cf6")
TEXT = HexColor("#111827")
MUTED = HexColor("#6b7280")
BORDER = HexColor("#d1d5db")
LIGHT = HexColor("#f3f4f6")
OK_GREEN = HexColor("#059669")
NOK_RED = HexColor("#dc2626")


def _draw_checkbox(c, x, y, checked=False, size=3.2):
    c.setStrokeColor(TEXT)
    c.setLineWidth(0.4)
    c.rect(x, y, size * mm, size * mm, stroke=1, fill=0)
    if checked:
        c.setLineWidth(0.9)
        c.setStrokeColor(PRIMARY)
        c.line(x + 0.6 * mm, y + 1.6 * mm, x + 1.3 * mm, y + 0.6 * mm)
        c.line(x + 1.3 * mm, y + 0.6 * mm, x + 2.7 * mm, y + 2.6 * mm)
        c.setStrokeColor(TEXT)


def _label(c, x, y, text, size=7, color=MUTED):
    c.setFont("Helvetica", size)
    c.setFillColor(color)
    c.drawString(x, y, text)


def _value(c, x, y, text, size=8, color=TEXT, bold=True):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.setFillColor(color)
    c.drawString(x, y, str(text or "–"))


def _section(c, x, y, width, title):
    """Render a section header bar."""
    c.setFillColor(PRIMARY)
    c.rect(x, y, width, 5.5 * mm, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 2 * mm, y + 1.6 * mm, title)
    c.setFillColor(TEXT)


def generate_messprotokoll_pdf(data: dict) -> bytes:
    """Generiert ein PDF aus den Messprotokoll-Feldern."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    margin = 12 * mm
    right = W - margin
    y = H - margin

    # ── Header ───────────────────────────────────────────────────────────
    c.setFillColor(PRIMARY)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y - 6, "Mess- und Prüfprotokoll")
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawString(margin, y - 5 * mm, "Elektrische Anlage nach DIN VDE 0100-600 / DGUV Vorschrift 3")
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(right, y - 6, f"Nr. {data.get('protokoll_nr', '')}")
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawRightString(right, y - 5 * mm, f"Datum: {data.get('pruef_datum', datetime.now().strftime('%d.%m.%Y'))}")
    c.setFillColor(TEXT)

    # trennlinie
    y -= 9 * mm
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.4)
    c.line(margin, y, right, y)

    # ── Auftragsdaten ────────────────────────────────────────────────────
    y -= 4 * mm
    col1 = margin
    col2 = margin + 90 * mm
    for label, key in [("Auftraggeber", "auftraggeber"), ("Kunden-Nr.", "kunden_nr"),
                        ("Anlage / Objekt", "anlage"), ("Auftrags-Nr.", "auftrags_nr")]:
        _label(c, col1, y, label)
        _value(c, col1, y - 3.5 * mm, data.get(key, ""))
        _label(c, col2, y, "Auftragnehmer" if label == "Auftraggeber" else ("Prüfer" if label == "Anlage / Objekt" else ("Blatt" if label == "Kunden-Nr." else "")))
        if label == "Auftraggeber":
            _value(c, col2, y - 3.5 * mm, data.get("auftragnehmer", "Eventenergie Deutschland GmbH & Co. KG"))
        elif label == "Anlage / Objekt":
            _value(c, col2, y - 3.5 * mm, data.get("pruefer_name", ""))
        elif label == "Kunden-Nr.":
            _value(c, col2, y - 3.5 * mm, f"{data.get('blatt_nr', 1)} / {data.get('blatt_gesamt', 1)}")
        y -= 8 * mm

    # ── Prüfung nach / Prüfart / Netz ────────────────────────────────────
    y -= 1 * mm
    _section(c, margin, y - 5 * mm, right - margin, "Prüfgrundlagen & Netzform")
    y -= 10 * mm

    normen = data.get("normen", {})
    _label(c, margin, y, "Prüfung nach:", size=8, color=TEXT)
    x = margin + 24 * mm
    for key, lbl in [("din_vde_0100_600", "DIN VDE 0100-600"), ("din_vde_0105", "DIN VDE 0105"), ("dguv_v3", "DGUV V3")]:
        _draw_checkbox(c, x, y - 0.5, checked=bool(normen.get(key)))
        _value(c, x + 4.5 * mm, y, lbl, size=8, bold=False)
        x += 38 * mm

    y -= 5 * mm
    pruefart = data.get("pruefart", {})
    _label(c, margin, y, "Prüfart:", size=8, color=TEXT)
    x = margin + 24 * mm
    for key, lbl in [("neuanlage", "Neuanlage"), ("erweiterung", "Erweiterung"), ("aenderung", "Änderung"),
                      ("instandsetzung", "Instandsetzung"), ("wiederholung", "Wiederholung")]:
        _draw_checkbox(c, x, y - 0.5, checked=bool(pruefart.get(key)))
        _value(c, x + 4.5 * mm, y, lbl, size=8, bold=False)
        x += 28 * mm

    y -= 6 * mm
    _label(c, margin, y, "Netz:", size=8, color=TEXT)
    _value(c, margin + 14 * mm, y, f"{data.get('netz_volt', '400')} V / {data.get('netz_hz', '50')} Hz", size=8)
    _label(c, margin + 55 * mm, y, "Netzsystem:", size=8, color=TEXT)
    x = margin + 80 * mm
    netzsystem = data.get("netzsystem", "")
    for opt in ["TN-C", "TN-S", "TN-C-S", "TT", "IT"]:
        _draw_checkbox(c, x, y - 0.5, checked=(netzsystem == opt))
        _value(c, x + 4.5 * mm, y, opt, size=8, bold=False)
        x += 20 * mm

    # ── Besichtigen ──────────────────────────────────────────────────────
    y -= 8 * mm
    _section(c, margin, y - 5 * mm, right - margin, "Besichtigen")
    y -= 10 * mm
    besichtigen = data.get("besichtigen", {})
    punkte_bes = [
        ("betriebsmittel", "Auswahl der Betriebsmittel"),
        ("kennzeichnung_stromkreise", "Kennzeichnung Stromkreise"),
        ("zugaenglichkeit", "Zugänglichkeit der Betriebsmittel"),
        ("trennschaltgeraete", "Trenn- und Schaltgeräte"),
        ("kennzeichnung_n_pe", "Kennzeichnung N- und PE-Leiter"),
        ("brandabschottungen", "Brandabschottungen"),
        ("leiterverbindungen", "Leiterverbindungen"),
        ("gebaeudesystemtechnik", "Gebäudesystemtechnik"),
        ("schutz_ueberwachung", "Schutz- und Überwachungsgeräte"),
        ("hauptpotenzialausgleich", "Hauptpotenzialausgleich"),
        ("kabel_leitungen", "Kabel, Leitungen und Stromschienen"),
        ("zus_oertl_pa", "Zus. örtl. Potenzialausgleich"),
        ("schutz_direkt_beruehren", "Schutz gegen direktes Berühren"),
        ("dokumentation", "Dokumentation / Warnhinweise"),
    ]
    col_w = (right - margin) / 2
    for i, (key, lbl) in enumerate(punkte_bes):
        col = i % 2
        row = i // 2
        x = margin + col * col_w
        yr = y - row * 4.5 * mm
        val = besichtigen.get(key, "")
        _value(c, x, yr, lbl, size=7.5, bold=False)
        _draw_checkbox(c, x + col_w - 22 * mm, yr - 0.3, checked=(val == "iO"))
        _label(c, x + col_w - 17 * mm, yr, "i.O.", size=7, color=OK_GREEN)
        _draw_checkbox(c, x + col_w - 10 * mm, yr - 0.3, checked=(val == "niO"))
        _label(c, x + col_w - 5 * mm, yr, "n.i.O.", size=7, color=NOK_RED)
    y -= (len(punkte_bes) // 2 + 1) * 4.5 * mm

    # ── Erproben ─────────────────────────────────────────────────────────
    y -= 2 * mm
    _section(c, margin, y - 5 * mm, right - margin, "Erproben")
    y -= 10 * mm
    erproben = data.get("erproben", {})
    punkte_erp = [
        ("funktion_anlage", "Funktion der Anlage"),
        ("rechtsdrehfeld", "Rechtsdrehfeld Drehstromsteckdosen"),
        ("schutz_funktion", "Funktion Schutz-/Überwachungseinrichtungen"),
        ("motoren_drehrichtung", "Drehrichtung der Motoren"),
        ("gebaeudesystemtechnik", "Gebäudesystemtechnik"),
    ]
    for i, (key, lbl) in enumerate(punkte_erp):
        col = i % 2
        row = i // 2
        x = margin + col * col_w
        yr = y - row * 4.5 * mm
        val = erproben.get(key, "")
        _value(c, x, yr, lbl, size=7.5, bold=False)
        _draw_checkbox(c, x + col_w - 22 * mm, yr - 0.3, checked=(val == "iO"))
        _label(c, x + col_w - 17 * mm, yr, "i.O.", size=7, color=OK_GREEN)
        _draw_checkbox(c, x + col_w - 10 * mm, yr - 0.3, checked=(val == "niO"))
        _label(c, x + col_w - 5 * mm, yr, "n.i.O.", size=7, color=NOK_RED)
    y -= ((len(punkte_erp) + 1) // 2 + 1) * 4.5 * mm

    # ── Messungen (neue Seite) ───────────────────────────────────────────
    c.showPage()
    y = H - margin
    _section(c, margin, y - 5 * mm, right - margin, "Messungen – Stromkreise")
    y -= 9 * mm
    _label(c, margin, y, f"Stromkreisverteiler-Nr.: {data.get('verteiler_nr', '')}", size=8, color=TEXT)
    y -= 5 * mm

    # Tabellen-Header (ohne R_iso mV – nicht durch DIN VDE 0100-600 gefordert)
    headers = ["Nr.", "Zielbezeichnung", "Kabel", "I_n (A)", "I_k (A)", "Z_S (Ω)",
               "R_iso (MΩ)", "RCD I_n (mA)", "t_a (ms)", "R_PE (Ω)"]
    col_widths = [8, 36, 22, 14, 14, 16, 22, 20, 16, 18]
    xs = [margin]
    for w in col_widths:
        xs.append(xs[-1] + w * mm)

    c.setFillColor(LIGHT)
    c.rect(margin, y - 4.5 * mm, right - margin, 4.5 * mm, stroke=0, fill=1)
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 6.5)
    for i, h in enumerate(headers):
        c.drawString(xs[i] + 1, y - 3 * mm, h)
    y -= 4.5 * mm

    c.setFont("Helvetica", 6.5)
    for i, row in enumerate(data.get("messungen", [])[:20]):
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.2)
        c.line(margin, y - 3.8 * mm, right, y - 3.8 * mm)
        row_vals = [
            str(i + 1),
            str(row.get("ziel", "") or "")[:28],
            str(row.get("kabel", "") or "")[:14],
            str(row.get("in_a", "") or ""),
            str(row.get("ik_a", "") or ""),
            str(row.get("zs_ohm", "") or ""),
            str(row.get("riso_ohne", "") or ""),
            str(row.get("rcd_ma", "") or ""),
            str(row.get("ta_ms", "") or ""),
            str(row.get("rpe_ohm", "") or ""),
        ]
        for j, v in enumerate(row_vals):
            c.drawString(xs[j] + 1, y - 3 * mm, v)
        y -= 4 * mm
    # Tabellen-Rahmen
    c.rect(margin, y, right - margin, (20 * 4 + 4.5) * mm - (H - margin - y - 9 * mm - 5 * mm), stroke=0, fill=0)

    # ── Potenzialausgleich ───────────────────────────────────────────────
    y -= 4 * mm
    _section(c, margin, y - 5 * mm, right - margin, "Durchgängigkeit Potenzialausgleich")
    y -= 10 * mm
    pa = data.get("potenzialausgleich", {})
    pa_items = [
        ("fundamenterder", "Fundamenterder"),
        ("pas_schiene", "Potenzialausgleichsschiene"),
        ("wasser_hauptltg", "Hauptwasserleitung"),
        ("hauptschutzleiter", "Hauptschutzleiter"),
        ("gas", "Gasinnenleitung"),
        ("heizung", "Heizungsanlage"),
        ("klima", "Klimaanlage"),
        ("aufzug", "Aufzugsanlage"),
        ("edv", "EDV-Anlage"),
        ("telefon", "Telefonanlage"),
        ("blitzschutz", "Blitzschutzanlage"),
        ("antenne", "Antennenanlage/BK"),
        ("gebaeude", "Gebäudekonstruktion"),
        ("wasser_zwischenzaehler", "Wasserzwischenzähler"),
    ]
    pa_col_w = (right - margin) / 3
    for i, (key, lbl) in enumerate(pa_items):
        col = i % 3
        row = i // 3
        x = margin + col * pa_col_w
        yr = y - row * 4.5 * mm
        _draw_checkbox(c, x, yr - 0.3, checked=bool(pa.get(key)))
        _value(c, x + 5 * mm, yr, lbl, size=7, bold=False)
    y -= ((len(pa_items) + 2) // 3 + 1) * 4.5 * mm

    _label(c, margin, y, f"Erdungswiderstand R_E = {data.get('erdungswiderstand', '')} Ω", size=8, color=TEXT)

    # ── Messgeräte ───────────────────────────────────────────────────────
    y -= 6 * mm
    _section(c, margin, y - 5 * mm, right - margin, "Verwendete Messgeräte")
    y -= 10 * mm
    for i, mg in enumerate(data.get("messgeraete", [])[:2]):
        _label(c, margin, y, f"Gerät {i + 1}:", size=8, color=TEXT)
        _value(c, margin + 16 * mm, y, f"{mg.get('fabrikat', '')} – {mg.get('typ', '')}", size=8, bold=False)
        y -= 4.5 * mm

    # ── Prüfergebnis ─────────────────────────────────────────────────────
    y -= 2 * mm
    _section(c, margin, y - 5 * mm, right - margin, "Prüfergebnis")
    y -= 10 * mm
    ergebnis = data.get("ergebnis", {})
    _draw_checkbox(c, margin, y - 0.3, checked=bool(ergebnis.get("keine_maengel")))
    _value(c, margin + 5 * mm, y, "keine Mängel festgestellt", size=8, bold=False, color=OK_GREEN if ergebnis.get("keine_maengel") else TEXT)
    _draw_checkbox(c, margin + 70 * mm, y - 0.3, checked=bool(ergebnis.get("maengel")))
    _value(c, margin + 75 * mm, y, "Mängel festgestellt", size=8, bold=False, color=NOK_RED if ergebnis.get("maengel") else TEXT)
    _label(c, margin + 130 * mm, y, "Plakette erteilt:", size=8, color=TEXT)
    _draw_checkbox(c, margin + 155 * mm, y - 0.3, checked=(ergebnis.get("plakette") == "ja"))
    _value(c, margin + 160 * mm, y, "ja", size=8, bold=False)
    _draw_checkbox(c, margin + 167 * mm, y - 0.3, checked=(ergebnis.get("plakette") == "nein"))
    _value(c, margin + 172 * mm, y, "nein", size=8, bold=False)

    y -= 6 * mm
    _label(c, margin, y, "Mängel / Bemerkungen:", size=8, color=TEXT)
    y -= 4 * mm
    c.setFont("Helvetica", 8)
    for line in (ergebnis.get("bemerkungen", "") or "").split("\n")[:5]:
        c.drawString(margin, y, line[:120])
        y -= 3.5 * mm

    y -= 3 * mm
    _label(c, margin, y, f"Nächster Prüftermin: {ergebnis.get('naechster_termin_monat', '')} / {ergebnis.get('naechster_termin_jahr', '')}", size=8, color=TEXT)

    # ── Unterschrift ─────────────────────────────────────────────────────
    y -= 14 * mm
    c.setStrokeColor(BORDER)
    c.line(margin, y, margin + 60 * mm, y)
    c.line(margin + 100 * mm, y, margin + 160 * mm, y)
    _label(c, margin, y - 3 * mm, "Auftraggeber (Ort, Datum, Unterschrift)")
    _label(c, margin + 100 * mm, y - 3 * mm, f"Prüfer: {data.get('pruefer_name', '')} – {data.get('pruef_datum', datetime.now().strftime('%d.%m.%Y'))}")

    c.save()
    buf.seek(0)
    return buf.getvalue()
