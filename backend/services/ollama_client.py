"""
Ollama-Client fuer lokale KI-Analyse von Dokumenten.
Ersetzt die frueheren Aufrufe an emergentintegrations.llm.chat (GPT-4o / Gemini).

Nutzt Vision-faehige Modelle wie gemma3:4b, die Bilder direkt lesen koennen.
PDFs werden seitenweise in Bilder konvertiert (via PyMuPDF).

Konfiguration kommt aus der DB-Collection 'ollama_config' (per Admin-UI gepflegt).
Falls dort kein Eintrag vorliegt, fallen wir auf .env-Defaults zurueck.
"""
import os
import base64
import json
import io
import logging
from typing import Optional

import httpx
import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Defaults aus Environment (Fallback wenn DB-Config fehlt)
# ──────────────────────────────────────────────────────────
DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:1b")
DEFAULT_OLLAMA_TEXT_MODEL = os.environ.get("OLLAMA_TEXT_MODEL", "gemma2:2b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "600"))
OLLAMA_MAX_PDF_PAGES = int(os.environ.get("OLLAMA_MAX_PDF_PAGES", "3"))
OLLAMA_MAX_TEXT_CHARS = int(os.environ.get("OLLAMA_MAX_TEXT_CHARS", "12000"))
OLLAMA_IMAGE_MAX_DIM = int(os.environ.get("OLLAMA_IMAGE_MAX_DIM", "1400"))

# DB-Handle wird aus server.py via set_db() injiziert (vermeidet Import-Zyklus).
_db = None


def set_db(db):
    """Wird von server.py beim Start aufgerufen. Bindet den Mongo-DB-Handle ein."""
    global _db
    _db = db


async def get_ollama_config() -> dict:
    """Liest die Live-Konfiguration aus der DB-Collection ollama_config.
    Fallback: Environment-Defaults. Niemals None - immer ein vollstaendiges dict."""
    cfg = {}
    if _db is not None:
        try:
            doc = await _db.ollama_config.find_one({"key": "ollama"}, {"_id": 0})
            if doc:
                cfg = doc
        except Exception as e:
            logger.warning(f"[ollama] DB-Config-Lookup fehlgeschlagen, nutze Env-Defaults: {e}")
    return {
        "url": (cfg.get("url") or DEFAULT_OLLAMA_URL).rstrip("/"),
        "api_key": cfg.get("api_key") or "",
        "model": cfg.get("model") or DEFAULT_OLLAMA_MODEL,
        "text_model": cfg.get("text_model") or DEFAULT_OLLAMA_TEXT_MODEL,
    }


def _auth_headers(api_key: str) -> dict:
    """Auth-Header für vorgeschaltete Reverse-Proxys (z.B. Nginx vor Ollama).
    Sendet sowohl X-Api-Key als auch Authorization: Bearer - der Proxy
    nimmt sich das, was er versteht."""
    if not api_key:
        return {}
    return {
        "X-Api-Key": api_key,
        "Authorization": f"Bearer {api_key}",
    }


# Semaphore: Nur EINE Analyse zur Zeit laufen lassen, damit bei vielen parallelen
# Uploads nicht der ganze Rechner hängt. Ollama selbst kann zwar parallel, aber auf
# CPU-only Systemen ist das kontraproduktiv.
_OLLAMA_CONCURRENCY = int(os.environ.get("OLLAMA_CONCURRENCY", "1"))
_ollama_semaphore = None


def _get_semaphore():
    """Lazy-init des Semaphors an den laufenden Event-Loop gebunden."""
    import asyncio
    global _ollama_semaphore
    if _ollama_semaphore is None:
        _ollama_semaphore = asyncio.Semaphore(_OLLAMA_CONCURRENCY)
    return _ollama_semaphore


def _image_to_base64(pil_image: Image.Image) -> str:
    """Downscale + JPEG-encode ein PIL-Bild und gibt base64 zurueck."""
    img = pil_image
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > OLLAMA_IMAGE_MAX_DIM:
        scale = OLLAMA_IMAGE_MAX_DIM / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _extract_text_from_pdf(file_path: str, max_pages: int = 10) -> str:
    """Extrahiert Text direkt aus einem PDF via PyMuPDF (kein OCR).
    Funktioniert bei allen digital erstellten PDFs (Rechnungen, Vertraege etc.).
    Gibt leeren String zurueck, wenn das PDF nur Bilder enthaelt (echter Scan)."""
    try:
        with fitz.open(file_path) as pdf:
            pages = min(len(pdf), max_pages)
            parts = []
            for i in range(pages):
                parts.append(pdf[i].get_text("text"))
            text = "\n".join(parts).strip()
            return text
    except Exception as e:
        logger.warning(f"[ollama] PDF-Text-Extraktion fehlgeschlagen: {e}")
        return ""


def _file_to_image_b64_list(file_path: str, mime_type: str) -> list:
    """Konvertiert ein Dokument in eine Liste von base64-kodierten Bildern.

    - PDFs: max. OLLAMA_MAX_PDF_PAGES Seiten (Standard: 3) als Bilder.
    - Bilder: direkt (ein einziges base64).
    """
    mt = (mime_type or "").lower()
    if mt == "application/pdf" or file_path.lower().endswith(".pdf"):
        images = []
        with fitz.open(file_path) as pdf:
            total_pages = min(len(pdf), OLLAMA_MAX_PDF_PAGES)
            for i in range(total_pages):
                page = pdf[i]
                # 150 dpi ergibt brauchbare OCR-Qualitaet bei akzeptabler Groesse
                pix = page.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                images.append(_image_to_base64(img))
        return images
    elif mt.startswith("image/") or any(file_path.lower().endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif")):
        with Image.open(file_path) as img:
            return [_image_to_base64(img)]
    else:
        # Fallback: als Bytes senden, Ollama laesst dann die Bilder leer
        return []


async def ollama_chat_vision(
    system_prompt: str,
    user_text: str,
    file_path: Optional[str] = None,
    mime_type: Optional[str] = None,
    model: Optional[str] = None,
    want_json: bool = True,
) -> str:
    """Sendet eine Chat-Anfrage an Ollama mit optionalem Datei-Bild-Anhang.

    Gibt den reinen Antworttext zurueck (ohne JSON-Parsing).
    Bei Fehlern wird eine Exception geworfen."""
    cfg = await get_ollama_config()
    mdl = model or cfg["model"]
    images = []
    if file_path:
        try:
            images = _file_to_image_b64_list(file_path, mime_type or "")
        except Exception as e:
            logger.warning(f"[ollama] Datei konnte nicht in Bilder konvertiert werden: {e}")
            images = []

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text, **({"images": images} if images else {})},
    ]
    payload = {
        "model": mdl,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_ctx": 8192,
        },
    }
    if want_json:
        payload["format"] = "json"

    sem = _get_semaphore()
    async with sem:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            try:
                r = await client.post(f"{cfg['url']}/api/chat", json=payload,
                                       headers=_auth_headers(cfg["api_key"]))
            except Exception as e:
                logger.error(f"[ollama] HTTP-Request fehlgeschlagen: {type(e).__name__}: {e}", exc_info=True)
                raise
            if r.status_code != 200:
                logger.error(f"[ollama] HTTP {r.status_code}: {r.text[:500]}")
                r.raise_for_status()
            try:
                data = r.json()
            except Exception as e:
                logger.error(f"[ollama] Antwort kein JSON: {r.text[:500]}")
                raise
    return (data.get("message") or {}).get("content", "")


def parse_json_response(text: str) -> dict:
    """Robustes JSON-Parsing - entfernt Markdown-Fences und whitespace."""
    t = (text or "").strip()
    if t.startswith("```"):
        # Fence-Markierungen entfernen
        lines = t.splitlines()
        inner = []
        in_block = False
        for ln in lines:
            if ln.startswith("```") and not in_block:
                in_block = True
                continue
            if ln.startswith("```") and in_block:
                break
            if in_block:
                inner.append(ln)
        t = "\n".join(inner).strip()
    # Manche Modelle schreiben Text vor/nach dem JSON - extrahiere via { ... }
    if not t.startswith("{"):
        start = t.find("{")
        end = t.rfind("}")
        if start >= 0 and end > start:
            t = t[start:end + 1]
    return json.loads(t)


async def ollama_is_reachable() -> bool:
    """Prueft ob Ollama erreichbar ist."""
    cfg = await get_ollama_config()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{cfg['url']}/api/tags",
                                 headers=_auth_headers(cfg["api_key"]))
            return r.status_code == 200
    except Exception:
        return False


async def ollama_list_models() -> list:
    """Liefert die installierten Modelle der konfigurierten Ollama-Instanz."""
    cfg = await get_ollama_config()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{cfg['url']}/api/tags",
                                 headers=_auth_headers(cfg["api_key"]))
            if r.status_code != 200:
                return []
            data = r.json() or {}
            return [m.get("name") for m in (data.get("models") or []) if m.get("name")]
    except Exception:
        return []


async def analyze_document_smart(
    system_prompt: str,
    file_path: str,
    mime_type: str,
    user_text_vision: str = "Analysiere dieses Dokument und gib ein JSON zurueck.",
    want_json: bool = True,
) -> tuple:
    """Hybrid-Analyse: versucht zuerst Text-Extraktion (schnell, 5-10s),
    faellt bei reinen Bildern/Scans auf Vision-Modell zurueck (langsam, 30-180s).

    Gibt (response_text, mode) zurueck, wobei mode 'text' oder 'vision' ist."""
    mt = (mime_type or "").lower()
    cfg = await get_ollama_config()
    # 1) Versuche Text-Extraktion fuer PDFs
    if mt == "application/pdf" or file_path.lower().endswith(".pdf"):
        extracted = _extract_text_from_pdf(file_path, max_pages=OLLAMA_MAX_PDF_PAGES)
        # Mind. 80 Zeichen = "echter" Text, nicht nur Metadaten
        if extracted and len(extracted.strip()) >= 80:
            trimmed = extracted[:OLLAMA_MAX_TEXT_CHARS]
            logger.info(f"[ollama] Text-first: {len(trimmed)} Zeichen aus PDF extrahiert, Modell={cfg['text_model']}")
            text_prompt = (
                "Hier ist der Text eines Dokuments (direkt aus dem PDF extrahiert):\n\n"
                f"----- DOKUMENT ANFANG -----\n{trimmed}\n----- DOKUMENT ENDE -----\n\n"
                "Analysiere das Dokument und gib ein JSON zurueck (keine weiteren Erklaerungen)."
            )
            resp = await ollama_chat_vision(
                system_prompt=system_prompt,
                user_text=text_prompt,
                file_path=None,      # Kein Bild-Anhang - wir haben Text
                mime_type=None,
                model=cfg["text_model"],
                want_json=want_json,
            )
            return resp, "text"

    # 2) Fallback auf Vision-Modell (Scans, Bilder, text-lose PDFs)
    logger.info(f"[ollama] Vision-Fallback: {file_path}, Modell={cfg['model']}")
    resp = await ollama_chat_vision(
        system_prompt=system_prompt,
        user_text=user_text_vision,
        file_path=file_path,
        mime_type=mime_type,
        model=cfg["model"],
        want_json=want_json,
    )
    return resp, "vision"
