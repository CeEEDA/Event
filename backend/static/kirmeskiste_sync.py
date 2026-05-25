#!/usr/bin/env python3
"""
Kirmeskiste Sync - Eventenergie Portal
=======================================
Liest 4x EMU Professional II 3/5 Zaehler via Modbus TCP
und synchronisiert die Messdaten mit dem Eventenergie Portal.

Hardware:
  - Raspberry Pi (gleiche Hardware wie Messkoffer)
  - 4x EMU Professional II 3/5 (Modbus TCP, feste LAN-IPs)
  - Router mit festen IP-Adressen im LAN

Voraussetzungen:
  sudo apt install python3-pip
  pip3 install pymodbus requests

Konfiguration:
  Datei /etc/kirmeskiste.conf erstellen oder Setup-Skript verwenden.

Status pruefen:
  sudo systemctl status kirmeskiste_sync
  sudo journalctl -u kirmeskiste_sync -f
"""

import struct
import time
import json
import logging
import os
import sys
import sqlite3
import hashlib
import configparser
from pathlib import Path
from datetime import datetime, timezone

import struct
import requests
from pymodbus.client import ModbusTcpClient


# ====== Konstanten: EMU Professional II Modbus Register ======
# Momentanwerte (Float32, Big-Endian, Holding Register, Function Code 03)
REG_P_SUM   = 9000   # Active Power L123 [W] (EMU liefert Watt, Backend rechnet in kW um)
REG_P_L1    = 9002   # Active Power L1 [W]
REG_P_L2    = 9004   # Active Power L2 [W]
REG_P_L3    = 9006   # Active Power L3 [W]
REG_I_SUM   = 9100   # Current L123 [A]
REG_I_L1    = 9102   # Current L1 [A]
REG_I_L2    = 9104   # Current L2 [A]
REG_I_L3    = 9106   # Current L3 [A]
REG_U_L1    = 9200   # Voltage L1-N [V]
REG_U_L2    = 9202   # Voltage L2-N [V]
REG_U_L3    = 9204   # Voltage L3-N [V]
REG_PF_L1   = 9300   # Power Factor L1
REG_PF_L2   = 9302   # Power Factor L2
REG_PF_L3   = 9304   # Power Factor L3
REG_FREQ    = 9310   # Frequency [Hz]
# Energiezaehler (UInt64, kWh direkt)
REG_E_IMP   = 7000   # Active Energy Import L123 Total [kWh]
REG_E_EXP   = 7020   # Active Energy Export L123 Total [kWh]
# Geraeteinfo
REG_SERIAL  = 5000   # Seriennummer (UInt32)
# Stromausfall-Zaehler
REG_PWRFAIL = 11000  # Power fail count (UInt16)


# ====== Konfiguration ======

DEFAULT_CONF = {
    "api_url": "",
    "device_key": "",
    "device_id": "",
    "db_path": "/var/lib/kirmeskiste/kirmeskiste.sqlite",
    "read_interval": 10,
    "sync_interval": 1200,
    "retry_delay": 30,
    "batch_size": 500,
}

DEFAULT_METERS = [
    {"meter_id": "", "ip": "192.168.88.240", "port": 502, "slave_id": 1, "name": "Zaehler 1"},
    {"meter_id": "", "ip": "192.168.88.241", "port": 502, "slave_id": 1, "name": "Zaehler 2"},
    {"meter_id": "", "ip": "192.168.88.242", "port": 502, "slave_id": 1, "name": "Zaehler 3"},
    {"meter_id": "", "ip": "192.168.88.243", "port": 502, "slave_id": 1, "name": "Zaehler 4"},
]


def load_config():
    conf = dict(DEFAULT_CONF)
    meters = list(DEFAULT_METERS)

    conf_path = Path("/etc/kirmeskiste.conf")
    if conf_path.exists():
        cp = configparser.ConfigParser()
        cp.read(str(conf_path))

        if "kirmeskiste" in cp:
            s = cp["kirmeskiste"]
            conf["api_url"] = s.get("api_url", conf["api_url"])
            conf["device_key"] = s.get("device_key", conf["device_key"])
            conf["device_id"] = s.get("device_id", conf["device_id"])
            conf["db_path"] = s.get("db_path", conf["db_path"])
            conf["read_interval"] = int(s.get("read_interval", conf["read_interval"]))
            conf["sync_interval"] = int(s.get("sync_interval", conf["sync_interval"]))
            conf["retry_delay"] = int(s.get("retry_delay", conf["retry_delay"]))
            conf["batch_size"] = int(s.get("batch_size", conf["batch_size"]))

        meters = []
        for i in range(1, 9):
            section = f"meter_{i}"
            if section in cp:
                m = cp[section]
                meters.append({
                    "meter_id": m.get("meter_id", ""),
                    "ip": m.get("ip", f"192.168.1.{100+i}"),
                    "port": int(m.get("port", "502")),
                    "slave_id": int(m.get("slave_id", "1")),
                    "name": m.get("name", f"Zaehler {i}"),
                })

    # Env overrides
    conf["api_url"] = os.environ.get("KIRMES_API_URL", conf["api_url"])
    conf["device_key"] = os.environ.get("KIRMES_DEVICE_KEY", conf["device_key"])
    conf["device_id"] = os.environ.get("KIRMES_DEVICE_ID", conf["device_id"])

    return conf, meters


# ====== Logging ======

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("kirmeskiste")

# ====== OTA Auto-Update ======

SCRIPT_VERSION = "1.0.0"

def get_script_hash():
    """Berechnet den SHA256-Hash des aktuellen Scripts."""
    try:
        script_path = Path(os.path.abspath(__file__))
        return hashlib.sha256(script_path.read_bytes()).hexdigest()
    except Exception:
        return ""


def check_and_apply_update(conf):
    """Prueft ob ein Update verfuegbar ist und installiert es."""
    if not conf.get("api_url"):
        return False
    try:
        resp = requests.get(
            f"{conf['api_url']}/system/ota/check",
            params={
                "api_key": conf["device_key"],
                "device_id": conf["device_id"],
                "hash": get_script_hash(),
                "version": SCRIPT_VERSION,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            log.warning(f"Update-Check Fehler: {resp.status_code}")
            return False

        data = resp.json()
        if not data.get("update_available"):
            log.info(f"Kein Update verfuegbar (Version {SCRIPT_VERSION})")
            return False

        new_version = data.get("version", "?")
        log.info(f"Update verfuegbar: {SCRIPT_VERSION} -> {new_version}")
        log.info(f"Changelog: {data.get('changelog', '-')}")

        # Download
        dl_resp = requests.get(
            f"{conf['api_url']}/system/ota/download",
            params={
                "api_key": conf["device_key"],
                "device_id": conf["device_id"],
            },
            timeout=60,
        )
        if dl_resp.status_code != 200:
            log.error(f"Download Fehler: {dl_resp.status_code}")
            return False

        new_content = dl_resp.content
        new_hash = hashlib.sha256(new_content).hexdigest()
        expected_hash = data.get("file_hash", "")

        if expected_hash and new_hash != expected_hash:
            log.error(f"Hash-Mismatch! Erwartet: {expected_hash[:16]}... Erhalten: {new_hash[:16]}...")
            return False

        # Backup + Replace
        script_path = Path(os.path.abspath(__file__))
        backup_path = script_path.with_suffix(".py.bak")

        log.info("Erstelle Backup...")
        if script_path.exists():
            import shutil
            shutil.copy2(str(script_path), str(backup_path))

        log.info("Installiere Update...")
        script_path.write_bytes(new_content)
        os.chmod(str(script_path), 0o755)

        log.info(f"Update auf Version {new_version} installiert!")
        log.info("Starte Dienst neu...")

        # Neustart via systemd
        import subprocess
        subprocess.run(["sudo", "systemctl", "restart", "kirmeskiste_sync"], check=False)
        sys.exit(0)

    except requests.ConnectionError:
        log.debug("Portal nicht erreichbar fuer Update-Check")
    except Exception as e:
        log.error(f"Update-Check Fehler: {e}")
    return False


# ====== Modbus Lesen ======

def _read_holding(client, register, count, slave_id):
    """Wrapper: liest Holding Registers (FC 03) - kompatibel mit allen pymodbus-Versionen."""
    import pymodbus
    version = tuple(int(x) for x in pymodbus.__version__.split('.')[:2])
    if version >= (3, 8):
        return client.read_holding_registers(register, count=count, device_id=slave_id)
    else:
        try:
            return client.read_holding_registers(register, count, slave=slave_id)
        except TypeError:
            return client.read_holding_registers(register, count, unit=slave_id)


def read_float32(client, register, slave_id=1):
    """Liest einen Float32-Wert (Big-Endian) von einem Holding Register (FC 03)."""
    try:
        result = _read_holding(client, register - 1, 2, slave_id)
        if result.isError():
            return None
        raw = struct.pack('>HH', result.registers[0], result.registers[1])
        return round(struct.unpack('>f', raw)[0], 4)
    except Exception:
        return None


def read_uint64(client, register, slave_id=1):
    """Liest einen UInt64-Wert (Big-Endian) von einem Holding Register (FC 03)."""
    try:
        result = _read_holding(client, register - 1, 4, slave_id)
        if result.isError():
            return None
        raw = struct.pack('>HHHH', *result.registers[:4])
        return struct.unpack('>Q', raw)[0]
    except Exception:
        return None


def read_uint32(client, register, slave_id=1):
    """Liest einen UInt32-Wert von einem Holding Register (FC 03)."""
    try:
        result = _read_holding(client, register - 1, 2, slave_id)
        if result.isError():
            return None
        raw = struct.pack('>HH', result.registers[0], result.registers[1])
        return struct.unpack('>I', raw)[0]
    except Exception:
        return None


def read_uint16(client, register, slave_id=1):
    """Liest einen UInt16-Wert von einem Holding Register (FC 03)."""
    try:
        result = _read_holding(client, register - 1, 1, slave_id)
        if result.isError():
            return None
        return result.registers[0]
    except Exception:
        return None


def read_meter(ip, port, slave_id, meter_name):
    """Liest alle relevanten Werte von einem EMU Professional II Zaehler."""
    client = ModbusTcpClient(ip, port=port, timeout=5)
    data = {
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "online": False,
        "error": None,
    }

    try:
        if not client.connect():
            data["error"] = f"Verbindung zu {ip}:{port} fehlgeschlagen"
            log.warning(f"[{meter_name}] {data['error']}")
            return data

        # Seriennummer
        serial = read_uint32(client, REG_SERIAL, slave_id)

        # Momentanwerte (Float32) - EMU liefert Watt, Backend rechnet in kW um
        data["P_sum_kW"] = read_float32(client, REG_P_SUM, slave_id) or 0
        data["P_L1_kW"]  = read_float32(client, REG_P_L1, slave_id) or 0
        data["P_L2_kW"]  = read_float32(client, REG_P_L2, slave_id) or 0
        data["P_L3_kW"]  = read_float32(client, REG_P_L3, slave_id) or 0
        data["I_sum"]    = read_float32(client, REG_I_SUM, slave_id) or 0
        data["I_L1"]     = read_float32(client, REG_I_L1, slave_id) or 0
        data["I_L2"]     = read_float32(client, REG_I_L2, slave_id) or 0
        data["I_L3"]     = read_float32(client, REG_I_L3, slave_id) or 0
        data["U_L1"]     = read_float32(client, REG_U_L1, slave_id) or 0
        data["U_L2"]     = read_float32(client, REG_U_L2, slave_id) or 0
        data["U_L3"]     = read_float32(client, REG_U_L3, slave_id) or 0
        data["PF_L1"]    = read_float32(client, REG_PF_L1, slave_id) or 0
        data["PF_L2"]    = read_float32(client, REG_PF_L2, slave_id) or 0
        data["PF_L3"]    = read_float32(client, REG_PF_L3, slave_id) or 0
        data["F_Hz"]     = read_float32(client, REG_FREQ, slave_id) or 0

        # Energiezaehler (UInt64, Wert in kWh direkt)
        e_imp_raw = read_uint64(client, REG_E_IMP, slave_id)
        e_exp_raw = read_uint64(client, REG_E_EXP, slave_id)
        data["E_imp_kWh"] = round(e_imp_raw * 1.0, 1) if e_imp_raw is not None else 0
        data["E_exp_kWh"] = round(e_exp_raw * 1.0, 1) if e_exp_raw is not None else 0

        # Stromausfaelle
        data["power_fail_count"] = read_uint16(client, REG_PWRFAIL, slave_id) or 0

        data["serial_number"] = serial
        data["online"] = True

        log.info(
            f"[{meter_name}] P={data['P_sum_kW']:.3f}kW "
            f"U={data['U_L1']:.0f}/{data['U_L2']:.0f}/{data['U_L3']:.0f}V "
            f"I={data['I_sum']:.1f}A F={data['F_Hz']:.1f}Hz "
            f"E={data['E_imp_kWh']:.1f}kWh"
        )

    except Exception as e:
        data["error"] = str(e)
        log.error(f"[{meter_name}] Lesefehler: {e}")
    finally:
        client.close()

    return data


# ====== Lokale SQLite Datenbank ======

def init_db(db_path):
    """Erstellt die lokale SQLite-Datenbank fuer Zwischenspeicherung."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meter_id TEXT NOT NULL,
            ts_utc TEXT NOT NULL,
            data_json TEXT NOT NULL,
            synced INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_synced ON readings(synced)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_meter ON readings(meter_id)")
    conn.commit()
    conn.close()
    log.info(f"Datenbank initialisiert: {db_path}")


def store_reading(db_path, meter_id, data):
    """Speichert einen Messwert in der lokalen DB."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO readings (meter_id, ts_utc, data_json) VALUES (?, ?, ?)",
        (meter_id, data["ts_utc"], json.dumps(data))
    )
    conn.commit()
    conn.close()


def get_unsynced(db_path, limit=500):
    """Holt ungesyncte Datensaetze aus der lokalen DB."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, meter_id, ts_utc, data_json FROM readings WHERE synced=0 ORDER BY id ASC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_synced(db_path, ids):
    """Markiert Datensaetze als synchronisiert."""
    if not ids:
        return
    conn = sqlite3.connect(db_path)
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"UPDATE readings SET synced=1 WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.close()


def cleanup_old(db_path, keep_days=7):
    """Loescht alte, bereits synchronisierte Datensaetze."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "DELETE FROM readings WHERE synced=1 AND created_at < datetime('now', ?)",
        (f"-{keep_days} days",)
    )
    conn.commit()
    conn.close()


# ====== Portal Sync ======

def sync_to_portal(conf, meters):
    """Sendet ungesyncte Daten an das Portal."""
    unsynced = get_unsynced(conf["db_path"], conf["batch_size"])
    if not unsynced:
        return 0

    # Gruppiere nach meter_id
    by_meter = {}
    for row in unsynced:
        mid = row["meter_id"]
        if mid not in by_meter:
            by_meter[mid] = []
        by_meter[mid].append(row)

    total_synced = 0

    for meter_id, rows in by_meter.items():
        records = []
        row_ids = []
        for row in rows:
            data = json.loads(row["data_json"])
            # Entferne lokale Felder, behalte Portal-Format
            portal_record = {
                "ts_utc": data.get("ts_utc", ""),
                "meter_ts": 0,
                "I_L1": data.get("I_L1", 0),
                "I_L2": data.get("I_L2", 0),
                "I_L3": data.get("I_L3", 0),
                "I_sum": data.get("I_sum", 0),
                "U_L1": data.get("U_L1", 0),
                "U_L2": data.get("U_L2", 0),
                "U_L3": data.get("U_L3", 0),
                "F_Hz": data.get("F_Hz", 0),
                "P_sum_kW": data.get("P_sum_kW", 0),
                "P_L1_kW": data.get("P_L1_kW", 0),
                "P_L2_kW": data.get("P_L2_kW", 0),
                "P_L3_kW": data.get("P_L3_kW", 0),
                "PF_L1": data.get("PF_L1", 0),
                "PF_L2": data.get("PF_L2", 0),
                "PF_L3": data.get("PF_L3", 0),
                "E_imp_kWh": data.get("E_imp_kWh", 0),
                "E_exp_kWh": data.get("E_exp_kWh", 0),
            }
            records.append(portal_record)
            row_ids.append(row["id"])

        payload = {
            "api_key": conf["device_key"],
            "device_id": conf["device_id"],
            "meter_id": meter_id,
            "records": records,
            "last_sync_id": row_ids[-1],
        }

        try:
            resp = requests.post(
                f"{conf['api_url']}/energy-monitoring/ingest",
                json=payload,
                timeout=60,
            )
            if resp.status_code == 200:
                mark_synced(conf["db_path"], row_ids)
                inserted = resp.json().get("inserted", 0)
                total_synced += inserted
                log.info(f"Sync OK: {inserted} Datensaetze fuer Zaehler {meter_id[:8]}...")
            else:
                log.warning(f"Sync Fehler {resp.status_code}: {resp.text[:200]}")
        except requests.ConnectionError:
            log.warning("Portal nicht erreichbar")
            break
        except Exception as e:
            log.error(f"Sync Fehler: {e}")

    return total_synced


# ====== Hauptprogramm ======

def main():
    conf, meters = load_config()

    log.info("=" * 60)
    log.info("  Kirmeskiste Sync - Eventenergie Portal")
    log.info("  4x EMU Professional II 3/5 via Modbus TCP")
    log.info("=" * 60)
    log.info(f"  Server:     {conf['api_url']}")
    log.info(f"  Device-ID:  {conf['device_id']}")
    log.info(f"  Schluessel: {conf['device_key'][:8]}..." if conf['device_key'] else "  Schluessel: NICHT GESETZT")
    log.info(f"  Datenbank:  {conf['db_path']}")
    log.info(f"  Leseintervall:  {conf['read_interval']}s")
    log.info(f"  Sync-Intervall: {conf['sync_interval']}s")
    log.info(f"  Zaehler:")
    for m in meters:
        log.info(f"    {m['name']}: {m['ip']}:{m['port']} (Slave {m['slave_id']}) -> {m['meter_id'][:8] if m['meter_id'] else 'NICHT KONFIGURIERT'}...")
    log.info("=" * 60)

    # Validierung
    errors = []
    if not conf["api_url"]:
        errors.append("api_url nicht gesetzt")
    if not conf["device_key"]:
        errors.append("device_key nicht gesetzt")
    if not conf["device_id"]:
        errors.append("device_id nicht gesetzt")
    active_meters = [m for m in meters if m["meter_id"]]
    if not active_meters:
        errors.append("Keine Zaehler mit meter_id konfiguriert")

    if errors:
        for e in errors:
            log.error(f"KONFIGURATIONSFEHLER: {e}")
        log.error("Bitte /etc/kirmeskiste.conf pruefen!")
        sys.exit(1)

    # DB initialisieren
    init_db(conf["db_path"])

    # Update-Check beim Start
    log.info("Pruefe auf Updates...")
    check_and_apply_update(conf)

    log.info(f"Starte Messung mit {len(active_meters)} Zaehlern...")

    last_sync_time = 0
    consecutive_errors = 0

    while True:
        try:
            # Alle Zaehler lesen
            for meter in active_meters:
                data = read_meter(meter["ip"], meter["port"], meter["slave_id"], meter["name"])
                if data.get("online"):
                    store_reading(conf["db_path"], meter["meter_id"], data)
                    consecutive_errors = 0

            # Periodisch zum Portal syncen
            now = time.time()
            if now - last_sync_time >= conf["sync_interval"]:
                synced = sync_to_portal(conf, meters)
                if synced > 0:
                    log.info(f"Gesamt synchronisiert: {synced} Datensaetze")
                last_sync_time = now

                # Alte Daten aufraeumen (einmal pro Sync-Zyklus)
                cleanup_old(conf["db_path"])

                # Update-Check bei jedem Sync-Zyklus (alle 20 Min)
                check_and_apply_update(conf)

        except KeyboardInterrupt:
            log.info("Beendet durch Benutzer")
            break
        except Exception as e:
            consecutive_errors += 1
            log.error(f"Hauptschleife Fehler: {e}")
            if consecutive_errors > 10:
                delay = min(conf["retry_delay"] * 2, 300)
                log.warning(f"Zu viele Fehler, warte {delay}s...")
                time.sleep(delay)

        time.sleep(conf["read_interval"])


if __name__ == "__main__":
    main()
