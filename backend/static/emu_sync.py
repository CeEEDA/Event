#!/usr/bin/env python3
"""
EMU Pi Sync Script
==================
Synchronisiert lokale SQLite-Daten (emu.db) mit dem Eventenergie Portal.
Laeuft als Hintergrund-Dienst auf dem Raspberry Pi.

Konfiguration:
  - API_URL:    URL des Backends (z.B. https://mqtt-monitor-hub.preview.emergentagent.com/api)
  - API_KEY:    Ingest API-Schluessel (aus dem Admin-Bereich)
  - DEVICE_ID:  Messkoffer-ID
  - METER_ID:   Zaehler-ID
  - DB_PATH:    Pfad zur lokalen SQLite-Datenbank

Installation auf dem Pi:
  pip3 install requests
  python3 emu_sync.py

Als Systemd-Dienst:
  sudo cp emu_sync.service /etc/systemd/system/
  sudo systemctl enable emu_sync
  sudo systemctl start emu_sync
"""

import sqlite3
import requests
import time
import json
import logging
import os
import sys

# ====== KONFIGURATION ======
API_URL    = os.environ.get("EMU_API_URL", "https://mqtt-monitor-hub.preview.emergentagent.com/api")
API_KEY    = os.environ.get("EMU_API_KEY", "HIER_API_KEY_EINTRAGEN")
DEVICE_ID  = os.environ.get("EMU_DEVICE_ID", "HIER_DEVICE_ID_EINTRAGEN")
METER_ID   = os.environ.get("EMU_METER_ID", "HIER_METER_ID_EINTRAGEN")
DB_PATH    = os.environ.get("EMU_DB_PATH", "/home/pi/emu.db")

BATCH_SIZE     = 500      # Datensaetze pro Batch
SYNC_INTERVAL  = 10       # Sekunden zwischen Sync-Versuchen
RETRY_DELAY    = 30       # Sekunden bei Verbindungsfehler
# ============================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/emu_sync.log", mode="a"),
    ]
)
log = logging.getLogger("emu_sync")


def get_last_sync_id():
    """Fragt den Server nach der letzten sync ID."""
    try:
        resp = requests.get(
            f"{API_URL}/energy-monitoring/ingest/sync-state",
            params={"device_id": DEVICE_ID, "meter_id": METER_ID, "api_key": API_KEY},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("last_sync_id", 0)
        log.warning(f"Sync-State Fehler: {resp.status_code} {resp.text}")
    except requests.ConnectionError:
        log.warning("Keine Verbindung zum Server")
    except Exception as e:
        log.error(f"Sync-State Fehler: {e}")
    return None


def read_new_records(db_path, after_id, limit):
    """Liest neue Datensaetze aus der lokalen SQLite-DB."""
    try:
        conn = sqlite3.connect(db_path)
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
    except Exception as e:
        log.error(f"DB Lesefehler: {e}")
        return []


def push_batch(records, last_id):
    """Sendet einen Batch an den Server."""
    payload = {
        "api_key": API_KEY,
        "device_id": DEVICE_ID,
        "meter_id": METER_ID,
        "records": records,
        "last_sync_id": last_id,
    }
    resp = requests.post(
        f"{API_URL}/energy-monitoring/ingest",
        json=payload,
        timeout=30
    )
    if resp.status_code == 200:
        return resp.json()
    else:
        raise Exception(f"Server Fehler: {resp.status_code} {resp.text}")


def main():
    log.info("=" * 50)
    log.info("EMU Sync gestartet")
    log.info(f"  Server:    {API_URL}")
    log.info(f"  Device:    {DEVICE_ID}")
    log.info(f"  Meter:     {METER_ID}")
    log.info(f"  DB:        {DB_PATH}")
    log.info(f"  Batch:     {BATCH_SIZE}")
    log.info(f"  Intervall: {SYNC_INTERVAL}s")
    log.info("=" * 50)

    if API_KEY == "HIER_API_KEY_EINTRAGEN":
        log.error("API_KEY nicht konfiguriert! Bitte setzen.")
        sys.exit(1)
    if DEVICE_ID == "HIER_DEVICE_ID_EINTRAGEN":
        log.error("DEVICE_ID nicht konfiguriert! Bitte setzen.")
        sys.exit(1)

    while True:
        try:
            # 1. Letzte sync ID vom Server holen
            last_id = get_last_sync_id()
            if last_id is None:
                log.info(f"Server nicht erreichbar, warte {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                continue

            log.info(f"Letzter Sync: ID {last_id}")

            # 2. Neue Datensaetze lesen
            records = read_new_records(DB_PATH, last_id, BATCH_SIZE)

            if not records:
                log.debug("Keine neuen Daten")
                time.sleep(SYNC_INTERVAL)
                continue

            new_last_id = records[-1]["id"]
            log.info(f"Sende {len(records)} Datensaetze (ID {last_id+1} bis {new_last_id})")

            # 3. An Server senden
            result = push_batch(records, new_last_id)
            log.info(f"Erfolgreich: {result.get('inserted', 0)} Datensaetze uebertragen")

            # Wenn noch mehr Daten vorhanden, sofort weiter synchen
            if len(records) >= BATCH_SIZE:
                continue

        except requests.ConnectionError:
            log.warning(f"Verbindung fehlgeschlagen, warte {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
            continue
        except Exception as e:
            log.error(f"Fehler: {e}", exc_info=True)
            time.sleep(RETRY_DELAY)
            continue

        time.sleep(SYNC_INTERVAL)


if __name__ == "__main__":
    main()
