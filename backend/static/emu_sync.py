#!/usr/bin/env python3
"""
EMU Pi Sync - Eventenergie Portal
==================================
Synchronisiert lokale SQLite-Messdaten mit dem Eventenergie Portal.

Voraussetzungen:
  sudo apt install python3-pip
  pip3 install requests

Konfiguration:
  Datei /etc/emu_sync.conf erstellen (siehe unten) oder Umgebungsvariablen setzen.

Als Systemd-Dienst installieren:
  sudo cp emu_sync.py /opt/emu_sync.py
  sudo cp emu_sync.service /etc/systemd/system/
  sudo cp emu_sync.conf /etc/emu_sync.conf   # Konfiguration anpassen!
  sudo systemctl daemon-reload
  sudo systemctl enable emu_sync
  sudo systemctl start emu_sync

Status pruefen:
  sudo systemctl status emu_sync
  sudo journalctl -u emu_sync -f
"""

import sqlite3
import requests
import time
import json
import logging
import os
import sys
import configparser
from pathlib import Path

# ====== Konfiguration laden ======

def load_config():
    """Laedt Konfiguration aus /etc/emu_sync.conf oder Umgebungsvariablen."""
    config = {
        "api_url": "",
        "device_key": "",
        "device_id": "",
        "meter_id": "",
        "db_path": "/home/pi/emu.db",
        "batch_size": 500,
        "sync_interval": 10,
        "retry_delay": 30,
    }

    # 1. Versuche Config-Datei zu laden
    conf_path = Path("/etc/emu_sync.conf")
    if conf_path.exists():
        cp = configparser.ConfigParser()
        cp.read(str(conf_path))
        if "emu_sync" in cp:
            s = cp["emu_sync"]
            config["api_url"] = s.get("api_url", config["api_url"])
            config["device_key"] = s.get("device_key", config["device_key"])
            config["device_id"] = s.get("device_id", config["device_id"])
            config["meter_id"] = s.get("meter_id", config["meter_id"])
            config["db_path"] = s.get("db_path", config["db_path"])
            config["batch_size"] = int(s.get("batch_size", config["batch_size"]))
            config["sync_interval"] = int(s.get("sync_interval", config["sync_interval"]))
            config["retry_delay"] = int(s.get("retry_delay", config["retry_delay"]))

    # 2. Umgebungsvariablen ueberschreiben Config-Datei
    config["api_url"] = os.environ.get("EMU_API_URL", config["api_url"])
    config["device_key"] = os.environ.get("EMU_DEVICE_KEY", config["device_key"])
    config["device_id"] = os.environ.get("EMU_DEVICE_ID", config["device_id"])
    config["meter_id"] = os.environ.get("EMU_METER_ID", config["meter_id"])
    config["db_path"] = os.environ.get("EMU_DB_PATH", config["db_path"])

    return config


CFG = load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/var/log/emu_sync.log", mode="a"),
    ]
)
log = logging.getLogger("emu_sync")


# ====== Sync-Funktionen ======

def get_last_sync_id():
    """Fragt den Server nach der letzten Sync-ID."""
    try:
        resp = requests.get(
            f"{CFG['api_url']}/energy-monitoring/ingest/sync-state",
            params={
                "device_id": CFG["device_id"],
                "meter_id": CFG["meter_id"],
                "api_key": CFG["device_key"]
            },
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json().get("last_sync_id", 0)
        log.warning(f"Sync-State Fehler: {resp.status_code} {resp.text}")
    except requests.ConnectionError:
        log.warning("Server nicht erreichbar")
    except Exception as e:
        log.error(f"Sync-State Fehler: {e}")
    return None


def read_new_records(after_id, limit):
    """Liest neue Datensaetze aus der lokalen SQLite-DB."""
    try:
        conn = sqlite3.connect(CFG["db_path"])
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM emu_samples WHERE id > ? ORDER BY id ASC LIMIT ?",
            (after_id, limit)
        )
        rows = cursor.fetchall()
        records = [dict(row) for row in rows]
        conn.close()
        return records
    except sqlite3.OperationalError as e:
        log.error(f"SQLite Fehler (DB: {CFG['db_path']}): {e}")
        return []
    except Exception as e:
        log.error(f"DB Lesefehler: {e}")
        return []


def push_batch(records, last_id):
    """Sendet einen Batch an den Server."""
    payload = {
        "api_key": CFG["device_key"],
        "device_id": CFG["device_id"],
        "meter_id": CFG["meter_id"],
        "records": records,
        "last_sync_id": last_id,
    }
    resp = requests.post(
        f"{CFG['api_url']}/energy-monitoring/ingest",
        json=payload,
        timeout=60
    )
    if resp.status_code == 200:
        return resp.json()
    elif resp.status_code == 401:
        raise Exception("Authentifizierung fehlgeschlagen! Geraeteschluessel pruefen.")
    elif resp.status_code == 404:
        raise Exception(f"Geraet/Zaehler nicht gefunden: {resp.text}")
    else:
        raise Exception(f"Server Fehler {resp.status_code}: {resp.text}")


def check_db():
    """Prueft ob die lokale Datenbank existiert und lesbar ist."""
    p = Path(CFG["db_path"])
    if not p.exists():
        log.error(f"Datenbank nicht gefunden: {CFG['db_path']}")
        return False
    try:
        conn = sqlite3.connect(CFG["db_path"])
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM emu_samples")
        count = c.fetchone()[0]
        conn.close()
        log.info(f"Datenbank OK: {count} Datensaetze in emu_samples")
        return True
    except Exception as e:
        log.error(f"Datenbank Fehler: {e}")
        return False


# ====== Hauptprogramm ======

def main():
    log.info("=" * 55)
    log.info("  EMU Sync - Eventenergie Portal")
    log.info("=" * 55)
    log.info(f"  Server:     {CFG['api_url']}")
    log.info(f"  Device-ID:  {CFG['device_id']}")
    log.info(f"  Meter-ID:   {CFG['meter_id']}")
    log.info(f"  Schluessel: {CFG['device_key'][:8]}...")
    log.info(f"  DB:         {CFG['db_path']}")
    log.info(f"  Batch:      {CFG['batch_size']}")
    log.info(f"  Intervall:  {CFG['sync_interval']}s")
    log.info("=" * 55)

    # Validierung
    errors = []
    if not CFG["api_url"]:
        errors.append("api_url nicht gesetzt")
    if not CFG["device_key"]:
        errors.append("device_key nicht gesetzt")
    if not CFG["device_id"]:
        errors.append("device_id nicht gesetzt")
    if not CFG["meter_id"]:
        errors.append("meter_id nicht gesetzt")

    if errors:
        for e in errors:
            log.error(f"KONFIGURATIONSFEHLER: {e}")
        log.error("Bitte /etc/emu_sync.conf pruefen!")
        sys.exit(1)

    if not check_db():
        log.error("Datenbank-Check fehlgeschlagen!")
        sys.exit(1)

    log.info("Sync-Schleife gestartet...")
    consecutive_errors = 0

    while True:
        try:
            # 1. Letzte Sync-ID vom Server holen
            last_id = get_last_sync_id()
            if last_id is None:
                log.info(f"Server nicht erreichbar, naechster Versuch in {CFG['retry_delay']}s...")
                time.sleep(CFG["retry_delay"])
                continue

            # 2. Neue Datensaetze lesen
            records = read_new_records(last_id, CFG["batch_size"])

            if not records:
                time.sleep(CFG["sync_interval"])
                continue

            new_last_id = records[-1]["id"]
            log.info(f"Sende {len(records)} Datensaetze (ID {last_id+1} bis {new_last_id})")

            # 3. An Server senden
            result = push_batch(records, new_last_id)
            log.info(f"OK: {result.get('inserted', 0)} uebertragen")
            consecutive_errors = 0

            # Wenn noch mehr Daten, sofort weiter
            if len(records) >= CFG["batch_size"]:
                continue

        except requests.ConnectionError:
            consecutive_errors += 1
            delay = min(CFG["retry_delay"] * consecutive_errors, 300)
            log.warning(f"Keine Verbindung (Versuch {consecutive_errors}), warte {delay}s...")
            time.sleep(delay)
            continue
        except Exception as e:
            consecutive_errors += 1
            delay = min(CFG["retry_delay"] * consecutive_errors, 300)
            log.error(f"Fehler: {e}")
            time.sleep(delay)
            continue

        time.sleep(CFG["sync_interval"])


if __name__ == "__main__":
    main()
