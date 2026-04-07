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


@router.get("/info")
async def get_download_info():
    files = []
    for name, label, platform in [
        ("install-mac.sh", "Mac Installer", "mac"),
        ("install-win.bat", "Windows Installer (.bat)", "windows"),
        ("install-win.ps1", "Windows Installer (.ps1)", "windows"),
    ]:
        filepath = DESKTOP_DIR / name
        exists = filepath.exists()
        size = filepath.stat().st_size if exists else 0
        files.append({
            "filename": name,
            "label": label,
            "platform": platform,
            "available": exists,
            "size_bytes": size,
        })
    return {"files": files, "version": "2.0.0"}
