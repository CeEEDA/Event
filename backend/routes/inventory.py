"""Inventar-Modul: Verwaltung von Anlagevermoegen mit Gruppen und Bildern.

Collections:
  - inventory_items: einzelne Inventar-Positionen
  - inventory_groups: Kategorien (Netzwerk, Werkzeug, Fahrzeug, ...)

Bilder werden ueber das bestehende Cloud-Storage (put_object/get_object) abgelegt,
Referenzen im Item-Dokument gespeichert.
"""
import os
import uuid
import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inventory", tags=["inventory"])

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]

APP_NAME = "eventenergie-inventory"

# ─── Cloud storage helpers (nutzt die gleichen wie documents.py) ────
from routes.documents import put_object, get_object

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
ALLOWED_DOC_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # pptx
    "text/plain",
    "text/csv",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Standard-Gruppen (Seed beim ersten Aufruf) ───────────────────
DEFAULT_GROUPS = [
    {"id": "netzwerk", "name": "Netzwerk", "color": "blue"},
    {"id": "werkzeug", "name": "Werkzeug", "color": "amber"},
    {"id": "fahrzeuge", "name": "Fahrzeuge", "color": "orange"},
    {"id": "buero", "name": "Buero", "color": "gray"},
    {"id": "veranstaltungstechnik", "name": "Veranstaltungstechnik", "color": "fuchsia"},
    {"id": "sonstiges", "name": "Sonstiges", "color": "emerald"},
]


async def _ensure_default_groups():
    """Legt Default-Gruppen an, wenn keine existieren."""
    count = await db.inventory_groups.count_documents({})
    if count == 0:
        for g in DEFAULT_GROUPS:
            await db.inventory_groups.insert_one({
                **g,
                "created_at": _now_iso(),
                "seed": True,
            })


# ─── Pydantic Models ─────────────────────────────────────────────
class GroupCreate(BaseModel):
    name: str
    color: Optional[str] = "gray"


class ItemCreate(BaseModel):
    bezeichnung: str
    anlagevermoegensnummer: Optional[str] = ""
    besitzer: str = "ES Besitz und Verwaltung GmbH & Co. KG"
    einkaufspreis: Optional[float] = 0.0
    anschaffung_monat: Optional[int] = None
    anschaffung_jahr: Optional[int] = None
    aktueller_bilanzwert: Optional[float] = 0.0
    marktschaetzwert: Optional[float] = 0.0
    stueckzahl: Optional[int] = 1
    notiz: Optional[str] = ""
    group_id: str


class ItemUpdate(BaseModel):
    bezeichnung: Optional[str] = None
    anlagevermoegensnummer: Optional[str] = None
    besitzer: Optional[str] = None
    einkaufspreis: Optional[float] = None
    anschaffung_monat: Optional[int] = None
    anschaffung_jahr: Optional[int] = None
    aktueller_bilanzwert: Optional[float] = None
    marktschaetzwert: Optional[float] = None
    stueckzahl: Optional[int] = None
    notiz: Optional[str] = None
    group_id: Optional[str] = None


# ─── Gruppen-Endpoints ────────────────────────────────────────────
@router.get("/groups")
async def list_groups():
    """Liste aller Inventar-Gruppen (Kategorien)."""
    await _ensure_default_groups()
    groups = []
    async for g in db.inventory_groups.find({}, {"_id": 0}).sort("name", 1):
        # Anzahl der Items in dieser Gruppe
        g["item_count"] = await db.inventory_items.count_documents({"group_id": g["id"], "is_deleted": {"$ne": True}})
        groups.append(g)
    return {"groups": groups}


@router.post("/groups")
async def create_group(payload: GroupCreate):
    """Neue Gruppe anlegen (z.B. wenn User im Formular eine neue Kategorie tippt)."""
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Name darf nicht leer sein")
    # Kollisions-Check (case-insensitive)
    existing = await db.inventory_groups.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}})
    if existing:
        return {"group": {k: v for k, v in existing.items() if k != "_id"}, "created": False}
    gid = name.lower().replace(" ", "_").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    gid = "".join(c for c in gid if c.isalnum() or c == "_") or f"g_{uuid.uuid4().hex[:6]}"
    doc = {
        "id": gid,
        "name": name,
        "color": payload.color or "gray",
        "created_at": _now_iso(),
        "seed": False,
    }
    await db.inventory_groups.insert_one(doc)
    # Motor mutates ``doc`` in-place and adds ``_id`` (ObjectId) which is NOT
    # JSON serializable. Strip it before returning – otherwise the FIRST call
    # would fail with HTTP 500 while the second call (matching the collision
    # check above) would suddenly work.
    doc.pop("_id", None)
    return {"group": doc, "created": True}


@router.delete("/groups/{group_id}")
async def delete_group(group_id: str):
    """Loescht eine Gruppe. Fehlschlag, wenn noch Items zugeordnet sind."""
    count = await db.inventory_items.count_documents({"group_id": group_id, "is_deleted": {"$ne": True}})
    if count > 0:
        raise HTTPException(400, f"Gruppe enthaelt noch {count} Inventar-Positionen. Erst leeren oder umziehen.")
    r = await db.inventory_groups.delete_one({"id": group_id})
    return {"deleted": r.deleted_count}


# ─── Item-Endpoints ───────────────────────────────────────────────
@router.get("/items")
async def list_items(
    q: Optional[str] = Query(None, description="Volltext-Suche"),
    group_id: Optional[str] = None,
    limit: int = 500,
):
    """Liste aller Inventar-Positionen. Mit Suche und optionalem Gruppen-Filter."""
    query: dict = {"is_deleted": {"$ne": True}}
    if group_id:
        query["group_id"] = group_id
    if q and q.strip():
        import re as _re
        # Multi-Term UND-Suche (Leerzeichen/Komma trennt)
        terms = [t.strip() for t in _re.split(r"[\s,;]+", q) if t.strip()]
        clauses = []
        for term in terms:
            esc = _re.escape(term)
            clauses.append({"$or": [
                {"bezeichnung": {"$regex": esc, "$options": "i"}},
                {"anlagevermoegensnummer": {"$regex": esc, "$options": "i"}},
                {"besitzer": {"$regex": esc, "$options": "i"}},
                {"notiz": {"$regex": esc, "$options": "i"}},
                {"group_name": {"$regex": esc, "$options": "i"}},
            ]})
        if len(clauses) == 1:
            query.update(clauses[0])
        else:
            query["$and"] = clauses

    # Gruppe-Namen fuer die UI mitliefern
    groups_by_id = {}
    async for g in db.inventory_groups.find({}, {"_id": 0}):
        groups_by_id[g["id"]] = g

    items = []
    async for it in db.inventory_items.find(query, {"_id": 0}).sort([("bezeichnung", 1)]).limit(limit):
        it["group_name"] = groups_by_id.get(it.get("group_id", ""), {}).get("name", "-")
        it["group_color"] = groups_by_id.get(it.get("group_id", ""), {}).get("color", "gray")
        items.append(it)
    return {"items": items, "total": len(items)}


@router.post("/items")
async def create_item(payload: ItemCreate):
    """Neue Inventar-Position anlegen."""
    if not payload.bezeichnung.strip():
        raise HTTPException(400, "Bezeichnung darf nicht leer sein")
    # Mindestens Bilanzwert ODER Marktschaetzwert muss angegeben sein
    bilanz = float(payload.aktueller_bilanzwert or 0)
    markt = float(payload.marktschaetzwert or 0)
    if bilanz <= 0 and markt <= 0:
        raise HTTPException(400, "Bitte einen Bilanzwert ODER einen Marktschaetzwert eintragen (mindestens einer > 0).")
    # Gruppe pruefen
    grp = await db.inventory_groups.find_one({"id": payload.group_id})
    if not grp:
        raise HTTPException(400, f"Gruppe '{payload.group_id}' existiert nicht")

    doc = {
        "id": str(uuid.uuid4()),
        "bezeichnung": payload.bezeichnung.strip(),
        "anlagevermoegensnummer": (payload.anlagevermoegensnummer or "").strip(),
        "besitzer": payload.besitzer.strip() or "ES Besitz und Verwaltung GmbH & Co. KG",
        "einkaufspreis": float(payload.einkaufspreis or 0),
        "anschaffung_monat": payload.anschaffung_monat,
        "anschaffung_jahr": payload.anschaffung_jahr,
        "aktueller_bilanzwert": bilanz,
        "marktschaetzwert": markt,
        "stueckzahl": int(payload.stueckzahl or 1),
        "notiz": (payload.notiz or "").strip(),
        "group_id": payload.group_id,
        "images": [],
        "documents": [],
        "is_deleted": False,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    await db.inventory_items.insert_one(doc)
    clean = {k: v for k, v in doc.items() if k != "_id"}
    return clean


@router.get("/items/{item_id}")
async def get_item(item_id: str):
    doc = await db.inventory_items.find_one({"id": item_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Inventar-Position nicht gefunden")
    return doc


@router.put("/items/{item_id}")
async def update_item(item_id: str, payload: ItemUpdate):
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "group_id" in updates:
        grp = await db.inventory_groups.find_one({"id": updates["group_id"]})
        if not grp:
            raise HTTPException(400, f"Gruppe '{updates['group_id']}' existiert nicht")
    # Wenn beide Werte-Felder betroffen: mind. einer muss > 0 sein (bezogen auf Zielzustand)
    if "aktueller_bilanzwert" in updates or "marktschaetzwert" in updates:
        current = await db.inventory_items.find_one({"id": item_id}, {"aktueller_bilanzwert": 1, "marktschaetzwert": 1})
        if current:
            bilanz = float(updates.get("aktueller_bilanzwert", current.get("aktueller_bilanzwert", 0)) or 0)
            markt = float(updates.get("marktschaetzwert", current.get("marktschaetzwert", 0)) or 0)
            if bilanz <= 0 and markt <= 0:
                raise HTTPException(400, "Bitte einen Bilanzwert ODER einen Marktschaetzwert eintragen.")
    if not updates:
        return {"status": "noop"}
    updates["updated_at"] = _now_iso()
    r = await db.inventory_items.update_one({"id": item_id, "is_deleted": {"$ne": True}}, {"$set": updates})
    if r.matched_count == 0:
        raise HTTPException(404, "Inventar-Position nicht gefunden")
    doc = await db.inventory_items.find_one({"id": item_id}, {"_id": 0})
    return doc


@router.delete("/items/{item_id}")
async def delete_item(item_id: str):
    r = await db.inventory_items.update_one(
        {"id": item_id},
        {"$set": {"is_deleted": True, "updated_at": _now_iso()}},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "Inventar-Position nicht gefunden")
    return {"status": "deleted"}


# ─── Bild-Endpoints ───────────────────────────────────────────────
@router.post("/items/{item_id}/images")
async def add_image(item_id: str, file: UploadFile = File(...)):
    """Bild an eine Inventar-Position anhaengen."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, f"Bildtyp {file.content_type} nicht unterstuetzt. Erlaubt: JPEG, PNG, WebP, HEIC")

    file_data = await file.read()
    if len(file_data) > 20 * 1024 * 1024:
        raise HTTPException(400, "Bild zu gross (max. 20 MB)")

    doc = await db.inventory_items.find_one({"id": item_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Inventar-Position nicht gefunden")

    ext = (file.filename or "img.jpg").rsplit(".", 1)[-1].lower()
    if len(ext) > 5 or not ext.isalnum():
        ext = "jpg"
    img_id = str(uuid.uuid4())
    storage_path = f"{APP_NAME}/{item_id}/{img_id}.{ext}"

    cloud_path = None
    try:
        result = put_object(storage_path, file_data, file.content_type)
        cloud_path = result["path"]
    except Exception as e:
        logger.warning(f"[inventory] Cloud upload failed, using local fallback: {e}")
        # Local fallback
        local_dir = f"/app/data/inventory/{item_id}"
        os.makedirs(local_dir, exist_ok=True)
        with open(f"{local_dir}/{img_id}.{ext}", "wb") as f:
            f.write(file_data)

    image_entry = {
        "id": img_id,
        "filename": file.filename or f"{img_id}.{ext}",
        "content_type": file.content_type,
        "size": len(file_data),
        "storage_path": cloud_path or f"local://{APP_NAME}/{item_id}/{img_id}.{ext}",
        "uploaded_at": _now_iso(),
    }
    await db.inventory_items.update_one(
        {"id": item_id},
        {"$push": {"images": image_entry}, "$set": {"updated_at": _now_iso()}},
    )
    return image_entry


@router.get("/items/{item_id}/images/{img_id}")
async def get_image(item_id: str, img_id: str):
    """Bild-Binary ausliefern (fuer <img src=...>)."""
    doc = await db.inventory_items.find_one({"id": item_id}, {"_id": 0, "images": 1})
    if not doc:
        raise HTTPException(404, "Inventar-Position nicht gefunden")
    img = next((i for i in doc.get("images", []) if i.get("id") == img_id), None)
    if not img:
        raise HTTPException(404, "Bild nicht gefunden")
    storage_path = img.get("storage_path", "")
    try:
        if storage_path.startswith("local://"):
            local_rel = storage_path.replace("local://", "", 1)
            local_path = f"/app/data/inventory/{item_id}/{local_rel.rsplit('/', 1)[-1]}"
            if not os.path.exists(local_path):
                raise HTTPException(404, "Bilddatei nicht auf Server")
            with open(local_path, "rb") as f:
                data = f.read()
            return Response(content=data, media_type=img.get("content_type") or "image/jpeg")
        data, ct = get_object(storage_path)
        return Response(content=data, media_type=ct or img.get("content_type") or "image/jpeg")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[inventory] Bildabruf fehlgeschlagen: {e}")
        raise HTTPException(500, "Bild konnte nicht geladen werden")


@router.delete("/items/{item_id}/images/{img_id}")
async def delete_image(item_id: str, img_id: str):
    r = await db.inventory_items.update_one(
        {"id": item_id},
        {"$pull": {"images": {"id": img_id}}, "$set": {"updated_at": _now_iso()}},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "Inventar-Position nicht gefunden")
    return {"deleted": True}


# ─── Dokumente-Endpoints (PDF/Word/Excel/CSV) ─────────────────────
@router.post("/items/{item_id}/documents")
async def add_document(item_id: str, file: UploadFile = File(...)):
    """Datei (PDF/Word/Excel etc.) an eine Inventar-Position anhaengen."""
    ct = file.content_type or ""
    if ct not in ALLOWED_DOC_TYPES:
        raise HTTPException(400, f"Dateityp {ct} nicht unterstuetzt. Erlaubt: PDF, DOC(X), XLS(X), PPT(X), TXT, CSV")

    file_data = await file.read()
    if len(file_data) > 50 * 1024 * 1024:
        raise HTTPException(400, "Datei zu gross (max. 50 MB)")

    doc = await db.inventory_items.find_one({"id": item_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Inventar-Position nicht gefunden")

    ext = (file.filename or "file.pdf").rsplit(".", 1)[-1].lower()
    if len(ext) > 5 or not ext.isalnum():
        ext = "bin"
    doc_id = str(uuid.uuid4())
    storage_path = f"{APP_NAME}/{item_id}/docs/{doc_id}.{ext}"

    cloud_path = None
    try:
        result = put_object(storage_path, file_data, ct)
        cloud_path = result["path"]
    except Exception as e:
        logger.warning(f"[inventory] Cloud doc upload failed, local fallback: {e}")
        local_dir = f"/app/data/inventory/{item_id}/docs"
        os.makedirs(local_dir, exist_ok=True)
        with open(f"{local_dir}/{doc_id}.{ext}", "wb") as f:
            f.write(file_data)

    doc_entry = {
        "id": doc_id,
        "filename": file.filename or f"{doc_id}.{ext}",
        "content_type": ct,
        "size": len(file_data),
        "storage_path": cloud_path or f"local://{APP_NAME}/{item_id}/docs/{doc_id}.{ext}",
        "uploaded_at": _now_iso(),
    }
    await db.inventory_items.update_one(
        {"id": item_id},
        {"$push": {"documents": doc_entry}, "$set": {"updated_at": _now_iso()}},
    )
    return doc_entry


@router.get("/items/{item_id}/documents/{doc_id}")
async def get_document(item_id: str, doc_id: str):
    """Dokument ausliefern (Download / Anzeigen)."""
    doc = await db.inventory_items.find_one({"id": item_id}, {"_id": 0, "documents": 1})
    if not doc:
        raise HTTPException(404, "Inventar-Position nicht gefunden")
    entry = next((d for d in doc.get("documents", []) if d.get("id") == doc_id), None)
    if not entry:
        raise HTTPException(404, "Dokument nicht gefunden")
    storage_path = entry.get("storage_path", "")
    filename = entry.get("filename", f"{doc_id}.bin")
    try:
        if storage_path.startswith("local://"):
            local_rel = storage_path.replace("local://", "", 1).rsplit("/", 1)[-1]
            local_path = f"/app/data/inventory/{item_id}/docs/{local_rel}"
            if not os.path.exists(local_path):
                raise HTTPException(404, "Datei nicht auf Server")
            with open(local_path, "rb") as f:
                data = f.read()
            return Response(
                content=data,
                media_type=entry.get("content_type") or "application/octet-stream",
                headers={"Content-Disposition": f'inline; filename="{filename}"'},
            )
        data, ct = get_object(storage_path)
        return Response(
            content=data,
            media_type=ct or entry.get("content_type") or "application/octet-stream",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[inventory] Dokument-Abruf fehlgeschlagen: {e}")
        raise HTTPException(500, "Dokument konnte nicht geladen werden")


@router.delete("/items/{item_id}/documents/{doc_id}")
async def delete_document_entry(item_id: str, doc_id: str):
    r = await db.inventory_items.update_one(
        {"id": item_id},
        {"$pull": {"documents": {"id": doc_id}}, "$set": {"updated_at": _now_iso()}},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "Inventar-Position nicht gefunden")
    return {"deleted": True}


# ─── Stats fuer die Uebersicht (spaeter Auswertung) ──────────────
@router.get("/stats")
async def stats():
    """Kurz-Statistik: Gesamtwerte + Gruppierung."""
    total_items = await db.inventory_items.count_documents({"is_deleted": {"$ne": True}})
    # Aggregation: Summe pro Gruppe
    pipeline = [
        {"$match": {"is_deleted": {"$ne": True}}},
        {"$group": {
            "_id": "$group_id",
            "count": {"$sum": 1},
            "total_einkauf": {"$sum": {"$multiply": ["$einkaufspreis", "$stueckzahl"]}},
            "total_bilanz": {"$sum": {"$multiply": ["$aktueller_bilanzwert", "$stueckzahl"]}},
            "total_markt": {"$sum": {"$multiply": [{"$ifNull": ["$marktschaetzwert", 0]}, "$stueckzahl"]}},
        }},
    ]
    per_group = []
    async for row in db.inventory_items.aggregate(pipeline):
        per_group.append({
            "group_id": row["_id"],
            "count": row["count"],
            "total_einkauf": round(row["total_einkauf"] or 0, 2),
            "total_bilanz": round(row["total_bilanz"] or 0, 2),
            "total_markt": round(row["total_markt"] or 0, 2),
        })
    total_einkauf = sum(r["total_einkauf"] for r in per_group)
    total_bilanz = sum(r["total_bilanz"] for r in per_group)
    total_markt = sum(r["total_markt"] for r in per_group)
    return {
        "total_items": total_items,
        "total_einkauf": round(total_einkauf, 2),
        "total_bilanz": round(total_bilanz, 2),
        "total_markt": round(total_markt, 2),
        "per_group": per_group,
    }


# ─── Exports (XLSX + PDF) ─────────────────────────────────────────
async def _load_items_and_groups(group_ids: Optional[list] = None) -> tuple[list, dict]:
    q = {"is_deleted": {"$ne": True}}
    if group_ids:
        q["group_id"] = {"$in": group_ids}
    items = [d async for d in db.inventory_items.find(q, {"_id": 0})]
    groups_by_id = {}
    async for g in db.inventory_groups.find({}, {"_id": 0}):
        groups_by_id[g["id"]] = g
    return items, groups_by_id


def _parse_group_ids(raw: Optional[str]) -> Optional[list]:
    if not raw:
        return None
    ids = [g.strip() for g in raw.split(",") if g.strip()]
    return ids or None


@router.get("/export/xlsx")
async def export_xlsx(groups: Optional[str] = Query(None, description="Komma-separierte Gruppen-IDs, leer = alle")):
    """Excel-Export mit Deckblatt + je 1 Sheet pro Gruppe.
    Wenn 'groups' gesetzt: nur diese Gruppen werden exportiert.
    """
    from routes.inventory_exports import build_xlsx
    group_ids = _parse_group_ids(groups)
    items, groups_by_id = await _load_items_and_groups(group_ids)
    data = build_xlsx(items, groups_by_id)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    suffix = f"_{len(group_ids)}Gruppen" if group_ids else ""
    fname = f"Inventar{suffix}_{ts}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/export/pdf")
async def export_pdf(
    mode: str = Query("smart", pattern="^(smart|mittel|gross)$"),
    groups: Optional[str] = Query(None, description="Komma-separierte Gruppen-IDs, leer = alle"),
):
    """PDF-Export mit 3 Detaillierungsstufen und optionalem Gruppen-Filter."""
    from routes.inventory_exports import build_pdf
    group_ids = _parse_group_ids(groups)
    items, groups_by_id = await _load_items_and_groups(group_ids)
    data = build_pdf(items, groups_by_id, mode=mode, get_object_fn=get_object)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    suffix = f"_{len(group_ids)}Gruppen" if group_ids else ""
    fname = f"Inventar_{mode}{suffix}_{ts}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
