"""Simple on-the-fly image thumbnail generator with disk caching.
Used by document, device and order file endpoints to avoid streaming
multi-MB originals for tiny list thumbnails.
"""
import hashlib
import os
from io import BytesIO
from typing import Optional

from PIL import Image, ImageOps

THUMB_CACHE_DIR = os.environ.get("THUMB_CACHE_DIR", "/app/data/thumb_cache")
os.makedirs(THUMB_CACHE_DIR, exist_ok=True)


def _cache_path(source_path: str, size: int) -> str:
    st = os.stat(source_path)
    key = f"{source_path}|{st.st_size}|{int(st.st_mtime)}|{size}"
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return os.path.join(THUMB_CACHE_DIR, f"{h}.jpg")


def make_thumbnail(source_path: str, size: int = 200) -> Optional[bytes]:
    """Return JPEG bytes of a thumbnail of the given image file (max edge = size, preserving aspect).
    Caches results on disk. Returns None on failure (caller should fall back to original).
    """
    if size <= 0 or size > 1024:
        size = 200
    try:
        cache = _cache_path(source_path, size)
        if os.path.exists(cache):
            with open(cache, "rb") as f:
                return f.read()

        with Image.open(source_path) as im:
            im = ImageOps.exif_transpose(im)
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.thumbnail((size, size), Image.LANCZOS)
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=75, optimize=True)
            data = buf.getvalue()

        try:
            with open(cache, "wb") as f:
                f.write(data)
        except Exception:
            pass  # cache write failure is non-fatal
        return data
    except Exception:
        return None


def make_thumbnail_from_bytes(raw: bytes, size: int = 200) -> Optional[bytes]:
    """Same as make_thumbnail but for in-memory bytes (e.g. GridFS). No caching (no stable key)."""
    if size <= 0 or size > 1024:
        size = 200
    try:
        with Image.open(BytesIO(raw)) as im:
            im = ImageOps.exif_transpose(im)
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.thumbnail((size, size), Image.LANCZOS)
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=75, optimize=True)
            return buf.getvalue()
    except Exception:
        return None
