"""Verbandsbuch (Workplace first-aid logbook).

Pflicht nach DGUV Vorschrift 1 / §24 Abs. 6 SGB VII: Arbeitgeber muss jede Erste-Hilfe-
Leistung dokumentieren. Das Verbandsbuch muss 5 Jahre aufbewahrt werden.

Datenschutz: Nur Admins dürfen alle Einträge lesen. Mitarbeiter dürfen eigene Einträge
anlegen (als Betroffener ODER Meldender).
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
from io import BytesIO
import uuid
import logging

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_LEFT

from email_service import send_email_with_attachment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/verbandsbuch", tags=["verbandsbuch"])
security = HTTPBearer()

_db = None
_decode_jwt_token = None


def init_verbandsbuch_routes(db, decode_jwt_token):
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
        raise HTTPException(status_code=403, detail="Nur Administratoren dürfen das Verbandsbuch einsehen")
    return user


async def _next_lfd_nr() -> int:
    """Get next consecutive Lfd. Nr. (starts at 1)."""
    pipeline = [
        {"$group": {"_id": None, "max": {"$max": "$lfd_nr"}}},
    ]
    results = await _db.verbandsbuch.aggregate(pipeline).to_list(1)
    if results and results[0].get("max"):
        return int(results[0]["max"]) + 1
    return 1


class VerbandsbuchCreate(BaseModel):
    injured_name: str  # Vorname, Name
    injured_address: Optional[str] = ""  # Anschrift
    event_date: str  # YYYY-MM-DD
    event_time: str  # HH:MM
    location: str  # Ort (Raum/Bereich)
    hergang: str  # Hergang des Unfalls
    injury_type: str  # Art und Umfang der Verletzung
    witnesses: Optional[str] = ""  # freies Zeugen-Feld
    first_aider: Optional[str] = ""  # Ersthelfer
    notes: Optional[str] = ""


class VerbandsbuchUpdate(BaseModel):
    injured_name: Optional[str] = None
    injured_address: Optional[str] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    location: Optional[str] = None
    hergang: Optional[str] = None
    injury_type: Optional[str] = None
    witnesses: Optional[str] = None
    first_aider: Optional[str] = None
    notes: Optional[str] = None


@router.post("")
async def create_entry(payload: VerbandsbuchCreate, user=Depends(_auth_user)):
    """Any authenticated user can create an entry (self or colleague)."""
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": str(uuid.uuid4()),
        "lfd_nr": await _next_lfd_nr(),
        "injured_name": payload.injured_name.strip(),
        "injured_address": (payload.injured_address or "").strip(),
        "event_date": payload.event_date,
        "event_time": payload.event_time,
        "location": payload.location.strip(),
        "hergang": payload.hergang.strip(),
        "injury_type": payload.injury_type.strip(),
        "witnesses": (payload.witnesses or "").strip(),
        "first_aider": (payload.first_aider or "").strip(),
        "notes": (payload.notes or "").strip(),
        "reporter_user_id": user["id"],
        "reporter_name": user.get("name") or user.get("email"),
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
    }
    await _db.verbandsbuch.insert_one(entry)
    return {k: v for k, v in entry.items() if k != "_id"}


@router.get("")
async def list_entries(user=Depends(_require_admin)):
    """Admin only: list all entries sorted by lfd_nr desc (newest first)."""
    items = []
    async for doc in _db.verbandsbuch.find({"is_deleted": False}, {"_id": 0}).sort("lfd_nr", -1):
        items.append(doc)
    return {"entries": items, "total": len(items)}


@router.get("/{entry_id}")
async def get_entry(entry_id: str, user=Depends(_require_admin)):
    entry = await _db.verbandsbuch.find_one({"id": entry_id, "is_deleted": False}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return entry


@router.patch("/{entry_id}")
async def update_entry(entry_id: str, payload: VerbandsbuchUpdate, user=Depends(_require_admin)):
    update = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Keine Änderungen")
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await _db.verbandsbuch.update_one({"id": entry_id, "is_deleted": False}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    entry = await _db.verbandsbuch.find_one({"id": entry_id}, {"_id": 0})
    return entry


@router.delete("/{entry_id}")
async def delete_entry(entry_id: str, user=Depends(_require_admin)):
    """Soft delete (Verbandsbuch muss 5 Jahre aufbewahrt werden, aber Admin darf fehlerhafte Einträge ausblenden)."""
    result = await _db.verbandsbuch.update_one(
        {"id": entry_id, "is_deleted": False},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc).isoformat(), "deleted_by": user["id"]}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return {"success": True}


# ── PDF Generation ──────────────────────────────────────────────────────────
def _format_date(d: str) -> str:
    if not d:
        return "—"
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return d


def _generate_pdf(entry: dict) -> bytes:
    """Generate DGUV-compliant single-entry PDF for a Verbandsbuch record."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Verbandsbuch Lfd. Nr. {entry.get('lfd_nr', '?')}",
        author="Eventenergie Deutschland GmbH & Co. KG",
    )
    styles = getSampleStyleSheet()
    h_style = ParagraphStyle("h", parent=styles["Heading1"], fontSize=16, spaceAfter=4, textColor=colors.HexColor("#166534"))
    sub_style = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, textColor=colors.grey, spaceAfter=12)
    label_style = ParagraphStyle("lbl", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#6b7280"))
    val_style = ParagraphStyle("val", parent=styles["Normal"], fontSize=10, leading=13, alignment=TA_LEFT)

    story = []
    story.append(Paragraph("Verbandsbuch – Eintragung Erste-Hilfe-Leistung", h_style))
    story.append(Paragraph(
        f"Lfd. Nr. <b>{entry.get('lfd_nr', '?')}</b> · Dokumentation gem. DGUV Vorschrift 1 und § 24 Abs. 6 SGB VII",
        sub_style,
    ))

    def row(label, value):
        return [
            Paragraph(label, label_style),
            Paragraph((value or "—").replace("\n", "<br/>"), val_style),
        ]

    data = [
        row("Vorname, Name der/des Verletzten bzw. Erkrankten", entry.get("injured_name")),
        row("Anschrift", entry.get("injured_address")),
        row("Datum des Ereignisses", _format_date(entry.get("event_date"))),
        row("Uhrzeit", entry.get("event_time")),
        row("Ort (innerhalb der Einrichtung, z. B. Raum)", entry.get("location")),
        row("Hergang des Unfalls bzw. des Gesundheitsschadens", entry.get("hergang")),
        row("Art und Umfang der Verletzung bzw. Erkrankung", entry.get("injury_type")),
        row("Name der/des Ersthelfer(s)", entry.get("first_aider")),
        row("Zeugen", entry.get("witnesses")),
        row("Bemerkungen / Notizen", entry.get("notes")),
    ]

    tbl = Table(data, colWidths=[60 * mm, 110 * mm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#e5e7eb")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f9fafb")),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 14))

    footer = (
        f"Gemeldet durch: <b>{entry.get('reporter_name', '—')}</b> · "
        f"Eingetragen am {datetime.fromisoformat(entry['created_at']).strftime('%d.%m.%Y um %H:%M Uhr') if entry.get('created_at') else '—'}"
    )
    story.append(Paragraph(footer, ParagraphStyle("foot", parent=styles["Normal"], fontSize=8, textColor=colors.grey)))
    story.append(Spacer(1, 30))
    story.append(Paragraph(
        "______________________________________<br/>Unterschrift Ersthelfer / Vorgesetzter",
        ParagraphStyle("sig", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#4b5563")),
    ))

    doc.build(story)
    return buf.getvalue()


@router.get("/{entry_id}/pdf")
async def download_pdf(entry_id: str, user=Depends(_require_admin)):
    entry = await _db.verbandsbuch.find_one({"id": entry_id, "is_deleted": False}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    pdf = _generate_pdf(entry)
    filename = f"Verbandsbuch_Nr{entry['lfd_nr']:04d}_{entry['event_date']}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class VerbandsbuchEmailRequest(BaseModel):
    to_email: EmailStr
    message: Optional[str] = ""


@router.post("/{entry_id}/email")
async def email_entry(entry_id: str, payload: VerbandsbuchEmailRequest, user=Depends(_require_admin)):
    """Send the PDF version of an entry via email."""
    entry = await _db.verbandsbuch.find_one({"id": entry_id, "is_deleted": False}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")

    pdf = _generate_pdf(entry)
    filename = f"Verbandsbuch_Nr{entry['lfd_nr']:04d}_{entry['event_date']}.pdf"

    custom = (payload.message or "").strip()
    html = f"""
    <p>Sehr geehrte Damen und Herren,</p>
    <p>anbei übersenden wir den Verbandsbuch-Eintrag <b>Lfd. Nr. {entry['lfd_nr']}</b>
    vom {_format_date(entry['event_date'])} um {entry.get('event_time', '')} Uhr
    (Verletzte/r: <b>{entry['injured_name']}</b>).</p>
    {f'<p><i>{custom}</i></p>' if custom else ''}
    <p>Mit freundlichen Grüßen<br/>Eventenergie Deutschland GmbH &amp; Co. KG</p>
    """
    try:
        send_email_with_attachment(
            to_email=payload.to_email,
            subject=f"Verbandsbuch-Eintrag Nr. {entry['lfd_nr']} – {entry['injured_name']}",
            html_body=html,
            attachment_bytes=pdf,
            attachment_filename=filename,
        )
    except Exception as e:
        logger.error(f"Verbandsbuch-Mail an {payload.to_email} fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=f"E-Mail-Versand fehlgeschlagen: {e}")

    # Audit log
    await _db.verbandsbuch.update_one(
        {"id": entry_id},
        {"$push": {"email_log": {
            "to": payload.to_email,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "sent_by": user["id"],
            "sent_by_name": user.get("name") or user.get("email"),
        }}},
    )
    return {"success": True}
