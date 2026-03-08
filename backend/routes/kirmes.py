from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import bcrypt

router = APIRouter(prefix="/api/kirmes", tags=["kirmes"])
security = HTTPBearer()

_db = None
_decode_jwt_token = None

# Standard connection types
CONNECTION_TYPES = ["Schuko", "16A", "32A", "63A", "125A", "Festanschluss"]


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def init_kirmes_routes(db, decode_jwt_token):
    global _db, _decode_jwt_token
    _db = db
    _decode_jwt_token = decode_jwt_token


async def _auth_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")
    return user


async def _require_staff(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await _auth_user(credentials)
    if user["role"] not in ("admin", "mitarbeiter"):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    return user


async def _require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await _auth_user(credentials)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin-Berechtigung erforderlich")
    return user


# ============== Models ==============

class StandardPrice(BaseModel):
    connection_type: str
    price: float = 0.0
    avg_kwh: float = 0.0

    @field_validator("price", "avg_kwh", mode="before")
    @classmethod
    def coerce_float(cls, v):
        if v is None or v == "":
            return 0.0
        return float(v)


class StandardPriceUpdate(BaseModel):
    prices: List[StandardPrice]
    kwh_price: Optional[float] = None
    handling_surcharge: Optional[float] = None


class EventCreate(BaseModel):
    name: str
    location: str
    start_date: str
    end_date: str
    dispo_start: Optional[str] = ""
    dispo_end: Optional[str] = ""
    notes: Optional[str] = ""
    use_standard_prices: bool = True
    custom_prices: Optional[List[StandardPrice]] = None


class EventUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    dispo_start: Optional[str] = None
    dispo_end: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    kwh_price: Optional[float] = None
    handling_surcharge: Optional[float] = None
    custom_prices: Optional[List[StandardPrice]] = None


class SchaustellerRegister(BaseModel):
    firma: str = ""
    vorname: str = ""
    name: str
    strasse: str = ""
    plz: str = ""
    ort: str = ""
    steuernummer: str = ""
    email: EmailStr
    password: str = ""
    telefon: str = ""
    rechnungs_email: str = ""


class SchaustellerUpdate(BaseModel):
    firma: Optional[str] = None
    name: Optional[str] = None
    strasse: Optional[str] = None
    plz: Optional[str] = None
    ort: Optional[str] = None
    steuernummer: Optional[str] = None
    email: Optional[EmailStr] = None
    telefon: Optional[str] = None
    rechnungs_email: Optional[EmailStr] = None
    kauf_auf_rechnung: Optional[bool] = None


class EventSignup(BaseModel):
    event_id: str
    schausteller_id: str
    platznummer: str
    fahrgeschaeft: str
    connection_type: str
    payment_method: str = "kreditkarte"  # kreditkarte, paypal, rechnung


# ============== Standard Price List ==============

@router.get("/standard-prices")
async def get_standard_prices(user: dict = Depends(_require_staff)):
    prices = await _db.kirmes_standard_prices.find({"type": {"$ne": "global"}}, {"_id": 0}).to_list(100)
    if not prices:
        now = datetime.now(timezone.utc).isoformat()
        defaults = []
        for ct in CONNECTION_TYPES:
            defaults.append({"id": str(uuid.uuid4()), "connection_type": ct, "price": 0.0, "avg_kwh": 0.0, "updated_at": now})
        await _db.kirmes_standard_prices.insert_many(defaults)
        # Re-fetch to avoid _id issues
        prices = await _db.kirmes_standard_prices.find({"type": {"$ne": "global"}}, {"_id": 0}).to_list(100)
    # Ensure Schuko exists
    existing_types = [p["connection_type"] for p in prices]
    if "Schuko" not in existing_types:
        now = datetime.now(timezone.utc).isoformat()
        schuko = {"id": str(uuid.uuid4()), "connection_type": "Schuko", "price": 0.0, "avg_kwh": 0.0, "updated_at": now}
        await _db.kirmes_standard_prices.insert_one(schuko)
        schuko.pop("_id", None)
        prices.insert(0, schuko)
    # Sort by CONNECTION_TYPES order
    type_order = {t: i for i, t in enumerate(CONNECTION_TYPES)}
    prices.sort(key=lambda p: type_order.get(p["connection_type"], 99))
    # Get global settings
    global_settings = await _db.kirmes_standard_prices.find_one({"type": "global"}, {"_id": 0})
    return {
        "prices": prices,
        "kwh_price": global_settings.get("kwh_price", 0.0) if global_settings else 0.0,
        "handling_surcharge": global_settings.get("handling_surcharge", 0.0) if global_settings else 0.0,
    }


@router.put("/standard-prices")
async def update_standard_prices(data: StandardPriceUpdate, user: dict = Depends(_require_admin)):
    now = datetime.now(timezone.utc).isoformat()
    for p in data.prices:
        await _db.kirmes_standard_prices.update_one(
            {"connection_type": p.connection_type, "type": {"$ne": "global"}},
            {"$set": {"price": p.price, "avg_kwh": p.avg_kwh, "updated_at": now}},
            upsert=True
        )
    # Save global settings
    await _db.kirmes_standard_prices.update_one(
        {"type": "global"},
        {"$set": {
            "type": "global",
            "kwh_price": data.kwh_price if data.kwh_price is not None else 0.0,
            "handling_surcharge": data.handling_surcharge if data.handling_surcharge is not None else 0.0,
            "updated_at": now,
        }},
        upsert=True
    )
    return await get_standard_prices(user)


# ============== Events ==============

@router.get("/events")
async def list_events(
    status: Optional[str] = None,
    user: dict = Depends(_require_staff)
):
    query = {}
    if status:
        query["status"] = status
    events = await _db.kirmes_events.find(query, {"_id": 0}).sort("start_date", -1).to_list(500)
    # Add signup counts
    for event in events:
        event["signup_count"] = await _db.kirmes_signups.count_documents({"event_id": event["id"]})
    return events


@router.post("/events")
async def create_event(data: EventCreate, user: dict = Depends(_require_staff)):
    # Get prices
    if data.use_standard_prices:
        std_prices = await _db.kirmes_standard_prices.find({"type": {"$ne": "global"}}, {"_id": 0}).to_list(100)
        prices = [{"connection_type": p["connection_type"], "price": p["price"], "avg_kwh": p.get("avg_kwh", 0.0)} for p in std_prices]
        global_settings = await _db.kirmes_standard_prices.find_one({"type": "global"}, {"_id": 0})
        kwh_price = global_settings.get("kwh_price", 0.0) if global_settings else 0.0
        handling_surcharge = global_settings.get("handling_surcharge", 0.0) if global_settings else 0.0
    else:
        prices = [p.dict() for p in (data.custom_prices or [])]
        kwh_price = 0.0
        handling_surcharge = 0.0

    event_id = str(uuid.uuid4())
    event_doc = {
        "id": event_id,
        "name": data.name,
        "location": data.location,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "dispo_start": data.dispo_start or "",
        "dispo_end": data.dispo_end or "",
        "notes": data.notes or "",
        "status": "entwurf",
        "prices": prices,
        "kwh_price": kwh_price,
        "handling_surcharge": handling_surcharge,
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.kirmes_events.insert_one(event_doc)
    event_doc.pop("_id", None)
    event_doc["signup_count"] = 0
    return event_doc


@router.get("/events/{event_id}")
async def get_event(event_id: str, user: dict = Depends(_require_staff)):
    event = await _db.kirmes_events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")
    event["signup_count"] = await _db.kirmes_signups.count_documents({"event_id": event_id})
    # Get signups with schausteller info
    signups = await _db.kirmes_signups.find({"event_id": event_id}, {"_id": 0}).to_list(500)
    for signup in signups:
        sch = await _db.kirmes_schausteller.find_one({"id": signup["schausteller_id"]}, {"_id": 0})
        if sch:
            signup["schausteller"] = sch
    event["signups"] = signups
    return event


@router.put("/events/{event_id}")
async def update_event(event_id: str, data: EventUpdate, user: dict = Depends(_require_staff)):
    event = await _db.kirmes_events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")

    update = {}
    for field in ["name", "location", "start_date", "end_date", "dispo_start", "dispo_end", "notes", "status", "kwh_price", "handling_surcharge"]:
        val = getattr(data, field, None)
        if val is not None:
            update[field] = val
    if data.custom_prices is not None:
        update["prices"] = [p.dict() for p in data.custom_prices]
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    await _db.kirmes_events.update_one({"id": event_id}, {"$set": update})
    updated = await _db.kirmes_events.find_one({"id": event_id}, {"_id": 0})
    updated["signup_count"] = await _db.kirmes_signups.count_documents({"event_id": event_id})
    return updated


@router.delete("/events/{event_id}")
async def delete_event(event_id: str, user: dict = Depends(_require_admin)):
    event = await _db.kirmes_events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")
    # Delete associated data
    await _db.kirmes_invoices.delete_many({"event_id": event_id})
    await _db.kirmes_signups.delete_many({"event_id": event_id})
    await _db.kirmes_events.delete_one({"id": event_id})
    return {"message": "Veranstaltung gelöscht"}


@router.post("/events/{event_id}/release")
async def release_event(event_id: str, user: dict = Depends(_require_staff)):
    """Set event status to 'freigegeben' - makes it visible for schausteller registration."""
    event = await _db.kirmes_events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")
    await _db.kirmes_events.update_one(
        {"id": event_id},
        {"$set": {"status": "freigegeben", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Veranstaltung freigegeben", "status": "freigegeben"}



class InviteRequest(BaseModel):
    schausteller_ids: List[str]


@router.post("/events/{event_id}/invite")
async def invite_schausteller(event_id: str, data: InviteRequest, user: dict = Depends(_require_staff)):
    """Send invitation emails to schausteller for an event."""
    from email_service import send_email
    import os

    event = await _db.kirmes_events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")

    frontend_url = os.environ.get("FRONTEND_URL", "")
    if not frontend_url:
        # Try to construct from environment
        frontend_url = ""

    sent = 0
    failed = 0
    for sch_id in data.schausteller_ids:
        sch = await _db.kirmes_schausteller.find_one({"id": sch_id}, {"_id": 0})
        if not sch:
            continue

        signup_link = f"{frontend_url}/kirmes/anmeldung?event={event_id}"
        start = event.get("start_date", "")
        end = event.get("end_date", "")

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f5f5f5;">
<div style="max-width:520px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e5e5;">
  <div style="background:#d946ef;padding:28px 32px;">
    <h1 style="margin:0;color:#fff;font-size:20px;">Eventenergie Deutschland</h1>
  </div>
  <div style="padding:32px;">
    <p style="color:#333;font-size:15px;line-height:1.6;">Hallo {sch['name']},</p>
    <p style="color:#555;font-size:14px;line-height:1.6;">
      Sie sind eingeladen zur Veranstaltung <strong>{event['name']}</strong>
      ({start} – {end}{', ' + event.get('location', '') if event.get('location') else ''}).
    </p>
    <p style="color:#555;font-size:14px;line-height:1.6;">
      Bitte melden Sie sich über den folgenden Link an und geben Sie Ihre Platznummer und den gewünschten Stromanschluss an:
    </p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{signup_link}" style="display:inline-block;background:#d946ef;color:#fff;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:15px;font-weight:600;">
        Jetzt anmelden
      </a>
    </div>
    <p style="color:#888;font-size:12px;line-height:1.5;">
      Sie sind bereits registriert. Melden Sie sich mit Ihrer E-Mail-Adresse ({sch['email']}) an.
    </p>
  </div>
  <div style="background:#fafafa;padding:16px 32px;border-top:1px solid #eee;">
    <p style="margin:0;color:#aaa;font-size:11px;text-align:center;">&copy; {datetime.now().year} Eventenergie Deutschland GmbH &amp; Co. KG</p>
  </div>
</div>
</body></html>"""

        subject = f"Einladung: {event['name']} – Stromanschluss anmelden"
        ok = send_email(sch["email"], subject, html)
        if ok:
            sent += 1
            # Track invitation
            await _db.kirmes_invitations.update_one(
                {"event_id": event_id, "schausteller_id": sch_id},
                {"$set": {"sent_at": datetime.now(timezone.utc).isoformat(), "email": sch["email"]}},
                upsert=True
            )
        else:
            failed += 1

    return {"sent": sent, "failed": failed, "message": f"{sent} Einladung(en) versendet, {failed} fehlgeschlagen"}



# ============== Schausteller (Public Registration) ==============

@router.post("/public/register")
async def register_schausteller(data: SchaustellerRegister):
    """Public endpoint - no auth required. Registers schausteller and sends verification code."""
    import random

    existing = await _db.kirmes_schausteller.find_one({"email": data.email}, {"_id": 0})
    if existing:
        if existing.get("email_verified") and existing.get("password_hash"):
            raise HTTPException(status_code=400, detail="Diese E-Mail-Adresse ist bereits registriert. Bitte melden Sie sich an.")
        # Resend verification code
        code = str(random.randint(100000, 999999))
        update = {"verification_code": code, "updated_at": datetime.now(timezone.utc).isoformat()}
        # Update name/firma if provided
        if data.name:
            update["name"] = data.name
        if data.firma:
            update["firma"] = data.firma
        await _db.kirmes_schausteller.update_one({"email": data.email}, {"$set": update})
        _send_verification_email(data.email, data.name or existing.get("name", ""), code)
        result = {k: v for k, v in existing.items() if k not in ("password_hash", "verification_code")}
        result["email_verified"] = False
        return result

    code = str(random.randint(100000, 999999))
    sch_id = str(uuid.uuid4())
    sch_doc = {
        "id": sch_id,
        "firma": data.firma,
        "vorname": data.vorname,
        "name": data.name,
        "strasse": data.strasse,
        "plz": data.plz,
        "ort": data.ort,
        "steuernummer": data.steuernummer,
        "email": data.email,
        "telefon": data.telefon,
        "rechnungs_email": data.rechnungs_email or data.email,
        "email_verified": False,
        "verification_code": code,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.kirmes_schausteller.insert_one(sch_doc)
    sch_doc.pop("_id", None)
    sch_doc.pop("verification_code", None)

    _send_verification_email(data.email, data.name, code)
    return sch_doc


def _send_verification_email(email, name, code):
    from email_service import send_email
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f5f5f5;">
<div style="max-width:520px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e5e5;">
  <div style="background:#d946ef;padding:28px 32px;">
    <h1 style="margin:0;color:#fff;font-size:20px;">Eventenergie Deutschland</h1>
  </div>
  <div style="padding:32px;">
    <p style="color:#333;font-size:15px;">Hallo {name},</p>
    <p style="color:#555;font-size:14px;line-height:1.6;">
      Bitte bestätigen Sie Ihre E-Mail-Adresse mit folgendem Code:
    </p>
    <div style="text-align:center;margin:28px 0;">
      <div style="display:inline-block;background:#f3e8ff;border:2px solid #d946ef;border-radius:12px;padding:16px 40px;">
        <span style="font-size:32px;font-weight:700;letter-spacing:8px;color:#d946ef;">{code}</span>
      </div>
    </div>
    <p style="color:#888;font-size:12px;">Der Code ist 30 Minuten gültig.</p>
  </div>
  <div style="background:#fafafa;padding:16px 32px;border-top:1px solid #eee;">
    <p style="margin:0;color:#aaa;font-size:11px;text-align:center;">&copy; {datetime.now().year} Eventenergie Deutschland GmbH &amp; Co. KG</p>
  </div>
</div>
</body></html>"""
    send_email(email, "Ihr Bestätigungscode – Eventenergie", html)


def _send_booking_confirmation_email(schausteller, event, signup):
    from email_service import send_email
    name = schausteller.get("name", "")
    email = schausteller.get("email", "")
    event_name = event.get("name", "")
    location = event.get("location", "")
    start = event.get("start_date", "")
    end = event.get("end_date", "")
    platznummer = signup.get("platznummer", "")
    fahrgeschaeft = signup.get("fahrgeschaeft", "")
    conn_type = signup.get("connection_type", "")
    price = signup.get("price", 0)
    payment = signup.get("payment_method", "")

    payment_labels = {"kreditkarte": "Kreditkarte", "paypal": "PayPal", "rechnung": "Auf Rechnung"}
    payment_label = payment_labels.get(payment, payment)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f5f5f5;">
<div style="max-width:520px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e5e5;">
  <div style="background:#d946ef;padding:28px 32px;">
    <h1 style="margin:0;color:#fff;font-size:20px;">Eventenergie Deutschland</h1>
  </div>
  <div style="padding:32px;">
    <p style="color:#333;font-size:15px;line-height:1.6;">Hallo {name},</p>
    <p style="color:#555;font-size:14px;line-height:1.6;">
      Ihre Anmeldung für die Veranstaltung <strong>{event_name}</strong> wurde erfolgreich entgegengenommen.
    </p>
    <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin:20px 0;">
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:6px 0;color:#888;font-size:13px;width:140px;">Veranstaltung</td><td style="padding:6px 0;color:#333;font-size:13px;font-weight:600;">{event_name}</td></tr>
        <tr><td style="padding:6px 0;color:#888;font-size:13px;">Ort</td><td style="padding:6px 0;color:#333;font-size:13px;">{location}</td></tr>
        <tr><td style="padding:6px 0;color:#888;font-size:13px;">Zeitraum</td><td style="padding:6px 0;color:#333;font-size:13px;">{start} – {end}</td></tr>
        <tr><td colspan="2" style="padding:8px 0;"><hr style="border:none;border-top:1px solid #e5e7eb;"></td></tr>
        <tr><td style="padding:6px 0;color:#888;font-size:13px;">Platznummer</td><td style="padding:6px 0;color:#333;font-size:13px;font-weight:600;">{platznummer}</td></tr>
        <tr><td style="padding:6px 0;color:#888;font-size:13px;">Fahrgeschäft</td><td style="padding:6px 0;color:#333;font-size:13px;">{fahrgeschaeft}</td></tr>
        <tr><td style="padding:6px 0;color:#888;font-size:13px;">Stromanschluss</td><td style="padding:6px 0;color:#333;font-size:13px;font-weight:600;">{conn_type}</td></tr>
        <tr><td style="padding:6px 0;color:#888;font-size:13px;">Anschlussgebühr</td><td style="padding:6px 0;color:#333;font-size:13px;font-weight:600;">{price:.2f} EUR</td></tr>
        <tr><td style="padding:6px 0;color:#888;font-size:13px;">Zahlungsmittel</td><td style="padding:6px 0;color:#333;font-size:13px;">{payment_label}</td></tr>
      </table>
    </div>
    <p style="color:#555;font-size:13px;line-height:1.6;">
      Bei Fragen wenden Sie sich bitte an unser Team.
    </p>
  </div>
  <div style="background:#fafafa;padding:16px 32px;border-top:1px solid #eee;">
    <p style="margin:0;color:#aaa;font-size:11px;text-align:center;">&copy; {datetime.now().year} Eventenergie Deutschland GmbH &amp; Co. KG</p>
  </div>
</div>
</body></html>"""
    try:
        send_email(email, f"Buchungsbestätigung: {event_name} – Platz {platznummer}", html)
    except Exception:
        pass  # Don't fail signup if email fails


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


@router.post("/public/verify-email")
async def verify_email(data: VerifyEmailRequest):
    """Public endpoint - verify email with code."""
    sch = await _db.kirmes_schausteller.find_one({"email": data.email}, {"_id": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Kein Konto mit dieser E-Mail gefunden.")
    if sch.get("email_verified") and sch.get("password_hash"):
        sch.pop("password_hash", None)
        sch.pop("verification_code", None)
        return sch
    if sch.get("verification_code") != data.code:
        raise HTTPException(status_code=400, detail="Ungültiger Code. Bitte erneut versuchen.")
    await _db.kirmes_schausteller.update_one(
        {"email": data.email},
        {"$set": {"email_verified": True, "verification_code": None, "verified_at": datetime.now(timezone.utc).isoformat()}}
    )
    updated = await _db.kirmes_schausteller.find_one({"email": data.email}, {"_id": 0})
    updated.pop("verification_code", None)
    updated.pop("password_hash", None)
    return updated


class SetPasswordPublic(BaseModel):
    email: EmailStr
    password: str


@router.post("/public/set-password")
async def public_set_password(data: SetPasswordPublic):
    """Public endpoint - Set password after email verification."""
    sch = await _db.kirmes_schausteller.find_one({"email": data.email}, {"_id": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Kein Konto gefunden.")
    if not sch.get("email_verified"):
        raise HTTPException(status_code=403, detail="E-Mail noch nicht bestätigt.")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Passwort muss mindestens 6 Zeichen lang sein.")
    await _db.kirmes_schausteller.update_one(
        {"email": data.email},
        {"$set": {"password_hash": _hash_password(data.password), "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    updated = await _db.kirmes_schausteller.find_one({"email": data.email}, {"_id": 0, "password_hash": 0, "verification_code": 0})
    return updated


@router.get("/public/resend-code")
async def resend_code(email: str = Query(...)):
    """Public endpoint - resend verification code."""
    import random
    sch = await _db.kirmes_schausteller.find_one({"email": email}, {"_id": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Kein Konto gefunden.")
    if sch.get("email_verified"):
        return {"message": "E-Mail bereits bestätigt."}
    code = str(random.randint(100000, 999999))
    await _db.kirmes_schausteller.update_one(
        {"email": email},
        {"$set": {"verification_code": code}}
    )
    _send_verification_email(email, sch["name"], code)
    return {"message": "Neuer Code wurde gesendet."}


@router.get("/public/my-bookings")
async def get_my_bookings(schausteller_id: str = Query(...)):
    """Public endpoint - Get all bookings and invoices for a schausteller."""
    sch = await _db.kirmes_schausteller.find_one({"id": schausteller_id}, {"_id": 0, "password_hash": 0, "verification_code": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")

    signups = await _db.kirmes_signups.find({"schausteller_id": schausteller_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    for s in signups:
        event = await _db.kirmes_events.find_one({"id": s["event_id"]}, {"_id": 0, "name": 1, "location": 1, "start_date": 1, "end_date": 1})
        s["event"] = event or {}

    invoices = await _db.kirmes_invoices.find(
        {"schausteller_id": schausteller_id},
        {"_id": 0, "id": 1, "invoice_number": 1, "event_name": 1, "invoice_date": 1, "brutto": 1, "status": 1}
    ).sort("created_at", -1).to_list(100)

    return {"signups": signups, "invoices": invoices}


class SchaustellerLogin(BaseModel):
    email: EmailStr
    password: str


@router.post("/public/login")
async def login_schausteller(data: SchaustellerLogin):
    """Public endpoint - Schausteller logs in with email + password."""
    sch = await _db.kirmes_schausteller.find_one({"email": data.email}, {"_id": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Kein Konto mit dieser E-Mail gefunden. Bitte zuerst registrieren.")
    if not sch.get("email_verified"):
        raise HTTPException(status_code=403, detail="E-Mail noch nicht bestätigt. Bitte prüfen Sie Ihren Posteingang.")
    if not sch.get("password_hash"):
        raise HTTPException(status_code=401, detail="Kein Passwort hinterlegt. Bitte registrieren Sie sich erneut mit einem Passwort.")
    if not _verify_password(data.password, sch["password_hash"]):
        raise HTTPException(status_code=401, detail="Falsches Passwort.")
    sch.pop("verification_code", None)
    sch.pop("password_hash", None)
    return sch


@router.get("/public/events")
async def list_public_events():
    """Public endpoint - List all released events for schausteller signup."""
    events = await _db.kirmes_events.find(
        {"status": {"$in": ["freigegeben", "aktiv"]}},
        {"_id": 0, "id": 1, "name": 1, "location": 1, "start_date": 1, "end_date": 1, "prices": 1, "status": 1}
    ).sort("start_date", 1).to_list(100)
    return events


@router.get("/public/events/{event_id}")
async def get_public_event(event_id: str):
    """Public endpoint - Get event details for signup."""
    event = await _db.kirmes_events.find_one(
        {"id": event_id, "status": {"$in": ["freigegeben", "aktiv"]}},
        {"_id": 0}
    )
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden oder nicht freigegeben")
    return event


@router.post("/public/signup")
async def signup_for_event(data: EventSignup):
    """Public endpoint - Schausteller signs up for an event."""
    # Validate event exists and is released
    event = await _db.kirmes_events.find_one(
        {"id": data.event_id, "status": {"$in": ["freigegeben", "aktiv"]}},
        {"_id": 0}
    )
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden oder nicht freigegeben")

    # Validate schausteller exists
    sch = await _db.kirmes_schausteller.find_one({"id": data.schausteller_id}, {"_id": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")

    # Check if already signed up
    existing = await _db.kirmes_signups.find_one({
        "event_id": data.event_id,
        "schausteller_id": data.schausteller_id
    })
    if existing:
        raise HTTPException(status_code=400, detail="Bereits für diese Veranstaltung angemeldet")

    # Validate connection type
    if data.connection_type not in CONNECTION_TYPES:
        raise HTTPException(status_code=400, detail=f"Ungültiger Anschlusstyp: {data.connection_type}")

    # Validate payment method - "rechnung" only allowed if kauf_auf_rechnung is enabled
    if data.payment_method == "rechnung" and not sch.get("kauf_auf_rechnung"):
        raise HTTPException(status_code=400, detail="Kauf auf Rechnung ist für diesen Schausteller nicht freigeschaltet.")

    # Find price for this connection type
    price = 0.0
    for p in event.get("prices", []):
        if p["connection_type"] == data.connection_type:
            price = p["price"]
            break

    signup_id = str(uuid.uuid4())
    signup_doc = {
        "id": signup_id,
        "event_id": data.event_id,
        "schausteller_id": data.schausteller_id,
        "platznummer": data.platznummer,
        "fahrgeschaeft": data.fahrgeschaeft,
        "connection_type": data.connection_type,
        "price": price,
        "payment_method": data.payment_method,
        "payment_status": "ausstehend",  # ausstehend, reserviert, bezahlt, erstattet
        "deposit_amount": 0.0,
        "meter_id": None,  # Will be linked later via QR code
        "meter_start": None,
        "meter_end": None,
        "kwh_used": None,
        "final_amount": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.kirmes_signups.insert_one(signup_doc)
    signup_doc.pop("_id", None)
    signup_doc["schausteller"] = sch

    # Send booking confirmation email
    _send_booking_confirmation_email(sch, event, signup_doc)

    return signup_doc


# ============== Schausteller Management (Staff) ==============

@router.get("/schausteller")
async def list_schausteller(
    search: Optional[str] = None,
    user: dict = Depends(_require_staff)
):
    query = {}
    if search:
        query["$or"] = [
            {"firma": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]
    schausteller = await _db.kirmes_schausteller.find(query, {"_id": 0, "password_hash": 0, "verification_code": 0}).sort("firma", 1).to_list(500)
    return schausteller


@router.get("/schausteller/{sch_id}")
async def get_schausteller(sch_id: str, user: dict = Depends(_require_staff)):
    sch = await _db.kirmes_schausteller.find_one({"id": sch_id}, {"_id": 0, "password_hash": 0, "verification_code": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")
    # Get their signups
    signups = await _db.kirmes_signups.find({"schausteller_id": sch_id}, {"_id": 0}).to_list(100)
    for s in signups:
        event = await _db.kirmes_events.find_one({"id": s["event_id"]}, {"_id": 0, "id": 1, "name": 1})
        s["event_name"] = event["name"] if event else "Unbekannt"
    sch["signups"] = signups
    # Get their invoices
    invoices = await _db.kirmes_invoices.find(
        {"schausteller_id": sch_id},
        {"_id": 0, "id": 1, "invoice_number": 1, "event_name": 1, "event_id": 1,
         "invoice_date": 1, "netto": 1, "brutto": 1, "status": 1, "sent_at": 1, "sent_to": 1, "created_at": 1}
    ).sort("created_at", -1).to_list(100)
    sch["invoices"] = invoices
    return sch


class SchaustellerSetPassword(BaseModel):
    password: str


@router.post("/schausteller/{sch_id}/set-password")
async def set_schausteller_password(sch_id: str, data: SchaustellerSetPassword, user: dict = Depends(_require_staff)):
    """Staff endpoint - Set password for a schausteller."""
    sch = await _db.kirmes_schausteller.find_one({"id": sch_id}, {"_id": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Passwort muss mindestens 6 Zeichen lang sein.")
    await _db.kirmes_schausteller.update_one(
        {"id": sch_id},
        {"$set": {
            "password_hash": _hash_password(data.password),
            "email_verified": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"message": "Passwort wurde gesetzt und E-Mail als bestätigt markiert."}


@router.put("/schausteller/{sch_id}")
async def update_schausteller(sch_id: str, data: SchaustellerUpdate, user: dict = Depends(_require_staff)):
    sch = await _db.kirmes_schausteller.find_one({"id": sch_id}, {"_id": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")
    update = {k: v for k, v in data.dict().items() if v is not None}
    if update:
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        await _db.kirmes_schausteller.update_one({"id": sch_id}, {"$set": update})
    updated = await _db.kirmes_schausteller.find_one({"id": sch_id}, {"_id": 0})
    return updated


@router.delete("/schausteller/{sch_id}")
async def delete_schausteller(sch_id: str, user: dict = Depends(_require_admin)):
    sch = await _db.kirmes_schausteller.find_one({"id": sch_id}, {"_id": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")
    # Check for active signups
    active_signups = await _db.kirmes_signups.count_documents({"schausteller_id": sch_id, "payment_status": {"$in": ["reserviert", "bezahlt"]}})
    if active_signups > 0:
        raise HTTPException(status_code=400, detail="Schausteller hat aktive Buchungen und kann nicht gelöscht werden")
    await _db.kirmes_signups.delete_many({"schausteller_id": sch_id})
    await _db.kirmes_schausteller.delete_one({"id": sch_id})
    return {"message": "Schausteller gelöscht"}



# ============== Signup Management (Staff) ==============

@router.get("/signups/{signup_id}")
async def get_signup(signup_id: str, user: dict = Depends(_require_staff)):
    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")
    sch = await _db.kirmes_schausteller.find_one({"id": signup["schausteller_id"]}, {"_id": 0})
    if sch:
        signup["schausteller"] = sch
    return signup


@router.delete("/signups/{signup_id}")
async def delete_signup(signup_id: str, user: dict = Depends(_require_staff)):
    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")
    await _db.kirmes_signups.delete_one({"id": signup_id})
    return {"message": "Anmeldung gelöscht"}


class SignupKwhUpdate(BaseModel):
    kwh_einbau: Optional[float] = None
    kwh_ausbau: Optional[float] = None


@router.put("/signups/{signup_id}/kwh")
async def update_signup_kwh(signup_id: str, data: SignupKwhUpdate, user: dict = Depends(_require_staff)):
    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")
    update = {}
    if data.kwh_einbau is not None:
        update["kwh_einbau"] = data.kwh_einbau
    if data.kwh_ausbau is not None:
        update["kwh_ausbau"] = data.kwh_ausbau
    if "kwh_einbau" in update and "kwh_ausbau" in update:
        update["kwh_used"] = round(update["kwh_ausbau"] - update["kwh_einbau"], 2)
    elif data.kwh_ausbau is not None and signup.get("kwh_einbau") is not None:
        update["kwh_used"] = round(data.kwh_ausbau - signup["kwh_einbau"], 2)
    elif data.kwh_einbau is not None and signup.get("kwh_ausbau") is not None:
        update["kwh_used"] = round(signup["kwh_ausbau"] - data.kwh_einbau, 2)
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _db.kirmes_signups.update_one({"id": signup_id}, {"$set": update})
    updated = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    return updated




@router.get("/public/invoice/{invoice_id}/pdf")
async def public_download_invoice_pdf(invoice_id: str, schausteller_id: str = Query(...)):
    """Public endpoint - Schausteller downloads their own invoice PDF."""
    from services.invoice_pdf import generate_invoice_pdf
    inv = await _db.kirmes_invoices.find_one({"id": invoice_id, "schausteller_id": schausteller_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    pdf_bytes = generate_invoice_pdf(inv)
    filename = f"{inv['invoice_number']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ============== Connection Types ==============

@router.get("/connection-types")
async def get_connection_types():
    """Public endpoint - Get available connection types."""
    return CONNECTION_TYPES


# ============== Invoice / Abrechnung ==============

async def _get_next_invoice_number():
    """Generate next invoice number: R{YY}-K-{NNNN}."""
    year_prefix = f"R{datetime.now().strftime('%y')}-K-"
    last = await _db.kirmes_invoices.find(
        {"invoice_number": {"$regex": f"^{year_prefix}"}},
        {"_id": 0, "invoice_number": 1}
    ).sort("invoice_number", -1).limit(1).to_list(1)
    if last:
        last_num = int(last[0]["invoice_number"].split("-K-")[1])
        return f"{year_prefix}{str(last_num + 1).zfill(4)}"
    return f"{year_prefix}0001"


def _calculate_invoice(signup: dict, event: dict, schausteller: dict) -> dict:
    """Calculate invoice amounts for a signup."""
    line_items = []
    pos = 1

    # 1. Connection fee (Anschlussgebühr)
    conn_fee = signup.get("price", 0)
    conn_type = signup.get("connection_type", "")
    line_items.append({
        "pos": pos, "description": f"Stromanschluss {conn_type} – Platz {signup.get('platznummer', '')}",
        "quantity": "1", "unit": "pauschal", "unit_price": conn_fee, "total": conn_fee,
    })
    pos += 1

    # 2. kWh consumption - always show Einbau, Ausbau, Verbrauch
    kwh_start = signup.get("kwh_einbau") or signup.get("kwh_start") or 0
    kwh_end = signup.get("kwh_ausbau") or signup.get("kwh_end") or 0
    kwh_used = max(0, kwh_end - kwh_start)
    kwh_price = event.get("kwh_price", 0)

    kwh_total = round(kwh_used * kwh_price, 2)
    line_items.append({
        "pos": pos,
        "description": f"Energieverbrauch\nZählerstand Einbau: {kwh_start:.2f} kWh\nZählerstand Ausbau: {kwh_end:.2f} kWh\nVerbrauch: {kwh_used:.2f} kWh",
        "quantity": f"{kwh_used:.2f}", "unit": "kWh", "unit_price": kwh_price, "total": kwh_total,
    })
    pos += 1

    # 3. Handling surcharge = kWh consumed * handling price per kWh
    handling_per_kwh = event.get("handling_surcharge", 0)
    if handling_per_kwh > 0:
        handling_total = round(kwh_used * handling_per_kwh, 2)
        line_items.append({
            "pos": pos,
            "description": f"Handlingpauschale ({kwh_used:.2f} kWh)",
            "quantity": f"{kwh_used:.2f}", "unit": "kWh", "unit_price": handling_per_kwh, "total": handling_total,
        })
        pos += 1

    netto = round(sum(item["total"] for item in line_items), 2)
    mwst_rate = 19
    mwst_amount = round(netto * mwst_rate / 100, 2)
    brutto = round(netto + mwst_amount, 2)

    return {
        "line_items": line_items,
        "netto": netto,
        "mwst_rate": mwst_rate,
        "mwst_amount": mwst_amount,
        "brutto": brutto,
    }


@router.post("/signups/{signup_id}/invoice")
async def generate_invoice_for_signup(signup_id: str, user: dict = Depends(_require_staff)):
    """Generate an invoice for a single signup."""
    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")

    # Check if invoice already exists
    existing = await _db.kirmes_invoices.find_one({"signup_id": signup_id}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail=f"Rechnung {existing['invoice_number']} existiert bereits für diese Anmeldung.")

    event = await _db.kirmes_events.find_one({"id": signup["event_id"]}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")
    sch = await _db.kirmes_schausteller.find_one({"id": signup["schausteller_id"]}, {"_id": 0, "password_hash": 0, "verification_code": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")

    calc = _calculate_invoice(signup, event, sch)
    inv_number = await _get_next_invoice_number()

    invoice_doc = {
        "id": str(uuid.uuid4()),
        "invoice_number": inv_number,
        "signup_id": signup_id,
        "event_id": signup["event_id"],
        "event_name": event.get("name", ""),
        "schausteller_id": signup["schausteller_id"],
        "schausteller_firma": sch.get("firma", ""),
        "schausteller_name": sch.get("name", ""),
        "schausteller_email": sch.get("email", ""),
        "invoice_date": datetime.now(timezone.utc).strftime("%d.%m.%Y"),
        "line_items": calc["line_items"],
        "netto": calc["netto"],
        "mwst_rate": calc["mwst_rate"],
        "mwst_amount": calc["mwst_amount"],
        "brutto": calc["brutto"],
        "status": "erstellt",
        "schausteller": sch,
        "event": {"name": event.get("name", ""), "location": event.get("location", ""),
                  "start_date": event.get("start_date", ""), "end_date": event.get("end_date", "")},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("name", ""),
    }
    await _db.kirmes_invoices.insert_one(invoice_doc)
    invoice_doc.pop("_id", None)

    # Update signup status
    await _db.kirmes_signups.update_one(
        {"id": signup_id},
        {"$set": {"invoice_id": invoice_doc["id"], "invoice_number": inv_number, "payment_status": "abgerechnet"}}
    )

    return invoice_doc


@router.post("/events/{event_id}/generate-invoices")
async def generate_all_invoices(event_id: str, user: dict = Depends(_require_staff)):
    """Generate invoices for all signups in an event that don't have one yet."""
    event = await _db.kirmes_events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")

    signups = await _db.kirmes_signups.find({"event_id": event_id}, {"_id": 0}).to_list(500)
    generated = []
    skipped = []

    for signup in signups:
        existing = await _db.kirmes_invoices.find_one({"signup_id": signup["id"]}, {"_id": 0})
        if existing:
            skipped.append({"signup_id": signup["id"], "invoice_number": existing["invoice_number"], "reason": "Bereits abgerechnet"})
            continue

        sch = await _db.kirmes_schausteller.find_one({"id": signup["schausteller_id"]}, {"_id": 0, "password_hash": 0, "verification_code": 0})
        if not sch:
            skipped.append({"signup_id": signup["id"], "reason": "Schausteller nicht gefunden"})
            continue

        calc = _calculate_invoice(signup, event, sch)
        inv_number = await _get_next_invoice_number()

        invoice_doc = {
            "id": str(uuid.uuid4()),
            "invoice_number": inv_number,
            "signup_id": signup["id"],
            "event_id": event_id,
            "event_name": event.get("name", ""),
            "schausteller_id": signup["schausteller_id"],
            "schausteller_firma": sch.get("firma", ""),
            "schausteller_name": sch.get("name", ""),
            "schausteller_email": sch.get("email", ""),
            "invoice_date": datetime.now(timezone.utc).strftime("%d.%m.%Y"),
            "line_items": calc["line_items"],
            "netto": calc["netto"],
            "mwst_rate": calc["mwst_rate"],
            "mwst_amount": calc["mwst_amount"],
            "brutto": calc["brutto"],
            "status": "erstellt",
            "schausteller": sch,
            "event": {"name": event.get("name", ""), "location": event.get("location", ""),
                      "start_date": event.get("start_date", ""), "end_date": event.get("end_date", "")},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get("name", ""),
        }
        await _db.kirmes_invoices.insert_one(invoice_doc)
        invoice_doc.pop("_id", None)

        await _db.kirmes_signups.update_one(
            {"id": signup["id"]},
            {"$set": {"invoice_id": invoice_doc["id"], "invoice_number": inv_number, "payment_status": "abgerechnet"}}
        )

        # Auto-send invoice via email
        try:
            from services.invoice_pdf import generate_invoice_pdf
            from email_service import send_email_with_attachment
            pdf_bytes = generate_invoice_pdf(invoice_doc)
            sch_email = sch.get("rechnungs_email") or sch.get("email", "")
            if sch_email:
                filename = f"{inv_number}.pdf"
                subject = f"Rechnung {inv_number} – {event.get('name', '')}"
                html = f"""<p>Sehr geehrte Damen und Herren,</p>
<p>anbei erhalten Sie die Rechnung <b>{inv_number}</b> für die Veranstaltung <b>{event.get('name', '')}</b>.</p>
<p>Rechnungsbetrag: <b>{calc['brutto']:.2f} EUR</b></p>
<p>Bitte überweisen Sie den Betrag innerhalb von 14 Tagen auf das in der Rechnung angegebene Konto.</p>
<p>Mit freundlichen Grüßen<br/><b>Eventenergie Deutschland GmbH &amp; Co. KG</b></p>"""
                send_email_with_attachment(sch_email, subject, html, pdf_bytes, filename)
                await _db.kirmes_invoices.update_one(
                    {"id": invoice_doc["id"]},
                    {"$set": {"status": "versendet", "sent_at": datetime.now(timezone.utc).isoformat(), "sent_to": sch_email}}
                )
        except Exception:
            pass  # Don't fail batch if single email fails

        generated.append({"signup_id": signup["id"], "invoice_number": inv_number, "brutto": calc["brutto"]})

    # Update event status
    await _db.kirmes_events.update_one({"id": event_id}, {"$set": {"status": "abgerechnet"}})

    return {"generated": len(generated), "skipped": len(skipped), "invoices": generated, "skipped_details": skipped}


@router.get("/invoices")
async def list_invoices(
    search: Optional[str] = None,
    event_id: Optional[str] = None,
    user: dict = Depends(_require_staff)
):
    """List/search invoices."""
    query = {}
    if event_id:
        query["event_id"] = event_id
    if search:
        query["$or"] = [
            {"invoice_number": {"$regex": search, "$options": "i"}},
            {"schausteller_firma": {"$regex": search, "$options": "i"}},
            {"schausteller_name": {"$regex": search, "$options": "i"}},
            {"event_name": {"$regex": search, "$options": "i"}},
        ]
    invoices = await _db.kirmes_invoices.find(query, {
        "_id": 0, "id": 1, "invoice_number": 1, "event_name": 1, "event_id": 1,
        "schausteller_firma": 1, "schausteller_name": 1, "schausteller_email": 1,
        "invoice_date": 1, "netto": 1, "brutto": 1, "status": 1, "created_at": 1,
    }).sort("created_at", -1).to_list(500)
    return invoices


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, user: dict = Depends(_require_staff)):
    """Get full invoice details."""
    inv = await _db.kirmes_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    return inv


@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(invoice_id: str, user: dict = Depends(_require_staff)):
    """Download invoice as PDF."""
    from services.invoice_pdf import generate_invoice_pdf
    inv = await _db.kirmes_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    pdf_bytes = generate_invoice_pdf(inv)
    filename = f"{inv['invoice_number'].replace('/', '-')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/invoices/{invoice_id}/send")
async def send_invoice_email(invoice_id: str, user: dict = Depends(_require_staff)):
    """Send invoice PDF via email to the schausteller."""
    from services.invoice_pdf import generate_invoice_pdf
    from email_service import send_email_with_attachment
    inv = await _db.kirmes_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    pdf_bytes = generate_invoice_pdf(inv)
    sch_email = inv.get("schausteller", {}).get("rechnungs_email") or inv.get("schausteller_email", "")
    if not sch_email:
        raise HTTPException(status_code=400, detail="Keine E-Mail-Adresse vorhanden")

    filename = f"{inv['invoice_number']}.pdf"
    subject = f"Rechnung {inv['invoice_number']} – {inv.get('event_name', '')}"
    html = f"""<p>Sehr geehrte Damen und Herren,</p>
<p>anbei erhalten Sie die Rechnung <b>{inv['invoice_number']}</b> für die Veranstaltung <b>{inv.get('event_name', '')}</b>.</p>
<p>Rechnungsbetrag: <b>{inv['brutto']:.2f} EUR</b></p>
<p>Bitte überweisen Sie den Betrag innerhalb von 14 Tagen auf das in der Rechnung angegebene Konto.</p>
<p>Mit freundlichen Grüßen<br/><b>Eventenergie Deutschland GmbH &amp; Co. KG</b></p>"""

    try:
        send_email_with_attachment(sch_email, subject, html, pdf_bytes, filename)
        await _db.kirmes_invoices.update_one(
            {"id": invoice_id},
            {"$set": {"status": "versendet", "sent_at": datetime.now(timezone.utc).isoformat(), "sent_to": sch_email}}
        )
        return {"message": f"Rechnung an {sch_email} versendet."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"E-Mail konnte nicht gesendet werden: {str(e)}")



# ============== EMU Meter Integration ==============

class LinkMeterRequest(BaseModel):
    emu_device_id: str
    emu_meter_id: str

@router.get("/emu-meters")
async def list_emu_meters(user: dict = Depends(_require_staff)):
    """List all available EMU meters for assignment to signups."""
    meters = await _db.emu_meters.find({}, {"_id": 0}).to_list(500)
    # Enrich each meter with its device info
    for m in meters:
        device = await _db.devices.find_one({"id": m["device_id"]}, {"_id": 0, "id": 1, "serial_number": 1, "name": 1})
        m["device_name"] = device.get("serial_number") or device.get("name", "") if device else ""
    return meters


@router.put("/signups/{signup_id}/link-meter")
async def link_meter_to_signup(signup_id: str, data: LinkMeterRequest, user: dict = Depends(_require_staff)):
    """Link an EMU meter to a Kirmes signup."""
    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")

    # Verify the meter exists
    meter = await _db.emu_meters.find_one({"id": data.emu_meter_id, "device_id": data.emu_device_id}, {"_id": 0})
    if not meter:
        raise HTTPException(status_code=404, detail="EMU-Zähler nicht gefunden")

    await _db.kirmes_signups.update_one(
        {"id": signup_id},
        {"$set": {
            "emu_device_id": data.emu_device_id,
            "emu_meter_id": data.emu_meter_id,
            "emu_meter_name": meter.get("meter_name", ""),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    updated = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    return updated


@router.delete("/signups/{signup_id}/link-meter")
async def unlink_meter_from_signup(signup_id: str, user: dict = Depends(_require_staff)):
    """Unlink an EMU meter from a Kirmes signup."""
    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")

    await _db.kirmes_signups.update_one(
        {"id": signup_id},
        {"$unset": {"emu_device_id": "", "emu_meter_id": "", "emu_meter_name": ""},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Zähler-Verknüpfung entfernt"}


@router.get("/signups/{signup_id}/meter-data")
async def get_signup_meter_data(
    signup_id: str,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    limit: int = Query(default=200, le=5000),
    user: dict = Depends(_require_staff),
):
    """Get EMU meter telemetry data for a linked signup."""
    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")

    device_id = signup.get("emu_device_id")
    meter_id = signup.get("emu_meter_id")
    if not device_id or not meter_id:
        return {"linked": False, "latest": None, "history": [], "meter_name": None}

    # Get latest reading
    latest = await _db.emu_data.find_one(
        {"device_id": device_id, "meter_id": meter_id},
        {"_id": 0},
        sort=[("ts_utc", -1)]
    )

    # Get historical data
    query = {"device_id": device_id, "meter_id": meter_id}
    if from_time or to_time:
        query["ts_utc"] = {}
        if from_time:
            query["ts_utc"]["$gte"] = from_time
        if to_time:
            query["ts_utc"]["$lte"] = to_time

    history = await _db.emu_data.find(
        query, {"_id": 0, "ts_utc": 1, "P_sum_kW": 1, "I_sum": 1, "U_L1": 1, "F_Hz": 1, "E_imp_kWh": 1}
    ).sort("ts_utc", -1).limit(limit).to_list(limit)
    history.reverse()

    # Check online status
    is_online = False
    if latest and latest.get("ts_utc"):
        try:
            last_ts = datetime.fromisoformat(latest["ts_utc"].replace("Z", "+00:00"))
            is_online = (datetime.now(timezone.utc) - last_ts).total_seconds() < 300
        except Exception:
            pass

    return {
        "linked": True,
        "meter_name": signup.get("emu_meter_name", ""),
        "is_online": is_online,
        "latest": latest,
        "history": history,
    }



# ============== QR Code System ==============

@router.get("/meters/{meter_id}/qr-code")
async def generate_meter_qr_code(meter_id: str, user: dict = Depends(_require_staff)):
    """Generate a QR code for a meter that links to the assignment page."""
    import qrcode
    import io as _io

    meter = await _db.emu_meters.find_one({"id": meter_id}, {"_id": 0})
    if not meter:
        raise HTTPException(status_code=404, detail="Zaehler nicht gefunden")

    # Build the QR URL
    import os
    base_url = os.environ.get("FRONTEND_URL", "")
    qr_url = f"{base_url}/kirmes/meter-zuordnung/{meter_id}"

    # Generate QR code
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = _io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return Response(content=buf.getvalue(), media_type="image/png",
                    headers={"Content-Disposition": f'inline; filename="meter_{meter_id[:8]}_qr.png"'})


@router.get("/meters/{meter_id}/qr-label")
async def generate_meter_qr_label(meter_id: str, token: Optional[str] = None, user: dict = Depends(_require_staff)):
    """Generate a printable QR label (QR code + meter info) as PDF."""
    import qrcode
    import io as _io
    from reportlab.lib.pagesizes import A6
    from reportlab.lib.units import mm as _mm
    from reportlab.pdfgen import canvas as _canvas

    meter = await _db.emu_meters.find_one({"id": meter_id}, {"_id": 0})
    if not meter:
        raise HTTPException(status_code=404, detail="Zaehler nicht gefunden")

    device = await _db.devices.find_one({"id": meter.get("device_id", "")}, {"_id": 0, "serial_number": 1, "name": 1})
    device_name = device.get("serial_number") or device.get("name", "") if device else ""

    import os
    base_url = os.environ.get("FRONTEND_URL", "")
    qr_url = f"{base_url}/kirmes/meter-zuordnung/{meter_id}"

    # Generate QR
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buf = _io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    # Generate PDF label (A6 size)
    from reportlab.lib.utils import ImageReader
    pdf_buf = _io.BytesIO()
    c = _canvas.Canvas(pdf_buf, pagesize=A6)
    w, h = A6

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2, h - 15 * _mm, "Eventenergie")
    c.setFont("Helvetica", 10)
    c.drawCentredString(w / 2, h - 22 * _mm, "Zaehler-Zuordnung")

    # QR Code
    qr_size = 45 * _mm
    qr_x = (w - qr_size) / 2
    c.drawImage(ImageReader(qr_buf), qr_x, h - 72 * _mm, qr_size, qr_size)

    # Meter info
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(w / 2, h - 80 * _mm, meter.get("meter_name", "Zaehler"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(w / 2, h - 86 * _mm, f"IP: {meter.get('meter_ip', '?')}")
    c.drawCentredString(w / 2, h - 91 * _mm, f"Geraet: {device_name}")
    c.setFont("Helvetica", 7)
    c.drawCentredString(w / 2, h - 98 * _mm, f"ID: {meter_id[:16]}...")

    c.save()
    pdf_buf.seek(0)

    return Response(content=pdf_buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="qr_label_{meter_id[:8]}.pdf"'})


@router.post("/meters/{meter_id}/assign-signup")
async def assign_meter_to_signup_via_qr(meter_id: str, data: dict, user: dict = Depends(_require_staff)):
    """Assign a meter to a signup (used from QR code scan page)."""
    signup_id = data.get("signup_id")
    if not signup_id:
        raise HTTPException(status_code=400, detail="signup_id fehlt")

    meter = await _db.emu_meters.find_one({"id": meter_id}, {"_id": 0})
    if not meter:
        raise HTTPException(status_code=404, detail="Zaehler nicht gefunden")

    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")

    await _db.kirmes_signups.update_one(
        {"id": signup_id},
        {"$set": {
            "emu_device_id": meter["device_id"],
            "emu_meter_id": meter_id,
            "emu_meter_name": meter.get("meter_name", ""),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    return {"message": f"Zaehler {meter.get('meter_name', '')} wurde der Anmeldung zugewiesen"}


@router.get("/meters/{meter_id}/info")
async def get_meter_info(meter_id: str, user: dict = Depends(_require_staff)):
    """Get meter info for the QR assignment page."""
    meter = await _db.emu_meters.find_one({"id": meter_id}, {"_id": 0})
    if not meter:
        raise HTTPException(status_code=404, detail="Zaehler nicht gefunden")

    device = await _db.devices.find_one({"id": meter.get("device_id", "")}, {"_id": 0, "serial_number": 1, "name": 1})
    device_name = device.get("serial_number") or device.get("name", "") if device else ""
    meter["device_name"] = device_name

    # Get current assignment if any
    current_signup = await _db.kirmes_signups.find_one(
        {"emu_meter_id": meter_id},
        {"_id": 0, "id": 1, "schausteller_id": 1, "event_id": 1}
    )
    if current_signup:
        sch = await _db.kirmes_schausteller.find_one(
            {"id": current_signup["schausteller_id"]},
            {"_id": 0, "id": 1, "name": 1, "vorname": 1, "firma": 1}
        )
        event = await _db.kirmes_events.find_one(
            {"id": current_signup["event_id"]},
            {"_id": 0, "id": 1, "name": 1}
        )
        meter["current_assignment"] = {
            "signup_id": current_signup["id"],
            "schausteller": sch,
            "event": event,
        }
    else:
        meter["current_assignment"] = None

    # Available signups (without meter) for quick assignment
    unlinked = await _db.kirmes_signups.find(
        {"emu_meter_id": {"$exists": False}},
        {"_id": 0, "id": 1, "schausteller_id": 1, "event_id": 1}
    ).to_list(100)

    # Also find ones where emu_meter_id is empty string or None
    unlinked2 = await _db.kirmes_signups.find(
        {"emu_meter_id": {"$in": [None, ""]}},
        {"_id": 0, "id": 1, "schausteller_id": 1, "event_id": 1}
    ).to_list(100)

    # Merge and dedupe
    seen = set()
    all_unlinked = []
    for s in unlinked + unlinked2:
        if s["id"] not in seen:
            seen.add(s["id"])
            all_unlinked.append(s)

    # Enrich with names
    for s in all_unlinked:
        sch = await _db.kirmes_schausteller.find_one({"id": s["schausteller_id"]}, {"_id": 0, "name": 1, "vorname": 1, "firma": 1})
        event = await _db.kirmes_events.find_one({"id": s["event_id"]}, {"_id": 0, "name": 1})
        s["schausteller_name"] = f"{sch.get('firma') or ''} {sch.get('vorname', '')} {sch.get('name', '')}".strip() if sch else "?"
        s["event_name"] = event.get("name", "?") if event else "?"

    meter["available_signups"] = all_unlinked

    return meter
