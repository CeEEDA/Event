"""
Software Downloads - Desktop App Installer
============================================
Stellt die Installer-Dateien fuer Mac und Windows zum Download bereit.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger("software_downloads")
router = APIRouter(prefix="/api/system/downloads", tags=["Software Downloads"])

DESKTOP_DIR = Path(__file__).parent.parent / "static" / "desktop-installers"


@router.get("/mac")
async def download_mac_installer():
    filepath = DESKTOP_DIR / "install-mac.sh"
    if not filepath.exists():
        raise HTTPException(404, "Mac-Installer nicht gefunden")
    return FileResponse(
        path=str(filepath),
        filename="install-mac.sh",
        media_type="application/x-sh",
    )


@router.get("/win-bat")
async def download_win_bat():
    filepath = DESKTOP_DIR / "install-win.bat"
    if not filepath.exists():
        raise HTTPException(404, "Windows-Installer nicht gefunden")
    return FileResponse(
        path=str(filepath),
        filename="install-win.bat",
        media_type="application/x-bat",
    )


@router.get("/win-ps1")
async def download_win_ps1():
    filepath = DESKTOP_DIR / "install-win.ps1"
    if not filepath.exists():
        raise HTTPException(404, "Windows-Installer nicht gefunden")
    return FileResponse(
        path=str(filepath),
        filename="install-win.ps1",
        media_type="application/octet-stream",
    )


@router.get("/server-setup")
async def download_server_setup():
    filepath = DESKTOP_DIR / "server-setup.sh"
    if not filepath.exists():
        raise HTTPException(404, "Server-Setup nicht gefunden")
    return FileResponse(
        path=str(filepath),
        filename="server-setup.sh",
        media_type="application/x-sh",
    )


@router.get("/db-migrate")
async def download_db_migrate():
    filepath = DESKTOP_DIR / "db-migrate.sh"
    if not filepath.exists():
        raise HTTPException(404, "DB-Migrate nicht gefunden")
    return FileResponse(
        path=str(filepath),
        filename="db-migrate.sh",
        media_type="application/x-sh",
    )


@router.get("/deploy")
async def download_deploy():
    filepath = DESKTOP_DIR / "deploy.sh"
    if not filepath.exists():
        raise HTTPException(404, "Deploy-Script nicht gefunden")
    return FileResponse(
        path=str(filepath),
        filename="deploy.sh",
        media_type="application/x-sh",
    )


@router.get("/info")
async def get_download_info():
    files = []
    for name, label, platform, category in [
        ("install-mac.sh", "Mac Desktop App", "mac", "desktop"),
        ("install-win.bat", "Windows Desktop App (.bat)", "windows", "desktop"),
        ("install-win.ps1", "Windows Desktop App (.ps1)", "windows", "desktop"),
        ("server-setup.sh", "Server-Installation", "linux", "server"),
        ("db-migrate.sh", "Datenbank-Migration", "linux", "server"),
        ("deploy.sh", "Code-Deployment", "linux", "server"),
    ]:
        filepath = DESKTOP_DIR / name
        exists = filepath.exists()
        size = filepath.stat().st_size if exists else 0
        files.append({
            "filename": name,
            "label": label,
            "platform": platform,
            "category": category,
            "available": exists,
            "size_bytes": size,
        })
    return {"files": files, "version": "2.0.0"}
