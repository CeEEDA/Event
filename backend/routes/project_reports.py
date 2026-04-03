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
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import base64

    # Auth via query param (for direct download links)
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

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2", parent=styles["Heading1"], fontSize=16, spaceAfter=6)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, spaceAfter=4, spaceBefore=10, textColor=colors.HexColor("#a21caf"))
    normal = ParagraphStyle("Normal2", parent=styles["Normal"], fontSize=9, leading=12)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.grey)

    elems = []
    elems.append(Paragraph("Projektbericht", title_style))
    elems.append(Paragraph(f"Nr. {report.get('projektnummer', '')} | Datum: {report.get('projekt_datum', '')}", small))
    elems.append(Spacer(1, 4*mm))

    # Kundendaten
    elems.append(Paragraph("Kundendaten", h2))
    kd = [
        ["Anrede:", report.get("anrede", "")],
        ["Name/Firma:", report.get("kunde_name", "")],
        ["Ansprechpartner:", report.get("kunde_ansprechpartner", "")],
        ["Anschrift:", report.get("kunde_anschrift", "")],
        ["PLZ / Ort:", f"{report.get('kunde_plz', '')} {report.get('kunde_ort', '')}"],
        ["Telefon:", report.get("kunde_telefon", "")],
    ]
    t = Table(kd, colWidths=[35*mm, 140*mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elems.append(t)

    # Mitarbeiter
    ma_list = report.get("mitarbeiter", [])
    if ma_list:
        elems.append(Paragraph("Mitarbeiter", h2))
        ma_data = [["Name", "Rolle", "Typ"]]
        for m in ma_list:
            typ = "Mitarbeiter" if m.get("is_user", True) else "Ext. Personal"
            ma_data.append([m.get("name", ""), m.get("rolle", ""), typ])
        t = Table(ma_data, colWidths=[70*mm, 30*mm, 40*mm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3e8ff")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        elems.append(t)

    # Arbeitsprotokoll
    wl = report.get("work_log", [])
    if wl:
        elems.append(Paragraph("Arbeitsprotokoll", h2))
        for entry in wl:
            elems.append(Paragraph(f"<b>{entry.get('datum', '')}</b>", normal))
            desc = (entry.get("beschreibung", "") or "").replace("\n", "<br/>")
            elems.append(Paragraph(desc, normal))
            stunden = entry.get("stunden", {})
            if stunden and ma_list:
                hrs_data = [["Person", "N", "E", "NO"]]
                for idx_str, vals in stunden.items():
                    idx = int(idx_str) if idx_str.isdigit() else 0
                    name = ma_list[idx]["name"] if idx < len(ma_list) else f"#{idx}"
                    hrs_data.append([name, vals.get("N", 0), vals.get("E", 0), vals.get("NO", 0)])
                t = Table(hrs_data, colWidths=[60*mm, 20*mm, 20*mm, 20*mm])
                t.setStyle(TableStyle([
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f9fafb")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                ]))
                elems.append(t)
            elems.append(Spacer(1, 2*mm))

    # Material
    mat = report.get("material", [])
    if mat:
        elems.append(Paragraph("Material / Artikel", h2))
        mat_data = [["Pos", "Material", "Vorber.", "Verarb.", "Bestell."]]
        for m in mat:
            mat_data.append([m.get("pos", ""), m.get("material", ""), m.get("vorbereitung", ""), m.get("verarbeitet", ""), m.get("bestellung", "")])
        t = Table(mat_data, colWidths=[12*mm, 80*mm, 25*mm, 25*mm, 25*mm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
        ]))
        elems.append(t)

    # Fahrzeuge
    fz = report.get("fahrzeuge", [])
    if fz:
        elems.append(Paragraph("Fahrzeuge", h2))
        fz_data = [["Typ", "KM", "Stunden"]]
        for f in fz:
            fz_data.append([f.get("typ", ""), f.get("km", 0), f.get("stunden", 0)])
        t = Table(fz_data, colWidths=[60*mm, 30*mm, 30*mm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
        ]))
        elems.append(t)

    # Bemerkungen
    bem = report.get("bemerkungen", "")
    if bem:
        elems.append(Paragraph("Bemerkungen", h2))
        elems.append(Paragraph(bem.replace("\n", "<br/>"), normal))

    ueb = report.get("uebernachtung_zeitraum", "")
    if ueb:
        elems.append(Paragraph(f"Uebernachtung: {ueb} ({report.get('uebernachtung_naechte', 0)} Naechte)", small))

    # Signatures
    elems.append(Spacer(1, 6*mm))
    sig_data = []
    for label, key in [("Techniker", "unterschrift_techniker"), ("Kunde", "unterschrift_kunde")]:
        sig = report.get(key)
        if sig and sig.startswith("data:image"):
            try:
                b64 = sig.split(",", 1)[1]
                img_buf = io.BytesIO(base64.b64decode(b64))
                img = RLImage(img_buf, width=50*mm, height=20*mm)
                sig_data.append([f"{label}:", img])
            except Exception:
                sig_data.append([f"{label}:", "(Unterschrift vorhanden)"])
        else:
            sig_data.append([f"{label}:", "(nicht unterschrieben)"])

    if sig_data:
        elems.append(Paragraph("Unterschriften", h2))
        t = Table(sig_data, colWidths=[30*mm, 60*mm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elems.append(t)

    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph(f"Erstellt von: {report.get('created_by', '')} | {report.get('created_at', '')[:16]}", small))

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
