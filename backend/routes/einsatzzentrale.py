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
