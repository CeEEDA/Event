"""Einsatzzentrale Kiosk-API.

Dieser PI steht physisch in der Einsatzzentrale. Bedienflow:
  1. Liste der Mitarbeiter/Freelancer (ohne Auth - Kiosk)
  2. User waehlt sich, gibt Passwort ein -> Token
  3. Aktive Auftraege im Zeitfenster (heute -14d ... +14d)
  4. Aufrag-Auswahl -> Arbeitsmaske

Sicherheits-Aspekte:
  - Public-Endpoint /users gibt NUR id, name, role zurueck (keine Email,
    kein Hash, keine Telefonnummer).
  - Login per user_id + password (nicht per Email) damit Email nicht
    auf einem oeffentlich sichtbaren Bildschirm haengt.
  - Token wird vom bestehenden create_jwt_token erzeugt.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta, timezone, date
import logging

router = APIRouter(prefix="/api/einsatzzentrale", tags=["einsatzzentrale"])
security = HTTPBearer()
logger = logging.getLogger("einsatzzentrale")

_db = None
_verify_password = None
_create_jwt_token = None
_decode_jwt_token = None
_get_default_apps = None


def init_einsatzzentrale_routes(db, verify_password, create_jwt_token,
                                  decode_jwt_token, get_default_apps):
    global _db, _verify_password, _create_jwt_token, _decode_jwt_token, _get_default_apps
    _db = db
    _verify_password = verify_password
    _create_jwt_token = create_jwt_token
    _decode_jwt_token = decode_jwt_token
    _get_default_apps = get_default_apps


async def _auth_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")
    return user


# ----------------------------------------------------------------------------
# 1. User-Liste (PUBLIC, Kiosk)
# ----------------------------------------------------------------------------

@router.get("/users")
async def list_kiosk_users():
    """Liste aller Mitarbeiter & Freelancer (id, name, role).

    KEINE Auth - dieser Bildschirm wird angezeigt sobald der PI startet.
    Es werden bewusst KEINE Mails/Telefonnummern zurueckgegeben.
    """
    cursor = _db.users.find(
        {
            "role": {"$in": ["mitarbeiter", "freelancer"]},
            "$or": [{"is_active": True}, {"is_active": {"$exists": False}}],
        },
        {"_id": 0, "id": 1, "name": 1, "role": 1}
    ).sort([("name", 1)])
    users = []
    async for u in cursor:
        users.append({
            "id": u.get("id"),
            "name": u.get("name") or "",
            "role": u.get("role") or "",
        })
    return {"total": len(users), "users": users}


# ----------------------------------------------------------------------------
# 2. Login per user_id + password
# ----------------------------------------------------------------------------

class KioskLoginRequest(BaseModel):
    user_id: str
    password: str = Field(..., min_length=1)


@router.post("/login")
async def kiosk_login(payload: KioskLoginRequest):
    """Login fuer den Kiosk-Bildschirm. user_id statt email."""
    user = await _db.users.find_one({"id": payload.user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Ungültige Anmeldedaten")
    if user.get("role") not in ("mitarbeiter", "freelancer"):
        raise HTTPException(status_code=403, detail="Nur Mitarbeiter/Freelancer dürfen den Kiosk nutzen")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Konto deaktiviert")
    if not _verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Ungültige Anmeldedaten")

    token = _create_jwt_token(user["id"], user["email"], user["role"])
    await _db.login_history.insert_one({
        "user_id": user["id"],
        "email": user["email"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "einsatzzentrale-pi",
    })
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "name": user.get("name") or "",
            "role": user.get("role") or "",
            "email": user["email"],
        },
    }


# ----------------------------------------------------------------------------
# 3. Aktive Auftraege im Zeitfenster (jetzt -14d ... +14d)
# ----------------------------------------------------------------------------

def _parse_date(s) -> Optional[date]:
    if not s:
        return None
    try:
        # Akzeptiere YYYY-MM-DD oder ISO-Zeitstempel
        if "T" in str(s):
            return datetime.fromisoformat(str(s).replace("Z", "+00:00")).date()
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _is_active_in_window(o: dict, window_start: date, window_end: date) -> bool:
    """Auftrag gilt als aktiv, wenn er nicht archiviert / nicht storniert ist
    UND das Event- bzw. Dispo-Zeitfenster mit dem Fenster ueberlappt."""
    if o.get("is_archived") or o.get("is_canceled"):
        return False
    # Bestimme Start/Ende - bevorzuge event_*, fallback dispo_*
    starts = [
        _parse_date(o.get("event_start")),
        _parse_date(o.get("dispo_start")),
        _parse_date(o.get("date_shipping")),
    ]
    ends = [
        _parse_date(o.get("event_end")),
        _parse_date(o.get("dispo_end")),
    ]
    starts = [d for d in starts if d]
    ends = [d for d in ends if d]
    if not starts and not ends:
        return False
    start = min(starts) if starts else min(ends)
    end = max(ends) if ends else max(starts)
    # Overlap-Check
    return not (end < window_start or start > window_end)


@router.get("/orders")
async def list_kiosk_orders(user: dict = Depends(_auth_user)):
    """Aktive Auftraege im Zeitfenster heute -14 Tage ... +14 Tage.

    Freelancer sehen nur eigene Auftraege.
    """
    today = datetime.now(timezone.utc).date()
    win_start = today - timedelta(days=14)
    win_end = today + timedelta(days=14)

    base_filter: dict = {}
    if (user.get("role") or "").lower() == "freelancer":
        allowed = [str(x) for x in (user.get("freelancer_orders") or [])]
        if not allowed:
            return {"total": 0, "window_start": win_start.isoformat(),
                    "window_end": win_end.isoformat(), "orders": []}
        try:
            allowed_int = [int(p) for p in allowed if str(p).isdigit()]
        except Exception:
            allowed_int = []
        base_filter = {"$or": [
            {"primary_key": {"$in": allowed}},
            {"primary_key": {"$in": allowed_int}} if allowed_int else {"primary_key": {"$in": allowed}},
        ]}

    rows = await _db.orders_cache.find(
        base_filter,
        {"_id": 0, "primary_key": 1, "order_no": 1, "address": 1,
         "contact_name": 1, "event": 1, "event_start": 1, "event_end": 1,
         "dispo_start": 1, "dispo_end": 1, "date_shipping": 1,
         "is_archived": 1, "is_canceled": 1, "editor_name": 1}
    ).to_list(5000)
    active = [o for o in rows if _is_active_in_window(o, win_start, win_end)]
    # Sortiere nach event_start (asc), dann nach order_no
    def _sort_key(o):
        d = _parse_date(o.get("event_start")) or _parse_date(o.get("dispo_start")) or date.max
        return (d, str(o.get("order_no") or ""))
    active.sort(key=_sort_key)
    return {
        "total": len(active),
        "window_start": win_start.isoformat(),
        "window_end": win_end.isoformat(),
        "orders": [
            {
                "primary_key": o.get("primary_key"),
                "order_no": o.get("order_no") or "",
                "contact_name": o.get("contact_name") or "",
                "address": o.get("address") or "",
                "event": o.get("event") or "",
                "event_start": o.get("event_start"),
                "event_end": o.get("event_end"),
                "dispo_start": o.get("dispo_start"),
                "dispo_end": o.get("dispo_end"),
                "editor_name": o.get("editor_name") or "",
            }
            for o in active
        ],
    }


# ----------------------------------------------------------------------------
# 4. Auftrag-Detail (Kurzbeschreibung fuer Workspace-Header)
# ----------------------------------------------------------------------------

@router.get("/orders/{order_pk}")
async def get_kiosk_order(order_pk: str, user: dict = Depends(_auth_user)):
    """Liefert die Kurzbeschreibung eines Auftrags fuer den Workspace-Header.

    Inkl. geocodierter Koordinaten (fuer Wetter-Lookup) falls vorhanden.
    """
    # Freelancer-Permission-Check
    if (user.get("role") or "").lower() == "freelancer":
        allowed = [str(x) for x in (user.get("freelancer_orders") or [])]
        if str(order_pk) not in allowed:
            raise HTTPException(status_code=403, detail="Keine Berechtigung")

    o = None
    if str(order_pk).isdigit():
        o = await _db.orders_cache.find_one({"primary_key": int(order_pk)}, {"_id": 0})
    if not o:
        o = await _db.orders_cache.find_one({"primary_key": str(order_pk)}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")

    # Settings koennen geocodierte Koordinaten enthalten
    settings = await _db.order_settings.find_one(
        {"order_pk": str(order_pk)}, {"_id": 0, "center_lat": 1, "center_lng": 1}
    ) or {}

    return {
        "primary_key": o.get("primary_key"),
        "order_no": o.get("order_no") or "",
        "event": o.get("event") or "",
        "contact_name": o.get("contact_name") or "",
        "address": o.get("address") or "",
        "event_start": o.get("event_start"),
        "event_end": o.get("event_end"),
        "dispo_start": o.get("dispo_start"),
        "dispo_end": o.get("dispo_end"),
        "editor_name": o.get("editor_name") or "",
        "customer_no": o.get("customer_no"),
        "sum_net": o.get("sum_net"),
        "sum_gro": o.get("sum_gro"),
        "center_lat": settings.get("center_lat"),
        "center_lng": settings.get("center_lng"),
    }


# ----------------------------------------------------------------------------
# 5. Wetter-Vorhersage (Open-Meteo, kein API-Key)
# ----------------------------------------------------------------------------

import httpx as _httpx  # noqa: E402

OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"

# WMO Weather-Codes (vereinfacht, deutsch)
_WEATHER_CODES = {
    0: ("Klar", "☀️"), 1: ("Überwiegend klar", "🌤️"), 2: ("Teils bewölkt", "⛅"),
    3: ("Bewölkt", "☁️"), 45: ("Nebel", "🌫️"), 48: ("Raureif-Nebel", "🌫️"),
    51: ("Leichter Nieselregen", "🌦️"), 53: ("Nieselregen", "🌦️"), 55: ("Starker Nieselregen", "🌧️"),
    61: ("Leichter Regen", "🌦️"), 63: ("Regen", "🌧️"), 65: ("Starker Regen", "🌧️"),
    66: ("Eisregen", "🌧️"), 67: ("Starker Eisregen", "🌧️"),
    71: ("Leichter Schneefall", "🌨️"), 73: ("Schneefall", "🌨️"), 75: ("Starker Schneefall", "❄️"),
    77: ("Schneegriesel", "🌨️"),
    80: ("Leichte Schauer", "🌦️"), 81: ("Schauer", "🌧️"), 82: ("Starke Schauer", "⛈️"),
    85: ("Leichte Schneeschauer", "🌨️"), 86: ("Schneeschauer", "❄️"),
    95: ("Gewitter", "⛈️"), 96: ("Gewitter mit Hagel", "⛈️"), 99: ("Schweres Gewitter", "⛈️"),
}


def _weather_label(code):
    if code is None:
        return ("Unbekannt", "❔")
    return _WEATHER_CODES.get(int(code), (f"Code {code}", "❔"))


@router.get("/weather")
async def kiosk_weather(
    lat: float,
    lng: float,
    start: Optional[str] = None,
    end: Optional[str] = None,
    user: dict = Depends(_auth_user),
):
    """Wettervorhersage fuer Veranstaltungszeitraum.

    Quelle: Open-Meteo (kostenlos, kein API-Key noetig).
    start/end im Format YYYY-MM-DD. Wenn nicht angegeben: heute + 7 Tage.
    """
    today = datetime.now(timezone.utc).date()
    s = _parse_date(start) or today
    e = _parse_date(end) or (today + timedelta(days=6))
    # Open-Meteo Forecast: max. 16 Tage in die Zukunft, bis 92 Tage rueckblickend.
    forecast_max = today + timedelta(days=16)
    if e > forecast_max:
        e = forecast_max
    if s > e:
        s = e

    # Bei Vergangenheit benutze Archiv-API, sonst Forecast (auch fuer "jetzt + zukunft")
    use_archive = e < today
    base = OPEN_METEO_ARCHIVE if use_archive else OPEN_METEO_BASE
    params = {
        "latitude": lat,
        "longitude": lng,
        "start_date": s.isoformat(),
        "end_date": e.isoformat(),
        "daily": ("weather_code,temperature_2m_max,temperature_2m_min,"
                  "precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max,"
                  "sunrise,sunset,precipitation_probability_max"),
        "timezone": "Europe/Berlin",
    }
    try:
        async with _httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(base, params=params)
            r.raise_for_status()
            data = r.json()
    except _httpx.HTTPError as ex:
        logger.warning(f"Open-Meteo Fehler: {ex}")
        raise HTTPException(status_code=502, detail="Wetterdienst nicht erreichbar")

    daily = data.get("daily") or {}
    times = daily.get("time") or []
    out_days = []
    for i, t in enumerate(times):
        code = daily.get("weather_code", [None] * len(times))[i]
        label, emoji = _weather_label(code)
        out_days.append({
            "date": t,
            "weather_code": code,
            "weather_label": label,
            "weather_emoji": emoji,
            "temp_max": daily.get("temperature_2m_max", [None] * len(times))[i],
            "temp_min": daily.get("temperature_2m_min", [None] * len(times))[i],
            "precipitation_mm": daily.get("precipitation_sum", [None] * len(times))[i],
            "precipitation_prob": (daily.get("precipitation_probability_max") or [None] * len(times))[i]
                if daily.get("precipitation_probability_max") else None,
            "wind_max_kmh": daily.get("wind_speed_10m_max", [None] * len(times))[i],
            "wind_gust_kmh": daily.get("wind_gusts_10m_max", [None] * len(times))[i],
            "sunrise": (daily.get("sunrise") or [None] * len(times))[i] if daily.get("sunrise") else None,
            "sunset": (daily.get("sunset") or [None] * len(times))[i] if daily.get("sunset") else None,
        })
    return {
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "timezone": data.get("timezone"),
        "source": "open-meteo",
        "start": s.isoformat(),
        "end": e.isoformat(),
        "days": out_days,
    }
