from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import bcrypt

import re

router = APIRouter(prefix="/api/kirmes", tags=["kirmes"])
security = HTTPBearer()

_db = None
_decode_jwt_token = None

# Standard connection types
CONNECTION_TYPES = ["Schuko", "16A", "32A", "63A", "125A", "Festanschluss"]
WOHNWAGEN_TYPES = ["Schuko", "16A CEE", "32A CEE"]


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def _validate_password(password: str):
    """Enforce strict password policy: min 8 chars, 1 digit, 1 uppercase, 1 lowercase, 1 special char."""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Passwort muss mindestens 8 Zeichen lang sein.")
    if not re.search(r'[0-9]', password):
        raise HTTPException(status_code=400, detail="Passwort muss mindestens eine Ziffer enthalten.")
    if not re.search(r'[A-Z]', password):
        raise HTTPException(status_code=400, detail="Passwort muss mindestens einen Großbuchstaben enthalten.")
    if not re.search(r'[a-z]', password):
        raise HTTPException(status_code=400, detail="Passwort muss mindestens einen Kleinbuchstaben enthalten.")
    if not re.search(r'[^A-Za-z0-9]', password):
        raise HTTPException(status_code=400, detail="Passwort muss mindestens ein Sonderzeichen enthalten.")


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
    wohnwagen_prices: Optional[List[StandardPrice]] = None
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
    custom_wohnwagen_prices: Optional[List[StandardPrice]] = None


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
    custom_wohnwagen_prices: Optional[List[StandardPrice]] = None


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
    prices = await _db.kirmes_standard_prices.find({"type": {"$ne": "global"}, "category": {"$ne": "wohnwagen"}}, {"_id": 0}).to_list(100)
    if not prices:
        now = datetime.now(timezone.utc).isoformat()
        defaults = []
        for ct in CONNECTION_TYPES:
            defaults.append({"id": str(uuid.uuid4()), "connection_type": ct, "price": 0.0, "avg_kwh": 0.0, "updated_at": now})
        await _db.kirmes_standard_prices.insert_many(defaults)
        prices = await _db.kirmes_standard_prices.find({"type": {"$ne": "global"}, "category": {"$ne": "wohnwagen"}}, {"_id": 0}).to_list(100)
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
    # Wohnwagen prices
    wohnwagen_prices = await _db.kirmes_standard_prices.find({"category": "wohnwagen"}, {"_id": 0}).to_list(100)
    if not wohnwagen_prices:
        now = datetime.now(timezone.utc).isoformat()
        ww_defaults = []
        for ct in WOHNWAGEN_TYPES:
            ww_defaults.append({"id": str(uuid.uuid4()), "category": "wohnwagen", "connection_type": ct, "price": 0.0, "avg_kwh": 0.0, "updated_at": now})
        await _db.kirmes_standard_prices.insert_many(ww_defaults)
        wohnwagen_prices = await _db.kirmes_standard_prices.find({"category": "wohnwagen"}, {"_id": 0}).to_list(100)
    ww_order = {t: i for i, t in enumerate(WOHNWAGEN_TYPES)}
    wohnwagen_prices.sort(key=lambda p: ww_order.get(p["connection_type"], 99))
    # Get global settings
    global_settings = await _db.kirmes_standard_prices.find_one({"type": "global"}, {"_id": 0})
    return {
        "prices": prices,
        "wohnwagen_prices": wohnwagen_prices,
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
    # Save wohnwagen prices
    if data.wohnwagen_prices:
        for p in data.wohnwagen_prices:
            await _db.kirmes_standard_prices.update_one(
                {"connection_type": p.connection_type, "category": "wohnwagen"},
                {"$set": {"price": p.price, "avg_kwh": p.avg_kwh, "category": "wohnwagen", "updated_at": now}},
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
    # Batch signup counts via aggregation instead of N+1 queries
    if events:
        event_ids = [e["id"] for e in events]
        pipeline = [
            {"$match": {"event_id": {"$in": event_ids}}},
            {"$group": {"_id": "$event_id", "count": {"$sum": 1}}}
        ]
        counts = {doc["_id"]: doc["count"] async for doc in _db.kirmes_signups.aggregate(pipeline)}
        for event in events:
            event["signup_count"] = counts.get(event["id"], 0)
    return events


@router.post("/events")
async def create_event(data: EventCreate, user: dict = Depends(_require_staff)):
    # Get prices
    if data.use_standard_prices:
        std_prices = await _db.kirmes_standard_prices.find({"type": {"$ne": "global"}, "category": {"$ne": "wohnwagen"}}, {"_id": 0}).to_list(100)
        prices = [{"connection_type": p["connection_type"], "price": p["price"], "avg_kwh": p.get("avg_kwh", 0.0)} for p in std_prices]
        ww_prices = await _db.kirmes_standard_prices.find({"category": "wohnwagen"}, {"_id": 0}).to_list(100)
        wohnwagen_prices = [{"connection_type": p["connection_type"], "price": p["price"], "avg_kwh": p.get("avg_kwh", 0.0)} for p in ww_prices]
        global_settings = await _db.kirmes_standard_prices.find_one({"type": "global"}, {"_id": 0})
        kwh_price = global_settings.get("kwh_price", 0.0) if global_settings else 0.0
        handling_surcharge = global_settings.get("handling_surcharge", 0.0) if global_settings else 0.0
    else:
        prices = [p.dict() for p in (data.custom_prices or [])]
        wohnwagen_prices = [p.dict() for p in (data.custom_wohnwagen_prices or [])]
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
        "wohnwagen_prices": wohnwagen_prices,
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
    # Get signups
    signups = await _db.kirmes_signups.find({"event_id": event_id}, {"_id": 0}).to_list(500)
    event["signup_count"] = len(signups)
    # Batch-load all Schausteller in one query instead of N+1
    sch_ids = list({s["schausteller_id"] for s in signups if s.get("schausteller_id")})
    if sch_ids:
        sch_docs = await _db.kirmes_schausteller.find({"id": {"$in": sch_ids}}, {"_id": 0}).to_list(len(sch_ids))
        sch_map = {s["id"]: s for s in sch_docs}
    else:
        sch_map = {}
    for signup in signups:
        sch = sch_map.get(signup.get("schausteller_id"))
        if sch:
            signup["schausteller"] = sch
    event["signups"] = signups
    return event


class EventPaymentMode(BaseModel):
    kauf_auf_rechnung: bool

@router.put("/events/{event_id}/payment-mode")
async def set_event_payment_mode(event_id: str, data: EventPaymentMode, user: dict = Depends(_require_staff)):
    """Toggle payment mode for entire event: Rechnung vs Kreditkarte/PayPal."""
    event = await _db.kirmes_events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")

    await _db.kirmes_events.update_one(
        {"id": event_id},
        {"$set": {"kauf_auf_rechnung": data.kauf_auf_rechnung}}
    )
    label = "Rechnung" if data.kauf_auf_rechnung else "Kreditkarte / PayPal"
    return {"message": f"Zahlungsart auf '{label}' gesetzt", "kauf_auf_rechnung": data.kauf_auf_rechnung}




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
    if data.custom_wohnwagen_prices is not None:
        update["wohnwagen_prices"] = [p.dict() for p in data.custom_wohnwagen_prices]
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



class EmailInvite(BaseModel):
    email: str
    name: str = ""

@router.post("/events/{event_id}/invite-email")
async def invite_by_email(event_id: str, data: EmailInvite, user: dict = Depends(_require_staff)):
    """Send registration link to a new email address for this event."""
    from email_service import send_email
    import os

    event = await _db.kirmes_events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")

    frontend_url = os.environ.get("FRONTEND_URL", "")
    signup_link = f"{frontend_url}/kirmes/anmeldung?event={event_id}"
    anrede = data.name or "Sehr geehrte Damen und Herren"
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
    <p style="color:#333;font-size:15px;line-height:1.6;">Hallo {anrede},</p>
    <p style="color:#555;font-size:14px;line-height:1.6;">
      Sie sind eingeladen zur Veranstaltung <strong>{event['name']}</strong>
      ({start} – {end}{', ' + event.get('location', '') if event.get('location') else ''}).
    </p>
    <p style="color:#555;font-size:14px;line-height:1.6;">
      Bitte registrieren Sie sich über den folgenden Link und melden Ihren Stromanschluss an:
    </p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{signup_link}" style="display:inline-block;background:#d946ef;color:#fff;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:15px;font-weight:600;">
        Jetzt registrieren &amp; anmelden
      </a>
    </div>
    <p style="color:#888;font-size:12px;line-height:1.5;">
      Falls Sie bereits registriert sind, melden Sie sich einfach mit Ihrer E-Mail-Adresse an.
    </p>
  </div>
  <div style="background:#fafafa;padding:16px 32px;border-top:1px solid #eee;">
    <p style="margin:0;color:#aaa;font-size:11px;text-align:center;">&copy; {datetime.now().year} Eventenergie Deutschland GmbH &amp; Co. KG</p>
  </div>
</div>
</body></html>"""

    subject = f"Einladung: {event['name']} – Stromanschluss anmelden"
    ok = send_email(data.email, subject, html)
    if not ok:
        raise HTTPException(status_code=500, detail="E-Mail konnte nicht gesendet werden")

    await _db.kirmes_invitations.update_one(
        {"event_id": event_id, "email": data.email},
        {"$set": {"sent_at": datetime.now(timezone.utc).isoformat(), "email": data.email, "name": data.name, "type": "email_invite"}},
        upsert=True
    )

    return {"message": f"Einladung an {data.email} gesendet"}




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
    kundennummer = await _get_next_kundennummer()
    sch_doc = {
        "id": sch_id,
        "kundennummer": kundennummer,
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
    import os
    import urllib.parse
    frontend_url = os.environ.get("FRONTEND_URL", "")
    verify_link = f"{frontend_url}/api/kirmes/public/verify-email-link?email={urllib.parse.quote(email)}&code={code}"

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
      Bitte bestätigen Sie Ihre E-Mail-Adresse mit einem Klick:
    </p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{verify_link}" style="display:inline-block;background:#d946ef;color:#fff;text-decoration:none;padding:14px 40px;border-radius:8px;font-size:16px;font-weight:600;">
        E-Mail bestätigen
      </a>
    </div>
    <p style="color:#888;font-size:12px;">Oder geben Sie diesen Code manuell ein: <strong style="color:#d946ef;letter-spacing:4px;">{code}</strong></p>
  </div>
  <div style="background:#fafafa;padding:16px 32px;border-top:1px solid #eee;">
    <p style="margin:0;color:#aaa;font-size:11px;text-align:center;">&copy; {datetime.now().year} Eventenergie Deutschland GmbH &amp; Co. KG</p>
  </div>
</div>
</body></html>"""
    send_email(email, "E-Mail bestätigen – Eventenergie", html)


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


@router.get("/public/verify-email-link")
async def verify_email_link(email: str = Query(...), code: str = Query(...)):
    """One-click email verification via link. Redirects to frontend."""
    import os
    frontend_url = os.environ.get("FRONTEND_URL", "")
    sch = await _db.kirmes_schausteller.find_one({"email": email}, {"_id": 0})
    if not sch:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{frontend_url}/kirmes/anmeldung?verify_error=not_found")
    if sch.get("email_verified"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{frontend_url}/kirmes/anmeldung?verified=1&email={email}")
    if sch.get("verification_code") != code:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{frontend_url}/kirmes/anmeldung?verify_error=invalid_code")
    await _db.kirmes_schausteller.update_one(
        {"email": email},
        {"$set": {"email_verified": True, "verification_code": None, "verified_at": datetime.now(timezone.utc).isoformat()}}
    )
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"{frontend_url}/kirmes/anmeldung?verified=1&email={email}")




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
    _validate_password(data.password)
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



class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    email: EmailStr
    code: str
    password: str


@router.post("/public/request-password-reset")
async def request_password_reset(data: PasswordResetRequest):
    """Send a reset code to the schausteller's email."""
    import random
    sch = await _db.kirmes_schausteller.find_one({"email": data.email}, {"_id": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Kein Konto mit dieser E-Mail gefunden.")
    if not sch.get("email_verified"):
        raise HTTPException(status_code=403, detail="E-Mail ist noch nicht verifiziert.")
    code = str(random.randint(100000, 999999))
    await _db.kirmes_schausteller.update_one(
        {"email": data.email},
        {"$set": {"reset_code": code, "reset_requested_at": datetime.now(timezone.utc).isoformat()}}
    )
    try:
        from email_service import send_email
        html = f"""<h2>Passwort zurücksetzen</h2>
        <p>Hallo {sch['name']},</p>
        <p>Ihr Code zum Zurücksetzen des Passworts lautet:</p>
        <h1 style="text-align:center;font-size:36px;letter-spacing:8px;color:#a21caf;">{code}</h1>
        <p>Falls Sie diese Anfrage nicht gestellt haben, ignorieren Sie diese E-Mail.</p>"""
        send_email(data.email, "Passwort zurücksetzen – Eventenergie Portal", html)
    except Exception:
        pass
    return {"message": "Ein Code wurde an Ihre E-Mail gesendet."}


@router.post("/public/confirm-password-reset")
async def confirm_password_reset(data: PasswordResetConfirm):
    """Verify reset code and set new password."""
    sch = await _db.kirmes_schausteller.find_one({"email": data.email}, {"_id": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Kein Konto gefunden.")
    if sch.get("reset_code") != data.code:
        raise HTTPException(status_code=400, detail="Ungültiger Code.")
    _validate_password(data.password)
    await _db.kirmes_schausteller.update_one(
        {"email": data.email},
        {"$set": {"password_hash": _hash_password(data.password), "reset_code": None, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    updated = await _db.kirmes_schausteller.find_one({"email": data.email}, {"_id": 0, "password_hash": 0, "verification_code": 0, "reset_code": 0})
    return updated


@router.get("/public/my-bookings")
async def get_my_bookings(schausteller_id: str = Query(...)):
    """Public endpoint - Get all bookings and invoices for a schausteller."""
    sch = await _db.kirmes_schausteller.find_one({"id": schausteller_id}, {"_id": 0, "password_hash": 0, "verification_code": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")

    signups = await _db.kirmes_signups.find({"schausteller_id": schausteller_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    # Batch-load events
    evt_ids = list({s["event_id"] for s in signups if s.get("event_id")})
    if evt_ids:
        evt_docs = await _db.kirmes_events.find({"id": {"$in": evt_ids}}, {"_id": 0, "id": 1, "name": 1, "location": 1, "start_date": 1, "end_date": 1}).to_list(len(evt_ids))
        evt_map = {e["id"]: e for e in evt_docs}
    else:
        evt_map = {}
    for s in signups:
        s["event"] = evt_map.get(s.get("event_id"), {})

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
        {"_id": 0, "id": 1, "name": 1, "location": 1, "start_date": 1, "end_date": 1, "prices": 1, "wohnwagen_prices": 1, "status": 1}
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
    sch = await _db.kirmes_schausteller.find_one({"id": data.schausteller_id}, {"_id": 0, "password_hash": 0, "verification_code": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")

    # Validate connection type
    all_types = CONNECTION_TYPES + WOHNWAGEN_TYPES
    if data.connection_type not in all_types:
        raise HTTPException(status_code=400, detail=f"Ungültiger Anschlusstyp: {data.connection_type}")

    # Validate payment method - "rechnung" allowed if event OR schausteller has kauf_auf_rechnung
    event_rechnung = event.get("kauf_auf_rechnung", False)
    sch_rechnung = sch.get("kauf_auf_rechnung", False)
    if data.payment_method == "rechnung" and not event_rechnung and not sch_rechnung:
        raise HTTPException(status_code=400, detail="Kauf auf Rechnung ist für diese Veranstaltung nicht freigeschaltet.")

    # If event forces Rechnung, override payment method
    if event_rechnung:
        data.payment_method = "rechnung"

    # Find price for this connection type
    # Wohnwagen signups use wohnwagen_prices, regular signups use regular prices
    price = 0.0
    is_wohnwagen = data.fahrgeschaeft == "Wohnwagen"
    if is_wohnwagen:
        for p in event.get("wohnwagen_prices", []):
            if p["connection_type"] == data.connection_type:
                price = p["price"]
                break
    else:
        for p in event.get("prices", []):
            if p["connection_type"] == data.connection_type:
                price = p["price"]
                break

    # Determine if upfront payment is required
    # "rechnung" (purchase on account) = immediate confirmation
    # "kreditkarte" / "paypal" = pending until payment confirmed
    requires_payment = data.payment_method != "rechnung"

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
        "payment_status": "pending_payment" if requires_payment else "ausstehend",
        "deposit_amount": 0.0,
        "meter_id": None,
        "meter_start": None,
        "meter_end": None,
        "kwh_used": None,
        "final_amount": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.kirmes_signups.insert_one(signup_doc)
    signup_doc.pop("_id", None)
    signup_doc["schausteller"] = sch

    # Only send confirmation email for "Kauf auf Rechnung" (immediate confirmation)
    if not requires_payment:
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
            {"kundennummer": {"$regex": search, "$options": "i"}},
            {"firma": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]
    schausteller = await _db.kirmes_schausteller.find(query, {"_id": 0, "password_hash": 0, "verification_code": 0}).sort("kundennummer", 1).to_list(500)
    return schausteller


@router.get("/schausteller/{sch_id}")
async def get_schausteller(sch_id: str, user: dict = Depends(_require_staff)):
    sch = await _db.kirmes_schausteller.find_one({"id": sch_id}, {"_id": 0, "password_hash": 0, "verification_code": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")
    # Get their signups
    signups = await _db.kirmes_signups.find({"schausteller_id": sch_id}, {"_id": 0}).to_list(100)
    # Batch-load events
    evt_ids = list({s["event_id"] for s in signups if s.get("event_id")})
    if evt_ids:
        evt_docs = await _db.kirmes_events.find({"id": {"$in": evt_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(evt_ids))
        evt_map = {e["id"]: e for e in evt_docs}
    else:
        evt_map = {}
    for s in signups:
        evt = evt_map.get(s.get("event_id"))
        s["event_name"] = evt["name"] if evt else "Unbekannt"
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
    _validate_password(data.password)
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

@router.post("/schausteller/migrate-kundennummern")
async def migrate_kundennummern(admin: dict = Depends(_require_admin)):
    """Einmalige Migration: Weist bestehenden Schaustellern ohne Kundennummer eine fortlaufende K-XXXX zu."""
    without = await _db.kirmes_schausteller.find(
        {"$or": [{"kundennummer": {"$exists": False}}, {"kundennummer": None}]},
        {"_id": 0, "id": 1, "firma": 1, "created_at": 1}
    ).sort("created_at", 1).to_list(10000)

    assigned = []
    for sch in without:
        knr = await _get_next_kundennummer()
        await _db.kirmes_schausteller.update_one({"id": sch["id"]}, {"$set": {"kundennummer": knr}})
        assigned.append({"id": sch["id"], "firma": sch.get("firma"), "kundennummer": knr})

    # Backfill: Kundennummer in bestehende Rechnungen eintragen (laeuft immer)
    inv_fixed = 0
    all_sch = await _db.kirmes_schausteller.find({}, {"_id": 0, "id": 1, "kundennummer": 1}).to_list(10000)
    sch_map = {s["id"]: s.get("kundennummer", "") for s in all_sch}
    invoices = await _db.kirmes_invoices.find(
        {"$or": [{"schausteller_kundennummer": {"$exists": False}}, {"schausteller_kundennummer": None}, {"schausteller_kundennummer": ""}]},
        {"_id": 0, "id": 1, "schausteller_id": 1}
    ).to_list(10000)
    for inv in invoices:
        knr = sch_map.get(inv.get("schausteller_id"), "")
        if knr:
            await _db.kirmes_invoices.update_one({"id": inv["id"]}, {"$set": {"schausteller_kundennummer": knr}})
            inv_fixed += 1

    return {"message": f"{len(assigned)} Kundennummern vergeben, {inv_fixed} Rechnungen aktualisiert", "count": len(assigned), "invoices_fixed": inv_fixed, "assigned": assigned}



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



async def _get_next_kundennummer() -> str:
    """Generate next customer number: K-XXXX (sequential)."""
    last = await _db.kirmes_schausteller.find_one(
        {"kundennummer": {"$exists": True, "$ne": None}},
        {"_id": 0, "kundennummer": 1},
        sort=[("kundennummer", -1)]
    )
    if last and last.get("kundennummer"):
        try:
            num = int(last["kundennummer"].split("-")[1]) + 1
        except (IndexError, ValueError):
            num = 1
    else:
        num = 1
    return f"K-{num:04d}"


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


async def _auto_set_kwh_ausbau(signup: dict) -> dict:
    """Setzt kwh_ausbau automatisch vom letzten EMU-Zaehlerstand, falls ein Meter verknuepft ist."""
    emu_device_id = signup.get("emu_device_id")
    emu_meter_id = signup.get("emu_meter_id")
    if not emu_device_id or not emu_meter_id:
        return signup

    # Nur setzen wenn kwh_ausbau noch nicht manuell gesetzt wurde
    if signup.get("kwh_ausbau"):
        return signup

    latest = await _db.emu_data.find_one(
        {"device_id": emu_device_id, "meter_id": emu_meter_id},
        {"_id": 0, "E_imp_kWh": 1},
        sort=[("ts_utc", -1)]
    )
    if latest and latest.get("E_imp_kWh") is not None:
        kwh_ausbau = round(float(latest["E_imp_kWh"]), 2)
        kwh_einbau = signup.get("kwh_einbau", 0) or 0
        kwh_used = round(max(0, kwh_ausbau - kwh_einbau), 2)

        await _db.kirmes_signups.update_one(
            {"id": signup["id"]},
            {"$set": {"kwh_ausbau": kwh_ausbau, "kwh_used": kwh_used, "meter_end": kwh_ausbau}}
        )
        signup["kwh_ausbau"] = kwh_ausbau
        signup["kwh_used"] = kwh_used
        signup["meter_end"] = kwh_ausbau

    return signup


def _calculate_invoice(signups: list, event: dict, schausteller: dict) -> dict:
    """Calculate invoice amounts for all signups of a schausteller."""
    line_items = []
    pos = 1

    for signup in signups:
        # 1. Connection fee (Anschlussgebühr)
        conn_fee = signup.get("price", 0)
        conn_type = signup.get("connection_type", "")
        fahrgeschaeft = signup.get("fahrgeschaeft", "")
        label = f"{fahrgeschaeft} – " if fahrgeschaeft else ""
        line_items.append({
            "pos": pos, "description": f"Stromanschluss {conn_type} – Platz {signup.get('platznummer', '')}\n{label}{conn_type}",
            "quantity": "1", "unit": "pauschal", "unit_price": conn_fee, "total": conn_fee,
        })
        pos += 1

        # 2. kWh consumption
        kwh_start = signup.get("kwh_einbau") or signup.get("kwh_start") or 0
        kwh_end = signup.get("kwh_ausbau") or signup.get("kwh_end") or 0
        kwh_used = max(0, kwh_end - kwh_start)
        kwh_price = event.get("kwh_price", 0)

        if kwh_used > 0 or kwh_start > 0 or kwh_end > 0:
            kwh_total = round(kwh_used * kwh_price, 2)
            line_items.append({
                "pos": pos,
                "description": f"Energieverbrauch Platz {signup.get('platznummer', '')}\nZählerstand Einbau: {kwh_start:.2f} kWh\nZählerstand Ausbau: {kwh_end:.2f} kWh\nVerbrauch: {kwh_used:.2f} kWh",
                "quantity": f"{kwh_used:.2f}", "unit": "kWh", "unit_price": kwh_price, "total": kwh_total,
            })
            pos += 1

            # 3. Handling surcharge
            handling_per_kwh = event.get("handling_surcharge", 0)
            if handling_per_kwh > 0:
                handling_total = round(kwh_used * handling_per_kwh, 2)
                line_items.append({
                    "pos": pos,
                    "description": f"Handlingpauschale Platz {signup.get('platznummer', '')} ({kwh_used:.2f} kWh)",
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
    """Generate a combined invoice for ALL signups of the same schausteller in the same event."""
    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")

    event = await _db.kirmes_events.find_one({"id": signup["event_id"]}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")
    sch = await _db.kirmes_schausteller.find_one({"id": signup["schausteller_id"]}, {"_id": 0, "password_hash": 0, "verification_code": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")

    # Find ALL signups of this schausteller for this event
    all_signups = await _db.kirmes_signups.find(
        {"event_id": signup["event_id"], "schausteller_id": signup["schausteller_id"]},
        {"_id": 0}
    ).to_list(100)

    # Check if any of these signups already has an invoice
    signup_ids = [s["id"] for s in all_signups]
    existing = await _db.kirmes_invoices.find_one({"signup_ids": {"$in": signup_ids}}, {"_id": 0})
    if not existing:
        existing = await _db.kirmes_invoices.find_one({"signup_id": {"$in": signup_ids}}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail=f"Rechnung {existing['invoice_number']} existiert bereits für diesen Schausteller.")

    # Auto-set kwh_ausbau for all signups
    processed_signups = []
    for s in all_signups:
        s = await _auto_set_kwh_ausbau(s)
        processed_signups.append(s)

    calc = _calculate_invoice(processed_signups, event, sch)
    inv_number = await _get_next_invoice_number()

    invoice_doc = {
        "id": str(uuid.uuid4()),
        "invoice_number": inv_number,
        "signup_ids": signup_ids,
        "signup_id": signup_ids[0],
        "event_id": signup["event_id"],
        "event_name": event.get("name", ""),
        "schausteller_id": signup["schausteller_id"],
        "schausteller_kundennummer": sch.get("kundennummer", ""),
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

    # Update ALL signups status
    for sid in signup_ids:
        await _db.kirmes_signups.update_one(
            {"id": sid},
            {"$set": {"invoice_id": invoice_doc["id"], "invoice_number": inv_number, "payment_status": "abgerechnet"}}
        )

    # Auto-save invoice PDF to Dokumentenverwaltung (Rechnungsausgang)
    try:
        from services.invoice_pdf import generate_invoice_pdf
        from routes.documents import _ensure_year_month_subfolder, _save_to_local_storage, put_object, db as doc_db

        pdf_bytes = generate_invoice_pdf(invoice_doc)
        filename = f"{inv_number}.pdf"
        inv_date = invoice_doc.get("created_at", datetime.now(timezone.utc).isoformat())
        subfolder_id = await _ensure_year_month_subfolder("rechnungsausgang", inv_date)
        storage_path = f"eventenergie-docs/uploads/{uuid.uuid4()}.pdf"
        put_object(storage_path, pdf_bytes, "application/pdf")

        doc_entry = {
            "id": str(uuid.uuid4()),
            "storage_path": storage_path,
            "original_filename": filename,
            "content_type": "application/pdf",
            "size": len(pdf_bytes),
            "folder_id": subfolder_id,
            "ai_status": "completed",
            "ai_metadata": {
                "document_type": "rechnung",
                "suggested_folder": "rechnungsausgang",
                "sender": "Eventenergie Deutschland GmbH & Co. KG",
                "recipient": sch.get("firma", sch.get("name", "")),
                "date": inv_date[:10] if len(inv_date) >= 10 else inv_date,
                "subject": f"Ausgangsrechnung {inv_number} - {event.get('name', '')}",
                "amount": calc.get("brutto"),
                "currency": "EUR",
                "invoice_number": inv_number,
                "reference": f"Event: {event.get('name', '')}",
                "tax_amount": calc.get("mwst_amount"),
            },
            "full_text": f"Rechnung {inv_number} {sch.get('firma', '')} {event.get('name', '')} {calc.get('brutto', 0):.2f} EUR",
            "keywords": [inv_number, sch.get("firma", ""), event.get("name", ""), "Ausgangsrechnung"],
            "is_deleted": False,
            "datev_forwarded": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await doc_db.documents.insert_one(doc_entry)
        await _save_to_local_storage(pdf_bytes, filename, subfolder_id)
        import logging as _log
        _log.getLogger(__name__).info(f"Invoice {inv_number} auto-saved to Dokumentenverwaltung (folder: {subfolder_id})")
    except Exception as doc_err:
        import logging as _log
        _log.getLogger(__name__).warning(f"Document storage for invoice {inv_number} failed: {doc_err}")

    return invoice_doc


@router.post("/events/{event_id}/generate-invoices")
async def generate_all_invoices(event_id: str, user: dict = Depends(_require_staff)):
    """Generate one combined invoice per schausteller for all their signups in an event."""
    event = await _db.kirmes_events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")

    signups = await _db.kirmes_signups.find({"event_id": event_id}, {"_id": 0}).to_list(500)
    generated = []
    skipped = []

    # Group signups by schausteller_id
    from collections import defaultdict
    grouped = defaultdict(list)
    for signup in signups:
        grouped[signup["schausteller_id"]].append(signup)

    for schausteller_id, sch_signups in grouped.items():
        # Check if any signup already has an invoice
        sch_signup_ids = [s["id"] for s in sch_signups]
        has_invoice = False
        for sid in sch_signup_ids:
            existing = await _db.kirmes_invoices.find_one(
                {"$or": [{"signup_id": sid}, {"signup_ids": sid}]}, {"_id": 0}
            )
            if existing:
                skipped.append({"schausteller_id": schausteller_id, "invoice_number": existing["invoice_number"], "reason": "Bereits abgerechnet"})
                has_invoice = True
                break
        if has_invoice:
            continue

        sch = await _db.kirmes_schausteller.find_one({"id": schausteller_id}, {"_id": 0, "password_hash": 0, "verification_code": 0})
        if not sch:
            skipped.append({"schausteller_id": schausteller_id, "reason": "Schausteller nicht gefunden"})
            continue

        # Auto-set kwh_ausbau for all signups
        processed_signups = []
        for s in sch_signups:
            s = await _auto_set_kwh_ausbau(s)
            processed_signups.append(s)

        calc = _calculate_invoice(processed_signups, event, sch)
        inv_number = await _get_next_invoice_number()

        invoice_doc = {
            "id": str(uuid.uuid4()),
            "invoice_number": inv_number,
            "signup_ids": sch_signup_ids,
            "signup_id": sch_signup_ids[0],
            "event_id": event_id,
            "event_name": event.get("name", ""),
            "schausteller_id": schausteller_id,
            "schausteller_kundennummer": sch.get("kundennummer", ""),
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

        for sid in sch_signup_ids:
            await _db.kirmes_signups.update_one(
                {"id": sid},
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
                send_email_with_attachment(sch_email, subject, html, pdf_bytes, filename, bcc=["d5aa2eb6-6bae-417a-8894-664a6eb160c8@uploadmail.datev.de"])
                await _db.kirmes_invoices.update_one(
                    {"id": invoice_doc["id"]},
                    {"$set": {"status": "versendet", "sent_at": datetime.now(timezone.utc).isoformat(), "sent_to": sch_email}}
                )
        except Exception:
            pass  # Don't fail batch if single email fails

        # Store invoice PDF in Dokumentenverwaltung (Rechnungsausgang)
        try:
            from routes.documents import _ensure_year_month_subfolder, _save_to_local_storage, put_object, db as doc_db
            import uuid as _uuid

            inv_date = invoice_doc.get("created_at", datetime.now(timezone.utc).isoformat())
            subfolder_id = await _ensure_year_month_subfolder("rechnungsausgang", inv_date)
            storage_path = f"eventenergie-docs/uploads/{_uuid.uuid4()}.pdf"
            cloud_path = None
            try:
                put_object(storage_path, pdf_bytes, "application/pdf")
                cloud_path = storage_path
            except Exception:
                pass
            final_path = cloud_path or f"local://{storage_path}"

            doc_entry = {
                "id": str(_uuid.uuid4()),
                "storage_path": final_path,
                "original_filename": filename,
                "content_type": "application/pdf",
                "size": len(pdf_bytes),
                "folder_id": subfolder_id,
                "ai_status": "completed",
                "ai_metadata": {
                    "document_type": "rechnung",
                    "suggested_folder": "rechnungsausgang",
                    "sender": "Eventenergie Deutschland GmbH & Co. KG",
                    "recipient": sch.get("firma", sch.get("name", "")),
                    "date": inv_date[:10] if len(inv_date) >= 10 else inv_date,
                    "subject": f"Ausgangsrechnung {inv_number} - {event.get('name', '')}",
                    "amount": calc.get("brutto"),
                    "currency": "EUR",
                    "invoice_number": inv_number,
                    "reference": f"Event: {event.get('name', '')}",
                    "tax_amount": calc.get("mwst_amount"),
                },
                "full_text": f"Rechnung {inv_number} {sch.get('firma', '')} {event.get('name', '')} {calc.get('brutto', 0):.2f} EUR",
                "keywords": [inv_number, sch.get("firma", ""), event.get("name", ""), "Ausgangsrechnung"],
                "is_deleted": False,
                "datev_forwarded": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await doc_db.documents.insert_one(doc_entry)

            # Save locally
            await _save_to_local_storage(pdf_bytes, filename, subfolder_id)
        except Exception as doc_err:
            logger.warning(f"Document storage for invoice {inv_number} failed: {doc_err}")

        generated.append({"schausteller_id": schausteller_id, "schausteller_firma": sch.get("firma", ""), "invoice_number": inv_number, "brutto": calc["brutto"], "signups_count": len(sch_signups)})

    # Update event status
    await _db.kirmes_events.update_one({"id": event_id}, {"$set": {"status": "abgerechnet"}})

    return {"generated": len(generated), "skipped": len(skipped), "invoices": generated, "skipped_details": skipped}


@router.post("/events/{event_id}/reset-invoices")
async def reset_and_regenerate_invoices(event_id: str, user: dict = Depends(_require_admin)):
    """Delete all invoices for an event and reset signup payment status, so invoices can be regenerated."""
    event = await _db.kirmes_events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")

    deleted = await _db.kirmes_invoices.delete_many({"event_id": event_id})
    await _db.kirmes_signups.update_many(
        {"event_id": event_id},
        {"$unset": {"invoice_id": "", "invoice_number": ""}, "$set": {"payment_status": "offen"}}
    )
    await _db.kirmes_events.update_one({"id": event_id}, {"$set": {"status": "freigegeben"}})

    return {"message": f"{deleted.deleted_count} Rechnungen gelöscht. Anmeldungen zurückgesetzt. Rechnungen können neu erstellt werden."}



@router.get("/invoices")
async def list_invoices(
    search: Optional[str] = None,
    event_id: Optional[str] = None,
    user: dict = Depends(_require_staff)
):
    """List/search invoices. Requires staff + can_billing or admin."""
    if user.get("role") != "admin" and not user.get("permissions", {}).get("can_billing"):
        raise HTTPException(status_code=403, detail="Keine Berechtigung für Rechnungen")

    query = {}
    if event_id:
        query["event_id"] = event_id
    if search:
        query["$or"] = [
            {"invoice_number": {"$regex": search, "$options": "i"}},
            {"schausteller_firma": {"$regex": search, "$options": "i"}},
            {"schausteller_name": {"$regex": search, "$options": "i"}},
            {"schausteller_kundennummer": {"$regex": search, "$options": "i"}},
            {"event_name": {"$regex": search, "$options": "i"}},
        ]
    invoices = await _db.kirmes_invoices.find(query, {
        "_id": 0, "id": 1, "invoice_number": 1, "event_name": 1, "event_id": 1,
        "schausteller_id": 1, "schausteller_firma": 1, "schausteller_name": 1, "schausteller_email": 1,
        "schausteller_kundennummer": 1,
        "invoice_date": 1, "netto": 1, "brutto": 1, "status": 1, "sent_at": 1, "created_at": 1,
        "payment_status": 1, "paid_at": 1, "paid_amount": 1, "payment_note": 1, "due_date": 1,
    }).sort("invoice_number", 1).to_list(5000)

    # Berechne Faelligkeitsstatus fuer jede Rechnung
    # Zahlungsziel: Rechnungsdatum + 14 Tage
    # Mahnung: ab 17 Tage nach Rechnungsdatum (3 Tage nach Faelligkeit)
    now = datetime.now(timezone.utc)
    for inv in invoices:
        ps = inv.get("payment_status", "offen")
        if ps == "bezahlt":
            inv["payment_status"] = "bezahlt"
        elif inv.get("sent_at"):
            inv.setdefault("payment_status", "offen")
            try:
                inv_date = datetime.strptime(inv.get("invoice_date", ""), "%d.%m.%Y").replace(tzinfo=timezone.utc)
                days_since = (now - inv_date).days
                inv["days_since_invoice"] = days_since
                if ps != "bezahlt" and days_since > 17:
                    inv["payment_status"] = "ueberfaellig"
                elif ps != "bezahlt" and days_since > 14:
                    inv["payment_status"] = "faellig"
                else:
                    inv["payment_status"] = "offen"
            except (ValueError, TypeError):
                pass
        else:
            inv["payment_status"] = "erstellt"

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


class PaymentStatusUpdate(BaseModel):
    payment_status: str  # "bezahlt", "offen", "teilweise_bezahlt"
    paid_amount: Optional[float] = None
    payment_note: Optional[str] = None


@router.put("/invoices/{invoice_id}/payment-status")
async def update_payment_status(invoice_id: str, data: PaymentStatusUpdate, user: dict = Depends(_require_staff)):
    """Update payment status of an invoice."""
    if user.get("role") != "admin" and not user.get("permissions", {}).get("can_billing"):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    inv = await _db.kirmes_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    update = {
        "payment_status": data.payment_status,
        "payment_updated_at": datetime.now(timezone.utc).isoformat(),
        "payment_updated_by": user.get("name", ""),
    }
    if data.payment_status == "bezahlt":
        update["paid_at"] = datetime.now(timezone.utc).isoformat()
        update["paid_amount"] = data.paid_amount or inv.get("brutto", 0)
    if data.payment_note:
        update["payment_note"] = data.payment_note

    await _db.kirmes_invoices.update_one({"id": invoice_id}, {"$set": update})
    return {"message": "Zahlungsstatus aktualisiert", "payment_status": data.payment_status}



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
        accounting_bcc = ["d5aa2eb6-6bae-417a-8894-664a6eb160c8@uploadmail.datev.de"]
        send_email_with_attachment(sch_email, subject, html, pdf_bytes, filename, bcc=accounting_bcc)
        await _db.kirmes_invoices.update_one(
            {"id": invoice_id},
            {"$set": {"status": "versendet", "sent_at": datetime.now(timezone.utc).isoformat(), "sent_to": sch_email}}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"E-Mail konnte nicht gesendet werden: {str(e)}")

    # Save invoice PDF to Dokumentenverwaltung (Rechnungsausgang) if not already there
    try:
        from routes.documents import _ensure_year_month_subfolder, _save_to_local_storage, put_object, db as doc_db

        inv_number = inv["invoice_number"]
        existing_doc = await doc_db.documents.find_one(
            {"original_filename": filename, "is_deleted": False}, {"_id": 0, "id": 1}
        )
        if not existing_doc:
            inv_date = inv.get("created_at", datetime.now(timezone.utc).isoformat())
            subfolder_id = await _ensure_year_month_subfolder("rechnungsausgang", inv_date)
            storage_path = f"eventenergie-docs/uploads/{uuid.uuid4()}.pdf"
            cloud_path = None
            try:
                put_object(storage_path, pdf_bytes, "application/pdf")
                cloud_path = storage_path
            except Exception:
                pass
            final_path = cloud_path or f"local://{storage_path}"

            sch_data = inv.get("schausteller", {})
            doc_entry = {
                "id": str(uuid.uuid4()),
                "storage_path": final_path,
                "original_filename": filename,
                "content_type": "application/pdf",
                "size": len(pdf_bytes),
                "folder_id": subfolder_id,
                "ai_status": "completed",
                "ai_metadata": {
                    "document_type": "rechnung",
                    "suggested_folder": "rechnungsausgang",
                    "sender": "Eventenergie Deutschland GmbH & Co. KG",
                    "recipient": sch_data.get("firma", sch_data.get("name", "")),
                    "date": inv_date[:10] if len(inv_date) >= 10 else inv_date,
                    "subject": f"Ausgangsrechnung {inv_number} - {inv.get('event_name', '')}",
                    "amount": inv.get("brutto"),
                    "currency": "EUR",
                    "invoice_number": inv_number,
                    "reference": f"Event: {inv.get('event_name', '')}",
                    "tax_amount": inv.get("mwst_amount"),
                },
                "full_text": f"Rechnung {inv_number} {sch_data.get('firma', '')} {inv.get('event_name', '')} {inv.get('brutto', 0):.2f} EUR",
                "keywords": [inv_number, sch_data.get("firma", ""), inv.get("event_name", ""), "Ausgangsrechnung"],
                "is_deleted": False,
                "datev_forwarded": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await doc_db.documents.insert_one(doc_entry)
            await _save_to_local_storage(pdf_bytes, filename, subfolder_id)
            import logging as _log
            _log.getLogger(__name__).info(f"Invoice {inv_number} saved to Dokumentenverwaltung via send")
    except Exception as doc_err:
        import logging as _log
        _log.getLogger(__name__).warning(f"Document storage for invoice {inv.get('invoice_number', '')} on send failed: {doc_err}")

    return {"message": f"Rechnung an {sch_email} versendet (DATEV + Dokumentenablage)."}



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

    # Auto-capture current kWh reading as Einbaustand
    kwh_einbau = None
    latest = await _db.emu_data.find_one(
        {"device_id": data.emu_device_id, "meter_id": data.emu_meter_id},
        {"_id": 0, "E_imp_kWh": 1},
        sort=[("ts_utc", -1)]
    )
    if latest and latest.get("E_imp_kWh") is not None:
        kwh_einbau = round(float(latest["E_imp_kWh"]), 2)

    update_fields = {
        "emu_device_id": data.emu_device_id,
        "emu_meter_id": data.emu_meter_id,
        "emu_meter_name": meter.get("meter_name", ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if kwh_einbau is not None:
        update_fields["kwh_einbau"] = kwh_einbau
        update_fields["meter_start"] = kwh_einbau

    await _db.kirmes_signups.update_one({"id": signup_id}, {"$set": update_fields})
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
    limit: int = Query(default=90000, le=100000),
    user: dict = Depends(_require_staff),
):
    """Get EMU meter telemetry data for a linked signup."""
    _METER_PROJECTION = {
        "_id": 0, "ts_utc": 1,
        "P_sum_kW": 1, "P_L1_kW": 1, "P_L2_kW": 1, "P_L3_kW": 1,
        "I_sum": 1, "I_L1": 1, "I_L2": 1, "I_L3": 1,
        "U_L1": 1, "U_L2": 1, "U_L3": 1,
        "F_Hz": 1, "E_imp_kWh": 1,
    }

    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")

    device_id = signup.get("emu_device_id")
    meter_id = signup.get("emu_meter_id")
    if not device_id or not meter_id:
        return {"linked": False, "latest": None, "history": [], "meter_name": None}

    base_filter = {"device_id": device_id, "meter_id": meter_id}

    # Get latest reading (only needed fields)
    latest = await _db.emu_data.find_one(base_filter, _METER_PROJECTION, sort=[("ts_utc", -1)])

    # Auto-backfill kwh_einbau if missing but live data available
    if signup.get("kwh_einbau") is None and latest and latest.get("E_imp_kWh") is not None:
        kwh_val = round(float(latest["E_imp_kWh"]), 2)
        await _db.kirmes_signups.update_one(
            {"id": signup_id},
            {"$set": {"kwh_einbau": kwh_val, "meter_start": kwh_val}}
        )

    # Get historical data with time filter
    query = dict(base_filter)
    if from_time or to_time:
        query["ts_utc"] = {}
        if from_time:
            query["ts_utc"]["$gte"] = from_time
        if to_time:
            query["ts_utc"]["$lte"] = to_time

    history = await _db.emu_data.find(
        query, _METER_PROJECTION
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




@router.get("/devices/{device_id}/qr-label/{meter_index}")
async def generate_single_qr_label(device_id: str, meter_index: int, user: dict = Depends(_require_staff)):
    """Generate a simple QR label for a single meter (QR code + 'Zaehler X')."""
    import qrcode
    import io as _io
    from reportlab.lib.units import mm as _mm
    from reportlab.pdfgen import canvas as _canvas
    from reportlab.lib.utils import ImageReader

    meters = await _db.emu_meters.find({"device_id": device_id}, {"_id": 0}).sort("meter_name", 1).to_list(20)
    if meter_index < 1 or meter_index > len(meters):
        raise HTTPException(status_code=404, detail="Zaehler nicht gefunden")

    meter = meters[meter_index - 1]

    import os
    base_url = os.environ.get("FRONTEND_URL", "")
    qr_url = f"{base_url}/kirmes/meter-zuordnung/{meter['id']}"

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_io = _io.BytesIO()
    qr_img.save(qr_io, format="PNG")
    qr_io.seek(0)

    # Small label: 60x70mm
    label_w = 60 * _mm
    label_h = 70 * _mm
    pdf_buf = _io.BytesIO()
    c = _canvas.Canvas(pdf_buf, pagesize=(label_w, label_h))

    # QR Code centered
    qr_size = 45 * _mm
    qr_x = (label_w - qr_size) / 2
    c.drawImage(ImageReader(qr_io), qr_x, 15 * _mm, qr_size, qr_size)

    # "Zaehler X" text below
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(label_w / 2, 5 * _mm, f"Zaehler {meter_index}")

    c.save()
    pdf_buf.seek(0)

    return Response(
        content=pdf_buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="qr_zaehler_{meter_index}.pdf"'},
    )


@router.post("/devices/{device_id}/print-label/{meter_index}")
async def print_meter_label(device_id: str, meter_index: int, user: dict = Depends(_require_staff)):
    """Generate a 32x57mm label and print directly to Dymo LabelWriter."""
    import qrcode
    import io as _io
    import os
    from PIL import Image, ImageDraw, ImageFont

    # Find device and meters
    device = await _db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    meters = await _db.emu_meters.find({"device_id": device_id}, {"_id": 0}).sort("meter_name", 1).to_list(20)
    if meter_index < 1 or meter_index > len(meters):
        raise HTTPException(status_code=404, detail="Zähler nicht gefunden")

    meter = meters[meter_index - 1]
    device_name = device.get("serial_number", device_id[:12])

    # QR URL
    base_url = os.environ.get("FRONTEND_URL", "")
    qr_url = f"{base_url}/kirmes/meter-zuordnung/{meter['id']}"

    # Label dimensions: 32mm wide x 57mm tall (PORTRAIT - Dymo driver rotates internally)
    DPI = 300
    LABEL_W_MM = 32
    LABEL_H_MM = 57
    label_w = int(LABEL_W_MM * DPI / 25.4)   # ~378 px
    label_h = int(LABEL_H_MM * DPI / 25.4)   # ~673 px

    # Generate QR code
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=1)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # QR sized to fill most of label width
    qr_target = int(label_w * 0.82)  # ~310px = ~26mm
    qr_img = qr_img.resize((qr_target, qr_target), Image.NEAREST)

    # Create label image (portrait)
    label = Image.new("RGB", (label_w, label_h), "white")
    draw = ImageDraw.Draw(label)

    # Load font
    font = None
    for font_path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\calibri.ttf",
    ]:
        try:
            font = ImageFont.truetype(font_path, 28)
            break
        except (OSError, IOError):
            continue
    if not font:
        font = ImageFont.load_default()

    # Layout: everything centered vertically and horizontally
    text_line1 = f"Zaehler {meter_index}"
    text_line2 = device_name

    # Measure text
    bbox1 = draw.textbbox((0, 0), text_line1, font=font)
    bbox2 = draw.textbbox((0, 0), text_line2, font=font)
    th1 = bbox1[3] - bbox1[1]
    th2 = bbox2[3] - bbox2[1]

    # Total content height: QR + gap + text1 + gap + text2
    total_h = qr_target + 15 + th1 + 6 + th2
    start_y = (label_h - total_h) // 2

    # QR Code - centered
    qr_x = (label_w - qr_target) // 2
    label.paste(qr_img, (qr_x, start_y))

    # Text below QR
    text_y = start_y + qr_target + 15
    tw1 = bbox1[2] - bbox1[0]
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((label_w - tw1) / 2, text_y), text_line1, fill="black", font=font)
    draw.text(((label_w - tw2) / 2, text_y + th1 + 6), text_line2, fill="black", font=font)

    # Convert to PNG bytes (portrait - Dymo driver rotates to landscape internally)
    img_buf = _io.BytesIO()
    label.save(img_buf, format="PNG", dpi=(DPI, DPI))
    img_bytes = img_buf.getvalue()

    # Try to print directly on Windows
    printer_name = os.environ.get("DYMO_PRINTER_NAME", "")
    print_success = False
    print_error = ""

    if printer_name:
        try:
            import win32print
            import win32ui
            import win32con
            from PIL import ImageWin

            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(printer_name)
            hdc.StartDoc(f"QR Label - Zaehler {meter_index}")
            hdc.StartPage()

            # Get printable area
            printable_w = hdc.GetDeviceCaps(8)   # HORZRES
            printable_h = hdc.GetDeviceCaps(10)  # VERTRES

            # Print the image scaled to fit printable area
            label_for_print = label.convert("RGB")
            dib = ImageWin.Dib(label_for_print)
            dib.draw(hdc.GetHandleOutput(), (0, 0, printable_w, printable_h))

            hdc.EndPage()
            hdc.EndDoc()
            hdc.DeleteDC()
            print_success = True
        except ImportError:
            print_error = "win32print nicht verfuegbar (nur auf Windows)"
        except Exception as e:
            print_error = str(e)

    # Return result
    if print_success:
        return {"success": True, "message": f"Label fuer Zaehler {meter_index} ({device_name}) gedruckt"}
    elif printer_name and print_error:
        # Printer configured but failed - return image as fallback + error
        img_buf.seek(0)
        return Response(
            content=img_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": f'inline; filename="label_zaehler_{meter_index}.png"',
                "X-Print-Error": print_error,
            },
        )
    else:
        # No printer configured - return image
        img_buf.seek(0)
        return Response(
            content=img_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f'inline; filename="label_zaehler_{meter_index}.png"'},
        )


@router.post("/devices/{device_id}/print-device-label")
async def print_device_label(device_id: str, user: dict = Depends(_require_staff)):
    """Generate and print a device QR code label (32x57mm) on Dymo LabelWriter."""
    import qrcode
    import io as _io
    import os
    from PIL import Image, ImageDraw, ImageFont

    device = await _db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    device_code = device.get("device_code", "")
    serial_number = device.get("serial_number", "")
    if not device_code:
        raise HTTPException(status_code=400, detail="Kein Geräte-Code vorhanden")

    # Label dimensions: 32mm wide x 57mm tall (portrait - Dymo driver rotates)
    DPI = 300
    label_w = int(32 * DPI / 25.4)   # ~378 px
    label_h = int(57 * DPI / 25.4)   # ~673 px

    # Generate QR code from device_code
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=1)
    qr.add_data(device_code)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # QR sized to ~82% of label width
    qr_target = int(label_w * 0.82)
    qr_img = qr_img.resize((qr_target, qr_target), Image.NEAREST)

    # Create label
    label = Image.new("RGB", (label_w, label_h), "white")
    draw = ImageDraw.Draw(label)

    # Load fonts
    font_code = None
    font_serial = None
    for font_path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\calibrib.ttf",
    ]:
        try:
            font_code = ImageFont.truetype(font_path, 30)
            font_serial = ImageFont.truetype(font_path.replace("Bold", "Regular").replace("bd.", ".").replace("rib.", "ri."), 22)
            break
        except (OSError, IOError):
            continue
    if not font_code:
        font_code = ImageFont.load_default()
        font_serial = font_code

    # Measure text
    bbox_code = draw.textbbox((0, 0), device_code, font=font_code)
    bbox_serial = draw.textbbox((0, 0), serial_number, font=font_serial)
    th_code = bbox_code[3] - bbox_code[1]
    th_serial = bbox_serial[3] - bbox_serial[1]
    tw_code = bbox_code[2] - bbox_code[0]
    tw_serial = bbox_serial[2] - bbox_serial[0]

    # Layout: QR top, device_code middle, serial_number bottom
    total_h = qr_target + 12 + th_code + 8 + th_serial
    start_y = (label_h - total_h) // 2

    # QR Code
    qr_x = (label_w - qr_target) // 2
    label.paste(qr_img, (qr_x, start_y))

    # Device code (bold)
    text_y = start_y + qr_target + 12
    draw.text(((label_w - tw_code) / 2, text_y), device_code, fill="black", font=font_code)

    # Serial number
    text_y += th_code + 8
    draw.text(((label_w - tw_serial) / 2, text_y), serial_number, fill="black", font=font_serial)

    # Convert to PNG
    img_buf = _io.BytesIO()
    label.save(img_buf, format="PNG", dpi=(DPI, DPI))
    img_bytes = img_buf.getvalue()

    # Try to print directly on Windows
    printer_name = os.environ.get("DYMO_PRINTER_NAME", "")
    print_success = False
    print_error = ""

    if printer_name:
        try:
            import win32print
            import win32ui
            from PIL import ImageWin

            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(printer_name)
            hdc.StartDoc(f"Device Label - {device_code}")
            hdc.StartPage()

            printable_w = hdc.GetDeviceCaps(8)
            printable_h = hdc.GetDeviceCaps(10)

            dib = ImageWin.Dib(label.convert("RGB"))
            dib.draw(hdc.GetHandleOutput(), (0, 0, printable_w, printable_h))

            hdc.EndPage()
            hdc.EndDoc()
            hdc.DeleteDC()
            print_success = True
        except ImportError:
            print_error = "win32print nicht verfuegbar (nur auf Windows)"
        except Exception as e:
            print_error = str(e)

    if print_success:
        return {"success": True, "message": f"Geraete-Label gedruckt: {device_code} / {serial_number}"}
    elif printer_name and print_error:
        return Response(content=img_bytes, media_type="image/png",
            headers={"Content-Disposition": f'inline; filename="label_{device_code}.png"', "X-Print-Error": print_error})
    else:
        return Response(content=img_bytes, media_type="image/png",
            headers={"Content-Disposition": f'inline; filename="label_{device_code}.png"'})



@router.get("/printers")
async def list_printers(user: dict = Depends(_require_staff)):
    """List available printers on the server (Windows only)."""
    import os
    configured = os.environ.get("DYMO_PRINTER_NAME", "")
    try:
        import win32print
        printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        default = win32print.GetDefaultPrinter()
        return {
            "printers": printers,
            "default": default,
            "configured": configured,
        }
    except ImportError:
        return {
            "printers": [],
            "default": "",
            "configured": configured,
            "error": "win32print nicht verfuegbar (nur auf Windows-Server)",
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

    # Auto-capture current kWh reading as Einbaustand
    kwh_einbau = None
    latest = await _db.emu_data.find_one(
        {"device_id": meter["device_id"], "meter_id": meter_id},
        {"_id": 0, "E_imp_kWh": 1},
        sort=[("ts_utc", -1)]
    )
    if latest and latest.get("E_imp_kWh") is not None:
        kwh_einbau = round(float(latest["E_imp_kWh"]), 2)

    update_fields = {
        "emu_device_id": meter["device_id"],
        "emu_meter_id": meter_id,
        "emu_meter_name": meter.get("meter_name", ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if kwh_einbau is not None:
        update_fields["kwh_einbau"] = kwh_einbau
        update_fields["meter_start"] = kwh_einbau

    await _db.kirmes_signups.update_one({"id": signup_id}, {"$set": update_fields})

    msg = f"Zaehler {meter.get('meter_name', '')} wurde der Anmeldung zugewiesen"
    if kwh_einbau is not None:
        msg += f" (Einbaustand: {kwh_einbau} kWh)"
    return {"message": msg}


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


# ============== Event Documents (Dokumentenablage) ==============

import os as _os
import re as _re
import shutil as _shutil
from fastapi import UploadFile, File, Form as _Form

ALLOWED_DOC_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_VALID_KATEGORIEN = ["messprotokolle", "plaene", "fotos", "sonstiges"]
DOC_STORAGE = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "storage", "event_documents")
_os.makedirs(DOC_STORAGE, exist_ok=True)


def _detect_kategorie(filename: str, content_type: str) -> str:
    """Auto-detect document category based on filename and content type."""
    if content_type.startswith("image/"):
        return "fotos"
    name_lower = (filename or "").lower()
    if _re.search(r"mess|protokoll|pru[eü]f|test|messung|abnahme|zertifikat", name_lower):
        return "messprotokolle"
    if _re.search(r"plan|lage|schema|zeichnung|grundriss|skizze|layout|aufbau", name_lower):
        return "plaene"
    return "sonstiges"


@router.post("/events/{event_id}/documents")
async def upload_event_document(event_id: str, file: UploadFile = File(...), kategorie: str = _Form(None), user: dict = Depends(_require_staff)):
    """Upload a document (PDF or image) to an event."""
    event = await _db.kirmes_events.find_one({"id": event_id}, {"_id": 0, "id": 1})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")

    ct = file.content_type or ""
    if ct not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Nur PDF und Bilder (JPG, PNG, WebP, GIF) erlaubt")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Datei zu groß (max. 20 MB)")

    detected = _detect_kategorie(file.filename or "", ct)
    final_kat = kategorie if kategorie and kategorie in _VALID_KATEGORIEN else detected

    doc_id = str(uuid.uuid4())
    ext = ALLOWED_DOC_TYPES[ct]
    stored_name = f"{doc_id}{ext}"
    event_dir = _os.path.join(DOC_STORAGE, event_id)
    _os.makedirs(event_dir, exist_ok=True)

    file_path = _os.path.join(event_dir, stored_name)
    with open(file_path, "wb") as f:
        f.write(content)

    doc = {
        "id": doc_id,
        "event_id": event_id,
        "filename": stored_name,
        "original_name": file.filename or "Dokument",
        "content_type": ct,
        "size": len(content),
        "kategorie": final_kat,
        "uploaded_by": user.get("name", user.get("email", "")),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.kirmes_event_documents.insert_one(doc)

    return {"id": doc_id, "original_name": doc["original_name"], "kategorie": final_kat, "detected": detected, "message": "Dokument hochgeladen"}


@router.get("/events/{event_id}/documents")
async def list_event_documents(event_id: str, user: dict = Depends(_require_staff)):
    """List all documents for an event."""
    docs = await _db.kirmes_event_documents.find(
        {"event_id": event_id}, {"_id": 0}
    ).sort("uploaded_at", -1).to_list(200)
    return docs


@router.put("/events/{event_id}/documents/{doc_id}")
async def update_event_document(event_id: str, doc_id: str, body: dict, user: dict = Depends(_require_staff)):
    """Update document category."""
    doc = await _db.kirmes_event_documents.find_one({"id": doc_id, "event_id": event_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    update = {}
    if "kategorie" in body and body["kategorie"] in _VALID_KATEGORIEN:
        update["kategorie"] = body["kategorie"]
    if not update:
        raise HTTPException(status_code=400, detail="Keine gueltige Aenderung")
    await _db.kirmes_event_documents.update_one({"id": doc_id}, {"$set": update})
    return {"message": "Dokument aktualisiert"}


@router.get("/events/{event_id}/documents/{doc_id}/file")
async def get_event_document_file(event_id: str, doc_id: str, token: str = None, request: Request = None):
    """Download or preview a document file. Accepts token via query param."""
    from server import get_user_from_token_param
    user = None
    if token:
        user = await get_user_from_token_param(token)
    else:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            user = await get_user_from_token_param(auth[7:])
    if not user:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")

    doc = await _db.kirmes_event_documents.find_one({"id": doc_id, "event_id": event_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    file_path = _os.path.join(DOC_STORAGE, event_id, doc["filename"])
    if not _os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    with open(file_path, "rb") as f:
        data = f.read()

    return Response(
        content=data,
        media_type=doc["content_type"],
        headers={"Content-Disposition": f'inline; filename="{doc["original_name"]}"'},
    )


@router.delete("/events/{event_id}/documents/{doc_id}")
async def delete_event_document(event_id: str, doc_id: str, user: dict = Depends(_require_staff)):
    """Delete a document from an event."""
    doc = await _db.kirmes_event_documents.find_one({"id": doc_id, "event_id": event_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    file_path = _os.path.join(DOC_STORAGE, event_id, doc["filename"])
    if _os.path.exists(file_path):
        _os.remove(file_path)

    await _db.kirmes_event_documents.delete_one({"id": doc_id})
    return {"message": "Dokument gelöscht"}


@router.get("/events/{event_id}/documents-zip")
async def download_event_documents_zip(event_id: str, token: str = None, request: Request = None):
    """Download all event documents as ZIP with folder structure."""
    from server import get_user_from_token_param
    user = None
    if token:
        user = await get_user_from_token_param(token)
    else:
        auth = (request.headers.get("authorization", "") if request else "")
        if auth.startswith("Bearer "):
            user = await get_user_from_token_param(auth[7:])
    if not user:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")

    docs = await _db.kirmes_event_documents.find({"event_id": event_id}, {"_id": 0}).to_list(500)
    if not docs:
        raise HTTPException(status_code=404, detail="Keine Dokumente vorhanden")

    import zipfile, io
    buf = io.BytesIO()
    kat_labels = {"messprotokolle": "Messprotokolle", "plaene": "Plaene", "fotos": "Fotos", "sonstiges": "Sonstiges"}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            kat = kat_labels.get(doc.get("kategorie", "sonstiges"), "Sonstiges")
            file_path = _os.path.join(DOC_STORAGE, event_id, doc["filename"])
            if _os.path.exists(file_path):
                arcname = f"{kat}/{doc['original_name']}"
                zf.write(file_path, arcname)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="Dokumente_Event_{event_id[:8]}.zip"'},
    )



# ============== Lastdiagramm (Load Diagram) ==============

LASTDIAGRAMM_PRICE_NETTO = 125.00
LASTDIAGRAMM_MWST_RATE = 19


@router.get("/public/lastdiagramm/available")
async def get_available_lastdiagramme(schausteller_id: str = Query(...)):
    """Get completed bookings that have linked meters and are eligible for Lastdiagramm purchase."""
    sch = await _db.kirmes_schausteller.find_one({"id": schausteller_id}, {"_id": 0, "password_hash": 0, "verification_code": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")

    # Find signups that have a linked meter (emu_device_id + emu_meter_id present)
    signups = await _db.kirmes_signups.find(
        {
            "schausteller_id": schausteller_id,
            "emu_device_id": {"$exists": True, "$ne": None},
            "emu_meter_id": {"$exists": True, "$ne": None},
        },
        {"_id": 0}
    ).to_list(100)

    if not signups:
        return {"available": [], "purchased": []}

    # Load events for these signups
    evt_ids = list({s["event_id"] for s in signups if s.get("event_id")})
    if evt_ids:
        evt_docs = await _db.kirmes_events.find({"id": {"$in": evt_ids}}, {"_id": 0}).to_list(len(evt_ids))
        evt_map = {e["id"]: e for e in evt_docs}
    else:
        evt_map = {}

    # Check which signups already have a purchased Lastdiagramm
    signup_ids = [s["id"] for s in signups]
    existing_orders = await _db.kirmes_lastdiagramm_orders.find(
        {"signup_id": {"$in": signup_ids}},
        {"_id": 0}
    ).to_list(100)
    purchased_map = {o["signup_id"]: o for o in existing_orders}

    available = []
    purchased = []
    for s in signups:
        event = evt_map.get(s.get("event_id"), {})
        item = {
            "signup_id": s["id"],
            "event_id": s.get("event_id"),
            "event_name": event.get("name", "–"),
            "event_location": event.get("location", ""),
            "event_start": event.get("start_date", ""),
            "event_end": event.get("end_date", ""),
            "connection_type": s.get("connection_type", ""),
            "platznummer": s.get("platznummer", ""),
            "fahrgeschaeft": s.get("fahrgeschaeft", ""),
            "kwh_used": s.get("kwh_used"),
            "emu_device_id": s.get("emu_device_id"),
            "emu_meter_id": s.get("emu_meter_id"),
        }
        if s["id"] in purchased_map:
            order = purchased_map[s["id"]]
            item["order_id"] = order["id"]
            item["invoice_number"] = order.get("invoice_number", "")
            item["status"] = order.get("status", "")
            purchased.append(item)
        else:
            available.append(item)

    return {"available": available, "purchased": purchased}


class LastdiagrammPurchase(BaseModel):
    schausteller_id: str
    signup_id: str
    payment_method: str = "rechnung"


@router.post("/public/lastdiagramm/purchase")
async def purchase_lastdiagramm(data: LastdiagrammPurchase):
    """Purchase a Lastdiagramm for a completed booking. Creates an invoice."""
    sch = await _db.kirmes_schausteller.find_one({"id": data.schausteller_id}, {"_id": 0, "password_hash": 0, "verification_code": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")

    signup = await _db.kirmes_signups.find_one({"id": data.signup_id, "schausteller_id": data.schausteller_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")

    if not signup.get("emu_device_id") or not signup.get("emu_meter_id"):
        raise HTTPException(status_code=400, detail="Kein Zähler verknüpft")

    # Check if already purchased
    existing = await _db.kirmes_lastdiagramm_orders.find_one({"signup_id": data.signup_id}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail=f"Lastdiagramm bereits bestellt (Rechnung: {existing.get('invoice_number', '')})")

    # Validate payment method
    sch_rechnung = sch.get("kauf_auf_rechnung", False)
    if data.payment_method == "rechnung" and not sch_rechnung:
        raise HTTPException(status_code=400, detail="Kauf auf Rechnung ist für diesen Account nicht freigeschaltet.")

    event = await _db.kirmes_events.find_one({"id": signup["event_id"]}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")

    # Calculate price
    netto = LASTDIAGRAMM_PRICE_NETTO
    mwst_amount = round(netto * LASTDIAGRAMM_MWST_RATE / 100, 2)
    brutto = round(netto + mwst_amount, 2)

    # Generate invoice number
    inv_number = await _get_next_invoice_number()

    # Determine status based on payment method
    requires_payment = data.payment_method != "rechnung"

    order_id = str(uuid.uuid4())
    invoice_doc = {
        "id": str(uuid.uuid4()),
        "invoice_number": inv_number,
        "type": "lastdiagramm",
        "lastdiagramm_order_id": order_id,
        "signup_id": data.signup_id,
        "event_id": signup["event_id"],
        "event_name": event.get("name", ""),
        "schausteller_id": data.schausteller_id,
        "schausteller_kundennummer": sch.get("kundennummer", ""),
        "schausteller_firma": sch.get("firma", ""),
        "schausteller_name": sch.get("name", ""),
        "schausteller_email": sch.get("email", ""),
        "invoice_date": datetime.now(timezone.utc).strftime("%d.%m.%Y"),
        "line_items": [{
            "pos": 1,
            "description": f"Lastdiagramm – {event.get('name', '')}\nPlatz {signup.get('platznummer', '')} / {signup.get('fahrgeschaeft', '')}",
            "quantity": "1",
            "unit": "Stück",
            "unit_price": netto,
            "total": netto,
        }],
        "netto": netto,
        "mwst_rate": LASTDIAGRAMM_MWST_RATE,
        "mwst_amount": mwst_amount,
        "brutto": brutto,
        "status": "erstellt" if requires_payment else "erstellt",
        "schausteller": sch,
        "event": {
            "name": event.get("name", ""),
            "location": event.get("location", ""),
            "start_date": event.get("start_date", ""),
            "end_date": event.get("end_date", ""),
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.kirmes_invoices.insert_one(invoice_doc)
    invoice_doc.pop("_id", None)

    # Create order record
    order_doc = {
        "id": order_id,
        "signup_id": data.signup_id,
        "schausteller_id": data.schausteller_id,
        "event_id": signup["event_id"],
        "invoice_id": invoice_doc["id"],
        "invoice_number": inv_number,
        "payment_method": data.payment_method,
        "status": "bezahlt" if not requires_payment else "pending_payment",
        "netto": netto,
        "mwst_amount": mwst_amount,
        "brutto": brutto,
        "emu_device_id": signup.get("emu_device_id"),
        "emu_meter_id": signup.get("emu_meter_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.kirmes_lastdiagramm_orders.insert_one(order_doc)
    order_doc.pop("_id", None)

    return {
        "order": order_doc,
        "invoice": {
            "id": invoice_doc["id"],
            "invoice_number": inv_number,
            "brutto": brutto,
        },
    }


@router.get("/public/lastdiagramm/{order_id}/pdf")
async def download_lastdiagramm_pdf(order_id: str, schausteller_id: str = Query(...)):
    """Download the Lastdiagramm PDF for a purchased order."""
    order = await _db.kirmes_lastdiagramm_orders.find_one(
        {"id": order_id, "schausteller_id": schausteller_id},
        {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    # For "rechnung" orders, always allow download. For others, check payment status.
    if order.get("status") == "pending_payment" and order.get("payment_method") != "rechnung":
        raise HTTPException(status_code=402, detail="Zahlung ausstehend")

    signup = await _db.kirmes_signups.find_one({"id": order["signup_id"]}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")

    event = await _db.kirmes_events.find_one({"id": order["event_id"]}, {"_id": 0})
    sch = await _db.kirmes_schausteller.find_one({"id": schausteller_id}, {"_id": 0, "password_hash": 0, "verification_code": 0})

    # Fetch meter data for the event period
    device_id = order.get("emu_device_id") or signup.get("emu_device_id")
    meter_id = order.get("emu_meter_id") or signup.get("emu_meter_id")

    if not device_id or not meter_id:
        raise HTTPException(status_code=400, detail="Kein Zähler verknüpft")

    # Determine date range from event
    date_from = event.get("start_date", "") if event else ""
    date_to = event.get("end_date", "") if event else ""

    query = {"device_id": device_id, "meter_id": meter_id}
    if date_from or date_to:
        ts_filter = {}
        if date_from:
            ts_filter["$gte"] = date_from + "T00:00:00.000Z" if "T" not in date_from else date_from
        if date_to:
            ts_filter["$lte"] = date_to + "T23:59:59.999Z" if "T" not in date_to else date_to
        if ts_filter:
            query["ts_utc"] = ts_filter

    measurements = await _db.emu_data.find(
        query,
        {"_id": 0, "ts_utc": 1, "P_sum_kW": 1, "I_L1": 1, "I_L2": 1, "I_L3": 1,
         "U_L1": 1, "U_L2": 1, "U_L3": 1, "E_imp_kWh": 1},
        sort=[("ts_utc", 1)]
    ).to_list(50000)

    from services.lastdiagramm_pdf import generate_lastdiagramm_pdf

    pdf_data = {
        "signup": signup,
        "event": event or {},
        "schausteller": sch or {},
    }
    pdf_bytes = generate_lastdiagramm_pdf(pdf_data, measurements)

    event_name = (event.get("name", "Lastdiagramm") if event else "Lastdiagramm").replace(" ", "_")
    filename = f"Lastdiagramm_{event_name}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/lastdiagramm/{signup_id}/pdf")
async def admin_download_lastdiagramm_pdf(signup_id: str, user: dict = Depends(_require_staff)):
    """Admin endpoint: Download Lastdiagramm PDF for any signup with a linked meter."""
    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")

    device_id = signup.get("emu_device_id")
    meter_id = signup.get("emu_meter_id")
    if not device_id or not meter_id:
        raise HTTPException(status_code=400, detail="Kein Zähler verknüpft")

    event = await _db.kirmes_events.find_one({"id": signup.get("event_id")}, {"_id": 0})
    sch = await _db.kirmes_schausteller.find_one(
        {"id": signup.get("schausteller_id")},
        {"_id": 0, "password_hash": 0, "verification_code": 0}
    )

    date_from = event.get("start_date", "") if event else ""
    date_to = event.get("end_date", "") if event else ""

    query = {"device_id": device_id, "meter_id": meter_id}
    if date_from or date_to:
        ts_filter = {}
        if date_from:
            ts_filter["$gte"] = date_from + "T00:00:00.000Z" if "T" not in date_from else date_from
        if date_to:
            ts_filter["$lte"] = date_to + "T23:59:59.999Z" if "T" not in date_to else date_to
        if ts_filter:
            query["ts_utc"] = ts_filter

    measurements = await _db.emu_data.find(
        query,
        {"_id": 0, "ts_utc": 1, "P_sum_kW": 1, "I_L1": 1, "I_L2": 1, "I_L3": 1,
         "U_L1": 1, "U_L2": 1, "U_L3": 1, "E_imp_kWh": 1},
        sort=[("ts_utc", 1)]
    ).to_list(50000)

    from services.lastdiagramm_pdf import generate_lastdiagramm_pdf

    pdf_data = {"signup": signup, "event": event or {}, "schausteller": sch or {}}
    pdf_bytes = generate_lastdiagramm_pdf(pdf_data, measurements)

    event_name = (event.get("name", "Lastdiagramm") if event else "Lastdiagramm").replace(" ", "_")
    filename = f"Lastdiagramm_{event_name}_{signup.get('platznummer', '')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
