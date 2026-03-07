from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/api/admin", tags=["admin"])


class IntegrationCreate(BaseModel):
    name: str
    type: Optional[str] = "ERP"
    api_url: Optional[str] = ""
    api_key: Optional[str] = ""
    active: Optional[bool] = True
    field_mappings: Optional[dict] = None
    username: Optional[str] = ""
    password: Optional[str] = ""
    sync_interval_minutes: Optional[int] = 60
    notes: Optional[str] = ""


class IntegrationUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    active: Optional[bool] = None
    field_mappings: Optional[dict] = None
    username: Optional[str] = None
    password: Optional[str] = None
    sync_interval_minutes: Optional[int] = None
    notes: Optional[str] = None


def get_db():
    from server import db
    return db


@router.get("/integrations")
async def list_integrations():
    db = get_db()
    items = await db.integrations.find({}, {"_id": 0}).to_list(100)
    return items


@router.post("/integrations")
async def create_integration(data: IntegrationCreate):
    db = get_db()
    integration_id = str(uuid.uuid4())
    doc = {
        "id": integration_id,
        "name": data.name,
        "type": data.type,
        "api_url": data.api_url,
        "api_key": data.api_key,
        "active": data.active,
        "field_mappings": data.field_mappings or {},
        "username": data.username,
        "password": data.password,
        "sync_interval_minutes": data.sync_interval_minutes,
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.integrations.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/integrations/{integration_id}")
async def update_integration(integration_id: str, data: IntegrationUpdate):
    db = get_db()
    existing = await db.integrations.find_one({"id": integration_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Schnittstelle nicht gefunden")

    update_data = {k: v for k, v in data.dict().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.integrations.update_one({"id": integration_id}, {"$set": update_data})
    updated = await db.integrations.find_one({"id": integration_id}, {"_id": 0})
    return updated


@router.delete("/integrations/{integration_id}")
async def delete_integration(integration_id: str):
    db = get_db()
    result = await db.integrations.delete_one({"id": integration_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Schnittstelle nicht gefunden")
    return {"detail": "Schnittstelle gelöscht"}
