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
    ssl_skip: Optional[bool] = True
    mandant_id: Optional[int] = 0
    mandant_name: Optional[str] = ""
    auftraege_als: Optional[str] = "jobs"
    zeitraum: Optional[str] = "event"
    unterjobs: Optional[str] = "keine"
    mehrtaegig_splitten: Optional[bool] = False
    kennzeichnungen: Optional[dict] = None


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
    ssl_skip: Optional[bool] = None
    mandant_id: Optional[int] = None
    mandant_name: Optional[str] = None
    auftraege_als: Optional[str] = None
    zeitraum: Optional[str] = None
    unterjobs: Optional[str] = None
    mehrtaegig_splitten: Optional[bool] = None
    kennzeichnungen: Optional[dict] = None


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
        "ssl_skip": data.ssl_skip,
        "mandant_id": data.mandant_id,
        "mandant_name": data.mandant_name,
        "auftraege_als": data.auftraege_als,
        "zeitraum": data.zeitraum,
        "unterjobs": data.unterjobs,
        "mehrtaegig_splitten": data.mehrtaegig_splitten,
        "kennzeichnungen": data.kennzeichnungen or {},
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


@router.post("/integrations/{integration_id}/test")
async def test_integration(integration_id: str):
    """Test the EpiRent API connection and return available mandants."""
    import httpx
    db = get_db()
    integration = await db.integrations.find_one({"id": integration_id}, {"_id": 0})
    if not integration:
        raise HTTPException(status_code=404, detail="Schnittstelle nicht gefunden")

    api_url = integration.get("api_url", "").rstrip("/")
    api_key = integration.get("api_key", "")

    if not api_url or not api_key:
        return {"success": False, "message": "URL oder API-Key fehlt"}

    headers = {
        "X-EPI-NO-SESSION": "True",
        "X-EPI-ACC-TOK": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Test with product/all (small request)
            resp = await client.get(f"{api_url}/v1/product/all?pgs=1", headers=headers)
            data = resp.json()
            if data.get("success") is False:
                return {"success": False, "message": data.get("message", "Verbindung fehlgeschlagen")}

            # Get product count
            product_count = data.get("payload_length", 0)

            # Try stock count
            resp2 = await client.get(f"{api_url}/v1/stock/all?pgs=1&ipg=true", headers=headers)
            data2 = resp2.json()
            stock_count = data2.get("payload_length", 0)

            return {
                "success": True,
                "message": "Verbindung erfolgreich",
                "product_count": product_count,
                "stock_count": stock_count,
                "server_time": data.get("req_datetime", {}).get("formatedDateTime", ""),
            }
    except httpx.ConnectError:
        return {"success": False, "message": "Server nicht erreichbar"}
    except Exception as e:
        return {"success": False, "message": str(e)}
