"""
Ollama-Client fuer lokale KI-Analyse von Dokumenten.
Ersetzt die frueheren Aufrufe an emergentintegrations.llm.chat (GPT-4o / Gemini).

Nutzt Vision-faehige Modelle wie gemma3:4b, die Bilder direkt lesen koennen.
PDFs werden seitenweise in Bilder konvertiert (via PyMuPDF).
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

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "180"))
OLLAMA_MAX_PDF_PAGES = int(os.environ.get("OLLAMA_MAX_PDF_PAGES", "3"))
OLLAMA_IMAGE_MAX_DIM = int(os.environ.get("OLLAMA_IMAGE_MAX_DIM", "1400"))

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
    mdl = model or OLLAMA_MODEL
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
                r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
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
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            return r.status_code == 200
    except Exception:
        return False
