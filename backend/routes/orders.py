from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import datetime, timezone, timedelta
import httpx
import asyncio

router = APIRouter(prefix="/api/orders", tags=["orders"])
security = HTTPBearer()

_db = None
_decode_jwt_token = None


def init_orders_routes(db, decode_jwt_token):
    global _db, _decode_jwt_token
    _db = db
    _decode_jwt_token = decode_jwt_token


async def _auth_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")
    return user


async def _get_epirent_config():
    config = await _db.integrations.find_one({"type": "ERP", "active": True}, {"_id": 0})
    if not config:
        raise HTTPException(status_code=503, detail="Keine aktive ERP-Schnittstelle konfiguriert")
    return config


async def _fetch_contact_address(client, api_url, headers, contact_pk):
    """Fetch a single contact's address from EpiRent."""
    try:
        resp = await client.get(f"{api_url}/v1/contact/{contact_pk}", headers=headers)
        data = resp.json()
        payload = data.get("payload")
        if isinstance(payload, list) and len(payload) > 0:
            payload = payload[0]
        if isinstance(payload, dict):
            addr = payload.get("address") or {}
            street = addr.get("street", "")
            plz = addr.get("postal_code", "")
            city = addr.get("city", "")
            parts = [p for p in [street, f"{plz} {city}".strip()] if p]
            return contact_pk, ", ".join(parts)
    except Exception:
        pass
    return contact_pk, ""


@router.get("/epirent")
async def get_epirent_orders(
    page: int = Query(0, ge=0),
    page_size: int = Query(200, ge=1, le=500),
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: dict = Depends(_auth_user),
):
    """Fetch orders from EpiRent API with optional date range and search."""
    config = await _get_epirent_config()
    api_url = config.get("api_url", "").rstrip("/")
    api_key = config.get("api_key", "")

    headers = {
        "X-EPI-NO-SESSION": "True",
        "X-EPI-ACC-TOK": api_key,
        "Content-Type": "application/json",
    }

    try:
        ssl_skip = config.get("ssl_skip", False)
        async with httpx.AsyncClient(timeout=30, verify=not ssl_skip) as client:
            resp = await client.post(
                f"{api_url}/v1/order/filter",
                headers=headers,
                json={"pgs": page_size, "page": page},
            )
            data = resp.json()

            if data.get("success") is False:
                raise HTTPException(status_code=502, detail=data.get("message", "EpiRent Fehler"))

            orders_raw = data.get("payload", [])

            # Collect unique contact PKs for address lookup
            contact_pks = set()
            for o in orders_raw:
                ct = o.get("contact")
                if ct and ct.get("primary_key"):
                    contact_pks.add(ct["primary_key"])

            # Batch-fetch contact addresses concurrently
            address_map = {}
            if contact_pks:
                sem = asyncio.Semaphore(10)

                async def _fetch_with_sem(pk):
                    async with sem:
                        return await _fetch_contact_address(client, api_url, {
                            "X-EPI-NO-SESSION": "True",
                            "X-EPI-ACC-TOK": api_key,
                        }, pk)

                results = await asyncio.gather(*[_fetch_with_sem(pk) for pk in contact_pks])
                address_map = {pk: addr for pk, addr in results}

            # Parse orders
            result = []
            for o in orders_raw:
                event_start = None
                event_end = None
                dispo_start = None
                dispo_end = None
                for sched in o.get("order_schedule", []):
                    stype = sched.get("type")
                    sname = sched.get("name", "")
                    if sname == "Event" or stype == 7:
                        event_start = sched.get("date_start")
                        event_end = sched.get("date_end")
                    elif sname == "Dispo" or stype == 1:
                        dispo_start = sched.get("date_start")
                        dispo_end = sched.get("date_end")

                contact = o.get("contact") or {}
                contact_pk = contact.get("primary_key")
                contact_name = contact.get("name", "")
                address = address_map.get(contact_pk, "") if contact_pk else ""

                order = {
                    "primary_key": o.get("primary_key"),
                    "order_no": o.get("order_no_fmt", str(o.get("order_no", ""))),
                    "event": o.get("event", ""),
                    "status": o.get("status", ""),
                    "event_start": event_start,
                    "event_end": event_end,
                    "dispo_start": dispo_start,
                    "dispo_end": dispo_end,
                    "date_shipping": o.get("date_shipping"),
                    "contact_name": contact_name,
                    "contact_pk": contact_pk,
                    "address": address,
                    "customer_no": o.get("customer_no"),
                    "is_confirmed": o.get("is_confirmed", False),
                    "is_canceled": o.get("is_canceled", False),
                    "is_archived": o.get("is_archived", False),
                    "is_current_version": o.get("is_current_version", True),
                    "editor_name": o.get("editor_name", ""),
                    "editor_short": o.get("editor_short", ""),
                    "sum_net": o.get("sum_net", 0),
                    "sum_gro": o.get("sum_gro", 0),
                }
                result.append(order)

            # Date filtering
            if date_from or date_to:
                filtered = []
                for o in result:
                    es = o.get("event_start") or o.get("dispo_start") or ""
                    ee = o.get("event_end") or o.get("dispo_end") or ""
                    if es == "0000-00-00":
                        es = ""
                    if ee == "0000-00-00":
                        ee = ""
                    if date_from and ee and ee < date_from:
                        continue
                    if date_to and es and es > date_to:
                        continue
                    filtered.append(o)
                result = filtered

            # Free-text search
            if search:
                s = search.lower()
                result = [o for o in result if
                    s in o.get("event", "").lower() or
                    s in o.get("order_no", "").lower() or
                    s in o.get("contact_name", "").lower() or
                    s in o.get("address", "").lower() or
                    s in str(o.get("customer_no", "")).lower()
                ]

            return {
                "orders": result,
                "total": len(result),
                "page": page,
                "page_size": page_size,
            }

    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="EpiRent Server nicht erreichbar")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
