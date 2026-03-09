#!/usr/bin/env python3
"""
Messkoffer Logger + Sync - Eventenergie Portal
================================================
Liest Shelly Pro 3EM + USB-GPS, speichert lokal in SQLite,
synchronisiert automatisch mit dem Portal wenn Internet da ist.

Voraussetzungen (werden vom Setup-Skript installiert):
  - python3, python3-gps, requests
  - gpsd (fuer USB-GPS)

Konfiguration: /etc/messkoffer.conf
Logs:          sudo journalctl -u messkoffer -f
"""

import sqlite3
import requests
import threading
import time
import json
import logging
import os
import sys
import configparser
from pathlib import Path
from datetime import datetime, timezone

# ====== GPS-Modul (optional) ======
try:
    from gps import gps as gpsd_connect, WATCH_ENABLE, WATCH_NEWSTYLE
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False


# ====== Konfiguration ======

def load_config():
    config = {
        "shelly_ip": "192.168.88.240",
        "api_url": "",
        "device_key": "",
        "device_id": "",
        "meter_id": "",
        "db_path": "/var/lib/messkoffer/messkoffer.sqlite",
        "log_interval": 1,
        "sync_interval": 10,
        "sync_batch_size": 500,
        "retry_delay": 30,
        "max_db_size_gb": 60,
        "cleanup_check_interval": 300,
    }

    conf_path = Path("/etc/messkoffer.conf")
    if conf_path.exists():
        cp = configparser.ConfigParser()
        cp.read(str(conf_path))
        if "messkoffer" in cp:
            s = cp["messkoffer"]
            for key in config:
                if key in s:
                    val = s[key]
                    if isinstance(config[key], int):
                        config[key] = int(val)
                    elif isinstance(config[key], float):
                        config[key] = float(val)
                    else:
                        config[key] = val

    # Umgebungsvariablen ueberschreiben
    for env_key, conf_key in [
        ("MK_SHELLY_IP", "shelly_ip"),
        ("MK_API_URL", "api_url"),
        ("MK_DEVICE_KEY", "device_key"),
        ("MK_DEVICE_ID", "device_id"),
        ("MK_METER_ID", "meter_id"),
        ("MK_DB_PATH", "db_path"),
    ]:
        val = os.environ.get(env_key)
        if val:
            config[conf_key] = val

    return config


CFG = load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("messkoffer")

# ====== Globaler GPS-Zustand ======
gps_data = {"lat": None, "lon": None, "alt": None, "speed": None, "fix": 0}
gps_lock = threading.Lock()


# ====== Datenbank ======

def init_db():
    """Erstellt DB und Tabelle falls noetig."""
    db_dir = os.path.dirname(CFG["db_path"])
    os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(CFG["db_path"])
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            a_current REAL, a_voltage REAL, a_act_power REAL, a_aprt_power REAL, a_pf REAL, a_freq REAL,
            b_current REAL, b_voltage REAL, b_act_power REAL, b_aprt_power REAL, b_pf REAL, b_freq REAL,
            c_current REAL, c_voltage REAL, c_act_power REAL, c_aprt_power REAL, c_pf REAL, c_freq REAL,
            n_current REAL, total_current REAL, total_act_power REAL, total_aprt_power REAL,
            total_energy_wh REAL, total_returned_wh REAL,
            gps_lat REAL, gps_lon REAL, gps_alt REAL, gps_speed REAL, gps_fix INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_measurements_ts ON measurements(ts)")
    conn.commit()
    conn.close()
    log.info(f"Datenbank bereit: {CFG['db_path']}")


def get_db_size_gb():
    """Gibt die aktuelle DB-Groesse in GB zurueck."""
    try:
        return os.path.getsize(CFG["db_path"]) / (1024 ** 3)
    except OSError:
        return 0


def cleanup_db():
    """Loescht aelteste Datensaetze wenn DB > max_db_size_gb."""
    size_gb = get_db_size_gb()
    if size_gb <= CFG["max_db_size_gb"]:
        return

    log.warning(f"DB ist {size_gb:.1f} GB (Limit: {CFG['max_db_size_gb']} GB), loesche aelteste Daten...")
    try:
        conn = sqlite3.connect(CFG["db_path"])
        # Loesche 5% der aeltesten Daten pro Durchlauf
        total = conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
        delete_count = max(int(total * 0.05), 10000)
        conn.execute(f"""
            DELETE FROM measurements WHERE id IN (
                SELECT id FROM measurements ORDER BY id ASC LIMIT {delete_count}
            )
        """)
        conn.commit()
        # VACUUM um Speicher freizugeben
        conn.execute("VACUUM")
        conn.commit()
        conn.close()
        new_size = get_db_size_gb()
        log.info(f"Bereinigt: {delete_count} Datensaetze geloescht, DB jetzt {new_size:.1f} GB")
    except Exception as e:
        log.error(f"DB-Bereinigung Fehler: {e}")


# ====== Shelly Pro 3EM lesen ======

def read_shelly():
    """Liest aktuelle Messwerte vom Shelly Pro 3EM."""
    try:
        resp = requests.get(
            f"http://{CFG['shelly_ip']}/rpc/Shelly.GetStatus",
            timeout=3
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        em = data.get("em:0", {})
        emdata = data.get("emdata:0", {})

        return {
            "a_current": em.get("a_current"),
            "a_voltage": em.get("a_voltage"),
            "a_act_power": em.get("a_act_power"),
            "a_aprt_power": em.get("a_aprt_power"),
            "a_pf": em.get("a_pf"),
            "a_freq": em.get("a_freq"),
            "b_current": em.get("b_current"),
            "b_voltage": em.get("b_voltage"),
            "b_act_power": em.get("b_act_power"),
            "b_aprt_power": em.get("b_aprt_power"),
            "b_pf": em.get("b_pf"),
            "b_freq": em.get("b_freq"),
            "c_current": em.get("c_current"),
            "c_voltage": em.get("c_voltage"),
            "c_act_power": em.get("c_act_power"),
            "c_aprt_power": em.get("c_aprt_power"),
            "c_pf": em.get("c_pf"),
            "c_freq": em.get("c_freq"),
            "n_current": em.get("n_current"),
            "total_current": em.get("total_current"),
            "total_act_power": em.get("total_act_power"),
            "total_aprt_power": em.get("total_aprt_power"),
            "total_energy_wh": emdata.get("total_act", 0),
            "total_returned_wh": emdata.get("total_act_ret", 0),
        }
    except requests.ConnectionError:
        return None
    except Exception as e:
        log.debug(f"Shelly Lesefehler: {e}")
        return None


# ====== GPS Thread ======

def gps_thread():
    """Liest kontinuierlich GPS-Daten via gpsd."""
    global gps_data
    if not GPS_AVAILABLE:
        log.warning("GPS-Modul nicht installiert (python3-gps). GPS deaktiviert.")
        return

    while True:
        try:
            session = gpsd_connect(mode=WATCH_ENABLE | WATCH_NEWSTYLE)
            log.info("GPS verbunden (gpsd)")
            while True:
                report = session.next()
                if report["class"] == "TPV":
                    with gps_lock:
                        gps_data["lat"] = report.get("lat")
                        gps_data["lon"] = report.get("lon")
                        gps_data["alt"] = report.get("alt")
                        gps_data["speed"] = report.get("speed")
                        gps_data["fix"] = report.get("mode", 0)
        except StopIteration:
            log.warning("GPS-Verbindung verloren, reconnect in 5s...")
        except Exception as e:
            log.warning(f"GPS Fehler: {e}, reconnect in 5s...")
        time.sleep(5)


def get_gps():
    """Gibt aktuelle GPS-Daten zurueck."""
    with gps_lock:
        return dict(gps_data)


# ====== Logger Thread (Hauptschleife) ======

def logger_loop():
    """Liest Shelly + GPS jede Sekunde, speichert in SQLite."""
    conn = sqlite3.connect(CFG["db_path"])
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    read_count = 0
    error_count = 0
    last_cleanup = time.time()

    log.info(f"Logger gestartet: Shelly {CFG['shelly_ip']} alle {CFG['log_interval']}s")

    while True:
        start = time.time()

        shelly = read_shelly()
        gps = get_gps()
        ts = datetime.now(timezone.utc).isoformat()

        if shelly:
            try:
                conn.execute("""
                    INSERT INTO measurements (
                        ts,
                        a_current, a_voltage, a_act_power, a_aprt_power, a_pf, a_freq,
                        b_current, b_voltage, b_act_power, b_aprt_power, b_pf, b_freq,
                        c_current, c_voltage, c_act_power, c_aprt_power, c_pf, c_freq,
                        n_current, total_current, total_act_power, total_aprt_power,
                        total_energy_wh, total_returned_wh,
                        gps_lat, gps_lon, gps_alt, gps_speed, gps_fix
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    ts,
                    shelly["a_current"], shelly["a_voltage"], shelly["a_act_power"],
                    shelly["a_aprt_power"], shelly["a_pf"], shelly["a_freq"],
                    shelly["b_current"], shelly["b_voltage"], shelly["b_act_power"],
                    shelly["b_aprt_power"], shelly["b_pf"], shelly["b_freq"],
                    shelly["c_current"], shelly["c_voltage"], shelly["c_act_power"],
                    shelly["c_aprt_power"], shelly["c_pf"], shelly["c_freq"],
                    shelly["n_current"], shelly["total_current"],
                    shelly["total_act_power"], shelly["total_aprt_power"],
                    shelly["total_energy_wh"], shelly["total_returned_wh"],
                    gps["lat"], gps["lon"], gps["alt"], gps["speed"], gps["fix"],
                ))
                conn.commit()
                read_count += 1
                error_count = 0

                if read_count % 60 == 0:
                    log.info(f"Logging OK: {read_count} Datensaetze | "
                             f"P={shelly['total_act_power']:.0f}W | "
                             f"GPS={'Fix' if gps['fix'] >= 2 else 'kein Fix'}")
            except Exception as e:
                log.error(f"SQLite Schreibfehler: {e}")
        else:
            error_count += 1
            if error_count <= 3 or error_count % 30 == 0:
                log.warning(f"Shelly nicht erreichbar ({error_count}x)")

        # DB-Groesse pruefen (alle 5 Minuten)
        if time.time() - last_cleanup > CFG["cleanup_check_interval"]:
            cleanup_db()
            last_cleanup = time.time()

        # Exaktes 1-Sekunden-Timing
        elapsed = time.time() - start
        sleep_time = max(0, CFG["log_interval"] - elapsed)
        time.sleep(sleep_time)


# ====== Sync Thread ======

def map_to_portal(row):
    """Mappt SQLite-Zeile auf Portal-API-Format (Watt -> kW)."""
    def safe(val):
        try:
            return float(val) if val is not None else 0
        except (ValueError, TypeError):
            return 0

    return {
        "id": row["id"],
        "ts_utc": row["ts"],
        "meter_ts": 0,
        "I_L1": safe(row["a_current"]),
        "I_L2": safe(row["b_current"]),
        "I_L3": safe(row["c_current"]),
        "I_sum": safe(row["total_current"]),
        "U_L1": safe(row["a_voltage"]),
        "U_L2": safe(row["b_voltage"]),
        "U_L3": safe(row["c_voltage"]),
        "F_Hz": safe(row["a_freq"]),
        "P_sum_kW": round(safe(row["total_act_power"]) / 1000, 4),
        "P_L1_kW": round(safe(row["a_act_power"]) / 1000, 4),
        "P_L2_kW": round(safe(row["b_act_power"]) / 1000, 4),
        "P_L3_kW": round(safe(row["c_act_power"]) / 1000, 4),
        "Q_sum": round(safe(row["total_aprt_power"]) / 1000, 4),
        "Q_L1": round(safe(row["a_aprt_power"]) / 1000, 4),
        "Q_L2": round(safe(row["b_aprt_power"]) / 1000, 4),
        "Q_L3": round(safe(row["c_aprt_power"]) / 1000, 4),
        "PF_L1": safe(row["a_pf"]),
        "PF_L2": safe(row["b_pf"]),
        "PF_L3": safe(row["c_pf"]),
        "E_imp_kWh": round(safe(row["total_energy_wh"]) / 1000, 4),
        "E_exp_kWh": round(safe(row["total_returned_wh"]) / 1000, 4),
        "gps_lat": row["gps_lat"],
        "gps_lon": row["gps_lon"],
        "gps_alt_m": row["gps_alt"],
        "gps_speed_mps": row["gps_speed"],
    }


def get_last_sync_id():
    """Fragt den Server nach der letzten synchronisierten ID."""
    try:
        resp = requests.get(
            f"{CFG['api_url']}/energy-monitoring/ingest/sync-state",
            params={
                "device_id": CFG["device_id"],
                "meter_id": CFG["meter_id"],
                "api_key": CFG["device_key"],
            },
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("last_sync_id", 0)
    except Exception:
        pass
    return None


def push_batch(records, last_id):
    """Sendet Batch an das Portal."""
    resp = requests.post(
        f"{CFG['api_url']}/energy-monitoring/ingest",
        json={
            "api_key": CFG["device_key"],
            "device_id": CFG["device_id"],
            "meter_id": CFG["meter_id"],
            "records": records,
            "last_sync_id": last_id,
        },
        timeout=60
    )
    if resp.status_code == 200:
        return resp.json()
    raise Exception(f"Server {resp.status_code}: {resp.text}")


def sync_loop():
    """Synchronisiert lokale Daten mit dem Portal (Hintergrund-Thread)."""
    if not CFG["api_url"] or not CFG["device_key"]:
        log.warning("Sync deaktiviert: api_url oder device_key nicht gesetzt")
        return

    consecutive_errors = 0
    log.info("Sync-Thread gestartet")

    while True:
        try:
            last_id = get_last_sync_id()
            if last_id is None:
                consecutive_errors += 1
                delay = min(CFG["retry_delay"] * consecutive_errors, 300)
                if consecutive_errors <= 3 or consecutive_errors % 10 == 0:
                    log.info(f"Portal nicht erreichbar, warte {delay}s...")
                time.sleep(delay)
                continue

            # Neue Datensaetze aus SQLite lesen
            conn = sqlite3.connect(CFG["db_path"])
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM measurements WHERE id > ? ORDER BY id ASC LIMIT ?",
                (last_id, CFG["sync_batch_size"])
            ).fetchall()
            conn.close()

            if not rows:
                time.sleep(CFG["sync_interval"])
                continue

            records = [map_to_portal(dict(r)) for r in rows]
            new_last_id = records[-1]["id"]

            result = push_batch(records, new_last_id)
            inserted = result.get("inserted", 0)
            log.info(f"Sync OK: {inserted} Datensaetze (bis ID {new_last_id})")
            consecutive_errors = 0

            # Sofort weiter wenn voller Batch
            if len(records) >= CFG["sync_batch_size"]:
                continue

        except requests.ConnectionError:
            consecutive_errors += 1
            delay = min(CFG["retry_delay"] * consecutive_errors, 300)
            time.sleep(delay)
            continue
        except Exception as e:
            consecutive_errors += 1
            delay = min(CFG["retry_delay"] * consecutive_errors, 300)
            log.error(f"Sync Fehler: {e}")
            time.sleep(delay)
            continue

        time.sleep(CFG["sync_interval"])


# ====== Hauptprogramm ======

def main():
    log.info("=" * 55)
    log.info("  Messkoffer Logger - Eventenergie Portal")
    log.info("=" * 55)
    log.info(f"  Shelly:     {CFG['shelly_ip']}")
    log.info(f"  DB:         {CFG['db_path']}")
    log.info(f"  Max. DB:    {CFG['max_db_size_gb']} GB")
    log.info(f"  Intervall:  {CFG['log_interval']}s")
    log.info(f"  Server:     {CFG['api_url'] or '(kein Sync)'}")
    log.info(f"  Device-ID:  {CFG['device_id'] or '(nicht gesetzt)'}")
    log.info(f"  GPS:        {'verfuegbar' if GPS_AVAILABLE else 'nicht installiert'}")
    log.info("=" * 55)

    # DB initialisieren
    init_db()

    # GPS-Thread starten
    t_gps = threading.Thread(target=gps_thread, daemon=True)
    t_gps.start()

    # Sync-Thread starten
    t_sync = threading.Thread(target=sync_loop, daemon=True)
    t_sync.start()

    # Logger-Hauptschleife (blockiert)
    logger_loop()


if __name__ == "__main__":
    main()
