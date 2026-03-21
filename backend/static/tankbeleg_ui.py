#!/usr/bin/env python3
"""
Tankbeleg UI - Kiosk-Webserver fuer Raspberry Pi
=================================================
Touch-optimiertes Frontend fuer Tankbeleg-Zuordnung.
Laeuft lokal auf dem Pi und zeigt eingehende Belege an.

Starten:
  python3 tankbeleg_ui.py

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
from urllib.parse import urlparse, parse_qs

try:
    import requests
except ImportError:
    requests = None

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


# ====== Logging ======
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("tankbeleg_ui")


# ====== Offline Cache (SQLite) ======

def init_cache_db(db_path):
    """Erstellt Cache-Tabellen fuer Auftraege und Fahrer."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders_cache (
            primary_key TEXT PRIMARY KEY,
            order_no TEXT,
            event TEXT,
            contact_name TEXT,
            address TEXT,
            dispo_start TEXT,
            dispo_end TEXT,
            event_start TEXT,
            event_end TEXT,
            status TEXT,
            data_json TEXT,
            cached_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS drivers_cache (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            role TEXT,
            cached_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def sync_orders_from_backend(conf):
    """Laedt Auftraege vom Backend und speichert sie lokal."""
    if not conf["api_url"] or not requests:
        return 0
    try:
        resp = requests.get(f"{conf['api_url']}/api/fuel-receipts/pi/orders", timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            orders = data.get("orders", [])
            conn = sqlite3.connect(conf["db_path"])
            for o in orders:
                conn.execute("""
                    INSERT OR REPLACE INTO orders_cache
                    (primary_key, order_no, event, contact_name, address,
                     dispo_start, dispo_end, event_start, event_end, status, data_json, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(o.get("primary_key", "")),
                    o.get("order_no", ""),
                    o.get("event", ""),
                    o.get("contact_name", ""),
                    o.get("address", ""),
                    o.get("dispo_start", ""),
                    o.get("dispo_end", ""),
                    o.get("event_start", ""),
                    o.get("event_end", ""),
                    o.get("status", ""),
                    json.dumps(o, default=str),
                    datetime.now(timezone.utc).isoformat(),
                ))
            conn.commit()
            conn.close()
            log.info(f"Auftraege synchronisiert: {len(orders)}")
            return len(orders)
    except requests.ConnectionError:
        log.warning("Backend nicht erreichbar - nutze Offline-Cache")
    except Exception as e:
        log.error(f"Auftrags-Sync Fehler: {e}")
    return 0


def sync_drivers_from_backend(conf):
    """Laedt Fahrer/Benutzer vom Backend."""
    if not conf["api_url"] or not requests:
        return 0
    try:
        resp = requests.get(f"{conf['api_url']}/api/fuel-receipts/pi/drivers", timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            drivers = data.get("drivers", [])
            conn = sqlite3.connect(conf["db_path"])
            for d in drivers:
                conn.execute("""
                    INSERT OR REPLACE INTO drivers_cache (id, name, email, role, cached_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    d.get("id", ""),
                    d.get("name", ""),
                    d.get("email", ""),
                    d.get("role", ""),
                    datetime.now(timezone.utc).isoformat(),
                ))
            conn.commit()
            conn.close()
            log.info(f"Fahrer synchronisiert: {len(drivers)}")
            return len(drivers)
    except Exception as e:
        log.error(f"Fahrer-Sync Fehler: {e}")
    return 0


def get_cached_orders(db_path):
    """Holt gecachte Auftraege aus SQLite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM orders_cache ORDER BY dispo_start DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_cached_drivers(db_path):
    """Holt gecachte Fahrer aus SQLite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM drivers_cache ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_receipts(db_path, limit=50):
    """Holt die letzten Belege."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM receipts ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unassigned_receipts(db_path):
    """Holt Belege ohne Auftragszuordnung."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM receipts WHERE (assigned=0 OR assigned IS NULL) ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def assign_receipt(db_path, local_id, order_pk, order_name, fahrer, notes):
    """Weist einem Beleg einen Auftrag zu."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        UPDATE receipts SET order_pk=?, order_name=?, fahrer=?, notes=?, assigned=1, synced=0
        WHERE local_id=?
    """, (order_pk, order_name, fahrer, notes, local_id))
    conn.commit()
    affected = conn.total_changes
    conn.close()
    return affected > 0


def get_receipt_stats(db_path):
    """Statistiken."""
    conn = sqlite3.connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
    unsynced = conn.execute("SELECT COUNT(*) FROM receipts WHERE synced=0").fetchone()[0]
    unassigned = conn.execute("SELECT COUNT(*) FROM receipts WHERE assigned=0 OR assigned IS NULL").fetchone()[0]
    conn.close()
    return {"total": total, "unsynced": unsynced, "unassigned": unassigned}


# ====== Background Sync Thread ======

def background_sync(conf):
    """Periodischer Hintergrund-Sync."""
    while True:
        try:
            sync_orders_from_backend(conf)
            sync_drivers_from_backend(conf)
        except Exception as e:
            log.error(f"Background sync error: {e}")
        time.sleep(int(conf.get("sync_interval", 300)))


# ====== HTML Kiosk Page ======

def get_kiosk_html():
    return """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>Tankbeleg - Eventenergie</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
:root {
  --bg: #f8f9fb; --card: #ffffff; --border: #e5e7eb;
  --text: #1a1d27; --muted: #6b7280; --accent: #c026d3;
  --accent-light: #f3e8ff; --accent-dark: #a21caf;
  --green: #16a34a; --green-bg: #dcfce7;
  --amber: #d97706; --amber-bg: #fef3c7;
  --red: #dc2626; --red-bg: #fee2e2;
}
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:var(--bg); color:var(--text); overflow:hidden; height:100vh; cursor:default; user-select:none; }

.header { background:var(--card); border-bottom:2px solid var(--border); padding:10px 24px; display:flex; align-items:center; justify-content:space-between; box-shadow:0 1px 3px rgba(0,0,0,0.04); }
.header-left { display:flex; align-items:center; gap:14px; }
.header-left img { height:32px; }
.header-left h1 { font-size:17px; font-weight:700; color:var(--text); }
.header-left .divider { width:1px; height:24px; background:var(--border); }
.header-left .sub { font-size:13px; color:var(--muted); font-weight:400; }
.status-bar { display:flex; gap:14px; align-items:center; }
.conn-badge { display:flex; align-items:center; gap:6px; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:600; }
.conn-badge.online { background:var(--green-bg); color:var(--green); }
.conn-badge.offline { background:var(--red-bg); color:var(--red); }
.conn-dot { width:8px; height:8px; border-radius:50%; }
.conn-badge.online .conn-dot { background:var(--green); box-shadow:0 0 6px var(--green); }
.conn-badge.offline .conn-dot { background:var(--red); }

.main { display:grid; grid-template-columns:1fr 1fr; gap:16px; padding:16px; height:calc(100vh - 54px); }

.panel { background:var(--card); border:1px solid var(--border); border-radius:14px; overflow:hidden; display:flex; flex-direction:column; box-shadow:0 1px 4px rgba(0,0,0,0.04); }
.panel-header { padding:14px 18px; border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; background:#fafbfc; }
.panel-header h2 { font-size:15px; font-weight:700; color:var(--text); }
.panel-body { flex:1; overflow-y:auto; padding:10px; }

.badge { font-size:11px; padding:3px 10px; border-radius:20px; font-weight:700; }
.badge-warn { background:var(--amber-bg); color:var(--amber); }
.badge-ok { background:var(--green-bg); color:var(--green); }

.receipt-card { background:var(--bg); border:2px solid var(--border); border-radius:10px; padding:14px; margin-bottom:8px; cursor:pointer; transition:all 0.15s; }
.receipt-card:active { transform:scale(0.98); }
.receipt-card.selected { border-color:var(--accent); background:var(--accent-light); }
.receipt-card .top { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
.receipt-card .nr { font-weight:800; font-size:16px; color:var(--text); }
.receipt-card .date { font-size:12px; color:var(--muted); background:var(--bg); padding:2px 8px; border-radius:6px; border:1px solid var(--border); }
.receipt-card .details { display:flex; gap:14px; font-size:13px; color:var(--muted); }
.receipt-card .fuel { color:var(--accent-dark); font-weight:700; font-size:14px; }
.receipt-card .assigned-tag { font-size:11px; color:var(--green); margin-top:6px; font-weight:600; display:flex; align-items:center; gap:4px; }
.receipt-card .unassigned-tag { font-size:11px; color:var(--red); margin-top:6px; font-weight:600; }

.form-section { padding:18px; }
.form-group { margin-bottom:18px; }
.form-group label { display:block; font-size:12px; color:var(--muted); margin-bottom:6px; font-weight:600; text-transform:uppercase; letter-spacing:0.3px; }
select, input, textarea {
  width:100%; padding:14px; background:var(--bg); border:2px solid var(--border); border-radius:10px;
  color:var(--text); font-size:16px; outline:none; -webkit-appearance:none; transition:border-color 0.2s;
}
select:focus, input:focus, textarea:focus { border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-light); }
textarea { resize:none; height:80px; }

.btn { display:inline-flex; align-items:center; justify-content:center; gap:8px; padding:16px 28px; border:none; border-radius:12px; font-size:16px; font-weight:700; cursor:pointer; width:100%; transition:all 0.15s; }
.btn:active { transform:scale(0.97); }
.btn-primary { background:var(--accent); color:white; box-shadow:0 2px 8px rgba(192,38,211,0.3); }
.btn-primary:hover { background:var(--accent-dark); }
.btn-secondary { background:var(--border); color:var(--muted); }
.btn:disabled { opacity:0.4; cursor:not-allowed; transform:none; }

.stats-bar { display:flex; gap:16px; padding:12px 18px; border-top:1px solid var(--border); background:#fafbfc; }
.stat { font-size:12px; color:var(--muted); }
.stat b { color:var(--text); }

.toast { position:fixed; bottom:24px; left:50%; transform:translateX(-50%); padding:14px 28px; border-radius:12px; font-size:15px; font-weight:700; display:none; z-index:100; box-shadow:0 6px 24px rgba(0,0,0,0.15); }
.toast.show { display:block; animation: slideUp 0.3s ease; }
.toast.success { background:var(--green); color:white; }
.toast.error { background:var(--red); color:white; }

.empty { text-align:center; padding:60px 20px; color:var(--muted); }
.empty p { font-size:14px; }
.empty .hint { font-size:12px; margin-top:8px; color:#9ca3af; }

.new-receipt-alert { position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.6); backdrop-filter:blur(4px); display:none; align-items:center; justify-content:center; z-index:50; }
.new-receipt-alert.show { display:flex; }
.new-receipt-alert .content { background:var(--card); border:3px solid var(--accent); border-radius:20px; padding:36px; text-align:center; max-width:420px; width:90%; box-shadow:0 20px 60px rgba(0,0,0,0.2); }
.new-receipt-alert h2 { font-size:22px; font-weight:800; color:var(--text); margin-bottom:8px; }
.new-receipt-alert .amount { font-size:56px; font-weight:900; color:var(--accent); line-height:1.1; }
.new-receipt-alert .unit { font-size:18px; color:var(--muted); font-weight:600; }
.new-receipt-alert .details-text { margin:20px 0; color:var(--muted); font-size:14px; }

.fullscreen-btn { background:none; border:1px solid var(--border); border-radius:8px; padding:6px 10px; cursor:pointer; color:var(--muted); font-size:11px; }
.fullscreen-btn:hover { background:var(--bg); }

@keyframes slideUp { from { opacity:0; transform:translateX(-50%) translateY(20px); } to { opacity:1; transform:translateX(-50%) translateY(0); } }

/* Scrollbar */
::-webkit-scrollbar { width:6px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:var(--border); border-radius:3px; }
::-webkit-scrollbar-thumb:hover { background:#bbb; }
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <img src="https://customer-assets.emergentagent.com/job_client-file-portal/artifacts/35th6vn9_cropped-logo.webp" alt="Logo" onerror="this.style.display='none'">
    <div class="divider"></div>
    <h1>Tankbeleg</h1>
    <span class="sub">Belegerfassung</span>
  </div>
  <div class="status-bar">
    <div class="conn-badge" id="connBadge">
      <span class="conn-dot"></span>
      <span id="connLabel">Pruefe...</span>
    </div>
    <button class="fullscreen-btn" onclick="toggleFullscreen()" title="Vollbild">&#x26F6; Vollbild</button>
  </div>
</div>

<div class="main">
  <div class="panel">
    <div class="panel-header">
      <h2>Eingehende Belege</h2>
      <span class="badge badge-warn" id="unassignedBadge">0 offen</span>
    </div>
    <div class="panel-body" id="receiptList">
      <div class="empty">
        <p>Keine Belege vorhanden</p>
        <p class="hint">Belege erscheinen automatisch wenn ein Tankvorgang abgeschlossen wird</p>
      </div>
    </div>
    <div class="stats-bar">
      <span class="stat">Gesamt: <b id="statTotal">0</b></span>
      <span class="stat">Offen: <b id="statUnassigned">0</b></span>
      <span class="stat">Wartend: <b id="statUnsynced">0</b></span>
    </div>
  </div>

  <div class="panel">
    <div class="panel-header">
      <h2>Beleg zuordnen</h2>
      <span id="selectedNr" style="font-size:13px;color:var(--muted)">Kein Beleg ausgewaehlt</span>
    </div>
    <div class="panel-body">
      <div id="noSelection" class="empty" style="padding-top:60px">
        <p>Beleg links antippen zum Zuordnen</p>
      </div>
      <div id="assignForm" class="form-section" style="display:none">
        <div class="form-group">
          <label>Fahrer / Mitarbeiter</label>
          <select id="driverSelect">
            <option value="">-- Fahrer waehlen --</option>
          </select>
        </div>
        <div class="form-group">
          <label>Auftrag</label>
          <select id="orderSelect">
            <option value="">-- Auftrag waehlen --</option>
          </select>
        </div>
        <div class="form-group">
          <label>Zusatzinfo / Notizen</label>
          <textarea id="notesInput" placeholder="Optionale Bemerkungen..."></textarea>
        </div>
        <div style="display:flex;gap:10px">
          <button class="btn btn-primary" id="saveBtn" onclick="saveAssignment()">Speichern</button>
          <button class="btn btn-secondary" onclick="clearSelection()" style="width:auto;padding:16px 22px;font-size:18px">&#x2715;</button>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="new-receipt-alert" id="newAlert">
  <div class="content">
    <img src="https://customer-assets.emergentagent.com/job_client-file-portal/artifacts/35th6vn9_cropped-logo.webp" alt="" style="height:28px;margin-bottom:16px" onerror="this.style.display='none'">
    <h2>Neuer Beleg empfangen!</h2>
    <div class="amount" id="alertAmount">0</div>
    <div class="unit">Liter</div>
    <p class="details-text" id="alertDetails"></p>
    <button class="btn btn-primary" onclick="dismissAlert()">Jetzt zuordnen</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const API = '';
let selectedReceipt = null;
let lastReceiptCount = -1;
let orders = [];
let drivers = [];
let receipts = [];

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(()=>{});
  } else {
    document.exitFullscreen();
  }
}

async function fetchJSON(url) {
  const r = await fetch(API + url);
  return r.json();
}

async function loadReceipts() {
  try {
    const data = await fetchJSON('/api/receipts');
    receipts = data.receipts || [];
    renderReceipts();
    updateStats(data.stats || {});
    if (lastReceiptCount >= 0 && receipts.length > lastReceiptCount) {
      showNewReceiptAlert(receipts[0]);
    }
    lastReceiptCount = receipts.length;
  } catch(e) { console.error('Receipts load error:', e); }
}

async function loadOrders() {
  try {
    const data = await fetchJSON('/api/orders');
    orders = data.orders || [];
    populateOrderSelect();
  } catch(e) { console.error('Orders load error:', e); }
}

async function loadDrivers() {
  try {
    const data = await fetchJSON('/api/drivers');
    drivers = data.drivers || [];
    populateDriverSelect();
  } catch(e) { console.error('Drivers load error:', e); }
}

async function checkConnection() {
  const badge = document.getElementById('connBadge');
  const label = document.getElementById('connLabel');
  try {
    const r = await fetch(API + '/api/status');
    const d = await r.json();
    const ok = d.backend_reachable;
    badge.className = 'conn-badge ' + (ok ? 'online' : 'offline');
    label.textContent = ok ? 'Portal verbunden' : 'Offline-Modus';
  } catch(e) {
    badge.className = 'conn-badge offline';
    label.textContent = 'Kein Server';
  }
}

function renderReceipts() {
  const list = document.getElementById('receiptList');
  if (!receipts.length) {
    list.innerHTML = '<div class="empty"><p>Keine Belege vorhanden</p><p class="hint">Belege erscheinen automatisch wenn ein Tankvorgang abgeschlossen wird</p></div>';
    return;
  }
  list.innerHTML = receipts.map(r => {
    const sel = selectedReceipt && selectedReceipt.local_id === r.local_id;
    const assigned = r.assigned && r.order_pk;
    return '<div class="receipt-card'+(sel?' selected':'')+'" onclick="selectReceipt(\\''+r.local_id+'\\')">'+
      '<div class="top"><span class="nr">Nr. '+esc(r.beleg_nr||'?')+'</span><span class="date">'+esc(r.datum||'')+' '+esc(r.zeit||'')+'</span></div>'+
      '<div class="details"><span class="fuel">'+esc(String(r.menge_liter||0))+' Liter</span><span>'+esc(r.fuel_type||'Diesel')+'</span>'+(r.fahrer?'<span>'+esc(r.fahrer)+'</span>':'')+'</div>'+
      (assigned?'<div class="assigned-tag">&#10003; '+esc(r.order_name||r.order_pk)+'</div>':'<div class="unassigned-tag">&#9679; Nicht zugeordnet</div>')+
    '</div>';
  }).join('');
}

function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML;}

function populateOrderSelect() {
  const sel = document.getElementById('orderSelect');
  sel.innerHTML = '<option value="">-- Auftrag waehlen --</option>';
  orders.forEach(o => {
    const label = (o.order_no||'')+ ' - ' +(o.event||o.contact_name||'');
    const dates = o.dispo_start ? ' ('+( o.dispo_start||'').substring(0,10)+')' : '';
    sel.innerHTML += '<option value="'+esc(o.primary_key)+'" data-name="'+esc(label)+'">'+esc(label)+dates+'</option>';
  });
}

function populateDriverSelect() {
  const sel = document.getElementById('driverSelect');
  sel.innerHTML = '<option value="">-- Fahrer waehlen --</option>';
  drivers.forEach(d => {
    sel.innerHTML += '<option value="'+esc(d.name||d.email)+'">'+esc(d.name||d.email)+'</option>';
  });
}

function updateStats(stats) {
  document.getElementById('statTotal').textContent = stats.total||0;
  document.getElementById('statUnassigned').textContent = stats.unassigned||0;
  document.getElementById('statUnsynced').textContent = stats.unsynced||0;
  const badge = document.getElementById('unassignedBadge');
  const n = stats.unassigned||0;
  badge.textContent = n+' offen';
  badge.className = 'badge '+(n>0?'badge-warn':'badge-ok');
}

function selectReceipt(localId) {
  selectedReceipt = receipts.find(r=>r.local_id===localId)||null;
  if(!selectedReceipt) return;
  document.getElementById('noSelection').style.display='none';
  document.getElementById('assignForm').style.display='block';
  document.getElementById('selectedNr').textContent='Beleg Nr. '+(selectedReceipt.beleg_nr||'?');
  if(selectedReceipt.fahrer) document.getElementById('driverSelect').value=selectedReceipt.fahrer;
  if(selectedReceipt.order_pk) document.getElementById('orderSelect').value=selectedReceipt.order_pk;
  document.getElementById('notesInput').value=selectedReceipt.notes||'';
  renderReceipts();
}

function clearSelection() {
  selectedReceipt=null;
  document.getElementById('noSelection').style.display='';
  document.getElementById('assignForm').style.display='none';
  document.getElementById('selectedNr').textContent='Kein Beleg ausgewaehlt';
  renderReceipts();
}

async function saveAssignment() {
  if(!selectedReceipt) return;
  const orderSel=document.getElementById('orderSelect');
  const orderPk=orderSel.value;
  const orderName=orderSel.selectedOptions[0]?.dataset?.name||'';
  const fahrer=document.getElementById('driverSelect').value;
  const notes=document.getElementById('notesInput').value;
  if(!fahrer){showToast('Bitte Fahrer waehlen',true);return;}
  if(!orderPk){showToast('Bitte Auftrag waehlen',true);return;}
  document.getElementById('saveBtn').disabled=true;
  try{
    const r=await fetch(API+'/api/assign',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({local_id:selectedReceipt.local_id,order_pk:orderPk,order_name:orderName,fahrer:fahrer,notes:notes})});
    const data=await r.json();
    if(data.ok){showToast('Beleg erfolgreich zugeordnet!');clearSelection();loadReceipts();}
    else{showToast('Fehler: '+(data.error||'Unbekannt'),true);}
  }catch(e){showToast('Speichern fehlgeschlagen',true);}
  document.getElementById('saveBtn').disabled=false;
}

function showNewReceiptAlert(receipt) {
  document.getElementById('alertAmount').textContent=receipt.menge_liter||'?';
  document.getElementById('alertDetails').textContent='Beleg Nr. '+(receipt.beleg_nr||'?')+' - '+(receipt.fuel_type||'Diesel')+' - '+(receipt.datum||'');
  document.getElementById('newAlert').classList.add('show');
}

function dismissAlert() {
  document.getElementById('newAlert').classList.remove('show');
  const unassigned=receipts.find(r=>!r.assigned||!r.order_pk);
  if(unassigned) selectReceipt(unassigned.local_id);
}

function showToast(msg,isError) {
  const t=document.getElementById('toast');
  t.textContent=msg;
  t.className='toast show '+(isError?'error':'success');
  setTimeout(()=>t.className='toast',3000);
}

// Auto fullscreen on load
document.addEventListener('DOMContentLoaded', function() {
  // Try fullscreen after first touch (browser requires user gesture)
  document.body.addEventListener('click', function fsOnce() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(()=>{});
    }
    document.body.removeEventListener('click', fsOnce);
  }, {once: true});
});

async function init() {
  await checkConnection();
  await loadOrders();
  await loadDrivers();
  await loadReceipts();
  setInterval(loadReceipts, 5000);
  setInterval(checkConnection, 30000);
  setInterval(loadOrders, 300000);
}
init();
</script>
</body>
</html>"""


# ====== HTTP Request Handler ======

class KioskHandler(SimpleHTTPRequestHandler):
    conf = {}

    def log_message(self, format, *args):
        pass  # Suppress access logs

    def _json(self, data, status=200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            html = get_kiosk_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html)

        elif path == "/api/receipts":
            recs = get_receipts(self.conf["db_path"])
            stats = get_receipt_stats(self.conf["db_path"])
            self._json({"receipts": recs, "stats": stats})

        elif path == "/api/orders":
            ords = get_cached_orders(self.conf["db_path"])
            self._json({"orders": ords})

        elif path == "/api/drivers":
            drvs = get_cached_drivers(self.conf["db_path"])
            self._json({"drivers": drvs})

        elif path == "/api/status":
            online = False
            if self.conf.get("api_url") and requests:
                try:
                    r = requests.get(f"{self.conf['api_url']}/api/health", timeout=5)
                    online = r.status_code == 200
                except Exception:
                    pass
            stats = get_receipt_stats(self.conf["db_path"])
            self._json({
                "backend_reachable": online,
                "stats": stats,
                "api_url": self.conf.get("api_url", ""),
            })

        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/assign":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            local_id = body.get("local_id")
            order_pk = body.get("order_pk")
            order_name = body.get("order_name", "")
            fahrer = body.get("fahrer", "")
            notes = body.get("notes", "")

            if not local_id:
                self._json({"ok": False, "error": "local_id fehlt"}, 400)
                return

            ok = assign_receipt(self.conf["db_path"], local_id, order_pk, order_name, fahrer, notes)
            self._json({"ok": ok})

        elif path == "/api/sync":
            sync_orders_from_backend(self.conf)
            sync_drivers_from_backend(self.conf)
            self._json({"ok": True})

        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ====== Main ======

def main():
    conf = load_config()

    log.info("=" * 50)
    log.info("  Tankbeleg UI - Kiosk-Webserver")
    log.info("  Eventenergie Deutschland")
    log.info("=" * 50)
    log.info(f"  Port:     {conf.get('ui_port', 8080)}")
    log.info(f"  Backend:  {conf['api_url'] or '(nicht konfiguriert)'}")
    log.info(f"  DB:       {conf['db_path']}")
    log.info("=" * 50)

    # Init cache tables
    init_cache_db(conf["db_path"])

    # Initial sync
    log.info("Lade Auftraege und Fahrer vom Backend...")
    sync_orders_from_backend(conf)
    sync_drivers_from_backend(conf)

    # Start background sync thread
    sync_thread = threading.Thread(target=background_sync, args=(conf,), daemon=True)
    sync_thread.start()

    # Start HTTP server
    KioskHandler.conf = conf
    port = int(conf.get("ui_port", 8080))
    server = HTTPServer(("0.0.0.0", port), KioskHandler)
    log.info(f"Kiosk-Server gestartet auf http://localhost:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Server beendet")
        server.server_close()


if __name__ == "__main__":
    main()
