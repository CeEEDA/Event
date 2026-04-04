import os
import uuid
import json
import logging
import requests
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "eventenergie-docs"

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

PREDEFINED_FOLDERS = [
    {"id": "rechnungseingang", "name": "Rechnungseingang", "icon": "receipt", "color": "emerald"},
    {"id": "kfz_versicherung", "name": "KFZ Versicherung", "icon": "car", "color": "blue"},
    {"id": "betriebshaftpflicht", "name": "Betriebshaftpflicht", "icon": "shield", "color": "amber"},
    {"id": "vertraege", "name": "Verträge", "icon": "file-text", "color": "fuchsia"},
    {"id": "lieferscheine", "name": "Lieferscheine", "icon": "truck", "color": "orange"},
    {"id": "behoerden", "name": "Behörden", "icon": "landmark", "color": "purple"},
    {"id": "sonstiges", "name": "Sonstiges", "icon": "folder", "color": "gray"},
]

storage_key = None

def init_storage():
    global storage_key
    if storage_key:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120
    )
    resp.raise_for_status()
    return resp.json()

def get_object(path: str):
    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


AI_SYSTEM_PROMPT = """Du bist ein Dokumentenerkennungssystem für die Firma Eventenergie Deutschland GmbH & Co. KG.
Analysiere das hochgeladene Dokument und extrahiere alle relevanten Informationen.

Antworte IMMER als valides JSON mit exakt dieser Struktur:
{
  "document_type": "rechnung|versicherung|vertrag|lieferschein|behoerdenschreiben|sonstiges",
  "suggested_folder": "rechnungseingang|kfz_versicherung|betriebshaftpflicht|vertraege|lieferscheine|behoerden|sonstiges",
  "sender": "Name des Absenders/Firma",
  "recipient": "Name des Empfängers (falls erkennbar)",
  "date": "Datum des Dokuments im Format YYYY-MM-DD (falls erkennbar)",
  "subject": "Betreff/Zusammenfassung in 1-2 Sätzen",
  "amount": null oder Betrag als Zahl (z.B. 1234.56),
  "currency": "EUR" oder andere Währung,
  "invoice_number": "Rechnungsnummer (falls vorhanden)",
  "reference": "Verwendungszweck/Referenznummer/Vertragsnummer/Policennummer",
  "due_date": "Fälligkeitsdatum YYYY-MM-DD (falls vorhanden)",
  "tax_amount": null oder MwSt-Betrag als Zahl,
  "iban": "IBAN (falls vorhanden)",
  "keywords": ["Stichwort1", "Stichwort2", "..."],
  "full_text": "Kompletter extrahierter Text des Dokuments für die Volltextsuche"
}

Regeln:
- Bei Rechnungen: Immer Rechnungsnummer, Betrag, MwSt extrahieren
- Bei Versicherungen: Policennummer als reference, Versicherungsart erkennen (KFZ→kfz_versicherung, Haftpflicht→betriebshaftpflicht)
- Bei Verträgen: Vertragsnummer als reference
- Bei Lieferscheinen: Lieferscheinnummer als reference
- keywords: Relevante Suchbegriffe inkl. Firmennamen, Beträge als Text, Vertragsnummern
- full_text: Den gesamten lesbaren Text des Dokuments extrahieren
- Wenn ein Feld nicht erkennbar ist, setze null oder leeren String"""


async def analyze_document_with_ai(file_path: str, mime_type: str) -> dict:
    """Analyze a document using Gemini AI."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType

        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"doc-analysis-{uuid.uuid4()}",
            system_message=AI_SYSTEM_PROMPT
        ).with_model("gemini", "gemini-2.5-flash")

        file_content = FileContentWithMimeType(
            file_path=file_path,
            mime_type=mime_type
        )

        user_message = UserMessage(
            text="Analysiere dieses Dokument und extrahiere alle Informationen als JSON.",
            file_contents=[file_content]
        )

        response = await chat.send_message(user_message)

        # Parse JSON from response
        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            response_text = "\n".join(json_lines)

        return json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"AI response not valid JSON: {e}, response: {response_text[:500]}")
        return {"document_type": "sonstiges", "suggested_folder": "sonstiges", "subject": "Nicht erkannt", "full_text": "", "keywords": []}
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        return {"document_type": "sonstiges", "suggested_folder": "sonstiges", "subject": "Analyse fehlgeschlagen", "full_text": "", "keywords": []}


@router.get("/folders")
async def get_folders():
    """Get all predefined folders with document counts."""
    counts = {}
    pipeline = [
        {"$match": {"is_deleted": False}},
        {"$group": {"_id": "$folder_id", "count": {"$sum": 1}}}
    ]
    async for item in db.documents.aggregate(pipeline):
        counts[item["_id"]] = item["count"]

    total = await db.documents.count_documents({"is_deleted": False})
    result = []
    for f in PREDEFINED_FOLDERS:
        result.append({**f, "count": counts.get(f["id"], 0)})
    return {"folders": result, "total": total}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), folder_id: str = Form("sonstiges")):
    """Upload a document, store it, and analyze with AI."""
    allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/webp", "image/tiff"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Dateityp {file.content_type} nicht unterstützt. Erlaubt: PDF, JPEG, PNG, WebP, TIFF")

    file_data = await file.read()
    if len(file_data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Datei zu groß (max. 50 MB)")

    ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    storage_path = f"{APP_NAME}/uploads/{uuid.uuid4()}.{ext}"

    try:
        result = put_object(storage_path, file_data, file.content_type)
    except Exception as e:
        logger.error(f"Storage upload failed: {e}")
        raise HTTPException(status_code=500, detail="Fehler beim Speichern der Datei")

    doc_id = str(uuid.uuid4())
    doc = {
        "id": doc_id,
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": result.get("size", len(file_data)),
        "folder_id": folder_id,
        "ai_status": "pending",
        "ai_metadata": {},
        "full_text": "",
        "keywords": [],
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.documents.insert_one(doc)

    # Save temp file for AI analysis
    temp_path = f"/tmp/{uuid.uuid4()}.{ext}"
    with open(temp_path, "wb") as f:
        f.write(file_data)

    try:
        ai_result = await analyze_document_with_ai(temp_path, file.content_type)
        suggested_folder = ai_result.get("suggested_folder", folder_id)
        if folder_id == "sonstiges" and suggested_folder in [f["id"] for f in PREDEFINED_FOLDERS]:
            doc["folder_id"] = suggested_folder

        doc["ai_status"] = "completed"
        doc["ai_metadata"] = {k: v for k, v in ai_result.items() if k not in ("full_text", "keywords")}
        doc["full_text"] = ai_result.get("full_text", "")
        doc["keywords"] = ai_result.get("keywords", [])
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        await db.documents.update_one({"id": doc_id}, {"$set": {
            "folder_id": doc["folder_id"],
            "ai_status": doc["ai_status"],
            "ai_metadata": doc["ai_metadata"],
            "full_text": doc["full_text"],
            "keywords": doc["keywords"],
            "updated_at": doc["updated_at"],
        }})
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        await db.documents.update_one({"id": doc_id}, {"$set": {"ai_status": "failed"}})
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

    clean = {k: v for k, v in doc.items() if k != "_id"}
    return clean


@router.get("/list")
async def list_documents(folder_id: str = None, page: int = 1, limit: int = 50):
    """List documents, optionally filtered by folder."""
    query = {"is_deleted": False}
    if folder_id:
        query["folder_id"] = folder_id

    total = await db.documents.count_documents(query)
    skip = (page - 1) * limit
    docs = []
    async for doc in db.documents.find(query, {"_id": 0, "full_text": 0}).sort("created_at", -1).skip(skip).limit(limit):
        docs.append(doc)

    return {"documents": docs, "total": total, "page": page, "limit": limit}


@router.get("/search")
async def search_documents(q: str = Query(..., min_length=1)):
    """Full-text search across all documents."""
    docs = []
    query = {
        "is_deleted": False,
        "$or": [
            {"full_text": {"$regex": q, "$options": "i"}},
            {"keywords": {"$regex": q, "$options": "i"}},
            {"original_filename": {"$regex": q, "$options": "i"}},
            {"ai_metadata.sender": {"$regex": q, "$options": "i"}},
            {"ai_metadata.subject": {"$regex": q, "$options": "i"}},
            {"ai_metadata.invoice_number": {"$regex": q, "$options": "i"}},
            {"ai_metadata.reference": {"$regex": q, "$options": "i"}},
            {"ai_metadata.iban": {"$regex": q, "$options": "i"}},
        ]
    }
    async for doc in db.documents.find(query, {"_id": 0, "full_text": 0}).sort("created_at", -1).limit(50):
        docs.append(doc)
    return {"documents": docs, "query": q}


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """Get a single document with all metadata."""
    doc = await db.documents.find_one({"id": doc_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return doc


@router.put("/{doc_id}/move")
async def move_document(doc_id: str, folder_id: str = Query(...)):
    """Move a document to a different folder."""
    valid_ids = [f["id"] for f in PREDEFINED_FOLDERS]
    if folder_id not in valid_ids:
        raise HTTPException(status_code=400, detail="Ungültiger Ordner")

    result = await db.documents.update_one(
        {"id": doc_id, "is_deleted": False},
        {"$set": {"folder_id": folder_id, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return {"status": "moved", "folder_id": folder_id}


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """Soft-delete a document."""
    result = await db.documents.update_one(
        {"id": doc_id, "is_deleted": False},
        {"$set": {"is_deleted": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return {"status": "deleted"}


@router.get("/{doc_id}/file")
async def download_file(doc_id: str):
    """Download the actual file."""
    doc = await db.documents.find_one({"id": doc_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    try:
        data, ct = get_object(doc["storage_path"])
        return Response(
            content=data,
            media_type=doc.get("content_type", ct),
            headers={"Content-Disposition": f'inline; filename="{doc["original_filename"]}"'}
        )
    except Exception as e:
        logger.error(f"File download failed: {e}")
        raise HTTPException(status_code=500, detail="Fehler beim Herunterladen")
