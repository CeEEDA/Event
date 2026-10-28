"""ffmpeg fuer die Durchsagen-Verarbeitung: finden, Version pruefen, auf Windows selbst installieren/aktualisieren.

Quelle (Windows): https://www.gyan.dev/ffmpeg/builds/ (release-essentials). Ablage: <LiveDir>/tools/ffmpeg/bin/ffmpeg.exe.
Auf Linux wird nur das Systempaket genutzt (kein Selbst-Download)."""
import asyncio
import glob
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools" / "ffmpeg"
EXE = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
RELEASE_VERSION_URL = "https://www.gyan.dev/ffmpeg/builds/release-version"
RELEASE_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

_state = {"running": False, "ok": None, "started_at": None, "finished_at": None, "message": "", "progress_mb": 0}
_cache = {"latest": None, "latest_at": 0.0}


def find_ffmpeg() -> Optional[str]:
    env = os.environ.get("FFMPEG_BIN")
    if env and Path(env).exists():
        return env
    own = TOOLS_DIR / "bin" / EXE
    if own.exists():
        return str(own)
    found = shutil.which("ffmpeg")
    if found:
        return found
    if sys.platform == "win32":
        cands = [r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"]
        for base in (os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
            if base:
                cands += glob.glob(os.path.join(base, "ffmpeg*", "bin", "ffmpeg.exe"))
                cands += glob.glob(os.path.join(base, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "ffmpeg-*", "bin", "ffmpeg.exe"))
        for c in cands:
            if Path(c).exists():
                return c
    return None


def local_version(binary: Optional[str] = None) -> Optional[str]:
    binary = binary or find_ffmpeg()
    if not binary:
        return None
    try:
        kwargs = {"creationflags": 0x08000000} if sys.platform == "win32" else {}
        out = subprocess.run([binary, "-version"], capture_output=True, text=True, timeout=15, **kwargs).stdout
        m = re.search(r"ffmpeg version\s+(\S+)", out)
        return m.group(1) if m else None
    except Exception:
        return None


def _num(v: Optional[str]) -> tuple:
    m = re.match(r"n?(\d+)(?:\.(\d+))?(?:\.(\d+))?", v or "")
    return tuple(int(x or 0) for x in m.groups()) if m else ()


async def latest_version() -> Optional[str]:
    import time
    if _cache["latest"] and time.monotonic() - _cache["latest_at"] < 3600:
        return _cache["latest"]
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            r = await c.get(RELEASE_VERSION_URL)
            r.raise_for_status()
            v = r.text.strip()
            if re.match(r"^\d+\.\d+", v):
                _cache.update(latest=v, latest_at=time.monotonic())
                return v
    except Exception as e:
        logger.debug(f"ffmpeg Versionsabfrage: {e}")
    return _cache["latest"]


async def status() -> dict:
    binary = find_ffmpeg()
    local = local_version(binary) if binary else None
    latest = await latest_version() if sys.platform == "win32" else None
    update = bool(latest and local and _num(latest) > _num(local))
    return {"bin": binary, "version": local, "latest": latest, "update_available": update, "tools_dir": str(TOOLS_DIR),
            "self_install": sys.platform == "win32", "install": dict(_state)}


def _download_and_extract() -> str:
    """Blockierend (laeuft im Thread): Zip laden, entpacken, nach TOOLS_DIR/bin verschieben."""
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    tmpdir = Path(tempfile.mkdtemp(prefix="ffmpeg_dl_"))
    zip_path = tmpdir / "ffmpeg.zip"
    try:
        with httpx.stream("GET", RELEASE_ZIP_URL, follow_redirects=True, timeout=120) as r:
            r.raise_for_status()
            got = 0
            with open(zip_path, "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
                    got += len(chunk)
                    _state["progress_mb"] = round(got / 1048576)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmpdir / "x")
        exe = next(Path(tmpdir / "x").rglob(EXE), None)
        if not exe:
            raise RuntimeError("ffmpeg.exe nicht im Archiv gefunden")
        new_bin = exe.parent
        target_bin = TOOLS_DIR / "bin"
        if target_bin.exists():
            shutil.rmtree(target_bin, ignore_errors=True)
        shutil.copytree(new_bin, target_bin)
        v = local_version(str(target_bin / EXE))
        if not v:
            raise RuntimeError("ffmpeg startet nach Installation nicht")
        return v
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


async def install_or_update(force: bool = False) -> dict:
    """Windows: ffmpeg nach tools/ffmpeg installieren bzw. aktualisieren. Linux: nur Hinweis."""
    if _state["running"]:
        return dict(_state)
    if sys.platform != "win32":
        _state.update(ok=find_ffmpeg() is not None, finished_at=datetime.now(timezone.utc).isoformat(),
                      message="Auf Linux wird das Systempaket genutzt (apt install ffmpeg) - kein Selbst-Download.")
        return dict(_state)
    st = await status()
    if st["bin"] and not st["update_available"] and not force:
        _state.update(ok=True, message=f"ffmpeg {st['version']} ist aktuell", finished_at=datetime.now(timezone.utc).isoformat())
        return dict(_state)
    _state.update(running=True, ok=None, started_at=datetime.now(timezone.utc).isoformat(), finished_at=None, message="Download laeuft...", progress_mb=0)
    try:
        v = await asyncio.to_thread(_download_and_extract)
        _state.update(ok=True, message=f"ffmpeg {v} installiert nach {TOOLS_DIR / 'bin'}")
        logger.info(_state["message"])
    except Exception as e:
        _state.update(ok=False, message=f"ffmpeg Installation fehlgeschlagen: {e}")
        logger.warning(_state["message"])
    finally:
        _state.update(running=False, finished_at=datetime.now(timezone.utc).isoformat())
    return dict(_state)


async def ensure_on_startup():
    """Beim Backend-Start: fehlt ffmpeg oder ist veraltet (Windows), automatisch installieren/aktualisieren."""
    try:
        st = await status()
        if not st["bin"]:
            logger.warning("ffmpeg fehlt - Durchsagen werden ungeprueft uebernommen" + (" - starte Selbst-Installation" if st["self_install"] else ""))
        elif st["update_available"]:
            logger.info(f"ffmpeg {st['version']} -> {st['latest']} verfuegbar - aktualisiere")
        if st["self_install"] and (not st["bin"] or st["update_available"]):
            await install_or_update()
    except Exception as e:
        logger.warning(f"ffmpeg Startpruefung: {e}")
