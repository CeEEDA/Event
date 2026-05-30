"""
Tank-Status-Modul

Use-Case: Tankwagen-Trupp faehrt taeglich die Stromerzeuger ab, erfasst pro
Generator: Tankgroesse (einmalig), aktueller Tankstand in L, aktuelle Last
(kW), Betriebsstunden. Ab Tag 3 (>= 2 vorherige Readings je Asset) wird der
Verbrauch (L/h) berechnet und eine Prognose ausgewiesen, wann der Tank leer
ist und ein Refill faellig wird.

Datenmodell `tank_readings`:
  id, order_pk, asset_id, asset_label, recorded_at,
  tank_size_l, fuel_level_l, fuel_percent, load_kw, runtime_h,
  comment, photo_id, created_by, created_by_id, latitude, longitude

`tank_reading_photos`:
  id, reading_id, order_pk, content_type, data_base64, uploaded_at
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid
import base64
import csv
import io

router = APIRouter(prefix="/api/orders", tags=["tank-status"])
security = HTTPBearer()

_db = None
_decode_jwt_token = None


def init_tank_status_routes(db, decode_jwt_token):
    global _db, _decode_jwt_token
    _db = db
    _decode_jwt_token = decode_jwt_token


async def _auth_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    payload = _decode_jwt_token(creds.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Ungueltiges Token")
    return payload


class TankReadingCreate(BaseModel):
    asset_id: str
    reading_type: Optional[str] = "normal"  # "commissioning" oder "normal"
    tank_size_l: Optional[float] = None  # nur bei commissioning Pflicht
    fuel_level_l: Optional[float] = None
    fuel_percent: Optional[float] = None
    load_kw: Optional[float] = None
    runtime_h: Optional[float] = None  # Betriebsstunden Generator-Display
    kwh_total: Optional[float] = None  # kWh-Zaehlerstand kumuliert
    comment: Optional[str] = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@router.post("/epirent/{order_pk}/tank-readings")
async def create_tank_reading(
    order_pk: int, data: TankReadingCreate, user: dict = Depends(_auth_user),
):
    # Asset existieren?
    asset = await _db.order_assets.find_one(
        {"id": data.asset_id, "order_pk": order_pk}, {"_id": 0, "id": 1, "label": 1, "asset_type": 1},
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset nicht gefunden")
    if (asset.get("asset_type") or "").lower() != "stromerzeuger":
        raise HTTPException(status_code=400, detail="Tankstatus nur fuer Stromerzeuger")

    reading_type = (data.reading_type or "normal").lower()
    existing_commissioning = await _db.tank_readings.find_one(
        {"order_pk": order_pk, "asset_id": data.asset_id, "reading_type": "commissioning"},
        {"_id": 0, "tank_size_l": 1},
    )

    if reading_type == "commissioning":
        # Pflicht: tank_size_l, fuel_level_l, runtime_h, kwh_total
        if existing_commissioning:
            raise HTTPException(status_code=400, detail="Inbetriebnahme bereits erfasst")
        missing = []
        if not data.tank_size_l or data.tank_size_l <= 0: missing.append("Tankgroesse")
        if data.fuel_level_l is None: missing.append("Tankstand (L)")
        if data.runtime_h is None: missing.append("Betriebsstunden")
        if data.kwh_total is None: missing.append("kWh-Zaehlerstand")
        if missing:
            raise HTTPException(status_code=400, detail=f"Pflichtfelder fehlen: {', '.join(missing)}")
        tank_size_l = float(data.tank_size_l)
        fuel_level_l = float(data.fuel_level_l)
        fuel_percent = round(fuel_level_l / tank_size_l * 100, 1)
    else:
        # Normales Reading: erst nach Inbetriebnahme moeglich
        if not existing_commissioning:
            raise HTTPException(
                status_code=400,
                detail="Bitte zuerst Inbetriebnahme erfassen (Tankgroesse + Betriebsstunden + kWh)",
            )
        tank_size_l = float(existing_commissioning["tank_size_l"])
        missing = []
        if data.kwh_total is None: missing.append("kWh-Zaehlerstand")
        if data.load_kw is None: missing.append("Aktuelle Last (kW)")
        if data.fuel_level_l is None and data.fuel_percent is None:
            missing.append("Tankstand (L) oder Prozent")
        if missing:
            raise HTTPException(status_code=400, detail=f"Pflichtfelder fehlen: {', '.join(missing)}")
        # Liter <-> Prozent autom. berechnen, je nachdem was angegeben wurde
        if data.fuel_level_l is not None:
            fuel_level_l = float(data.fuel_level_l)
            fuel_percent = round(fuel_level_l / tank_size_l * 100, 1)
        else:
            fuel_percent = float(data.fuel_percent)
            fuel_level_l = round(tank_size_l * fuel_percent / 100, 1)

    if fuel_level_l < 0 or fuel_level_l > tank_size_l * 1.05:
        raise HTTPException(status_code=400, detail="Tankstand liegt ausserhalb plausibler Grenzen")

    doc = {
        "id": str(uuid.uuid4()),
        "order_pk": order_pk,
        "asset_id": data.asset_id,
        "asset_label": asset.get("label") or "",
        "asset_type": asset.get("asset_type") or "",
        "reading_type": reading_type,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "tank_size_l": tank_size_l,
        "fuel_level_l": fuel_level_l,
        "fuel_percent": fuel_percent,
        "load_kw": float(data.load_kw) if data.load_kw is not None else None,
        "runtime_h": float(data.runtime_h) if data.runtime_h is not None else None,
        "kwh_total": float(data.kwh_total) if data.kwh_total is not None else None,
        "comment": (data.comment or "").strip(),
        "photo_id": None,
        "created_by": user.get("name") or user.get("email") or "",
        "created_by_id": user.get("id") or user.get("user_id") or user.get("email") or "",
        "latitude": data.latitude,
        "longitude": data.longitude,
    }
    await _db.tank_readings.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/epirent/{order_pk}/tank-readings")
async def list_tank_readings(
    order_pk: int,
    asset_id: Optional[str] = None,
    min_fuel_l: Optional[float] = None,
    max_fuel_l: Optional[float] = None,
    user: dict = Depends(_auth_user),
):
    q = {"order_pk": order_pk}
    if asset_id:
        q["asset_id"] = asset_id
    fuel_q = {}
    if min_fuel_l is not None:
        fuel_q["$gte"] = min_fuel_l
    if max_fuel_l is not None:
        fuel_q["$lte"] = max_fuel_l
    if fuel_q:
        q["fuel_level_l"] = fuel_q
    rows = await _db.tank_readings.find(q, {"_id": 0}).sort("recorded_at", -1).to_list(2000)
    return {"readings": rows}


@router.delete("/epirent/{order_pk}/tank-readings/{reading_id}")
async def delete_tank_reading(
    order_pk: int, reading_id: str, user: dict = Depends(_auth_user),
):
    r = await _db.tank_readings.delete_one({"id": reading_id, "order_pk": order_pk})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Reading nicht gefunden")
    await _db.tank_reading_photos.delete_many({"reading_id": reading_id})
    return {"ok": True}


@router.get("/epirent/{order_pk}/tank-readings/forecast")
async def tank_readings_forecast(order_pk: int, user: dict = Depends(_auth_user)):
    """Pro Stromerzeuger: latest Tankstand + durchschnittlicher Verbrauch (L/h)
    + geschaetzte Restlaufzeit + Kritisch-ETA.

    Verbrauch wird ueber konsekutive Paare berechnet, Refill-Spruenge
    (curr.fuel > prev.fuel) werden uebersprungen. Wenn beide Readings
    `runtime_h` haben, nutzen wir die Differenz der Betriebsstunden;
    sonst Wall-Clock-Stunden zwischen den Readings.
    """
    rows = await _db.tank_readings.find(
        {"order_pk": order_pk},
        {"_id": 0},
    ).sort("recorded_at", 1).to_list(5000)

    grouped: dict[str, list] = {}
    for r in rows:
        grouped.setdefault(r["asset_id"], []).append(r)

    out = []
    for asset_id, readings in grouped.items():
        latest = readings[-1]
        # Verbrauchs-LpH aus Paaren
        lph_samples: list[float] = []
        for i in range(1, len(readings)):
            prev, curr = readings[i - 1], readings[i]
            if curr["fuel_level_l"] > prev["fuel_level_l"]:
                continue  # Refill -> Paar verwerfen
            delta_fuel = prev["fuel_level_l"] - curr["fuel_level_l"]
            if delta_fuel <= 0:
                continue
            # bevorzugt: runtime_h-Delta (Generator-Laufzeit), sonst Wall-Clock
            hours: Optional[float] = None
            if prev.get("runtime_h") is not None and curr.get("runtime_h") is not None:
                rh = curr["runtime_h"] - prev["runtime_h"]
                if rh > 0:
                    hours = rh
            if hours is None:
                try:
                    p_dt = datetime.fromisoformat(prev["recorded_at"].replace("Z", "+00:00"))
                    c_dt = datetime.fromisoformat(curr["recorded_at"].replace("Z", "+00:00"))
                    hours = (c_dt - p_dt).total_seconds() / 3600.0
                except Exception:
                    hours = None
            if hours and hours > 0:
                lph_samples.append(delta_fuel / hours)

        avg_lph = round(sum(lph_samples) / len(lph_samples), 2) if lph_samples else None
        hours_remaining = None
        eta_empty = None
        if avg_lph and avg_lph > 0:
            hours_remaining = round(latest["fuel_level_l"] / avg_lph, 1)
            try:
                base = datetime.fromisoformat(latest["recorded_at"].replace("Z", "+00:00"))
                from datetime import timedelta
                eta_empty = (base + timedelta(hours=hours_remaining)).isoformat()
            except Exception:
                eta_empty = None

        # Kritikalitaet
        percent = round(latest["fuel_level_l"] / latest["tank_size_l"] * 100, 1) if latest.get("tank_size_l") else None
        criticality = "ok"
        if percent is not None and percent < 20:
            criticality = "critical"
        elif percent is not None and percent < 40:
            criticality = "warn"
        if hours_remaining is not None and hours_remaining < 12:
            criticality = "critical"
        elif hours_remaining is not None and hours_remaining < 24:
            criticality = "warn" if criticality == "ok" else criticality

        out.append({
            "asset_id": asset_id,
            "asset_label": latest.get("asset_label") or "",
            "tank_size_l": latest.get("tank_size_l"),
            "current_fuel_l": latest.get("fuel_level_l"),
            "current_percent": percent,
            "current_load_kw": latest.get("load_kw"),
            "current_runtime_h": latest.get("runtime_h"),
            "recorded_at": latest.get("recorded_at"),
            "avg_lph": avg_lph,
            "samples": len(lph_samples),
            "hours_remaining": hours_remaining,
            "eta_empty": eta_empty,
            "criticality": criticality,
            "readings_count": len(readings),
        })

    # Sortierung: kritisch zuerst (hours_remaining aufsteigend, None ans Ende)
    def _sort_key(x):
        hr = x.get("hours_remaining")
        return (0 if x["criticality"] == "critical" else (1 if x["criticality"] == "warn" else 2),
                hr if hr is not None else 1e9)
    out.sort(key=_sort_key)
    return {"forecast": out}


@router.get("/epirent/{order_pk}/tank-readings/export.csv")
async def export_tank_readings_csv(order_pk: int, user: dict = Depends(_auth_user)):
    rows = await _db.tank_readings.find(
        {"order_pk": order_pk}, {"_id": 0},
    ).sort("recorded_at", 1).to_list(5000)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([
        "recorded_at", "reading_type", "asset_label", "tank_size_l", "fuel_level_l", "fuel_percent",
        "load_kw", "runtime_h", "kwh_total", "latitude", "longitude", "comment", "created_by",
    ])
    for r in rows:
        writer.writerow([
            r.get("recorded_at", ""),
            r.get("reading_type", "normal"),
            r.get("asset_label", ""),
            r.get("tank_size_l", ""),
            r.get("fuel_level_l", ""),
            r.get("fuel_percent", ""),
            r.get("load_kw", "") if r.get("load_kw") is not None else "",
            r.get("runtime_h", "") if r.get("runtime_h") is not None else "",
            r.get("kwh_total", "") if r.get("kwh_total") is not None else "",
            r.get("latitude", "") if r.get("latitude") is not None else "",
            r.get("longitude", "") if r.get("longitude") is not None else "",
            (r.get("comment") or "").replace("\n", " "),
            r.get("created_by", ""),
        ])
    data = buf.getvalue().encode("utf-8-sig")  # BOM, damit Excel UTF-8 erkennt
    fname = f"tankstatus_{order_pk}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"{fname}\""},
    )


# Photo-Upload als separate Sub-Resource (max 4 MB)
@router.post("/epirent/{order_pk}/tank-readings/{reading_id}/photo")
async def upload_reading_photo(
    order_pk: int, reading_id: str, file: UploadFile = File(...), user: dict = Depends(_auth_user),
):
    reading = await _db.tank_readings.find_one({"id": reading_id, "order_pk": order_pk}, {"_id": 0, "id": 1})
    if not reading:
        raise HTTPException(status_code=404, detail="Reading nicht gefunden")
    content = await file.read()
    if len(content) > 4 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Foto zu gross (max 4 MB)")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Nur Bilddateien erlaubt")
    photo_id = str(uuid.uuid4())
    await _db.tank_reading_photos.insert_one({
        "id": photo_id,
        "reading_id": reading_id,
        "order_pk": order_pk,
        "content_type": file.content_type,
        "data_base64": base64.b64encode(content).decode("ascii"),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    })
    await _db.tank_readings.update_one(
        {"id": reading_id, "order_pk": order_pk},
        {"$set": {"photo_id": photo_id}},
    )
    return {"ok": True, "photo_id": photo_id}


@router.get("/epirent/{order_pk}/tank-readings/{reading_id}/photo")
async def get_reading_photo(
    order_pk: int, reading_id: str, user: dict = Depends(_auth_user),
):
    photo = await _db.tank_reading_photos.find_one(
        {"reading_id": reading_id, "order_pk": order_pk}, {"_id": 0},
    )
    if not photo:
        raise HTTPException(status_code=404, detail="Foto nicht gefunden")
    return Response(
        content=base64.b64decode(photo["data_base64"]),
        media_type=photo.get("content_type") or "image/jpeg",
    )
