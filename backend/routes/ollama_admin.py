"""
Admin-Endpoints für die Ollama-Konfiguration.

UI: /admin/settings -> "Ollama / KI-Dokumentanalyse"-Section
Storage: MongoDB-Collection `ollama_config`, single doc mit key="ollama".
Fields: url, api_key, model, text_model.

Test-Endpoint: nimmt eine hochgeladene Datei, jagt sie durch denselben
analyze_document_with_ai-Flow wie ein echter Upload und liefert das
Resultat zurueck (suggested_folder, document_type, metadata, etc.).
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone
import os
import tempfile
import logging

from services.ollama_client import (
    get_ollama_config,
    ollama_is_reachable,
    ollama_list_models,
)

router = APIRouter(prefix="/api/admin/ollama-config", tags=["admin-ollama"])
security = HTTPBearer()
logger = logging.getLogger(__name__)

_db = None
_decode_jwt_token = None


def init_ollama_admin_routes(db, decode_jwt_token):
    global _db, _decode_jwt_token
    _db = db
    _decode_jwt_token = decode_jwt_token


async def _require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert")
    role = user.get("role", "")
    if role != "admin" and "admin" not in (user.get("modules") or []):
        raise HTTPException(status_code=403, detail="Nur Admins")
    return user


@router.get("")
async def get_config(user: dict = Depends(_require_admin)):
    """Liefert die aktuelle Konfiguration (mit Defaults als Fallback)."""
    cfg = await get_ollama_config()
    # API-Key maskieren wenn lang (...letzte 4)
    masked = cfg.get("api_key") or ""
    return {
        "url": cfg["url"],
        "api_key": masked,         # voller Wert zurueck (Admin-Only Endpoint)
        "model": cfg["model"],
        "text_model": cfg["text_model"],
    }


@router.put("")
async def update_config(data: dict, user: dict = Depends(_require_admin)):
    """Speichert die Ollama-Konfiguration. Leerstrings werden so abgelegt,
    damit der Server beim naechsten Read auf die Env-Defaults zurueckfaellt."""
    doc = {
        "key": "ollama",
        "url": (data.get("url") or "").strip().rstrip("/"),
        "api_key": (data.get("api_key") or "").strip(),
        "model": (data.get("model") or "").strip(),
        "text_model": (data.get("text_model") or "").strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": user.get("id"),
    }
    await _db.ollama_config.update_one({"key": "ollama"}, {"$set": doc}, upsert=True)
    logger.info(f"[ollama-config] aktualisiert von {user.get('email','?')}: url={doc['url']}, model={doc['model']}")
    return {"ok": True, "saved": {k: v for k, v in doc.items() if k != "_id"}}


@router.get("/status")
async def get_status(user: dict = Depends(_require_admin)):
    """Health-Check: Erreichbarkeit + installierte Modelle der konfigurierten Instanz."""
    reachable = await ollama_is_reachable()
    models = await ollama_list_models() if reachable else []
    cfg = await get_ollama_config()
    return {
        "reachable": reachable,
        "url": cfg["url"],
        "configured_model": cfg["model"],
        "configured_text_model": cfg["text_model"],
        "available_models": models,
        "model_installed": cfg["model"] in models if models else None,
        "text_model_installed": cfg["text_model"] in models if models else None,
    }


@router.post("/test-document")
async def test_document(file: UploadFile = File(...), user: dict = Depends(_require_admin)):
    """Lädt eine Test-Datei hoch, jagt sie durch den Dokumenten-Analyse-Flow
    (analyze_document_with_ai) und liefert das vollständige Resultat zurück.
    Wird NICHT in der Dokumentenablage gespeichert."""
    suffix = os.path.splitext(file.filename or "test")[1] or ".bin"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.flush()
        tmp.close()

        # Lazy import um Zyklen zu vermeiden
        from routes.documents import analyze_document_with_ai

        started = datetime.now(timezone.utc)
        result = await analyze_document_with_ai(
            file_path=tmp.name,
            mime_type=file.content_type or "",
            custom_folders=[],
        )
        duration = (datetime.now(timezone.utc) - started).total_seconds()

        return {
            "ok": True,
            "filename": file.filename,
            "size_bytes": len(content),
            "mime_type": file.content_type,
            "duration_seconds": round(duration, 2),
            "result": result,
        }
    except Exception as e:
        logger.error(f"[ollama-test] Analyse fehlgeschlagen: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analyse fehlgeschlagen: {type(e).__name__}: {e}")
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass
