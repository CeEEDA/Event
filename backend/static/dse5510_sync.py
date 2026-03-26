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
import serial

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

# --- Page 1: Identification & Mode (Base: 256) ---
PAGE1 = 1 * 256  # = 256
REG_INSTRUMENT_MODE    = PAGE1 + 14   # Betriebsmodus, 16bit
# Werte: 0=Stop, 1=Auto, 2=Manual, 3=Test on Load, 4=Auto w/ Manual Restore, 5=User Config, 6=Off

# DSE Mode Mapping
DSE_MODE_MAP = {
    0: "stop",
    1: "auto",
    2: "manual",
    3: "test_on_load",
    4: "auto_manual_restore",
    5: "user_config",
    6: "off",
}

# --- Page 3 Status Flags ---
REG_GEN_AVAILABLE      = PAGE3 + 14   # Generator verfuegbar Flag, 16bit
REG_GEN_BREAKER_CLOSED = PAGE3 + 15   # Hauptschalter geschlossen Flag, 16bit

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
    "mute":                {"key": 35706, "complement": 29829, "label": "Alarm stumm"},
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
    "baud_rate": 19200,
    "parity": "N",
    "slave_id": 10,
    "read_interval": 1,
    "sync_interval": 30,
    "retry_delay": 30,
    "batch_size": 500,
    "max_disk_gb": 60,
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
                    if key in ("baud_rate", "slave_id", "read_interval", "sync_interval", "retry_delay", "batch_size", "max_disk_gb"):
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


# ====== Raw Modbus RTU (ohne pymodbus - P810 kompatibel) ======

GENCOMM_NA_VALUES = {0xFFFF, 0xFFFE, 0xFFFD, 0xFFFB}
GENCOMM_NA_SIGNED = {0x7FFB, 0x7FFC, 0x7FFD, 0x7FFE, 0x7FFF}


def _calc_crc(data):
    """Modbus RTU CRC16."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack("<H", crc)


def _raw_read(ser, slave, register, count, timeout_s=0.25):
    """Liest Modbus Holding Register via rohem Serial (FC03)."""
    frame = struct.pack(">BBHH", slave, 0x03, register, count)
    frame += _calc_crc(frame)

    ser.reset_input_buffer()
    ser.write(frame)
    time.sleep(timeout_s)

    expected = 3 + count * 2 + 2
    response = ser.read(expected + 10)

    if len(response) < 5:
        return None
    if response[0] != slave:
        return None
    if response[1] & 0x80:
        return None
    if response[1] != 0x03:
        return None

    byte_count = response[2]
    if byte_count != count * 2:
        return None

    data_len = 3 + byte_count
    if len(response) < data_len + 2:
        return None

    payload = response[:data_len]
    crc_recv = response[data_len:data_len + 2]
    if crc_recv != _calc_crc(payload):
        return None

    regs = []
    for i in range(count):
        val = struct.unpack(">H", response[3 + i * 2: 5 + i * 2])[0]
        regs.append(val)
    return regs


def _raw_write(ser, slave, register, values, timeout_s=1.0):
    """Schreibt Modbus Holding Register via rohem Serial (FC16).
    DSE GenComm antwortet mit FC03 Read-Back statt Standard FC16 Response."""
    count = len(values)
    byte_count = count * 2
    frame = struct.pack(">BBHHB", slave, 0x10, register, count, byte_count)
    for v in values:
        frame += struct.pack(">H", v)
    frame += _calc_crc(frame)

    ser.reset_input_buffer()
    ser.write(frame)
    time.sleep(timeout_s)

    response = ser.read(ser.in_waiting or 20)

    if len(response) == 0:
        log.warning(f"Write FC16: Keine Antwort (0 bytes) fuer Register {register}")
        return False

    # DSE GenComm Quirk: Antwortet mit FC03 (Read-Back) statt FC10 (Write-Confirm)
    # Jede nicht-leere Antwort mit korrekter Slave-ID und ohne Exception = Erfolg
    if response[0] == slave and not (response[1] & 0x80):
        return True

    if response[1] & 0x80:
        log.warning(f"Write FC16: Modbus Exception 0x{response[2]:02X} fuer Register {register}")
        return False

    # Slave-ID stimmt nicht - evtl. verzoegerte Antwort einer vorherigen Abfrage
    log.warning(f"Write FC16: Unerwartete Antwort Slave={response[0]} Func=0x{response[1]:02X}")
    return False


def _raw_write_single(ser, slave, register, value, timeout_s=1.0):
    """Schreibt ein einzelnes Modbus Holding Register via FC06."""
    frame = struct.pack(">BBH", slave, 0x06, register)
    frame += struct.pack(">H", value)
    frame += _calc_crc(frame)

    log.info(f"  TX FC06: {frame.hex()}")

    ser.reset_input_buffer()
    ser.write(frame)

    time.sleep(timeout_s)
    response = ser.read(ser.in_waiting or 20)

    if len(response) > 0:
        log.info(f"  RX: {response.hex()} ({len(response)} bytes)")
    else:
        log.warning(f"  RX: LEER (0 bytes) - DSE antwortet nicht auf FC06 @{register}")
        return False

    if len(response) < 6:
        return False
    if response[0] != slave:
        return False
    if response[1] & 0x80:
        log.warning(f"  Modbus Exception: 0x{response[2]:02X}")
        return False
    if response[1] != 0x06:
        return False
    return True


def read_uint16(ser, register, slave_id):
    """Liest einen 16bit unsigned Integer."""
    regs = _raw_read(ser, slave_id, register, 1)
    if regs is None:
        return None
    val = regs[0]
    if val in GENCOMM_NA_VALUES or val in GENCOMM_NA_SIGNED:
        return None
    return val


def read_int16(ser, register, slave_id):
    """Liest einen 16bit signed Integer."""
    regs = _raw_read(ser, slave_id, register, 1)
    if regs is None:
        return None
    val = regs[0]
    if val in GENCOMM_NA_VALUES or val in GENCOMM_NA_SIGNED:
        return None
    return struct.unpack(">h", struct.pack(">H", val))[0]


def read_uint32(ser, register, slave_id):
    """Liest einen 32bit unsigned Integer (MSB zuerst)."""
    regs = _raw_read(ser, slave_id, register, 2)
    if regs is None:
        return None
    raw = struct.pack(">HH", regs[0], regs[1])
    val = struct.unpack(">I", raw)[0]
    if val >= 0xFFFFFFFE:
        return None
    return val


def read_int32(ser, register, slave_id):
    """Liest einen 32bit signed Integer (MSB zuerst)."""
    regs = _raw_read(ser, slave_id, register, 2)
    if regs is None:
        return None
    raw = struct.pack(">HH", regs[0], regs[1])
    return struct.unpack(">i", raw)[0]


def read_dse5510(ser, slave_id):
    """Liest alle relevanten Register vom DSE 5510."""
    data = {
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "online": False,
        "error": None,
        "source": "dse5510_pi",
    }

    try:
        # --- Page 4: Basic Instrumentation ---
        oil_press = read_uint16(ser, REG_OIL_PRESSURE, slave_id)
        coolant_temp = read_uint16(ser, REG_COOLANT_TEMP, slave_id)
        oil_temp = read_uint16(ser, REG_OIL_TEMP, slave_id)
        fuel_level = read_uint16(ser, REG_FUEL_LEVEL, slave_id)
        charge_alt_v = read_uint16(ser, REG_CHARGE_ALT_VOLT, slave_id)
        battery_v = read_uint16(ser, REG_BATTERY_VOLTAGE, slave_id)
        rpm = read_uint16(ser, REG_ENGINE_SPEED, slave_id)
        frequency = read_uint16(ser, REG_GEN_FREQUENCY, slave_id)

        # Spannungen (32bit, 0.1V)
        v_l1n = read_uint32(ser, REG_GEN_V_L1N, slave_id)
        v_l2n = read_uint32(ser, REG_GEN_V_L2N, slave_id)
        v_l3n = read_uint32(ser, REG_GEN_V_L3N, slave_id)
        v_l1l2 = read_uint32(ser, REG_GEN_V_L1L2, slave_id)
        v_l2l3 = read_uint32(ser, REG_GEN_V_L2L3, slave_id)
        v_l3l1 = read_uint32(ser, REG_GEN_V_L3L1, slave_id)

        # Stroeme (32bit, 0.1A)
        i_l1 = read_uint32(ser, REG_GEN_I_L1, slave_id)
        i_l2 = read_uint32(ser, REG_GEN_I_L2, slave_id)
        i_l3 = read_uint32(ser, REG_GEN_I_L3, slave_id)

        # Leistung pro Phase (32bit signed, W)
        w_l1 = read_int32(ser, REG_GEN_W_L1, slave_id)
        w_l2 = read_int32(ser, REG_GEN_W_L2, slave_id)
        w_l3 = read_int32(ser, REG_GEN_W_L3, slave_id)

        # --- Page 6: Derived Instrumentation ---
        total_w = read_int32(ser, REG_GEN_TOTAL_W, slave_id)
        total_va = read_uint32(ser, REG_GEN_TOTAL_VA, slave_id)
        total_var = read_int32(ser, REG_GEN_TOTAL_VAR, slave_id)
        pf_l1 = read_int16(ser, REG_GEN_PF_L1, slave_id)
        pf_l2 = read_int16(ser, REG_GEN_PF_L2, slave_id)
        pf_l3 = read_int16(ser, REG_GEN_PF_L3, slave_id)
        pf_avg = read_int16(ser, REG_GEN_PF_AVG, slave_id)

        # --- Page 7: Accumulated Instrumentation ---
        run_time_s = read_uint32(ser, REG_ENGINE_RUN_TIME, slave_id)
        pos_kwh = read_uint32(ser, REG_GEN_POS_KWH, slave_id)
        num_starts = read_uint32(ser, REG_NUM_STARTS, slave_id)

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

        # DSE Betriebsmodus - aus vorhandenen Daten ableiten
        # (Page 1/3 Register-Reads nicht unterstuetzt beim DSE 5510 via P810)
        data["dse_mode_raw"] = None
        data["dse_mode"] = "unknown"

        # Generator-Status aus Messwerten ableiten
        has_voltage = (data["voltage_l1"] > 50 or data["voltage_l2"] > 50 or data["voltage_l3"] > 50)
        has_frequency = data["frequency"] > 40
        data["generator_available"] = has_voltage and has_frequency
        data["breaker_closed"] = data["generator_available"] and data["power_total_w"] > 100

        data["online"] = True

        log.info(
            f"DSE5510: "
            f"RPM={'n/a' if rpm is None else rpm} "
            f"V={data['voltage_l1']:.0f}/{data['voltage_l2']:.0f}/{data['voltage_l3']:.0f}V "
            f"I={data['current_l1']:.1f}/{data['current_l2']:.1f}/{data['current_l3']:.1f}A "
            f"P={data['power_total_w']}W F={data['frequency']:.1f}Hz "
            f"Batt={data['battery_voltage']:.1f}V "
            f"Oil={'n/a' if oil_press is None else str(oil_press) + 'kPa'} "
            f"Cool={'n/a' if coolant_temp is None else str(coolant_temp) + 'C'} "
            f"Fuel={data['fuel_level_pct']}%"
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


def poll_commands(conf, ser):
    """Schnelle Befehlsabfrage (alle 5 Sek.) - leichtgewichtig, ohne Telemetriedaten."""
    try:
        resp = requests.get(
            f"{conf['api_url']}/generators/poll-commands/{conf['device_id']}",
            params={"key": conf["device_key"]},
            timeout=10,
        )
        if resp.status_code == 200:
            result = resp.json()
            cmds = result.get("pending_commands", [])
            for cmd in cmds:
                cmd_name = cmd.get("command", "")
                cmd_id = cmd.get("id", "")
                log.info(f"[POLL] Steuerbefehl: {cmd_name} (ID: {cmd_id})")
                if ser and ser.is_open:
                    success = execute_command(ser, int(conf["slave_id"]), cmd_name)
                    store_command_result(conf["db_path"], cmd_id, cmd_name, success,
                                        "OK" if success else "Modbus-Schreibfehler")
                else:
                    store_command_result(conf["db_path"], cmd_id, cmd_name, False,
                                        "Modbus nicht verbunden")
            return len(cmds)
    except requests.ConnectionError:
        pass
    except Exception as e:
        log.debug(f"Command-Poll Fehler: {e}")
    return 0


# ====== Steuerbefehle ======

def execute_command(ser, slave_id, command_name):
    """Fuehrt den Write-Befehl in einem SEPARATEN Prozess aus.
    Genau wie beim Diagnose-Skript: eigener File-Descriptor auf den Serial-Port.
    Der Hauptprozess liest weiter - der Subprocess schreibt parallel."""
    cmd = DSE_COMMANDS.get(command_name)
    if not cmd:
        log.warning(f"Unbekannter Befehl: {command_name}")
        return False

    key = cmd["key"]
    complement = cmd["complement"]
    port_name = ser.port
    baudrate = ser.baudrate

    # Python-Einzeiler der den Write in einem eigenen Prozess ausfuehrt
    py_cmd = f"""
import serial, struct, time, sys
def crc(d):
    c=0xFFFF
    for b in d:
        c^=b
        for _ in range(8):
            c=(c>>1)^0xA001 if c&1 else c>>1
    return struct.pack("<H",c)
ser=serial.Serial("{port_name}",{baudrate},bytesize=8,parity="N",stopbits=1,timeout=2)
time.sleep(0.3)
f=struct.pack(">BBHHB",{slave_id},0x10,{REG_CONTROL_KEY},2,4)
f+=struct.pack(">HH",{key},{complement})
f+=crc(f)
ser.write(f)
time.sleep(1.5)
r=ser.read(ser.in_waiting or 50)
ser.close()
print(f"OK:{{len(r)}}:{{r.hex() if r else 'leer'}}")
"""
    try:
        import subprocess
        log.info(f"Sende Befehl (Subprocess): {cmd['label']} (Key={key})")
        result = subprocess.run(
            [sys.executable, "-c", py_cmd],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout.strip()
        log.info(f"Subprocess Ergebnis: {output}")
        if output.startswith("OK:"):
            return True
        if result.stderr:
            log.warning(f"Subprocess Fehler: {result.stderr.strip()[:200]}")
        return False
    except Exception as e:
        log.error(f"Fehler: {command_name}: {e}")
        return False


# ====== Lokale SQLite Datenbank ======

def init_db(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    # WAL-Modus fuer bessere Performance bei haeufigen Schreibzugriffen
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON telemetry(ts_utc)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alarms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            alarm_type TEXT NOT NULL,
            alarm_code INTEGER,
            description TEXT,
            active INTEGER DEFAULT 1,
            cleared_at TEXT,
            synced INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alarm_synced ON alarms(synced)")
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


def store_alarm(db_path, alarm_type, alarm_code, description):
    """Speichert eine Stoerung mit Zeitstempel."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO alarms (ts_utc, alarm_type, alarm_code, description) VALUES (?, ?, ?, ?)",
        (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), alarm_type, alarm_code, description)
    )
    conn.commit()
    conn.close()
    log.warning(f"STOERUNG: [{alarm_type}] Code={alarm_code} - {description}")


def clear_alarm(db_path, alarm_type):
    """Markiert eine Stoerung als behoben."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE alarms SET active=0, cleared_at=? WHERE alarm_type=? AND active=1",
        (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), alarm_type)
    )
    conn.commit()
    conn.close()


def get_unsynced_alarms(db_path, limit=100):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, ts_utc, alarm_type, alarm_code, description, active, cleared_at FROM alarms WHERE synced=0 ORDER BY id ASC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_alarms_synced(db_path, ids):
    if not ids:
        return
    conn = sqlite3.connect(db_path)
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"UPDATE alarms SET synced=1 WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.close()


def check_disk_space(db_path, max_gb):
    """Prueft die DB-Groesse und loescht aelteste Daten wenn > max_gb."""
    try:
        db_file = Path(db_path)
        if not db_file.exists():
            return
        size_gb = db_file.stat().st_size / (1024**3)
        if size_gb < max_gb:
            return

        log.warning(f"Datenbank {size_gb:.1f} GB > Limit {max_gb} GB. Raeume auf...")
        conn = sqlite3.connect(db_path)
        # Loesche aelteste synchronisierte Daten (30 Tage alt)
        conn.execute("DELETE FROM telemetry WHERE synced=1 AND created_at < datetime('now', '-30 days')")
        conn.execute("DELETE FROM alarms WHERE synced=1 AND created_at < datetime('now', '-90 days')")
        deleted = conn.total_changes
        conn.execute("VACUUM")
        conn.commit()
        conn.close()
        new_size = db_file.stat().st_size / (1024**3)
        log.info(f"Aufraumen: {deleted} Eintraege geloescht. Neu: {new_size:.1f} GB")

        # Falls immer noch zu gross, loesche auch unsynchronisierte alte Daten
        if new_size >= max_gb:
            conn = sqlite3.connect(db_path)
            conn.execute("DELETE FROM telemetry WHERE created_at < datetime('now', '-7 days')")
            conn.execute("VACUUM")
            conn.commit()
            conn.close()
            log.warning("Notfall-Aufraumen: Daten aelter als 7 Tage geloescht.")
    except Exception as e:
        log.error(f"Fehler beim Disk-Check: {e}")


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


def cleanup_old(db_path, max_gb=60):
    """Loescht synchronisierte Daten und prueft Disk-Limit."""
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM telemetry WHERE synced=1 AND created_at < datetime('now', '-7 days')")
    conn.execute("DELETE FROM command_results WHERE synced=1 AND created_at < datetime('now', '-7 days')")
    conn.execute("DELETE FROM alarms WHERE synced=1 AND created_at < datetime('now', '-30 days')")
    conn.commit()
    conn.close()
    check_disk_space(db_path, max_gb)


# ====== Portal Sync ======

def sync_to_portal(conf, gps_data, ser):
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

    # Nicht synchronisierte Stoerungen sammeln
    alarm_records = get_unsynced_alarms(conf["db_path"])

    payload = {
        "api_key": conf["device_key"],
        "device_id": conf["device_id"],
        "generator_id": conf.get("generator_id", ""),
        "records": records,
        "command_results": [
            {"command_id": r["command_id"], "command": r["command"], "success": bool(r["success"]), "message": r["message"]}
            for r in cmd_results
        ],
        "alarms": [
            {"ts_utc": a["ts_utc"], "alarm_type": a["alarm_type"], "alarm_code": a["alarm_code"],
             "description": a["description"], "active": bool(a["active"]), "cleared_at": a["cleared_at"]}
            for a in alarm_records
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
            if alarm_records:
                mark_alarms_synced(conf["db_path"], [a["id"] for a in alarm_records])

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
                if ser and ser.is_open:
                    success = execute_command(ser, int(conf["slave_id"]), cmd_name)
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
    log.info(f"  Paritaet:      {conf.get('parity', 'N')}")
    log.info(f"  Slave ID:      {conf['slave_id']}")
    log.info(f"  Datenbank:     {conf['db_path']}")
    log.info(f"  Leseintervall: {conf['read_interval']}s (1x/Sek.)")
    log.info(f"  Sync-Intervall:{conf['sync_interval']}s")
    log.info(f"  Max Disk:      {conf['max_disk_gb']} GB")
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

    # Serielle Verbindung (Raw Serial - P810 kompatibel)
    parity_map = {"N": "N", "E": "E", "O": "O"}
    parity = parity_map.get(conf.get("parity", "N"), "N")

    ser = None
    last_sync_time = 0
    last_cmd_poll_time = 0
    last_gps = None
    last_gps_time = 0
    last_disk_check = 0
    consecutive_errors = 0
    portal_connected = False
    prev_alarm_state = {}

    log.info("Starte 1-Sekunden-Messung...")

    while True:
        try:
            # Serielle Verbindung oeffnen
            if ser is None or not ser.is_open:
                try:
                    ser = serial.Serial(
                        port=conf["serial_port"],
                        baudrate=int(conf["baud_rate"]),
                        bytesize=8,
                        parity=parity,
                        stopbits=1,
                        timeout=1,
                    )
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    time.sleep(0.5)
                    log.info(f"Seriell verbunden: {conf['serial_port']} @ {conf['baud_rate']} Baud")
                    clear_alarm(conf["db_path"], "modbus_disconnect")
                except Exception as e:
                    log.warning(f"Serielle Verbindung zu {conf['serial_port']} fehlgeschlagen: {e}")
                    store_alarm(conf["db_path"], "modbus_disconnect", 0,
                                f"Serielle Verbindung fehlgeschlagen: {e}")
                    consecutive_errors += 1
                    time.sleep(int(conf["retry_delay"]))
                    continue

            # DSE 5510 auslesen (jede Sekunde)
            data = read_dse5510(ser, int(conf["slave_id"]))
            if data.get("online"):
                store_telemetry(conf["db_path"], data)
                consecutive_errors = 0

                # Stoerungserkennung
                # Plausibilitaetsgrenzen: Werte ausserhalb physikalisch moeglicher
                # Bereiche sind Sentinel-Reste und werden ignoriert
                coolant = data.get("coolant_temp_c", 0)
                oil_kpa = data.get("oil_pressure_kpa", 0)
                batt_v = data.get("battery_voltage", 0)
                engine_rpm = data.get("rpm", 0)

                # Kuehlmitteltemperatur: nur 1-300C ist physikalisch moeglich
                coolant_valid = 0 < coolant < 300
                if coolant_valid and coolant > 100 and not prev_alarm_state.get("overtemp"):
                    store_alarm(conf["db_path"], "overtemp", 1, f"Kuehlmittel-Uebertemperatur: {coolant}C")
                    prev_alarm_state["overtemp"] = True
                elif (not coolant_valid or coolant <= 95) and prev_alarm_state.get("overtemp"):
                    clear_alarm(conf["db_path"], "overtemp")
                    prev_alarm_state["overtemp"] = False

                # Oeldruck: nur pruefen wenn Motor laeuft (RPM > 500) und Wert plausibel (< 2000 kPa)
                oil_valid = 0 < oil_kpa < 2000
                if oil_valid and oil_kpa < 100 and engine_rpm > 500 and not prev_alarm_state.get("low_oil"):
                    store_alarm(conf["db_path"], "low_oil_pressure", 2, f"Niedriger Oeldruck: {oil_kpa}kPa bei {engine_rpm}rpm")
                    prev_alarm_state["low_oil"] = True
                elif (not oil_valid or oil_kpa >= 150 or engine_rpm <= 500) and prev_alarm_state.get("low_oil"):
                    clear_alarm(conf["db_path"], "low_oil_pressure")
                    prev_alarm_state["low_oil"] = False

                # Batteriespannung: nur 1-50V ist plausibel
                batt_valid = 0 < batt_v < 50
                if batt_valid and batt_v < 10.5 and not prev_alarm_state.get("low_batt"):
                    store_alarm(conf["db_path"], "low_battery", 3, f"Niedrige Batteriespannung: {batt_v}V")
                    prev_alarm_state["low_batt"] = True
                elif (not batt_valid or batt_v >= 11.5) and prev_alarm_state.get("low_batt"):
                    clear_alarm(conf["db_path"], "low_battery")
                    prev_alarm_state["low_batt"] = False

            else:
                consecutive_errors += 1

            # GPS lesen (alle 60 Sekunden)
            now = time.time()
            if now - last_gps_time >= 60:
                gps = read_gps()
                if gps:
                    last_gps = gps
                last_gps_time = now

            # Schnelles Command-Polling (alle 5 Sekunden)
            if now - last_cmd_poll_time >= 5:
                poll_commands(conf, ser)
                last_cmd_poll_time = now

            # Periodisch zum Portal syncen (alle 30 Sekunden)
            if now - last_sync_time >= int(conf["sync_interval"]):
                synced = sync_to_portal(conf, last_gps, ser)
                portal_connected = synced >= 0  # Track portal connectivity  # noqa: F841
                last_sync_time = now

                # Disk-Pruefung (nur alle 5 Minuten)
                if now - last_disk_check >= 300:
                    cleanup_old(conf["db_path"], int(conf["max_disk_gb"]))
                    last_disk_check = now

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

    if ser and ser.is_open:
        ser.close()
    log.info("Verbindung geschlossen.")


if __name__ == "__main__":
    main()
