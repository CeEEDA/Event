from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import io

router = APIRouter(prefix="/api/project-reports", tags=["Project Reports"])
security = HTTPBearer()
_db = None
_decode_jwt_token = None


def init_project_report_routes(db, decode_jwt_token):
    global _db, _decode_jwt_token
    _db = db
    _decode_jwt_token = decode_jwt_token


async def _auth_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")
    return user


async def _require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await _auth_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Administratoren")
    return user


# ── Models ──

class WorkLogEntry(BaseModel):
    datum: Optional[str] = ""
    beschreibung: Optional[str] = ""
    stunden: Optional[dict] = {}

class MaterialEntry(BaseModel):
    pos: Optional[int] = 0
    material: Optional[str] = ""
    vorbereitung: Optional[str] = ""
    verarbeitet: Optional[str] = ""
    bestellung: Optional[str] = ""

class EmployeeEntry(BaseModel):
    name: Optional[str] = ""
    rolle: Optional[str] = "T"
    is_user: Optional[bool] = True

class VehicleEntry(BaseModel):
    typ: Optional[str] = ""
    km: Optional[float] = 0
    stunden: Optional[float] = 0

class ProjectReportCreate(BaseModel):
    order_pk: Optional[str] = None
    order_name: Optional[str] = None
    anrede: Optional[str] = "Firma"
    kunde_name: Optional[str] = ""
    kunde_anschrift: Optional[str] = ""
    kunde_plz: Optional[str] = ""
    kunde_ort: Optional[str] = ""
    kunde_telefon: Optional[str] = ""
    kunde_ansprechpartner: Optional[str] = ""
    projektnummer: Optional[str] = ""
    projekt_datum: Optional[str] = ""
    kunde_nicht_anwesend: Optional[bool] = False
    mitarbeiter: Optional[List[EmployeeEntry]] = []
    work_log: Optional[List[WorkLogEntry]] = []
    material: Optional[List[MaterialEntry]] = []
    fahrzeuge: Optional[List[VehicleEntry]] = []
    bemerkungen: Optional[str] = ""
    uebernachtung_zeitraum: Optional[str] = ""
    uebernachtung_naechte: Optional[int] = 0
    unterschrift_techniker: Optional[str] = None
    unterschrift_kunde: Optional[str] = None

class ProjectReportUpdate(BaseModel):
    anrede: Optional[str] = None
    kunde_name: Optional[str] = None
    kunde_anschrift: Optional[str] = None
    kunde_plz: Optional[str] = None
    kunde_ort: Optional[str] = None
    kunde_telefon: Optional[str] = None
    kunde_ansprechpartner: Optional[str] = None
    projektnummer: Optional[str] = None
    projekt_datum: Optional[str] = None
    kunde_nicht_anwesend: Optional[bool] = None
    mitarbeiter: Optional[List[EmployeeEntry]] = None
    work_log: Optional[List[WorkLogEntry]] = None
    material: Optional[List[MaterialEntry]] = None
    fahrzeuge: Optional[List[VehicleEntry]] = None
    bemerkungen: Optional[str] = None
    uebernachtung_zeitraum: Optional[str] = None
    uebernachtung_naechte: Optional[int] = None
    unterschrift_techniker: Optional[str] = None
    unterschrift_kunde: Optional[str] = None

class WorkTemplateCreate(BaseModel):
    bezeichnung: str
    text: str
    kategorie: Optional[str] = ""

class WorkTemplateUpdate(BaseModel):
    bezeichnung: Optional[str] = None
    text: Optional[str] = None
    kategorie: Optional[str] = None
    sort_order: Optional[int] = None


# ── Endpoints (static paths FIRST, then dynamic /{id}) ──

@router.post("")
async def create_project_report(data: ProjectReportCreate, user: dict = Depends(_auth_user)):
    report_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "id": report_id,
        "order_pk": data.order_pk,
        "order_name": data.order_name or "",
        "anrede": data.anrede or "Firma",
        "kunde_name": data.kunde_name or "",
        "kunde_anschrift": data.kunde_anschrift or "",
        "kunde_plz": data.kunde_plz or "",
        "kunde_ort": data.kunde_ort or "",
        "kunde_telefon": data.kunde_telefon or "",
        "kunde_ansprechpartner": data.kunde_ansprechpartner or "",
        "projektnummer": data.projektnummer or "",
        "projekt_datum": data.projekt_datum or now[:10],
        "kunde_nicht_anwesend": data.kunde_nicht_anwesend or False,
        "mitarbeiter": [m.dict() for m in (data.mitarbeiter or [])],
        "work_log": [w.dict() for w in (data.work_log or [])],
        "material": [m.dict() for m in (data.material or [])],
        "fahrzeuge": [f.dict() for f in (data.fahrzeuge or [])],
        "bemerkungen": data.bemerkungen or "",
        "uebernachtung_zeitraum": data.uebernachtung_zeitraum or "",
        "uebernachtung_naechte": data.uebernachtung_naechte or 0,
        "unterschrift_techniker": data.unterschrift_techniker,
        "unterschrift_kunde": data.unterschrift_kunde,
        "created_by": user.get("name", user.get("email", "")),
        "created_by_id": user.get("id"),
        "created_at": now,
        "updated_at": now,
    }

    await _db.project_reports.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/by-order/{order_pk}")
async def get_reports_by_order(order_pk: str, user: dict = Depends(_auth_user)):
    reports = await _db.project_reports.find(
        {"order_pk": order_pk}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return reports


# ── Work Templates (Textbausteine) ──

@router.get("/work-templates")
async def list_work_templates(user: dict = Depends(_auth_user)):
    templates = await _db.work_templates.find({}, {"_id": 0}).sort("sort_order", 1).to_list(200)
    return templates


@router.post("/work-templates")
async def create_work_template(data: WorkTemplateCreate, user: dict = Depends(_require_admin)):
    tid = str(uuid.uuid4())
    count = await _db.work_templates.count_documents({})
    doc = {
        "id": tid,
        "bezeichnung": data.bezeichnung,
        "text": data.text,
        "kategorie": data.kategorie or "",
        "sort_order": count,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.work_templates.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/work-templates/{template_id}")
async def update_work_template(template_id: str, data: WorkTemplateUpdate, user: dict = Depends(_require_admin)):
    update = {}
    for field, value in data.dict(exclude_unset=True).items():
        if value is not None:
            update[field] = value
    if not update:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")
    await _db.work_templates.update_one({"id": template_id}, {"$set": update})
    updated = await _db.work_templates.find_one({"id": template_id}, {"_id": 0})
    if not updated:
        raise HTTPException(status_code=404, detail="Textbaustein nicht gefunden")
    return updated


@router.delete("/work-templates/{template_id}")
async def delete_work_template(template_id: str, user: dict = Depends(_require_admin)):
    result = await _db.work_templates.delete_one({"id": template_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Textbaustein nicht gefunden")
    return {"message": "Geloescht"}


# ── Single Report CRUD (dynamic /{report_id} LAST) ──

@router.get("/{report_id}/pdf")
async def get_report_pdf(report_id: str, token: str = Query(None)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    import base64, os

    if not token:
        raise HTTPException(status_code=401, detail="Token fehlt")
    try:
        payload = _decode_jwt_token(token)
        user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401)
    except Exception:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")

    report = await _db.project_reports.find_one({"id": report_id}, {"_id": 0})
    if not report:
        raise HTTPException(status_code=404, detail="Nicht gefunden")

    # Colors
    PURPLE = colors.HexColor("#7c3aed")
    LIGHT_PURPLE = colors.HexColor("#f5f3ff")
    BORDER = colors.HexColor("#d1d5db")
    HEADER_BG = colors.HexColor("#ede9fe")
    LIGHT_GRAY = colors.HexColor("#f9fafb")
    DARK = colors.HexColor("#1f2937")

    # Styles
    s_title = ParagraphStyle("T", fontSize=18, fontName="Helvetica-Bold", textColor=PURPLE, alignment=TA_LEFT, spaceAfter=2)
    s_subtitle = ParagraphStyle("ST", fontSize=8, textColor=colors.grey, alignment=TA_LEFT)
    s_h2 = ParagraphStyle("H2", fontSize=10, fontName="Helvetica-Bold", textColor=PURPLE, spaceBefore=8, spaceAfter=3)
    s_label = ParagraphStyle("L", fontSize=7.5, textColor=colors.HexColor("#6b7280"), fontName="Helvetica")
    s_value = ParagraphStyle("V", fontSize=8.5, textColor=DARK, fontName="Helvetica")
    s_small = ParagraphStyle("SM", fontSize=7, textColor=colors.grey)
    s_cell = ParagraphStyle("C", fontSize=7.5, textColor=DARK, leading=9)
    s_cell_bold = ParagraphStyle("CB", fontSize=7.5, textColor=DARK, fontName="Helvetica-Bold", leading=9)
    s_footer = ParagraphStyle("F", fontSize=7, textColor=colors.grey, alignment=TA_CENTER)
    s_confirm = ParagraphStyle("CF", fontSize=6.5, textColor=DARK, leading=8)

    buf = io.BytesIO()
    pw, ph = A4
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12*mm, rightMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)
    W = pw - 24*mm
    elems = []

    ma_list = report.get("mitarbeiter", [])

    # ── HEADER: Logo + Title ──
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "logo.png")
    header_data = [[Paragraph("Projektbericht", s_title), ""]]
    if os.path.exists(logo_path):
        logo = RLImage(logo_path, width=45*mm, height=10.5*mm)
        header_data = [[Paragraph("Projektbericht", s_title), logo]]
    ht = Table(header_data, colWidths=[W - 50*mm, 50*mm])
    ht.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    elems.append(ht)
    elems.append(Spacer(1, 1*mm))

    # ── CUSTOMER + PROJECT INFO (2-column) ──
    left_data = [
        [Paragraph("<b>Auftrags-/Liefer-/Reparaturanschrift:</b>", s_value), ""],
        [Paragraph("Firma:", s_label), Paragraph(report.get("kunde_name", ""), s_value)],
        [Paragraph("Anschrift:", s_label), Paragraph(report.get("kunde_anschrift", ""), s_value)],
        [Paragraph("PLZ / Ort:", s_label), Paragraph(f"{report.get('kunde_plz', '')} {report.get('kunde_ort', '')}", s_value)],
        [Paragraph("Telefon:", s_label), Paragraph(report.get("kunde_telefon", ""), s_value)],
        [Paragraph("Ansprechpartner:", s_label), Paragraph(report.get("kunde_ansprechpartner", ""), s_value)],
    ]
    lt = Table(left_data, colWidths=[25*mm, 60*mm])
    lt.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("LINEBELOW", (1, 1), (1, -1), 0.5, BORDER),
    ]))

    # Right: Mitarbeiter + Projekt-Nr
    ma_rows = []
    for i, m in enumerate(ma_list):
        rolle = m.get("rolle", "")
        name = m.get("name", "")
        typ_label = "" if m.get("is_user", True) else " (ext.)"
        ma_rows.append([Paragraph(f"{i+1}.", s_label), Paragraph(f"{name}{typ_label}", s_value), Paragraph(rolle, s_label)])
    if not ma_rows:
        ma_rows.append(["", Paragraph("—", s_value), ""])
    ma_header = [[Paragraph("Nr.", s_label), Paragraph("<b>Mitarbeiter:</b>", s_label), Paragraph("Rolle", s_label)]]
    ma_all = ma_header + ma_rows
    rt = Table(ma_all, colWidths=[8*mm, 55*mm, 12*mm])
    rt.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, PURPLE),
    ]))

    # Combine left + right
    info_table = Table([[lt, rt]], colWidths=[W * 0.48, W * 0.52])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elems.append(info_table)
    elems.append(Spacer(1, 1*mm))

    # Project number line
    pn_data = [[
        Paragraph("Projektnummer:", s_label),
        Paragraph(f"<b>{report.get('projektnummer', '')}</b>", s_value),
        Paragraph("am:", s_label),
        Paragraph(report.get("projekt_datum", ""), s_value),
        Paragraph("PL=Projektleiter ME=Meister T=Techniker H=Helfer", s_small),
    ]]
    pnt = Table(pn_data, colWidths=[28*mm, 25*mm, 8*mm, 22*mm, W - 83*mm])
    pnt.setStyle(TableStyle([
        ("LINEBELOW", (1, 0), (1, 0), 0.5, BORDER),
        ("LINEBELOW", (3, 0), (3, 0), 0.5, BORDER),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elems.append(pnt)
    elems.append(Spacer(1, 3*mm))

    # ── ARBEITSPROTOKOLL TABLE ──
    elems.append(Paragraph("Arbeitsprotokoll", s_h2))

    num_ma = len(ma_list) if ma_list else 1
    # Build header: Datum | Arbeitsbeschreibung | Lohn: N/E/NO per employee
    hdr1 = [Paragraph("<b>Datum</b>", s_cell_bold), Paragraph("<b>Arbeitsbeschreibung</b>", s_cell_bold)]
    hdr2 = ["", ""]
    for i, m in enumerate(ma_list or [{"name": "MA 1"}]):
        short = m.get("name", f"MA {i+1}")
        if len(short) > 12:
            short = short[:12] + "."
        hdr1.append(Paragraph(f"<b>{short}</b>", ParagraphStyle("MH", fontSize=6.5, fontName="Helvetica-Bold", alignment=TA_CENTER, textColor=PURPLE)))
        hdr1.append("")
        hdr1.append("")
        hdr2.append(Paragraph("N", ParagraphStyle("SH", fontSize=6, alignment=TA_CENTER, textColor=colors.grey)))
        hdr2.append(Paragraph("E", ParagraphStyle("SH", fontSize=6, alignment=TA_CENTER, textColor=grey if (grey := colors.grey) else colors.grey)))
        hdr2.append(Paragraph("NO", ParagraphStyle("SH", fontSize=6, alignment=TA_CENTER, textColor=colors.grey)))

    date_w = 18*mm
    desc_w = max(W - date_w - num_ma * 3 * 10*mm, 30*mm)
    hr_w = (W - date_w - desc_w) / max(num_ma * 3, 1)
    col_widths = [date_w, desc_w] + [hr_w] * (num_ma * 3)

    rows = [hdr1, hdr2]
    wl = report.get("work_log", [])
    for entry in wl:
        row = [
            Paragraph(entry.get("datum", ""), s_cell),
            Paragraph((entry.get("beschreibung", "") or "").replace("\n", "<br/>"), s_cell),
        ]
        stunden = entry.get("stunden", {})
        for emp_idx in range(num_ma):
            emp_hrs = stunden.get(str(emp_idx), {})
            for t in ["N", "E", "NO"]:
                val = emp_hrs.get(t, "")
                if val and val != 0 and val != "0":
                    row.append(Paragraph(str(val), ParagraphStyle("HV", fontSize=7, alignment=TA_CENTER, textColor=DARK)))
                else:
                    row.append("")
        rows.append(row)

    # Add empty rows to fill the table if < 8
    for _ in range(max(0, 8 - len(wl))):
        rows.append(["", ""] + [""] * (num_ma * 3))

    wt = Table(rows, colWidths=col_widths, repeatRows=2)

    # Merge employee name headers (span 3 cols each)
    merge_cmds = []
    for i in range(num_ma):
        col_start = 2 + i * 3
        merge_cmds.append(("SPAN", (col_start, 0), (col_start + 2, 0)))

    wt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("BACKGROUND", (0, 0), (-1, 1), HEADER_BG),
        ("BACKGROUND", (0, 2), (0, -1), LIGHT_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("ALIGN", (2, 2), (-1, -1), "CENTER"),
        ("ROWHEIGHTS", (0, 2), (-1, -1), 14*mm),
    ] + merge_cmds))
    elems.append(wt)
    elems.append(Spacer(1, 2*mm))

    # ── BEMERKUNGEN ──
    bem = report.get("bemerkungen", "")
    elems.append(Paragraph("Projektbesprechung, besondere Vorkommnisse, Behinderungen, Verluste, Beschaedigungen:", s_label))
    bem_data = [[Paragraph(bem.replace("\n", "<br/>") if bem else " ", s_cell)]]
    bt = Table(bem_data, colWidths=[W])
    bt.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("MINROWHEIGHT", (0, 0), (-1, -1), 15*mm),
    ]))
    elems.append(bt)
    elems.append(Spacer(1, 3*mm))

    # ── MATERIAL TABLE (only if data exists) ──
    mat = report.get("material", [])
    mat_filled = [m for m in mat if m.get("material")]
    if mat_filled:
        elems.append(Paragraph("Material / Artikel", s_h2))
        mat_hdr = [
        Paragraph("<b>Pos.</b>", s_cell_bold),
        Paragraph("<b>Material, Artikel</b>", s_cell_bold),
        Paragraph("<b>Vorbereitung</b>", s_cell_bold),
        Paragraph("<b>Verarbeitet</b>", s_cell_bold),
        Paragraph("<b>Bestellung</b>", s_cell_bold),
    ]
        mat_rows = [mat_hdr]
        for m in mat_filled:
            mat_rows.append([
                Paragraph(str(m.get("pos", "")), s_cell),
                Paragraph(m.get("material", ""), s_cell),
                Paragraph(str(m.get("vorbereitung", "")), s_cell),
                Paragraph(str(m.get("verarbeitet", "")), s_cell),
                Paragraph(str(m.get("bestellung", "")), s_cell),
            ])
        mt = Table(mat_rows, colWidths=[12*mm, W - 12*mm - 75*mm, 25*mm, 25*mm, 25*mm])
        mt.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ]))
        elems.append(mt)
        elems.append(Spacer(1, 3*mm))

    # ── FAHRZEUGE (only if data exists) ──
    fz = report.get("fahrzeuge", [])
    fz_filled = [f for f in fz if f.get("typ")]
    if fz_filled:
        elems.append(Paragraph("Fahrzeuge / Geraete", s_h2))
        fz_hdr = [
        Paragraph("<b>Typ</b>", s_cell_bold),
        Paragraph("<b>KM einf. Strecke</b>", s_cell_bold),
        Paragraph("<b>Stunden</b>", s_cell_bold),
    ]
        fz_rows = [fz_hdr]
        for f in fz_filled:
            fz_rows.append([
                Paragraph(f.get("typ", ""), s_cell),
                Paragraph(str(f.get("km", "")), s_cell),
                Paragraph(str(f.get("stunden", "")), s_cell),
            ])
        ft = Table(fz_rows, colWidths=[W * 0.5, W * 0.25, W * 0.25])
        ft.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ]))
        elems.append(ft)
        elems.append(Spacer(1, 3*mm))

    # ── UEBERNACHTUNG ──
    ueb = report.get("uebernachtung_zeitraum", "")
    naechte = report.get("uebernachtung_naechte", 0)
    if ueb or naechte:
        ub_data = [[
            Paragraph("Uebernachtung:", s_label),
            Paragraph(ueb, s_value),
            Paragraph("Naechte:", s_label),
            Paragraph(str(naechte), s_value),
        ]]
        ubt = Table(ub_data, colWidths=[22*mm, W * 0.4, 15*mm, 20*mm])
        ubt.setStyle(TableStyle([
            ("LINEBELOW", (1, 0), (1, 0), 0.5, BORDER),
            ("LINEBELOW", (3, 0), (3, 0), 0.5, BORDER),
        ]))
        elems.append(ubt)
        elems.append(Spacer(1, 3*mm))

    # ── HINWEIS (AW explanation) ──
    aw_data = [[
        Paragraph("Hinweis:", s_label),
        Paragraph("1 AW = 10 Min | 6 AW = 1 Std. | 0,25 = 1/4 Std. | 1,0 = 1 Std.", s_small),
    ]]
    awt = Table(aw_data, colWidths=[15*mm, W - 15*mm])
    elems.append(awt)
    elems.append(Spacer(1, 4*mm))

    # ── SIGNATURES ──
    sig_left_content = [Paragraph("Hiermit bestaetige ich die ordnungsgemaesse Ausfuehrung der Arbeiten und die Korrektheit der gemachten Angaben.", s_confirm)]
    sig_right_content = [Paragraph("Hiermit bestaetige ich die maengelfreie Ausfuehrung der Arbeiten und die Korrektheit der gemachten Angaben.", s_confirm)]

    for label, key, target in [("Techniker", "unterschrift_techniker", sig_left_content), ("Kunde", "unterschrift_kunde", sig_right_content)]:
        sig = report.get(key)
        if sig and sig.startswith("data:image"):
            try:
                b64 = sig.split(",", 1)[1]
                img_buf = io.BytesIO(base64.b64decode(b64))
                target.append(Spacer(1, 2*mm))
                target.append(RLImage(img_buf, width=45*mm, height=18*mm))
            except Exception:
                target.append(Paragraph("(Unterschrift vorhanden)", s_small))
        else:
            target.append(Spacer(1, 15*mm))

    sig_left_content.append(Paragraph("_" * 40, s_small))
    sig_left_content.append(Paragraph("Datum, Techniker", s_label))
    sig_right_content.append(Paragraph("_" * 40, s_small))
    sig_right_content.append(Paragraph("Datum, Unterschrift Kunde / Bauherr / Bauleiter", s_label))

    sig_left_table = Table([[c] for c in sig_left_content], colWidths=[W * 0.47])
    sig_right_table = Table([[c] for c in sig_right_content], colWidths=[W * 0.47])

    sig_combined = Table([[sig_left_table, sig_right_table]], colWidths=[W * 0.5, W * 0.5])
    sig_combined.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    elems.append(sig_combined)

    # Footer
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph(f"Erstellt von: {report.get('created_by', '')} | {report.get('created_at', '')[:16]} | EVENTENERGIE DEUTSCHLAND | 0800 POWER24", s_footer))

    doc.build(elems)
    buf.seek(0)
    filename = f"Projektbericht_{report.get('projektnummer', report_id[:8])}_{report.get('projekt_datum', '')}.pdf"
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{report_id}")
async def get_report(report_id: str, user: dict = Depends(_auth_user)):
    report = await _db.project_reports.find_one({"id": report_id}, {"_id": 0})
    if not report:
        raise HTTPException(status_code=404, detail="Projektbericht nicht gefunden")
    return report


@router.put("/{report_id}")
async def update_report(report_id: str, data: ProjectReportUpdate, user: dict = Depends(_auth_user)):
    report = await _db.project_reports.find_one({"id": report_id}, {"_id": 0})
    if not report:
        raise HTTPException(status_code=404, detail="Projektbericht nicht gefunden")

    # Lock: once customer has signed, no more edits
    if report.get("unterschrift_kunde"):
        raise HTTPException(status_code=403, detail="Bericht ist gesperrt - Kunde hat bereits unterschrieben")

    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field, value in data.dict(exclude_unset=True).items():
        if value is not None:
            if field in ("mitarbeiter", "work_log", "material", "fahrzeuge"):
                update[field] = [item if isinstance(item, dict) else item.dict() for item in value]
            else:
                update[field] = value

    await _db.project_reports.update_one({"id": report_id}, {"$set": update})
    updated = await _db.project_reports.find_one({"id": report_id}, {"_id": 0})
    return updated


@router.delete("/{report_id}")
async def delete_report(report_id: str, user: dict = Depends(_auth_user)):
    result = await _db.project_reports.delete_one({"id": report_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Projektbericht nicht gefunden")
    return {"message": "Geloescht"}
