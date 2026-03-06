from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging
import io

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/serviceplan", tags=["serviceplan"])
security = HTTPBearer()

db = None
decode_jwt_token = None
fs = None


def init_serviceplan_routes(_db, _decode_jwt_token, _fs=None):
    global db, decode_jwt_token, fs
    db = _db
    decode_jwt_token = _decode_jwt_token
    fs = _fs


# ============== Models ==============

class ServicePlanCreate(BaseModel):
    device_id: str
    current_hours: Optional[float] = 0
    interval_hours: Optional[int] = 500
    interval_months: Optional[int] = 12
    tasks: List[str] = []
    notes: Optional[str] = ""


class ServicePlanUpdate(BaseModel):
    current_hours: Optional[float] = None
    interval_hours: Optional[int] = None
    interval_months: Optional[int] = None
    tasks: Optional[List[str]] = None
    notes: Optional[str] = None


class MaintenanceEntryCreate(BaseModel):
    performed_by: str
    performed_at: str
    hours_at_service: Optional[float] = None
    next_maintenance_months: Optional[int] = None
    next_maintenance_hours: Optional[int] = None
    # Legacy fields for backwards compat
    next_maintenance_mode: Optional[str] = None
    next_maintenance_value: Optional[int] = None
    checklist_data: Optional[dict] = None
    measurements: Optional[dict] = None
    load_test: Optional[list] = None
    ats_test: Optional[dict] = None
    diagnosis: Optional[dict] = None
    notes: Optional[str] = ""
    remarks: Optional[str] = ""


# ============== Helpers ==============

async def get_authenticated_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_jwt_token(credentials.credentials)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    return user


async def require_staff(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await get_authenticated_user(credentials)
    if user["role"] not in ("admin", "mitarbeiter"):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    return user


async def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await get_authenticated_user(credentials)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin-Berechtigung erforderlich")
    return user


# ============== Service Plan CRUD ==============

@router.get("")
async def list_service_plans(user: dict = Depends(require_staff)):
    plans = await db.service_plans.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)

    # Enrich with device info and latest maintenance
    for plan in plans:
        device = await db.devices.find_one({"id": plan["device_id"]}, {"_id": 0})
        if device:
            plan["device_serial"] = device.get("serial_number", "")
            plan["device_type"] = device.get("device_type", "")
            plan["device_model"] = device.get("model", "")
            plan["device_user_field"] = device.get("user_field", "")
            plan["device_status"] = device.get("status", "aktiv")

        # Get latest maintenance entry
        latest_entry = await db.maintenance_entries.find_one(
            {"service_plan_id": plan["id"]},
            {"_id": 0},
            sort=[("performed_at", -1)]
        )
        plan["latest_entry"] = latest_entry

        # Count entries
        entry_count = await db.maintenance_entries.count_documents({"service_plan_id": plan["id"]})
        plan["entry_count"] = entry_count

    return plans


@router.post("")
async def create_service_plan(data: ServicePlanCreate, user: dict = Depends(require_staff)):
    # Verify device exists
    device = await db.devices.find_one({"id": data.device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    # Check if plan already exists for this device
    existing = await db.service_plans.find_one({"device_id": data.device_id}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Für dieses Gerät existiert bereits ein Serviceplan")

    plan_doc = {
        "id": str(uuid.uuid4()),
        "device_id": data.device_id,
        "current_hours": data.current_hours or 0,
        "interval_hours": data.interval_hours,
        "interval_months": data.interval_months,
        "tasks": data.tasks,
        "notes": data.notes or "",
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.service_plans.insert_one(plan_doc)
    result = {k: v for k, v in plan_doc.items() if k != "_id"}
    return result


@router.get("/{plan_id}")
async def get_service_plan(plan_id: str, user: dict = Depends(require_staff)):
    plan = await db.service_plans.find_one({"id": plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Serviceplan nicht gefunden")

    # Enrich with device info
    device = await db.devices.find_one({"id": plan["device_id"]}, {"_id": 0})
    if device:
        plan["device_serial"] = device.get("serial_number", "")
        plan["device_type"] = device.get("device_type", "")
        plan["device_model"] = device.get("model", "")
        plan["device_user_field"] = device.get("user_field", "")
        plan["device_status"] = device.get("status", "aktiv")

    # Get all maintenance entries
    entries = await db.maintenance_entries.find(
        {"service_plan_id": plan_id}, {"_id": 0}
    ).sort([("performed_at", -1), ("created_at", -1)]).to_list(500)
    plan["entries"] = entries

    return plan


@router.put("/{plan_id}")
async def update_service_plan(plan_id: str, data: ServicePlanUpdate, user: dict = Depends(require_staff)):
    plan = await db.service_plans.find_one({"id": plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Serviceplan nicht gefunden")

    update_data = {}
    if data.current_hours is not None:
        update_data["current_hours"] = data.current_hours
    if data.interval_hours is not None:
        update_data["interval_hours"] = data.interval_hours
    if data.interval_months is not None:
        update_data["interval_months"] = data.interval_months
    if data.tasks is not None:
        update_data["tasks"] = data.tasks
    if data.notes is not None:
        update_data["notes"] = data.notes

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.service_plans.update_one({"id": plan_id}, {"$set": update_data})

    updated = await db.service_plans.find_one({"id": plan_id}, {"_id": 0})
    return updated


@router.delete("/{plan_id}")
async def delete_service_plan(plan_id: str, user: dict = Depends(require_admin)):
    result = await db.service_plans.delete_one({"id": plan_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Serviceplan nicht gefunden")
    await db.maintenance_entries.delete_many({"service_plan_id": plan_id})
    return {"message": "Serviceplan gelöscht"}


# ============== Maintenance Entries ==============

@router.post("/{plan_id}/entries")
async def add_maintenance_entry(plan_id: str, data: MaintenanceEntryCreate, user: dict = Depends(require_staff)):
    plan = await db.service_plans.find_one({"id": plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Serviceplan nicht gefunden")

    entry_doc = {
        "id": str(uuid.uuid4()),
        "service_plan_id": plan_id,
        "device_id": plan["device_id"],
        "performed_by": data.performed_by,
        "performed_at": data.performed_at,
        "hours_at_service": data.hours_at_service,
        "next_maintenance_months": data.next_maintenance_months,
        "next_maintenance_hours": data.next_maintenance_hours,
        "checklist_data": data.checklist_data or {},
        "measurements": data.measurements or {},
        "load_test": data.load_test or [],
        "ats_test": data.ats_test or {},
        "diagnosis": data.diagnosis or {},
        "notes": data.notes or "",
        "remarks": data.remarks or "",
        "images": [],
        "created_by_user_id": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.maintenance_entries.insert_one(entry_doc)

    # Calculate and update next maintenance on the device
    device = await db.devices.find_one({"id": plan["device_id"]}, {"_id": 0})
    if device:
        update_fields = {"last_maintenance": data.performed_at}
        if data.hours_at_service:
            update_fields["last_maintenance_hours"] = data.hours_at_service

        # Calculate next maintenance by months
        months_val = data.next_maintenance_months
        if months_val:
            from dateutil.relativedelta import relativedelta
            performed_date = datetime.fromisoformat(data.performed_at)
            next_date = performed_date + relativedelta(months=months_val)
            update_fields["next_maintenance"] = next_date.strftime("%Y-%m-%d")

        # Calculate next maintenance by hours
        hours_val = data.next_maintenance_hours
        if hours_val and data.hours_at_service:
            update_fields["next_maintenance_hours"] = data.hours_at_service + hours_val

        await db.devices.update_one({"id": plan["device_id"]}, {"$set": update_fields})

    result = {k: v for k, v in entry_doc.items() if k != "_id"}
    return result


@router.delete("/{plan_id}/entries/{entry_id}")
async def delete_maintenance_entry(plan_id: str, entry_id: str, user: dict = Depends(require_admin)):
    result = await db.maintenance_entries.delete_one({"id": entry_id, "service_plan_id": plan_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return {"message": "Eintrag gelöscht"}


# ============== Device Service Status ==============

@router.get("/device/{device_id}")
async def get_device_service_info(device_id: str, user: dict = Depends(require_staff)):
    """Get service plan and maintenance info for a specific device"""
    plan = await db.service_plans.find_one({"device_id": device_id}, {"_id": 0})
    if not plan:
        return {"has_plan": False, "device_id": device_id}

    entries = await db.maintenance_entries.find(
        {"service_plan_id": plan["id"]}, {"_id": 0}
    ).sort("performed_at", -1).to_list(500)
    plan["entries"] = entries
    plan["has_plan"] = True

    return plan


# ============== Entry Image Upload ==============

@router.post("/{plan_id}/entries/{entry_id}/images")
async def upload_entry_image(plan_id: str, entry_id: str, file: UploadFile = File(...), user: dict = Depends(require_staff)):
    entry = await db.maintenance_entries.find_one({"id": entry_id, "service_plan_id": plan_id}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Datei zu groß (max 20MB)")

    gridfs_id = await fs.upload_from_stream(file.filename, content)
    image_doc = {
        "id": str(uuid.uuid4()),
        "entry_id": entry_id,
        "filename": file.filename,
        "content_type": file.content_type or "image/jpeg",
        "size": len(content),
        "gridfs_id": gridfs_id,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.maintenance_images.insert_one(image_doc)

    # Update entry images list
    images = entry.get("images", [])
    images.append(image_doc["id"])
    await db.maintenance_entries.update_one({"id": entry_id}, {"$set": {"images": images}})

    result = {k: v for k, v in image_doc.items() if k != "_id"}
    result["gridfs_id"] = str(result["gridfs_id"])
    return result


@router.get("/images/{image_id}")
async def get_entry_image(image_id: str):
    img = await db.maintenance_images.find_one({"id": image_id})
    if not img:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden")

    grid_out = await fs.open_download_stream(img["gridfs_id"])
    content = await grid_out.read()
    return StreamingResponse(
        io.BytesIO(content),
        media_type=img.get("content_type", "image/jpeg"),
        headers={"Content-Disposition": f'inline; filename="{img["filename"]}"'}
    )


@router.get("/{plan_id}/entries/{entry_id}/images")
async def list_entry_images(plan_id: str, entry_id: str, user: dict = Depends(require_staff)):
    images = await db.maintenance_images.find({"entry_id": entry_id}, {"_id": 0}).to_list(50)
    for img in images:
        if "gridfs_id" in img:
            img["gridfs_id"] = str(img["gridfs_id"])
    return images
