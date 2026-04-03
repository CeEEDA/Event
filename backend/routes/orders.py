from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import httpx
import asyncio
import math

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

        return {
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    """Find generators within the order's radius."""
    settings = await _db.order_settings.find_one({"order_pk": order_pk}, {"_id": 0})
    if not settings or not settings.get("center_lat"):
        return {"generators": []}

    center_lat = settings["center_lat"]
    center_lng = settings["center_lng"]
    radius_km = settings.get("radius_km", 5.0)

    # Get all generators with GPS coordinates
    generators = await _db.generators.find(
        {"latitude": {"$ne": None}, "longitude": {"$ne": None}},
        {"_id": 0},
    ).to_list(500)

    nearby = []
    for g in generators:
        lat = g.get("latitude")
        lng = g.get("longitude")
        if lat is None or lng is None:
            continue
        try:
            dist = _haversine_km(center_lat, center_lng, float(lat), float(lng))
        except (ValueError, TypeError):
            continue
        if dist <= radius_km:
            nearby.append({
                "id": g.get("id"),
                "name": g.get("name", ""),
                "model": g.get("model", ""),
                "serial_number": g.get("serial_number", ""),
                "status": g.get("status", "offline"),
                "latitude": lat,
                "longitude": lng,
                "distance_km": round(dist, 2),
                "last_seen": g.get("last_seen"),
            })

    nearby.sort(key=lambda x: x["distance_km"])
    return {"generators": nearby, "center_lat": center_lat, "center_lng": center_lng, "radius_km": radius_km}


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
    """Get deployment history for a specific generator."""
    deployments = await _db.deployment_history.find(
        {"generator_id": generator_id}, {"_id": 0}
    ).sort("started_at", -1).to_list(100)
    return {"deployments": deployments}



# ── Order Assets (manual placement) ──

@router.get("/epirent/{order_pk}/assets")
async def get_order_assets(order_pk: int, user: dict = Depends(_auth_user)):
    """Get all manually placed assets for an order."""
    assets = await _db.order_assets.find(
        {"order_pk": order_pk}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
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
    """Delete a manually placed asset."""
    result = await _db.order_assets.delete_one({"id": asset_id, "order_pk": order_pk})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Asset nicht gefunden")
    return {"ok": True}


@router.get("/epirent/{order_pk}/billing-pdf")
async def get_billing_pdf(order_pk: int, token: str = Query(None)):
    """Generate a comprehensive billing PDF for an order."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    import io, os, base64

    if not token:
        raise HTTPException(status_code=401)
    try:
        payload = _decode_jwt_token(token)
        user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401)
    except Exception:
        raise HTTPException(status_code=401)

    # Fetch order data
    from routes.orders import _get_epirent_config
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

    # Fetch all project reports
    reports = await _db.project_reports.find({"order_pk": str(order_pk)}, {"_id": 0}).sort("created_at", 1).to_list(100)
    # Fetch all fuel receipts
    fuel_receipts = await _db.fuel_receipts.find({"order_pk": str(order_pk)}, {"_id": 0}).sort("date", 1).to_list(100)

    # ── PDF Setup ──
    PURPLE = colors.HexColor("#7c3aed")
    HEADER_BG = colors.HexColor("#ede9fe")
    BORDER = colors.HexColor("#d1d5db")
    DARK = colors.HexColor("#1f2937")
    LIGHT_GRAY = colors.HexColor("#f9fafb")

    s_title = ParagraphStyle("T", fontSize=22, fontName="Helvetica-Bold", textColor=PURPLE, spaceAfter=4)
    s_h2 = ParagraphStyle("H2", fontSize=12, fontName="Helvetica-Bold", textColor=PURPLE, spaceBefore=10, spaceAfter=4)
    s_h3 = ParagraphStyle("H3", fontSize=10, fontName="Helvetica-Bold", textColor=DARK, spaceBefore=6, spaceAfter=3)
    s_label = ParagraphStyle("L", fontSize=8, textColor=colors.HexColor("#6b7280"))
    s_value = ParagraphStyle("V", fontSize=9, textColor=DARK)
    s_value_bold = ParagraphStyle("VB", fontSize=9, textColor=DARK, fontName="Helvetica-Bold")
    s_cell = ParagraphStyle("C", fontSize=8, textColor=DARK, leading=10)
    s_cell_bold = ParagraphStyle("CB", fontSize=8, textColor=DARK, fontName="Helvetica-Bold", leading=10)
    s_cell_right = ParagraphStyle("CR", fontSize=8, textColor=DARK, fontName="Helvetica-Bold", alignment=TA_RIGHT)
    s_small = ParagraphStyle("SM", fontSize=7, textColor=colors.grey)
    s_confirm = ParagraphStyle("CF", fontSize=7, textColor=DARK, leading=9)

    def _short_name(full_name):
        parts = (full_name or "").strip().split()
        if len(parts) >= 2:
            return f"{parts[0][0]}.{parts[-1]}"
        return full_name or ""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    pw, ph = A4
    W = pw - 30*mm
    elems = []

    # ═══════════════════════════════════════
    # PAGE 1: DECKBLATT (Cover Page)
    # ═══════════════════════════════════════
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "logo.png")
    if os.path.exists(logo_path):
        logo = RLImage(logo_path, width=55*mm, height=12.8*mm)
        elems.append(logo)
    elems.append(Spacer(1, 10*mm))
    elems.append(Paragraph("Abrechnung", s_title))
    elems.append(Spacer(1, 8*mm))

    cover_data = [
        [Paragraph("Auftragsnummer:", s_label), Paragraph(f"<b>{order_no}</b>", s_value_bold)],
        [Paragraph("Kundennummer:", s_label), Paragraph(str(customer_no), s_value)],
        [Paragraph("Kunde:", s_label), Paragraph(f"<b>{contact_name}</b>", s_value_bold)],
        [Paragraph("Projekt:", s_label), Paragraph(f"<b>{event_name}</b>", s_value_bold)],
        [Paragraph("Adresse:", s_label), Paragraph(raw.get("address", ""), s_value)],
        [Paragraph("Zeitraum:", s_label), Paragraph(f"{raw.get('date_start', '')} - {raw.get('date_end', '')}", s_value)],
        [Paragraph("Projektberichte:", s_label), Paragraph(f"<b>{len(reports)}</b>", s_value_bold)],
        [Paragraph("Tankbelege:", s_label), Paragraph(f"<b>{len(fuel_receipts)}</b>", s_value_bold)],
    ]
    ct = Table(cover_data, colWidths=[35*mm, W - 35*mm])
    ct.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (1, 0), (1, -1), 0.5, BORDER),
    ]))
    elems.append(ct)
    elems.append(Spacer(1, 10*mm))

    # ═══════════════════════════════════════
    # STUNDEN-ZUSAMMENFASSUNG
    # ═══════════════════════════════════════
    elems.append(Paragraph("Stunden-Zusammenfassung", s_h2))

    # Collect all employees across all reports
    all_employees = {}  # name -> set of roles
    for r in reports:
        for m in r.get("mitarbeiter", []):
            name = m.get("name", "")
            if name:
                all_employees.setdefault(name, set()).add(m.get("rolle", "T"))
    emp_names = sorted(all_employees.keys())

    if emp_names and reports:
        # Aggregate hours by date
        date_hours = {}  # date -> {emp_name: {N: x, E: x, NO: x}}
        for r in reports:
            ma_list = r.get("mitarbeiter", [])
            for entry in r.get("work_log", []):
                datum = entry.get("datum", "")
                if not datum:
                    continue
                if datum not in date_hours:
                    date_hours[datum] = {}
                stunden = entry.get("stunden", {})
                for idx_str, vals in stunden.items():
                    if not isinstance(vals, dict):
                        continue
                    idx = int(idx_str) if idx_str.isdigit() else 0
                    if idx < len(ma_list):
                        emp_name = ma_list[idx].get("name", "")
                    else:
                        continue
                    if emp_name not in date_hours[datum]:
                        date_hours[datum][emp_name] = {"N": 0, "E": 0, "NO": 0}
                    for t in ["N", "E", "NO"]:
                        v = vals.get(t, 0)
                        if v and str(v) != "0":
                            try:
                                date_hours[datum][emp_name][t] += float(v)
                            except (ValueError, TypeError):
                                pass

        # Find which (emp, type) combos have data
        active_cols = []
        for emp in emp_names:
            for t in ["N", "E", "NO"]:
                has_val = any(
                    date_hours[d].get(emp, {}).get(t, 0)
                    for d in date_hours
                )
                if has_val:
                    active_cols.append((emp, t))

        if active_cols:
            hdr = [Paragraph("<b>Datum</b>", s_cell_bold)]
            for emp, t in active_cols:
                hdr.append(Paragraph(f"<b>{_short_name(emp)}</b><br/><font size='5' color='grey'>{t}</font>",
                    ParagraphStyle("AH", fontSize=7, fontName="Helvetica-Bold", alignment=TA_CENTER, textColor=PURPLE, leading=9)))

            num_cols = len(active_cols)
            col_w = min(18*mm, (W - 25*mm) / num_cols)
            h_widths = [25*mm] + [col_w] * num_cols

            h_rows = [hdr]
            totals = {(e, t): 0 for e, t in active_cols}

            for datum in sorted(date_hours.keys()):
                row = [Paragraph(datum, s_cell)]
                for emp, t in active_cols:
                    val = date_hours[datum].get(emp, {}).get(t, 0)
                    if val:
                        totals[(emp, t)] += val
                        row.append(Paragraph(str(val), ParagraphStyle("HV2", fontSize=8, alignment=TA_CENTER, textColor=DARK)))
                    else:
                        row.append("")
                h_rows.append(row)

            # Totals row
            total_row = [Paragraph("<b>GESAMT</b>", s_cell_bold)]
            for emp, t in active_cols:
                val = totals[(emp, t)]
                total_row.append(Paragraph(f"<b>{val}</b>", ParagraphStyle("TT", fontSize=8, fontName="Helvetica-Bold", alignment=TA_CENTER, textColor=PURPLE)))
            h_rows.append(total_row)

            ht = Table(h_rows, colWidths=h_widths)
            ht.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f5f3ff")),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ]))
            elems.append(ht)
    else:
        elems.append(Paragraph("Keine Stunden erfasst.", s_small))

    elems.append(Spacer(1, 8*mm))

    # ═══════════════════════════════════════
    # TANKBELEGE-ZUSAMMENFASSUNG
    # ═══════════════════════════════════════
    if fuel_receipts:
        elems.append(Paragraph("Tankbelege-Zusammenfassung", s_h2))
        fr_hdr = [
            Paragraph("<b>Datum</b>", s_cell_bold),
            Paragraph("<b>Kraftstoff</b>", s_cell_bold),
            Paragraph("<b>Liter</b>", s_cell_bold),
            Paragraph("<b>Preis/L</b>", s_cell_bold),
            Paragraph("<b>Gesamt</b>", s_cell_bold),
        ]
        fr_rows = [fr_hdr]
        total_liters = 0
        total_cost = 0
        for fr in fuel_receipts:
            liters = fr.get("quantity_liters", 0) or 0
            price = fr.get("price_per_liter", 0) or 0
            cost = liters * price
            total_liters += liters
            total_cost += cost
            fr_rows.append([
                Paragraph(fr.get("date", ""), s_cell),
                Paragraph(fr.get("fuel_type_label", fr.get("fuel_type", "")), s_cell),
                Paragraph(f"{liters:.1f}", s_cell),
                Paragraph(f"{price:.3f} EUR" if price else "", s_cell),
                Paragraph(f"{cost:.2f} EUR" if price else "", s_cell),
            ])
        # Total row
        fr_rows.append([
            Paragraph("<b>GESAMT</b>", s_cell_bold), "", 
            Paragraph(f"<b>{total_liters:.1f} L</b>", s_cell_bold),
            "",
            Paragraph(f"<b>{total_cost:.2f} EUR</b>", s_cell_bold),
        ])
        ft = Table(fr_rows, colWidths=[25*mm, 40*mm, 25*mm, 25*mm, W - 115*mm])
        ft.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f5f3ff")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ]))
        elems.append(ft)

    # ═══════════════════════════════════════
    # ANHANG: Einzelne Projektberichte
    # ═══════════════════════════════════════
    for r_idx, report in enumerate(reports):
        elems.append(PageBreak())
        ma_list = report.get("mitarbeiter", [])
        num_ma = len(ma_list) if ma_list else 0

        # Report header
        header_data = [[Paragraph(f"Projektbericht Nr. {report.get('projektnummer', '')}", s_h2), ""]]
        if os.path.exists(logo_path):
            rlogo = RLImage(logo_path, width=40*mm, height=9.3*mm)
            header_data = [[Paragraph(f"Projektbericht Nr. {report.get('projektnummer', '')}", s_h2), rlogo]]
        rht = Table(header_data, colWidths=[W - 45*mm, 45*mm])
        rht.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
        elems.append(rht)

        # Customer info line
        elems.append(Paragraph(f"{report.get('kunde_name', '')} | {report.get('kunde_anschrift', '')} {report.get('kunde_plz', '')} {report.get('kunde_ort', '')} | {report.get('projekt_datum', '')}", s_small))
        elems.append(Spacer(1, 2*mm))

        # Mitarbeiter list
        if ma_list:
            ma_text = ", ".join([f"{_short_name(m.get('name',''))} ({m.get('rolle','')})" for m in ma_list])
            elems.append(Paragraph(f"Mitarbeiter: {ma_text}", s_small))
            elems.append(Spacer(1, 2*mm))

        # Worklog table
        wl = report.get("work_log", [])
        if wl:
            # Find active cols for this report
            r_active = []
            for emp_idx in range(num_ma):
                name = _short_name(ma_list[emp_idx].get("name", "")) if emp_idx < len(ma_list) else ""
                for t in ["N", "E", "NO"]:
                    has_v = any(
                        e.get("stunden", {}).get(str(emp_idx), {}).get(t, "")
                        for e in wl
                        if e.get("stunden", {}).get(str(emp_idx), {}).get(t, "") not in ("", 0, "0")
                    )
                    if has_v:
                        r_active.append((emp_idx, t, name))

            wl_hdr = [Paragraph("<b>Datum</b>", s_cell_bold), Paragraph("<b>Beschreibung</b>", s_cell_bold)]
            for _, t, name in r_active:
                wl_hdr.append(Paragraph(f"<b>{name}</b><br/><font size='5' color='grey'>{t}</font>",
                    ParagraphStyle("WH", fontSize=6, fontName="Helvetica-Bold", alignment=TA_CENTER, textColor=PURPLE, leading=8)))

            n_cols = len(r_active)
            wl_hr_w = min(12*mm, (W - 18*mm - 30*mm) / max(n_cols, 1)) if n_cols else 10*mm
            wl_widths = [18*mm, W - 18*mm - n_cols * wl_hr_w] + [wl_hr_w] * n_cols

            wl_rows = [wl_hdr]
            for entry in wl:
                stunden = entry.get("stunden", {})
                has_content = entry.get("beschreibung", "").strip() or entry.get("datum", "").strip()
                has_hrs = any(stunden.get(str(ei), {}).get(t, "") not in ("", 0, "0") for ei, t, _ in r_active)
                if not has_content and not has_hrs:
                    continue
                row = [
                    Paragraph(entry.get("datum", ""), s_cell),
                    Paragraph((entry.get("beschreibung", "") or "").replace("\n", "<br/>"), s_cell),
                ]
                for emp_idx, t, _ in r_active:
                    val = stunden.get(str(emp_idx), {}).get(t, "")
                    if val and str(val) != "0" and val != 0:
                        row.append(Paragraph(f"<b>{val}</b>", ParagraphStyle("WV", fontSize=8, alignment=TA_CENTER, textColor=DARK, fontName="Helvetica-Bold")))
                    else:
                        row.append("")
                wl_rows.append(row)

            if len(wl_rows) > 1:
                wlt = Table(wl_rows, colWidths=wl_widths, repeatRows=1)
                wlt.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                    ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                ]))
                elems.append(wlt)

        # Bemerkungen
        bem = report.get("bemerkungen", "")
        if bem and bem.strip():
            elems.append(Spacer(1, 2*mm))
            elems.append(Paragraph(f"Bemerkungen: {bem}", s_small))

        # Signatures
        elems.append(Spacer(1, 4*mm))
        sig_items = []
        for label, key in [("Techniker", "unterschrift_techniker"), ("Kunde", "unterschrift_kunde")]:
            sig = report.get(key)
            if sig and sig.startswith("data:image"):
                try:
                    b64 = sig.split(",", 1)[1]
                    img_buf = io.BytesIO(base64.b64decode(b64))
                    sig_items.append([Paragraph(f"{label}:", s_label), RLImage(img_buf, width=35*mm, height=14*mm)])
                except Exception:
                    sig_items.append([Paragraph(f"{label}:", s_label), Paragraph("(vorhanden)", s_small)])
            else:
                sig_items.append([Paragraph(f"{label}:", s_label), Paragraph("—", s_small)])
        if sig_items:
            st = Table(sig_items, colWidths=[20*mm, 40*mm])
            st.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
            elems.append(st)

    # ═══════════════════════════════════════
    # ANHANG: Einzelne Tankbelege
    # ═══════════════════════════════════════
    if fuel_receipts:
        elems.append(PageBreak())
        elems.append(Paragraph("Tankbelege (Einzelnachweise)", s_h2))
        for fr in fuel_receipts:
            liters = fr.get("quantity_liters", 0) or 0
            price = fr.get("price_per_liter", 0) or 0
            cost = liters * price
            elems.append(Paragraph(
                f"<b>{fr.get('date', '')}</b> | {fr.get('fuel_type_label', fr.get('fuel_type', ''))} | "
                f"{liters:.1f} L | {cost:.2f} EUR | {fr.get('location', '')}",
                s_cell
            ))
            elems.append(Spacer(1, 1*mm))

    doc.build(elems)
    buf.seek(0)
    filename = f"Abrechnung_{order_no}_{event_name}.pdf".replace(" ", "_")
    from fastapi.responses import StreamingResponse
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
