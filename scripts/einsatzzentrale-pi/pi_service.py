"""Einsatzzentrale Pi-Service — Smart Proxy + Offline-Cache.

Laeuft als systemd-Service auf Port 8001 auf dem Pi. Die Aufgaben:

  1. Liefert die kiosk-page (HTML) lokal aus -> kein Cloud-Roundtrip beim Boot.
  2. Reverse-Proxy fuer /api/*: GET-Anfragen werden aggressiv in SQLite gecached,
     POST/PUT/DELETE bei Online direkt durchgereicht, bei Offline in eine
     Outbox-Queue geschrieben und spaeter beim naechsten Sync abgesetzt.
  3. Sync-Worker (alle 2 Min): Holt wichtige Daten (Aktive Aufträge, Diary,
     Trupps, Assets) vom Cloud-Backend und cached sie. Photos/PDFs werden bei
     Bedarf in einen lokalen blob-Folder kopiert.
  4. Retention: Cache-Eintraege aelter als 90 Tage werden taeglich geloescht.
  5. Heartbeat: Meldet sich alle 2 Min beim Cloud-Backend als "online".

Konfiguration via /etc/einsatzzentrale-pi.conf (vom Install-Script erstellt):
    CLOUD_URL=https://...
    PI_ID=...
    PI_KEY=...
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
CONFIG_PATH = Path(os.environ.get("PI_CONFIG", "/etc/einsatzzentrale-pi.conf"))
DATA_DIR = Path(os.environ.get("PI_DATA_DIR", "/var/lib/einsatzzentrale-pi"))
BLOB_DIR = DATA_DIR / "blobs"
DB_PATH = DATA_DIR / "cache.db"
LOG_PATH = Path(os.environ.get("PI_LOG", "/var/log/einsatzzentrale-pi.log"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
BLOB_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("pi-service")


def load_config() -> Dict[str, str]:
    cfg: Dict[str, str] = {}
    if CONFIG_PATH.exists():
        for ln in CONFIG_PATH.read_text().splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, _, v = ln.partition("=")
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg


CFG = load_config()
CLOUD_URL = CFG.get("CLOUD_URL", os.environ.get("CLOUD_URL", "")).rstrip("/")
PI_ID = CFG.get("PI_ID", os.environ.get("PI_ID", ""))
PI_KEY = CFG.get("PI_KEY", os.environ.get("PI_KEY", ""))
SYNC_INTERVAL_SEC = int(CFG.get("SYNC_INTERVAL_SEC", "120"))
RETENTION_DAYS = int(CFG.get("RETENTION_DAYS", "90"))

if not CLOUD_URL:
    log.error("CLOUD_URL nicht gesetzt - Service kann nicht zur Cloud syncen.")

KIOSK_HTML_PATH = Path(os.environ.get(
    "PI_KIOSK_HTML",
    str(Path(__file__).resolve().parent / "kiosk.html"),
))

# ---------------------------------------------------------------------------
# SQLite-Cache
# ---------------------------------------------------------------------------
def _db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, isolation_level=None, timeout=10)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    return c


def init_db() -> None:
    with _db() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS cache_get (
                url_key   TEXT PRIMARY KEY,   -- z.B. "GET /api/einsatzzentrale/orders?..."
                status    INTEGER NOT NULL,
                content_type TEXT,
                body      BLOB NOT NULL,
                etag      TEXT,
                fetched_at TEXT NOT NULL      -- ISO UTC
            );
            CREATE INDEX IF NOT EXISTS idx_cache_get_fetched ON cache_get(fetched_at);

            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                method   TEXT NOT NULL,
                path     TEXT NOT NULL,
                headers  TEXT NOT NULL,       -- JSON
                body     BLOB,
                content_type TEXT,
                created_at TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                last_error TEXT,
                done INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS state (
                k TEXT PRIMARY KEY,
                v TEXT
            );
            """
        )


def state_get(k: str) -> Optional[str]:
    with _db() as c:
        row = c.execute("SELECT v FROM state WHERE k=?", (k,)).fetchone()
    return row[0] if row else None


def state_set(k: str, v: str) -> None:
    with _db() as c:
        c.execute(
            "INSERT INTO state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            (k, v),
        )


def cache_put(method: str, path: str, query: str, status: int, ct: str, body: bytes) -> None:
    key = f"{method} {path}?{query}"
    with _db() as c:
        c.execute(
            "INSERT OR REPLACE INTO cache_get(url_key,status,content_type,body,fetched_at) VALUES(?,?,?,?,?)",
            (key, status, ct, body, datetime.now(timezone.utc).isoformat()),
        )


def cache_get(method: str, path: str, query: str):
    key = f"{method} {path}?{query}"
    with _db() as c:
        row = c.execute(
            "SELECT status,content_type,body,fetched_at FROM cache_get WHERE url_key=?",
            (key,),
        ).fetchone()
    return row


def outbox_add(method: str, path: str, headers: Dict[str, str], body: bytes, ct: str) -> int:
    with _db() as c:
        cur = c.execute(
            "INSERT INTO outbox(method,path,headers,body,content_type,created_at) VALUES(?,?,?,?,?,?)",
            (method, path, json.dumps(headers), body, ct, datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def outbox_pending() -> List[sqlite3.Row]:
    with _db() as c:
        c.row_factory = sqlite3.Row
        return c.execute(
            "SELECT * FROM outbox WHERE done=0 ORDER BY id ASC LIMIT 50"
        ).fetchall()


def outbox_done(oid: int) -> None:
    with _db() as c:
        c.execute("UPDATE outbox SET done=1 WHERE id=?", (oid,))


def outbox_fail(oid: int, err: str) -> None:
    with _db() as c:
        c.execute("UPDATE outbox SET attempts=attempts+1, last_error=? WHERE id=?", (err, oid))


def retention_cleanup() -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
    with _db() as c:
        cur = c.execute("DELETE FROM cache_get WHERE fetched_at < ?", (cutoff,))
        n1 = cur.rowcount
        cur = c.execute("DELETE FROM outbox WHERE done=1 AND created_at < ?", (cutoff,))
        n2 = cur.rowcount
    if n1 or n2:
        log.info(f"Retention: {n1} cache + {n2} outbox-Einträge geloescht (>{RETENTION_DAYS} Tage)")
    return n1 + n2


# ---------------------------------------------------------------------------
# Sync / Heartbeat
# ---------------------------------------------------------------------------
SYNC_URLS = [
    # Diese URLs werden alle 2 Min im Hintergrund vom Cloud-Backend geholt
    # und in den Cache geschrieben. Token-Anforderungen werden mit dem zuletzt
    # bekannten User-Token gemacht (siehe state['last_token']).
    "/api/einsatzzentrale/users",
    "/api/einsatzzentrale/orders",
]


_sync_lock = asyncio.Lock()
_online: bool = True  # optimistisch starten - faellt bei erstem Fehler auf False


async def _heartbeat(client: httpx.AsyncClient) -> None:
    if not (PI_ID and PI_KEY):
        return
    try:
        r = await client.post(
            f"{CLOUD_URL}/api/einsatzzentrale/pis/{PI_ID}/heartbeat",
            params={"key": PI_KEY},
            timeout=10,
        )
        if r.status_code == 200:
            globals()["_online"] = True
    except Exception:
        globals()["_online"] = False


async def _sync_url(client: httpx.AsyncClient, url: str, headers: Dict[str, str]) -> None:
    try:
        r = await client.get(f"{CLOUD_URL}{url}", headers=headers, timeout=15)
        if 200 <= r.status_code < 400:
            cache_put("GET", url.split("?")[0], url.split("?", 1)[1] if "?" in url else "",
                      r.status_code, r.headers.get("content-type", ""), r.content)
    except Exception as ex:
        log.warning(f"Sync {url} fehlgeschlagen: {ex}")


async def _flush_outbox(client: httpx.AsyncClient) -> None:
    rows = outbox_pending()
    if not rows:
        return
    for row in rows:
        try:
            headers = json.loads(row["headers"]) if row["headers"] else {}
            r = await client.request(
                row["method"],
                f"{CLOUD_URL}{row['path']}",
                content=row["body"],
                headers=headers,
                timeout=30,
            )
            if 200 <= r.status_code < 500:
                outbox_done(row["id"])
                log.info(f"Outbox flushed: {row['method']} {row['path']} -> {r.status_code}")
            else:
                outbox_fail(row["id"], f"HTTP {r.status_code}")
        except Exception as ex:
            outbox_fail(row["id"], str(ex))


async def sync_worker() -> None:
    """Background-Task: alle SYNC_INTERVAL_SEC Sekunden."""
    last_retention = 0.0
    while True:
        async with _sync_lock:
            try:
                async with httpx.AsyncClient() as client:
                    await _heartbeat(client)
                    await _flush_outbox(client)
                    tok = state_get("last_token")
                    headers = {"Authorization": f"Bearer {tok}"} if tok else {}
                    for u in SYNC_URLS:
                        await _sync_url(client, u, headers)
                    # Aktiver Auftrag (falls hinterlegt) zusaetzlich syncen
                    active_pk = state_get("active_order_pk")
                    if active_pk:
                        for u in [
                            f"/api/einsatzzentrale/orders/{active_pk}",
                            f"/api/orders/{active_pk}/diary",
                            f"/api/orders/{active_pk}/trupps",
                            f"/api/orders/epirent/{active_pk}/assets",
                            f"/api/orders/epirent/{active_pk}/generators",
                            f"/api/orders/order-documents/{active_pk}",
                        ]:
                            await _sync_url(client, u, headers)
            except Exception as ex:
                log.exception(f"Sync-Worker: {ex}")

            # Retention 1x pro Tag
            if time.time() - last_retention > 86400:
                retention_cleanup()
                last_retention = time.time()

        await asyncio.sleep(SYNC_INTERVAL_SEC)


# ---------------------------------------------------------------------------
# FastAPI App + Proxy-Handler
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(sync_worker())
    log.info(f"Pi-Service gestartet (CLOUD_URL={CLOUD_URL}, PI_ID={PI_ID[:8] if PI_ID else 'NONE'}…)")
    yield
    task.cancel()


app = FastAPI(title="Einsatzzentrale Pi-Service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
@app.get("/kiosk")
async def kiosk_root():
    """Liefert die Kiosk-HTML aus.

    Strategie:
      1. Wenn online: live vom Cloud-Backend holen + lokal cachen (so kommen
         HTML-Updates sofort an, der Pi muss nicht neu installiert werden).
      2. Wenn offline: lokal gecachte HTML verwenden.
      3. Bei Erstaufruf ohne Cache: Redirect zur Cloud.
    """
    if CLOUD_URL and _online:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{CLOUD_URL}/api/einsatzzentrale/kiosk-page")
            if 200 <= r.status_code < 300 and r.content:
                # Lokale Kopie aktualisieren (fuer Offline-Fallback)
                try:
                    KIOSK_HTML_PATH.write_bytes(r.content)
                except Exception as ex:
                    log.warning(f"Konnte kiosk.html nicht lokal cachen: {ex}")
                return Response(content=r.content, media_type="text/html")
        except Exception as ex:
            log.warning(f"Cloud kiosk-page Fetch fehlgeschlagen: {ex}")
    # Offline-Fallback: lokale Kopie
    if KIOSK_HTML_PATH.exists():
        return FileResponse(KIOSK_HTML_PATH, media_type="text/html")
    if CLOUD_URL:
        return RedirectResponse(f"{CLOUD_URL}/api/einsatzzentrale/kiosk-page")
    return Response(content="<h1>Pi-Service: weder Cloud noch lokaler Cache verfuegbar</h1>",
                    status_code=503, media_type="text/html")


@app.get("/pi-status")
async def pi_status():
    """Eigener Endpoint: zeigt den lokalen Service-Status."""
    with _db() as c:
        cache_count = c.execute("SELECT COUNT(*) FROM cache_get").fetchone()[0]
        outbox_pending_n = c.execute("SELECT COUNT(*) FROM outbox WHERE done=0").fetchone()[0]
        outbox_total = c.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
    return {
        "service": "einsatzzentrale-pi",
        "cloud_url": CLOUD_URL,
        "pi_id": PI_ID,
        "online": _online,
        "cache_entries": cache_count,
        "outbox_pending": outbox_pending_n,
        "outbox_total": outbox_total,
        "retention_days": RETENTION_DAYS,
        "sync_interval_sec": SYNC_INTERVAL_SEC,
        "now": datetime.now(timezone.utc).isoformat(),
    }


# Generischer Proxy fuer alle /api/* Pfade
@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request) -> Response:
    full_path = "/api/" + path
    method = request.method
    query = request.url.query
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "content-length", "connection")}

    if method == "GET":
        # Token aus dem Request speichern (fuer Sync-Worker)
        auth = headers.get("authorization") or headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            state_set("last_token", auth[7:])

        # Cache-Eintrag pruefen
        cached = cache_get("GET", full_path, query)

        # Live holen mit 2 Retry-Versuchen bei DNS/Netzwerk-Aussetzern
        last_err = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(f"{CLOUD_URL}{full_path}",
                                          headers=headers,
                                          params=dict(request.query_params))
                if 200 <= r.status_code < 400:
                    cache_put("GET", full_path, query, r.status_code,
                              r.headers.get("content-type", ""), r.content)
                    globals()["_online"] = True
                    return Response(content=r.content, status_code=r.status_code,
                                     media_type=r.headers.get("content-type"))
                # Bei 4xx (401/403/etc) liefere Cloud-Response transparent (kein Retry)
                return Response(content=r.content, status_code=r.status_code,
                                 media_type=r.headers.get("content-type"))
            except Exception as ex:
                last_err = ex
                if attempt < 2:
                    await asyncio.sleep(0.6 * (attempt + 1))
                    continue
        log.warning(f"Cloud GET {full_path} nach Retry fehlgeschlagen: {last_err}")
        globals()["_online"] = False

        # Cloud nicht erreichbar -> liefere Cache wenn vorhanden
        if cached:
            status, ct, b, fetched_at = cached
            return Response(content=b, status_code=status,
                             media_type=ct,
                             headers={"X-Pi-Cache": "HIT-OFFLINE", "X-Pi-Cached-At": fetched_at})
        return JSONResponse(
            {"detail": "Aktuell offline und nicht im Cache - bitte spaeter erneut versuchen",
             "error": str(last_err)},
            status_code=503,
            headers={"X-Pi-Cache": "MISS", "X-Pi-Offline": "1"},
        )

    # POST/PUT/PATCH/DELETE
    if _online:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.request(method,
                                          f"{CLOUD_URL}{full_path}",
                                          content=body,
                                          headers=headers,
                                          params=dict(request.query_params))
            return Response(content=r.content, status_code=r.status_code,
                             media_type=r.headers.get("content-type"))
        except Exception as ex:
            log.warning(f"Cloud {method} {full_path} fehlgeschlagen: {ex} -> Outbox")

    # Offline: in Outbox
    oid = outbox_add(method, full_path + ("?" + query if query else ""), headers,
                     body, headers.get("content-type", ""))
    return JSONResponse(
        {"detail": "Pi offline - Anfrage in Queue", "outbox_id": oid, "queued": True},
        status_code=202,
        headers={"X-Pi-Outbox": str(oid)},
    )


# Catch-All: jede unbekannte URL (z.B. nach versehentlichem Bookmark, alter
# Pfad nach Update, Mistype) -> Redirect zur Kiosk-Page. So kann es im
# Vollbild-Modus keine 404-Seite mehr geben.
@app.get("/{full_path:path}")
async def catch_all_redirect(full_path: str):
    if full_path.startswith("api/"):
        # Sollte schon vom /api/{path:path}-Handler abgefangen sein - safety net.
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return RedirectResponse("/kiosk", status_code=307)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PI_PORT", "8001")))
