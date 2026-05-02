#!/usr/bin/env python3
"""
Kirmeskiste 8 Zaehler Sync - Eventenergie Portal
=================================================
Liest 8 S0-Pulse-Counter ueber Sequent Microsystems "16 LV Digital Inputs HAT"
und synchronisiert die kWh-Zaehlerstaende mit dem Eventenergie Portal.

Hardware:
  - Raspberry Pi 5
  - Sequent Microsystems "16 LV Digital Inputs HAT V3.1" (Stack 0)
  - SIM7600X 4G HAT (LTE + GPS, optional)
  - 8x ABB D11/D13 Energy Meter (S0 Pulse Output, 1000 imp/kWh)

Software-Voraussetzungen (im Setup-Skript installiert):
  - /usr/local/bin/16inpind (Sequent CLI)
  - python3, requests
  - Optional: gpsd, gpsd-py3 fuer GPS

Konfiguration:
  /etc/kirmeskiste8z.conf

Statuspruefung:
  sudo systemctl status kirmeskiste8z_sync
  sudo journalctl -u kirmeskiste8z_sync -f

Logbefehl: zeigt die letzten Zaehlerstaende:
  python3 /opt/kirmeskiste8z/show.py
"""

import configparser
import hashlib
import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


SCRIPT_VERSION = "1.1.0"
DEVICE_TYPE_OTA = "kirmeskiste_8z"
SEQUENT_CLI = "/usr/local/bin/16inpind"
DEFAULT_STACK_LEVEL = 0
STACK_LEVEL = None  # wird zur Laufzeit per Auto-Discovery gesetzt


# ====== Konfiguration ======

DEFAULT_CONF = {
    "api_url": "",
    "device_key": "",
    "device_id": "",
    "db_path": "/var/lib/kirmeskiste8z/kirmeskiste8z.sqlite",
    "read_interval": 10,
    "sync_interval": 60,
    "retry_delay": 30,
    "batch_size": 500,
    "gps_enabled": "true",
}

DEFAULT_METERS = [
    {"meter_id": "", "channel": i, "pulses_per_kwh": 1000, "name": f"Zaehler {i}"}
    for i in range(1, 9)
]


def load_config():
    conf = dict(DEFAULT_CONF)
    meters = list(DEFAULT_METERS)

    conf_path = Path("/etc/kirmeskiste8z.conf")
    if conf_path.exists():
        cp = configparser.ConfigParser()
        cp.read(str(conf_path))

        if "kirmeskiste8z" in cp:
            s = cp["kirmeskiste8z"]
            for k in ("api_url", "device_key", "device_id", "db_path", "gps_enabled"):
                if k in s:
                    conf[k] = s[k]
            for k in ("read_interval", "sync_interval", "retry_delay", "batch_size"):
                if k in s:
                    conf[k] = int(s[k])

        meters = []
        for i in range(1, 17):
            section = f"meter_{i}"
            if section in cp:
                m = cp[section]
                meters.append({
                    "meter_id": m.get("meter_id", ""),
                    "channel": int(m.get("channel", str(i))),
                    "pulses_per_kwh": int(m.get("pulses_per_kwh", "1000")),
                    "name": m.get("name", f"Zaehler {i}"),
                })

    return conf, meters


# ====== Logging ======

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("kirmeskiste8z")


# ====== OTA Auto-Update ======

PI_ID_FILE = Path("/var/lib/kirmeskiste8z/pi_id")


def get_pi_id():
    """Persistente UUID fuer dieses Pi."""
    if PI_ID_FILE.exists():
        return PI_ID_FILE.read_text().strip()
    import uuid as _uuid
    pid = str(_uuid.uuid4())
    PI_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PI_ID_FILE.write_text(pid)
    return pid


def get_script_hash():
    try:
        return hashlib.sha256(Path(os.path.abspath(__file__)).read_bytes()).hexdigest()
    except Exception:
        return ""


def get_hostname():
    try:
        return subprocess.run(["hostname"], capture_output=True, text=True, timeout=2).stdout.strip()
    except Exception:
        return ""


def check_and_apply_update(conf):
    """OTA: prueft Hash, laedt neues Skript, ersetzt sich selbst, neu starten."""
    if not conf.get("api_url"):
        return False
    try:
        resp = requests.get(
            f"{conf['api_url']}/system/ota/pi/{DEVICE_TYPE_OTA}/check",
            params={
                "pi_id": get_pi_id(),
                "hostname": get_hostname(),
                "hash": get_script_hash(),
                "version": SCRIPT_VERSION,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            log.warning(f"OTA-Check Fehler: {resp.status_code}")
            return False

        data = resp.json()
        if not data.get("update_available"):
            return False

        log.info(f"OTA Update verfuegbar: {SCRIPT_VERSION} -> ?")

        dl = requests.get(
            f"{conf['api_url']}/system/ota/pi/{DEVICE_TYPE_OTA}/download",
            params={"pi_id": get_pi_id()},
            timeout=60,
        )
        if dl.status_code != 200:
            log.error(f"Download fehlgeschlagen: {dl.status_code}")
            return False

        new_content = dl.content
        new_hash = hashlib.sha256(new_content).hexdigest()
        if data.get("file_hash") and new_hash != data["file_hash"]:
            log.error("OTA Hash mismatch, breche ab.")
            return False

        script_path = Path(os.path.abspath(__file__))
        script_path.with_suffix(".py.bak").write_bytes(script_path.read_bytes())
        script_path.write_bytes(new_content)
        os.chmod(str(script_path), 0o755)
        log.info("OTA: Update installiert, Service-Neustart...")
        os.system("sudo systemctl restart kirmeskiste8z_sync")
        sys.exit(0)
    except requests.ConnectionError:
        log.debug("Portal nicht erreichbar fuer OTA-Check")
    except Exception as e:
        log.error(f"OTA-Check Fehler: {e}")
    return False


# ====== Sequent HAT ======

def hat_discover_stack_level():
    """Probiert Stack 0..7, gibt den Level zurueck der antwortet."""
    global STACK_LEVEL
    if STACK_LEVEL is not None:
        return STACK_LEVEL
    for lvl in range(8):
        try:
            r = subprocess.run(
                [SEQUENT_CLI, str(lvl), "optcntrd", "1"],
                capture_output=True, text=True, timeout=2,
            )
            if r.returncode == 0 and r.stdout.strip().isdigit():
                STACK_LEVEL = lvl
                log.info(f"Sequent HAT auf Stack-Level {lvl} entdeckt")
                return lvl
        except Exception:
            continue
    log.error("Kein Sequent HAT auf Stack 0-7 gefunden! Fallback auf Stack 0.")
    STACK_LEVEL = DEFAULT_STACK_LEVEL
    return STACK_LEVEL


def hat_setup_channel(channel):
    """Edge-Detection (falling) + Counter-Interrupt aktivieren. Muss nach Boot pro Kanal gesetzt werden."""
    lvl = hat_discover_stack_level()
    try:
        subprocess.run([SEQUENT_CLI, str(lvl), "optedgewr", str(channel), "1"],
                       capture_output=True, timeout=3)
        subprocess.run([SEQUENT_CLI, str(lvl), "optintwr", str(channel), "1"],
                       capture_output=True, timeout=3)
    except Exception as e:
        log.warning(f"HAT-Setup Kanal {channel} fehlgeschlagen: {e}")


def hat_read_counter(channel):
    """Liest den aktuellen Pulse-Counter (UInt32) eines Kanals."""
    lvl = hat_discover_stack_level()
    try:
        r = subprocess.run(
            [SEQUENT_CLI, str(lvl), "optcntrd", str(channel)],
            capture_output=True, text=True, timeout=2,
        )
        return int(r.stdout.strip())
    except Exception as e:
        log.warning(f"HAT-Read Kanal {channel} fehlgeschlagen: {e}")
        return None


# ====== Lokale DB ======

def init_db(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS meter_state (
            meter_id        TEXT PRIMARY KEY,
            channel         INTEGER NOT NULL,
            pulses_per_kwh  INTEGER NOT NULL DEFAULT 1000,
            counter_offset  INTEGER NOT NULL DEFAULT 0,
            kwh_offset      REAL NOT NULL DEFAULT 0.0,
            last_counter    INTEGER NOT NULL DEFAULT 0,
            last_update     TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            meter_id    TEXT NOT NULL,
            ts_utc      TEXT NOT NULL,
            counter     INTEGER NOT NULL,
            kwh         REAL NOT NULL,
            data_json   TEXT NOT NULL,
            synced      INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_readings_synced ON readings(synced, meter_id)")
    con.commit()
    con.close()


def ensure_meter_state_row(db_path, meter):
    """Stellt sicher, dass ein State-Eintrag fuer den Meter existiert."""
    con = sqlite3.connect(db_path)
    con.execute("""
        INSERT OR IGNORE INTO meter_state (meter_id, channel, pulses_per_kwh, kwh_offset)
        VALUES (?, ?, ?, 0.0)
    """, (meter["meter_id"], meter["channel"], meter["pulses_per_kwh"]))
    # pulses_per_kwh + channel ggf. aktualisieren (Pi-Reboot mit neuer Config)
    con.execute("""
        UPDATE meter_state SET channel=?, pulses_per_kwh=? WHERE meter_id=?
    """, (meter["channel"], meter["pulses_per_kwh"], meter["meter_id"]))
    con.commit()
    con.close()


def fetch_kwh_offset_from_portal(conf, meter_id):
    """Holt den Anfangs-kWh-Offset einmalig vom Portal (wird im Geraete-Modal eingetragen)."""
    if not conf.get("api_url") or not conf.get("device_key"):
        return None
    try:
        resp = requests.get(
            f"{conf['api_url']}/energy-monitoring/devices/{conf['device_id']}/meters/{meter_id}/kwh-offset",
            params={"api_key": conf["device_key"]},
            timeout=10,
        )
        if resp.status_code == 200:
            return float(resp.json().get("kwh_offset", 0.0))
    except Exception as e:
        log.debug(f"kWh-Offset-Fetch fehlgeschlagen ({meter_id[:8]}): {e}")
    return None


def get_meter_state(db_path, meter_id):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT * FROM meter_state WHERE meter_id=?", (meter_id,)
    ).fetchone()
    con.close()
    return dict(row) if row else None


def update_meter_state(db_path, meter_id, fields):
    if not fields:
        return
    con = sqlite3.connect(db_path)
    sets = ", ".join(f"{k}=?" for k in fields)
    con.execute(f"UPDATE meter_state SET {sets} WHERE meter_id=?",
                list(fields.values()) + [meter_id])
    con.commit()
    con.close()


def store_reading(db_path, meter_id, counter, kwh, gps):
    ts_utc = datetime.now(timezone.utc).isoformat()
    record = {
        "ts_utc": ts_utc,
        "E_imp_kWh": round(kwh, 4),
        "E_exp_kWh": 0.0,
        "I_L1": 0, "I_L2": 0, "I_L3": 0, "I_sum": 0,
        "U_L1": 0, "U_L2": 0, "U_L3": 0,
        "F_Hz": 0,
        "P_sum_kW": 0, "P_L1_kW": 0, "P_L2_kW": 0, "P_L3_kW": 0,
        "Q_sum": 0, "Q_L1": 0, "Q_L2": 0, "Q_L3": 0,
        "PF_L1": 0, "PF_L2": 0, "PF_L3": 0,
        "gps_lat": gps.get("lat"), "gps_lon": gps.get("lon"),
        "gps_alt_m": gps.get("alt"), "gps_speed_mps": gps.get("speed"),
        "gps_mode": gps.get("mode"),
        "http_ok": 1, "error": "",
    }
    con = sqlite3.connect(db_path)
    con.execute("""
        INSERT INTO readings (meter_id, ts_utc, counter, kwh, data_json, synced)
        VALUES (?, ?, ?, ?, ?, 0)
    """, (meter_id, ts_utc, counter, round(kwh, 4), json.dumps(record)))
    con.commit()
    con.close()


def get_unsynced(db_path, batch_size=500):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT * FROM readings WHERE synced=0 ORDER BY id ASC LIMIT ?",
        (batch_size,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def mark_synced(db_path, ids):
    if not ids:
        return
    con = sqlite3.connect(db_path)
    placeholders = ",".join("?" * len(ids))
    con.execute(f"UPDATE readings SET synced=1 WHERE id IN ({placeholders})", ids)
    con.commit()
    con.close()


def cleanup_old(db_path, keep_days=14):
    con = sqlite3.connect(db_path)
    con.execute(
        "DELETE FROM readings WHERE synced=1 AND created_at < datetime('now', ?)",
        (f"-{keep_days} days",),
    )
    con.commit()
    con.close()


# ====== GPS via gpsd (optional, SIM7600 GPS) ======

def read_gps():
    """Liest letzte GPS-Position via gpsd. Gibt {} zurueck wenn nicht verfuegbar."""
    try:
        import gpsd  # gpsd-py3
        gpsd.connect()
        pkt = gpsd.get_current()
        if pkt.mode >= 2:
            return {
                "lat": pkt.lat,
                "lon": pkt.lon,
                "alt": pkt.alt if pkt.mode >= 3 else None,
                "speed": pkt.hspeed,
                "mode": pkt.mode,
            }
    except Exception:
        pass
    return {}


# ====== Portal Sync ======

def sync_to_portal(conf):
    rows = get_unsynced(conf["db_path"], conf["batch_size"])
    if not rows:
        return 0

    by_meter = {}
    for row in rows:
        by_meter.setdefault(row["meter_id"], []).append(row)

    total = 0
    for meter_id, mrows in by_meter.items():
        records = []
        ids = []
        for row in mrows:
            records.append(json.loads(row["data_json"]))
            ids.append(row["id"])

        payload = {
            "api_key": conf["device_key"],
            "device_id": conf["device_id"],
            "meter_id": meter_id,
            "records": records,
            "last_sync_id": str(ids[-1]),
        }
        try:
            resp = requests.post(
                f"{conf['api_url']}/energy-monitoring/ingest",
                json=payload, timeout=60,
            )
            if resp.status_code == 200:
                mark_synced(conf["db_path"], ids)
                inserted = resp.json().get("inserted", 0)
                total += inserted
                log.info(f"Sync OK: {inserted} Datensaetze fuer Zaehler {meter_id[:8]}...")
            else:
                log.warning(f"Sync Fehler {resp.status_code}: {resp.text[:200]}")
        except requests.ConnectionError:
            log.warning("Portal nicht erreichbar - Daten bleiben lokal gespeichert")
            break
        except Exception as e:
            log.error(f"Sync Fehler: {e}")
    return total


# ====== Hauptprogramm ======

def main():
    conf, meters = load_config()

    log.info("=" * 60)
    log.info("  Kirmeskiste 8 Zaehler Sync - Eventenergie Portal")
    log.info("  8x ABB D11/D13 via Sequent S0-Pulse-HAT")
    log.info("=" * 60)
    log.info(f"  Server:        {conf['api_url']}")
    log.info(f"  Device-ID:     {conf['device_id']}")
    log.info(f"  Datenbank:     {conf['db_path']}")
    log.info(f"  Leseintervall: {conf['read_interval']}s")
    log.info(f"  Sync-Intervall:{conf['sync_interval']}s")
    log.info(f"  Pi-ID:         {get_pi_id()}")
    log.info("  Zaehler:")
    for m in meters:
        log.info(f"    Kanal {m['channel']:2d}: {m['name']} ({m['pulses_per_kwh']} imp/kWh) -> {m['meter_id'][:8] if m['meter_id'] else 'NICHT KONFIG.'}")
    log.info("=" * 60)

    # Validierung
    errors = []
    if not conf["api_url"]:
        errors.append("api_url nicht gesetzt")
    if not conf["device_key"]:
        errors.append("device_key nicht gesetzt")
    if not conf["device_id"]:
        errors.append("device_id nicht gesetzt")
    active = [m for m in meters if m["meter_id"]]
    if not active:
        errors.append("Keine Zaehler mit meter_id konfiguriert")
    if errors:
        for e in errors:
            log.error(f"KONFIG-FEHLER: {e}")
        sys.exit(1)

    init_db(conf["db_path"])

    # HAT-Kanaele initialisieren + State-Zeilen anlegen
    log.info("Initialisiere Sequent HAT...")
    for m in active:
        hat_setup_channel(m["channel"])
        ensure_meter_state_row(conf["db_path"], m)

        # kWh-Offset einmalig vom Portal laden (falls dort eingetragen
        # und lokal noch 0 ist)
        state = get_meter_state(conf["db_path"], m["meter_id"])
        if state and state["kwh_offset"] == 0.0 and state["last_counter"] == 0:
            offs = fetch_kwh_offset_from_portal(conf, m["meter_id"])
            if offs is not None and offs > 0:
                update_meter_state(conf["db_path"], m["meter_id"], {"kwh_offset": offs})
                log.info(f"  {m['name']}: kWh-Offset {offs:.3f} aus Portal uebernommen")

    log.info("OTA-Pruefung beim Start...")
    check_and_apply_update(conf)

    last_sync = 0
    last_gps_check = 0
    gps_cache = {}

    while True:
        try:
            now = time.time()

            # GPS alle 30s aktualisieren
            if conf.get("gps_enabled", "true") == "true" and (now - last_gps_check) >= 30:
                gps_cache = read_gps()
                last_gps_check = now

            # Alle Zaehler lesen
            for m in active:
                cnt = hat_read_counter(m["channel"])
                if cnt is None:
                    continue
                state = get_meter_state(conf["db_path"], m["meter_id"]) or {}
                last_cnt = state.get("last_counter", 0)
                c_off = state.get("counter_offset", 0)
                k_off = float(state.get("kwh_offset", 0.0))
                ppk = m["pulses_per_kwh"]

                # Counter-Reset erkennen (z.B. nach HAT-Stromausfall)
                if cnt < last_cnt:
                    pulses_lost = max(0, last_cnt - c_off)
                    k_off = k_off + pulses_lost / ppk
                    c_off = 0
                    log.warning(f"  {m['name']}: Counter-Reset erkannt, neuer kWh-Offset: {k_off:.3f}")

                pulses = max(0, cnt - c_off)
                kwh = k_off + pulses / ppk

                update_meter_state(conf["db_path"], m["meter_id"], {
                    "counter_offset": c_off,
                    "kwh_offset": k_off,
                    "last_counter": cnt,
                    "last_update": datetime.now(timezone.utc).isoformat(),
                })
                store_reading(conf["db_path"], m["meter_id"], cnt, kwh, gps_cache)

            # Periodisch zum Portal syncen
            if (now - last_sync) >= conf["sync_interval"]:
                synced = sync_to_portal(conf)
                if synced > 0:
                    log.info(f"Gesamt synchronisiert: {synced} Datensaetze")
                last_sync = now
                cleanup_old(conf["db_path"])
                check_and_apply_update(conf)

        except KeyboardInterrupt:
            log.info("Beendet durch Benutzer")
            break
        except Exception as e:
            log.error(f"Hauptschleife Fehler: {e}")
            time.sleep(conf["retry_delay"])

        time.sleep(conf["read_interval"])


if __name__ == "__main__":
    main()
