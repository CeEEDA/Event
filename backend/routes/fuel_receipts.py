from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import math
import httpx

router = APIRouter(prefix="/api/fuel-receipts", tags=["fuel-receipts"])
security = HTTPBearer()

_db = None
_decode_jwt_token = None

ZAEHLER_NR = "11461"
MANUAL_BELEG_PREFIX = "X"
MANUAL_BELEG_START = 12000
LOGO_URL = "https://customer-assets.emergentagent.com/job_client-file-portal/artifacts/35th6vn9_cropped-logo.webp"


def init_fuel_receipt_routes(db, decode_jwt_token):
    global _db, _decode_jwt_token
    _db = db
    _decode_jwt_token = decode_jwt_token


FUEL_TYPES = {
    "diesel": "Diesel",
    "heizoel_leicht": "HEL schwefelarm",
    "hvo": "HVO",
}


async def _next_manual_beleg_nr():
    """Get next sequential manual receipt number (X12000, X12001, ...)."""
    pipeline = [
        {"$match": {"beleg_nr": {"$regex": f"^{MANUAL_BELEG_PREFIX}"}}},
        {"$project": {"num": {"$substr": ["$beleg_nr", len(MANUAL_BELEG_PREFIX), -1]}}},
        {"$project": {"num_int": {"$toInt": "$num"}}},
        {"$sort": {"num_int": -1}},
        {"$limit": 1},
    ]
    results = await _db.fuel_receipts.aggregate(pipeline).to_list(1)
    if results:
        return f"{MANUAL_BELEG_PREFIX}{results[0]['num_int'] + 1}"
    return f"{MANUAL_BELEG_PREFIX}{MANUAL_BELEG_START}"


def _calc_abgabe_times(quantity_liters, time_str):
    """Calculate Abgabe-Start and Abgabe-Ende for manual receipts.
    Rule: 3 min per 100L + 4 min base per refueling."""
    minutes = math.ceil(quantity_liters / 100) * 3 + 4
    try:
        parts = time_str.split(":")
        h, m = int(parts[0]), int(parts[1])
        total_start = h * 60 + m
        total_end = total_start + minutes
        end_h = (total_end // 60) % 24
        end_m = total_end % 60
        return f"{h:02d}:{m:02d}:00", f"{end_h:02d}:{end_m:02d}:00"
    except Exception:
        return time_str, time_str


# ── Auth helpers ──
async def _auth_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")
    return user


async def _require_admin_or_staff(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await _auth_user(credentials)
    if user.get("role") not in ("admin", "mitarbeiter"):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    return user


# ── Models ──
class FuelReceiptCreate(BaseModel):
    order_pk: Optional[str] = None
    order_name: Optional[str] = None
    fuel_type: str
    quantity_liters: float
    date: str
    time: str
    location: Optional[str] = ""
    beleg_nr: Optional[str] = None
    abgabe_start: Optional[str] = None
    abgabe_ende: Optional[str] = None
    zaehler_vor_start: Optional[float] = None
    fahrer: Optional[str] = ""
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    notes: Optional[str] = ""
    pi_local_id: Optional[str] = None
    raw_receipt_data: Optional[str] = None


class FuelReceiptUpdate(BaseModel):
    order_pk: Optional[str] = None
    order_name: Optional[str] = None
    fuel_type: Optional[str] = None
    quantity_liters: Optional[float] = None
    date: Optional[str] = None
    time: Optional[str] = None
    location: Optional[str] = None
    beleg_nr: Optional[str] = None
    abgabe_start: Optional[str] = None
    abgabe_ende: Optional[str] = None
    zaehler_vor_start: Optional[float] = None
    fahrer: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[str] = None


# ── Endpoints ──

@router.post("")
async def create_fuel_receipt(data: FuelReceiptCreate, user: dict = Depends(_require_admin_or_staff)):
    """Create a fuel receipt (manual entry from portal)."""
    created_by = user.get("name", user.get("email", ""))

    if data.fuel_type not in FUEL_TYPES:
        raise HTTPException(status_code=400, detail=f"Ungueltige Kraftstoffart. Erlaubt: {', '.join(FUEL_TYPES.keys())}")

    if data.pi_local_id:
        existing = await _db.fuel_receipts.find_one({"pi_local_id": data.pi_local_id}, {"_id": 0})
        if existing:
            return existing

    # Auto-generate beleg_nr for manual receipts
    beleg_nr = data.beleg_nr
    if not beleg_nr:
        beleg_nr = await _next_manual_beleg_nr()

    receipt_id = str(uuid.uuid4())
    doc = {
        "id": receipt_id,
        "order_pk": data.order_pk,
        "order_name": data.order_name or "",
        "fuel_type": data.fuel_type,
        "fuel_type_label": FUEL_TYPES[data.fuel_type],
        "quantity_liters": data.quantity_liters,
        "date": data.date,
        "time": data.time,
        "location": data.location or "",
        "zaehler_nr": ZAEHLER_NR,
        "beleg_nr": beleg_nr,
        "abgabe_start": data.abgabe_start,
        "abgabe_ende": data.abgabe_ende,
        "zaehler_vor_start": data.zaehler_vor_start,
        "fahrer": data.fahrer or "",
        "gps_lat": data.gps_lat,
        "gps_lng": data.gps_lng,
        "raw_receipt_data": data.raw_receipt_data,
        "notes": data.notes or "",
        "status": "pending",
        "source": "pi" if data.pi_local_id else "manual",
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "confirmed_by": None,
        "confirmed_at": None,
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "pi_local_id": data.pi_local_id,
    }
    await _db.fuel_receipts.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.post("/sync")
async def sync_fuel_receipts(receipts: List[FuelReceiptCreate]):
    """Bulk sync from Pi - creates multiple receipts with dedup. No auth required for Pi."""
    created = []
    skipped = 0
    for r in receipts:
        if r.pi_local_id:
            existing = await _db.fuel_receipts.find_one({"pi_local_id": r.pi_local_id}, {"_id": 0})
            if existing:
                skipped += 1
                continue

        receipt_id = str(uuid.uuid4())
        doc = {
            "id": receipt_id,
            "order_pk": r.order_pk,
            "order_name": r.order_name or "",
            "fuel_type": r.fuel_type,
            "fuel_type_label": FUEL_TYPES.get(r.fuel_type, r.fuel_type),
            "quantity_liters": r.quantity_liters,
            "date": r.date,
            "time": r.time,
            "location": r.location or "",
            "zaehler_nr": ZAEHLER_NR,
            "beleg_nr": r.beleg_nr or "",
            "abgabe_start": r.abgabe_start,
            "abgabe_ende": r.abgabe_ende,
            "zaehler_vor_start": r.zaehler_vor_start,
            "fahrer": r.fahrer or "",
            "gps_lat": r.gps_lat,
            "gps_lng": r.gps_lng,
            "raw_receipt_data": r.raw_receipt_data,
            "notes": r.notes or "",
            "status": "pending",
            "source": "pi",
            "created_by": "Tankwagen-Pi",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "confirmed_by": None,
            "confirmed_at": None,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "pi_local_id": r.pi_local_id,
        }
        await _db.fuel_receipts.insert_one(doc)
        doc.pop("_id", None)
        created.append(doc)

    return {"created": len(created), "skipped": skipped, "receipts": created}


@router.get("")
async def list_fuel_receipts(
    status: Optional[str] = None,
    fuel_type: Optional[str] = None,
    order_pk: Optional[str] = None,
    user: dict = Depends(_auth_user),
):
    query = {}
    if status:
        query["status"] = status
    if fuel_type:
        query["fuel_type"] = fuel_type
    if order_pk:
        query["order_pk"] = order_pk
    receipts = await _db.fuel_receipts.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return receipts


@router.get("/stats")
async def fuel_receipt_stats(user: dict = Depends(_auth_user)):
    total = await _db.fuel_receipts.count_documents({})
    pending = await _db.fuel_receipts.count_documents({"status": "pending"})
    confirmed = await _db.fuel_receipts.count_documents({"status": "confirmed"})
    pipeline = [
        {"$group": {"_id": "$fuel_type", "total_liters": {"$sum": "$quantity_liters"}, "count": {"$sum": 1}}},
    ]
    by_type = await _db.fuel_receipts.aggregate(pipeline).to_list(10)
    return {
        "total": total,
        "pending": pending,
        "confirmed": confirmed,
        "by_fuel_type": {r["_id"]: {"liters": r["total_liters"], "count": r["count"]} for r in by_type},
    }


@router.get("/by-order/{order_pk}")
async def get_receipts_by_order(order_pk: str, user: dict = Depends(_auth_user)):
    """Get all fuel receipts for a specific order with adjustment applied."""
    receipts = await _db.fuel_receipts.find(
        {"order_pk": str(order_pk)}, {"_id": 0}
    ).sort("date", -1).to_list(100)

    # Load adjustment for this order
    adj = await _db.fuel_adjustments.find_one({"order_pk": str(order_pk)}, {"_id": 0})
    pct = adj.get("adjustment_percent", 0) if adj else 0

    for r in receipts:
        r["original_quantity_liters"] = r["quantity_liters"]
        if pct != 0:
            r["quantity_liters"] = round(r["quantity_liters"] * (1 + pct / 100), 1)
        r["adjustment_percent"] = pct

    return receipts


@router.get("/by-order/{order_pk}/adjustment")
async def get_order_adjustment(order_pk: str, user: dict = Depends(_require_admin_or_staff)):
    """Get the %-adjustment for an order."""
    adj = await _db.fuel_adjustments.find_one({"order_pk": str(order_pk)}, {"_id": 0})
    return adj or {"order_pk": order_pk, "adjustment_percent": 0}


@router.post("/by-order/{order_pk}/adjustment")
async def set_order_adjustment(order_pk: str, data: dict, user: dict = Depends(_require_admin_or_staff)):
    """Admin: Set %-adjustment for all receipts in an order."""
    pct = data.get("adjustment_percent", 0)
    await _db.fuel_adjustments.update_one(
        {"order_pk": str(order_pk)},
        {"$set": {
            "order_pk": str(order_pk),
            "adjustment_percent": float(pct),
            "updated_by": user.get("name", user.get("email", "")),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"order_pk": order_pk, "adjustment_percent": float(pct)}


@router.get("/by-order/{order_pk}/pdf-all")
async def export_all_receipts_pdf(
    order_pk: str,
    token: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
):
    """Export ALL receipts for an order as a single multi-page PDF."""
    if token:
        _decode_jwt_token(token)
    elif credentials:
        _decode_jwt_token(credentials.credentials)
    else:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert")

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from io import BytesIO
    from starlette.responses import Response

    receipts = await _db.fuel_receipts.find(
        {"order_pk": str(order_pk)}, {"_id": 0}
    ).sort("date", -1).to_list(100)

    if not receipts:
        raise HTTPException(status_code=404, detail="Keine Belege fuer diesen Auftrag")

    adj = await _db.fuel_adjustments.find_one({"order_pk": str(order_pk)}, {"_id": 0})
    pct = adj.get("adjustment_percent", 0) if adj else 0

    # Fetch logo once
    logo_img = None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(LOGO_URL, timeout=10)
            if resp.status_code == 200:
                logo_img = ImageReader(BytesIO(resp.content))
    except Exception:
        pass

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    for doc in receipts:
        qty = doc["quantity_liters"]
        if pct != 0:
            qty = round(qty * (1 + pct / 100), 1)
        _draw_receipt_page(c, doc, qty, logo_img)
        c.showPage()

    c.save()
    buf.seek(0)

    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Tankbelege_Auftrag_{order_pk}.pdf"},
    )


@router.get("/{receipt_id}")
async def get_fuel_receipt(receipt_id: str, user: dict = Depends(_auth_user)):
    doc = await _db.fuel_receipts.find_one({"id": receipt_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Tankbeleg nicht gefunden")
    return doc


@router.put("/{receipt_id}")
async def update_fuel_receipt(receipt_id: str, data: FuelReceiptUpdate, user: dict = Depends(_require_admin_or_staff)):
    doc = await _db.fuel_receipts.find_one({"id": receipt_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Tankbeleg nicht gefunden")

    update = {}
    for field, value in data.dict(exclude_unset=True).items():
        if value is not None:
            update[field] = value

    if "fuel_type" in update:
        if update["fuel_type"] not in FUEL_TYPES:
            raise HTTPException(status_code=400, detail="Ungueltige Kraftstoffart")
        update["fuel_type_label"] = FUEL_TYPES[update["fuel_type"]]

    if "status" in update and update["status"] == "confirmed":
        update["confirmed_at"] = datetime.now(timezone.utc).isoformat()
        update["confirmed_by"] = user.get("name", user.get("email", ""))

    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _db.fuel_receipts.update_one({"id": receipt_id}, {"$set": update})
    updated = await _db.fuel_receipts.find_one({"id": receipt_id}, {"_id": 0})
    return updated


@router.post("/{receipt_id}/confirm")
async def confirm_fuel_receipt(receipt_id: str, user: dict = Depends(_require_admin_or_staff)):
    doc = await _db.fuel_receipts.find_one({"id": receipt_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Tankbeleg nicht gefunden")
    await _db.fuel_receipts.update_one(
        {"id": receipt_id},
        {"$set": {
            "status": "confirmed",
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
            "confirmed_by": user.get("name", user.get("email", "")),
        }},
    )
    return {"message": "Tankbeleg bestaetigt"}


@router.post("/{receipt_id}/reject")
async def reject_fuel_receipt(receipt_id: str, user: dict = Depends(_require_admin_or_staff)):
    doc = await _db.fuel_receipts.find_one({"id": receipt_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Tankbeleg nicht gefunden")
    await _db.fuel_receipts.update_one(
        {"id": receipt_id},
        {"$set": {"status": "rejected", "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"message": "Tankbeleg abgelehnt"}


@router.delete("/{receipt_id}")
async def delete_fuel_receipt(receipt_id: str, user: dict = Depends(_require_admin_or_staff)):
    result = await _db.fuel_receipts.delete_one({"id": receipt_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tankbeleg nicht gefunden")
    return {"message": "Tankbeleg geloescht"}


@router.get("/{receipt_id}/pdf")
async def export_fuel_receipt_pdf(
    receipt_id: str,
    token: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
):
    """Export a single fuel receipt as PDF with adjustment applied."""
    if token:
        _decode_jwt_token(token)
    elif credentials:
        _decode_jwt_token(credentials.credentials)
    else:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert")

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from io import BytesIO
    from starlette.responses import Response

    doc = await _db.fuel_receipts.find_one({"id": receipt_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Tankbeleg nicht gefunden")

    # Load adjustment
    qty = doc["quantity_liters"]
    if doc.get("order_pk"):
        adj = await _db.fuel_adjustments.find_one({"order_pk": doc["order_pk"]}, {"_id": 0})
        pct = adj.get("adjustment_percent", 0) if adj else 0
        if pct != 0:
            qty = round(qty * (1 + pct / 100), 1)

    logo_img = None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(LOGO_URL, timeout=10)
            if resp.status_code == 200:
                logo_img = ImageReader(BytesIO(resp.content))
    except Exception:
        pass

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _draw_receipt_page(c, doc, qty, logo_img)
    c.save()
    buf.seek(0)

    beleg_nr = doc.get("beleg_nr", doc["id"][:8])
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Tankbeleg_{beleg_nr}.pdf"},
    )


def _draw_receipt_page(c, doc, display_qty, logo_img=None):
    """Draw a single receipt page on the canvas."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor

    w, h = A4
    margin = 25 * mm
    fuchsia = HexColor("#a21caf")

    is_manual = doc.get("source") != "pi"
    abgabe_start = doc.get("abgabe_start")
    abgabe_ende = doc.get("abgabe_ende")
    if is_manual and (not abgabe_start or not abgabe_ende):
        abgabe_start, abgabe_ende = _calc_abgabe_times(
            display_qty, doc.get("time", "00:00"),
        )

    # Logo
    if logo_img:
        try:
            c.drawImage(logo_img, margin, h - 45 * mm, width=55 * mm, height=20 * mm, preserveAspectRatio=True, mask="auto")
        except Exception:
            c.setFont("Helvetica-Bold", 16)
            c.setFillColor(HexColor("#1f2937"))
            c.drawString(margin, h - 30 * mm, "EVENTENERGIE DEUTSCHLAND")
    else:
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(HexColor("#1f2937"))
        c.drawString(margin, h - 30 * mm, "EVENTENERGIE DEUTSCHLAND")

    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#6b7280"))
    c.drawString(margin, h - 52 * mm, "Thyssenstrasse 10 | 56626 Andernach")

    c.setStrokeColor(fuchsia)
    c.setLineWidth(1.5)
    c.line(margin, h - 55 * mm, w - margin, h - 55 * mm)

    # Kunde
    y = h - 68 * mm
    c.setFillColor(HexColor("#1f2937"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Kunde:")
    c.setFont("Helvetica", 11)
    kunde_text = doc.get("order_name", "") or (f"Auftrag {doc['order_pk']}" if doc.get("order_pk") else "—")
    c.drawString(margin + 25 * mm, y, kunde_text)

    # Printer data block
    y = h - 90 * mm
    c.setFillColor(HexColor("#f3f4f6"))
    c.roundRect(margin, y - 60 * mm, w - 2 * margin, 62 * mm, 3 * mm, fill=1, stroke=0)

    c.setFillColor(HexColor("#374151"))
    row_y = y - 5 * mm
    label_x = margin + 8 * mm
    val_x = w - margin - 8 * mm

    zvs = doc.get("zaehler_vor_start")
    printer_fields = [
        ("Zaehler-Nr.", doc.get("zaehler_nr", ZAEHLER_NR)),
        ("Beleg-Nr.", doc.get("beleg_nr", "—")),
        ("Abgabe-Datum", doc.get("date", "—")),
        ("Abgabe-Start", abgabe_start or "—"),
        ("Abgabe-Ende", abgabe_ende or "—"),
        ("Zaehler vor Start", f"{zvs} L" if zvs is not None else "0 L"),
    ]

    c.setFont("Courier", 10)
    for label, value in printer_fields:
        c.drawString(label_x, row_y, label)
        c.drawRightString(val_x, row_y, str(value))
        row_y -= 7 * mm

    row_y -= 3 * mm
    c.setFont("Courier-Bold", 10)
    c.setFillColor(fuchsia)
    fuel_label = doc.get("fuel_type_label", FUEL_TYPES.get(doc.get("fuel_type", ""), ""))
    c.drawString(label_x, row_y, f"*{fuel_label}*")
    row_y -= 8 * mm
    c.setFont("Courier-Bold", 14)
    c.drawString(label_x, row_y, "Menge bei 15 C")
    c.drawRightString(val_x, row_y, f"{display_qty:.0f} L")

    # Manual fields
    y = h - 165 * mm
    c.setFillColor(HexColor("#1f2937"))
    c.setFont("Helvetica-Bold", 10)
    for label, value in [("Standort:", doc.get("location", "")), ("Fahrer:", doc.get("fahrer", doc.get("created_by", "")))]:
        c.drawString(margin, y, label)
        c.setFont("Helvetica", 10)
        c.drawString(margin + 28 * mm, y, str(value) if value else "—")
        c.setStrokeColor(HexColor("#d1d5db"))
        c.setLineWidth(0.5)
        c.line(margin + 28 * mm, y - 2, w - margin, y - 2)
        c.setFont("Helvetica-Bold", 10)
        y -= 12 * mm

    # Footer
    c.setFillColor(HexColor("#9ca3af"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(w / 2, 20 * mm, "Eventenergie Deutschland GmbH & Co. KG")
    c.setFont("Helvetica", 7)
    c.drawCentredString(w / 2, 15 * mm, f"Beleg-ID: {doc['id'][:8]}")
