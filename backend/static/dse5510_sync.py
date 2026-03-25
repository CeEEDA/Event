#!/usr/bin/env python3
"""
DSE 5510 Sync - Eventenergie Portal
====================================
Liest einen DSE 5510 Generator-Controller via RS232 Modbus RTU
und synchronisiert die Telemetrie-Daten mit dem Eventenergie Portal.

Hardware:
  - Raspberry Pi
  - USB-RS232-Adapter (z.B. FTDI) -> DSE 5510 RS232 Port
  - USB GPS-Antenne (optional)

Voraussetzungen:
  sudo apt install python3-pip python3-venv gpsd gpsd-clients
  pip3 install pymodbus pyserial requests gpsd-py3

Konfiguration:
  Datei /etc/dse5510.conf (wird vom Setup-Skript erstellt)

Status pruefen:
  sudo systemctl status dse5510_sync
  sudo journalctl -u dse5510_sync -f
"""

import struct
import time
import json
import logging
import os
import sys
import sqlite3
import configparser
from pathlib import Path
from datetime import datetime, timezone

import requests
from pymodbus.client import ModbusSerialClient

# ====== DSE GenComm Modbus Register Map ======
# Adressberechnung: address = page * 256 + offset
# DSE Default: Slave ID 10, 9600 Baud, 8N1

# --- Page 4: Basic Instrumentation (Base: 1024) ---
PAGE4 = 4 * 256  # = 1024
REG_OIL_PRESSURE       = PAGE4 + 0    # kPa, 16bit, scale 1
REG_COOLANT_TEMP       = PAGE4 + 1    # Grad C, 16bit, scale 1
REG_OIL_TEMP           = PAGE4 + 2    # Grad C, 16bit, scale 1
REG_FUEL_LEVEL         = PAGE4 + 3    # %, 16bit, scale 1
REG_CHARGE_ALT_VOLT    = PAGE4 + 4    # V, 16bit, scale 0.1
REG_BATTERY_VOLTAGE    = PAGE4 + 5    # V, 16bit, scale 0.1
REG_ENGINE_SPEED       = PAGE4 + 6    # RPM, 16bit, scale 1
REG_GEN_FREQUENCY      = PAGE4 + 7    # Hz, 16bit, scale 0.1
REG_GEN_V_L1N          = PAGE4 + 8    # V, 32bit, scale 0.1
REG_GEN_V_L2N          = PAGE4 + 10   # V, 32bit, scale 0.1
REG_GEN_V_L3N          = PAGE4 + 12   # V, 32bit, scale 0.1
REG_GEN_V_L1L2         = PAGE4 + 14   # V, 32bit, scale 0.1
REG_GEN_V_L2L3         = PAGE4 + 16   # V, 32bit, scale 0.1
REG_GEN_V_L3L1         = PAGE4 + 18   # V, 32bit, scale 0.1
REG_GEN_I_L1           = PAGE4 + 20   # A, 32bit, scale 0.1
REG_GEN_I_L2           = PAGE4 + 22   # A, 32bit, scale 0.1
REG_GEN_I_L3           = PAGE4 + 24   # A, 32bit, scale 0.1
REG_GEN_EARTH_I        = PAGE4 + 26   # A, 32bit, scale 0.1
REG_GEN_W_L1           = PAGE4 + 28   # W, 32bit signed, scale 1
REG_GEN_W_L2           = PAGE4 + 30   # W, 32bit signed, scale 1
REG_GEN_W_L3           = PAGE4 + 32   # W, 32bit signed, scale 1

# --- Page 6: Derived Instrumentation (Base: 1536) ---
PAGE6 = 6 * 256  # = 1536
REG_GEN_TOTAL_W        = PAGE6 + 0    # W, 32bit signed, scale 1
REG_GEN_TOTAL_VA       = PAGE6 + 8    # VA, 32bit, scale 1
REG_GEN_TOTAL_VAR      = PAGE6 + 16   # Var, 32bit signed, scale 1
REG_GEN_PF_L1          = PAGE6 + 18   # PF, 16bit signed, scale 0.01
REG_GEN_PF_L2          = PAGE6 + 19   # PF, 16bit signed, scale 0.01
REG_GEN_PF_L3          = PAGE6 + 20   # PF, 16bit signed, scale 0.01
REG_GEN_PF_AVG         = PAGE6 + 21   # PF, 16bit signed, scale 0.01

# --- Page 7: Accumulated Instrumentation (Base: 1792) ---
PAGE7 = 7 * 256  # = 1792
REG_ENGINE_RUN_TIME    = PAGE7 + 6    # Sekunden, 32bit, scale 1
REG_GEN_POS_KWH        = PAGE7 + 8    # kWh, 32bit, scale 0.1
REG_GEN_NEG_KWH        = PAGE7 + 10   # kWh, 32bit, scale 0.1
REG_NUM_STARTS         = PAGE7 + 16   # Starts, 32bit, scale 1

# --- Page 3: Status Information (Base: 768) ---
PAGE3 = 3 * 256  # = 768

# --- Page 16: System Control (Base: 4096) ---
PAGE16 = 16 * 256  # = 4096
REG_CONTROL_KEY        = PAGE16 + 8   # Write only, 16bit
REG_CONTROL_COMPLEMENT = PAGE16 + 9   # Write only, 16bit

# DSE System Control Keys
DSE_COMMANDS = {
    "stop":                {"key": 35700, "complement": 29835, "label": "Stop-Modus"},
    "auto_on":             {"key": 35701, "complement": 29834, "label": "Automatikmodus"},
    "manual":              {"key": 35702, "complement": 29833, "label": "Manueller Modus"},
    "test_on_load":        {"key": 35703, "complement": 29832, "label": "Testlauf unter Last"},
    "auto_manual_restore": {"key": 35704, "complement": 29831, "label": "Auto mit manueller Rueckkehr"},
    "start":               {"key": 35705, "complement": 29830, "label": "Motor starten"},
    "reset":               {"key": 35707, "complement": 29828, "label": "Alarme zuruecksetzen"},
    "gen_switch_on":       {"key": 35708, "complement": 29827, "label": "Generator zuschalten"},
    "gen_switch_off":      {"key": 35709, "complement": 29826, "label": "Generator abschalten"},
    "reset_mains":         {"key": 35710, "complement": 29825, "label": "Netzausfall zuruecksetzen"},
}


# ====== Konfiguration ======

DEFAULT_CONF = {
    "api_url": "",
    "device_key": "",
    "device_id": "",
    "generator_id": "",
    "db_path": "/var/lib/dse5510/dse5510.sqlite",
    "serial_port": "/dev/ttyUSB0",
    "baud_rate": 9600,
    "slave_id": 10,
    "read_interval": 10,
    "sync_interval": 30,
    "retry_delay": 30,
    "batch_size": 200,
}


def load_config():
    conf = dict(DEFAULT_CONF)
    conf_path = Path("/etc/dse5510.conf")
    if conf_path.exists():
        cp = configparser.ConfigParser()
        cp.read(str(conf_path))
        if "dse5510" in cp:
            s = cp["dse5510"]
            for key in conf:
                if key in s:
                    if key in ("baud_rate", "slave_id", "read_interval", "sync_interval", "retry_delay", "batch_size"):
                        conf[key] = int(s[key])
                    else:
                        conf[key] = s[key]

    # Env overrides
    conf["api_url"] = os.environ.get("DSE_API_URL", conf["api_url"])
    conf["device_key"] = os.environ.get("DSE_DEVICE_KEY", conf["device_key"])
    conf["device_id"] = os.environ.get("DSE_DEVICE_ID", conf["device_id"])
    return conf


# ====== Logging ======

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("dse5510")


# ====== Modbus RTU Lesen ======

def _read_holding(client, register, count, slave_id):
    """Liest Holding Registers (FC 03) - kompatibel mit pymodbus 3.x."""
    import pymodbus
    version = tuple(int(x) for x in pymodbus.__version__.split(".")[:2])
    if version >= (3, 8):
        return client.read_holding_registers(register, count=count, device_id=slave_id)
    else:
        try:
            return client.read_holding_registers(register, count, slave=slave_id)
        except TypeError:
            return client.read_holding_registers(register, count, unit=slave_id)


def _write_registers(client, register, values, slave_id):
    """Schreibt mehrere Holding Registers (FC 16)."""
    import pymodbus
    version = tuple(int(x) for x in pymodbus.__version__.split(".")[:2])
    if version >= (3, 8):
        return client.write_registers(register, values=values, device_id=slave_id)
    else:
        try:
            return client.write_registers(register, values, slave=slave_id)
        except TypeError:
            return client.write_registers(register, values, unit=slave_id)


def read_uint16(client, register, slave_id):
    """Liest einen 16bit unsigned Integer."""
    try:
        result = _read_holding(client, register, 1, slave_id)
        if result.isError():
            return None
        val = result.registers[0]
        return val if val != 0xFFFF else None  # 0xFFFF = nicht implementiert
    except Exception:
        return None


def read_int16(client, register, slave_id):
    """Liest einen 16bit signed Integer."""
    try:
        result = _read_holding(client, register, 1, slave_id)
        if result.isError():
            return None
        val = result.registers[0]
        if val == 0xFFFF:
            return None
        return struct.unpack(">h", struct.pack(">H", val))[0]
    except Exception:
        return None


def read_uint32(client, register, slave_id):
    """Liest einen 32bit unsigned Integer (MSB zuerst)."""
    try:
        result = _read_holding(client, register, 2, slave_id)
        if result.isError():
            return None
        raw = struct.pack(">HH", result.registers[0], result.registers[1])
        val = struct.unpack(">I", raw)[0]
        return val if val != 0xFFFFFFFF else None
    except Exception:
        return None


def read_int32(client, register, slave_id):
    """Liest einen 32bit signed Integer (MSB zuerst)."""
    try:
        result = _read_holding(client, register, 2, slave_id)
        if result.isError():
            return None
        raw = struct.pack(">HH", result.registers[0], result.registers[1])
        return struct.unpack(">i", raw)[0]
    except Exception:
        return None


def read_dse5510(client, slave_id):
    """Liest alle relevanten Register vom DSE 5510."""
    data = {
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "online": False,
        "error": None,
        "source": "dse5510_pi",
    }

    try:
        # --- Page 4: Basic Instrumentation ---
        oil_press = read_uint16(client, REG_OIL_PRESSURE, slave_id)
        coolant_temp = read_uint16(client, REG_COOLANT_TEMP, slave_id)
        oil_temp = read_uint16(client, REG_OIL_TEMP, slave_id)
        fuel_level = read_uint16(client, REG_FUEL_LEVEL, slave_id)
        charge_alt_v = read_uint16(client, REG_CHARGE_ALT_VOLT, slave_id)
        battery_v = read_uint16(client, REG_BATTERY_VOLTAGE, slave_id)
        rpm = read_uint16(client, REG_ENGINE_SPEED, slave_id)
        frequency = read_uint16(client, REG_GEN_FREQUENCY, slave_id)

        # Spannungen (32bit, 0.1V)
        v_l1n = read_uint32(client, REG_GEN_V_L1N, slave_id)
        v_l2n = read_uint32(client, REG_GEN_V_L2N, slave_id)
        v_l3n = read_uint32(client, REG_GEN_V_L3N, slave_id)
        v_l1l2 = read_uint32(client, REG_GEN_V_L1L2, slave_id)
        v_l2l3 = read_uint32(client, REG_GEN_V_L2L3, slave_id)
        v_l3l1 = read_uint32(client, REG_GEN_V_L3L1, slave_id)

        # Stroeme (32bit, 0.1A)
        i_l1 = read_uint32(client, REG_GEN_I_L1, slave_id)
        i_l2 = read_uint32(client, REG_GEN_I_L2, slave_id)
        i_l3 = read_uint32(client, REG_GEN_I_L3, slave_id)

        # Leistung pro Phase (32bit signed, W)
        w_l1 = read_int32(client, REG_GEN_W_L1, slave_id)
        w_l2 = read_int32(client, REG_GEN_W_L2, slave_id)
        w_l3 = read_int32(client, REG_GEN_W_L3, slave_id)

        # --- Page 6: Derived Instrumentation ---
        total_w = read_int32(client, REG_GEN_TOTAL_W, slave_id)
        total_va = read_uint32(client, REG_GEN_TOTAL_VA, slave_id)
        total_var = read_int32(client, REG_GEN_TOTAL_VAR, slave_id)
        pf_l1 = read_int16(client, REG_GEN_PF_L1, slave_id)
        pf_l2 = read_int16(client, REG_GEN_PF_L2, slave_id)
        pf_l3 = read_int16(client, REG_GEN_PF_L3, slave_id)
        pf_avg = read_int16(client, REG_GEN_PF_AVG, slave_id)

        # --- Page 7: Accumulated Instrumentation ---
        run_time_s = read_uint32(client, REG_ENGINE_RUN_TIME, slave_id)
        pos_kwh = read_uint32(client, REG_GEN_POS_KWH, slave_id)
        num_starts = read_uint32(client, REG_NUM_STARTS, slave_id)

        # Skalierung anwenden
        data["oil_pressure_kpa"] = oil_press if oil_press is not None else 0
        data["coolant_temp_c"] = coolant_temp if coolant_temp is not None else 0
        data["oil_temp_c"] = oil_temp if oil_temp is not None else 0
        data["fuel_level_pct"] = fuel_level if fuel_level is not None else 0
        data["charge_alt_voltage"] = round(charge_alt_v * 0.1, 1) if charge_alt_v is not None else 0
        data["battery_voltage"] = round(battery_v * 0.1, 1) if battery_v is not None else 0
        data["rpm"] = rpm if rpm is not None else 0
        data["frequency"] = round(frequency * 0.1, 1) if frequency is not None else 0

        data["voltage_l1"] = round(v_l1n * 0.1, 1) if v_l1n is not None else 0
        data["voltage_l2"] = round(v_l2n * 0.1, 1) if v_l2n is not None else 0
        data["voltage_l3"] = round(v_l3n * 0.1, 1) if v_l3n is not None else 0
        data["voltage_l1_l2"] = round(v_l1l2 * 0.1, 1) if v_l1l2 is not None else 0
        data["voltage_l2_l3"] = round(v_l2l3 * 0.1, 1) if v_l2l3 is not None else 0
        data["voltage_l3_l1"] = round(v_l3l1 * 0.1, 1) if v_l3l1 is not None else 0

        data["current_l1"] = round(i_l1 * 0.1, 1) if i_l1 is not None else 0
        data["current_l2"] = round(i_l2 * 0.1, 1) if i_l2 is not None else 0
        data["current_l3"] = round(i_l3 * 0.1, 1) if i_l3 is not None else 0

        data["power_l1_w"] = w_l1 if w_l1 is not None else 0
        data["power_l2_w"] = w_l2 if w_l2 is not None else 0
        data["power_l3_w"] = w_l3 if w_l3 is not None else 0
        data["power_total_w"] = total_w if total_w is not None else 0
        data["power_total_va"] = total_va if total_va is not None else 0
        data["power_total_var"] = total_var if total_var is not None else 0

        data["power_factor_l1"] = round(pf_l1 * 0.01, 2) if pf_l1 is not None else 0
        data["power_factor_l2"] = round(pf_l2 * 0.01, 2) if pf_l2 is not None else 0
        data["power_factor_l3"] = round(pf_l3 * 0.01, 2) if pf_l3 is not None else 0
        data["power_factor_avg"] = round(pf_avg * 0.01, 2) if pf_avg is not None else 0

        data["engine_run_time_s"] = run_time_s if run_time_s is not None else 0
        data["engine_run_hours"] = round(run_time_s / 3600.0, 1) if run_time_s is not None else 0
        data["energy_kwh"] = round(pos_kwh * 0.1, 1) if pos_kwh is not None else 0
        data["num_starts"] = num_starts if num_starts is not None else 0

        # Motor-Laufstatus ableiten
        data["engine_running"] = (rpm is not None and rpm > 100)

        data["online"] = True

        log.info(
            f"DSE5510: RPM={data['rpm']} "
            f"V={data['voltage_l1']:.0f}/{data['voltage_l2']:.0f}/{data['voltage_l3']:.0f}V "
            f"I={data['current_l1']:.1f}/{data['current_l2']:.1f}/{data['current_l3']:.1f}A "
            f"P={data['power_total_w']}W F={data['frequency']:.1f}Hz "
            f"Batt={data['battery_voltage']:.1f}V Oil={data['oil_pressure_kpa']}kPa "
            f"Cool={data['coolant_temp_c']}C Fuel={data['fuel_level_pct']}%"
        )

    except Exception as e:
        data["error"] = str(e)
        log.error(f"Lesefehler: {e}")

    return data


# ====== GPS ======

def read_gps():
    """Liest GPS-Position via gpsd."""
    try:
        import gpsd
        gpsd.connect()
        packet = gpsd.get_current()
        if packet.mode >= 2:
            return {
                "latitude": round(packet.lat, 6),
                "longitude": round(packet.lon, 6),
            }
    except Exception as e:
        log.debug(f"GPS nicht verfuegbar: {e}")
    return None


# ====== Steuerbefehle ======

def execute_command(client, slave_id, command_name):
    """Fuehrt einen DSE-Steuerbefehl via Modbus RTU aus."""
    cmd = DSE_COMMANDS.get(command_name)
    if not cmd:
        log.warning(f"Unbekannter Befehl: {command_name}")
        return False

    try:
        log.info(f"Fuehre Befehl aus: {cmd['label']} (Key={cmd['key']})")
        result = _write_registers(client, REG_CONTROL_KEY, [cmd["key"], cmd["complement"]], slave_id)
        if result.isError():
            log.error(f"Befehl fehlgeschlagen: {result}")
            return False
        log.info(f"Befehl erfolgreich: {cmd['label']}")
        return True
    except Exception as e:
        log.error(f"Fehler beim Ausfuehren von {command_name}: {e}")
        return False


# ====== Lokale SQLite Datenbank ======

def init_db(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            data_json TEXT NOT NULL,
            synced INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_synced ON telemetry(synced)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS command_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command_id TEXT NOT NULL,
            command TEXT NOT NULL,
            success INTEGER DEFAULT 0,
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            synced INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    log.info(f"Datenbank initialisiert: {db_path}")


def store_telemetry(db_path, data):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO telemetry (ts_utc, data_json) VALUES (?, ?)",
        (data["ts_utc"], json.dumps(data))
    )
    conn.commit()
    conn.close()


def get_unsynced(db_path, limit=200):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, ts_utc, data_json FROM telemetry WHERE synced=0 ORDER BY id ASC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_synced(db_path, ids):
    if not ids:
        return
    conn = sqlite3.connect(db_path)
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"UPDATE telemetry SET synced=1 WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.close()


def store_command_result(db_path, command_id, command, success, message=""):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO command_results (command_id, command, success, message) VALUES (?, ?, ?, ?)",
        (command_id, command, 1 if success else 0, message)
    )
    conn.commit()
    conn.close()


def get_unsynced_command_results(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, command_id, command, success, message FROM command_results WHERE synced=0"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_commands_synced(db_path, ids):
    if not ids:
        return
    conn = sqlite3.connect(db_path)
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"UPDATE command_results SET synced=1 WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.close()


def cleanup_old(db_path, keep_days=7):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "DELETE FROM telemetry WHERE synced=1 AND created_at < datetime('now', ?)",
        (f"-{keep_days} days",)
    )
    conn.execute(
        "DELETE FROM command_results WHERE synced=1 AND created_at < datetime('now', ?)",
        (f"-{keep_days} days",)
    )
    conn.commit()
    conn.close()


# ====== Portal Sync ======

def sync_to_portal(conf, gps_data, modbus_client):
    """Sendet Telemetrie-Daten an das Portal und empfaengt Steuerbefehle."""
    unsynced = get_unsynced(conf["db_path"], conf["batch_size"])
    if not unsynced:
        return 0

    records = []
    row_ids = []
    for row in unsynced:
        data = json.loads(row["data_json"])
        records.append(data)
        row_ids.append(row["id"])

    # Nicht synchronisierte Befehlsergebnisse sammeln
    cmd_results = get_unsynced_command_results(conf["db_path"])

    payload = {
        "api_key": conf["device_key"],
        "device_id": conf["device_id"],
        "generator_id": conf.get("generator_id", ""),
        "records": records,
        "command_results": [
            {"command_id": r["command_id"], "command": r["command"], "success": bool(r["success"]), "message": r["message"]}
            for r in cmd_results
        ],
    }

    if gps_data:
        payload["latitude"] = gps_data["latitude"]
        payload["longitude"] = gps_data["longitude"]

    try:
        resp = requests.post(
            f"{conf['api_url']}/generators/ingest",
            json=payload,
            timeout=60,
        )
        if resp.status_code == 200:
            mark_synced(conf["db_path"], row_ids)
            if cmd_results:
                mark_commands_synced(conf["db_path"], [r["id"] for r in cmd_results])

            result = resp.json()
            inserted = result.get("inserted", 0)
            log.info(f"Sync OK: {inserted} Datensaetze gesendet")

            # Generator-ID merken (vom Portal zugewiesen)
            if result.get("generator_id") and not conf.get("generator_id"):
                conf["generator_id"] = result["generator_id"]
                _save_generator_id(conf["generator_id"])

            # Steuerbefehle verarbeiten
            pending_cmds = result.get("pending_commands", [])
            for cmd in pending_cmds:
                cmd_name = cmd.get("command", "")
                cmd_id = cmd.get("id", "")
                log.info(f"Steuerbefehl empfangen: {cmd_name} (ID: {cmd_id})")
                if modbus_client and modbus_client.connected:
                    success = execute_command(modbus_client, int(conf["slave_id"]), cmd_name)
                    store_command_result(conf["db_path"], cmd_id, cmd_name, success,
                                        "OK" if success else "Modbus-Schreibfehler")
                else:
                    store_command_result(conf["db_path"], cmd_id, cmd_name, False,
                                        "Modbus nicht verbunden")

            return inserted
        else:
            log.warning(f"Sync Fehler {resp.status_code}: {resp.text[:200]}")
    except requests.ConnectionError:
        log.warning("Portal nicht erreichbar")
    except Exception as e:
        log.error(f"Sync Fehler: {e}")

    return 0


def _save_generator_id(gen_id):
    """Speichert die vom Portal zugewiesene Generator-ID in der Konfiguration."""
    try:
        conf_path = "/etc/dse5510.conf"
        cp = configparser.ConfigParser()
        cp.read(conf_path)
        if "dse5510" not in cp:
            cp["dse5510"] = {}
        cp["dse5510"]["generator_id"] = gen_id
        with open(conf_path, "w") as f:
            cp.write(f)
        log.info(f"Generator-ID gespeichert: {gen_id}")
    except Exception as e:
        log.warning(f"Konnte Generator-ID nicht speichern: {e}")


# ====== Hauptprogramm ======

def main():
    conf = load_config()

    log.info("=" * 60)
    log.info("  DSE 5510 Sync - Eventenergie Portal")
    log.info("  RS232 Modbus RTU + GPS")
    log.info("=" * 60)
    log.info(f"  Server:        {conf['api_url']}")
    log.info(f"  Device-ID:     {conf['device_id']}")
    log.info(f"  Generator-ID:  {conf.get('generator_id', 'wird automatisch zugewiesen')}")
    log.info(f"  Serial Port:   {conf['serial_port']}")
    log.info(f"  Baud Rate:     {conf['baud_rate']}")
    log.info(f"  Slave ID:      {conf['slave_id']}")
    log.info(f"  Datenbank:     {conf['db_path']}")
    log.info(f"  Leseintervall: {conf['read_interval']}s")
    log.info(f"  Sync-Intervall:{conf['sync_interval']}s")
    log.info("=" * 60)

    # Validierung
    errors = []
    if not conf["api_url"]:
        errors.append("api_url nicht gesetzt")
    if not conf["device_key"]:
        errors.append("device_key nicht gesetzt")
    if not conf["device_id"]:
        errors.append("device_id nicht gesetzt")
    if errors:
        for e in errors:
            log.error(f"KONFIGURATIONSFEHLER: {e}")
        log.error("Bitte /etc/dse5510.conf pruefen!")
        sys.exit(1)

    # DB initialisieren
    init_db(conf["db_path"])

    # Modbus RTU Client
    client = ModbusSerialClient(
        port=conf["serial_port"],
        baudrate=int(conf["baud_rate"]),
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=3,
    )

    last_sync_time = 0
    last_gps = None
    consecutive_errors = 0

    log.info("Starte Messung...")

    while True:
        try:
            # Modbus verbinden
            if not client.connected:
                if not client.connect():
                    log.warning(f"Modbus-Verbindung zu {conf['serial_port']} fehlgeschlagen")
                    consecutive_errors += 1
                    time.sleep(conf["retry_delay"])
                    continue
                log.info(f"Modbus verbunden: {conf['serial_port']}")

            # DSE 5510 auslesen
            data = read_dse5510(client, int(conf["slave_id"]))
            if data.get("online"):
                store_telemetry(conf["db_path"], data)
                consecutive_errors = 0
            else:
                consecutive_errors += 1

            # GPS lesen (einmal pro Minute reicht)
            gps = read_gps()
            if gps:
                last_gps = gps

            # Periodisch zum Portal syncen
            now = time.time()
            if now - last_sync_time >= int(conf["sync_interval"]):
                synced = sync_to_portal(conf, last_gps, client)
                last_sync_time = now
                cleanup_old(conf["db_path"])

        except KeyboardInterrupt:
            log.info("Beendet durch Benutzer")
            break
        except Exception as e:
            consecutive_errors += 1
            log.error(f"Hauptschleife Fehler: {e}")
            if consecutive_errors > 10:
                delay = min(int(conf["retry_delay"]) * 2, 300)
                log.warning(f"Zu viele Fehler, warte {delay}s...")
                time.sleep(delay)

        time.sleep(int(conf["read_interval"]))

    client.close()
    log.info("Verbindung geschlossen.")


if __name__ == "__main__":
    main()
