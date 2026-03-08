from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/api/kirmes", tags=["kirmes"])
security = HTTPBearer()

_db = None
_decode_jwt_token = None

# Standard connection types
CONNECTION_TYPES = ["Schuko", "16A", "32A", "63A", "125A", "Festanschluss"]


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
    price: float
    avg_kwh: float = 0.0  # Durchschnittlicher Verbrauch für Kautionsberechnung


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
    custom_prices: Optional[List[StandardPrice]] = None


class SchaustellerRegister(BaseModel):
    firma: str
    name: str
    strasse: str
    plz: str
    ort: str
    steuernummer: str
    email: EmailStr
    telefon: str
    rechnungs_email: EmailStr


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
    for field in ["name", "location", "start_date", "end_date", "dispo_start", "dispo_end", "notes", "status"]:
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
    if event.get("status") in ("aktiv", "abgerechnet"):
        raise HTTPException(status_code=400, detail="Aktive/abgerechnete Veranstaltungen können nicht gelöscht werden")
    await _db.kirmes_events.delete_one({"id": event_id})
    await _db.kirmes_signups.delete_many({"event_id": event_id})
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


# ============== Schausteller (Public Registration) ==============

@router.post("/public/register")
async def register_schausteller(data: SchaustellerRegister):
    """Public endpoint - no auth required. Schausteller registers once."""
    existing = await _db.kirmes_schausteller.find_one({"email": data.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Diese E-Mail-Adresse ist bereits registriert. Bitte melden Sie sich an.")

    sch_id = str(uuid.uuid4())
    sch_doc = {
        "id": sch_id,
        "firma": data.firma,
        "name": data.name,
        "strasse": data.strasse,
        "plz": data.plz,
        "ort": data.ort,
        "steuernummer": data.steuernummer,
        "email": data.email,
        "telefon": data.telefon,
        "rechnungs_email": data.rechnungs_email,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.kirmes_schausteller.insert_one(sch_doc)
    sch_doc.pop("_id", None)
    return sch_doc


@router.post("/public/login")
async def login_schausteller(email: str = Query(...)):
    """Public endpoint - Schausteller 'logs in' by email to see their events."""
    sch = await _db.kirmes_schausteller.find_one({"email": email}, {"_id": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Kein Konto mit dieser E-Mail gefunden. Bitte zuerst registrieren.")
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
    schausteller = await _db.kirmes_schausteller.find(query, {"_id": 0}).sort("firma", 1).to_list(500)
    return schausteller


@router.get("/schausteller/{sch_id}")
async def get_schausteller(sch_id: str, user: dict = Depends(_require_staff)):
    sch = await _db.kirmes_schausteller.find_one({"id": sch_id}, {"_id": 0})
    if not sch:
        raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")
    # Get their signups
    signups = await _db.kirmes_signups.find({"schausteller_id": sch_id}, {"_id": 0}).to_list(100)
    for s in signups:
        event = await _db.kirmes_events.find_one({"id": s["event_id"]}, {"_id": 0, "id": 1, "name": 1})
        s["event_name"] = event["name"] if event else "Unbekannt"
    sch["signups"] = signups
    return sch


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




# ============== Connection Types ==============

@router.get("/connection-types")
async def get_connection_types():
    """Public endpoint - Get available connection types."""
    return CONNECTION_TYPES
