"""Backup-System: Automatische und manuelle Backups für MongoDB und Quellcode."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import asyncio
import logging
import os
import subprocess
import shutil
import uuid
import zipfile
from pathlib import Path

router = APIRouter(prefix="/api/backup", tags=["backup"])
logger = logging.getLogger(__name__)

BACKUP_BASE_DIR = Path(__file__).parent.parent.parent / "backups"
BACKUP_BASE_DIR.mkdir(parents=True, exist_ok=True)

_scheduler_task: Optional[asyncio.Task] = None


def get_db():
    from server import db
    return db


# ── Models ──

class BackupSettings(BaseModel):
    db_backup_enabled: bool = True
    db_backup_interval_hours: int = 12
    files_backup_enabled: bool = True
    files_backup_interval_hours: int = 72
    retention_days: int = 7


DEFAULT_SETTINGS = {
    "config_type": "backup",
    "db_backup_enabled": True,
    "db_backup_interval_hours": 12,
    "files_backup_enabled": True,
    "files_backup_interval_hours": 72,
    "retention_days": 7,
}


# ── Settings Endpoints ──

@router.get("/settings")
async def get_backup_settings():
    db = get_db()
    settings = await db.app_config.find_one({"config_type": "backup"}, {"_id": 0})
    if not settings:
        return DEFAULT_SETTINGS
    return settings


@router.post("/settings")
async def update_backup_settings(data: BackupSettings):
    db = get_db()
    doc = {
        "config_type": "backup",
        "db_backup_enabled": data.db_backup_enabled,
        "db_backup_interval_hours": data.db_backup_interval_hours,
        "files_backup_enabled": data.files_backup_enabled,
        "files_backup_interval_hours": data.files_backup_interval_hours,
        "retention_days": data.retention_days,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.app_config.update_one(
        {"config_type": "backup"},
        {"$set": doc},
        upsert=True,
    )
    # Restart scheduler with new settings
    await _restart_scheduler()
    return {**doc, "message": "Backup-Einstellungen gespeichert"}


# ── Backup List ──

@router.get("/list")
async def list_backups():
    db = get_db()
    backups = await db.backups.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    # Verify files still exist on disk
    for b in backups:
        b["file_exists"] = os.path.exists(b.get("file_path", ""))
        if b["file_exists"]:
            try:
                b["file_size"] = os.path.getsize(b["file_path"])
            except OSError:
                b["file_size"] = 0
    return backups


# ── Manual Trigger ──

@router.post("/trigger/db")
async def trigger_db_backup():
    result = await _run_db_backup()
    if result.get("success"):
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "Backup fehlgeschlagen"))


@router.post("/trigger/files")
async def trigger_files_backup():
    result = await _run_files_backup()
    if result.get("success"):
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "Backup fehlgeschlagen"))


# ── Delete Backup ──

@router.delete("/{backup_id}")
async def delete_backup(backup_id: str):
    db = get_db()
    backup = await db.backups.find_one({"id": backup_id}, {"_id": 0})
    if not backup:
        raise HTTPException(status_code=404, detail="Backup nicht gefunden")

    # Delete file from disk
    file_path = backup.get("file_path", "")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            logger.error(f"Fehler beim Löschen der Datei {file_path}: {e}")

    await db.backups.delete_one({"id": backup_id})
    return {"message": "Backup gelöscht"}


# ── Download Backup ──

@router.get("/{backup_id}/download")
async def download_backup(backup_id: str):
    from fastapi.responses import FileResponse
    db = get_db()
    backup = await db.backups.find_one({"id": backup_id}, {"_id": 0})
    if not backup:
        raise HTTPException(status_code=404, detail="Backup nicht gefunden")

    file_path = backup.get("file_path", "")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Backup-Datei nicht gefunden")

    filename = os.path.basename(file_path)
    return FileResponse(
        file_path,
        media_type="application/zip" if filename.endswith(".zip") else "application/gzip",
        filename=filename,
    )


# ── Backup Execution ──

async def _run_db_backup() -> dict:
    """Execute a MongoDB database backup. Tries mongodump first, falls back to Python-native export."""
    db = get_db()
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = BACKUP_BASE_DIR / "db"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Try mongodump first
    mongodump_path = shutil.which("mongodump")
    if mongodump_path:
        archive_path = str(backup_dir / f"db_backup_{timestamp}.gz")
        try:
            cmd = [
                mongodump_path,
                f"--uri={mongo_url}",
                f"--db={db_name}",
                f"--archive={archive_path}",
                "--gzip",
            ]
            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                file_size = os.path.getsize(archive_path) if os.path.exists(archive_path) else 0
                backup_doc = {
                    "id": str(uuid.uuid4()),
                    "type": "database",
                    "file_path": archive_path,
                    "file_name": f"db_backup_{timestamp}.gz",
                    "file_size": file_size,
                    "status": "success",
                    "trigger": "manual",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                await db.backups.insert_one(backup_doc)
                backup_doc.pop("_id", None)
                logger.info(f"DB-Backup (mongodump) erstellt: {archive_path} ({file_size} bytes)")
                return {"success": True, "backup": backup_doc}
            else:
                logger.warning(f"mongodump fehlgeschlagen, Fallback auf Python-Export: {result.stderr[:200]}")
        except Exception as e:
            logger.warning(f"mongodump nicht nutzbar ({e}), Fallback auf Python-Export")

    # Fallback: Python-native JSON export (nur kleine Collections, grosse werden uebersprungen)
    import json as json_mod
    archive_path = str(backup_dir / f"db_backup_{timestamp}.zip")
    MAX_DOCS_FOR_RAM_EXPORT = 10000
    try:
        collections = await db.list_collection_names()
        # Pre-fetch all docs per collection (async), then compress synchronously in a thread
        coll_data = {}
        for coll_name in collections:
            count = await db[coll_name].estimated_document_count()
            if count > MAX_DOCS_FOR_RAM_EXPORT:
                coll_data[coll_name] = {"skipped": True, "count": count}
                logger.info(f"Backup: {coll_name} uebersprungen ({count} Docs > {MAX_DOCS_FOR_RAM_EXPORT})")
                continue
            docs = await db[coll_name].find({}).to_list(MAX_DOCS_FOR_RAM_EXPORT)
            for doc in docs:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                for key, val in doc.items():
                    if isinstance(val, datetime):
                        doc[key] = val.isoformat()
            coll_data[coll_name] = {"skipped": False, "docs": docs}

        def _write_zip():
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for cname, cdata in coll_data.items():
                    if cdata.get("skipped"):
                        zf.writestr(
                            f"{cname}_SKIPPED.txt",
                            f"Collection '{cname}' hat {cdata['count']} Dokumente und wurde uebersprungen.\n"
                            f"Verwende mongodump fuer vollstaendige Backups.",
                        )
                    else:
                        json_str = json_mod.dumps(cdata["docs"], ensure_ascii=False, indent=2, default=str)
                        zf.writestr(f"{cname}.json", json_str)

        await asyncio.to_thread(_write_zip)

        file_size = os.path.getsize(archive_path) if os.path.exists(archive_path) else 0
        backup_doc = {
            "id": str(uuid.uuid4()),
            "type": "database",
            "file_path": archive_path,
            "file_name": f"db_backup_{timestamp}.zip",
            "file_size": file_size,
            "status": "success",
            "trigger": "manual",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.backups.insert_one(backup_doc)
        backup_doc.pop("_id", None)
        logger.info(f"DB-Backup (Python-Export) erstellt: {archive_path} ({file_size} bytes)")
        return {"success": True, "backup": backup_doc}

    except Exception as e:
        logger.error(f"DB-Backup Fehler: {e}")
        return {"success": False, "error": str(e)}


async def _run_files_backup() -> dict:
    """Create a ZIP archive of the application source code."""
    db = get_db()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = BACKUP_BASE_DIR / "files"
    backup_dir.mkdir(parents=True, exist_ok=True)
    archive_path = str(backup_dir / f"files_backup_{timestamp}.zip")

    PROJECT_ROOT = Path("/app")

    EXCLUDE_DIRS = {
        "node_modules", "build", "dist", ".git", ".emergent", "__pycache__",
        "backups", "test_reports", "memory", "tests", ".next",
        "venv", "env", ".venv", "yarn-cache", ".pytest_cache", ".cache",
        "storage",
    }
    EXCLUDE_FILES = {".env", ".env.backup", ".env.local", ".env.production"}
    EXCLUDE_EXTENSIONS = {".pyc", ".pyo", ".log", ".lock"}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    INCLUDE_TOPLEVEL = {
        "backend", "frontend", "desktop", "deployment",
        "update.bat", "start-all.bat", "stop-all.bat",
        "start_services.bat", "stop_services.bat",
        "UPDATE_ANLEITUNG.md", "Caddyfile",
    }

    try:
        def _build_files_zip():
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for item_name in sorted(INCLUDE_TOPLEVEL):
                    item_path = PROJECT_ROOT / item_name
                    if not item_path.exists():
                        continue

                    if item_path.is_file():
                        zf.write(str(item_path), item_name)
                    elif item_path.is_dir():
                        for root, dirs, files in os.walk(str(item_path)):
                            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                            for fname in sorted(files):
                                if fname in EXCLUDE_FILES:
                                    continue
                                if any(fname.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
                                    continue
                                file_path = os.path.join(root, fname)
                                try:
                                    if os.path.getsize(file_path) > MAX_FILE_SIZE:
                                        continue
                                except OSError:
                                    continue
                                rel_path = os.path.relpath(file_path, str(PROJECT_ROOT))
                                zf.write(file_path, rel_path)

        await asyncio.to_thread(_build_files_zip)

        file_size = os.path.getsize(archive_path) if os.path.exists(archive_path) else 0

        backup_doc = {
            "id": str(uuid.uuid4()),
            "type": "files",
            "file_path": archive_path,
            "file_name": f"files_backup_{timestamp}.zip",
            "file_size": file_size,
            "status": "success",
            "trigger": "manual",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.backups.insert_one(backup_doc)
        backup_doc.pop("_id", None)

        logger.info(f"Dateien-Backup erstellt: {archive_path} ({file_size} bytes)")
        return {"success": True, "backup": backup_doc}

    except Exception as e:
        logger.error(f"Dateien-Backup Fehler: {e}")
        return {"success": False, "error": str(e)}


# ── Retention Cleanup ──

async def _cleanup_old_backups():
    """Delete backups older than the configured retention period.

    Doppelte Sicherung:
    1. DB-registrierte Backups loeschen (DB-Eintrag + File).
    2. Verwaiste Files auf der Festplatte: alles unter BACKUP_BASE_DIR/db
       und BACKUP_BASE_DIR/files, dessen mtime aelter ist als cutoff,
       wird zusaetzlich entfernt - auch wenn KEIN DB-Eintrag dazu existiert.
       Hintergrund: Bei Server-Crash, manuellem mongodump, oder Migrationen
       entstehen Backup-Files OHNE DB-Registrierung. Diese sind dem alten
       Cleanup durch die Lappen gegangen und haben C:\\ vollgemacht.
    """
    db = get_db()
    settings = await db.app_config.find_one({"config_type": "backup"}, {"_id": 0})
    retention_days = (settings or DEFAULT_SETTINGS).get("retention_days", 7)

    from datetime import timedelta
    now = datetime.now(timezone.utc)
    cutoff_iso = (now - timedelta(days=retention_days)).isoformat()
    cutoff_ts = (now - timedelta(days=retention_days)).timestamp()

    # 1) DB-registrierte Backups
    old_backups = await db.backups.find(
        {"created_at": {"$lt": cutoff_iso}}, {"_id": 0}
    ).to_list(10000)

    deleted_db = 0
    for backup in old_backups:
        file_path = backup.get("file_path", "")
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as e:
                logger.error(f"Fehler beim Loeschen: {file_path}: {e}")
        await db.backups.delete_one({"id": backup["id"]})
        deleted_db += 1

    # 2) Verwaiste Files auf der Festplatte
    deleted_orphans = 0
    orphan_bytes = 0
    for sub in ("db", "files"):
        sub_dir = BACKUP_BASE_DIR / sub
        if not sub_dir.exists():
            continue
        for f in sub_dir.iterdir():
            if not f.is_file():
                continue
            try:
                if f.stat().st_mtime < cutoff_ts:
                    orphan_bytes += f.stat().st_size
                    f.unlink()
                    deleted_orphans += 1
            except OSError as e:
                logger.error(f"Fehler beim Loeschen verwaister Backup-Datei {f}: {e}")

    # 3) Alte Verzeichnisse wie pre-migration nach 60 Tagen weg
    legacy_cutoff_ts = (now - timedelta(days=60)).timestamp()
    for legacy in ("pre-migration",):
        legacy_dir = BACKUP_BASE_DIR / legacy
        if legacy_dir.exists() and legacy_dir.is_dir():
            try:
                if legacy_dir.stat().st_mtime < legacy_cutoff_ts:
                    shutil.rmtree(legacy_dir, ignore_errors=True)
                    logger.info(f"Legacy-Backup-Ordner geloescht: {legacy_dir}")
            except OSError as e:
                logger.error(f"Fehler beim Loeschen Legacy-Dir {legacy_dir}: {e}")

    if deleted_db or deleted_orphans:
        logger.info(
            f"Retention: {deleted_db} DB-registriertes + {deleted_orphans} verwaiste "
            f"Backup(s) geloescht ({round(orphan_bytes / (1024*1024*1024), 2)} GB freigegeben, "
            f"aelter als {retention_days} Tage)"
        )


# ── Background Scheduler ──

async def _scheduler_loop():
    """Background loop that triggers backups based on configured intervals."""
    logger.info("Backup-Scheduler gestartet")
    while True:
        try:
            db = get_db()
            settings = await db.app_config.find_one({"config_type": "backup"}, {"_id": 0})
            if not settings:
                settings = DEFAULT_SETTINGS

            now = datetime.now(timezone.utc)

            # Check DB backup
            if settings.get("db_backup_enabled", True):
                interval_h = settings.get("db_backup_interval_hours", 12)
                last_db = await db.backups.find_one(
                    {"type": "database", "status": "success"},
                    {"_id": 0},
                    sort=[("created_at", -1)],
                )
                should_run = True
                if last_db:
                    try:
                        last_time = datetime.fromisoformat(last_db["created_at"])
                        from datetime import timedelta
                        if now - last_time < timedelta(hours=interval_h):
                            should_run = False
                    except (ValueError, TypeError):
                        pass
                if should_run:
                    logger.info("Automatisches DB-Backup wird ausgeführt...")
                    result = await _run_db_backup()
                    if result.get("success"):
                        # Tag as automatic
                        await db.backups.update_one(
                            {"id": result["backup"]["id"]},
                            {"$set": {"trigger": "auto"}}
                        )

            # Check files backup
            if settings.get("files_backup_enabled", True):
                interval_h = settings.get("files_backup_interval_hours", 72)
                last_files = await db.backups.find_one(
                    {"type": "files", "status": "success"},
                    {"_id": 0},
                    sort=[("created_at", -1)],
                )
                should_run = True
                if last_files:
                    try:
                        last_time = datetime.fromisoformat(last_files["created_at"])
                        from datetime import timedelta
                        if now - last_time < timedelta(hours=interval_h):
                            should_run = False
                    except (ValueError, TypeError):
                        pass
                if should_run:
                    logger.info("Automatisches Dateien-Backup wird ausgeführt...")
                    result = await _run_files_backup()
                    if result.get("success"):
                        await db.backups.update_one(
                            {"id": result["backup"]["id"]},
                            {"$set": {"trigger": "auto"}}
                        )

            # Cleanup old backups
            await _cleanup_old_backups()

        except Exception as e:
            logger.error(f"Scheduler-Fehler: {e}")

        # Check every 15 minutes
        await asyncio.sleep(900)


async def start_backup_scheduler():
    """Start the background backup scheduler."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("Backup-Scheduler Task erstellt")


async def _restart_scheduler():
    """Restart scheduler (e.g. after settings change)."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("Backup-Scheduler neu gestartet")
