#!/usr/bin/env python3
"""
Tankbeleg UI - Kiosk-Webserver fuer Raspberry Pi
=================================================
Touch-optimiert. Kein Login - Mitarbeiter per Dropdown.
Beleg empfangen -> Auftrag zuweisen -> Sync

Port: 8080 (localhost)
"""

import sqlite3
import json
import os
import sys
import time
import threading
import logging
import configparser
from pathlib import Path
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None

# Cloudflare blockt User-Agent "Python-urllib/X.Y" mit Error 1010, "python-requests/X"
# kommt aktuell durch - wir setzen aber trotzdem einen sprechenden UA, damit der
# Sync auch ueberlebt falls CF die Default-UA spaeter mitblockt.
PI_HEADERS = {"User-Agent": "TankbelegPi-UI/1.0 (eventenergie-deutschland)"}

try:
    import bcrypt
except ImportError:
    bcrypt = None

# ====== Konfiguration ======

DEFAULT_CONF = {
    "api_url": "",
    "db_path": "/var/lib/tankbeleg/tankbeleg.sqlite",
    "ui_port": 8080,
    "sync_interval": 300,
}


def load_config():
    conf = dict(DEFAULT_CONF)
    conf_path = Path("/etc/tankbeleg_pi.conf")
    if conf_path.exists():
        cp = configparser.ConfigParser()
        cp.read(str(conf_path))
        if "tankbeleg" in cp:
            s = cp["tankbeleg"]
            for key in conf:
                if key in s:
                    conf[key] = s[key]
            conf["ui_port"] = int(conf.get("ui_port", 8080))
            conf["sync_interval"] = int(conf.get("sync_interval", 300))
    conf["api_url"] = os.environ.get("TANKBELEG_API_URL", conf["api_url"])
    conf["db_path"] = os.environ.get("TANKBELEG_DB_PATH", conf["db_path"])
    return conf


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("tankbeleg_ui")


# ====== Helper ======

def _api_base(conf):
    url = conf.get("api_url", "").rstrip("/")
    if url.endswith("/api"):
        return url
    return url + "/api"


# ====== SQLite ======

def init_cache_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS orders_cache (
        primary_key TEXT PRIMARY KEY, order_no TEXT, event TEXT,
        contact_name TEXT, address TEXT, dispo_start TEXT, dispo_end TEXT,
        event_start TEXT, event_end TEXT, status TEXT, data_json TEXT, cached_at TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS drivers_cache (
        id TEXT PRIMARY KEY, name TEXT, email TEXT, role TEXT,
        password_hash TEXT, cached_at TEXT)""")
    for col, ctype in [("assigned","INTEGER DEFAULT 0"),("order_pk","TEXT"),("order_name","TEXT"),("notes","TEXT DEFAULT ''")]:
        try:
            conn.execute(f"ALTER TABLE receipts ADD COLUMN {col} {ctype}")
        except sqlite3.OperationalError:
            pass
    try:
        conn.execute("ALTER TABLE drivers_cache ADD COLUMN password_hash TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE drivers_cache ADD COLUMN pin_hash TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def sync_orders_from_backend(conf):
    if not conf["api_url"] or not requests:
        return 0
    base = _api_base(conf)
    try:
        resp = requests.get(f"{base}/fuel-receipts/pi/orders", timeout=15, headers=PI_HEADERS)
        if resp.status_code == 200:
            orders = resp.json().get("orders", [])
            conn = sqlite3.connect(conf["db_path"])
            for o in orders:
                conn.execute("""INSERT OR REPLACE INTO orders_cache
                    (primary_key,order_no,event,contact_name,address,dispo_start,dispo_end,event_start,event_end,status,data_json,cached_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (str(o.get("primary_key","")),o.get("order_no",""),o.get("event",""),o.get("contact_name",""),
                     o.get("address",""),o.get("dispo_start",""),o.get("dispo_end",""),o.get("event_start",""),
                     o.get("event_end",""),o.get("status",""),json.dumps(o,default=str),
                     datetime.now(timezone.utc).isoformat()))
            conn.commit(); conn.close()
            log.info(f"Auftraege synchronisiert: {len(orders)}")
            return len(orders)
        else:
            log.warning(f"Auftrags-Sync HTTP {resp.status_code}: {resp.text[:200]}")
    except requests.ConnectionError:
        log.warning("Backend nicht erreichbar")
    except Exception as e:
        log.error(f"Auftrags-Sync Fehler: {e}")
    return 0


def sync_drivers_from_backend(conf):
    if not conf["api_url"] or not requests:
        return 0
    base = _api_base(conf)
    try:
        resp = requests.get(f"{base}/fuel-receipts/pi/drivers", timeout=15, headers=PI_HEADERS)
        if resp.status_code == 200:
            drivers = resp.json().get("drivers", [])
            conn = sqlite3.connect(conf["db_path"])
            # Replace cache: ADR-Liste komplett austauschen, damit deaktivierte User verschwinden
            conn.execute("DELETE FROM drivers_cache")
            for d in drivers:
                conn.execute("""INSERT OR REPLACE INTO drivers_cache (id,name,email,role,password_hash,pin_hash,cached_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (d.get("id",""),d.get("name",""),d.get("email",""),d.get("role",""),
                     d.get("password_hash",""),d.get("pin_hash",""),datetime.now(timezone.utc).isoformat()))
            conn.commit(); conn.close()
            log.info(f"Fahrer synchronisiert: {len(drivers)}")
            return len(drivers)
        else:
            log.warning(f"Fahrer-Sync HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        log.error(f"Fahrer-Sync Fehler: {e}")
    return 0


def get_cached_orders(db_path):
    conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM orders_cache ORDER BY dispo_start DESC").fetchall()
    conn.close(); return [dict(r) for r in rows]


def get_cached_drivers(db_path):
    conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id,name,email,role FROM drivers_cache WHERE role != 'admin' ORDER BY name").fetchall()
    conn.close(); return [dict(r) for r in rows]


def get_all_drivers(db_path):
    conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id,name,email,role FROM drivers_cache ORDER BY name").fetchall()
    conn.close(); return [dict(r) for r in rows]


def verify_driver_pin(db_path, driver_id, pin):
    """Prueft den eingegebenen 6-stelligen PIN gegen den gecachten bcrypt-Hash.
    Funktioniert offline. Gibt True zurueck, wenn PIN korrekt.

    Loggt bei Fehler genau warum der Versuch nicht akzeptiert wurde,
    damit Login-Probleme im Feld nachvollziehbar sind (driver_id falsch?
    pin_hash leer? bcrypt-Mismatch?).
    """
    short_id = (driver_id or "")[:8]
    pin_len = len(pin or "")
    if not driver_id:
        log.warning(f"PIN-Verify: driver_id leer (pin_len={pin_len})")
        return False
    if not pin:
        log.warning(f"PIN-Verify {short_id}: PIN leer")
        return False
    if not bcrypt:
        log.error("PIN-Verify: bcrypt-Modul nicht installiert!")
        return False
    conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT name, pin_hash FROM drivers_cache WHERE id=?", (driver_id,)).fetchone()
    conn.close()
    if not row:
        log.warning(f"PIN-Verify {short_id}: driver_id NICHT im Cache (Sync laeuft? pin_len={pin_len})")
        return False
    if not row["pin_hash"]:
        log.warning(f"PIN-Verify {short_id} ({row['name']}): pin_hash LEER im Cache (date_of_birth im Backend gesetzt? pin_len={pin_len})")
        return False
    try:
        ok = bcrypt.checkpw(pin.encode("utf-8"), row["pin_hash"].encode("utf-8"))
        if ok:
            log.info(f"PIN-Verify {short_id} ({row['name']}): OK")
        else:
            log.warning(f"PIN-Verify {short_id} ({row['name']}): PIN FALSCH (eingegeben={pin_len} Ziffern, erwartet=6 Ziffern Format TTMMJJ)")
        return ok
    except Exception as e:
        log.error(f"PIN-Verify {short_id}: Exception {e}")
        return False


def get_receipts(db_path, limit=50):
    conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM receipts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close(); return [dict(r) for r in rows]


def assign_receipt(db_path, local_id, order_pk, order_name, fahrer, notes):
    """Speichert Auftragszuordnung. Kraftstoff-Override ist NICHT erlaubt
    (Eichrecht: Fahrer darf den vom Sening-Drucker gemessenen Kraftstoff
    NICHT manuell aendern, sonst waere die Messung manipulierbar)."""
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE receipts SET order_pk=?,order_name=?,fahrer=?,notes=?,assigned=1,synced=0 WHERE local_id=?",
                 (order_pk, order_name, fahrer, notes, local_id))
    conn.commit(); affected = conn.total_changes; conn.close()
    return affected > 0


def get_receipt_stats(db_path):
    conn = sqlite3.connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
    unsynced = conn.execute("SELECT COUNT(*) FROM receipts WHERE synced=0").fetchone()[0]
    unassigned = conn.execute("SELECT COUNT(*) FROM receipts WHERE assigned=0 OR assigned IS NULL").fetchone()[0]
    conn.close()
    return {"total": total, "unsynced": unsynced, "unassigned": unassigned}


# ====== Background Sync ======

_backend_online = False
_last_sync_ok = ""

def background_sync(conf):
    global _backend_online, _last_sync_ok
    while True:
        try:
            n = sync_orders_from_backend(conf)
            sync_drivers_from_backend(conf)
            if n > 0:
                _backend_online = True
                _last_sync_ok = datetime.now(timezone.utc).isoformat()
            else:
                if conf.get("api_url") and requests:
                    base = _api_base(conf)
                    try:
                        r = requests.get(f"{base}/health", timeout=5, headers=PI_HEADERS)
                        _backend_online = r.status_code == 200
                        if _backend_online:
                            _last_sync_ok = datetime.now(timezone.utc).isoformat()
                    except Exception:
                        _backend_online = False
        except Exception as e:
            _backend_online = False
            log.error(f"Background sync error: {e}")
        time.sleep(int(conf.get("sync_interval", 300)))


# ====== HTML ======

LOGO_URL = "https://customer-assets.emergentagent.com/job_client-file-portal/artifacts/35th6vn9_cropped-logo.webp"


def get_dashboard_html():
    return f"""<!DOCTYPE html>
<html lang="de"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no">
<title>Tankbeleg - Eventenergie</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}}
:root{{--bg:#f8f9fb;--card:#fff;--border:#e5e7eb;--text:#1a1d27;--muted:#6b7280;--accent:#c026d3;--accent-light:#f3e8ff;--accent-dark:#a21caf;--green:#16a34a;--green-bg:#dcfce7;--amber:#d97706;--amber-bg:#fef3c7;--red:#dc2626;--red-bg:#fee2e2}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);overflow:hidden;height:100vh;user-select:none}}

.header{{background:var(--card);border-bottom:2px solid var(--border);padding:8px 20px;display:flex;align-items:center;justify-content:space-between;box-shadow:0 1px 3px rgba(0,0,0,0.04);cursor:pointer;transition:background 0.15s}}
.header:active{{background:var(--accent-light)}}
.header.refreshing{{background:var(--accent-light)}}
.header-left{{display:flex;align-items:center;gap:12px}}
.header-left img{{height:28px}}
.header-left h1{{font-size:16px;font-weight:700}}
.refresh-hint{{font-size:12px;color:var(--accent-dark);font-weight:600;background:var(--accent-light);padding:5px 10px;border-radius:14px;margin-left:8px}}
.header.refreshing .refresh-hint{{background:var(--accent);color:white}}
.header-right{{display:flex;align-items:center;gap:14px}}
.conn-badge{{display:flex;align-items:center;gap:5px;padding:3px 10px;border-radius:16px;font-size:11px;font-weight:600}}
.conn-badge.online{{background:var(--green-bg);color:var(--green)}}
.conn-badge.offline{{background:var(--red-bg);color:var(--red)}}
.conn-dot{{width:7px;height:7px;border-radius:50%}}
.conn-badge.online .conn-dot{{background:var(--green);box-shadow:0 0 5px var(--green)}}
.conn-badge.offline .conn-dot{{background:var(--red)}}

.driver-bar{{background:var(--accent-light);border-bottom:1px solid var(--border);padding:8px 20px;display:flex;align-items:center;gap:12px}}
.driver-bar label{{font-size:12px;font-weight:700;color:var(--accent-dark);white-space:nowrap}}
.driver-bar select{{padding:8px 12px;border:2px solid var(--accent);border-radius:8px;font-size:15px;font-weight:600;background:white;color:var(--text);min-width:250px;outline:none}}

.main{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px;height:calc(100vh - 94px)}}
.panel{{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 1px 3px rgba(0,0,0,0.04)}}
.panel-header{{padding:10px 14px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:#fafbfc}}
.panel-header h2{{font-size:14px;font-weight:700}}
.panel-body{{flex:1;overflow-y:auto;padding:8px}}

.badge{{font-size:10px;padding:2px 8px;border-radius:16px;font-weight:700}}
.badge-warn{{background:var(--amber-bg);color:var(--amber)}}
.badge-ok{{background:var(--green-bg);color:var(--green)}}

.receipt-card{{background:var(--bg);border:2px solid var(--border);border-radius:8px;padding:10px 12px;margin-bottom:6px;cursor:pointer;transition:all 0.12s}}
.receipt-card:active{{transform:scale(0.98)}}
.receipt-card.selected{{border-color:var(--accent);background:var(--accent-light)}}
.receipt-card .top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.receipt-card .nr{{font-weight:800;font-size:15px}}
.receipt-card .date{{font-size:11px;color:var(--muted);padding:1px 6px;border-radius:4px;border:1px solid var(--border);background:white}}
.receipt-card .details{{display:flex;gap:12px;font-size:12px;color:var(--muted)}}
.receipt-card .fuel{{color:var(--accent-dark);font-weight:700;font-size:13px}}
.receipt-card .assigned-tag{{font-size:10px;color:var(--green);margin-top:4px;font-weight:600}}
.receipt-card .assigned-tag.pending{{color:var(--amber)}}
.receipt-card .assigned-tag .sync-state{{display:inline-block;margin-left:6px;padding:1px 7px;border-radius:10px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.3px}}
.receipt-card .assigned-tag .sync-state.ok{{background:var(--green-bg);color:var(--green)}}
.receipt-card .assigned-tag .sync-state.pending{{background:var(--amber-bg);color:var(--amber)}}
.receipt-card .unassigned-tag{{font-size:10px;color:var(--red);margin-top:4px;font-weight:600}}

.form-section{{padding:12px 14px 0 14px;display:flex;flex-direction:column;height:100%}}
.form-scroll{{flex:1;overflow-y:auto;padding-bottom:8px}}
.form-actions{{display:flex;gap:8px;padding:10px 0 12px 0;background:var(--card);border-top:1px solid var(--border);margin-top:4px;position:sticky;bottom:0}}
.form-group{{margin-bottom:10px}}
.form-group label{{display:block;font-size:11px;color:var(--muted);margin-bottom:4px;font-weight:600;text-transform:uppercase;letter-spacing:0.3px}}
select,.notes-input{{width:100%;padding:10px;background:var(--bg);border:2px solid var(--border);border-radius:8px;color:var(--text);font-size:15px;outline:none;-webkit-appearance:none;transition:border-color 0.2s}}
select:focus,.notes-input:focus{{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-light)}}
.notes-input{{resize:none;height:52px;cursor:pointer}}

.btn{{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:11px 20px;border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;width:100%;transition:all 0.12s}}
.btn:active{{transform:scale(0.97)}}
.btn-primary{{background:var(--accent);color:white;box-shadow:0 2px 6px rgba(192,38,211,0.3)}}
.btn-lager{{background:#f59e0b;color:white;margin-bottom:10px;padding:10px 16px;font-size:14px;box-shadow:0 2px 6px rgba(245,158,11,0.3)}}
.btn-lager:hover{{background:#d97706}}

.order-picker{{display:flex;gap:8px;align-items:stretch}}
.order-list{{flex:1;background:var(--bg);border:2px solid var(--border);border-radius:10px;max-height:180px;overflow-y:auto;scroll-behavior:smooth}}
.order-list::-webkit-scrollbar{{width:0;display:none}}
.order-item{{padding:14px 14px;font-size:15px;border-bottom:1px solid var(--border);cursor:pointer;line-height:1.3}}
.order-item:last-child{{border-bottom:none}}
.order-item:active{{background:var(--accent-light)}}
.order-item.selected{{background:var(--accent);color:white;font-weight:700}}
.order-item .ord-no{{font-weight:700}}
.order-item .ord-dt{{font-size:12px;color:var(--muted);margin-top:2px}}
.order-item.selected .ord-dt{{color:rgba(255,255,255,0.8)}}
.order-arrows{{display:flex;flex-direction:column;gap:6px}}
.order-arrow{{width:56px;height:60px;border:2px solid var(--border);background:var(--card);border-radius:10px;font-size:28px;font-weight:700;color:var(--accent);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.12s}}
.order-arrow:active{{background:var(--accent);color:white;transform:scale(0.94)}}
.order-arrow:disabled{{opacity:0.3;cursor:not-allowed}}
.btn:disabled{{opacity:0.4;cursor:not-allowed;transform:none}}
.btn-cancel{{background:var(--border);color:var(--muted);border:none;border-radius:10px;padding:12px 18px;font-size:16px;font-weight:700;cursor:pointer}}

.stats-bar{{display:flex;gap:14px;padding:8px 14px;border-top:1px solid var(--border);background:#fafbfc}}
.stat{{font-size:11px;color:var(--muted)}}
.stat b{{color:var(--text)}}

.empty{{text-align:center;padding:40px 16px;color:var(--muted)}}
.empty p{{font-size:13px}}

.new-alert{{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);backdrop-filter:blur(4px);display:none;align-items:center;justify-content:center;z-index:50}}
.new-alert.show{{display:flex}}
.new-alert .content{{background:var(--card);border:3px solid var(--accent);border-radius:18px;padding:32px;text-align:center;max-width:400px;width:90%;box-shadow:0 16px 50px rgba(0,0,0,0.2)}}
.new-alert h2{{font-size:20px;font-weight:800;margin-bottom:6px}}
.new-alert .amount{{font-size:52px;font-weight:900;color:var(--accent);line-height:1.1}}
.new-alert .unit{{font-size:16px;color:var(--muted);font-weight:600}}

/* Touch Keyboard Overlay */
.kbd-overlay{{position:fixed;bottom:0;left:0;right:0;background:var(--card);border-top:2px solid var(--border);padding:12px;display:none;z-index:60;box-shadow:0 -4px 20px rgba(0,0,0,0.15)}}
.kbd-overlay.show{{display:block}}
.kbd-preview{{background:var(--bg);border:2px solid var(--border);border-radius:10px;padding:14px 18px;margin-bottom:10px;font-size:22px;min-height:54px;color:var(--text);display:flex;align-items:center;justify-content:space-between}}
.kbd-preview span{{flex:1;word-break:break-all}}
.kbd-done{{background:var(--accent);color:white;border:none;border-radius:10px;padding:14px 28px;font-size:18px;font-weight:700;cursor:pointer}}
.kbd-row{{display:flex;gap:6px;margin-bottom:6px;justify-content:center}}
.kbd-key{{min-width:64px;height:68px;border:1px solid var(--border);border-radius:10px;background:var(--bg);color:var(--text);font-size:24px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.08s;flex:1;max-width:88px}}
.kbd-key:active{{background:var(--accent);color:white;transform:scale(0.94)}}
.kbd-key.wide{{min-width:96px;max-width:120px;font-size:20px}}
.kbd-key.space{{flex:3;max-width:380px}}

.toast{{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);padding:12px 24px;border-radius:10px;font-size:14px;font-weight:700;display:none;z-index:100;box-shadow:0 4px 16px rgba(0,0,0,0.15)}}
.toast.show{{display:block;animation:slideUp 0.3s ease}}
.toast.success{{background:var(--green);color:white}}
.toast.error{{background:var(--red);color:white}}
@keyframes slideUp{{from{{opacity:0;transform:translateX(-50%) translateY(20px)}}to{{opacity:1;transform:translateX(-50%) translateY(0)}}}}

/* PIN Login Overlay */
.pin-overlay{{position:fixed;inset:0;background:rgba(15,23,42,0.78);backdrop-filter:blur(6px);display:none;align-items:center;justify-content:center;z-index:80}}
.pin-overlay.show{{display:flex}}
.pin-card{{background:var(--card);border:2px solid var(--accent);border-radius:18px;padding:24px 26px;width:380px;max-width:90vw;box-shadow:0 16px 60px rgba(0,0,0,0.35)}}
.pin-card h2{{font-size:18px;font-weight:800;margin-bottom:4px;text-align:center}}
.pin-card .pin-driver{{font-size:13px;color:var(--accent-dark);text-align:center;margin-bottom:16px;font-weight:600}}
.pin-dots{{display:flex;justify-content:center;gap:10px;margin-bottom:18px}}
.pin-dot{{width:18px;height:18px;border-radius:50%;border:2px solid var(--border);background:var(--bg);transition:all 0.15s}}
.pin-dot.filled{{background:var(--accent);border-color:var(--accent);transform:scale(1.1)}}
.pin-card.error .pin-dot{{border-color:var(--red);background:var(--red-bg)}}
.pin-card.error{{animation:shake 0.4s}}
@keyframes shake{{0%,100%{{transform:translateX(0)}}25%{{transform:translateX(-8px)}}75%{{transform:translateX(8px)}}}}
.pin-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px}}
.pin-key{{height:64px;border:1px solid var(--border);border-radius:10px;background:var(--bg);color:var(--text);font-size:24px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.08s}}
.pin-key:active{{background:var(--accent);color:white;transform:scale(0.94)}}
.pin-key.action{{font-size:14px;font-weight:600}}
.pin-cancel{{width:100%;padding:10px;border:none;background:var(--border);color:var(--muted);border-radius:10px;font-size:14px;font-weight:700;cursor:pointer}}
::-webkit-scrollbar{{width:5px}}
::-webkit-scrollbar-thumb{{background:var(--border);border-radius:3px}}
</style></head>
<body>

<div class="header" onclick="refreshAll()" id="headerBar" title="Antippen zum Aktualisieren">
  <div class="header-left">
    <img src="{LOGO_URL}" alt="Logo" onerror="this.style.display='none'">
    <h1>Tankbeleg</h1>
    <span class="refresh-hint" id="refreshHint">&#x21bb; Antippen zum Aktualisieren</span>
  </div>
  <div class="header-right">
    <div class="conn-badge" id="connBadge"><span class="conn-dot"></span><span id="connLabel">...</span></div>
  </div>
</div>

<div class="driver-bar">
  <label>Mitarbeiter:</label>
  <select id="driverSelect" onchange="onDriverChange()"><option value="">-- Mitarbeiter waehlen --</option></select>
</div>

<div class="main">
  <div class="panel">
    <div class="panel-header">
      <h2>Eingehende Belege</h2>
      <span class="badge badge-warn" id="unassignedBadge">0 offen</span>
    </div>
    <div class="panel-body" id="receiptList">
      <div class="empty"><p>Warte auf Belege...</p></div>
    </div>
    <div class="stats-bar">
      <span class="stat">Gesamt: <b id="statTotal">0</b></span>
      <span class="stat">Offen: <b id="statUnassigned">0</b></span>
      <span class="stat">Sync: <b id="statUnsynced">0</b></span>
    </div>
  </div>

  <div class="panel">
    <div class="panel-header">
      <h2>Beleg zuordnen</h2>
      <span id="selectedNr" style="font-size:12px;color:var(--muted)">Kein Beleg gewaehlt</span>
    </div>
    <div class="panel-body">
      <div id="noSelection" class="empty" style="padding-top:40px"><p>Beleg links antippen</p></div>
      <div id="assignForm" class="form-section" style="display:none">
        <div class="form-scroll">
          <button type="button" class="btn btn-lager" id="lagerBtn" onclick="assignLager()">Lager / Testlauf</button>
          <div class="form-group">
            <label>Auftrag</label>
            <div class="order-picker">
              <div class="order-list" id="orderList"></div>
              <div class="order-arrows">
                <button type="button" class="order-arrow" id="orderUpBtn" onclick="scrollOrders(-1)">&#9650;</button>
                <button type="button" class="order-arrow" id="orderDownBtn" onclick="scrollOrders(1)">&#9660;</button>
              </div>
            </div>
          </div>
          <div class="form-group">
            <label>Bemerkung (optional)</label>
            <div class="notes-input" id="notesDisplay" onclick="openKeyboard('notes')">Antippen zum Schreiben...</div>
            <input type="hidden" id="notesValue">
          </div>
        </div>
        <div class="form-actions">
          <button class="btn btn-primary" id="saveBtn" onclick="saveAssignment()">Speichern</button>
          <button class="btn-cancel" onclick="clearSelection()">&#x2715;</button>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- New Receipt Alert -->
<div class="new-alert" id="newAlert">
  <div class="content">
    <img src="{LOGO_URL}" alt="" style="height:24px;margin-bottom:12px" onerror="this.style.display='none'">
    <h2>Neuer Beleg!</h2>
    <div class="amount" id="alertAmount">0</div>
    <div class="unit">Liter</div>
    <p style="margin:16px 0;color:var(--muted);font-size:13px" id="alertDetails"></p>
    <button class="btn btn-primary" onclick="dismissAlert()">Jetzt zuordnen</button>
  </div>
</div>

<!-- Touch Keyboard Overlay -->
<div class="kbd-overlay" id="kbdOverlay">
  <div class="kbd-preview">
    <span id="kbdPreview"></span>
    <button class="kbd-done" onclick="closeKeyboard()">Fertig</button>
  </div>
  <div id="kbdRows"></div>
</div>

<!-- PIN Login Overlay -->
<div class="pin-overlay" id="pinOverlay">
  <div class="pin-card" id="pinCard">
    <h2>PIN eingeben</h2>
    <div class="pin-driver" id="pinDriver"></div>
    <div class="pin-dots" id="pinDots">
      <div class="pin-dot"></div><div class="pin-dot"></div><div class="pin-dot"></div>
      <div class="pin-dot"></div><div class="pin-dot"></div><div class="pin-dot"></div>
    </div>
    <div class="pin-grid" id="pinGrid"></div>
    <button class="pin-cancel" onclick="cancelPin()">Abbrechen</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let selectedReceipt=null, lastReceiptCount=-1, orders=[], receipts=[], selectedOrderPk='', selectedOrderName='';
let kbdTarget=null, kbdValue='', kbdShift=false;
let verifiedDriver='', verifiedDriverId='', verifiedPin='', driversMap={{}}, pinDriverId='', pinDriverName='', pinValue='';

const ROWS_DIGITS=['1','2','3','4','5','6','7','8','9','0'];
const ROWS=[['q','w','e','r','t','z','u','i','o','p'],['a','s','d','f','g','h','j','k','l'],['y','x','c','v','b','n','m']];
const ROWS_SHIFT=[['Q','W','E','R','T','Z','U','I','O','P'],['A','S','D','F','G','H','J','K','L'],['Y','X','C','V','B','N','M']];

function buildKbd() {{
  const rows=kbdShift?ROWS_SHIFT:ROWS;
  let html='';
  // Ziffern-Reihe IMMER oben - unabhaengig von Shift. Auf einem Tankwagen-PI
  // werden oft Auftragsnummern wie "251024-01" oder Funkmast-Bezeichnungen
  // mit Zahlen ("FUNKMAST 3") eingegeben - daher muss die Tastatur Zahlen
  // dauerhaft anbieten, nicht hinter einem Shift-Toggle verstecken.
  html+='<div class="kbd-row">';
  ROWS_DIGITS.forEach(k=>{{ html+='<div class="kbd-key" onmousedown="kbdType(\\''+k+'\\');event.preventDefault()" ontouchstart="kbdType(\\''+k+'\\');event.preventDefault()">'+k+'</div>'; }});
  html+='</div>';
  for(let i=0;i<rows.length;i++) {{
    html+='<div class="kbd-row">';
    if(i===2) html+='<div class="kbd-key wide '+(kbdShift?'accent':'')+'" onmousedown="kbdToggleShift()" ontouchstart="kbdToggleShift()">&#8679;</div>';
    rows[i].forEach(k=>{{ html+='<div class="kbd-key" onmousedown="kbdType(\\''+k+'\\');event.preventDefault()" ontouchstart="kbdType(\\''+k+'\\');event.preventDefault()">'+k+'</div>'; }});
    if(i===1) html+='<div class="kbd-key wide" onmousedown="kbdBack();event.preventDefault()" ontouchstart="kbdBack();event.preventDefault()">&#9003;</div>';
    html+='</div>';
  }}
  html+='<div class="kbd-row"><div class="kbd-key" onmousedown="kbdType(\\'@\\');event.preventDefault()" ontouchstart="kbdType(\\'@\\');event.preventDefault()">@</div><div class="kbd-key" onmousedown="kbdType(\\'-\\');event.preventDefault()" ontouchstart="kbdType(\\'-\\');event.preventDefault()">-</div><div class="kbd-key" onmousedown="kbdType(\\'_\\');event.preventDefault()" ontouchstart="kbdType(\\'_\\');event.preventDefault()">_</div><div class="kbd-key" onmousedown="kbdType(\\'/\\');event.preventDefault()" ontouchstart="kbdType(\\'/\\');event.preventDefault()">/</div><div class="kbd-key space" onmousedown="kbdType(\\' \\');event.preventDefault()" ontouchstart="kbdType(\\' \\');event.preventDefault()">Leer</div><div class="kbd-key" onmousedown="kbdType(\\'.\\');event.preventDefault()" ontouchstart="kbdType(\\'.\\');event.preventDefault()">.</div><div class="kbd-key" onmousedown="kbdType(\\',\\');event.preventDefault()" ontouchstart="kbdType(\\',\\');event.preventDefault()">,</div></div>';
  document.getElementById('kbdRows').innerHTML=html;
}}

function openKeyboard(target) {{
  kbdTarget=target;
  kbdValue=document.getElementById(target+'Value').value||'';
  document.getElementById('kbdPreview').textContent=kbdValue||'...';
  document.getElementById('kbdOverlay').classList.add('show');
  buildKbd();
}}

function closeKeyboard() {{
  if(kbdTarget) {{
    document.getElementById(kbdTarget+'Value').value=kbdValue;
    document.getElementById(kbdTarget+'Display').textContent=kbdValue||'Antippen zum Schreiben...';
  }}
  document.getElementById('kbdOverlay').classList.remove('show');
  kbdTarget=null;
}}

function kbdType(ch) {{
  kbdValue+=ch;
  document.getElementById('kbdPreview').textContent=kbdValue;
}}

function kbdBack() {{
  kbdValue=kbdValue.slice(0,-1);
  document.getElementById('kbdPreview').textContent=kbdValue||'...';
}}

function kbdToggleShift() {{
  kbdShift=!kbdShift;
  buildKbd();
}}

async function fetchJSON(url){{return(await fetch(url)).json()}}

async function loadReceipts(){{
  try{{
    const d=await fetchJSON('/api/receipts');
    receipts=d.receipts||[];
    renderReceipts();
    updateStats(d.stats||{{}});
    if(lastReceiptCount>=0&&receipts.length>lastReceiptCount) showNewAlert(receipts[0]);
    lastReceiptCount=receipts.length;
  }}catch(e){{}}
}}

async function loadOrders(){{
  try{{orders=(await fetchJSON('/api/orders')).orders||[];populateOrders()}}catch(e){{}}
}}

async function loadDrivers(){{
  try{{
    const d=await fetchJSON('/api/drivers');
    const drivers=d.drivers||[];
    driversMap={{}};
    drivers.forEach(dr=>{{ driversMap[dr.name||dr.email]={{id:dr.id,name:dr.name||dr.email}}; }});
    const sel=document.getElementById('driverSelect');
    const previous=sel.value;
    sel.innerHTML='<option value="">-- Mitarbeiter waehlen --</option>';
    drivers.forEach(dr=>{{
      const v=esc(dr.name||dr.email);
      sel.innerHTML+='<option value="'+v+'" data-id="'+esc(dr.id)+'">'+v+'</option>';
    }});
    // Falls der bisherige Mitarbeiter nicht mehr in der Liste ist (ADR deaktiviert) -> abmelden
    if(previous && !driversMap[previous]){{
      sel.value='';
      verifiedDriver='';
      showToast('Mitarbeiter nicht mehr freigegeben',true);
    }}else if(previous){{
      sel.value=previous;
    }}
  }}catch(e){{}}
}}

function onDriverChange(){{
  const sel=document.getElementById('driverSelect');
  const name=sel.value;
  if(!name){{ verifiedDriver=''; verifiedDriverId=''; verifiedPin=''; return; }}
  if(name===verifiedDriver) return; // bereits angemeldet
  // PIN-Eingabe oeffnen
  openPinDialog(name);
}}

function openPinDialog(driverName){{
  const dr=driversMap[driverName];
  if(!dr){{ showToast('Unbekannter Mitarbeiter',true); return; }}
  pinDriverId=dr.id;
  pinDriverName=driverName;
  pinValue='';
  document.getElementById('pinDriver').textContent=driverName;
  renderPinDots();
  buildPinGrid();
  document.getElementById('pinCard').classList.remove('error');
  document.getElementById('pinOverlay').classList.add('show');
}}

function buildPinGrid(){{
  const keys=['1','2','3','4','5','6','7','8','9','C','0','OK'];
  const html=keys.map(k=>{{
    const cls=(k==='C'||k==='OK')?'pin-key action':'pin-key';
    return '<div class="'+cls+'" onmousedown="pinKey(\\''+k+'\\');event.preventDefault()" ontouchstart="pinKey(\\''+k+'\\');event.preventDefault()">'+k+'</div>';
  }}).join('');
  document.getElementById('pinGrid').innerHTML=html;
}}

function pinKey(k){{
  if(k==='C'){{ pinValue=''; renderPinDots(); return; }}
  if(k==='OK'){{ verifyPin(); return; }}
  if(pinValue.length>=6) return;
  pinValue+=k;
  renderPinDots();
  if(pinValue.length===6) verifyPin();
}}

function renderPinDots(){{
  const dots=document.querySelectorAll('#pinDots .pin-dot');
  dots.forEach((d,i)=>{{ d.classList.toggle('filled', i<pinValue.length); }});
}}

async function verifyPin(){{
  if(pinValue.length!==6){{ showPinError(); return; }}
  try{{
    const r=await fetch('/api/verify-pin',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{driver_id:pinDriverId,pin:pinValue}})}});
    const d=await r.json();
    if(d.ok){{
      verifiedDriver=pinDriverName;
      verifiedDriverId=pinDriverId;
      verifiedPin=pinValue;
      document.getElementById('pinOverlay').classList.remove('show');
      showToast('Angemeldet: '+pinDriverName);
    }}else{{ showPinError(); }}
  }}catch(e){{ showPinError(); }}
}}

function showPinError(){{
  const card=document.getElementById('pinCard');
  card.classList.add('error');
  pinValue='';
  setTimeout(()=>{{ card.classList.remove('error'); renderPinDots(); }},500);
}}

function cancelPin(){{
  document.getElementById('pinOverlay').classList.remove('show');
  // Dropdown auf den letzten verifizierten Mitarbeiter zuruecksetzen
  document.getElementById('driverSelect').value=verifiedDriver||'';
}}

async function checkConn(){{
  try{{
    const d=await fetchJSON('/api/status');
    const b=document.getElementById('connBadge');
    b.className='conn-badge '+(d.backend_reachable?'online':'offline');
    document.getElementById('connLabel').textContent=d.backend_reachable?'Portal verbunden':'Offline';
  }}catch(e){{}}
}}

async function refreshAll(){{
  const header=document.getElementById('headerBar');
  const hint=document.getElementById('refreshHint');
  header.classList.add('refreshing');
  if(hint) hint.innerHTML='&#x21bb; Aktualisiere...';
  try{{
    // Backend sofort pollen (Auftraege, Fahrer ziehen)
    await fetch('/api/sync',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}});
  }}catch(e){{}}
  await Promise.all([loadOrders(),loadDrivers(),loadReceipts(),checkConn()]);
  setTimeout(()=>{{
    header.classList.remove('refreshing');
    if(hint) hint.innerHTML='&#x21bb; Antippen zum Aktualisieren';
  }},700);
}}

function renderReceipts(){{
  const el=document.getElementById('receiptList');
  if(!receipts.length){{el.innerHTML='<div class="empty"><p>Warte auf Belege...</p></div>';return}}
  el.innerHTML=receipts.map(r=>{{
    const sel=selectedReceipt&&selectedReceipt.local_id===r.local_id;
    const asg=r.assigned&&r.order_pk;
    const synced=Number(r.synced||0)===1;
    // Drei klare Status, damit der Fahrer auch offline sicher weiss dass
    // der Beleg gebucht ist (gruen-Hell = lokal gespeichert, gruen-Voll =
    // ans Backend synchronisiert, rot = noch nicht zugeordnet).
    let badge='';
    if(asg){{
      if(synced){{
        badge='<div class="assigned-tag synced">&#10003; '+esc(r.order_name||r.order_pk)+' <span class="sync-state ok">synchron</span></div>';
      }}else{{
        badge='<div class="assigned-tag pending">&#10003; '+esc(r.order_name||r.order_pk)+' <span class="sync-state pending">lokal gebucht &#183; Sync ausstehend</span></div>';
      }}
    }}else{{
      badge='<div class="unassigned-tag">&#9679; Offen</div>';
    }}
    return '<div class="receipt-card'+(sel?' selected':'')+'" onclick="selectReceipt(\\''+r.local_id+'\\')">'+
      '<div class="top"><span class="nr">Nr. '+esc(r.beleg_nr||'?')+'</span><span class="date">'+esc(r.datum||'')+' '+esc(r.zeit||'')+'</span></div>'+
      '<div class="details"><span class="fuel">'+esc(String(r.menge_liter||0))+' L</span><span>'+esc(fuelLabel(r.fuel_type))+'</span>'+(r.fahrer?'<span>'+esc(r.fahrer)+'</span>':'')+'</div>'+
      badge+
    '</div>';
  }}).join('');
}}

function esc(s){{const d=document.createElement('div');d.textContent=s;return d.innerHTML}}

// Map fuel_type code -> Anzeige-Label. None/leer = "Unbekannt" (NICHT mehr stiller "Diesel"-Fallback, das hat HEL-Belege falsch klassifiziert)
function fuelLabel(ft){{
  if(!ft) return 'Unbekannt';
  if(ft==='heizoel_leicht') return 'HEL leicht';
  if(ft==='diesel') return 'Diesel';
  if(ft==='hvo') return 'HVO';
  return ft;
}}

function populateOrders(){{
  const list=document.getElementById('orderList');
  list.innerHTML='';
  orders.forEach(o=>{{
    const label=(o.order_no||'')+' - '+(o.event||o.contact_name||'');
    const dt=o.dispo_start?(o.dispo_start||'').substring(0,10):'';
    const div=document.createElement('div');
    div.className='order-item';
    div.setAttribute('data-pk',o.primary_key||'');
    div.setAttribute('data-name',label);
    div.innerHTML='<div class="ord-no">'+esc(label)+'</div>'+(dt?'<div class="ord-dt">'+esc(dt)+'</div>':'');
    div.onclick=function(){{selectOrder(o.primary_key||'',label)}};
    list.appendChild(div);
  }});
}}

function selectOrder(pk,label){{
  selectedOrderPk=pk;
  selectedOrderName=label;
  document.querySelectorAll('.order-item').forEach(el=>{{
    el.classList.toggle('selected',el.getAttribute('data-pk')===pk);
  }});
  // Ausgewaehltes Element ins Sichtfeld scrollen
  const sel=document.querySelector('.order-item.selected');
  if(sel) sel.scrollIntoView({{block:'nearest',behavior:'smooth'}});
}}

function scrollOrders(direction){{
  const list=document.getElementById('orderList');
  list.scrollBy({{top:direction*150,behavior:'smooth'}});
}}

function updateStats(s){{
  document.getElementById('statTotal').textContent=s.total||0;
  document.getElementById('statUnassigned').textContent=s.unassigned||0;
  document.getElementById('statUnsynced').textContent=s.unsynced||0;
  const b=document.getElementById('unassignedBadge');
  const n=s.unassigned||0;
  b.textContent=n+' offen';
  b.className='badge '+(n>0?'badge-warn':'badge-ok');
}}

function selectReceipt(id){{
  // Gate: kein Beleg-Detail/Zuordnung ohne PIN-Anmeldung. Eichrechtlich
  // muss klar dokumentiert sein, WER einen Beleg einem Auftrag zugeordnet hat.
  if(!verifiedDriver){{
    showToast('Bitte zuerst oben Mitarbeiter waehlen + PIN eingeben',true);
    const sel=document.getElementById('driverSelect');
    const name=sel.value;
    if(name && driversMap[name]) openPinDialog(name);
    else sel.focus();
    return;
  }}
  selectedReceipt=receipts.find(r=>r.local_id===id)||null;
  if(!selectedReceipt) return;
  document.getElementById('noSelection').style.display='none';
  document.getElementById('assignForm').style.display='block';
  document.getElementById('selectedNr').textContent='Beleg Nr. '+(selectedReceipt.beleg_nr||'?');
  // Vorhandene Zuordnung in der Liste markieren
  selectedOrderPk=selectedReceipt.order_pk||'';
  selectedOrderName=selectedReceipt.order_name||'';
  document.querySelectorAll('.order-item').forEach(el=>{{
    el.classList.toggle('selected',el.getAttribute('data-pk')===selectedOrderPk);
  }});
  const selEl=document.querySelector('.order-item.selected');
  if(selEl) selEl.scrollIntoView({{block:'nearest'}});
  else document.getElementById('orderList').scrollTop=0;
  document.getElementById('notesValue').value=selectedReceipt.notes||'';
  document.getElementById('notesDisplay').textContent=selectedReceipt.notes||'Antippen zum Schreiben...';
  renderReceipts();
}}

function clearSelection(){{
  selectedReceipt=null;
  selectedOrderPk='';
  selectedOrderName='';
  document.querySelectorAll('.order-item.selected').forEach(el=>el.classList.remove('selected'));
  document.getElementById('noSelection').style.display='';
  document.getElementById('assignForm').style.display='none';
  document.getElementById('selectedNr').textContent='Kein Beleg gewaehlt';
  renderReceipts();
}}

async function saveAssignment(){{
  if(!selectedReceipt) return;
  const fahrer=document.getElementById('driverSelect').value;
  if(!fahrer){{showToast('Bitte Mitarbeiter oben waehlen',true);return}}
  if(fahrer!==verifiedDriver){{showToast('PIN-Verifikation fehlt',true);openPinDialog(fahrer);return}}
  if(!verifiedDriverId||!verifiedPin){{showToast('PIN-Verifikation fehlt',true);openPinDialog(fahrer);return}}
  if(!selectedOrderPk){{showToast('Bitte Auftrag aus Liste waehlen',true);return}}
  const notes=document.getElementById('notesValue').value||'';
  document.getElementById('saveBtn').disabled=true;
  try{{
    const r=await fetch('/api/assign',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{local_id:selectedReceipt.local_id,order_pk:selectedOrderPk,order_name:selectedOrderName,fahrer:fahrer,driver_id:verifiedDriverId,pin:verifiedPin,notes:notes}})}});
    const d=await r.json();
    if(d.ok){{showToast('Beleg zugeordnet!');clearSelection();loadReceipts()}}
    else showToast('Fehler: '+(d.error||'?'),true);
  }}catch(e){{showToast('Speichern fehlgeschlagen',true)}}
  document.getElementById('saveBtn').disabled=false;
}}

async function assignLager(){{
  if(!selectedReceipt) return;
  const fahrer=document.getElementById('driverSelect').value;
  if(!fahrer){{showToast('Bitte Mitarbeiter oben waehlen',true);return}}
  if(fahrer!==verifiedDriver){{showToast('PIN-Verifikation fehlt',true);openPinDialog(fahrer);return}}
  if(!verifiedDriverId||!verifiedPin){{showToast('PIN-Verifikation fehlt',true);openPinDialog(fahrer);return}}
  const notes=document.getElementById('notesValue').value||'';
  document.getElementById('lagerBtn').disabled=true;
  document.getElementById('saveBtn').disabled=true;
  try{{
    const r=await fetch('/api/assign',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{local_id:selectedReceipt.local_id,order_pk:'LAGER',order_name:'Lager / Testlauf',fahrer:fahrer,driver_id:verifiedDriverId,pin:verifiedPin,notes:notes}})}});
    const d=await r.json();
    if(d.ok){{showToast('Beleg auf Lager gebucht!');clearSelection();loadReceipts()}}
    else showToast('Fehler: '+(d.error||'?'),true);
  }}catch(e){{showToast('Speichern fehlgeschlagen',true)}}
  document.getElementById('lagerBtn').disabled=false;
  document.getElementById('saveBtn').disabled=false;
}}

function showNewAlert(r){{
  document.getElementById('alertAmount').textContent=r.menge_liter||'?';
  document.getElementById('alertDetails').textContent='Nr. '+(r.beleg_nr||'?')+' - '+fuelLabel(r.fuel_type)+' - '+(r.datum||'');
  document.getElementById('newAlert').classList.add('show');
}}

function dismissAlert(){{
  document.getElementById('newAlert').classList.remove('show');
  const u=receipts.find(r=>!r.assigned||!r.order_pk);
  if(u) selectReceipt(u.local_id);
}}

function showToast(m,err){{
  const t=document.getElementById('toast');
  t.textContent=m;
  t.className='toast show '+(err?'error':'success');
  setTimeout(()=>t.className='toast',3000);
}}

document.addEventListener('DOMContentLoaded',()=>{{
  document.body.addEventListener('click',function f(){{
    if(!document.fullscreenElement) document.documentElement.requestFullscreen().catch(()=>{{}});
    document.body.removeEventListener('click',f);
  }},{{once:true}});
}});

(async()=>{{
  await checkConn();
  await loadDrivers();
  await loadOrders();
  await loadReceipts();
  setInterval(loadReceipts,5000);
  setInterval(checkConn,30000);
  setInterval(loadOrders,300000);
  setInterval(loadDrivers,300000);
}})();
</script>
</body></html>"""


# ====== HTTP Handler ======

class KioskHandler(SimpleHTTPRequestHandler):
    conf = {}

    def log_message(self, format, *args):
        pass

    def _json(self, data, status=200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/dashboard", "/index.html"):
            self._html(get_dashboard_html())
        elif path == "/api/receipts":
            self._json({"receipts": get_receipts(self.conf["db_path"]), "stats": get_receipt_stats(self.conf["db_path"])})
        elif path == "/api/orders":
            self._json({"orders": get_cached_orders(self.conf["db_path"])})
        elif path == "/api/drivers":
            self._json({"drivers": get_all_drivers(self.conf["db_path"])})
        elif path == "/api/status":
            self._json({"backend_reachable": _backend_online, "last_sync": _last_sync_ok, "stats": get_receipt_stats(self.conf["db_path"])})
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        if path == "/api/assign":
            # Server-side Gate: Beleg darf nur zugewiesen werden, wenn der
            # Fahrername in der lokalen drivers_cache existiert UND ein
            # frischer PIN-Verify im Body mitgegeben wurde. Das verhindert,
            # dass jemand mit curl/Devtools die UI umgeht.
            fahrer = (body.get("fahrer") or "").strip()
            pin = (body.get("pin") or "").strip()
            driver_id = (body.get("driver_id") or "").strip()
            if not fahrer or not driver_id or not pin:
                log.warning(f"/api/assign abgelehnt: fahrer/driver_id/pin fehlt (lid={body.get('local_id')})")
                self._json({"ok": False, "error": "Anmeldung erforderlich"}); return
            if not verify_driver_pin(self.conf["db_path"], driver_id, pin):
                log.warning(f"/api/assign abgelehnt: PIN-Verify fehlgeschlagen ({fahrer})")
                self._json({"ok": False, "error": "PIN ungueltig"}); return
            ok = assign_receipt(self.conf["db_path"], body.get("local_id"), body.get("order_pk"),
                                body.get("order_name", ""), fahrer, body.get("notes", ""))
            self._json({"ok": ok})
        elif path == "/api/sync":
            sync_orders_from_backend(self.conf)
            sync_drivers_from_backend(self.conf)
            self._json({"ok": True})
        elif path == "/api/verify-pin":
            ok = verify_driver_pin(self.conf["db_path"], body.get("driver_id", ""), body.get("pin", ""))
            self._json({"ok": ok})
        else:
            self.send_error(404)


# ====== Main ======

def main():
    conf = load_config()
    log.info("=" * 50)
    log.info("  Tankbeleg UI - Kiosk (ohne Login)")
    log.info("=" * 50)
    log.info(f"  Port:    {conf.get('ui_port', 8080)}")
    log.info(f"  Backend: {conf['api_url'] or '(nicht konfiguriert)'}")
    log.info(f"  DB:      {conf['db_path']}")
    log.info("=" * 50)

    init_cache_db(conf["db_path"])

    global _backend_online, _last_sync_ok
    n = sync_orders_from_backend(conf)
    sync_drivers_from_backend(conf)
    if n > 0:
        _backend_online = True
        _last_sync_ok = datetime.now(timezone.utc).isoformat()

    threading.Thread(target=background_sync, args=(conf,), daemon=True).start()

    KioskHandler.conf = conf
    port = int(conf.get("ui_port", 8080))
    server = HTTPServer(("0.0.0.0", port), KioskHandler)
    log.info(f"Kiosk gestartet: http://localhost:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
