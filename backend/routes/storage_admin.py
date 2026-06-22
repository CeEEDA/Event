"""
Storage-Health-Check fuer die Dokumentenablage.

Zeigt im Admin-UI:
- Konfigurierten LOCAL_STORAGE_PATH
- Existenz / Beschreibbarkeit des Pfads
- Freien Speicherplatz auf der Partition
- Top-Level-Datei-Count
- 10 juengste Dateien (Beispiel-Listing)
- Schreib-Test (legt eine ~10-Byte-Testdatei an und loescht sie wieder)
"""
import os
import shutil
import logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter(prefix="/api/admin/storage", tags=["admin-storage"])
security = HTTPBearer()
logger = logging.getLogger(__name__)

_db = None
_decode_jwt_token = None


def init_storage_admin_routes(db, decode_jwt_token):
    global _db, _decode_jwt_token
    _db = db
    _decode_jwt_token = decode_jwt_token


def _local_storage_root() -> str:
    # Selbe Logik wie in routes/documents.py - hier nochmal um Zyklen zu vermeiden.
    default = r"C:\eventenergie\Dokumentenablage" if os.name == "nt" else "/app/data/Dokumentenablage"
    return os.environ.get("LOCAL_STORAGE_PATH", default)


async def _require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = _decode_jwt_token(credentials.credentials)
    user = await _db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert")
    if user.get("role") != "admin" and "admin" not in (user.get("modules") or []):
        raise HTTPException(status_code=403, detail="Nur Admins")
    return user


@router.get("/health")
async def get_storage_health(user: dict = Depends(_require_admin)):
    root = _local_storage_root()
    root_exists = os.path.isdir(root)
    writable = False
    write_error = None
    free_gb = None
    total_gb = None
    used_pct = None
    file_count = 0
    recent_files = []

    # Schreib-Test
    if root_exists:
        try:
            test_file = os.path.join(root, ".storage_health_check.tmp")
            with open(test_file, "wb") as f:
                f.write(b"healthcheck")
            os.remove(test_file)
            writable = True
        except Exception as e:
            write_error = str(e)[:200]

        # Disk-Space
        try:
            usage = shutil.disk_usage(root)
            free_gb = round(usage.free / (1024 ** 3), 2)
            total_gb = round(usage.total / (1024 ** 3), 2)
            used_pct = round((usage.used / usage.total) * 100, 1)
        except Exception as e:
            write_error = f"{write_error or ''} | disk_usage: {e}"

        # File-Count + 10 juengste Files
        try:
            all_files = []
            for entry in Path(root).rglob("*"):
                if entry.is_file():
                    try:
                        st = entry.stat()
                        all_files.append({
                            "rel_path": str(entry.relative_to(root)),
                            "size_kb": round(st.st_size / 1024, 1),
                            "modified": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                        })
                    except OSError:
                        continue
            file_count = len(all_files)
            all_files.sort(key=lambda f: f["modified"], reverse=True)
            recent_files = all_files[:10]
        except Exception as e:
            write_error = f"{write_error or ''} | listing: {e}"

    # MongoDB-Vergleich: Wie viele Dokumente sollten da sein?
    db_doc_count = 0
    db_with_local_path = 0
    try:
        db_doc_count = await _db.documents.count_documents({"is_deleted": False})
        db_with_local_path = await _db.documents.count_documents({"is_deleted": False, "local_path": {"$exists": True, "$ne": None}})
    except Exception:
        pass

    return {
        "configured_path": root,
        "configured_via_env": "LOCAL_STORAGE_PATH" in os.environ,
        "exists": root_exists,
        "writable": writable,
        "write_error": write_error,
        "platform": os.name,            # "nt" auf Windows, "posix" auf Linux
        "free_gb": free_gb,
        "total_gb": total_gb,
        "used_percent": used_pct,
        "file_count": file_count,
        "recent_files": recent_files,
        "db_documents_total": db_doc_count,
        "db_documents_with_local_path": db_with_local_path,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
