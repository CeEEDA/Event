from fastapi import APIRouter, HTTPException, Query, Depends, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import httpx
import asyncio
import math
import re

router = APIRouter(prefix="/api/orders", tags=["orders"])
security = HTTPBearer()

_db = None
_decode_jwt_token = None
_sync_task = None
_sync_running = False


def init_orders_routes(db, decode_jwt_token):
    global _db, _decode_jwt_token
    _db = db
    _decode_jwt_token = decode_jwt_token


import logging
logger = logging.getLogger("orders_sync")


async def _get_sync_settings():
    """Get sync interval from DB, default 30 min."""
    doc = await _db.sync_settings.find_one({"key": "epirent"}, {"_id": 0})
    return doc or {"key": "epirent", "interval_minutes": 30}


async def _run_epirent_sync():
    """Fetch ALL orders from EpiRent and store in orders_cache."""
    global _sync_running
    if _sync_running:
        return {"status": "already_running"}
    _sync_running = True

    try:
        config = await _db.integrations.find_one({"type": "ERP", "active": True}, {"_id": 0})
        if not config:
            logger.warning("Sync: Keine aktive ERP-Schnittstelle")
            return {"status": "no_config"}

        api_url = config.get("api_url", "").rstrip("/")
        api_key = config.get("api_key", "")
        ssl_skip = config.get("ssl_skip", False)

        headers = {
            "X-EPI-NO-SESSION": "True",
            "X-EPI-ACC-TOK": api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30, verify=not ssl_skip) as client:
            resp = await client.post(
                f"{api_url}/v1/order/filter",
                headers=headers,
                json={"pgs": 500, "page": 0},
            )
            data = resp.json()
            if data.get("success") is False:
                return {"status": "epirent_error", "message": data.get("message")}

            orders_raw = data.get("payload", [])

            # Parse orders
            parsed = []
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
                parsed.append({
                    "primary_key": o.get("primary_key"),
                    "order_no": o.get("order_no_fmt", str(o.get("order_no", ""))),
                    "event": o.get("event", ""),
                    "status": o.get("status", ""),
                    "event_start": event_start,
                    "event_end": event_end,
                    "dispo_start": dispo_start,
                    "dispo_end": dispo_end,
                    "date_shipping": o.get("date_shipping"),
                    "contact_name": contact.get("name", ""),
                    "contact_pk": contact.get("primary_key"),
                    "address": "",
                    "customer_no": o.get("customer_no"),
                    "is_confirmed": o.get("is_confirmed", False),
                    "is_canceled": o.get("is_canceled", False),
                    "is_archived": o.get("is_archived", False),
                    "is_current_version": o.get("is_current_version", True),
                    "editor_name": o.get("editor_name", ""),
                    "editor_short": o.get("editor_short", ""),
                    "sum_net": o.get("sum_net", 0),
                    "sum_gro": o.get("sum_gro", 0),
                    "sum_transport": o.get("sum_transport", 0),
                    "sum_rent": o.get("sum_rent", 0),
                })

            # Fetch delivery addresses (parallel, max 15 concurrent)
            epi_headers = {"X-EPI-NO-SESSION": "True", "X-EPI-ACC-TOK": api_key}
            sem = asyncio.Semaphore(15)

            async def _fetch_addr(pk):
                async with sem:
                    return await _fetch_order_delivery_address(client, api_url, epi_headers, pk)

            pks = [o["primary_key"] for o in parsed if o.get("primary_key")]
            if pks:
                addr_results = await asyncio.gather(*[_fetch_addr(pk) for pk in pks])
                addr_map = {pk: addr for pk, addr in addr_results}
                for o in parsed:
                    o["address"] = addr_map.get(o["primary_key"], "")

        # Store in DB - upsert each order, preserve manual address overrides
        now = datetime.now(timezone.utc).isoformat()
        for o in parsed:
            o["_synced_at"] = now
            # Check if manual address override exists
            existing = await _db.orders_cache.find_one(
                {"primary_key": o["primary_key"]}, {"address_manual": 1, "address": 1}
            )
            if existing and existing.get("address_manual"):
                o["address"] = existing.get("address", o["address"])
                o["address_manual"] = True
            await _db.orders_cache.update_one(
                {"primary_key": o["primary_key"]},
                {"$set": o},
                upsert=True,
            )

        # Update last sync timestamp
        await _db.sync_settings.update_one(
            {"key": "epirent"},
            {"$set": {"last_synced": now, "last_count": len(parsed)}},
            upsert=True,
        )

        logger.info(f"Sync: {len(parsed)} Auftraege synchronisiert")
        return {"status": "ok", "count": len(parsed), "synced_at": now}

    except Exception as e:
        logger.error(f"Sync Fehler: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        _sync_running = False


async def _sync_loop():
    """Background loop that syncs EpiRent orders on interval."""
    # Wait 10 sec after startup before first sync
    await asyncio.sleep(10)
    while True:
        try:
            settings = await _get_sync_settings()
            interval = settings.get("interval_minutes", 30)
            await _run_epirent_sync()
            await asyncio.sleep(interval * 60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Sync loop error: {e}")
            await asyncio.sleep(60)


def start_sync_task():
    """Start the background sync loop."""
    global _sync_task
    if _sync_task is None or _sync_task.done():
        _sync_task = asyncio.get_event_loop().create_task(_sync_loop())
        logger.info("EpiRent Sync-Task gestartet")


async def _auth_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")
    return user


# ── Freelancer Helpers ──
def _freelancer_assigned_pks(user: dict):
    """Return list of order_pks (strings) assigned to a freelancer user."""
    raw = user.get("freelancer_orders") or []
    return [str(x) for x in raw]


def _freelancer_order_visible(order_obj: dict, today_str: str = None):
    """Freelancer-Sichtbarkeit: Auftrag nur sichtbar bis 5 Tage NACH Job-Ende.
    Verwendet event_end (fallback dispo_end). Aufträge ohne Enddatum bleiben sichtbar."""
    from datetime import date
    if today_str is None:
        today_str = date.today().isoformat()
    end = order_obj.get("event_end") or order_obj.get("dispo_end") or ""
    if not end or end == "0000-00-00":
        return True
    try:
        end_d = date.fromisoformat(end)
        from datetime import timedelta
        cutoff = end_d + timedelta(days=5)
        return date.fromisoformat(today_str) <= cutoff
    except Exception:
        return True


async def _check_freelancer_order_access(user: dict, order_pk):
    """Raise 403 wenn role=freelancer und Auftrag nicht (mehr) zugewiesen."""
    if user.get("role") != "freelancer":
        return
    pks = _freelancer_assigned_pks(user)
    if str(order_pk) not in pks:
        raise HTTPException(status_code=403, detail="Auftrag nicht zugewiesen")
    # Lookup order to check 5-day cutoff
    o = None
    if str(order_pk).isdigit():
        o = await _db.orders_cache.find_one({"primary_key": int(order_pk)}, {"_id": 0})
    if not o:
        o = await _db.orders_cache.find_one({"primary_key": str(order_pk)}, {"_id": 0})
    if o and not _freelancer_order_visible(o):
        raise HTTPException(status_code=403, detail="Auftrag bereits abgeschlossen (5 Tage nach Ende abgelaufen)")


# ── Sync Endpoints ──

@router.get("/sync/status")
async def get_sync_status(user: dict = Depends(_auth_user)):
    """Get sync status and settings."""
    settings = await _db.sync_settings.find_one({"key": "epirent"}, {"_id": 0})
    if not settings:
        settings = {"key": "epirent", "interval_minutes": 30}
    cache_count = await _db.orders_cache.count_documents({})
    return {
        "interval_minutes": settings.get("interval_minutes", 30),
        "last_synced": settings.get("last_synced"),
        "last_count": settings.get("last_count", 0),
        "cache_count": cache_count,
        "is_running": _sync_running,
    }


@router.post("/sync/trigger")
async def trigger_sync(user: dict = Depends(_auth_user)):
    """Manually trigger an EpiRent sync."""
    if _sync_running:
        return {"status": "already_running"}
    result = await _run_epirent_sync()
    return result


@router.post("/cleanup-expired-assignments")
async def trigger_cleanup_expired_assignments(user: dict = Depends(_auth_user)):
    """Admin: Manuell die Auto-Unassign-Routine für abgelaufene Aufträge
    triggern (sonst läuft sie automatisch 1x täglich)."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    from deployment_tracker import cleanup_expired_order_assignments
    result = await cleanup_expired_order_assignments(_db)
    return {"ok": True, **result}



@router.post("/sync/settings")
async def update_sync_settings(data: dict, user: dict = Depends(_auth_user)):
    """Update sync interval."""
    interval = data.get("interval_minutes", 30)
    if interval < 1:
        raise HTTPException(status_code=400, detail="Intervall muss mindestens 1 Minute sein")
    await _db.sync_settings.update_one(
        {"key": "epirent"},
        {"$set": {"interval_minutes": int(interval)}},
        upsert=True,
    )
    return {"interval_minutes": int(interval)}


@router.get("/address-override/{order_pk}")
async def get_address_override(order_pk: str, user: dict = Depends(_auth_user)):
    """Get manual address override for an order."""
    doc = await _db.order_address_overrides.find_one({"order_pk": str(order_pk)}, {"_id": 0})
    return doc or {"order_pk": str(order_pk), "address": ""}


@router.post("/address-override/{order_pk}")
async def set_address_override(order_pk: str, data: dict, user: dict = Depends(_auth_user)):
    """Set manual address override for an order."""
    address = data.get("address", "").strip()
    now = datetime.now(timezone.utc).isoformat()
    await _db.order_address_overrides.update_one(
        {"order_pk": str(order_pk)},
        {"$set": {
            "order_pk": str(order_pk),
            "address": address,
            "updated_by": user.get("name", user.get("email", "")),
            "updated_at": now,
        }},
        upsert=True,
    )
    # Also update the cached order
    await _db.orders_cache.update_one(
        {"primary_key": int(order_pk) if order_pk.isdigit() else order_pk},
        {"$set": {"address": address, "address_manual": True}},
    )
    return {"order_pk": str(order_pk), "address": address, "updated_at": now}


class OrderSettingsUpdate(BaseModel):
    radius_km: Optional[float] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None


class DeploymentCreate(BaseModel):
    generator_id: str
    generator_name: Optional[str] = ""
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    operating_hours: Optional[float] = 0
    kwh_start: Optional[float] = 0
    kwh_end: Optional[float] = 0
    faults: Optional[str] = ""
    notes: Optional[str] = ""


class OrderAssetCreate(BaseModel):
    asset_type: str  # Lichtmast, Stromerzeuger, Verteiler, Sonstiges
    latitude: float
    longitude: float
    label: Optional[str] = ""
    plus_code: Optional[str] = ""


class AssetCommentCreate(BaseModel):
    text: str


class AssetMove(BaseModel):
    target_order_pk: int


class AssetEdit(BaseModel):
    asset_type: Optional[str] = None
    label: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    plus_code: Optional[str] = None


class BulkDismantle(BaseModel):
    asset_ids: list[str]


class CopyToOrder(BaseModel):
    target_order_pk: int
    asset_ids: list[str] = []
    generator_ids: list[str] = []
    document_ids: list[str] = []


def _haversine_km(lat1, lng1, lat2, lng2):
    """Calculate distance between two GPS points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def _get_epirent_config():
    config = await _db.integrations.find_one({"type": "ERP", "active": True}, {"_id": 0})
    if not config:
        raise HTTPException(status_code=503, detail="Keine aktive ERP-Schnittstelle konfiguriert")
    return config


def _format_delivery_address(addr):
    """Format an EpiRent address_delivery object into a readable string."""
    if not addr or not isinstance(addr, dict):
        return ""
    name = addr.get("name", "")
    street = addr.get("street", "")
    plz = addr.get("postal_code", "")
    city = addr.get("city", "")
    plz_city = f"{plz} {city}".strip()
    parts = [p for p in [name, street, plz_city] if p]
    return ", ".join(parts)


async def _fetch_order_delivery_address(client, api_url, headers, order_pk):
    """Fetch delivery address from a single order's detail endpoint.
    Falls back to contact address if delivery address is empty."""
    try:
        resp = await client.get(f"{api_url}/v1/order/{order_pk}", headers=headers)
        data = resp.json()
        payload = data.get("payload")
        if isinstance(payload, list) and len(payload) > 0:
            payload = payload[0]
        if isinstance(payload, dict):
            addr = payload.get("address_delivery")
            formatted = _format_delivery_address(addr)
            if formatted:
                return order_pk, formatted

            # Fallback: contact address
            contact = payload.get("contact") or {}
            contact_pk = contact.get("primary_key")
            if contact_pk:
                try:
                    c_resp = await client.get(f"{api_url}/v1/contact/{contact_pk}", headers=headers)
                    c_data = c_resp.json()
                    c_payload = c_data.get("payload")
                    if isinstance(c_payload, list) and len(c_payload) > 0:
                        c_payload = c_payload[0]
                    if isinstance(c_payload, dict):
                        c_addr = c_payload.get("address")
                        if isinstance(c_addr, dict):
                            parts = []
                            if c_addr.get("street"):
                                parts.append(c_addr["street"])
                            if c_addr.get("postal_code") or c_addr.get("city"):
                                parts.append(f"{c_addr.get('postal_code', '')} {c_addr.get('city', '')}".strip())
                            if parts:
                                return order_pk, ", ".join(parts)
                except Exception:
                    pass
    except Exception:
        pass
    return order_pk, ""


@router.get("/epirent")
async def get_epirent_orders(
    page: int = Query(0, ge=0),
    page_size: int = Query(200, ge=1, le=500),
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: dict = Depends(_auth_user),
):
    """Fetch orders from local cache. Falls back to live EpiRent if cache is empty."""
    cache_count = await _db.orders_cache.count_documents({})

    if cache_count == 0:
        # Cache leer - direkt synchronisieren
        sync_result = await _run_epirent_sync()
        if sync_result.get("status") != "ok":
            raise HTTPException(status_code=503, detail="EpiRent Sync fehlgeschlagen")

    # Read from cache
    result = await _db.orders_cache.find({}, {"_id": 0, "_synced_at": 0}).to_list(500)

    # Apply date filtering
    if date_from or date_to:
        filtered = []
        for o in result:
            # Fuer die Einsatzplanung ist der DISPO-Zeitraum entscheidend
            # (Lieferung, Abbau, Personal) - nicht das reine Event-Datum.
            # Beispiel: Ruhr-in-Love hat event=04.07., aber dispo 22.06.-11.07.
            es = o.get("dispo_start") or o.get("event_start") or ""
            ee = o.get("dispo_end") or o.get("event_end") or ""
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

    # Apply text search
    if search:
        s = search.lower()
        result = [o for o in result if
            s in o.get("event", "").lower() or
            s in o.get("order_no", "").lower() or
            s in o.get("contact_name", "").lower() or
            s in str(o.get("customer_no", "")).lower() or
            s in o.get("address", "").lower()
        ]

    # Freelancer-Filter: nur zugewiesene Aufträge + 5 Tage nach Job-Ende
    if user.get("role") == "freelancer":
        assigned = set(_freelancer_assigned_pks(user))
        result = [o for o in result
                  if str(o.get("primary_key")) in assigned and _freelancer_order_visible(o)]
        # Kundendaten aus der Liste entfernen
        for o in result:
            o["contact_name"] = ""
            o["customer_no"] = ""

    return {
        "orders": result,
        "total": len(result),
        "page": page,
        "page_size": page_size,
    }


async def _geocode_address(address_str, addr_raw=None):
    """Geocode an address using Nominatim with fallback strategies."""
    if not address_str and not addr_raw:
        return None, None

    # Build query candidates from most specific to least
    candidates = []
    if addr_raw and isinstance(addr_raw, dict):
        street = addr_raw.get("street", "")
        plz = addr_raw.get("postal_code", "")
        city = addr_raw.get("city", "")
        name = addr_raw.get("name", "")
        if street and city:
            candidates.append(f"{street}, {plz} {city}".strip())
        if name and city:
            candidates.append(f"{name}, {city}")
        if plz and city:
            candidates.append(f"{plz} {city}")
        if city:
            candidates.append(city)
    if address_str:
        candidates.insert(0, address_str)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for query in candidates:
                if not query.strip():
                    continue
                resp = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": query, "format": "json", "limit": 1, "countrycodes": "de"},
                    headers={"User-Agent": "EventenergiePortal/1.0"},
                )
                results = resp.json()
                if results:
                    return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        pass
    return None, None


async def _get_full_order(api_url, api_key, order_pk, ssl_skip=False):
    """Fetch full order detail from EpiRent."""
    headers = {"X-EPI-NO-SESSION": "True", "X-EPI-ACC-TOK": api_key}
    async with httpx.AsyncClient(timeout=15, verify=not ssl_skip) as client:
        resp = await client.get(f"{api_url}/v1/order/{order_pk}", headers=headers)
        data = resp.json()
        payload = data.get("payload")
        if isinstance(payload, list) and len(payload) > 0:
            return payload[0]
        if isinstance(payload, dict):
            return payload
    return None


@router.get("/epirent/{order_pk}")
async def get_order_detail(order_pk: int, user: dict = Depends(_auth_user)):
    """Get full order detail including delivery address and geocoded location."""
    await _check_freelancer_order_access(user, order_pk)
    config = await _get_epirent_config()
    api_url = config.get("api_url", "").rstrip("/")
    api_key = config.get("api_key", "")
    ssl_skip = config.get("ssl_skip", False)

    try:
        raw = await _get_full_order(api_url, api_key, order_pk, ssl_skip)
        if not raw:
            raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")

        # Parse schedule
        event_start = event_end = dispo_start = dispo_end = None
        for sched in raw.get("order_schedule", []):
            stype = sched.get("type")
            sname = sched.get("name", "")
            if sname == "Event" or stype == 7:
                event_start = sched.get("date_start")
                event_end = sched.get("date_end")
            elif sname == "Dispo" or stype == 1:
                dispo_start = sched.get("date_start")
                dispo_end = sched.get("date_end")

        contact = raw.get("contact") or {}
        addr_raw = raw.get("address_delivery") or {}
        address_str = _format_delivery_address(addr_raw)

        # Fetch contact details (phone, email, address) from EpiRent
        contact_details = {"phone": "", "email": "", "street": "", "postal_code": "", "city": ""}
        contact_pk = contact.get("primary_key")
        if contact_pk:
            try:
                config_c = await _get_epirent_config()
                c_headers = {"X-EPI-NO-SESSION": "True", "X-EPI-ACC-TOK": config_c.get("api_key", "")}
                async with httpx.AsyncClient(timeout=10, verify=not ssl_skip) as c:
                    c_resp = await c.get(f"{api_url}/v1/contact/{contact_pk}", headers=c_headers)
                    c_data = c_resp.json()
                    c_payload = c_data.get("payload")
                    if isinstance(c_payload, list) and len(c_payload) > 0:
                        c_payload = c_payload[0]
                    if isinstance(c_payload, dict):
                        contact_details["phone"] = c_payload.get("phone", "") or c_payload.get("phone_mobile", "") or ""
                        contact_details["email"] = c_payload.get("email", "") or ""
                        c_addr = c_payload.get("address")
                        if isinstance(c_addr, dict):
                            contact_details["street"] = c_addr.get("street", "") or ""
                            contact_details["postal_code"] = c_addr.get("postal_code", "") or ""
                            contact_details["city"] = c_addr.get("city", "") or ""
            except Exception:
                pass

        # Check for manual address override
        override = await _db.order_address_overrides.find_one({"order_pk": str(order_pk)}, {"_id": 0})
        address_manual = False
        if override and override.get("address"):
            address_str = override["address"]
            address_manual = True
        elif not address_str:
            # Fallback to contact address
            contact_pk = contact.get("primary_key")
            if contact_pk:
                try:
                    config2 = await _get_epirent_config()
                    epi_headers = {"X-EPI-NO-SESSION": "True", "X-EPI-ACC-TOK": config2.get("api_key", "")}
                    async with httpx.AsyncClient(timeout=10, verify=not ssl_skip) as c:
                        c_resp = await c.get(f"{api_url}/v1/contact/{contact_pk}", headers=epi_headers)
                        c_data = c_resp.json()
                        c_payload = c_data.get("payload")
                        if isinstance(c_payload, list) and len(c_payload) > 0:
                            c_payload = c_payload[0]
                        if isinstance(c_payload, dict):
                            c_addr = c_payload.get("address")
                            if isinstance(c_addr, dict):
                                parts = []
                                if c_addr.get("street"):
                                    parts.append(c_addr["street"])
                                if c_addr.get("postal_code") or c_addr.get("city"):
                                    parts.append(f"{c_addr.get('postal_code', '')} {c_addr.get('city', '')}".strip())
                                if parts:
                                    address_str = ", ".join(parts)
                except Exception:
                    pass

        # Get stored settings for this order
        settings = await _db.order_settings.find_one(
            {"order_pk": order_pk}, {"_id": 0}
        )
        radius_km = 5.0
        center_lat = None
        center_lng = None

        if settings:
            radius_km = settings.get("radius_km", 5.0)
            center_lat = settings.get("center_lat")
            center_lng = settings.get("center_lng")

        # Geocode if no stored coordinates
        if center_lat is None or center_lng is None:
            center_lat, center_lng = await _geocode_address(address_str, addr_raw)
            # Auto-save geocoded coordinates
            if center_lat is not None:
                await _db.order_settings.update_one(
                    {"order_pk": order_pk},
                    {"$set": {
                        "order_pk": order_pk,
                        "center_lat": center_lat,
                        "center_lng": center_lng,
                        "radius_km": radius_km,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )

        result_payload = {
            "primary_key": raw.get("primary_key"),
            "order_no": raw.get("order_no_fmt", str(raw.get("order_no", ""))),
            "event": raw.get("event", ""),
            "status": raw.get("status", ""),
            "event_start": event_start,
            "event_end": event_end,
            "dispo_start": dispo_start,
            "dispo_end": dispo_end,
            "date_shipping": raw.get("date_shipping"),
            "contact_name": contact.get("name", ""),
            "customer_no": raw.get("customer_no"),
            "address": address_str,
            "address_manual": address_manual,
            "address_raw": {
                "name": addr_raw.get("name", ""),
                "street": addr_raw.get("street", ""),
                "postal_code": addr_raw.get("postal_code", ""),
                "city": addr_raw.get("city", ""),
            },
            "is_confirmed": raw.get("is_confirmed", False),
            "is_canceled": raw.get("is_canceled", False),
            "is_archived": raw.get("is_archived", False),
            "editor_name": raw.get("editor_name", ""),
            "sum_net": raw.get("sum_net", 0),
            "sum_gro": raw.get("sum_gro", 0),
            "center_lat": center_lat,
            "center_lng": center_lng,
            "radius_km": radius_km,
            "contact_phone": contact_details.get("phone", ""),
            "contact_email": contact_details.get("email", ""),
            "contact_street": contact_details.get("street", ""),
            "contact_postal_code": contact_details.get("postal_code", ""),
            "contact_city": contact_details.get("city", ""),
        }

        # Freelancer: Kundendaten unkenntlich machen
        if user.get("role") == "freelancer":
            for k in ("contact_name", "customer_no", "contact_phone", "contact_email",
                      "contact_street", "contact_postal_code", "contact_city", "sum_net", "sum_gro"):
                result_payload[k] = "" if isinstance(result_payload.get(k), str) else 0
            result_payload["address_raw"]["name"] = ""

        return result_payload

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _generate_delivery_note_pdf(
    raw_order: dict,
    contact_details: dict,
    delivery_note_no: str,
    positions: list = None,
    notes_override: str = None,
    signature_sender_b64: str = None,
    signature_receiver_b64: str = None,
    signed_at_location: str = None,
    signed_at_iso: str = None,
):
    """Generate a Lieferschein-PDF (Eventenergie-Briefpapier-Stil).

    Args:
        positions: Optional list of {pos, title, amount, unit, remark}. Falls None,
                   werden order_items vom raw_order genommen.
        signature_sender_b64 / signature_receiver_b64: Optional data-URL PNGs der Unterschriften.
        signed_at_location: Optional Ort der Unterschrift.
        signed_at_iso: Optional ISO Datum/Uhrzeit der Unterschrift.
        notes_override: Optional Notiz-Text (statt raw_order.notes).
    Returns:
        io.BytesIO
    """
    import io
    import os
    import base64
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import (
        BaseDocTemplate, PageTemplate, Frame, Table, TableStyle,
        Paragraph, Spacer, Image as RLImage,
    )
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

    PURPLE = colors.HexColor("#7c3aed")
    BORDER = colors.HexColor("#d1d5db")
    HEADER_BG = colors.HexColor("#ede9fe")
    LIGHT_GRAY = colors.HexColor("#f9fafb")
    DARK = colors.HexColor("#1f2937")
    MUTED = colors.HexColor("#6b7280")

    s_title = ParagraphStyle("T", fontSize=20, fontName="Helvetica-Bold", textColor=PURPLE, alignment=TA_LEFT, spaceAfter=4, leading=22)
    s_meta_lbl = ParagraphStyle("ML", fontSize=8, textColor=MUTED, fontName="Helvetica")
    s_meta_val = ParagraphStyle("MV", fontSize=9, textColor=DARK, fontName="Helvetica-Bold")
    s_sender_small = ParagraphStyle("SS", fontSize=6.5, textColor=MUTED, fontName="Helvetica")
    s_addr_label = ParagraphStyle("AL", fontSize=7, textColor=MUTED, fontName="Helvetica", spaceAfter=1)
    s_addr_val = ParagraphStyle("AV", fontSize=10, textColor=DARK, fontName="Helvetica", leading=12)
    s_h2 = ParagraphStyle("H2", fontSize=11, fontName="Helvetica-Bold", textColor=PURPLE, spaceBefore=4, spaceAfter=3)  # noqa: F841
    s_label = ParagraphStyle("L", fontSize=8, textColor=MUTED, fontName="Helvetica")  # noqa: F841
    s_value = ParagraphStyle("V", fontSize=9, textColor=DARK, fontName="Helvetica")
    s_cell = ParagraphStyle("C", fontSize=9, textColor=DARK, leading=11)
    s_cell_b = ParagraphStyle("CB", fontSize=9, textColor=DARK, fontName="Helvetica-Bold", leading=11)
    s_cell_r = ParagraphStyle("CR", fontSize=9, textColor=DARK, leading=11, alignment=TA_RIGHT)
    s_intro = ParagraphStyle("I", fontSize=9.5, textColor=DARK, leading=13, fontName="Helvetica")
    s_footer_col = ParagraphStyle("FC", fontSize=6.5, textColor=MUTED, leading=8.5, fontName="Helvetica")  # noqa: F841
    s_footer_lbl = ParagraphStyle("FL", fontSize=6.5, textColor=MUTED, leading=8.5, fontName="Helvetica-Bold")  # noqa: F841
    s_sig = ParagraphStyle("SG", fontSize=8, textColor=DARK, fontName="Helvetica", alignment=TA_CENTER)
    s_sig_label = ParagraphStyle("SGL", fontSize=7, textColor=MUTED, fontName="Helvetica", alignment=TA_CENTER)

    buf = io.BytesIO()
    page_w, page_h = A4

    LEFT = 18*mm
    RIGHT = 18*mm
    TOP = 12*mm
    BOTTOM = 28*mm
    USABLE_W = page_w - LEFT - RIGHT

    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "portal_logo.png")

    def draw_header_footer(canv, doc):
        _draw_ee_brand_chrome(canv, doc)

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=LEFT, rightMargin=RIGHT, topMargin=TOP + 18*mm, bottomMargin=BOTTOM,
    )
    frame = Frame(LEFT, BOTTOM, USABLE_W, page_h - TOP - 28*mm - BOTTOM, showBoundary=0)
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=draw_header_footer)])

    elems = []

    # ===== ABSENDERZEILE (kleine Zeile ueber Empfaenger) =====
    elems.append(Paragraph(
        "Eventenergie Deutschland GmbH &amp; Co. KG  ·  Thyssenstraße 10  ·  56626 Andernach",
        s_sender_small,
    ))
    elems.append(Spacer(1, 4*mm))

    # ===== EMPFAENGER + META =====
    contact = raw_order.get("contact") or {}
    customer_name = contact.get("name") or ""
    addr_d = raw_order.get("address_delivery") or {}
    # Bevorzugt explizite Lieferadresse, sonst Kontakt-Adresse
    deliv_street = addr_d.get("street") or contact_details.get("street", "")
    deliv_plz = addr_d.get("postal_code") or contact_details.get("postal_code", "")
    deliv_city = addr_d.get("city") or contact_details.get("city", "")
    deliv_country = addr_d.get("country") or "Deutschland"
    addr_name = addr_d.get("name") or customer_name

    addr_lines = []
    if addr_name:
        addr_lines.append(f"<b>{addr_name}</b>")
    if deliv_street:
        addr_lines.append(deliv_street)
    if deliv_plz or deliv_city:
        addr_lines.append(f"{deliv_plz} {deliv_city}".strip())
    if deliv_country and deliv_country.lower() not in ("deutschland", "de", ""):
        addr_lines.append(deliv_country)
    addr_html = "<br/>".join(addr_lines) if addr_lines else "—"

    order_no_fmt = raw_order.get("order_no_fmt") or str(raw_order.get("order_no", ""))
    # Parse Dispo / Event Schedule
    sched = raw_order.get("order_schedule") or []
    dispo_start = dispo_end = event_start = event_end = ""
    for s in sched:
        nm = s.get("name", "")
        if nm == "Dispo":
            dispo_start = s.get("date_start") or ""
            dispo_end = s.get("date_end") or ""
        elif nm == "Event":
            event_start = s.get("date_start") or ""
            event_end = s.get("date_end") or ""

    def _fmt_de(d):
        if not d or d == "0000-00-00":
            return ""
        try:
            y, m, day = d.split("-")
            return f"{day}.{m}.{y}"
        except Exception:
            return d

    # ===== GEWICHTS-SUMME (für Meta-Box) =====
    total_weight = 0.0
    article_count = 0
    if positions:
        for _p in positions:
            if _p.get("is_chapter") or _p.get("is_heading"):
                continue
            try:
                _amt = float(_p.get("amount") or 0)
                _wn = float(_p.get("weight_net") or 0)
            except (TypeError, ValueError):
                continue
            if _amt > 0 and _wn > 0:
                total_weight += _amt * _wn
                article_count += 1

    meta_data = [
        [Paragraph("Lieferschein-Nr.", s_meta_lbl), Paragraph(delivery_note_no, s_meta_val)],
        [Paragraph("Auftrags-Nr.", s_meta_lbl), Paragraph(order_no_fmt, s_meta_val)],
        [Paragraph("Datum", s_meta_lbl), Paragraph(datetime.now(timezone.utc).astimezone().strftime("%d.%m.%Y"), s_meta_val)],
        [Paragraph("Kunden-Nr.", s_meta_lbl), Paragraph(str(raw_order.get("customer_no", "")), s_meta_val)],
    ]
    if event_start or event_end:
        meta_data.append([Paragraph("Event", s_meta_lbl), Paragraph(f"{_fmt_de(event_start)} – {_fmt_de(event_end)}", s_meta_val)])
    if dispo_start or dispo_end:
        meta_data.append([Paragraph("Dispo", s_meta_lbl), Paragraph(f"{_fmt_de(dispo_start)} – {_fmt_de(dispo_end)}", s_meta_val)])
    if total_weight > 0:
        weight_str = f"{total_weight:.1f}".replace(".", ",")
        meta_data.append([Paragraph("Gesamtgewicht", s_meta_lbl), Paragraph(f"{weight_str} kg", s_meta_val)])

    meta_t = Table(meta_data, colWidths=[28*mm, 47*mm])
    meta_t.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    addr_para = Paragraph(addr_html, s_addr_val)
    addr_block = Table(
        [[Paragraph("LIEFERADRESSE", s_addr_label)], [addr_para]],
        colWidths=[USABLE_W - 75*mm - 5*mm],
    )
    addr_block.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (0, 0), 0.4, PURPLE),
    ]))

    head_t = Table([[addr_block, meta_t]], colWidths=[USABLE_W - 75*mm - 5*mm + 5*mm, 75*mm])
    head_t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elems.append(head_t)
    elems.append(Spacer(1, 6*mm))

    # ===== TITEL =====
    elems.append(Paragraph("Lieferschein", s_title))
    event_text = raw_order.get("event") or ""
    if event_text:
        elems.append(Spacer(1, 1*mm))
        elems.append(Paragraph(f"<i>{event_text}</i>", s_intro))
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph(
        "Sehr geehrte Damen und Herren,<br/>"
        "wir liefern Ihnen zu o. g. Auftrag folgende Positionen:",
        s_intro,
    ))
    elems.append(Spacer(1, 4*mm))

    # ===== POSITIONEN-TABELLE =====
    if positions is None:
        # Fallback: aus order_items (Kapitel-Koepfen)
        positions = []
        for i, it in enumerate(raw_order.get("order_items") or []):
            positions.append({
                "pos": it.get("position_no_str") or str(i + 1),
                "title": it.get("title") or "",
                "amount": it.get("amount_base") or 0,
                "unit": it.get("unit_product") or "",
                "remark": "",
            })

    rows = [[
        Paragraph("<b>Pos.</b>", s_cell_b),
        Paragraph("<b>Bezeichnung</b>", s_cell_b),
        Paragraph("<b>Menge</b>", s_cell_b),
        Paragraph("<b>Einheit</b>", s_cell_b),
        Paragraph("<b>Bemerkung</b>", s_cell_b),
    ]]
    chapter_row_indices = []  # fuer special styling
    heading_row_indices = []  # fuer Sub-Header-Styling (Ueberschriften zwischen Artikeln)
    for idx, p in enumerate(positions):
        is_chap = p.get("is_chapter", False)
        is_heading = p.get("is_heading", False)
        try:
            amount = p.get("amount") or 0
            amount_str = f"{float(amount):g}" if amount else ""
        except Exception:
            amount_str = str(p.get("amount", ""))
        if is_chap:
            # Kapitel-Zeile: nur Pos + Titel, fett, lila Hintergrund
            chapter_row_indices.append(len(rows))
            rows.append([
                Paragraph(f"<b>{p.get('pos') or (idx + 1)}</b>", s_cell_b),
                Paragraph(f"<b>{p.get('title') or ''}</b>", s_cell_b),
                "", "", "",
            ])
        elif is_heading:
            # Ueberschrift-Zeile: nur Bezeichnung, kursiv, hellgrauer Hintergrund
            heading_row_indices.append(len(rows))
            rows.append([
                "",
                Paragraph(f"<i>{p.get('title') or ''}</i>", s_cell),
                "", "", "",
            ])
        else:
            rows.append([
                Paragraph(str(p.get("pos") or (idx + 1)), s_cell),
                Paragraph(str(p.get("title") or ""), s_cell),
                Paragraph(amount_str, s_cell_r),
                Paragraph(str(p.get("unit") or ""), s_cell),
                Paragraph(str(p.get("remark") or ""), s_cell),
            ])
    if not positions:
        rows.append([Paragraph("—", s_cell), Paragraph("Keine Positionen", s_cell), "", "", ""])

    col_widths = [12*mm, USABLE_W - 12*mm - 22*mm - 22*mm - 50*mm, 22*mm, 22*mm, 50*mm]
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl_style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, PURPLE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    # Kapitel-Zeilen visuell hervorheben (lila Hintergrund)
    for ri in chapter_row_indices:
        tbl_style.append(("BACKGROUND", (0, ri), (-1, ri), HEADER_BG))
        tbl_style.append(("LINEABOVE", (0, ri), (-1, ri), 0.4, PURPLE))
    # Ueberschrift-Zeilen leicht abheben (hellgrau, kursiv)
    for ri in heading_row_indices:
        tbl_style.append(("BACKGROUND", (0, ri), (-1, ri), LIGHT_GRAY))
        tbl_style.append(("SPAN", (1, ri), (-1, ri)))  # Bezeichnung ueber gesamte Breite
    tbl.setStyle(TableStyle(tbl_style))
    elems.append(tbl)
    elems.append(Spacer(1, 4*mm))

    # ===== HINWEIS =====
    notes = notes_override if notes_override is not None else (raw_order.get("notes") or "")
    if notes:
        elems.append(Paragraph(f"<b>Hinweis:</b> {notes}", s_value))
        elems.append(Spacer(1, 3*mm))

    elems.append(Paragraph(
        "Bitte prüfen Sie die Lieferung auf Vollständigkeit und Unversehrtheit. "
        "Mängel sind unverzüglich schriftlich anzuzeigen.",
        s_value,
    ))
    elems.append(Spacer(1, 10*mm))

    # ===== UNTERSCHRIFTEN =====
    sig_w = (USABLE_W - 10*mm) / 2

    def _sig_cell(b64_data, label):
        """Erzeuge eine Zelle mit (optional) Unterschriftsbild + Linie + Label."""
        if b64_data:
            try:
                if b64_data.startswith("data:"):
                    b64_data = b64_data.split(",", 1)[1]
                img_bytes = base64.b64decode(b64_data)
                img = RLImage(io.BytesIO(img_bytes), width=sig_w - 8*mm, height=22*mm, kind="proportional")
                return img
            except Exception:
                return Paragraph("_______________________________", s_sig)
        return Paragraph("_______________________________", s_sig)

    sig_sender_cell = _sig_cell(signature_sender_b64, "Lieferant")
    sig_receiver_cell = _sig_cell(signature_receiver_b64, "Empfänger")

    # Optional Ort/Datum darunter
    sign_meta = ""
    if signed_at_iso or signed_at_location:
        when = ""
        if signed_at_iso:
            try:
                # ISO 2026-05-30T15:30:00 -> 30.05.2026 15:30
                from datetime import datetime as _dt
                dtobj = _dt.fromisoformat(signed_at_iso.replace("Z", "+00:00"))
                when = dtobj.strftime("%d.%m.%Y %H:%M")
            except Exception:
                when = signed_at_iso
        parts = [p for p in [signed_at_location, when] if p]
        sign_meta = ", ".join(parts)

    label_left = "Datum / Unterschrift Lieferant"
    label_right = "Datum / Unterschrift Empfänger"
    if sign_meta:
        label_left = f"{sign_meta}  ·  Lieferant"
        label_right = f"{sign_meta}  ·  Empfänger"

    sig_block = Table([
        [sig_sender_cell, sig_receiver_cell],
        [Paragraph("———————————————————", s_sig), Paragraph("———————————————————", s_sig)],
        [Paragraph(label_left, s_sig_label), Paragraph(label_right, s_sig_label)],
    ], colWidths=[sig_w, sig_w])
    sig_block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, 0), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elems.append(sig_block)

    doc.build(elems)
    buf.seek(0)
    return buf


async def _fetch_contact_address(api_url, api_key, ssl_skip, contact_pk):
    """Helper: Adresse + Kontakt-Details aus EpiRent /v1/contact/{pk}.

    Extrahiert auch E-Mail-Adressen aus dem `communication[]`-Array
    (type=3 = E-Mail; is_invoice=True markiert die Rechnungs-Mail).
    """
    out = {"street": "", "postal_code": "", "city": "", "phone": "", "email": "", "email_invoice": "", "emails": []}
    if not contact_pk:
        return out
    try:
        headers = {"X-EPI-NO-SESSION": "True", "X-EPI-ACC-TOK": api_key}
        async with httpx.AsyncClient(timeout=10, verify=not ssl_skip) as c:
            r = await c.get(f"{api_url}/v1/contact/{contact_pk}", headers=headers)
            cd = r.json().get("payload")
            if isinstance(cd, list) and cd:
                cd = cd[0]
            if isinstance(cd, dict):
                a = cd.get("address") or {}
                out["street"] = a.get("street", "") or ""
                out["postal_code"] = a.get("postal_code", "") or ""
                out["city"] = a.get("city", "") or ""
                out["phone"] = cd.get("phone", "") or ""
                # E-Mails aus communication[]
                emails = []
                for comm in (cd.get("communication") or []):
                    uplink = (comm.get("uplink") or "").strip()
                    if comm.get("type") == 3 and "@" in uplink:
                        emails.append({
                            "email": uplink,
                            "is_invoice": bool(comm.get("is_invoice")),
                            "description": comm.get("description", "") or "",
                        })
                out["emails"] = emails
                if emails:
                    # primaere E-Mail: erste nicht-invoice, sonst irgendeine
                    primary = next((e["email"] for e in emails if not e["is_invoice"]), emails[0]["email"])
                    invoice = next((e["email"] for e in emails if e["is_invoice"]), "")
                    out["email"] = primary
                    out["email_invoice"] = invoice
    except Exception as e:
        logger.warning(f"Kontakt-Lookup fehlgeschlagen fuer PK={contact_pk}: {e}")
    return out


def _draw_ee_brand_chrome(canv, doc, page_w_mm=None, footer_y_mm=22, top_mm=10, left_mm=18, right_mm=18):
    """Wiederverwendbarer Painter fuer Eventenergie-Briefpapier-Header/Footer.

    Wird sowohl vom Lieferschein als auch von der Abrechnungs-PDF benutzt,
    damit beide Dokumente identisch aussehen.
    Erwartet: A4 Pagesize.
    """
    import os
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors as _c

    PURPLE = _c.HexColor("#7c3aed")
    BORDER = _c.HexColor("#d1d5db")
    MUTED = _c.HexColor("#6b7280")
    page_w, page_h = A4
    LEFT = left_mm * mm
    RIGHT = right_mm * mm

    canv.saveState()
    # ===== HEADER: Logo (50mm breit) + Purple-Trennlinie =====
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "portal_logo.png")
    if os.path.exists(logo_path):
        logo_w = 50 * mm
        logo_h = logo_w / 4.3
        canv.drawImage(logo_path, LEFT, page_h - top_mm * mm - logo_h,
                       width=logo_w, height=logo_h, mask="auto", preserveAspectRatio=True)
    canv.setStrokeColor(PURPLE)
    canv.setLineWidth(0.4)
    canv.line(LEFT, page_h - 23 * mm, page_w - RIGHT, page_h - 23 * mm)

    # ===== FOOTER: 2-Spalten Pflichtangaben =====
    footer_y = footer_y_mm * mm
    canv.setStrokeColor(BORDER)
    canv.setLineWidth(0.3)
    canv.line(LEFT, footer_y, page_w - RIGHT, footer_y)
    USABLE_W = page_w - LEFT - RIGHT
    col_w = USABLE_W / 2.0
    cols = [
        ("Eventenergie Deutschland GmbH & Co. KG",
         "Thyssenstraße 10",
         "56626 Andernach",
         "Tel.: +49 (0) 2632 30921-0",
         "Hotline: +49 (0) 800 POWER24",
         "info@eventenergie-deutschland.de",
         "www.eventenergie-deutschland.de"),
        ("Amtsgericht Koblenz: HRA 22723",
         "Finanzamt Mayen",
         "Ust.-ID: DE 333489815"),
    ]
    for ci, lines in enumerate(cols):
        x = LEFT + ci * col_w + 2
        for li, txt in enumerate(lines):
            canv.setFont("Helvetica", 6)
            canv.setFillColor(MUTED)
            canv.drawString(x, footer_y - 4 - li * 7, txt)
    # Seiten-Nr rechts
    canv.setFont("Helvetica", 6.5)
    canv.setFillColor(MUTED)
    canv.drawRightString(page_w - RIGHT, 8 * mm, f"Seite {doc.page}")
    canv.restoreState()


async def _fetch_chapter_items(api_url, api_key, ssl_skip, chapter_pk):
    """Helper: holt Sub-Artikel eines Kapitels via /v1/journal/filter?chid={chapter_pk}.

    EpiRent strukturiert order_items in 2+ Ebenen:
    - Top-Level Eintraege mit type=5 sind Kapitel (chapter_id=0)
    - In Kapitel: type=0 sind Artikel, type=21 sind "Ueberschriften" (Sub-Headings ohne Menge)
    - Reihenfolge: das Feld `_pos_no_intern` (1000, 2000, 3000, ...) gibt die EpiRent-Anzeige-Reihenfolge an
    """
    if not chapter_pk:
        return []
    try:
        headers = {"X-EPI-NO-SESSION": "True", "X-EPI-ACC-TOK": api_key}
        async with httpx.AsyncClient(timeout=15, verify=not ssl_skip) as c:
            r = await c.get(f"{api_url}/v1/journal/filter", headers=headers, params={"chid": chapter_pk})
            if r.status_code != 200:
                return []
            j = r.json()
            payload = j.get("payload") or []
            if not isinstance(payload, list):
                return []
            # Sortiere nach _pos_no_intern (echte EpiRent-Anzeige-Reihenfolge)
            return sorted(payload, key=lambda it: it.get("_pos_no_intern", 999999))
    except Exception as e:
        logger.warning(f"Chapter-items-Lookup fehlgeschlagen fuer chid={chapter_pk}: {e}")
        return []


@router.get("/epirent/{order_pk}/delivery-notes")
async def list_delivery_notes(order_pk: int, user: dict = Depends(_auth_user)):
    """Liste aller Lieferscheine zu einem Auftrag.

    Frontend nutzt das fuer die Submenu-Anzeige (mit "Lieferschein anlegen"-Button).
    """
    if user.get("role") == "freelancer":
        raise HTTPException(status_code=403, detail="Lieferscheine sind fuer Freelancer nicht verfuegbar")
    await _check_freelancer_order_access(user, order_pk)
    docs = await _db.delivery_notes.find(
        {"order_pk": order_pk},
        {"_id": 0, "signature_sender_b64": 0, "signature_receiver_b64": 0, "pdf_b64": 0},
    ).sort("created_at", -1).to_list(500)
    return docs


@router.get("/epirent/{order_pk}/customer-emails")
async def get_customer_emails(order_pk: int, user: dict = Depends(_auth_user)):
    """Liefert die im EpiRent-Kontakt hinterlegten E-Mail-Adressen.

    Frontend nutzt das im Lieferschein-E-Mail-Dialog fuer schnelle 1-Klick-Buttons.
    """
    if user.get("role") == "freelancer":
        raise HTTPException(status_code=403, detail="Freelancer haben keinen Zugriff")
    await _check_freelancer_order_access(user, order_pk)

    config = await _get_epirent_config()
    api_url = config.get("api_url", "").rstrip("/")
    api_key = config.get("api_key", "")
    ssl_skip = config.get("ssl_skip", False)

    raw = await _get_full_order(api_url, api_key, order_pk, ssl_skip)
    if not raw:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")

    contact = raw.get("contact") or {}
    contact_pk = contact.get("primary_key")
    details = await _fetch_contact_address(api_url, api_key, ssl_skip, contact_pk)
    return {
        "customer_name": contact.get("name") or "",
        "primary": details.get("email") or "",
        "invoice": details.get("email_invoice") or "",
        "all": details.get("emails") or [],
    }


@router.get("/epirent/{order_pk}/delivery-notes/prefill")
async def prefill_delivery_note(order_pk: int, user: dict = Depends(_auth_user)):
    """Liefert die Vorbefuellung fuer eine neue Lieferschein-Maske:
    - Empfaenger-Adresse (aus EpiRent address_delivery oder Kontakt)
    - Positionen aus order_items (mit position_no, title, amount, unit)
    - Vorgeschlagene LS-Nr. (naechste Sequenz)
    - Event/Dispo Zeitraum, Hinweise
    """
    if user.get("role") == "freelancer":
        raise HTTPException(status_code=403, detail="Lieferscheine sind fuer Freelancer nicht verfuegbar")
    await _check_freelancer_order_access(user, order_pk)

    config = await _get_epirent_config()
    api_url = config.get("api_url", "").rstrip("/")
    api_key = config.get("api_key", "")
    ssl_skip = config.get("ssl_skip", False)

    raw = await _get_full_order(api_url, api_key, order_pk, ssl_skip)
    if not raw:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")

    contact = raw.get("contact") or {}
    addr_d = raw.get("address_delivery") or {}
    contact_details = await _fetch_contact_address(api_url, api_key, ssl_skip, contact.get("primary_key"))

    deliv = {
        "name": addr_d.get("name") or contact.get("name") or "",
        "street": addr_d.get("street") or contact_details["street"],
        "postal_code": addr_d.get("postal_code") or contact_details["postal_code"],
        "city": addr_d.get("city") or contact_details["city"],
        "country": addr_d.get("country") or "Deutschland",
    }

    positions = []
    groups = []
    # Bereits gelieferte Mengen aus vorherigen LS aggregieren (pro primary_key)
    # damit der neue LS automatisch nur noch die Restmenge vorschlaegt.
    delivered_by_pk = {}
    async for ls_doc in _db.delivery_notes.find(
        {"order_pk": order_pk},
        {"_id": 0, "positions": 1},
    ):
        for p in (ls_doc.get("positions") or []):
            pk = p.get("primary_key")
            if pk is None:
                continue
            try:
                delivered_by_pk[pk] = delivered_by_pk.get(pk, 0) + float(p.get("amount") or 0)
            except (ValueError, TypeError):
                pass

    for i, it in enumerate(raw.get("order_items") or []):
        chapter_pk = it.get("primary_key")
        chapter_title = it.get("title") or ""
        chapter_pos = it.get("position_no_str") or str(i + 1)
        # Sub-Artikel pro Kapitel via _ref_chapter_items
        sub_items_raw = await _fetch_chapter_items(api_url, api_key, ssl_skip, chapter_pk)
        items = []
        for sub in sub_items_raw:
            sub_type = sub.get("type", 0)
            is_heading = (sub_type == 21)
            # Echte Menge: amount_total bevorzugt (1), amount_base ist 0 bei diesem Modus
            amt = 0 if is_heading else (sub.get("amount_total") or sub.get("amount_base") or sub.get("amount_external") or 1)
            # Einheit: EpiRent liefert sie oft leer -> Default "Stk." fuer normale Artikel
            unit_raw = (sub.get("unit_product") or "").strip()
            unit = "" if is_heading else (unit_raw or "Stk.")
            sub_pk = sub.get("primary_key")
            already_delivered = 0 if is_heading else float(delivered_by_pk.get(sub_pk, 0) or 0)
            remaining = 0 if is_heading else max(0, float(amt or 0) - already_delivered)
            # Default-Vorschlag:
            #  - Wenn noch NICHTS geliefert wurde -> volle Soll-Menge (User entscheidet
            #    ob er teilen will).
            #  - Wenn schon etwas auf vorherigen LS war -> nur noch die Restmenge,
            #    damit der naechste LS nicht aus Versehen Doppellieferungen erzeugt.
            default_amount = 0 if is_heading else (
                float(amt or 0) if already_delivered <= 0 else remaining
            )
            items.append({
                "primary_key": sub_pk,
                "is_heading": is_heading,
                "pos": sub.get("position_no_str") or "",
                "title": sub.get("title") or "",
                "product_no": str(sub.get("product_no", "")) if sub.get("product_no") and not is_heading else "",
                "inventory_no": sub.get("inventory_no", "") or "",
                "amount_total": float(amt or 0),
                "amount_delivered": already_delivered,
                "amount_remaining": remaining,
                "amount": default_amount,
                "unit": unit,
                "warehouse": sub.get("warehouse_str", "") or "",
                "weight_net": float(sub.get("weight_net") or 0),
                "remark": "",
            })
        # Bereits vollstaendig gelieferte Items rausfiltern - sie sollen im
        # neuen LS nicht mehr erscheinen. Headings nur dann behalten, wenn
        # mindestens 1 nicht-vollstaendig-gelieferter Artikel darunter folgt
        # (sonst wirken Headings ohne Inhalt verloren).
        filtered_items = []
        for it in items:
            if it.get("is_heading"):
                filtered_items.append(it)
                continue
            total = float(it.get("amount_total") or 0)
            delivered = float(it.get("amount_delivered") or 0)
            # Items komplett raus, wenn Soll > 0 und alles geliefert wurde.
            if total > 0 and delivered >= total:
                continue
            filtered_items.append(it)
        # Trailing-Headings ohne nachfolgenden Artikel entfernen (Saeuberung).
        cleaned_items = []
        for idx, it in enumerate(filtered_items):
            if it.get("is_heading"):
                has_following_article = any(
                    not nxt.get("is_heading") for nxt in filtered_items[idx + 1:]
                )
                if not has_following_article:
                    continue
            cleaned_items.append(it)
        # Gruppe komplett ueberspringen, wenn nichts mehr drin ist
        non_heading_left = [i for i in cleaned_items if not i.get("is_heading")]
        if not non_heading_left:
            continue
        groups.append({
            "chapter_pk": chapter_pk,
            "chapter_pos": chapter_pos,
            "chapter_title": chapter_title,
            "items": cleaned_items,
        })
        # Backward-compat: flatten in legacy "positions" array (chapter as header row)
        positions.append({
            "pos": chapter_pos,
            "title": chapter_title,
            "amount": 0,
            "unit": "",
            "remark": "",
            "is_chapter": True,
        })
        for sub in cleaned_items:
            positions.append({
                "pos": sub["pos"],
                "title": sub["title"],
                "amount": sub["amount"],
                "unit": sub["unit"],
                "remark": sub["remark"],
                "weight_net": sub.get("weight_net", 0),
                "is_chapter": False,
                "is_heading": sub.get("is_heading", False),
            })

    sched = raw.get("order_schedule") or []
    dispo_start = dispo_end = event_start = event_end = ""
    for s in sched:
        nm = s.get("name", "")
        if nm == "Dispo":
            dispo_start = s.get("date_start") or ""
            dispo_end = s.get("date_end") or ""
        elif nm == "Event":
            event_start = s.get("date_start") or ""
            event_end = s.get("date_end") or ""

    # Naechste Sequenz vorhersehen (ohne $inc, damit reine Vorschau)
    counter = await _db.delivery_note_counters.find_one({"order_pk": order_pk}) or {}
    next_seq = (counter.get("seq", 0) or 0) + 1
    order_no_fmt = raw.get("order_no_fmt") or str(raw.get("order_no", ""))
    suggested_no = f"{order_no_fmt}-LS-{next_seq:03d}"

    return {
        "order_no_fmt": order_no_fmt,
        "event": raw.get("event") or "",
        "customer_no": raw.get("customer_no", ""),
        "customer_name": contact.get("name") or "",
        "delivery_address": deliv,
        "groups": groups,
        "positions": positions,  # legacy flat list (chapters + items)
        "event_start": event_start, "event_end": event_end,
        "dispo_start": dispo_start, "dispo_end": dispo_end,
        "notes": raw.get("notes") or "",
        "suggested_delivery_note_no": suggested_no,
    }


@router.post("/epirent/{order_pk}/delivery-notes")
async def create_delivery_note(order_pk: int, body: dict, user: dict = Depends(_auth_user)):
    """Erstellt einen Lieferschein-Datensatz, generiert das PDF und persistiert beides.

    Body: {
      positions: [{pos, title, amount, unit, remark}, ...],
      notes_override?: str,
      signature_sender_b64?: data-URL PNG,
      signature_receiver_b64?: data-URL PNG,
      signed_at_location?: str,
    }
    """
    if user.get("role") == "freelancer":
        raise HTTPException(status_code=403, detail="Lieferscheine sind fuer Freelancer nicht verfuegbar")
    await _check_freelancer_order_access(user, order_pk)

    config = await _get_epirent_config()
    api_url = config.get("api_url", "").rstrip("/")
    api_key = config.get("api_key", "")
    ssl_skip = config.get("ssl_skip", False)

    raw = await _get_full_order(api_url, api_key, order_pk, ssl_skip)
    if not raw:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")

    contact = raw.get("contact") or {}
    contact_details = await _fetch_contact_address(api_url, api_key, ssl_skip, contact.get("primary_key"))

    order_no_fmt = raw.get("order_no_fmt") or str(raw.get("order_no", ""))
    counter = await _db.delivery_note_counters.find_one_and_update(
        {"order_pk": order_pk},
        {"$inc": {"seq": 1}, "$setOnInsert": {"order_pk": order_pk}},
        upsert=True,
        return_document=True,
    )
    seq = (counter or {}).get("seq", 1)
    delivery_note_no = f"{order_no_fmt}-LS-{seq:03d}"

    positions = body.get("positions") or []
    groups = body.get("groups") or []
    # Falls Frontend "groups" schickt -> flatten zu positions mit is_chapter-Flag
    if groups and not positions:
        for g in groups:
            positions.append({
                "pos": g.get("chapter_pos") or "",
                "title": g.get("chapter_title") or "",
                "amount": 0,
                "unit": "",
                "remark": "",
                "is_chapter": True,
            })
            for it in (g.get("items") or []):
                positions.append({
                    "pos": it.get("pos") or "",
                    "title": it.get("title") or "",
                    "amount": it.get("amount") or 0,
                    "unit": it.get("unit") or "",
                    "remark": it.get("remark") or "",
                    "product_no": it.get("product_no") or "",
                    "weight_net": float(it.get("weight_net") or 0),
                    "primary_key": it.get("primary_key"),
                    "is_chapter": False,
                    "is_heading": bool(it.get("is_heading", False)),
                })
    notes_override = body.get("notes_override")
    sig_sender = body.get("signature_sender_b64")
    sig_receiver = body.get("signature_receiver_b64")
    signed_loc = body.get("signed_at_location") or ""
    signed_iso = datetime.now(timezone.utc).isoformat()
    import uuid as _uuid_ls

    pdf_buf = _generate_delivery_note_pdf(
        raw, contact_details, delivery_note_no,
        positions=positions,
        notes_override=notes_override,
        signature_sender_b64=sig_sender,
        signature_receiver_b64=sig_receiver,
        signed_at_location=signed_loc,
        signed_at_iso=signed_iso,
    )

    # Persist PDF in MongoDB-GridFS-aehnlich -> wir nutzen base64 im Dokument (klein genug)
    pdf_bytes = pdf_buf.getvalue()
    import base64 as _b64
    pdf_b64 = _b64.b64encode(pdf_bytes).decode("ascii")

    doc = {
        "id": str(_uuid_ls.uuid4()),
        "order_pk": order_pk,
        "delivery_note_no": delivery_note_no,
        "seq": seq,
        "positions": positions,
        "notes_override": notes_override or "",
        "signature_sender_b64": sig_sender or "",
        "signature_receiver_b64": sig_receiver or "",
        "signed_at_location": signed_loc,
        "signed_at": signed_iso,
        "has_signatures": bool(sig_sender or sig_receiver),
        "pdf_b64": pdf_b64,
        "pdf_size": len(pdf_bytes),
        "created_at": signed_iso,
        "created_by_user_id": user.get("id"),
        "created_by_name": user.get("name", user.get("email", "")),
    }
    await _db.delivery_notes.insert_one(doc)
    return {
        "id": doc["id"],
        "delivery_note_no": delivery_note_no,
        "seq": seq,
        "pdf_size": len(pdf_bytes),
        "created_at": signed_iso,
        "has_signatures": doc["has_signatures"],
    }


@router.get("/epirent/{order_pk}/delivery-notes/{ls_id}/pdf")
async def get_delivery_note_pdf_by_id(order_pk: int, ls_id: str, user: dict = Depends(_auth_user), token: str = None):
    """Liefert das gespeicherte PDF eines bereits erstellten Lieferscheins."""
    from fastapi.responses import StreamingResponse
    import io
    import base64 as _b64

    if user.get("role") == "freelancer":
        raise HTTPException(status_code=403, detail="Lieferscheine sind fuer Freelancer nicht verfuegbar")
    await _check_freelancer_order_access(user, order_pk)

    doc = await _db.delivery_notes.find_one({"id": ls_id, "order_pk": order_pk}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Lieferschein nicht gefunden")

    pdf_b64 = doc.get("pdf_b64")
    if not pdf_b64:
        raise HTTPException(status_code=410, detail="PDF nicht mehr verfuegbar")
    pdf_bytes = _b64.b64decode(pdf_b64)
    fname = f"Lieferschein_{doc.get('delivery_note_no', ls_id)}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.delete("/epirent/{order_pk}/delivery-notes/{ls_id}")
async def delete_delivery_note(order_pk: int, ls_id: str, user: dict = Depends(_auth_user)):
    """Loescht einen Lieferschein (nur Admin, und nur solange noch nicht per E-Mail versandt)."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admin darf Lieferscheine loeschen")
    existing = await _db.delivery_notes.find_one(
        {"id": ls_id, "order_pk": order_pk}, {"_id": 0, "id": 1, "email_log": 1},
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Lieferschein nicht gefunden")
    if (existing.get("email_log") or []):
        raise HTTPException(
            status_code=423,
            detail="Lieferschein wurde bereits per E-Mail versandt und ist gesperrt",
        )
    r = await _db.delivery_notes.delete_one({"id": ls_id, "order_pk": order_pk})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lieferschein nicht gefunden")
    return {"deleted": True}


@router.post("/epirent/{order_pk}/delivery-notes/{ls_id}/email")
async def email_delivery_note(order_pk: int, ls_id: str, body: dict, user: dict = Depends(_auth_user)):
    """Versendet einen Lieferschein per E-Mail an die angegebene Adresse.

    Body: {to_email: str}

    Mehrfaches Versenden ist erlaubt. Jeder Versand wird in `email_log` getrackt.
    """
    if user.get("role") == "freelancer":
        raise HTTPException(status_code=403, detail="Freelancer duerfen keine Lieferscheine versenden")
    await _check_freelancer_order_access(user, order_pk)

    to_email = (body.get("to_email") or "").strip()
    if not to_email or "@" not in to_email:
        raise HTTPException(status_code=400, detail="Gueltige E-Mail erforderlich")

    doc = await _db.delivery_notes.find_one({"id": ls_id, "order_pk": order_pk}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Lieferschein nicht gefunden")

    # Lock-Stufe 1: bereits unterschrieben -> nur Admin darf (re-)versenden
    if doc.get("has_signatures") and user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Lieferschein ist unterschrieben - nur Admin darf versenden",
        )
    # Lock-Stufe 2: bereits per E-Mail versandt -> komplett gesperrt
    if (doc.get("email_log") or []):
        raise HTTPException(
            status_code=423,
            detail="Lieferschein wurde bereits versandt und ist gesperrt",
        )

    pdf_b64 = doc.get("pdf_b64")
    if not pdf_b64:
        raise HTTPException(status_code=410, detail="PDF nicht mehr verfuegbar")

    import base64 as _b64
    pdf_bytes = _b64.b64decode(pdf_b64)
    ls_no = doc.get("delivery_note_no", ls_id)

    # E-Mail-Inhalt (komplett ASCII-safe, keine Umlaute / Sonderzeichen)
    subject = f"Lieferschein {ls_no} - Eventenergie Deutschland"
    html = f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f5f5f5;">
<div style="max-width:560px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e5e5;">
  <div style="padding:24px 28px;background:#7c3aed;color:#fff;">
    <h2 style="margin:0;font-size:18px;">Lieferschein {ls_no}</h2>
  </div>
  <div style="padding:24px 28px;color:#1f2937;line-height:1.5;font-size:14px;">
    <p>Sehr geehrte Damen und Herren,</p>
    <p>anbei erhalten Sie den Lieferschein zu Ihrem Auftrag.</p>
    <p>Bei Fragen erreichen Sie uns unter <a href="tel:+49263230921-0">+49 (0) 2632 30921-0</a> oder
    per Mail an <a href="mailto:info@eventenergie-deutschland.de">info@eventenergie-deutschland.de</a>.</p>
    <p style="margin-top:24px;">Mit freundlichen Gruessen<br/>Eventenergie Deutschland GmbH &amp; Co. KG</p>
  </div>
</div>
</body></html>
"""
    try:
        from email_service import send_email_with_attachment
        send_email_with_attachment(
            to_email=to_email,
            subject=subject,
            html_body=html,
            attachment_bytes=pdf_bytes,
            attachment_filename=f"Lieferschein_{ls_no}.pdf",
        )
    except Exception as e:
        logger.error(f"E-Mail-Versand Lieferschein {ls_no} an {to_email} fehlgeschlagen: {e}")
        raise HTTPException(status_code=502, detail=f"E-Mail-Versand fehlgeschlagen: {str(e)[:200]}")

    # Versand-Log persistieren (im Lieferschein-Dokument)
    now_iso = datetime.now(timezone.utc).isoformat()
    entry = {
        "to": to_email,
        "sent_at": now_iso,
        "sent_by_user_id": user.get("id"),
        "sent_by_name": user.get("name", user.get("email", "")),
    }
    await _db.delivery_notes.update_one(
        {"id": ls_id, "order_pk": order_pk},
        {"$push": {"email_log": entry}, "$set": {"last_email_to": to_email, "last_email_at": now_iso}},
    )

    return {"sent": True, "to": to_email, "sent_at": now_iso}




@router.put("/epirent/{order_pk}/settings")
async def update_order_settings(
    order_pk: int, data: OrderSettingsUpdate, user: dict = Depends(_auth_user)
):
    """Update order-specific settings like radius and center coordinates."""
    update = {"order_pk": order_pk, "updated_at": datetime.now(timezone.utc).isoformat()}
    if data.radius_km is not None:
        update["radius_km"] = data.radius_km
    if data.center_lat is not None:
        update["center_lat"] = data.center_lat
    if data.center_lng is not None:
        update["center_lng"] = data.center_lng

    await _db.order_settings.update_one(
        {"order_pk": order_pk}, {"$set": update}, upsert=True
    )
    return {"ok": True}


@router.get("/epirent/{order_pk}/generators")
async def get_generators_in_radius(
    order_pk: int,
    user: dict = Depends(_auth_user),
):
    """Find generators within the order's radius + manually assigned ones."""
    settings = await _db.order_settings.find_one({"order_pk": order_pk}, {"_id": 0})
    manual_ids = (settings or {}).get("manual_generator_ids") or []

    if not settings or not settings.get("center_lat"):
        # Auch wenn kein Radius gesetzt, manuelle Zuordnungen liefern
        if not manual_ids:
            return {"generators": []}
        center_lat = center_lng = None
        radius_km = 0.0
    else:
        center_lat = settings["center_lat"]
        center_lng = settings["center_lng"]
        radius_km = settings.get("radius_km", 5.0)

    # Get all generators (with or without GPS, fuer manuell zugeordnete brauchen
    # wir auch die ohne Koordinaten)
    generators = await _db.generators.find({}, {"_id": 0}).to_list(2000)

    seen_ids = set()
    nearby = []

    def _enrich_telemetry(snap):
        """Normalize Pi-ingest fields to standard frontend field names."""
        if not snap:
            return None
        if "power_total_w" in snap and "power_kw" not in snap:
            snap["power_kw"] = round(snap["power_total_w"] / 1000, 2) if snap.get("power_total_w") else 0
        if "fuel_level_pct" in snap and "fuel_level" not in snap:
            snap["fuel_level"] = snap.get("fuel_level_pct")
        return snap

    async def _get_telemetry(gen_doc, gen_id):
        latest = gen_doc.get("latest_snapshot") if gen_doc else None
        if not latest and gen_id.startswith("dev-"):
            dev = await _db.devices.find_one(
                {"id": gen_id[4:]}, {"_id": 0, "latest_snapshot": 1}
            )
            if dev:
                latest = dev.get("latest_snapshot")
        return _enrich_telemetry(latest)

    for g in generators:
        gid = g.get("id")
        if not gid:
            continue
        is_manual = gid in manual_ids
        lat = g.get("latitude")
        lng = g.get("longitude")
        dist = None
        in_radius = False
        if lat is not None and lng is not None and center_lat is not None:
            try:
                dist = _haversine_km(center_lat, center_lng, float(lat), float(lng))
                in_radius = dist <= radius_km
            except (ValueError, TypeError):
                dist = None
        if not in_radius and not is_manual:
            continue
        seen_ids.add(gid)
        nearby.append({
            "id": gid,
            "name": g.get("name", ""),
            "model": g.get("model", ""),
            "serial_number": g.get("serial_number", ""),
            "status": g.get("status", "offline"),
            "latitude": lat,
            "longitude": lng,
            "distance_km": round(dist, 2) if dist is not None else None,
            "last_seen": g.get("last_seen"),
            "is_manual": is_manual,
            "latest_telemetry": await _get_telemetry(g, gid),
        })

    # Auch device-basierte virtuelle Generatoren (Stromerzeuger/Lichtmast aus
    # db.devices) auflisten, falls in manual_ids referenziert (id-Format: dev-*)
    for mid in manual_ids:
        if mid in seen_ids:
            continue
        if mid.startswith("dev-"):
            dev = await _db.devices.find_one({"id": mid[4:]}, {"_id": 0})
            if dev:
                nearby.append({
                    "id": mid,
                    "name": dev.get("user_field") or dev.get("model") or dev.get("serial_number", ""),
                    "model": dev.get("controller") or dev.get("model") or "–",
                    "serial_number": dev.get("serial_number", ""),
                    "status": dev.get("mqtt_status", "offline"),
                    "latitude": dev.get("latitude"),
                    "longitude": dev.get("longitude"),
                    "distance_km": None,
                    "last_seen": dev.get("last_seen"),
                    "is_manual": True,
                    "latest_telemetry": _enrich_telemetry(dev.get("latest_snapshot")),
                })

    nearby.sort(key=lambda x: (not x["is_manual"], x.get("distance_km") or 9999))
    return {
        "generators": nearby,
        "center_lat": center_lat,
        "center_lng": center_lng,
        "radius_km": radius_km,
    }


@router.post("/epirent/{order_pk}/generators/manual")
async def add_manual_generator(
    order_pk: int, data: dict = Body(...), user: dict = Depends(_auth_user)
):
    """Manuell einen Generator dem Auftrag zuordnen + automatisch einen offenen
    Eintrag in der Einsatzhistorie des Generators anlegen."""
    generator_id = (data or {}).get("generator_id", "").strip()
    if not generator_id:
        raise HTTPException(400, "generator_id fehlt")

    await _db.order_settings.update_one(
        {"order_pk": order_pk},
        {"$addToSet": {"manual_generator_ids": generator_id},
         "$set": {"order_pk": order_pk, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )

    # Auto-Deployment-Eintrag (nur wenn noch nicht vorhanden)
    existing = await _db.deployment_history.find_one({
        "order_pk": order_pk,
        "generator_id": generator_id,
        "auto_assigned": True,
    })
    if not existing:
        # Generator-Name ermitteln
        gen_name = ""
        gen_doc = await _db.generators.find_one({"id": generator_id}, {"_id": 0, "name": 1, "serial_number": 1})
        if gen_doc:
            gen_name = gen_doc.get("name") or gen_doc.get("serial_number") or ""
        elif generator_id.startswith("dev-"):
            dev = await _db.devices.find_one({"id": generator_id[4:]}, {"_id": 0})
            if dev:
                gen_name = dev.get("user_field") or dev.get("model") or dev.get("serial_number", "")
        # Order-Meta (Name) holen aus orders_cache
        order_doc = await _db.orders_cache.find_one(
            {"primary_key": order_pk}, {"_id": 0, "name": 1, "title": 1}
        ) or await _db.orders_cache.find_one(
            {"primary_key": str(order_pk)}, {"_id": 0, "name": 1, "title": 1}
        )
        order_label = (order_doc or {}).get("name") or (order_doc or {}).get("title") or f"Auftrag #{order_pk}"
        import uuid as _uuid_h
        await _db.deployment_history.insert_one({
            "id": str(_uuid_h.uuid4()),
            "order_pk": order_pk,
            "order_label": order_label,
            "generator_id": generator_id,
            "generator_name": gen_name,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "stopped_at": None,
            "operating_hours": None,
            "kwh_start": None, "kwh_end": None,
            "faults": None, "notes": "Automatisch zugeordnet",
            "auto_assigned": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get("name", user.get("email", "")),
        })
    return {"ok": True}


@router.delete("/epirent/{order_pk}/generators/manual/{generator_id}")
async def remove_manual_generator(
    order_pk: int, generator_id: str, user: dict = Depends(_auth_user)
):
    """Manuelle Zuordnung wieder entfernen + den Auto-Deployment-Eintrag loeschen."""
    await _db.order_settings.update_one(
        {"order_pk": order_pk},
        {"$pull": {"manual_generator_ids": generator_id},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Nur Auto-Deployments loeschen (manuelle Eintraege nicht antasten)
    await _db.deployment_history.delete_many({
        "order_pk": order_pk,
        "generator_id": generator_id,
        "auto_assigned": True,
    })
    return {"ok": True}


# ── Deployment History ──

@router.get("/epirent/{order_pk}/deployments")
async def get_order_deployments(order_pk: int, user: dict = Depends(_auth_user)):
    """Get deployment history entries for an order."""
    deployments = await _db.deployment_history.find(
        {"order_pk": order_pk}, {"_id": 0}
    ).sort("started_at", -1).to_list(100)
    return {"deployments": deployments}


@router.post("/epirent/{order_pk}/deployments")
async def create_deployment(order_pk: int, data: DeploymentCreate, user: dict = Depends(_auth_user)):
    """Create a deployment history entry for an order."""
    import uuid
    doc = {
        "id": str(uuid.uuid4()),
        "order_pk": order_pk,
        "generator_id": data.generator_id,
        "generator_name": data.generator_name,
        "started_at": data.started_at,
        "stopped_at": data.stopped_at,
        "operating_hours": data.operating_hours,
        "kwh_start": data.kwh_start,
        "kwh_end": data.kwh_end,
        "faults": data.faults,
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("name", user.get("email", "")),
    }
    await _db.deployment_history.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/deployments/by-generator/{generator_id}")
async def get_generator_deployments(generator_id: str, user: dict = Depends(_auth_user)):
    """Get deployment history for a specific generator.

    Falls `order_label` nur als generisches Fallback ("Auftrag #<pk>") in der
    History gespeichert wurde (z.B. weil der orders_cache zum Zeitpunkt des
    Auto-Matches noch keinen Event-Namen kannte), loesen wir das Label HIER
    live aus dem aktuellen orders_cache nach. So sieht der User sofort den
    Projektnamen / das Event, sobald EpiRent ihn ein-syncted hat - ohne dass
    wir alte History-Records anfassen muessen.
    """
    deployments = await _db.deployment_history.find(
        {"generator_id": generator_id}, {"_id": 0}
    ).sort("started_at", -1).to_list(100)

    # Live-Label-Resolve fuer Eintraege mit generischem Fallback
    pks_to_resolve = set()
    for d in deployments:
        pk = d.get("order_pk")
        label = d.get("order_label") or ""
        if pk and (not label or label.startswith("Auftrag #")):
            pks_to_resolve.add(pk)

    if pks_to_resolve:
        # Beide Typen (int+str) abfangen, weil orders_cache mal so mal so anlegt
        pk_list = list(pks_to_resolve) + [str(p) for p in pks_to_resolve]
        cache_docs = await _db.orders_cache.find(
            {"primary_key": {"$in": pk_list}},
            {"_id": 0, "primary_key": 1, "name": 1, "title": 1, "event": 1}
        ).to_list(len(pk_list))
        pk_to_label = {}
        for doc in cache_docs:
            pretty = doc.get("name") or doc.get("title") or doc.get("event")
            if pretty:
                pk_to_label[doc["primary_key"]] = pretty
                pk_to_label[str(doc["primary_key"])] = pretty
        for d in deployments:
            pk = d.get("order_pk")
            if pk and pk in pk_to_label:
                d["order_label"] = pk_to_label[pk]

    return {"deployments": deployments}



# ── Order Assets (manual placement) ──

@router.get("/epirent/{order_pk}/assets")
async def get_order_assets(order_pk: int, user: dict = Depends(_auth_user)):
    """Get all manually placed assets for an order.

    Kein hartes 500er-Limit mehr: Bei Grossevents (Rock am Ring, 24h Rennen
    etc.) hat ein Auftrag schnell mehrere hundert Verteiler / Lichtmasten /
    Tanks. Vorher: `to_list(500)` + Sort DESC nach created_at hat die zuerst
    angelegten/kopierten Artikel ab Position 501 stillschweigend verschluckt -
    User hat das als "Verteiler kommen nicht alle an" wahrgenommen.
    Neu: 10.000 als Sicherheits-Cap (immer noch DOS-Schutz, aber praktisch
    unbeschraenkt fuer realistische Auftraege)."""
    assets = await _db.order_assets.find(
        {"order_pk": order_pk}, {"_id": 0}
    ).sort("created_at", -1).to_list(10000)
    return {"assets": assets}


@router.post("/epirent/{order_pk}/assets")
async def create_order_asset(order_pk: int, data: OrderAssetCreate, user: dict = Depends(_auth_user)):
    """Create a manually placed asset for an order."""
    import uuid
    doc = {
        "id": str(uuid.uuid4()),
        "order_pk": order_pk,
        "asset_type": data.asset_type,
        "latitude": data.latitude,
        "longitude": data.longitude,
        "label": data.label or data.asset_type,
        "plus_code": data.plus_code,
        "status": "placed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("name", user.get("email", "")),
    }
    await _db.order_assets.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/epirent/{order_pk}/assets/{asset_id}/status")
async def update_asset_status(order_pk: int, asset_id: str, user: dict = Depends(_auth_user)):
    """Toggle asset status between placed and dismantled."""
    asset = await _db.order_assets.find_one({"id": asset_id, "order_pk": order_pk})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset nicht gefunden")

    current = asset.get("status", "placed")
    if current == "placed":
        new_status = "dismantled"
        update = {
            "status": new_status,
            "dismantled_at": datetime.now(timezone.utc).isoformat(),
            "dismantled_by": user.get("name", user.get("email", "")),
        }
    else:
        new_status = "placed"
        update = {
            "status": new_status,
            "dismantled_at": None,
            "dismantled_by": None,
        }

    await _db.order_assets.update_one({"id": asset_id}, {"$set": update})
    return {"ok": True, "status": new_status}


@router.delete("/epirent/{order_pk}/assets/{asset_id}")
async def delete_order_asset(order_pk: int, asset_id: str, user: dict = Depends(_auth_user)):
    """Delete a manually placed asset. Nur Admin (Asset-Loeschen ist
    irreversibel - kein Soft-Delete).

    Schutz gegen Daten-Inkonsistenzen: wenn dieser Asset noch in Messprotokollen
    referenziert wird (typisch fuer Verteiler), wird das Loeschen verweigert -
    sonst entstehen Geister-Protokolle mit toter `verteiler_asset_id`.
    """
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admin darf Artikel loeschen")
    # Referenz-Check: Messprotokolle, die diesen Asset noch zeigen
    ref_count = await _db.messprotokolle.count_documents({"data.verteiler_asset_id": asset_id})
    if ref_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Loeschen abgelehnt: {ref_count} Messprotokoll(e) verweisen "
                f"noch auf diesen Artikel. Bitte erst die Messprotokolle "
                f"loeschen oder das Asset stattdessen als 'abgebaut' markieren."
            ),
        )
    result = await _db.order_assets.delete_one({"id": asset_id, "order_pk": order_pk})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Asset nicht gefunden")
    return {"ok": True}


@router.post("/epirent/{order_pk}/assets/bulk-dismantle")
async def bulk_dismantle_assets(
    order_pk: int, data: BulkDismantle, user: dict = Depends(_auth_user),
):
    """Markiert mehrere Artikel auf einmal als 'abgebaut'.
    Anwendungsfall: Trupp C steht am Auftragsende vor 50 Verteilern und will
    sie per Karten-Auswahl in einem Rutsch abhaken statt 50x einzeln zu tippen.
    Idempotent: bereits abgebaute Items werden ignoriert."""
    if not data.asset_ids:
        return {"ok": True, "updated": 0}
    now = datetime.now(timezone.utc).isoformat()
    actor = user.get("name", user.get("email", ""))
    result = await _db.order_assets.update_many(
        {
            "order_pk": order_pk,
            "id": {"$in": data.asset_ids},
            "status": {"$ne": "dismantled"},
        },
        {"$set": {
            "status": "dismantled",
            "dismantled_at": now,
            "dismantled_by": actor,
        }},
    )
    return {"ok": True, "updated": result.modified_count}


@router.patch("/epirent/{order_pk}/assets/{asset_id}")
async def edit_order_asset(
    order_pk: int, asset_id: str, data: AssetEdit, user: dict = Depends(_auth_user),
):
    """Aktualisiert die Metadaten eines Assets (Typ, Bezeichnung, Position,
    Plus Code). Status/dismantled-Felder werden hier NICHT angefasst — dafuer
    gibt es separate Endpoints (/status, /move, /bulk-dismantle).

    Schutz gegen Daten-Inkonsistenzen: Wenn ein Asset noch in Messprotokollen
    referenziert wird (typisch fuer Verteiler), darf der `asset_type` NICHT
    umgestellt werden - sonst zeigen Messprotokolle auf einen Lichtmast/Tank
    und der Verteiler verschwindet aus der Verteiler-Ansicht.
    """
    asset = await _db.order_assets.find_one({"id": asset_id, "order_pk": order_pk}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset nicht gefunden")
    update = {k: v for k, v in data.dict(exclude_unset=True).items() if v is not None}
    if not update:
        return asset

    # Asset-Typ-Wechsel: Referenz-Check, wenn von "Verteiler" auf anderen Typ
    new_type = update.get("asset_type")
    old_type = asset.get("asset_type")
    type_changed = new_type is not None and new_type != old_type
    if type_changed and (old_type or "").lower() == "verteiler":
        ref_count = await _db.messprotokolle.count_documents({"data.verteiler_asset_id": asset_id})
        if ref_count > 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Typ-Wechsel abgelehnt: {ref_count} Messprotokoll(e) verweisen "
                    f"noch auf diesen Verteiler. Bitte erst die Messprotokolle "
                    f"loeschen oder einem anderen Verteiler zuweisen, bevor der "
                    f"Typ geaendert wird."
                ),
            )

    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    update["updated_by"] = user.get("name", user.get("email", ""))

    set_ops: dict = {"$set": update}
    if type_changed:
        # Audit-Kommentar bei jedem Typ-Wechsel, damit forensisch
        # nachvollziehbar bleibt wer wann den Typ geaendert hat.
        import uuid
        audit = {
            "id": str(uuid.uuid4()),
            "text": f"Artikeltyp geaendert: {old_type or '?'} -> {new_type}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get("name") or user.get("email") or "System",
            "created_by_id": user.get("id") or user.get("user_id") or user.get("email") or "",
            "kind": "system",
        }
        set_ops["$push"] = {"comments": audit}

    await _db.order_assets.update_one({"id": asset_id, "order_pk": order_pk}, set_ops)
    updated = await _db.order_assets.find_one({"id": asset_id, "order_pk": order_pk}, {"_id": 0})
    return updated


@router.patch("/epirent/{order_pk}/assets/{asset_id}/move")
async def move_order_asset(
    order_pk: int, asset_id: str, data: AssetMove,
    user: dict = Depends(_auth_user),
):
    """Verschiebt einen Artikel in einen anderen Auftrag.
    Anwendungsfall: Beim Aufbau wurde ein Lichtmast versehentlich auf Auftrag A
    gebucht statt auf Auftrag B (gleicher Termin, andere Kostenstelle). Statt
    loeschen + neu anlegen kann der User den Eintrag direkt umhaengen - dabei
    bleiben Kommentare, Position und Status erhalten. Audit-Spur als Kommentar.
    Nur Admin (folgenschwere Aktion - Asset verschwindet aus Quell-Auftrag).
    """
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admin darf Artikel verschieben")
    if data.target_order_pk == order_pk:
        raise HTTPException(400, "Ziel-Auftrag muss vom aktuellen Auftrag verschieden sein")
    target = await _db.orders_cache.find_one(
        {"primary_key": data.target_order_pk}, {"_id": 0, "primary_key": 1, "event": 1, "order_no": 1, "address": 1}
    )
    if not target:
        raise HTTPException(404, "Ziel-Auftrag nicht gefunden")
    asset = await _db.order_assets.find_one(
        {"id": asset_id, "order_pk": order_pk}, {"_id": 0, "id": 1}
    )
    if not asset:
        raise HTTPException(404, "Asset nicht gefunden")
    # Audit-Kommentar mit Quell-Auftrag, damit nachvollziehbar bleibt warum
    # der Artikel hier auftaucht.
    import uuid
    audit = {
        "id": str(uuid.uuid4()),
        "text": f"Verschoben aus Auftrag #{order_pk} nach #{data.target_order_pk}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("name") or user.get("email") or "System",
        "created_by_id": user.get("id") or user.get("user_id") or user.get("email") or "",
        "kind": "system",
    }
    await _db.order_assets.update_one(
        {"id": asset_id, "order_pk": order_pk},
        {"$set": {"order_pk": data.target_order_pk}, "$push": {"comments": audit}},
    )
    return {"ok": True, "target": target}


@router.post("/epirent/{order_pk}/copy-to")
async def copy_assets_and_generators(
    order_pk: int, data: CopyToOrder, user: dict = Depends(_auth_user),
):
    """Admin-Funktion: kopiert ausgewaehlte Artikel und/oder Generator-Zuordnungen
    in einen anderen Auftrag. Anwendungsfall: gleiches Equipment bleibt ueber
    mehrere Folge-Events am selben Standort - der User muss es nicht alles neu
    eintragen. Artikel werden 1:1 dupliziert (inkl. Position, Kommentare und
    Status), Generatoren werden zusaetzlich der Ziel-Auftragsliste hinzugefuegt
    (kein Verschieben - sie bleiben in beiden Auftraegen sichtbar).
    Audit-Kommentar/-Notiz haengt am kopierten Objekt damit nachvollziehbar
    bleibt wo es herkommt.
    """
    if user.get("role") != "admin":
        raise HTTPException(403, "Nur Admins duerfen kopieren")
    if data.target_order_pk == order_pk:
        raise HTTPException(400, "Ziel-Auftrag muss vom aktuellen Auftrag verschieden sein")
    if not data.asset_ids and not data.generator_ids and not data.document_ids:
        raise HTTPException(400, "Keine Auswahl uebergeben")
    target = await _db.orders_cache.find_one(
        {"primary_key": data.target_order_pk},
        {"_id": 0, "primary_key": 1, "event": 1, "order_no": 1, "name": 1, "title": 1},
    )
    if not target:
        raise HTTPException(404, "Ziel-Auftrag nicht gefunden")

    import uuid
    now = datetime.now(timezone.utc).isoformat()
    creator = user.get("name") or user.get("email") or "System"
    creator_id = user.get("id") or user.get("user_id") or user.get("email") or ""

    copied_assets = 0
    if data.asset_ids:
        cursor = _db.order_assets.find(
            {"order_pk": order_pk, "id": {"$in": data.asset_ids}}
        )
        async for asset in cursor:
            asset.pop("_id", None)
            new_doc = dict(asset)
            new_doc["id"] = str(uuid.uuid4())
            new_doc["order_pk"] = data.target_order_pk
            audit = {
                "id": str(uuid.uuid4()),
                "text": f"Kopiert aus Auftrag #{order_pk}",
                "created_at": now,
                "created_by": creator,
                "created_by_id": creator_id,
                "kind": "system",
            }
            new_doc["comments"] = list(new_doc.get("comments") or []) + [audit]
            await _db.order_assets.insert_one(new_doc)
            new_doc.pop("_id", None)
            copied_assets += 1

    copied_generators = 0
    if data.generator_ids:
        # Nur tatsaechlich neue IDs zaehlen damit das Frontend einen ehrlichen
        # Count anzeigen kann (addToSet bei bereits zugewiesenen Generatoren
        # wuerde sonst stillschweigend nichts tun und der Count waere falsch).
        existing_settings = await _db.order_settings.find_one(
            {"order_pk": data.target_order_pk}, {"_id": 0, "manual_generator_ids": 1}
        ) or {}
        already = set((existing_settings.get("manual_generator_ids") or []))
        new_ids = [gid for gid in data.generator_ids if gid not in already]

        if new_ids:
            await _db.order_settings.update_one(
                {"order_pk": data.target_order_pk},
                {
                    "$addToSet": {"manual_generator_ids": {"$each": new_ids}},
                    "$setOnInsert": {"order_pk": data.target_order_pk},
                    "$set": {"updated_at": now},
                },
                upsert=True,
            )

        # Auto-Deployment-Eintraege analog zu add_manual_generator
        order_label = target.get("name") or target.get("title") or target.get("event") or f"Auftrag #{data.target_order_pk}"
        for gid in new_ids:
            existing = await _db.deployment_history.find_one({
                "order_pk": data.target_order_pk,
                "generator_id": gid,
                "auto_assigned": True,
            })
            if existing:
                continue
            gen_name = ""
            gen_doc = await _db.generators.find_one(
                {"id": gid}, {"_id": 0, "name": 1, "serial_number": 1}
            )
            if gen_doc:
                gen_name = gen_doc.get("name") or gen_doc.get("serial_number") or ""
            elif gid.startswith("dev-"):
                dev = await _db.devices.find_one({"id": gid[4:]}, {"_id": 0})
                if dev:
                    gen_name = dev.get("user_field") or dev.get("model") or dev.get("serial_number", "")
            await _db.deployment_history.insert_one({
                "id": str(uuid.uuid4()),
                "order_pk": data.target_order_pk,
                "order_label": order_label,
                "generator_id": gid,
                "generator_name": gen_name,
                "started_at": now,
                "stopped_at": None,
                "operating_hours": None,
                "kwh_start": None, "kwh_end": None,
                "faults": None,
                "notes": f"Kopiert aus Auftrag #{order_pk}",
                "auto_assigned": True,
                "created_at": now,
                "created_by": creator,
            })
            copied_generators += 1

    copied_documents = 0
    if data.document_ids:
        # Dokumente werden physisch dupliziert: DB-Doc + Datei auf Platte.
        # order_pk wird in order_documents als STRING gespeichert (anders als
        # bei order_assets), daher str() Cast hier. Datei-Layout:
        # storage/order_documents/{order_pk}/{uuid}.{ext}
        import shutil as _shutil
        src_pk_str = str(order_pk)
        tgt_pk_str = str(data.target_order_pk)
        tgt_dir = _os.path.join(_ORDER_DOC_STORAGE, tgt_pk_str)
        _os.makedirs(tgt_dir, exist_ok=True)
        cursor = _db.order_documents.find(
            {"order_pk": src_pk_str, "id": {"$in": data.document_ids}}
        )
        async for doc in cursor:
            doc.pop("_id", None)
            old_filename = doc.get("filename") or ""
            # Extension aus altem Filename uebernehmen damit ZIP/MIME stimmen
            _, ext = _os.path.splitext(old_filename)
            new_id = str(uuid.uuid4())
            new_filename = f"{new_id}{ext}"
            src_path = _os.path.join(_ORDER_DOC_STORAGE, src_pk_str, old_filename)
            dst_path = _os.path.join(tgt_dir, new_filename)
            if not _os.path.exists(src_path):
                # Quelldatei fehlt - DB-Eintrag ueberspringen damit kein
                # toter Verweis im Ziel-Auftrag landet.
                continue
            try:
                _shutil.copy2(src_path, dst_path)
            except Exception:
                continue
            new_doc = dict(doc)
            new_doc["id"] = new_id
            new_doc["order_pk"] = tgt_pk_str
            new_doc["filename"] = new_filename
            new_doc["uploaded_at"] = now
            new_doc["uploaded_by"] = creator
            # Original-Name mit Hinweis ergaenzen waere zu invasiv -
            # stattdessen den ursprünglichen Namen behalten, die Audit-Spur
            # kommt aus uploaded_by + uploaded_at.
            await _db.order_documents.insert_one(new_doc)
            copied_documents += 1

    return {
        "ok": True,
        "copied_assets": copied_assets,
        "copied_generators": copied_generators,
        "copied_documents": copied_documents,
        "target": target,
    }


@router.get("/epirent-search/quick")
async def quick_search_orders(
    q: str = Query("", description="Suchstring (Event/Auftragsnr/Kunde)"),
    exclude_pk: Optional[int] = Query(None),
    limit: int = 20,
    user: dict = Depends(_auth_user),
):
    """Schlanker Auftrags-Search-Endpoint fuer Asset-Move-Picker.
    Gibt nur die Felder zurueck die der Picker braucht (event, order_no, primary_key).
    Lebt hier statt im Haupt-Listen-Endpoint, damit das Filter-Setup dort nicht
    mit-kompliziert wird; der Picker braucht eine eigene, fokussierte Query.
    """
    qf = (q or "").strip()
    mongo_q = {}
    if exclude_pk is not None:
        mongo_q["primary_key"] = {"$ne": exclude_pk}
    if qf:
        # Case-insensitive Suche ueber Event-Name + Auftragsnummer + Kundenname
        rx = {"$regex": qf, "$options": "i"}
        mongo_q["$or"] = [
            {"event": rx}, {"order_no": rx}, {"customer_name": rx},
            {"address": rx},
        ]
        # Wenn rein numerisch, auch nach primary_key matchen
        if qf.isdigit():
            existing_or = mongo_q["$or"]
            existing_or.append({"primary_key": int(qf)})
    cursor = _db.orders_cache.find(
        mongo_q,
        {"_id": 0, "primary_key": 1, "event": 1, "order_no": 1, "customer_name": 1, "address": 1, "start_date": 1},
    ).sort("start_date", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"orders": items}


# ── Asset Comments ──
# Kommentare werden als eingebettetes Array im Asset-Dokument gespeichert.
# Vorteil: ein einziger DB-Read in /assets liefert alle Kommentare gleich mit,
# kein zusaetzlicher Roundtrip pro Asset noetig. Loeschen ist nur fuer den
# Autor des Kommentars erlaubt (bzw. fuer Admins, falls noetig).

@router.post("/epirent/{order_pk}/assets/{asset_id}/comments")
async def add_asset_comment(
    order_pk: int, asset_id: str, data: AssetCommentCreate,
    user: dict = Depends(_auth_user),
):
    """Append a comment to an asset. Returns the new comment object."""
    text = (data.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Kommentar darf nicht leer sein")
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="Kommentar zu lang (max. 2000 Zeichen)")
    asset = await _db.order_assets.find_one({"id": asset_id, "order_pk": order_pk}, {"_id": 0, "id": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset nicht gefunden")
    import uuid
    comment = {
        "id": str(uuid.uuid4()),
        "text": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("name") or user.get("email") or "",
        "created_by_id": user.get("id") or user.get("user_id") or user.get("email") or "",
    }
    await _db.order_assets.update_one(
        {"id": asset_id, "order_pk": order_pk},
        {"$push": {"comments": comment}},
    )
    return comment


@router.delete("/epirent/{order_pk}/assets/{asset_id}/comments/{comment_id}")
async def delete_asset_comment(
    order_pk: int, asset_id: str, comment_id: str,
    user: dict = Depends(_auth_user),
):
    """Delete a comment. Only the author or an admin/staff can delete."""
    asset = await _db.order_assets.find_one(
        {"id": asset_id, "order_pk": order_pk}, {"_id": 0, "comments": 1},
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset nicht gefunden")
    comments = asset.get("comments") or []
    target = next((c for c in comments if c.get("id") == comment_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Kommentar nicht gefunden")
    user_id = user.get("id") or user.get("user_id") or user.get("email") or ""
    user_role = (user.get("role") or "").lower()
    is_author = target.get("created_by_id") == user_id or target.get("created_by") == (user.get("name") or user.get("email") or "")
    is_privileged = user_role in ("admin", "staff", "manager")
    if not (is_author or is_privileged):
        raise HTTPException(status_code=403, detail="Nur Autor oder Admin darf Kommentare loeschen")
    await _db.order_assets.update_one(
        {"id": asset_id, "order_pk": order_pk},
        {"$pull": {"comments": {"id": comment_id}}},
    )
    return {"ok": True}


@router.get("/epirent/{order_pk}/billing-pdf")
async def get_billing_pdf(order_pk: int, token: str = Query(None)):
    """Generate billing PDF: Cover + Hours summary + Fuel summary + Attached report PDFs + Attached fuel receipt PDFs."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.utils import ImageReader
    from pypdf import PdfWriter, PdfReader
    import io
    import os
    import base64

    if not token:
        raise HTTPException(status_code=401)
    try:
        payload = _decode_jwt_token(token)
        user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401)
    except Exception:
        raise HTTPException(status_code=401)

    # Fetch order
    config = await _get_epirent_config()
    api_url = config.get("api_url", "").rstrip("/")
    headers = {"X-EPI-NO-SESSION": "True", "X-EPI-ACC-TOK": config.get("api_key", "")}
    ssl_skip = config.get("ssl_skip", False)
    async with httpx.AsyncClient(timeout=15, verify=not ssl_skip) as client:
        resp = await client.get(f"{api_url}/v1/order/{order_pk}", headers=headers)
    raw = resp.json().get("payload", {})
    if isinstance(raw, list) and raw:
        raw = raw[0]
    contact = raw.get("contact") or {}
    order_no = raw.get("order_no", "")
    event_name = raw.get("event", "") or raw.get("name", "")
    contact_name = contact.get("name", "")
    customer_no = raw.get("customer_no", "")

    # Fetch data
    reports = await _db.project_reports.find({"order_pk": str(order_pk)}, {"_id": 0}).sort("created_at", 1).to_list(500)
    fuel_receipts = await _db.fuel_receipts.find({"order_pk": str(order_pk)}, {"_id": 0}).sort("date", 1).to_list(length=None)
    delivery_notes_for_billing = await _db.delivery_notes.find(
        {"order_pk": order_pk}, {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    adj = await _db.fuel_adjustments.find_one({"order_pk": str(order_pk)}, {"_id": 0})
    fuel_pct = adj.get("adjustment_percent", 0) if adj else 0

    # ── Colors & Styles ──
    PURPLE = colors.HexColor("#7c3aed")
    HEADER_BG = colors.HexColor("#ede9fe")
    BORDER = colors.HexColor("#d1d5db")
    DARK = colors.HexColor("#1f2937")

    s_title = ParagraphStyle("T", fontSize=22, fontName="Helvetica-Bold", textColor=PURPLE, spaceAfter=4)
    s_h2 = ParagraphStyle("H2", fontSize=12, fontName="Helvetica-Bold", textColor=PURPLE, spaceBefore=10, spaceAfter=4)
    s_label = ParagraphStyle("L", fontSize=8, textColor=colors.HexColor("#6b7280"))
    s_value = ParagraphStyle("V", fontSize=9, textColor=DARK)
    s_value_bold = ParagraphStyle("VB", fontSize=9, textColor=DARK, fontName="Helvetica-Bold")
    s_cell = ParagraphStyle("C", fontSize=9, textColor=DARK, leading=11)
    s_cell_bold = ParagraphStyle("CB", fontSize=9, textColor=DARK, fontName="Helvetica-Bold", leading=11)
    s_cell_c = ParagraphStyle("CC", fontSize=9, textColor=DARK, alignment=TA_CENTER)
    s_cell_c_bold = ParagraphStyle("CCB", fontSize=9, textColor=DARK, fontName="Helvetica-Bold", alignment=TA_CENTER)
    s_total = ParagraphStyle("TT", fontSize=10, textColor=PURPLE, fontName="Helvetica-Bold", alignment=TA_CENTER)
    s_small = ParagraphStyle("SM", fontSize=7, textColor=colors.grey)

    pw, ph = A4
    W = pw - 36*mm  # 18mm Rand links + rechts (wie Lieferschein)

    # ═══════════════════════════════════════
    # PART 1: Summary pages (platypus)
    # ═══════════════════════════════════════
    summary_buf = io.BytesIO()
    # SimpleDocTemplate mit Brand-Chrome via onFirstPage/onLaterPages.
    # topMargin = 30mm (Header bis 23mm + Puffer); bottomMargin = 30mm (Footer ab 22mm + Puffer)
    doc = SimpleDocTemplate(
        summary_buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=30*mm, bottomMargin=30*mm,
    )
    elems = []

    elems.append(Paragraph("Abrechnungs-Doku", s_title))
    elems.append(Spacer(1, 4*mm))

    # Cover info
    cover = [
        [Paragraph("Auftragsnummer:", s_label), Paragraph(f"<b>{order_no}</b>", s_value_bold)],
        [Paragraph("Kundennummer:", s_label), Paragraph(str(customer_no), s_value)],
        [Paragraph("Kunde:", s_label), Paragraph(f"<b>{contact_name}</b>", s_value_bold)],
        [Paragraph("Projekt:", s_label), Paragraph(f"<b>{event_name}</b>", s_value_bold)],
        [Paragraph("Adresse:", s_label), Paragraph(raw.get("address", ""), s_value)],
        [Paragraph("Zeitraum:", s_label), Paragraph(f"{raw.get('date_start', '')} - {raw.get('date_end', '')}", s_value)],
        [Paragraph("Projektberichte:", s_label), Paragraph(f"<b>{len(reports)}</b>", s_value_bold)],
        [Paragraph("Tankbelege:", s_label), Paragraph(f"<b>{len(fuel_receipts)}</b>", s_value_bold)],
        [Paragraph("Lieferscheine:", s_label), Paragraph(f"<b>{len(delivery_notes_for_billing)}</b>", s_value_bold)],
    ]
    ct = Table(cover, colWidths=[35*mm, W - 35*mm])
    ct.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (1, 0), (1, -1), 0.5, BORDER),
    ]))
    elems.append(ct)
    elems.append(Spacer(1, 10*mm))

    # ── STUNDEN-ZUSAMMENFASSUNG (simplified) ──
    elems.append(Paragraph("Stunden-Zusammenfassung", s_h2))

    # Aggregate: date -> {N: sum, E: sum, NO: sum}
    date_totals = {}
    for r in reports:
        for entry in r.get("work_log", []):
            datum = entry.get("datum", "")
            if not datum:
                continue
            if datum not in date_totals:
                date_totals[datum] = {"N": 0, "E": 0, "NO": 0}
            for emp_hrs in entry.get("stunden", {}).values():
                if not isinstance(emp_hrs, dict):
                    continue
                for t in ["N", "E", "NO"]:
                    v = emp_hrs.get(t, 0)
                    if v and str(v) != "0":
                        try:
                            date_totals[datum][t] += float(v)
                        except (ValueError, TypeError):
                            pass

    if date_totals:
        h_hdr = [
            Paragraph("<b>Datum</b>", s_cell_bold),
            Paragraph("<b>Normalstunden</b>", s_cell_bold),
            Paragraph("<b>Extrastunden</b>", s_cell_bold),
            Paragraph("<b>Notdienststunden</b>", s_cell_bold),
        ]
        h_rows = [h_hdr]
        sum_n = sum_e = sum_no = 0
        for datum in sorted(date_totals.keys()):
            vals = date_totals[datum]
            sum_n += vals["N"]
            sum_e += vals["E"]
            sum_no += vals["NO"]
            h_rows.append([
                Paragraph(datum, s_cell),
                Paragraph(str(vals["N"]) if vals["N"] else "", s_cell_c),
                Paragraph(str(vals["E"]) if vals["E"] else "", s_cell_c),
                Paragraph(str(vals["NO"]) if vals["NO"] else "", s_cell_c),
            ])
        # GESAMT
        h_rows.append([
            Paragraph("<b>GESAMT</b>", s_cell_bold),
            Paragraph(f"<b>{sum_n}</b>", s_total),
            Paragraph(f"<b>{sum_e}</b>", s_total),
            Paragraph(f"<b>{sum_no}</b>", s_total),
        ])
        ht = Table(h_rows, colWidths=[30*mm, (W - 30*mm) / 3, (W - 30*mm) / 3, (W - 30*mm) / 3])
        ht.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f5f3ff")),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ]))
        elems.append(ht)
    else:
        elems.append(Paragraph("Keine Stunden erfasst.", s_small))

    elems.append(Spacer(1, 8*mm))

    # ── TANKBELEGE-ZUSAMMENFASSUNG ──
    if fuel_receipts:
        elems.append(Paragraph("Tankbelege-Zusammenfassung", s_h2))
        fr_hdr = [
            Paragraph("<b>Datum</b>", s_cell_bold),
            Paragraph("<b>Beleg-Nr.</b>", s_cell_bold),
            Paragraph("<b>Kraftstoff</b>", s_cell_bold),
            Paragraph("<b>Liter</b>", s_cell_bold),
            Paragraph("<b>Preis/L</b>", s_cell_bold),
            Paragraph("<b>Gesamt</b>", s_cell_bold),
        ]
        fr_rows = [fr_hdr]
        total_liters = 0
        total_cost = 0
        for fr in fuel_receipts:
            liters_raw = fr.get("quantity_liters", 0) or 0
            if fuel_pct:
                liters_raw = liters_raw * (1 + fuel_pct / 100)
            # Geschaeftsregel: Tankwagen kennt nur ganze Liter -> immer
            # auf naechste ganze Zahl AUFRUNDEN (nicht kaufmaennisch runden).
            # Einzelne Tankbelege behalten ihre Originalmenge - nur in der
            # Abrechnungs-Gesamtansicht wird aufgerundet.
            liters = int(math.ceil(liters_raw))
            price = fr.get("price_per_liter", 0) or 0
            cost = liters * price
            total_liters += liters
            total_cost += cost
            fr_rows.append([
                Paragraph(fr.get("date", ""), s_cell),
                Paragraph(fr.get("beleg_nr", ""), s_cell),
                Paragraph(fr.get("fuel_type_label", fr.get("fuel_type", "")), s_cell),
                Paragraph(f"{liters}", s_cell_c),
                Paragraph(f"{price:.3f}" if price else "", s_cell_c),
                Paragraph(f"{cost:.2f}" if price else "", s_cell_c),
            ])
        fr_rows.append([
            Paragraph("<b>GESAMT</b>", s_cell_bold), "", "",
            Paragraph(f"<b>{total_liters} L</b>", s_total),
            "",
            Paragraph(f"<b>{total_cost:.2f} EUR</b>", s_total),
        ])
        ft = Table(fr_rows, colWidths=[22*mm, 22*mm, 35*mm, 22*mm, 22*mm, W - 123*mm])
        ft.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f5f3ff")),
            ("ALIGN", (3, 1), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ]))
        elems.append(ft)

    doc.build(elems, onFirstPage=_draw_ee_brand_chrome, onLaterPages=_draw_ee_brand_chrome)
    summary_buf.seek(0)

    # ═══════════════════════════════════════
    # PART 2: Individual project report PDFs
    # ═══════════════════════════════════════
    from routes.project_reports import _generate_report_pdf
    report_pdfs = []
    for r in reports:
        rid = r.get("id")
        if not rid:
            continue
        try:
            rpdf_buf = _generate_report_pdf(r)
            report_pdfs.append(rpdf_buf)
        except Exception:
            pass

    # ═══════════════════════════════════════
    # PART 3: Individual fuel receipt PDFs
    # ═══════════════════════════════════════
    from routes.fuel_receipts import _draw_receipt_page, LOGO_URL
    logo_img = None
    try:
        async with httpx.AsyncClient() as hc:
            logo_resp = await hc.get(LOGO_URL, timeout=10)
            if logo_resp.status_code == 200:
                logo_img = ImageReader(io.BytesIO(logo_resp.content))
    except Exception:
        pass

    fuel_pdf_buf = io.BytesIO()
    if fuel_receipts:
        c = rl_canvas.Canvas(fuel_pdf_buf, pagesize=A4)
        for fr_doc in fuel_receipts:
            qty = fr_doc.get("quantity_liters", 0)
            if fuel_pct:
                qty = qty * (1 + fuel_pct / 100)
            # Aufrunden vor Anzeige - konsistent mit Zusammenstellung-Tabelle.
            qty = int(math.ceil(qty or 0))
            _draw_receipt_page(c, fr_doc, qty, logo_img)
            c.showPage()
        c.save()
    fuel_pdf_buf.seek(0)

    # ═══════════════════════════════════════
    # MERGE all PDFs
    # ═══════════════════════════════════════
    writer = PdfWriter()
    # Add summary pages
    summary_reader = PdfReader(summary_buf)
    for page in summary_reader.pages:
        writer.add_page(page)
    # Add individual report PDFs
    for rpdf in report_pdfs:
        rpdf.seek(0)
        reader = PdfReader(rpdf)
        for page in reader.pages:
            writer.add_page(page)
    # Add fuel receipt pages
    if fuel_receipts:
        fuel_pdf_buf.seek(0)
        fuel_reader = PdfReader(fuel_pdf_buf)
        for page in fuel_reader.pages:
            writer.add_page(page)
    # Add delivery note pages (aus delivery_notes Collection -> pdf_b64)
    for ln in delivery_notes_for_billing:
        pdf_b64 = ln.get("pdf_b64")
        if not pdf_b64:
            continue
        try:
            ln_bytes = base64.b64decode(pdf_b64)
            ln_reader = PdfReader(io.BytesIO(ln_bytes))
            for page in ln_reader.pages:
                writer.add_page(page)
        except Exception as e:
            logger.warning(f"Lieferschein {ln.get('delivery_note_no')} konnte nicht angehaengt werden: {e}")

    final_buf = io.BytesIO()
    writer.write(final_buf)
    final_buf.seek(0)

    filename = f"Abrechnung_{order_no}_{event_name}.pdf".replace(" ", "_")
    from fastapi.responses import StreamingResponse
    return StreamingResponse(final_buf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ============== Order Documents (Dokumentenablage) ==============

import os as _os
import uuid as _uuid
import re as _re
from fastapi import UploadFile, File, Request, Form
from fastapi.responses import Response

_ALLOWED_DOC_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_VALID_KATEGORIEN = ["messprotokolle", "plaene", "fotos", "sonstiges"]
_ORDER_DOC_STORAGE = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "storage", "order_documents")
_os.makedirs(_ORDER_DOC_STORAGE, exist_ok=True)


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


async def _auth_user_from_token(token: str = None, request: Request = None):
    user = None
    if token:
        try:
            payload = _decode_jwt_token(token)
            user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        except Exception:
            pass
    if not user and request:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            try:
                payload = _decode_jwt_token(auth[7:])
                user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
            except Exception:
                pass
    return user


@router.post("/order-documents/{order_pk}")
async def upload_order_document(order_pk: str, file: UploadFile = File(...), kategorie: str = Form(None), credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401)

    ct = file.content_type or ""
    if ct not in _ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Nur PDF und Bilder (JPG, PNG, WebP, GIF) erlaubt")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Datei zu gross (max. 20 MB)")

    # Auto-detect or use provided kategorie
    detected = _detect_kategorie(file.filename or "", ct)
    final_kat = kategorie if kategorie and kategorie in _VALID_KATEGORIEN else detected

    doc_id = str(_uuid.uuid4())
    ext = _ALLOWED_DOC_TYPES[ct]
    stored_name = f"{doc_id}{ext}"
    order_dir = _os.path.join(_ORDER_DOC_STORAGE, order_pk)
    _os.makedirs(order_dir, exist_ok=True)

    file_path = _os.path.join(order_dir, stored_name)
    with open(file_path, "wb") as f:
        f.write(content)

    doc = {
        "id": doc_id,
        "order_pk": order_pk,
        "filename": stored_name,
        "original_name": file.filename or "Dokument",
        "content_type": ct,
        "size": len(content),
        "kategorie": final_kat,
        "uploaded_by": user.get("name", user.get("email", "")),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.order_documents.insert_one(doc)

    return {"id": doc_id, "original_name": doc["original_name"], "kategorie": final_kat, "detected": detected, "message": "Dokument hochgeladen"}


@router.get("/order-documents/{order_pk}")
async def list_order_documents(order_pk: str, credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401)
    docs = await _db.order_documents.find(
        {"order_pk": order_pk}, {"_id": 0}
    ).sort("uploaded_at", -1).to_list(200)
    return docs


@router.put("/order-documents/{order_pk}/{doc_id}")
async def update_order_document(order_pk: str, doc_id: str, body: dict, credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401)

    doc = await _db.order_documents.find_one({"id": doc_id, "order_pk": order_pk}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    update = {}
    if "kategorie" in body and body["kategorie"] in _VALID_KATEGORIEN:
        update["kategorie"] = body["kategorie"]
    if not update:
        raise HTTPException(status_code=400, detail="Keine gueltige Aenderung")

    await _db.order_documents.update_one({"id": doc_id}, {"$set": update})
    return {"message": "Dokument aktualisiert"}


@router.get("/order-documents/{order_pk}/{doc_id}/file")
async def get_order_document_file(order_pk: str, doc_id: str, token: str = None, thumbnail: int = 0, size: int = 200, request: Request = None):
    user = await _auth_user_from_token(token, request)
    if not user:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")

    doc = await _db.order_documents.find_one({"id": doc_id, "order_pk": order_pk}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    file_path = _os.path.join(_ORDER_DOC_STORAGE, order_pk, doc["filename"])
    if not _os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    # Thumbnail for list views (images only)
    if thumbnail and doc.get("content_type", "").startswith("image/"):
        from utils.thumbnails import make_thumbnail
        tdata = make_thumbnail(file_path, size=min(max(int(size), 16), 1024))
        if tdata is not None:
            return Response(
                content=tdata,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=31536000", "Content-Disposition": 'inline; filename="thumb.jpg"'},
            )

    with open(file_path, "rb") as f:
        data = f.read()

    return Response(
        content=data,
        media_type=doc["content_type"],
        headers={"Content-Disposition": f'inline; filename="{doc["original_name"]}"'},
    )


@router.delete("/order-documents/{order_pk}/{doc_id}")
async def delete_order_document(order_pk: str, doc_id: str, credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins duerfen Dokumente loeschen")

    doc = await _db.order_documents.find_one({"id": doc_id, "order_pk": order_pk}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    file_path = _os.path.join(_ORDER_DOC_STORAGE, order_pk, doc["filename"])
    if _os.path.exists(file_path):
        _os.remove(file_path)

    await _db.order_documents.delete_one({"id": doc_id})
    return {"message": "Dokument geloescht"}


@router.get("/order-documents/{order_pk}/zip")
async def download_order_documents_zip(order_pk: str, token: str = None, request: Request = None):
    """Download all order documents as ZIP with folder structure."""
    user = await _auth_user_from_token(token, request)
    if not user:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")

    docs = await _db.order_documents.find({"order_pk": order_pk}, {"_id": 0}).to_list(500)
    if not docs:
        raise HTTPException(status_code=404, detail="Keine Dokumente vorhanden")

    import zipfile, io
    buf = io.BytesIO()
    kat_labels = {"messprotokolle": "Messprotokolle", "plaene": "Plaene", "fotos": "Fotos", "sonstiges": "Sonstiges"}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            kat = kat_labels.get(doc.get("kategorie", "sonstiges"), "Sonstiges")
            file_path = _os.path.join(_ORDER_DOC_STORAGE, order_pk, doc["filename"])
            if _os.path.exists(file_path):
                arcname = f"{kat}/{doc['original_name']}"
                zf.write(file_path, arcname)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="Dokumente_Auftrag_{order_pk}.zip"'},
    )



def _parse_crew_item(item):
    """Parse a single type-3 crew item into our format."""
    ts = item.get("time_start", 0)
    te = item.get("time_end", 0)
    return {
        "pk": item.get("primary_key"),
        "title": item.get("title", ""),
        "count": item.get("amount_total", 1),
        "date_start": item.get("date_start", ""),
        "date_end": item.get("date_end", ""),
        "time_start": f"{ts // 3600:02d}:{(ts % 3600) // 60:02d}" if ts else "",
        "time_end": f"{te // 3600:02d}:{(te % 3600) // 60:02d}" if te else "",
        "hours": item.get("calc_hours", item.get("calc_days", 0)),
        "service_pk": item.get("service_pk"),
    }


def _parse_crew_items(payload):
    """Extract type-3 crew items from an EpiRent order payload (top-level only)."""
    crew = []
    for item in payload.get("order_items", []):
        if item.get("type") == 3:
            crew.append(_parse_crew_item(item))
    return crew


def _find_personal_chapter_refs(payload):
    """Find _ref_chapter_items URLs for 'Personal' chapters in order items."""
    refs = []
    for item in payload.get("order_items", []):
        title = (item.get("title") or "").lower()
        if "personal" in title:
            ref = item.get("_ref_chapter_items", "")
            if ref and "chid=" in ref:
                refs.append(ref)
    return refs


async def _fetch_crew_deep(payload, api_url, headers, ssl_skip):
    """Fetch crew items: first check top-level, then look inside Personal chapters."""
    # 1. Check for type-3 items directly in order_items
    crew = _parse_crew_items(payload)
    if crew:
        return crew

    # 2. Look for 'Personal' chapter sub-items
    refs = _find_personal_chapter_refs(payload)
    if not refs:
        return []

    crew = []
    async with httpx.AsyncClient(timeout=20, verify=not ssl_skip) as client:
        for ref in refs:
            try:
                resp = await client.get(f"{api_url}/v1/{ref}", headers=headers)
                data = resp.json()
                sub_items = data.get("payload", [])
                for item in sub_items:
                    if item.get("type") == 3:
                        parsed = _parse_crew_item(item)
                        if parsed.get("date_start") and parsed["date_start"] != "0000-00-00":
                            crew.append(parsed)
            except Exception as e:
                logger.warning(f"Chapter sub-item fetch failed for {ref}: {e}")
    return crew


@router.get("/epirent/{order_pk}/crew")
async def get_order_crew(order_pk: int, user: dict = Depends(_auth_user)):
    """Get personnel/crew requirements from EpiRent order (Crewbrain data)."""
    # Check cache first (valid for 30 min)
    cached = await _db.crew_cache.find_one({"order_pk": order_pk}, {"_id": 0})
    if cached:
        cached_at = cached.get("cached_at", "")
        if cached_at:
            try:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached_at)).total_seconds()
                if age < 1800:
                    return {"crew": cached.get("crew", []), "event": cached.get("event", ""), "is_staff_planning": cached.get("is_staff_planning", False)}
            except Exception:
                pass

    config = await _get_epirent_config()
    api_url = config.get("api_url", "").rstrip("/")
    api_key = config.get("api_key", "")
    ssl_skip = config.get("ssl_skip", False)
    headers = {"X-EPI-NO-SESSION": "True", "X-EPI-ACC-TOK": api_key}

    try:
        async with httpx.AsyncClient(timeout=20, verify=not ssl_skip) as client:
            resp = await client.get(f"{api_url}/v1/order/{order_pk}", headers=headers)
            data = resp.json()
            if not data.get("success"):
                return {"crew": [], "event": ""}
            payload = data["payload"][0] if isinstance(data["payload"], list) else data["payload"]
            crew = await _fetch_crew_deep(payload, api_url, headers, ssl_skip)
            result = {
                "crew": crew,
                "event": payload.get("event", ""),
                "is_staff_planning": payload.get("is_staff_planning", False),
            }
            # Cache result
            await _db.crew_cache.update_one(
                {"order_pk": order_pk},
                {"$set": {"order_pk": order_pk, "cached_at": datetime.now(timezone.utc).isoformat(), **result}},
                upsert=True,
            )
            return result
    except Exception as e:
        logger.warning(f"Crew fetch failed for {order_pk}: {e}")
        if cached:
            return {"crew": cached.get("crew", []), "event": cached.get("event", ""), "is_staff_planning": cached.get("is_staff_planning", False)}
        return {"crew": [], "event": ""}


@router.post("/epirent/crew/batch")
async def get_crew_batch(data: dict, user: dict = Depends(_auth_user)):
    """Batch fetch crew data for multiple orders with concurrency limiting and caching."""
    order_pks = data.get("order_pks", [])
    if not order_pks or len(order_pks) > 50:
        return {"results": {}}

    now = datetime.now(timezone.utc)
    results = {}

    # Check cache for all orders first
    uncached_pks = []
    for pk in order_pks:
        cached = await _db.crew_cache.find_one({"order_pk": int(pk)}, {"_id": 0})
        if cached and cached.get("cached_at"):
            try:
                age = (now - datetime.fromisoformat(cached["cached_at"])).total_seconds()
                if age < 1800:
                    crew = cached.get("crew", [])
                    if crew:
                        results[str(pk)] = crew
                    continue
            except Exception:
                pass
        uncached_pks.append(int(pk))

    # Fetch uncached with concurrency limit of 3
    if uncached_pks:
        try:
            config = await _get_epirent_config()
            api_url = config.get("api_url", "").rstrip("/")
            api_key = config.get("api_key", "")
            ssl_skip = config.get("ssl_skip", False)
            headers_epi = {"X-EPI-NO-SESSION": "True", "X-EPI-ACC-TOK": api_key}
            sem = asyncio.Semaphore(3)

            async def _fetch_one(pk):
                async with sem:
                    try:
                        async with httpx.AsyncClient(timeout=20, verify=not ssl_skip) as client:
                            resp = await client.get(f"{api_url}/v1/order/{pk}", headers=headers_epi)
                            d = resp.json()
                            if not d.get("success"):
                                return pk, []
                            p = d["payload"][0] if isinstance(d["payload"], list) else d["payload"]
                            crew = await _fetch_crew_deep(p, api_url, headers_epi, ssl_skip)
                            # Cache
                            await _db.crew_cache.update_one(
                                {"order_pk": pk},
                                {"$set": {
                                    "order_pk": pk,
                                    "cached_at": now.isoformat(),
                                    "crew": crew,
                                    "event": p.get("event", ""),
                                    "is_staff_planning": p.get("is_staff_planning", False),
                                }},
                                upsert=True,
                            )
                            return pk, crew
                    except Exception as e:
                        logger.warning(f"Batch crew fetch failed for {pk}: {e}")
                        return pk, []

            fetch_results = await asyncio.gather(*[_fetch_one(pk) for pk in uncached_pks])
            for pk, crew in fetch_results:
                if crew:
                    results[str(pk)] = crew
        except Exception as e:
            logger.error(f"Batch crew error: {e}")

    return {"results": results}



# ══════════════════════════════════════════════════════════════════════════
# Messprotokoll (elektrische Anlage nach DIN VDE 0100-600 / DGUV V3)
# ══════════════════════════════════════════════════════════════════════════
from fastapi import Body as _Body  # noqa: E402


@router.post("/messprotokoll/{order_pk}")
async def create_messprotokoll(order_pk: str, data: dict = _Body(...),
                                credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Generate Messprotokoll PDF, store in order_documents (kategorie=messprotokolle)
    and persist structured data in messprotokolle collection."""
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert")

    # Prüfer = aktuell angemeldeter User
    data["pruefer_id"] = user.get("id", "")
    data["pruefer_name"] = user.get("name", user.get("email", ""))

    # Fortlaufende Protokoll-Nr. je Auftrag:
    #   ohne Verteiler:  {Auftragsnummer}-MP-{NNNN}
    #   mit Verteiler:   {Auftragsnummer}-V{verteiler_nr}-MP-{NNNN}
    if not data.get("protokoll_nr"):
        order_doc = None
        if order_pk.isdigit():
            order_doc = await _db.orders_cache.find_one({"primary_key": int(order_pk)}, {"_id": 0, "order_no": 1})
        if not order_doc:
            order_doc = await _db.orders_cache.find_one({"primary_key": order_pk}, {"_id": 0, "order_no": 1})
        order_no = (order_doc or {}).get("order_no") or data.get("auftrags_nr") or order_pk
        existing_count = await _db.messprotokolle.count_documents({"order_pk": order_pk})
        verteiler_raw = (data.get("verteiler_nr") or "").strip()
        # Sicher für Dateinamen: nur alphanumerisch, -, _ behalten
        verteiler_safe = "".join(ch for ch in verteiler_raw if ch.isalnum() or ch in ("-", "_"))
        if verteiler_safe:
            data["protokoll_nr"] = f"{order_no}-V{verteiler_safe}-MP-{existing_count + 1:04d}"
        else:
            data["protokoll_nr"] = f"{order_no}-MP-{existing_count + 1:04d}"

    if not data.get("pruef_datum"):
        data["pruef_datum"] = datetime.now(timezone.utc).strftime("%d.%m.%Y")

    # PDF generieren
    try:
        from services.messprotokoll_pdf import generate_messprotokoll_pdf
        pdf_bytes = generate_messprotokoll_pdf(data)
    except Exception as e:
        logger.error(f"Messprotokoll PDF-Fehler: {e}")
        raise HTTPException(status_code=500, detail=f"PDF-Erzeugung fehlgeschlagen: {e}")

    # PDF als order_document speichern
    doc_id = str(_uuid.uuid4())
    stored_name = f"{doc_id}.pdf"
    order_dir = _os.path.join(_ORDER_DOC_STORAGE, order_pk)
    _os.makedirs(order_dir, exist_ok=True)
    file_path = _os.path.join(order_dir, stored_name)
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    original_name = f"Messprotokoll_{data['protokoll_nr']}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
    doc = {
        "id": doc_id,
        "order_pk": order_pk,
        "filename": stored_name,
        "original_name": original_name,
        "content_type": "application/pdf",
        "size": len(pdf_bytes),
        "kategorie": "messprotokolle",
        "uploaded_by": user.get("name", user.get("email", "")),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "messprotokoll_id": doc_id,
    }
    await _db.order_documents.insert_one(doc)

    # Messprotokoll-Datensatz separat speichern (fuer spaeteres Bearbeiten/Erneut-PDF)
    mp_record = {
        "id": doc_id,
        "order_pk": order_pk,
        "protokoll_nr": data["protokoll_nr"],
        "pruefer_id": data["pruefer_id"],
        "pruefer_name": data["pruefer_name"],
        "pruef_datum": data["pruef_datum"],
        "data": data,
        "document_id": doc_id,
        "created_by": user.get("name", user.get("email", "")),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.messprotokolle.insert_one(mp_record)

    return {
        "id": doc_id,
        "protokoll_nr": data["protokoll_nr"],
        "original_name": original_name,
        "message": "Messprotokoll angelegt",
    }


@router.get("/messprotokoll/{order_pk}")
async def list_messprotokolle(order_pk: str,
                                credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Liste aller Messprotokolle dieses Auftrags (nur Metadaten)."""
    _decode_jwt_token(credentials.credentials)
    rows = await _db.messprotokolle.find(
        {"order_pk": order_pk},
        {"_id": 0, "id": 1, "protokoll_nr": 1, "pruefer_name": 1, "pruef_datum": 1,
         "created_at": 1, "created_by": 1, "document_id": 1,
         "data.verteiler_asset_id": 1, "data.verteiler_nr": 1}
    ).sort("created_at", -1).to_list(200)
    return rows


@router.get("/messprotokoll/{order_pk}/{doc_id}")
async def get_messprotokoll(order_pk: str, doc_id: str,
                              credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Liefert ein einzelnes Messprotokoll inkl. vollstaendiger Formular-Daten
    (zum Vorbefuellen im Edit-Dialog). Admin-only."""
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins duerfen Messprotokolle bearbeiten")
    mp = await _db.messprotokolle.find_one({"id": doc_id, "order_pk": order_pk}, {"_id": 0})
    if not mp:
        raise HTTPException(status_code=404, detail="Messprotokoll nicht gefunden")
    return mp


@router.put("/messprotokoll/{order_pk}/{doc_id}")
async def update_messprotokoll(order_pk: str, doc_id: str, data: dict = _Body(...),
                                 credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Aktualisiert ein bestehendes Messprotokoll: regeneriert das PDF mit neuen
    Daten, ueberschreibt die gespeicherte PDF-Datei und aktualisiert den DB-
    Datensatz. Protokoll-Nr. und ID bleiben gleich. Admin-only."""
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins duerfen Messprotokolle bearbeiten")

    mp = await _db.messprotokolle.find_one({"id": doc_id, "order_pk": order_pk}, {"_id": 0})
    if not mp:
        raise HTTPException(status_code=404, detail="Messprotokoll nicht gefunden")

    # Protokoll-Nr., Pruefer und Datum aus dem bestehenden Datensatz uebernehmen
    # (Admin darf alles ANDERE anpassen, aber die forensische Kette - wer wann
    # geprueft hat - bleibt unveraendert; siehe Audit-Log).
    data["protokoll_nr"] = mp.get("protokoll_nr") or data.get("protokoll_nr")
    data["pruefer_id"] = mp.get("pruefer_id") or data.get("pruefer_id")
    data["pruefer_name"] = mp.get("pruefer_name") or data.get("pruefer_name")
    if not data.get("pruef_datum"):
        data["pruef_datum"] = mp.get("pruef_datum") or datetime.now(timezone.utc).strftime("%d.%m.%Y")

    # PDF neu generieren
    try:
        from services.messprotokoll_pdf import generate_messprotokoll_pdf
        pdf_bytes = generate_messprotokoll_pdf(data)
    except Exception as e:
        logger.error(f"Messprotokoll PDF-Fehler bei Update: {e}")
        raise HTTPException(status_code=500, detail=f"PDF-Erzeugung fehlgeschlagen: {e}")

    # Gespeicherte PDF-Datei UEBERSCHREIBEN (selber Dateiname, selber Pfad)
    document_id = mp.get("document_id") or doc_id
    od = await _db.order_documents.find_one({"id": document_id, "order_pk": order_pk}, {"_id": 0})
    if not od:
        raise HTTPException(status_code=404, detail="Zugehoeriges Dokument nicht gefunden")
    file_path = _os.path.join(_ORDER_DOC_STORAGE, order_pk, od.get("filename", f"{doc_id}.pdf"))
    _os.makedirs(_os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    # order_documents-Eintrag: Groesse aktualisieren, uploaded_at NICHT
    # ueberschreiben (sonst rutscht das Dokument in der Liste nach vorn,
    # obwohl es derselbe MP ist). Stattdessen separates updated_at-Feld.
    now_iso = datetime.now(timezone.utc).isoformat()
    await _db.order_documents.update_one(
        {"id": document_id, "order_pk": order_pk},
        {"$set": {
            "size": len(pdf_bytes),
            "updated_by": user.get("name", user.get("email", "")),
            "updated_at": now_iso,
        }}
    )

    # messprotokolle: data komplett ersetzen, Audit-Felder ergaenzen
    await _db.messprotokolle.update_one(
        {"id": doc_id, "order_pk": order_pk},
        {"$set": {
            "data": data,
            "pruef_datum": data["pruef_datum"],
            "updated_by": user.get("name", user.get("email", "")),
            "updated_at": now_iso,
        }}
    )

    logger.info(f"Messprotokoll {mp.get('protokoll_nr')} aktualisiert durch {user.get('name')}")
    return {
        "id": doc_id,
        "protokoll_nr": data["protokoll_nr"],
        "message": "Messprotokoll aktualisiert",
    }


@router.delete("/messprotokoll/{order_pk}/{doc_id}")
async def delete_messprotokoll(order_pk: str, doc_id: str,
                                credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Loescht ein Messprotokoll (DB-Eintrag, order_document und PDF-Datei). Nur Admin."""
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins duerfen Messprotokolle loeschen")

    mp = await _db.messprotokolle.find_one({"id": doc_id, "order_pk": order_pk}, {"_id": 0})
    if not mp:
        raise HTTPException(status_code=404, detail="Messprotokoll nicht gefunden")

    document_id = mp.get("document_id") or doc_id
    od = await _db.order_documents.find_one({"id": document_id, "order_pk": order_pk}, {"_id": 0})
    if od:
        file_path = _os.path.join(_ORDER_DOC_STORAGE, order_pk, od.get("filename", ""))
        if od.get("filename") and _os.path.exists(file_path):
            try:
                _os.remove(file_path)
            except Exception as e:
                logger.warning(f"Messprotokoll-PDF konnte nicht geloescht werden: {e}")
        await _db.order_documents.delete_one({"id": document_id})

    await _db.messprotokolle.delete_one({"id": doc_id, "order_pk": order_pk})
    return {"message": "Messprotokoll geloescht"}



# ══════════════════════════════════════════════════════════════════════════
# Freelancer Auftragszuweisung (Admin only)
# ══════════════════════════════════════════════════════════════════════════

async def _require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    u = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not u or u.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    return u


@router.get("/freelancer-assignments/{user_id}")
async def get_freelancer_assignments(user_id: str, _admin: dict = Depends(_require_admin)):
    """Aktuelle Auftrags-Zuweisungen eines Freelancers mit Auftrags-Details."""
    u = await _db.users.find_one({"id": user_id}, {"_id": 0, "id": 1, "role": 1, "freelancer_orders": 1})
    if not u:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    pks = _freelancer_assigned_pks(u)
    # Lade Auftrags-Details
    orders = []
    if pks:
        int_pks = [int(p) for p in pks if str(p).isdigit()]
        rows = await _db.orders_cache.find(
            {"primary_key": {"$in": int_pks}}, {"_id": 0, "_synced_at": 0}
        ).to_list(500)
        orders = [{
            "primary_key": str(o.get("primary_key")),
            "order_no": o.get("order_no") or "",
            "event": o.get("event") or "",
            "contact_name": o.get("contact_name") or "",
            "event_start": o.get("event_start") or o.get("dispo_start") or "",
            "event_end": o.get("event_end") or o.get("dispo_end") or "",
            "address": o.get("address") or "",
        } for o in rows]
    return {"user_id": user_id, "order_pks": pks, "orders": orders}


class _FreelancerAssignmentUpdate(BaseModel):
    order_pks: list[str]


@router.put("/freelancer-assignments/{user_id}")
async def set_freelancer_assignments(user_id: str, data: _FreelancerAssignmentUpdate,
                                       _admin: dict = Depends(_require_admin)):
    """Setze die komplette Liste zugewiesener Aufträge fuer einen Freelancer."""
    u = await _db.users.find_one({"id": user_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    pks = [str(x) for x in (data.order_pks or [])]
    await _db.users.update_one({"id": user_id}, {"$set": {"freelancer_orders": pks}})
    return {"user_id": user_id, "order_pks": pks, "count": len(pks)}


@router.get("/freelancer-search")
async def search_assignable_orders(q: str = "", limit: int = Query(50, ge=1, le=200),
                                     _admin: dict = Depends(_require_admin)):
    """Suche im orders_cache fuer die Freelancer-Zuweisungs-Maske.
    Liefert NUR bestaetigte Auftraege (is_confirmed == True), analog zur
    Auftragsverwaltung-Default-Ansicht."""
    rows = await _db.orders_cache.find({}, {"_id": 0, "_synced_at": 0}).to_list(1000)
    # Filter: nur bestaetigte, nicht storniert/archiviert
    rows = [o for o in rows
            if o.get("is_confirmed") is True
            and not o.get("is_canceled")
            and not o.get("is_archived")]
    if q:
        s = q.lower()
        rows = [o for o in rows if
                s in (o.get("event") or "").lower() or
                s in (o.get("order_no") or "").lower() or
                s in (o.get("contact_name") or "").lower() or
                s in str(o.get("customer_no") or "").lower() or
                s in (o.get("address") or "").lower()]
    # Sortiere nach event_start desc
    rows.sort(key=lambda o: (o.get("event_start") or o.get("dispo_start") or ""), reverse=True)
    rows = rows[:limit]
    # Reduzierte Felder
    return [{
        "primary_key": str(o.get("primary_key")),
        "order_no": o.get("order_no") or "",
        "event": o.get("event") or "",
        "contact_name": o.get("contact_name") or "",
        "event_start": o.get("event_start") or o.get("dispo_start") or "",
        "event_end": o.get("event_end") or o.get("dispo_end") or "",
        "address": o.get("address") or "",
    } for o in rows]


# ============================================================================
# Verschoben-Audit: zeigt alle Asset-Verschiebungen (Move-Operationen)
# ============================================================================

_MOVE_RE = re.compile(r"Verschoben aus Auftrag #(\d+) nach #(\d+)", re.IGNORECASE)


@router.get("/asset-orphan-messprotokolle")
async def asset_orphan_messprotokolle(_admin: dict = Depends(_require_admin)):
    """Listet Messprotokolle, deren referenzierter Verteiler-Asset nicht mehr
    existiert (Geister-Protokolle). Hilft beim Aufraeumen nach versehentlichem
    Loeschen eines Verteilers (passierte vor der Loesch-Schutz-Aenderung)."""
    mps = await _db.messprotokolle.find(
        {"data.verteiler_asset_id": {"$nin": [None, ""]}},
        {"_id": 0, "id": 1, "protokoll_nr": 1, "order_pk": 1, "pruef_datum": 1,
         "created_at": 1, "created_by": 1, "data.verteiler_asset_id": 1, "data.verteiler_nr": 1},
    ).to_list(2000)
    vid_set = set(mps and [m.get("data", {}).get("verteiler_asset_id") for m in mps] or [])
    vid_set.discard(None)
    vid_set.discard("")
    existing = set()
    if vid_set:
        async for a in _db.order_assets.find({"id": {"$in": list(vid_set)}}, {"_id": 0, "id": 1}):
            existing.add(a.get("id"))
    orphans = []
    for m in mps:
        vid = (m.get("data") or {}).get("verteiler_asset_id")
        if vid and vid not in existing:
            orphans.append({
                "id": m.get("id"),
                "protokoll_nr": m.get("protokoll_nr"),
                "order_pk": m.get("order_pk"),
                "pruef_datum": m.get("pruef_datum"),
                "created_at": m.get("created_at"),
                "created_by": m.get("created_by"),
                "verteiler_asset_id": vid,
                "verteiler_nr": (m.get("data") or {}).get("verteiler_nr"),
            })
    orphans.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"orphans": orphans, "count": len(orphans)}


@router.get("/asset-move-audit")
async def asset_move_audit(
    order_pk: int | None = Query(None, description="Optional: nur Moves aus diesem Quell-Auftrag"),
    q: str = Query("", description="Optional: Filter auf Label/Asset-Typ/User"),
    limit: int = Query(500, ge=1, le=2000),
    _admin: dict = Depends(_require_admin),
):
    """Audit-Trail aller Asset-Verschiebungen.

    Liest alle Assets, deren Kommentar-Audit-Log Eintraege vom Typ
    'Verschoben aus Auftrag #X nach #Y' enthaelt, und gibt sie als flache
    Liste zurueck. Ein Asset, das mehrfach verschoben wurde, erscheint
    mehrfach (ein Eintrag pro Move-Vorgang). Aktueller Standort
    (order_pk + order_no) wird mitgeliefert, damit Admins verlorene Artikel
    direkt wiederfinden koennen.
    """
    # Build pipeline: filter assets that have at least one move-comment
    match_filter = {"comments.text": {"$regex": "Verschoben aus Auftrag"}}
    assets = await _db.order_assets.find(match_filter, {"_id": 0}).to_list(limit)

    # Sammle order_pks zur Anreicherung
    referenced_pks = set()
    raw_entries: list[dict] = []
    for a in assets:
        for c in (a.get("comments") or []):
            txt = (c.get("text") or "").strip()
            m = _MOVE_RE.search(txt)
            if not m:
                continue
            from_pk = int(m.group(1))
            to_pk = int(m.group(2))
            referenced_pks.add(from_pk)
            referenced_pks.add(to_pk)
            referenced_pks.add(a.get("order_pk"))
            raw_entries.append({
                "asset_id": a.get("id"),
                "label": a.get("label"),
                "asset_type": a.get("asset_type"),
                "from_pk": from_pk,
                "to_pk": to_pk,
                "current_pk": a.get("order_pk"),
                "moved_by": c.get("created_by") or "?",
                "moved_at": c.get("created_at") or "",
                "latitude": a.get("latitude"),
                "longitude": a.get("longitude"),
                "plus_code": a.get("plus_code"),
                "status": a.get("status") or "placed",
            })

    # Auftragsnummern fuer alle referenzierten PKs holen
    referenced_pks = {p for p in referenced_pks if isinstance(p, int)}
    order_info: dict[int, dict] = {}
    if referenced_pks:
        rows = await _db.orders_cache.find(
            {"primary_key": {"$in": list(referenced_pks)}},
            {"_id": 0, "primary_key": 1, "order_no": 1, "event": 1, "contact_name": 1},
        ).to_list(2000)
        order_info = {r["primary_key"]: r for r in rows}

    for e in raw_entries:
        e["from_order_no"] = (order_info.get(e["from_pk"]) or {}).get("order_no") or f"#{e['from_pk']}"
        e["to_order_no"] = (order_info.get(e["to_pk"]) or {}).get("order_no") or f"#{e['to_pk']}"
        e["current_order_no"] = (order_info.get(e["current_pk"]) or {}).get("order_no") or f"#{e['current_pk']}"
        e["from_event"] = (order_info.get(e["from_pk"]) or {}).get("event") or ""
        e["current_event"] = (order_info.get(e["current_pk"]) or {}).get("event") or ""

    # Optional: nur Moves aus einem bestimmten Quell-Auftrag
    if order_pk is not None:
        raw_entries = [e for e in raw_entries if e["from_pk"] == order_pk]

    # Optional: Volltext-Filter
    if q:
        s = q.lower()
        raw_entries = [
            e for e in raw_entries
            if s in (e.get("label") or "").lower()
            or s in (e.get("asset_type") or "").lower()
            or s in (e.get("moved_by") or "").lower()
            or s in (e.get("from_order_no") or "").lower()
            or s in (e.get("to_order_no") or "").lower()
            or s in (e.get("current_order_no") or "").lower()
        ]

    # Sort neueste zuerst
    raw_entries.sort(key=lambda e: e.get("moved_at") or "", reverse=True)
    return {"moves": raw_entries, "count": len(raw_entries)}
