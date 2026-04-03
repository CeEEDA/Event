from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid

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


# ── Models ──

class WorkLogEntry(BaseModel):
    datum: Optional[str] = ""
    beschreibung: Optional[str] = ""
    stunden: Optional[dict] = {}  # {"1": {"N": 0, "E": 0, "NO": 0}, "2": {...}}

class MaterialEntry(BaseModel):
    pos: Optional[int] = 0
    material: Optional[str] = ""
    vorbereitung: Optional[str] = ""
    verarbeitet: Optional[str] = ""
    bestellung: Optional[str] = ""

class EmployeeEntry(BaseModel):
    name: Optional[str] = ""
    rolle: Optional[str] = "T"  # PL, ME, T, H

class VehicleEntry(BaseModel):
    typ: Optional[str] = ""  # PKW, LKW, LKW_LDK, PKW_ANH, Tankwagen
    km: Optional[float] = 0
    stunden: Optional[float] = 0

class ProjectReportCreate(BaseModel):
    order_pk: Optional[str] = None
    order_name: Optional[str] = None
    # Kundendaten
    anrede: Optional[str] = "Firma"  # Herr, Frau, Firma, Projekt
    kunde_name: Optional[str] = ""
    kunde_anschrift: Optional[str] = ""
    kunde_plz: Optional[str] = ""
    kunde_ort: Optional[str] = ""
    kunde_telefon: Optional[str] = ""
    kunde_ansprechpartner: Optional[str] = ""
    # Projekt
    projektnummer: Optional[str] = ""
    projekt_datum: Optional[str] = ""
    kunde_nicht_anwesend: Optional[bool] = False
    # Mitarbeiter
    mitarbeiter: Optional[List[EmployeeEntry]] = []
    # Arbeitsprotokoll
    work_log: Optional[List[WorkLogEntry]] = []
    # Material
    material: Optional[List[MaterialEntry]] = []
    # Fahrzeuge
    fahrzeuge: Optional[List[VehicleEntry]] = []
    # Bemerkungen
    bemerkungen: Optional[str] = ""
    uebernachtung_zeitraum: Optional[str] = ""
    uebernachtung_naechte: Optional[int] = 0
    # Unterschriften (base64 data URLs)
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


# ── Endpoints ──

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


@router.get("/{report_id}")
async def get_report(report_id: str, user: dict = Depends(_auth_user)):
    report = await _db.project_reports.find_one({"id": report_id}, {"_id": 0})
    if not report:
        raise HTTPException(status_code=404, detail="Projektbericht nicht gefunden")
    return report


@router.put("/{report_id}")
async def update_report(report_id: str, data: ProjectReportUpdate, user: dict = Depends(_auth_user)):
    report = await _db.project_reports.find_one({"id": report_id}, {"_id": 0, "id": 1})
    if not report:
        raise HTTPException(status_code=404, detail="Projektbericht nicht gefunden")

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
    return {"message": "Gelöscht"}
