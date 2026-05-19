"""
Reisekosten / Travel Expense Module
- Verpflegungsmehraufwand nach §9 Abs. 4a EStG (Inland-Pauschalen 2026: 28€ voll, 14€ teil)
- Kürzung gestellter Mahlzeiten: Frühstück -20%, Mittag -40%, Abend -40% der vollen Tagespauschale
- KM-Pauschale Privat-Kfz: 0,30 €/km
- Ausland: BMF-Tagessätze 2026 (Auswahl der wichtigsten Länder, sonst Default Inland)
- PDF-Reisekostenabrechnung pro Reise + Excel-Monatsexport für Steuerbüro
"""
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Body, Depends
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, date as date_cls
from calendar import monthrange
import uuid
import base64
import io
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/employee/travel-expenses", tags=["travel-expenses"])

db = None
decode_jwt_token = None


def init_travel_expense_routes(_db, _decode_jwt_token):
    global db, decode_jwt_token
    db = _db
    decode_jwt_token = _decode_jwt_token


# ────── BMF 2026 Tagessätze (EUR) ──────
# (voller Tag bei 24h Abwesenheit, An-/Abreisetag bei >8h Abwesenheit)
COUNTRY_RATES_2026: Dict[str, Dict[str, Any]] = {
    "DE": {"name": "Deutschland",   "full": 28.0,  "partial": 14.0},
    "AT": {"name": "Österreich",    "full": 43.0,  "partial": 29.0},
    "CH": {"name": "Schweiz",       "full": 66.0,  "partial": 44.0},
    "NL": {"name": "Niederlande",   "full": 49.0,  "partial": 33.0},
    "BE": {"name": "Belgien",       "full": 48.0,  "partial": 32.0},
    "LU": {"name": "Luxemburg",     "full": 47.0,  "partial": 32.0},
    "FR": {"name": "Frankreich",    "full": 60.0,  "partial": 40.0},
    "IT": {"name": "Italien",       "full": 50.0,  "partial": 34.0},
    "ES": {"name": "Spanien",       "full": 42.0,  "partial": 28.0},
    "PT": {"name": "Portugal",      "full": 33.0,  "partial": 22.0},
    "PL": {"name": "Polen",         "full": 33.0,  "partial": 22.0},
    "CZ": {"name": "Tschechien",    "full": 41.0,  "partial": 28.0},
    "DK": {"name": "Dänemark",      "full": 75.0,  "partial": 50.0},
    "SE": {"name": "Schweden",      "full": 56.0,  "partial": 38.0},
    "NO": {"name": "Norwegen",      "full": 80.0,  "partial": 53.0},
    "GB": {"name": "Großbritannien","full": 66.0,  "partial": 44.0},
    "IE": {"name": "Irland",        "full": 58.0,  "partial": 39.0},
    "US": {"name": "USA (Standard)","full": 62.0,  "partial": 41.0},
    "CA": {"name": "Kanada",        "full": 57.0,  "partial": 38.0},
    "TR": {"name": "Türkei",        "full": 35.0,  "partial": 23.0},
    "HU": {"name": "Ungarn",        "full": 37.0,  "partial": 25.0},
    "SK": {"name": "Slowakei",      "full": 39.0,  "partial": 26.0},
    "SI": {"name": "Slowenien",     "full": 38.0,  "partial": 25.0},
    "HR": {"name": "Kroatien",      "full": 38.0,  "partial": 25.0},
}

KM_RATE_PRIVATE_CAR = 0.30  # EUR/km nach §9 Abs. 1 Nr. 4a S. 2 EStG

# Kürzungssätze gestellte Mahlzeit (% der vollen Tagespauschale, hier DE = 28€ → 5,60 / 11,20 / 11,20)
MEAL_DEDUCTION_PCT = {"breakfast": 0.20, "lunch": 0.40, "dinner": 0.40}


# ────── Pydantic Models ──────

class TripCreate(BaseModel):
    trip_purpose: str
    country_code: str = "DE"
    departure_at: str  # ISO datetime
    arrival_at: str    # ISO datetime
    km_private: float = 0.0
    breakfasts_provided: int = 0  # gesamte Reise
    lunches_provided: int = 0
    dinners_provided: int = 0
    accommodation_cost: float = 0.0
    other_expenses: float = 0.0
    other_expenses_note: str = ""
    notes: str = ""


# ────── Helpers ──────

async def _get_user(token: str):
    payload = decode_jwt_token(token)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1, "apps": 1})
    if not user:
        raise HTTPException(status_code=401, detail="Ungültiger Token")
    return user


def _has_verwaltung(caller: dict) -> bool:
    if caller.get("role") == "admin":
        return True
    if caller.get("role") == "mitarbeiter":
        modules = (caller.get("apps") or {}).get("modules") or {}
        return modules.get("verwaltung") is not False
    return False


def _parse_iso(dt_str: str) -> datetime:
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ungültiges Datum: {dt_str} ({e})")


def calculate_per_diem(trip: dict) -> dict:
    """Calc Verpflegungsmehraufwand + KM-Pauschale + Summen nach §9 EStG.
    Returns dict mit allen berechneten Werten."""
    country = trip.get("country_code", "DE").upper()
    rates = COUNTRY_RATES_2026.get(country, COUNTRY_RATES_2026["DE"])
    full_rate = float(rates["full"])
    partial_rate = float(rates["partial"])

    dep = _parse_iso(trip["departure_at"])
    arr = _parse_iso(trip["arrival_at"])
    if arr <= dep:
        raise HTTPException(status_code=400, detail="Reiseende muss nach Reisebeginn liegen")

    total_seconds = (arr - dep).total_seconds()
    total_hours = total_seconds / 3600

    dep_day = dep.date()
    arr_day = arr.date()
    full_days = 0
    partial_days = 0

    if dep_day == arr_day:
        # Eintagesreise (keine Übernachtung)
        if total_hours > 8:
            partial_days = 1
            applied_rate_partial = partial_rate
        else:
            applied_rate_partial = 0.0
        applied_rate_full = 0.0
    else:
        # Mehrtagesreise: An- und Abreisetag jeweils partial, dazwischen full
        days_total = (arr_day - dep_day).days
        partial_days = 2  # An- und Abreisetag
        full_days = max(days_total - 1, 0)
        applied_rate_partial = partial_rate
        applied_rate_full = full_rate

    per_diem_gross = round(full_days * applied_rate_full + partial_days * applied_rate_partial, 2)

    # Kürzung für gestellte Mahlzeiten (immer vom VOLLEN Tagessatz, auch an Teiltagen)
    b = int(trip.get("breakfasts_provided") or 0)
    l_ = int(trip.get("lunches_provided") or 0)
    d = int(trip.get("dinners_provided") or 0)
    meal_deduction = round(
        b * full_rate * MEAL_DEDUCTION_PCT["breakfast"]
        + l_ * full_rate * MEAL_DEDUCTION_PCT["lunch"]
        + d * full_rate * MEAL_DEDUCTION_PCT["dinner"],
        2,
    )
    # Pauschale darf nicht negativ werden
    per_diem_net = max(round(per_diem_gross - meal_deduction, 2), 0.0)

    km = float(trip.get("km_private") or 0)
    km_eur = round(km * KM_RATE_PRIVATE_CAR, 2)
    accommodation_eur = round(float(trip.get("accommodation_cost") or 0), 2)
    other_eur = round(float(trip.get("other_expenses") or 0), 2)

    total_eur = round(per_diem_net + km_eur + accommodation_eur + other_eur, 2)

    return {
        "country_code": country,
        "country_name": rates["name"],
        "full_rate": full_rate,
        "partial_rate": partial_rate,
        "full_days": full_days,
        "partial_days": partial_days,
        "total_hours": round(total_hours, 2),
        "per_diem_gross": per_diem_gross,
        "meal_deduction": meal_deduction,
        "per_diem_net": per_diem_net,
        "km": km,
        "km_rate": KM_RATE_PRIVATE_CAR,
        "km_eur": km_eur,
        "accommodation_eur": accommodation_eur,
        "other_eur": other_eur,
        "total_eur": total_eur,
    }


def _month_key(iso_dt: str) -> str:
    """YYYY-MM aus ISO-Datum (departure_at)."""
    try:
        return iso_dt[:7]
    except Exception:
        return ""


# ────── Endpoints: Country List ──────

@router.get("/countries")
async def list_countries(token: str = Query(...)):
    """Liste der unterstützten Länder mit Tagessätzen."""
    await _get_user(token)
    items = [{"code": k, **v} for k, v in COUNTRY_RATES_2026.items()]
    items.sort(key=lambda x: (0 if x["code"] == "DE" else 1, x["name"]))
    return {"countries": items, "km_rate": KM_RATE_PRIVATE_CAR, "meal_deduction_pct": MEAL_DEDUCTION_PCT}


# ────── Endpoints: Preview Calculation (no save) ──────

@router.post("/preview")
async def preview_calculation(trip: TripCreate, token: str = Query(...)):
    """Live-Vorschau während Eingabe – ohne Speichern."""
    await _get_user(token)
    return calculate_per_diem(trip.dict())


# ────── Endpoints: Create (Employee Self-Service) ──────

@router.post("/")
async def create_trip(
    token: str = Query(...),
    trip_purpose: str = Form(...),
    country_code: str = Form("DE"),
    departure_at: str = Form(...),
    arrival_at: str = Form(...),
    km_private: float = Form(0.0),
    breakfasts_provided: int = Form(0),
    lunches_provided: int = Form(0),
    dinners_provided: int = Form(0),
    accommodation_cost: float = Form(0.0),
    other_expenses: float = Form(0.0),
    other_expenses_note: str = Form(""),
    notes: str = Form(""),
    receipts: List[UploadFile] = File(default=[]),
):
    """Mitarbeiter reicht neue Reise ein. Belege als Multi-Part-Upload."""
    user = await _get_user(token)
    if user["role"] not in ("admin", "mitarbeiter"):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    trip_data = {
        "trip_purpose": trip_purpose.strip(),
        "country_code": country_code.upper(),
        "departure_at": departure_at,
        "arrival_at": arrival_at,
        "km_private": km_private,
        "breakfasts_provided": breakfasts_provided,
        "lunches_provided": lunches_provided,
        "dinners_provided": dinners_provided,
        "accommodation_cost": accommodation_cost,
        "other_expenses": other_expenses,
        "other_expenses_note": other_expenses_note,
        "notes": notes,
    }
    if not trip_data["trip_purpose"]:
        raise HTTPException(status_code=400, detail="Reisezweck ist erforderlich")

    computed = calculate_per_diem(trip_data)

    # Belege speichern (max 10 MB pro Datei, max 6 Belege)
    stored_receipts = []
    for r in (receipts or [])[:6]:
        content = await r.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"Beleg {r.filename} zu groß (>10MB)")
        stored_receipts.append({
            "id": str(uuid.uuid4()),
            "filename": r.filename,
            "content_type": r.content_type or "application/octet-stream",
            "size": len(content),
            "data_b64": base64.b64encode(content).decode("ascii"),
        })

    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_name": user.get("name") or user.get("email", ""),
        **trip_data,
        "month": _month_key(departure_at),
        "computed": computed,
        "receipts": stored_receipts,
        "status": "submitted",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_at": None,
        "approved_by_id": None,
        "approved_by_name": None,
        "rejection_reason": None,
    }
    await db.travel_expenses.insert_one(doc)
    doc.pop("_id", None)
    # Reduzierte Antwort (ohne base64) damit Frontend nicht zugemüllt wird
    doc_out = {**doc, "receipts": [{k: v for k, v in r.items() if k != "data_b64"} for r in stored_receipts]}
    return doc_out


# ────── Endpoints: List ──────

@router.get("/mine")
async def list_my_trips(token: str = Query(...), year: Optional[int] = Query(None)):
    """Mitarbeiter sieht eigene Reisen."""
    user = await _get_user(token)
    q = {"user_id": user["id"]}
    if year:
        q["month"] = {"$regex": f"^{year}-"}
    docs = await db.travel_expenses.find(q, {"_id": 0}).sort("departure_at", -1).to_list(500)
    # Belege ohne base64 ausliefern
    for d in docs:
        d["receipts"] = [{k: v for k, v in r.items() if k != "data_b64"} for r in (d.get("receipts") or [])]
    return docs


@router.get("/user/{user_id}")
async def list_user_trips(user_id: str, token: str = Query(...), month: Optional[str] = Query(None)):
    """Admin/Verwaltung sieht Reisen eines Mitarbeiters (optional pro Monat)."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller) and caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    q = {"user_id": user_id}
    if month:
        q["month"] = month
    docs = await db.travel_expenses.find(q, {"_id": 0}).sort("departure_at", -1).to_list(500)
    for d in docs:
        d["receipts"] = [{k: v for k, v in r.items() if k != "data_b64"} for r in (d.get("receipts") or [])]
    return docs


# ────── Endpoints: Approve / Reject ──────

@router.patch("/{expense_id}/approve")
async def approve_trip(expense_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Verwaltung")
    result = await db.travel_expenses.update_one(
        {"id": expense_id},
        {"$set": {
            "status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_by_id": caller["id"],
            "approved_by_name": caller.get("name") or caller.get("email", ""),
            "rejection_reason": None,
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Reise nicht gefunden")
    return {"ok": True}


@router.patch("/{expense_id}/reject")
async def reject_trip(expense_id: str, token: str = Query(...), data: dict = Body(default={})):
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Nur Verwaltung")
    reason = (data.get("reason") or "").strip()
    result = await db.travel_expenses.update_one(
        {"id": expense_id},
        {"$set": {
            "status": "rejected",
            "approved_at": None,
            "approved_by_id": caller["id"],
            "approved_by_name": caller.get("name") or caller.get("email", ""),
            "rejection_reason": reason or "Ohne Angabe",
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Reise nicht gefunden")
    return {"ok": True}


# ────── Endpoints: Delete ──────

@router.delete("/{expense_id}")
async def delete_trip(expense_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    doc = await db.travel_expenses.find_one({"id": expense_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Reise nicht gefunden")
    # Mitarbeiter darf nur eigene und nur SUBMITTED löschen; Verwaltung darf alles
    if not _has_verwaltung(caller):
        if doc["user_id"] != caller["id"] or doc.get("status") != "submitted":
            raise HTTPException(status_code=403, detail="Genehmigte Reisen können nur von der Verwaltung gelöscht werden")
    await db.travel_expenses.delete_one({"id": expense_id})
    return {"ok": True}


# ────── Endpoints: Receipt Download ──────

@router.get("/{expense_id}/receipt/{receipt_id}")
async def download_receipt(expense_id: str, receipt_id: str, token: str = Query(...)):
    caller = await _get_user(token)
    doc = await db.travel_expenses.find_one({"id": expense_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Reise nicht gefunden")
    if not _has_verwaltung(caller) and doc["user_id"] != caller["id"]:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    for r in (doc.get("receipts") or []):
        if r.get("id") == receipt_id:
            data = base64.b64decode(r["data_b64"])
            return Response(
                content=data,
                media_type=r.get("content_type") or "application/octet-stream",
                headers={"Content-Disposition": f'attachment; filename="{r.get("filename","beleg")}"'},
            )
    raise HTTPException(status_code=404, detail="Beleg nicht gefunden")


# ────── Endpoints: Monthly Summary (Payroll-Integration) ──────

@router.get("/summary/{user_id}")
async def monthly_summary(user_id: str, month: str = Query(...), token: str = Query(...)):
    """Monatssumme – wird in Lohnabrechnung integriert.
    Nur GENEHMIGTE Reisen zählen."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller) and caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    docs = await db.travel_expenses.find(
        {"user_id": user_id, "month": month, "status": "approved"}, {"_id": 0}
    ).to_list(500)
    per_diem_total = sum(d.get("computed", {}).get("per_diem_net", 0) for d in docs)
    km_total_eur = sum(d.get("computed", {}).get("km_eur", 0) for d in docs)
    km_total = sum(d.get("computed", {}).get("km", 0) for d in docs)
    accommodation_total = sum(d.get("computed", {}).get("accommodation_eur", 0) for d in docs)
    other_total = sum(d.get("computed", {}).get("other_eur", 0) for d in docs)
    grand_total = round(per_diem_total + km_total_eur + accommodation_total + other_total, 2)
    return {
        "month": month,
        "user_id": user_id,
        "trip_count": len(docs),
        "per_diem_total": round(per_diem_total, 2),
        "km_total": round(km_total, 2),
        "km_total_eur": round(km_total_eur, 2),
        "accommodation_total": round(accommodation_total, 2),
        "other_total": round(other_total, 2),
        "grand_total": grand_total,
        "trips": [
            {
                "id": d["id"],
                "trip_purpose": d.get("trip_purpose"),
                "country_name": d.get("computed", {}).get("country_name", ""),
                "departure_at": d.get("departure_at"),
                "arrival_at": d.get("arrival_at"),
                "computed": d.get("computed", {}),
            }
            for d in docs
        ],
    }


# ────── PDF Export ──────

@router.get("/{expense_id}/pdf")
async def export_pdf(expense_id: str, token: str = Query(...)):
    """PDF Reisekostenabrechnung pro Reise (inkl. Belegen als Anhang-Liste)."""
    caller = await _get_user(token)
    doc = await db.travel_expenses.find_one({"id": expense_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Reise nicht gefunden")
    if not _has_verwaltung(caller) and doc["user_id"] != caller["id"]:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, textColor=colors.HexColor("#6b21a8"), spaceAfter=2)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=12)
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#555"))

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    story = []

    c = doc.get("computed", {})
    dep_dt = _parse_iso(doc["departure_at"])
    arr_dt = _parse_iso(doc["arrival_at"])

    story.append(Paragraph("Reisekostenabrechnung", h1))
    story.append(Paragraph(f"<b>{doc.get('user_name','')}</b> &nbsp;|&nbsp; {doc.get('trip_purpose','')}", body))
    story.append(Spacer(1, 4))
    status_lbl = {"submitted": "Eingereicht", "approved": "Genehmigt", "rejected": "Abgelehnt"}.get(doc.get("status",""), doc.get("status",""))
    story.append(Paragraph(f"Status: <b>{status_lbl}</b> &nbsp;|&nbsp; Reise-ID: {doc['id'][:8]}", small))
    story.append(Spacer(1, 8))

    # Reisedaten
    story.append(Paragraph("Reisedaten", h2))
    trip_table = [
        ["Land", f"{c.get('country_name','')} ({c.get('country_code','')})"],
        ["Reisebeginn", dep_dt.strftime("%d.%m.%Y %H:%M")],
        ["Reiseende",   arr_dt.strftime("%d.%m.%Y %H:%M")],
        ["Dauer", f"{c.get('total_hours',0):.1f} Stunden"],
        ["Gefahrene km (Privat-Kfz)", f"{c.get('km',0):.1f} km"],
    ]
    t = Table(trip_table, colWidths=[60*mm, 110*mm])
    t.setStyle(TableStyle([
        ("FONTSIZE",(0,0),(-1,-1),9),
        ("TEXTCOLOR",(0,0),(0,-1), colors.HexColor("#666")),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("TOPPADDING",(0,0),(-1,-1),3),
        ("LINEBELOW",(0,0),(-1,-1),0.3,colors.HexColor("#eee")),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # Verpflegungsmehraufwand
    story.append(Paragraph("Verpflegungsmehraufwand (§9 Abs. 4a EStG)", h2))
    vma_rows = [
        ["Volle Tage (24h)", f"{c.get('full_days',0)} × {c.get('full_rate',0):.2f} €",
         f"{c.get('full_days',0)*c.get('full_rate',0):.2f} €"],
        ["An-/Abreise-/Teiltage (>8h)", f"{c.get('partial_days',0)} × {c.get('partial_rate',0):.2f} €",
         f"{c.get('partial_days',0)*c.get('partial_rate',0):.2f} €"],
        ["Pauschale brutto", "", f"{c.get('per_diem_gross',0):.2f} €"],
    ]
    b = int(doc.get("breakfasts_provided") or 0)
    l_ = int(doc.get("lunches_provided") or 0)
    d = int(doc.get("dinners_provided") or 0)
    if b or l_ or d:
        vma_rows.append(["Kürzung gestellte Mahlzeiten",
                         f"F:{b}×20% / M:{l_}×40% / A:{d}×40%",
                         f"− {c.get('meal_deduction',0):.2f} €"])
    vma_rows.append(["Verpflegungspauschale netto", "", f"{c.get('per_diem_net',0):.2f} €"])

    t = Table(vma_rows, colWidths=[80*mm, 55*mm, 35*mm])
    t.setStyle(TableStyle([
        ("FONTSIZE",(0,0),(-1,-1),9),
        ("ALIGN",(2,0),(2,-1),"RIGHT"),
        ("TEXTCOLOR",(0,0),(0,-1), colors.HexColor("#555")),
        ("LINEABOVE",(0,-1),(-1,-1),0.5,colors.HexColor("#999")),
        ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#fef3c7")),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("TOPPADDING",(0,0),(-1,-1),3),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # Übrige Kosten
    story.append(Paragraph("Übrige erstattungsfähige Kosten", h2))
    other_rows = [
        ["KM-Pauschale", f"{c.get('km',0):.1f} km × {c.get('km_rate',0):.2f} €", f"{c.get('km_eur',0):.2f} €"],
        ["Übernachtungskosten (Beleg)", "", f"{c.get('accommodation_eur',0):.2f} €"],
        ["Sonstige Kosten" + (f" ({doc.get('other_expenses_note','')})" if doc.get('other_expenses_note') else ""),
         "", f"{c.get('other_eur',0):.2f} €"],
    ]
    t = Table(other_rows, colWidths=[80*mm, 55*mm, 35*mm])
    t.setStyle(TableStyle([
        ("FONTSIZE",(0,0),(-1,-1),9),
        ("ALIGN",(2,0),(2,-1),"RIGHT"),
        ("TEXTCOLOR",(0,0),(0,-1), colors.HexColor("#555")),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("TOPPADDING",(0,0),(-1,-1),3),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # Gesamtsumme
    total_t = Table(
        [["GESAMTSUMME (steuerfrei erstattbar)", f"{c.get('total_eur',0):.2f} €"]],
        colWidths=[135*mm, 35*mm],
    )
    total_t.setStyle(TableStyle([
        ("FONTSIZE",(0,0),(-1,-1),12),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold"),
        ("ALIGN",(1,0),(1,0),"RIGHT"),
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#10b981")),
        ("TEXTCOLOR",(0,0),(-1,-1),colors.white),
        ("BOTTOMPADDING",(0,0),(-1,-1),8),
        ("TOPPADDING",(0,0),(-1,-1),8),
    ]))
    story.append(total_t)
    story.append(Spacer(1, 10))

    if doc.get("notes"):
        story.append(Paragraph("Notizen", h2))
        story.append(Paragraph(doc["notes"].replace("\n","<br/>"), body))
        story.append(Spacer(1, 8))

    # Belege-Liste
    if doc.get("receipts"):
        story.append(Paragraph("Beigefügte Belege", h2))
        for r in doc["receipts"]:
            size_kb = round(int(r.get("size",0))/1024)
            story.append(Paragraph(f"• {r.get('filename','')} ({size_kb} KB)", small))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f"Erstellt am {datetime.now().strftime('%d.%m.%Y %H:%M')} – "
        f"Berechnung nach §9 EStG (Inlandspauschalen 2026: 28€/14€) und §9 Abs. 1 Nr. 4a EStG (KM-Pauschale 0,30€/km).",
        small,
    ))

    pdf.build(story)
    pdf_bytes = buf.getvalue()
    fname = f"reisekosten_{doc.get('user_name','').replace(' ','_')}_{dep_dt.strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ────── Excel Export – Monatsauswertung pro Mitarbeiter ──────

@router.get("/summary/{user_id}/xlsx")
async def export_summary_xlsx(user_id: str, month: str = Query(...), token: str = Query(...)):
    """Excel-Monatsauswertung für Steuerbüro."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller) and caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    user = await db.users.find_one({"id": user_id}, {"_id": 0, "name": 1, "email": 1})
    uname = (user or {}).get("name") or (user or {}).get("email") or user_id

    docs = await db.travel_expenses.find(
        {"user_id": user_id, "month": month, "status": "approved"}, {"_id": 0}
    ).sort("departure_at", 1).to_list(500)

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = f"Reisekosten {month}"

    bold = Font(bold=True)
    head_fill = PatternFill("solid", fgColor="6b21a8")
    head_font = Font(bold=True, color="FFFFFF")
    sum_fill = PatternFill("solid", fgColor="d1fae5")
    thin = Border(left=Side(style="thin", color="cccccc"),
                  right=Side(style="thin", color="cccccc"),
                  top=Side(style="thin", color="cccccc"),
                  bottom=Side(style="thin", color="cccccc"))

    ws["A1"] = f"Reisekostenabrechnung {month}"
    ws["A1"].font = Font(bold=True, size=14, color="6b21a8")
    ws["A2"] = f"Mitarbeiter: {uname}"
    ws["A2"].font = bold
    ws["A3"] = f"Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    ws["A3"].font = Font(italic=True, color="666666")

    headers = ["Datum von", "Datum bis", "Zweck", "Land", "Volle Tage", "Teil Tage",
               "VMA brutto €", "Mahlz.-Kürzung €", "VMA netto €",
               "km", "KM-Pauschale €", "Übernachtung €", "Sonstige €", "Gesamt €"]
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=5, column=i, value=h)
        cell.fill = head_fill
        cell.font = head_font
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border = thin
    ws.row_dimensions[5].height = 30

    row = 6
    totals = {"vma_n": 0.0, "km": 0.0, "km_eur": 0.0, "acc": 0.0, "other": 0.0, "total": 0.0}
    for d in docs:
        c = d.get("computed", {})
        dep = _parse_iso(d["departure_at"]).strftime("%d.%m.%Y %H:%M")
        arr = _parse_iso(d["arrival_at"]).strftime("%d.%m.%Y %H:%M")
        vals = [
            dep, arr, d.get("trip_purpose",""),
            c.get("country_name",""), c.get("full_days",0), c.get("partial_days",0),
            c.get("per_diem_gross",0), c.get("meal_deduction",0), c.get("per_diem_net",0),
            c.get("km",0), c.get("km_eur",0),
            c.get("accommodation_eur",0), c.get("other_eur",0), c.get("total_eur",0),
        ]
        for i, v in enumerate(vals, 1):
            cell = ws.cell(row=row, column=i, value=v)
            cell.border = thin
            if isinstance(v, (int, float)) and i >= 5:
                cell.number_format = "#,##0.00" if i >= 7 and i != 10 else "#,##0"
        totals["vma_n"] += c.get("per_diem_net", 0)
        totals["km"] += c.get("km", 0)
        totals["km_eur"] += c.get("km_eur", 0)
        totals["acc"] += c.get("accommodation_eur", 0)
        totals["other"] += c.get("other_eur", 0)
        totals["total"] += c.get("total_eur", 0)
        row += 1

    # Total row
    sum_row = row + 1
    ws.cell(row=sum_row, column=1, value="SUMME").font = bold
    for col, val in [(9, totals["vma_n"]), (10, totals["km"]), (11, totals["km_eur"]),
                     (12, totals["acc"]), (13, totals["other"]), (14, totals["total"])]:
        cell = ws.cell(row=sum_row, column=col, value=round(val, 2))
        cell.font = bold
        cell.fill = sum_fill
        cell.number_format = "#,##0.00"
        cell.border = thin
    ws.cell(row=sum_row, column=1).fill = sum_fill
    for col in range(2, 15):
        ws.cell(row=sum_row, column=col).fill = sum_fill
        ws.cell(row=sum_row, column=col).border = thin

    # Column widths
    widths = [16, 16, 32, 18, 9, 9, 12, 14, 12, 9, 14, 14, 12, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64+i) if i <= 26 else "A"+chr(64+i-26)].width = w

    # Steuerliche Anmerkung
    info_row = sum_row + 3
    ws.cell(row=info_row, column=1, value="Steuerliche Hinweise:").font = bold
    ws.cell(row=info_row+1, column=1,
            value="• Verpflegungsmehraufwand netto + KM-Pauschale sind nach §3 Nr.13/16 EStG steuer- u. sozialabgabenfrei.")
    ws.cell(row=info_row+2, column=1, value="• Übernachtungskosten gegen Beleg = steuerfreie Reisekosten.")
    ws.cell(row=info_row+3, column=1, value="• Grundlage: §9 Abs. 4a EStG (Pauschalen 2026) + §9 Abs. 1 Nr. 4a EStG (KM 0,30€).")
    for r_off in range(0, 4):
        ws.cell(row=info_row+r_off, column=1).font = Font(italic=True, color="555555", bold=(r_off==0))

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    fname = f"reisekosten_{uname.replace(' ','_')}_{month}.xlsx"
    return StreamingResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
