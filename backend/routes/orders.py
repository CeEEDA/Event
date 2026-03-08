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
    """Fetch delivery address from a single order's detail endpoint."""
    try:
        resp = await client.get(f"{api_url}/v1/order/{order_pk}", headers=headers)
        data = resp.json()
        payload = data.get("payload")
        if isinstance(payload, list) and len(payload) > 0:
            payload = payload[0]
        if isinstance(payload, dict):
            addr = payload.get("address_delivery")
            return order_pk, _format_delivery_address(addr)
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

            # Step 1: Parse orders (without addresses yet)
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
                }
                result.append(order)

            # Step 2: Apply date filtering BEFORE fetching addresses
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

            # Step 3: Apply text search (except address) BEFORE fetching addresses
            if search:
                s = search.lower()
                result = [o for o in result if
                    s in o.get("event", "").lower() or
                    s in o.get("order_no", "").lower() or
                    s in o.get("contact_name", "").lower() or
                    s in str(o.get("customer_no", "")).lower()
                ]

            # Step 4: Fetch delivery addresses only for filtered results
            order_pks = [o["primary_key"] for o in result if o.get("primary_key")]
            if order_pks:
                epi_headers = {
                    "X-EPI-NO-SESSION": "True",
                    "X-EPI-ACC-TOK": api_key,
                }
                sem = asyncio.Semaphore(15)

                async def _fetch_with_sem(pk):
                    async with sem:
                        return await _fetch_order_delivery_address(client, api_url, epi_headers, pk)

                addr_results = await asyncio.gather(*[_fetch_with_sem(pk) for pk in order_pks])
                delivery_map = {pk: addr for pk, addr in addr_results}
                for o in result:
                    o["address"] = delivery_map.get(o["primary_key"], "")

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
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("name", user.get("email", "")),
    }
    await _db.order_assets.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/epirent/{order_pk}/assets/{asset_id}")
async def delete_order_asset(order_pk: int, asset_id: str, user: dict = Depends(_auth_user)):
    """Delete a manually placed asset."""
    result = await _db.order_assets.delete_one({"id": asset_id, "order_pk": order_pk})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Asset nicht gefunden")
    return {"ok": True}
