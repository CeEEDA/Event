"""HTTP-Header Helper.

Behandelt die Kodierung von Dateinamen fuer Content-Disposition-Header, damit
Umlaute (\u00fc, \u00e4, \u00f6, \u00df) und andere Nicht-ASCII-Zeichen keinen
UnicodeEncodeError in starlette/uvicorn werfen (latin-1 kann nur 0-255).
"""
from urllib.parse import quote


def content_disposition(filename: str, disposition: str = "inline") -> str:
    """Erzeuge einen RFC 5987 / RFC 6266 konformen Content-Disposition-Header.

    Enthaelt sowohl den ASCII-Fallback ("filename=...") fuer alte Clients
    als auch die UTF-8 kodierte Variante ("filename*=UTF-8''...") fuer moderne
    Browser. So funktioniert der Download in allen gaengigen Browsern und
    verhindert den UnicodeEncodeError beim latin-1 Encode-Schritt.

    Args:
        filename: Der Original-Dateiname (kann Umlaute etc. enthalten).
        disposition: "inline" (im Browser anzeigen) oder "attachment" (Download).

    Returns:
        Header-Wert, direkt in headers={"Content-Disposition": ...} verwendbar.
    """
    safe_name = filename or "download"
    ascii_fallback = safe_name.encode("ascii", errors="replace").decode("ascii").replace("?", "_")
    utf8_encoded = quote(safe_name, safe="")
    return f"{disposition}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{utf8_encoded}"
