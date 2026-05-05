from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import secrets
import string
import logging
import qrcode
import io

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["devices"])
security = HTTPBearer()

db = None
decode_jwt_token = None
fs = None


def init_device_routes(_db, _decode_jwt_token, _fs):
    global db, decode_jwt_token, fs
    db = _db
    decode_jwt_token = _decode_jwt_token
    fs = _fs


DEVICE_TYPES = ["stromerzeuger", "lichtmast", "messkoffer", "kirmeskiste", "verteiler"]


# ============== Models ==============

class DeviceCreate(BaseModel):
    device_type: str
    serial_number: str
    user_field: str = ""
    model: Optional[str] = None
    engine_manufacturer: Optional[str] = None
    engine_type: Optional[str] = None
    engine_number: Optional[str] = None
    generator_manufacturer: Optional[str] = None
    generator_type: Optional[str] = None
    generator_number: Optional[str] = None
    year_of_manufacture: Optional[int] = None
    power_output: Optional[str] = None
    controller: Optional[str] = None
    acquired_date: Optional[str] = None
    portal_link: Optional[str] = None
    notes: Optional[str] = None
    copy_from_device_id: Optional[str] = None
    # Pi connection fields for Messkoffer
    pi_hostname: Optional[str] = None
    pi_ip: Optional[str] = None
    pi_port: Optional[str] = None
    pi_username: Optional[str] = None
    pi_password: Optional[str] = None
    pi_notes: Optional[str] = None
    # MQTT Gateway fields for DSE890
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    dse_module_uid: Optional[str] = None
    # Kirmeskiste variant: "standard" (Live, alte Variante) | "8z" (8 Impulszähler, SIM7600)
    kirmeskiste_variant: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def coerce_optional_float(cls, v):
        if v is None or v == "":
            return None
        return float(v)

    @field_validator("year_of_manufacture", mode="before")
    @classmethod
    def coerce_optional_int(cls, v):
        if v is None or v == "":
            return None
        return int(v)


class DeviceUpdate(BaseModel):
    device_type: Optional[str] = None
    serial_number: Optional[str] = None
    user_field: Optional[str] = None
    model: Optional[str] = None
    engine_manufacturer: Optional[str] = None
    engine_type: Optional[str] = None
    engine_number: Optional[str] = None
    generator_manufacturer: Optional[str] = None
    generator_type: Optional[str] = None
    generator_number: Optional[str] = None
    year_of_manufacture: Optional[int] = None
    power_output: Optional[str] = None
    controller: Optional[str] = None
    acquired_date: Optional[str] = None
    portal_link: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    # Pi connection fields for Messkoffer
    pi_hostname: Optional[str] = None
    pi_ip: Optional[str] = None
    pi_port: Optional[str] = None
    pi_username: Optional[str] = None
    pi_password: Optional[str] = None
    pi_notes: Optional[str] = None
    # MQTT Gateway fields for DSE890
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    dse_module_uid: Optional[str] = None
    # Kirmeskiste variant: "standard" | "8z"
    kirmeskiste_variant: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def coerce_optional_float(cls, v):
        if v is None or v == "":
            return None
        return float(v)

    @field_validator("year_of_manufacture", mode="before")
    @classmethod
    def coerce_optional_int(cls, v):
        if v is None or v == "":
            return None
        return int(v)


PART_TYPES = [
    "Kraftstoffvorfilter", "Kraftstofffilter", "Ölfilter", "Keilriemen",
    "Umlenkrollen", "Wasserpumpe", "Luftfilter", "Motoröl",
]


class PartCreate(BaseModel):
    part_type: str
    part_number: Optional[str] = ""
    liters: Optional[float] = None
    notes: Optional[str] = ""


class PartUpdate(BaseModel):
    part_type: Optional[str] = None
    part_number: Optional[str] = None
    liters: Optional[float] = None
    notes: Optional[str] = None


# ============== Helpers ==============

async def get_authenticated_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_jwt_token(credentials.credentials)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    return user


async def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await get_authenticated_user(credentials)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin-Berechtigung erforderlich")
    return user


async def require_staff(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Admin or Mitarbeiter"""
    user = await get_authenticated_user(credentials)
    if user["role"] not in ("admin", "mitarbeiter"):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    return user


# ============== CRUD ==============

def generate_device_code():
    """Generate a unique 8-character alphanumeric device code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(8))




@router.post("")
async def create_device(data: DeviceCreate, admin: dict = Depends(require_staff)):
    if data.device_type not in DEVICE_TYPES:
        raise HTTPException(status_code=400, detail=f"Gerätetyp muss einer von {DEVICE_TYPES} sein")

    existing = await db.devices.find_one({"serial_number": data.serial_number}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Seriennummer bereits vorhanden")

    # Generate unique device code
    device_code = generate_device_code()
    while await db.devices.find_one({"device_code": device_code}):
        device_code = generate_device_code()

    device_doc = {
        "id": str(uuid.uuid4()),
        "device_code": device_code,
        "device_type": data.device_type,
        "serial_number": data.serial_number,
        "user_field": data.user_field,
        "model": data.model,
        "engine_manufacturer": data.engine_manufacturer,
        "engine_type": data.engine_type,
        "engine_number": data.engine_number,
        "generator_manufacturer": data.generator_manufacturer,
        "generator_type": data.generator_type,
        "generator_number": data.generator_number,
        "year_of_manufacture": data.year_of_manufacture,
        "operating_hours": None,
        "power_output": data.power_output,
        "controller": data.controller,
        "acquired_date": data.acquired_date,
        "portal_link": data.portal_link,
        "notes": data.notes,
        "status": "aktiv",
        # Pi connection fields for Messkoffer
        "pi_hostname": data.pi_hostname,
        "pi_ip": data.pi_ip,
        "pi_port": data.pi_port,
        "pi_username": data.pi_username,
        "pi_password": data.pi_password,
        "pi_notes": data.pi_notes,
        "mqtt_username": data.mqtt_username,
        "mqtt_password": data.mqtt_password,
        # Kirmeskiste-Variante: nur fuer device_type="kirmeskiste" relevant.
        # Defaults: bestehende ("standard") bleibt unangetastet, neue Pi-Generation = "8z".
        "kirmeskiste_variant": (data.kirmeskiste_variant or "standard") if data.device_type == "kirmeskiste" else None,
        "latitude": data.latitude,
        "longitude": data.longitude,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.devices.insert_one(device_doc)

    # Copy image, parts, and documents from source device if specified
    if data.copy_from_device_id:
        source = await db.devices.find_one({"id": data.copy_from_device_id})
        if source:
            # Copy image reference
            if source.get("image_gridfs_id"):
                await db.devices.update_one(
                    {"id": device_doc["id"]},
                    {"$set": {
                        "image_gridfs_id": source["image_gridfs_id"],
                        "image_content_type": source.get("image_content_type"),
                        "image_filename": source.get("image_filename"),
                    }}
                )
            # Copy parts
            source_parts = await db.device_parts.find({"device_id": data.copy_from_device_id}, {"_id": 0}).to_list(100)
            for part in source_parts:
                part["id"] = str(uuid.uuid4())
                part["device_id"] = device_doc["id"]
                part["created_at"] = datetime.now(timezone.utc).isoformat()
                await db.device_parts.insert_one(part)
            # Copy documents
            source_docs = await db.device_documents.find({"device_id": data.copy_from_device_id}, {"_id": 0}).to_list(100)
            for doc in source_docs:
                doc["id"] = str(uuid.uuid4())
                doc["device_id"] = device_doc["id"]
                doc["created_at"] = datetime.now(timezone.utc).isoformat()
                await db.device_documents.insert_one(doc)

    result = {k: v for k, v in device_doc.items() if k != "_id"}
    if "image_gridfs_id" in result and result["image_gridfs_id"]:
        result["image_gridfs_id"] = str(result["image_gridfs_id"])
    return result


@router.get("")
async def list_devices(user: dict = Depends(require_staff)):
    devices = await db.devices.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)

    # Collect serial numbers to look up generator last_seen
    serial_numbers = [d["serial_number"] for d in devices if d.get("device_type") in ("stromerzeuger", "lichtmast")]
    gen_last_seen = {}
    if serial_numbers:
        gens = await db.generators.find(
            {"serial_number": {"$in": serial_numbers}},
            {"_id": 0, "serial_number": 1, "last_seen": 1}
        ).to_list(2000)
        for g in gens:
            if g.get("last_seen"):
                gen_last_seen[g["serial_number"]] = g["last_seen"]

    # Kirmeskiste/Messkoffer/DSE: last_seen aus emu_data ableiten (Pi-Sync-Source-of-Truth)
    pi_device_ids = [d["id"] for d in devices
                     if d.get("device_type") in ("kirmeskiste", "messkoffer", "dse")]
    pi_last_seen = {}
    for did in pi_device_ids:
        latest = await db.emu_data.find_one(
            {"device_id": did}, {"_id": 0, "ts_utc": 1}, sort=[("ts_utc", -1)]
        )
        if latest and latest.get("ts_utc"):
            pi_last_seen[did] = latest["ts_utc"]

    # Batch-count documents per device instead of N+1
    device_ids = [d["id"] for d in devices]
    doc_counts = {}
    if device_ids:
        pipeline = [
            {"$match": {"device_id": {"$in": device_ids}}},
            {"$group": {"_id": "$device_id", "count": {"$sum": 1}}}
        ]
        doc_counts = {doc["_id"]: doc["count"] async for doc in db.device_documents.aggregate(pipeline)}

    for d in devices:
        d["document_count"] = doc_counts.get(d["id"], 0)
        # Convert ObjectId to string for JSON serialization
        if "image_gridfs_id" in d and d["image_gridfs_id"]:
            d["image_gridfs_id"] = str(d["image_gridfs_id"])
        # Generate device_code for legacy devices
        if not d.get("device_code"):
            code = generate_device_code()
            while await db.devices.find_one({"device_code": code}):
                code = generate_device_code()
            await db.devices.update_one({"id": d["id"]}, {"$set": {"device_code": code}})
            d["device_code"] = code
        # Enrich with generator last_seen for Stromerzeuger/Lichtmast
        if d.get("device_type") in ("stromerzeuger", "lichtmast") and not d.get("last_seen"):
            gen_ls = gen_last_seen.get(d.get("serial_number"))
            if gen_ls:
                d["last_seen"] = gen_ls
        # Enrich with Pi-sync last_seen fuer Kirmeskiste/Messkoffer/DSE
        if d.get("device_type") in ("kirmeskiste", "messkoffer", "dse"):
            pi_ls = pi_last_seen.get(d["id"])
            if pi_ls and (not d.get("last_seen") or pi_ls > d["last_seen"]):
                d["last_seen"] = pi_ls
    return devices


@router.get("/{device_id}")
async def get_device(device_id: str, user: dict = Depends(require_staff)):
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")
    docs = await db.device_documents.find({"device_id": device_id}, {"_id": 0}).to_list(100)
    for d in docs:
        if "gridfs_id" in d:
            d["gridfs_id"] = str(d["gridfs_id"])
    device["documents"] = docs
    # Convert ObjectId to string for JSON serialization
    if "image_gridfs_id" in device and device["image_gridfs_id"]:
        device["image_gridfs_id"] = str(device["image_gridfs_id"])
    return device


@router.put("/{device_id}")
async def update_device(device_id: str, data: DeviceUpdate, user: dict = Depends(require_staff)):
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    update_data = {}
    for k, v in data.dict(exclude_unset=True).items():
        if v is not None:
            update_data[k] = v

    # Validate status
    if "status" in update_data and update_data["status"] not in ("aktiv", "ausser_betrieb"):
        raise HTTPException(status_code=400, detail="Status muss 'aktiv' oder 'ausser_betrieb' sein")

    # Check serial number uniqueness
    if "serial_number" in update_data and update_data["serial_number"] != device["serial_number"]:
        existing = await db.devices.find_one({"serial_number": update_data["serial_number"]}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=400, detail="Seriennummer bereits vorhanden")

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.devices.update_one({"id": device_id}, {"$set": update_data})

    # Sync latitude/longitude to linked generator (if Stromerzeuger/Lichtmast)
    if ("latitude" in update_data or "longitude" in update_data) and device.get("device_type") in ("stromerzeuger", "lichtmast"):
        gen_update = {}
        new_lat = update_data.get("latitude", device.get("latitude"))
        new_lng = update_data.get("longitude", device.get("longitude"))
        if new_lat is not None:
            gen_update["latitude"] = new_lat
        if new_lng is not None:
            gen_update["longitude"] = new_lng
        if gen_update:
            serial = update_data.get("serial_number", device.get("serial_number"))
            await db.generators.update_many(
                {"serial_number": serial},
                {"$set": gen_update}
            )

    updated = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if "image_gridfs_id" in updated and updated["image_gridfs_id"]:
        updated["image_gridfs_id"] = str(updated["image_gridfs_id"])
    return updated


@router.delete("/{device_id}")
async def delete_device(device_id: str, admin: dict = Depends(require_admin)):
    result = await db.devices.delete_one({"id": device_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")
    docs = await db.device_documents.find({"device_id": device_id}).to_list(100)
    for doc in docs:
        if doc.get("gridfs_id"):
            try:
                await fs.delete(doc["gridfs_id"])
            except Exception:
                pass
    await db.device_documents.delete_many({"device_id": device_id})
    await db.device_parts.delete_many({"device_id": device_id})

    # Delete associated service plan and its maintenance entries
    plan = await db.service_plans.find_one({"device_id": device_id})
    if plan:
        await db.maintenance_entries.delete_many({"service_plan_id": plan["id"]})
        await db.service_plans.delete_one({"device_id": device_id})

    return {"message": "Gerät gelöscht"}


# ============== Copy (Admin only) ==============

@router.post("/{device_id}/copy")
async def copy_device(device_id: str, admin: dict = Depends(require_staff)):
    source = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    new_device = {**source}
    new_device["id"] = str(uuid.uuid4())
    new_device["serial_number"] = f"KOPIE-{source['serial_number']}"
    new_device["engine_number"] = ""
    new_device["generator_number"] = ""
    new_device["operating_hours"] = None
    new_device["status"] = "aktiv"
    new_device["created_at"] = datetime.now(timezone.utc).isoformat()
    new_device["updated_at"] = datetime.now(timezone.utc).isoformat()
    # Generate new unique device code
    device_code = generate_device_code()
    while await db.devices.find_one({"device_code": device_code}):
        device_code = generate_device_code()
    new_device["device_code"] = device_code
    # Keep image_gridfs_id from source so copied device has same image

    await db.devices.insert_one(new_device)
    result = {k: v for k, v in new_device.items() if k != "_id"}
    if "image_gridfs_id" in result and result["image_gridfs_id"]:
        result["image_gridfs_id"] = str(result["image_gridfs_id"])

    # Copy parts from source device
    source_parts = await db.device_parts.find({"device_id": device_id}, {"_id": 0}).to_list(100)
    for part in source_parts:
        part["id"] = str(uuid.uuid4())
        part["device_id"] = new_device["id"]
        part["created_at"] = datetime.now(timezone.utc).isoformat()
        await db.device_parts.insert_one(part)

    return result


# ============== Status change (Mitarbeiter) ==============

@router.post("/{device_id}/ausser-betrieb")
async def set_out_of_service(device_id: str, user: dict = Depends(require_staff)):
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    new_status = "aktiv" if device.get("status") == "ausser_betrieb" else "ausser_betrieb"
    await db.devices.update_one(
        {"id": device_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": f"Status geändert auf: {new_status}", "status": new_status}


# ============== Document Management ==============

@router.post("/{device_id}/documents")
async def upload_document(device_id: str, file: UploadFile = File(...), user: dict = Depends(require_staff)):
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")
    content = await file.read()
    gridfs_id = await fs.upload_from_stream(file.filename, content)
    doc_record = {
        "id": str(uuid.uuid4()),
        "device_id": device_id,
        "filename": file.filename,
        "content_type": file.content_type or "application/octet-stream",
        "size": len(content),
        "gridfs_id": gridfs_id,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.device_documents.insert_one(doc_record)
    result = {k: v for k, v in doc_record.items() if k != "_id"}
    result["gridfs_id"] = str(result["gridfs_id"])
    return result


@router.get("/{device_id}/documents")
async def list_documents(device_id: str, user: dict = Depends(require_staff)):
    docs = await db.device_documents.find({"device_id": device_id}, {"_id": 0}).to_list(100)
    for d in docs:
        if "gridfs_id" in d:
            d["gridfs_id"] = str(d["gridfs_id"])
    return docs


@router.delete("/{device_id}/documents/{doc_id}")
async def delete_document(device_id: str, doc_id: str, user: dict = Depends(require_staff)):
    doc = await db.device_documents.find_one({"id": doc_id, "device_id": device_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if doc.get("gridfs_id"):
        try:
            await fs.delete(doc["gridfs_id"])
        except Exception:
            pass
    await db.device_documents.delete_one({"id": doc_id})
    return {"message": "Dokument gelöscht"}


@router.get("/{device_id}/documents/{doc_id}/download")
async def download_document(device_id: str, doc_id: str, user: dict = Depends(get_authenticated_user)):
    doc = await db.device_documents.find_one({"id": doc_id, "device_id": device_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    if not doc.get("gridfs_id"):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    grid_out = await fs.open_download_stream(doc["gridfs_id"])
    content = await grid_out.read()
    content_type = doc.get("content_type", "application/octet-stream")
    filename = doc.get("filename", "dokument")
    return Response(content=content, media_type=content_type, headers={"Content-Disposition": f'inline; filename="{filename}"'})


# ============== Device Image ==============

@router.post("/{device_id}/image")
async def upload_device_image(device_id: str, file: UploadFile = File(...), user: dict = Depends(require_staff)):
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Bild zu groß (max 10MB)")

    # Delete old image if exists
    old_gridfs_id = device.get("image_gridfs_id")
    if old_gridfs_id:
        try:
            await fs.delete(old_gridfs_id)
        except Exception:
            pass

    gridfs_id = await fs.upload_from_stream(file.filename, content)
    await db.devices.update_one({"id": device_id}, {"$set": {
        "image_gridfs_id": gridfs_id,
        "image_filename": file.filename,
        "image_content_type": file.content_type or "image/jpeg",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})

    return {"message": "Bild hochgeladen", "image_gridfs_id": str(gridfs_id)}


@router.get("/{device_id}/image")
async def get_device_image(device_id: str, thumbnail: int = 0, size: int = 200):
    from fastapi.responses import StreamingResponse, Response
    import io
    device = await db.devices.find_one({"id": device_id})
    if not device or not device.get("image_gridfs_id"):
        raise HTTPException(status_code=404, detail="Kein Bild vorhanden")

    grid_out = await fs.open_download_stream(device["image_gridfs_id"])
    content = await grid_out.read()

    # Thumbnail for list views
    if thumbnail:
        from utils.thumbnails import make_thumbnail_from_bytes
        tdata = make_thumbnail_from_bytes(content, size=min(max(int(size), 16), 1024))
        if tdata is not None:
            return Response(
                content=tdata,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400", "Content-Disposition": 'inline; filename="thumb.jpg"'},
            )

    return StreamingResponse(
        io.BytesIO(content),
        media_type=device.get("image_content_type", "image/jpeg"),
        headers={"Content-Disposition": f'inline; filename="{device.get("image_filename", "device.jpg")}"'}
    )


# ============== QR Code ==============

@router.get("/{device_id}/qrcode")
async def get_device_qrcode(device_id: str):
    device = await db.devices.find_one({"id": device_id}, {"_id": 0, "device_code": 1, "serial_number": 1})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    code = device.get("device_code")
    if not code:
        # Generate code for legacy devices
        code = generate_device_code()
        while await db.devices.find_one({"device_code": code}):
            code = generate_device_code()
        await db.devices.update_one({"id": device_id}, {"$set": {"device_code": code}})

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")


@router.get("/search/by-code/{code}")
async def search_by_code(code: str, user: dict = Depends(get_authenticated_user)):
    device = await db.devices.find_one({"device_code": code.upper().strip()}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Kein Gerät mit diesem Code gefunden")
    if "image_gridfs_id" in device and device["image_gridfs_id"]:
        device["image_gridfs_id"] = str(device["image_gridfs_id"])
    return device


# ============== Parts (Ersatzteile) Management ==============

@router.get("/{device_id}/parts")
async def list_parts(device_id: str, user: dict = Depends(require_staff)):
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")
    parts = await db.device_parts.find({"device_id": device_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
    return parts


@router.post("/{device_id}/parts")
async def add_part(device_id: str, data: PartCreate, user: dict = Depends(require_staff)):
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    part_doc = {
        "id": str(uuid.uuid4()),
        "device_id": device_id,
        "part_type": data.part_type,
        "part_number": data.part_number or "",
        "liters": data.liters,
        "notes": data.notes or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.device_parts.insert_one(part_doc)
    result = {k: v for k, v in part_doc.items() if k != "_id"}
    return result


@router.put("/parts/{part_id}")
async def update_part(part_id: str, data: PartUpdate, user: dict = Depends(require_staff)):
    part = await db.device_parts.find_one({"id": part_id}, {"_id": 0})
    if not part:
        raise HTTPException(status_code=404, detail="Ersatzteil nicht gefunden")

    update_data = {}
    if data.part_type is not None:
        update_data["part_type"] = data.part_type
    if data.part_number is not None:
        update_data["part_number"] = data.part_number
    if data.liters is not None:
        update_data["liters"] = data.liters
    if data.notes is not None:
        update_data["notes"] = data.notes

    if update_data:
        await db.device_parts.update_one({"id": part_id}, {"$set": update_data})

    updated = await db.device_parts.find_one({"id": part_id}, {"_id": 0})
    return updated


@router.delete("/parts/{part_id}")
async def delete_part(part_id: str, user: dict = Depends(require_staff)):
    result = await db.device_parts.delete_one({"id": part_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ersatzteil nicht gefunden")
    return {"message": "Ersatzteil gelöscht"}


@router.get("/parts/types")
async def get_part_types(user: dict = Depends(require_staff)):
    return {"types": PART_TYPES}


# ============== Quick Info (expandable row) ==============

@router.get("/{device_id}/quick-info")
async def get_device_quick_info(device_id: str, user: dict = Depends(require_staff)):
    """Get quick info for expandable row: last_seen + latest meter readings."""
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    result = {
        "device_id": device_id,
        "last_seen": device.get("last_seen"),
        "device_type": device.get("device_type"),
        "kirmeskiste_variant": device.get("kirmeskiste_variant"),
        "pi_health": device.get("pi_health"),
        "readings": [],
    }

    dtype = device.get("device_type", "")

    # Pi-Status aus OTA-Checkin als Fallback (fuer Geraete ohne authentifizierten
    # /pi-health Push, z.B. Tankwagen). Match: explizit verlinkte device.pi_id ODER
    # einziger aktuell aktiver Checkin desselben Geraetetyps.
    if not result["pi_health"]:
        ota_match = None
        linked_pi_id = device.get("pi_id")
        if linked_pi_id:
            ota_match = await db.ota_checkins.find_one({"device_id": linked_pi_id}, {"_id": 0})
        elif dtype in ("tankwagen", "kirmeskiste"):
            ota_type = "tankwagen" if dtype == "tankwagen" else "kirmeskiste"
            # Nur Checkins der letzten 30 Minuten zaehlen als "aktiv"
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
            cursor = db.ota_checkins.find(
                {"device_type": ota_type, "last_seen": {"$gte": cutoff}},
                {"_id": 0},
            ).sort("last_seen", -1).limit(2)
            active = await cursor.to_list(2)
            if len(active) == 1:
                # Genau ein aktiver Pi dieses Typs -> automatisch zuordnen
                ota_match = active[0]
            elif len(active) > 1:
                # Mehrere aktive Pis -> Admin muss device.pi_id setzen,
                # fallback zum juengsten Checkin damit zumindest etwas angezeigt wird
                # (markiert als ambiguous fuer das UI, optional)
                ota_match = None
        if ota_match:
            result["pi_health"] = {
                "lte_ip": ota_match.get("lte_ip"),
                "lte_csq": ota_match.get("lte_csq"),
                "lte_signal_dbm": ota_match.get("lte_signal_dbm"),
                "lte_operator": ota_match.get("lte_operator"),
                "lte_act": ota_match.get("lte_act"),
                "script_version": ota_match.get("current_version"),
                "hostname": ota_match.get("hostname"),
                "pi_id": ota_match.get("device_id"),
                "received_at": ota_match.get("last_seen"),
            }
            # GPS optional ergaenzen, falls nicht aus anderer Quelle gesetzt
            if ota_match.get("gps_lat") is not None and ota_match.get("gps_lon") is not None:
                result.setdefault("gps", {
                    "lat": ota_match["gps_lat"],
                    "lon": ota_match["gps_lon"],
                    "timestamp": ota_match.get("last_seen"),
                })

    if dtype in ("stromerzeuger", "lichtmast"):
        # Get latest generator telemetry (from MQTT)
        gen = await db.generators.find_one({"serial_number": device.get("serial_number")}, {"_id": 0})
        if gen:
            result["last_seen"] = result["last_seen"] or gen.get("last_seen")
            latest = await db.generator_telemetry.find_one(
                {"generator_id": gen.get("id")}, {"_id": 0},
                sort=[("timestamp", -1)]
            )
            if latest:
                readings = []
                if latest.get("voltage_l1") is not None:
                    readings.append({"label": "Spannung L1", "value": f"{latest['voltage_l1']:.1f} V"})
                if latest.get("voltage_l2") is not None:
                    readings.append({"label": "Spannung L2", "value": f"{latest['voltage_l2']:.1f} V"})
                if latest.get("voltage_l3") is not None:
                    readings.append({"label": "Spannung L3", "value": f"{latest['voltage_l3']:.1f} V"})
                if latest.get("current_l1") is not None:
                    readings.append({"label": "Strom L1", "value": f"{latest['current_l1']:.1f} A"})
                if latest.get("current_l2") is not None:
                    readings.append({"label": "Strom L2", "value": f"{latest['current_l2']:.1f} A"})
                if latest.get("current_l3") is not None:
                    readings.append({"label": "Strom L3", "value": f"{latest['current_l3']:.1f} A"})
                if latest.get("power_kw") is not None:
                    readings.append({"label": "Leistung", "value": f"{latest['power_kw']:.1f} kW"})
                if latest.get("frequency") is not None:
                    readings.append({"label": "Frequenz", "value": f"{latest['frequency']:.1f} Hz"})
                if latest.get("rpm") is not None:
                    readings.append({"label": "Drehzahl", "value": f"{int(latest['rpm'])} RPM"})
                if latest.get("fuel_level") is not None:
                    readings.append({"label": "Kraftstoff", "value": f"{latest['fuel_level']}%"})
                if latest.get("coolant_temp") is not None:
                    readings.append({"label": "Kühlmittel", "value": f"{latest['coolant_temp']} °C"})
                if latest.get("battery_voltage") is not None:
                    readings.append({"label": "Batterie", "value": f"{latest['battery_voltage']:.1f} V"})
                if latest.get("hours_run") is not None:
                    readings.append({"label": "Betriebsstunden", "value": f"{latest['hours_run']:.1f} h"})
                result["readings"] = readings
                result["telemetry_timestamp"] = latest.get("timestamp")

    elif dtype in ("messkoffer", "kirmeskiste", "verteiler"):
        # Sortiere Zaehler nach hat_channel (Kirmeskiste 8Z), dann nach Name
        meters = await db.emu_meters.find({"device_id": device_id}, {"_id": 0}).to_list(20)
        meters.sort(key=lambda m: (m.get("hat_channel") or 99, m.get("meter_name") or ""))
        readings = []
        for meter in meters:
            latest = await db.emu_data.find_one(
                {"device_id": device_id, "meter_id": meter["id"]},
                {"_id": 0},
                sort=[("ts_utc", -1)]
            )
            kwh_offset = float(meter.get("kwh_offset") or 0.0)
            entry = {
                "label": meter.get("meter_name") or meter.get("meter_ip", "Zähler"),
                "value": "Keine Daten",
                "meter_id": meter["id"],
                "kwh_offset": kwh_offset,
            }
            if latest:
                # Telemetrie vorhanden: zeige max(E_imp_kWh, kwh_offset),
                # damit der Anfangsstand sichtbar bleibt, falls der Pi
                # ihn noch nicht uebernommen hat.
                e_imp = latest.get("E_imp_kWh")
                p_sum = latest.get("P_sum_kW")
                effective_kwh = e_imp if (e_imp is not None and e_imp >= kwh_offset) else kwh_offset
                parts = []
                if effective_kwh is not None:
                    parts.append(f"{effective_kwh:.2f} kWh")
                if p_sum is not None:
                    parts.append(f"{p_sum:.2f} kW")
                entry["value"] = " | ".join(parts) if parts else "Daten vorhanden"
                entry["timestamp"] = latest.get("ts_utc")
                # Hinweis falls Pi den Offset noch nicht uebernommen hat
                if kwh_offset > 0 and e_imp is not None and e_imp < kwh_offset:
                    entry["pending_offset"] = True
            elif kwh_offset > 0:
                # Noch keine Telemetrie: Anfangsstand als Vorschau zeigen
                entry["value"] = f"{kwh_offset:.2f} kWh (Anfangsstand)"
                entry["pending_offset"] = True
            readings.append(entry)
        result["readings"] = readings

        # GPS: letzte Position aus emu_data (Messkoffer/Kirmeskiste senden gps_lat/gps_lon)
        gps_doc = await db.emu_data.find_one(
            {"device_id": device_id, "gps_lat": {"$gt": 0}, "gps_lon": {"$ne": None}},
            {"_id": 0, "gps_lat": 1, "gps_lon": 1, "ts_utc": 1},
            sort=[("ts_utc", -1)]
        )
        if gps_doc and gps_doc.get("gps_lat") and gps_doc.get("gps_lon"):
            result["gps"] = {
                "lat": gps_doc["gps_lat"],
                "lon": gps_doc["gps_lon"],
                "timestamp": gps_doc.get("ts_utc"),
            }

    return result


@router.get("/{device_id}/meters/{meter_id}/diagnostics")
async def get_meter_diagnostics(
    device_id: str, meter_id: str,
    limit: int = 50,
    date_from: str = None, date_to: str = None,
    user: dict = Depends(require_staff),
):
    """Get raw measurements for a specific meter with optional date range."""
    meter = await db.emu_meters.find_one({"id": meter_id, "device_id": device_id}, {"_id": 0})
    if not meter:
        raise HTTPException(status_code=404, detail="Zähler nicht gefunden")

    device = await db.devices.find_one({"id": device_id}, {"_id": 0, "id": 1, "name": 1})

    query = {"device_id": device_id, "meter_id": meter_id}
    if date_from or date_to:
        ts_filter = {}
        if date_from:
            ts_filter["$gte"] = date_from + "T00:00:00.000Z" if "T" not in date_from else date_from
        if date_to:
            ts_filter["$lte"] = date_to + "T23:59:59.999Z" if "T" not in date_to else date_to
        if ts_filter:
            query["ts_utc"] = ts_filter

    projection = {
        "_id": 0, "ts_utc": 1, "P_sum_kW": 1,
        "U_L1": 1, "U_L2": 1, "U_L3": 1,
        "I_L1": 1, "I_L2": 1, "I_L3": 1,
        "I_sum": 1, "F_Hz": 1, "E_imp_kWh": 1, "cosphi": 1,
    }

    docs = await db.emu_data.find(
        query, projection, sort=[("ts_utc", -1)],
    ).to_list(min(limit, 500))

    return {
        "meter_id": meter_id,
        "meter_name": meter.get("meter_name") or meter.get("meter_ip", "Zähler"),
        "device_id": device_id,
        "device_name": device.get("name", "") if device else meter.get("device_name", ""),
        "count": len(docs),
        "data": docs,
    }


@router.get("/{device_id}/meters/{meter_id}/history")
async def get_meter_assignment_history(device_id: str, meter_id: str, user: dict = Depends(require_staff)):
    """Get assignment history: which events/customers this meter was linked to."""
    meter = await db.emu_meters.find_one({"id": meter_id, "device_id": device_id}, {"_id": 0})
    if not meter:
        raise HTTPException(status_code=404, detail="Zähler nicht gefunden")

    # Find all kirmes_signups that reference this meter (by device+meter OR meter alone)
    signups_by_device = await db.kirmes_signups.find(
        {"emu_device_id": device_id, "emu_meter_id": meter_id},
        {"_id": 0, "id": 1, "event_id": 1, "schausteller_id": 1,
         "fahrgeschaeft": 1, "platznummer": 1, "kwh_einbau": 1,
         "kwh_ausbau": 1, "kwh_used": 1, "created_at": 1, "invoice_number": 1},
    ).to_list(100)

    # Also search by meter_id alone (meter might have been on a different device before)
    signups_by_meter = await db.kirmes_signups.find(
        {"emu_meter_id": meter_id, "emu_device_id": {"$ne": device_id}},
        {"_id": 0, "id": 1, "event_id": 1, "schausteller_id": 1,
         "fahrgeschaeft": 1, "platznummer": 1, "kwh_einbau": 1,
         "kwh_ausbau": 1, "kwh_used": 1, "created_at": 1, "invoice_number": 1},
    ).to_list(100)

    # Also check archived/unlinked signups that previously had this meter
    unlinked = await db.kirmes_signups.find(
        {"previous_emu_meter_id": meter_id},
        {"_id": 0, "id": 1, "event_id": 1, "schausteller_id": 1,
         "fahrgeschaeft": 1, "platznummer": 1, "kwh_einbau": 1,
         "kwh_ausbau": 1, "kwh_used": 1, "created_at": 1, "invoice_number": 1},
    ).to_list(100)

    current_ids = {s["id"] for s in signups_by_device}
    all_signups = {s["id"]: s for s in signups_by_device + signups_by_meter + unlinked}.values()

    # Enrich with event names and schausteller names
    event_ids = list({s["event_id"] for s in all_signups if s.get("event_id")})
    schausteller_ids = list({s["schausteller_id"] for s in all_signups if s.get("schausteller_id")})

    events_map = {}
    if event_ids:
        events = await db.kirmes_events.find({"id": {"$in": event_ids}}, {"_id": 0, "id": 1, "name": 1, "start_date": 1, "end_date": 1}).to_list(100)
        events_map = {e["id"]: e for e in events}

    schausteller_map = {}
    if schausteller_ids:
        schausteller = await db.schausteller.find({"id": {"$in": schausteller_ids}}, {"_id": 0, "id": 1, "firma": 1, "name": 1}).to_list(100)
        schausteller_map = {s["id"]: s for s in schausteller}

    history = []
    for s in all_signups:
        ev = events_map.get(s.get("event_id"), {})
        sch = schausteller_map.get(s.get("schausteller_id"), {})
        history.append({
            "signup_id": s["id"],
            "event_name": ev.get("name", "–"),
            "event_start": ev.get("start_date"),
            "event_end": ev.get("end_date"),
            "firma": sch.get("firma", "–"),
            "kunde": sch.get("name", "–"),
            "fahrgeschaeft": s.get("fahrgeschaeft", "–"),
            "platznummer": s.get("platznummer", "–"),
            "kwh_einbau": s.get("kwh_einbau"),
            "kwh_ausbau": s.get("kwh_ausbau"),
            "kwh_used": s.get("kwh_used"),
            "invoice_number": s.get("invoice_number"),
            "created_at": s.get("created_at"),
            "is_current": s["id"] in current_ids,
        })

    history.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    return {
        "meter_id": meter_id,
        "meter_name": meter.get("meter_name") or meter.get("meter_ip", "Zähler"),
        "assignments": history,
    }

@router.get("/stats/overview")
async def device_stats(user: dict = Depends(require_staff)):
    total = await db.devices.count_documents({})
    active = await db.devices.count_documents({"status": {"$ne": "ausser_betrieb"}})
    out_of_service = await db.devices.count_documents({"status": "ausser_betrieb"})
    by_type = {}
    for dt in DEVICE_TYPES:
        by_type[dt] = await db.devices.count_documents({"device_type": dt})
    return {"total": total, "active": active, "out_of_service": out_of_service, "by_type": by_type}
