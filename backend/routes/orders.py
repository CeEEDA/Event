from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone, timedelta
import httpx

router = APIRouter(prefix="/api/orders", tags=["orders"])

_db = None


def init_orders_routes(db):
    global _db
    _db = db


async def _get_epirent_config():
    config = await _db.integrations.find_one({"type": "ERP", "active": True}, {"_id": 0})
    if not config:
        raise HTTPException(status_code=503, detail="Keine aktive ERP-Schnittstelle konfiguriert")
    return config


@router.get("/epirent")
async def get_epirent_orders(
    page: int = Query(0, ge=0),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Fetch orders from EpiRent API with optional date range and search."""
    config = await _get_epirent_config()
    api_url = config.get("api_url", "").rstrip("/")
    api_key = config.get("api_key", "")

    headers = {
        "X-EPI-NO-SESSION": "True",
        "X-EPI-ACC-TOK": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=15, verify=not config.get("ssl_skip", False)) as client:
            # Fetch all orders (EpiRent paging)
            resp = await client.get(
                f"{api_url}/v1/order/all?pgs={page_size}&page={page}",
                headers=headers,
            )
            data = resp.json()

            if not data.get("success"):
                raise HTTPException(status_code=502, detail=data.get("message", "EpiRent Fehler"))

            orders = data.get("payload", [])
            total = data.get("paging", {}).get("pages_length", len(orders))

            # Parse orders into our format
            result = []
            for o in orders:
                # Extract event schedule
                event_start = None
                event_end = None
                dispo_start = None
                dispo_end = None
                for sched in o.get("order_schedule", []):
                    if sched.get("name") == "Event" or sched.get("type") == 7:
                        event_start = sched.get("date_start")
                        event_end = sched.get("date_end")
                    elif sched.get("name") == "Dispo" or sched.get("type") == 1:
                        dispo_start = sched.get("date_start")
                        dispo_end = sched.get("date_end")

                contact_name = ""
                if o.get("contact"):
                    contact_name = o["contact"].get("name", "")

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
                    "customer_no": o.get("customer_no"),
                    "is_confirmed": o.get("is_confirmed", False),
                    "is_canceled": o.get("is_canceled", False),
                    "is_archived": o.get("is_archived", False),
                    "is_current_version": o.get("is_current_version", False),
                    "editor_name": o.get("editor_name", ""),
                    "editor_short": o.get("editor_short", ""),
                    "sum_net": o.get("sum_net", 0),
                    "sum_gro": o.get("sum_gro", 0),
                }
                result.append(order)

            # Client-side filtering (EpiRent API doesn't support complex filters)
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

            if search:
                s = search.lower()
                result = [o for o in result if
                    s in o.get("event", "").lower() or
                    s in o.get("order_no", "").lower() or
                    s in o.get("contact_name", "").lower() or
                    s in str(o.get("customer_no", "")).lower()
                ]

            return {
                "orders": result,
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="EpiRent Server nicht erreichbar")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
