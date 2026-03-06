from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["devices"])
security = HTTPBearer()

db = None
decode_jwt_token = None
fs = None  # GridFS


def init_device_routes(_db, _decode_jwt_token, _fs):
    global db, decode_jwt_token, fs
    db = _db
    decode_jwt_token = _decode_jwt_token
    fs = _fs


DEVICE_TYPES = ["stromerzeuger", "lichtmast", "messkoffer", "kirmeskiste"]


# ============== Models ==============

class DeviceCreate(BaseModel):
    device_type: str  # stromerzeuger, lichtmast, messkoffer, kirmeskiste
    serial_number: str
    user_field: str = ""  # free text searchable field
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Stromerzeuger + Lichtmast fields
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
    last_maintenance: Optional[str] = None
    next_maintenance: Optional[str] = None
    notes: Optional[str] = None


class DeviceUpdate(BaseModel):
    device_type: Optional[str] = None
    serial_number: Optional[str] = None
    user_field: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
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
    last_maintenance: Optional[str] = None
    next_maintenance: Optional[str] = None
    notes: Optional[str] = None


# ============== Helpers ==============

async def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_jwt_token(credentials.credentials)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin-Berechtigung erforderlich")
    return user


# ============== CRUD ==============

@router.post("")
async def create_device(data: DeviceCreate, admin: dict = Depends(require_admin)):
    if data.device_type not in DEVICE_TYPES:
        raise HTTPException(status_code=400, detail=f"Gerätetyp muss einer von {DEVICE_TYPES} sein")

    existing = await db.devices.find_one({"serial_number": data.serial_number}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Seriennummer bereits vorhanden")

    device_doc = {
        "id": str(uuid.uuid4()),
        "device_type": data.device_type,
        "serial_number": data.serial_number,
        "user_field": data.user_field,
        "latitude": data.latitude,
        "longitude": data.longitude,
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
        "last_maintenance": data.last_maintenance,
        "next_maintenance": data.next_maintenance,
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.devices.insert_one(device_doc)
    result = {k: v for k, v in device_doc.items() if k != "_id"}
    return result


@router.get("")
async def list_devices(admin: dict = Depends(require_admin)):
    devices = await db.devices.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)

    # Attach document count for each device
    for d in devices:
        doc_count = await db.device_documents.count_documents({"device_id": d["id"]})
        d["document_count"] = doc_count

    return devices


@router.get("/{device_id}")
async def get_device(device_id: str, admin: dict = Depends(require_admin)):
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    docs = await db.device_documents.find({"device_id": device_id}, {"_id": 0}).to_list(100)
    # Convert gridfs_id ObjectId to string
    for d in docs:
        if "gridfs_id" in d:
            d["gridfs_id"] = str(d["gridfs_id"])
    device["documents"] = docs

    return device


@router.put("/{device_id}")
async def update_device(device_id: str, data: DeviceUpdate, admin: dict = Depends(require_admin)):
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    update_data = {}
    for k, v in data.dict(exclude_unset=True).items():
        if v is not None:
            update_data[k] = v

    # Check serial number uniqueness if changed
    if "serial_number" in update_data and update_data["serial_number"] != device["serial_number"]:
        existing = await db.devices.find_one({"serial_number": update_data["serial_number"]}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=400, detail="Seriennummer bereits vorhanden")

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.devices.update_one({"id": device_id}, {"$set": update_data})

    updated = await db.devices.find_one({"id": device_id}, {"_id": 0})
    return updated


@router.delete("/{device_id}")
async def delete_device(device_id: str, admin: dict = Depends(require_admin)):
    result = await db.devices.delete_one({"id": device_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    # Delete associated documents from GridFS
    docs = await db.device_documents.find({"device_id": device_id}).to_list(100)
    for doc in docs:
        if doc.get("gridfs_id"):
            try:
                await fs.delete(doc["gridfs_id"])
            except Exception:
                pass
    await db.device_documents.delete_many({"device_id": device_id})

    return {"message": "Gerät gelöscht"}


# ============== Copy Device ==============

@router.post("/{device_id}/copy")
async def copy_device(device_id: str, admin: dict = Depends(require_admin)):
    source = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    new_device = {**source}
    new_device["id"] = str(uuid.uuid4())
    new_device["serial_number"] = f"KOPIE-{source['serial_number']}"
    new_device["engine_number"] = ""
    new_device["generator_number"] = ""
    new_device["operating_hours"] = None
    new_device["created_at"] = datetime.now(timezone.utc).isoformat()
    new_device["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.devices.insert_one(new_device)
    result = {k: v for k, v in new_device.items() if k != "_id"}
    return result


# ============== Document Management ==============

@router.post("/{device_id}/documents")
async def upload_document(
    device_id: str,
    file: UploadFile = File(...),
    admin: dict = Depends(require_admin),
):
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
    # Convert ObjectId to string
    result["gridfs_id"] = str(result["gridfs_id"])
    return result


@router.get("/{device_id}/documents")
async def list_documents(device_id: str, admin: dict = Depends(require_admin)):
    docs = await db.device_documents.find({"device_id": device_id}, {"_id": 0}).to_list(100)
    for d in docs:
        if "gridfs_id" in d:
            d["gridfs_id"] = str(d["gridfs_id"])
    return docs


@router.delete("/{device_id}/documents/{doc_id}")
async def delete_document(device_id: str, doc_id: str, admin: dict = Depends(require_admin)):
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


# ============== Stats ==============

@router.get("/stats/overview")
async def device_stats(admin: dict = Depends(require_admin)):
    total = await db.devices.count_documents({})
    by_type = {}
    for dt in DEVICE_TYPES:
        by_type[dt] = await db.devices.count_documents({"device_type": dt})

    return {"total": total, "by_type": by_type}
