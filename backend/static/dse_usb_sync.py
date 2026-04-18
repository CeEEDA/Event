#!/usr/bin/env python3
"""
DSE USB Sync - Liest DSE Controller (L401/8610/etc.) ueber USB BULK und sendet Daten ans Portal.
Nutzt pyusb statt pymodbus (DSE USB ist kein Standard-Serial).
"""
import usb.core
import usb.util
import struct
import time
import json
import sqlite3
import os
import sys
import logging
import configparser
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dse_usb_sync")


# ============== GPS via gpsd ==============

def read_gps():
    """Read GPS position from gpsd (if running)."""
    try:
        import subprocess
        result = subprocess.run(
            ["gpspipe", "-w", "-n", "5"],
            capture_output=True, text=True, timeout=8
        )
        for line in result.stdout.splitlines():
            if '"class":"TPV"' in line:
                import json as _json
                tpv = _json.loads(line)
                lat = tpv.get("lat")
                lon = tpv.get("lon")
                if lat is not None and lon is not None:
                    return round(lat, 6), round(lon, 6)
    except Exception:
        pass
    return None, None

# ============== Modbus RTU over USB BULK ==============

def modbus_crc(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return struct.pack('<H', crc)


class DseUsbConnection:
    """Direct USB BULK communication with DSE controllers."""

    DSE_VID = 0x1b90
    DSE_PID = 0x0001

    def __init__(self, slave_id=1):
        self.slave_id = slave_id
        self.dev = None
        self.ep_out = None
        self.ep_in = None

    def connect(self):
        self.dev = usb.core.find(idVendor=self.DSE_VID, idProduct=self.DSE_PID)
        if self.dev is None:
            raise ConnectionError("DSE USB Geraet nicht gefunden (VID=1b90 PID=0001)")
        try:
            if self.dev.is_kernel_driver_active(0):
                self.dev.detach_kernel_driver(0)
        except Exception:
            pass
        self.dev.set_configuration()
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0, 0)]
        self.ep_out = usb.util.find_descriptor(
            intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        self.ep_in = usb.util.find_descriptor(
            intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
        if not self.ep_out or not self.ep_in:
            raise ConnectionError("DSE USB Endpoints nicht gefunden")
        logger.info(f"DSE USB verbunden (Slave {self.slave_id})")
        return True

    def close(self):
        if self.dev:
            usb.util.dispose_resources(self.dev)
            self.dev = None

    def read_registers(self, page, register, count):
        """Read GenComm registers. Address = (page << 8) | register."""
        addr = (page << 8) | register
        pdu = struct.pack('>BBHH', self.slave_id, 0x03, addr, count)
        pkt = pdu + modbus_crc(pdu)
        try:
            self.ep_out.write(pkt)
            time.sleep(0.15)
            resp = self.ep_in.read(64, timeout=2000)
            data = resp.tobytes()
            if len(data) >= 3 and data[1] == 0x03:
                n = data[2]
                regs = []
                for i in range(0, n, 2):
                    if 3 + i + 1 < len(data):
                        regs.append(struct.unpack('>H', data[3 + i:5 + i])[0])
                return regs
            elif len(data) >= 2 and data[1] == 0x83:
                logger.warning(f"Modbus Exception P{page}R{register}: code={data[2]}")
                return None
        except usb.core.USBError as e:
            if "timed out" in str(e).lower():
                return None
            raise
        return None

    def read_32bit(self, page, register):
        """Read a 32-bit value from two consecutive registers."""
        regs = self.read_registers(page, register, 2)
        if regs and len(regs) >= 2:
            return (regs[0] << 16) | regs[1]
        return None

    def write_register(self, page, register, value):
        """Write a single GenComm register. Used for control commands (Page 16)."""
        addr = (page << 8) | register
        pdu = struct.pack('>BBHH', self.slave_id, 0x06, addr, value)
        pkt = pdu + modbus_crc(pdu)
        try:
            self.ep_out.write(pkt)
            time.sleep(0.3)
            resp = self.ep_in.read(64, timeout=2000)
            data = resp.tobytes()
            if len(data) >= 4 and data[1] == 0x06:
                return True
            elif len(data) >= 2 and data[1] == 0x86:
                logger.warning(f"Write Exception P{page}R{register}: code={data[2]}")
        except usb.core.USBError as e:
            if "timed out" not in str(e).lower():
                raise
        return False


# ============== Sentinel Filter ==============

SENTINEL_VALUES = {0xFFFF, 0xFFFE, 0xFFFD, 0xFFFC, 0x7FFF, 0x7FFE, 0x7FFD, 0x7FFC, 0x8000}

ALARM_NAMES = {
    1: "Notaus (Emergency Stop)", 2: "Niedriger Oeldruck", 3: "Hohe Kuehlwassertemperatur",
    4: "Hohe Oeltemperatur", 5: "Unterdrehzahl", 6: "Ueberdrehzahl",
    7: "Start fehlgeschlagen", 8: "Stopp fehlgeschlagen", 9: "Drehzahlsignal verloren",
    10: "Generator Unterspannung", 11: "Generator Ueberspannung", 12: "Generator Unterfrequenz",
    13: "Generator Ueberfrequenz", 14: "Generator Ueberstrom", 15: "Erdschluss",
    16: "Rueckleistung", 17: "Luftklappe", 18: "Oeldrucksensor Fehler",
    19: "Kuehlmitteltemp. Sensor Fehler", 20: "Oeltemp. Sensor Fehler",
    21: "Kraftstoffsensor Fehler", 22: "Drehzahlgeber Fehler",
    23: "AC Drehzahlsignal verloren", 24: "Lademaschine Fehler",
    25: "Niedrige Batteriespannung", 26: "Hohe Batteriespannung",
    27: "Niedriger Kraftstoff", 28: "Hoher Kraftstoff",
}

def valid(val):
    if val is None:
        return False
    if val in SENTINEL_VALUES:
        return False
    return True

def valid32(val):
    if val is None:
        return False
    if val >= 0x7FFFFFFC:
        return False
    return True


# ============== GenComm Register Reader ==============

def read_all_gencomm(conn):
    """Read all relevant GenComm pages and return telemetry dict."""
    data = {"timestamp": datetime.now(timezone.utc).isoformat()}

    # Page 3: Status
    p3 = conn.read_registers(3, 0, 10)
    if p3:
        if len(p3) > 4 and valid(p3[4]):
            data["dse_mode"] = p3[4]
        if len(p3) > 6:
            data["status_bits"] = p3[6]

    # Page 4: Engine + Generator (all 3 phases)
    p4 = conn.read_registers(4, 0, 20)
    if p4:
        if len(p4) > 0 and valid(p4[0]):
            data["oil_pressure"] = p4[0]
        if len(p4) > 1 and valid(p4[1]):
            data["coolant_temp"] = p4[1]
        if len(p4) > 2 and valid(p4[2]):
            data["oil_temp"] = p4[2]
        if len(p4) > 3 and valid(p4[3]):
            data["fuel_level"] = min(p4[3], 100)
        if len(p4) > 4 and valid(p4[4]):
            data["charge_alt_voltage"] = p4[4] / 10.0
        if len(p4) > 5 and valid(p4[5]):
            data["battery_voltage"] = p4[5] / 10.0
        if len(p4) > 6 and valid(p4[6]):
            data["engine_speed"] = p4[6]
        if len(p4) > 7 and valid(p4[7]):
            data["frequency"] = p4[7] / 10.0
        # L1 Voltage/Current/Watts
        if len(p4) > 8 and valid(p4[8]):
            data["gen_l1_voltage"] = p4[8] / 10.0
        if len(p4) > 12 and valid(p4[12]):
            data["gen_l1_current"] = p4[12] / 10.0
        if len(p4) > 16 and valid(p4[16]):
            data["gen_l1_watts"] = p4[16]
        # L2 Voltage/Current/Watts (3-phase: 8610, 7310)
        if len(p4) > 9 and valid(p4[9]):
            data["gen_l2_voltage"] = p4[9] / 10.0
        if len(p4) > 13 and valid(p4[13]):
            data["gen_l2_current"] = p4[13] / 10.0
        if len(p4) > 17 and valid(p4[17]):
            data["gen_l2_watts"] = p4[17]
        # L3 Voltage/Current/Watts (3-phase: 8610, 7310)
        if len(p4) > 10 and valid(p4[10]):
            data["gen_l3_voltage"] = p4[10] / 10.0
        if len(p4) > 14 and valid(p4[14]):
            data["gen_l3_current"] = p4[14] / 10.0
        if len(p4) > 18 and valid(p4[18]):
            data["gen_l3_watts"] = p4[18]

    # Page 6: Power factor, total watts
    p6 = conn.read_registers(6, 0, 22)
    if p6:
        if len(p6) >= 2:
            total_w = (p6[0] << 16) | p6[1]
            if total_w < 0x7FFFFFFC:
                if total_w > 0x7FFFFFFF:
                    total_w -= 0x100000000
                data["gen_total_watts"] = total_w
        if len(p6) > 21 and valid(p6[21]):
            data["power_factor"] = p6[21] / 100.0

    # Page 7: Hours, kWh, starts
    p7_hours = conn.read_32bit(7, 6)
    if p7_hours is not None and valid32(p7_hours):
        data["hours_run"] = round(p7_hours / 3600.0, 1)
    p7_starts = conn.read_32bit(7, 16)
    if p7_starts is not None and valid32(p7_starts):
        data["engine_starts"] = p7_starts
    p7_kwh = conn.read_32bit(7, 4)
    if p7_kwh is not None and valid32(p7_kwh):
        data["energy_kwh"] = p7_kwh

    # Page 8: Alarm conditions (first 7 registers = 28 alarms)
    p8 = conn.read_registers(8, 1, 7)
    if p8:
        active_alarms = []
        alarm_pos = 0
        for reg_val in p8:
            nibbles = [(reg_val >> 12) & 0xF, (reg_val >> 8) & 0xF, (reg_val >> 4) & 0xF, reg_val & 0xF]
            for condition in nibbles:
                alarm_pos += 1
                if condition in (2, 3, 4, 5, 10):
                    active_alarms.append({"pos": alarm_pos, "condition": condition})
        if active_alarms:
            data["active_alarms"] = active_alarms

    return data


# ============== Local DB Buffer ==============

def init_db(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS telemetry_buffer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        data TEXT NOT NULL,
        synced INTEGER DEFAULT 0
    )""")
    conn.commit()
    return conn


def buffer_telemetry(db_conn, data):
    db_conn.execute("INSERT INTO telemetry_buffer (timestamp, data) VALUES (?, ?)",
                    (data["timestamp"], json.dumps(data)))
    db_conn.commit()


def sync_to_portal(db_conn, api_url, device_id, device_key):
    """Send buffered telemetry to portal via /api/generators/ingest."""
    rows = db_conn.execute(
        "SELECT id, data FROM telemetry_buffer WHERE synced=0 ORDER BY id LIMIT 100"
    ).fetchall()

    records = []
    ids = []
    all_alarms = []
    lat, lon = read_gps()  # GPS from gpsd
    for row_id, data_json in rows:
        raw = json.loads(data_json)
        # Map to Pi ingest field names
        rec = {"ts_utc": raw.get("timestamp", ""), "source": "dse_usb_pi"}
        field_map = {
            "oil_pressure": "oil_pressure_kpa",
            "coolant_temp": "coolant_temp_c",
            "oil_temp": "oil_temp_c",
            "fuel_level": "fuel_level_pct",
            "charge_alt_voltage": "charge_alt_voltage",
            "battery_voltage": "battery_voltage",
            "engine_speed": "rpm",
            "frequency": "frequency",
            "gen_l1_voltage": "voltage_l1",
            "gen_l1_current": "current_l1",
            "gen_l1_watts": "power_l1_w",
            "gen_l2_voltage": "voltage_l2",
            "gen_l2_current": "current_l2",
            "gen_l2_watts": "power_l2_w",
            "gen_l3_voltage": "voltage_l3",
            "gen_l3_current": "current_l3",
            "gen_l3_watts": "power_l3_w",
            "gen_total_watts": "power_total_w",
            "power_factor": "power_factor_avg",
            "hours_run": "engine_run_hours",
            "engine_starts": "num_starts",
            "energy_kwh": "energy_kwh",
            "dse_mode": "dse_mode",
        }
        for src_key, dst_key in field_map.items():
            if src_key in raw and raw[src_key] is not None:
                rec[dst_key] = raw[src_key]
        rec["engine_running"] = (raw.get("engine_speed", 0) or 0) > 100
        records.append(rec)
        ids.append(row_id)

        # Collect alarms
        for alarm in raw.get("active_alarms", []):
            all_alarms.append({
                "ts_utc": raw.get("timestamp", ""),
                "alarm_type": "shutdown" if alarm.get("condition") in (3, 4) else "warning",
                "alarm_code": alarm.get("pos", 0),
                "description": ALARM_NAMES.get(alarm.get("pos", 0), f"Alarm #{alarm.get('pos')}"),
                "active": True,
            })

    if not records and not all_alarms:
        return 0

    payload = {
        "api_key": device_key,
        "device_id": device_id,
        "generator_id": "",
        "records": records,
        "alarms": all_alarms,
        "command_results": [],
        "latitude": lat,
        "longitude": lon,
    }

    try:
        resp = requests.post(
            f"{api_url}/generators/ingest",
            json=payload,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            placeholders = ",".join("?" * len(ids))
            db_conn.execute(f"UPDATE telemetry_buffer SET synced=1 WHERE id IN ({placeholders})", ids)
            db_conn.commit()
            result = resp.json()
            logger.info(f"Portal-Sync: {result.get('inserted', 0)} Datensaetze, {len(all_alarms)} Alarme")
            # Return pending commands from portal
            return len(ids), result.get("pending_commands", [])
        else:
            logger.warning(f"Portal-Sync Fehler: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Portal-Sync Fehler: {e}")
    return 0, []


# DSE GenComm Page 16 Register 8: Control register
# Write values for commands
DSE_COMMAND_MAP = {
    "stop": 0x01,
    "auto_on": 0x03,
    "manual": 0x04,
    "start": 0x07,
    "mute": 0x08,
    "reset": 0x15,
    "gen_switch_on": 0x09,
    "gen_switch_off": 0x0A,
    "test_on_load": 0x05,
    "auto_manual_restore": 0x06,
    "reset_mains": 0x17,
}


def execute_commands(dse_conn, commands):
    """Execute pending control commands from portal via GenComm Page 16."""
    results = []
    for cmd in commands:
        cmd_name = cmd.get("command", "")
        cmd_id = cmd.get("id", "")
        value = DSE_COMMAND_MAP.get(cmd_name)
        if value is None:
            logger.warning(f"Unbekannter Befehl: {cmd_name}")
            results.append({"id": cmd_id, "status": "error", "detail": f"Unbekannt: {cmd_name}"})
            continue
        logger.info(f"Fuehre Befehl aus: {cmd_name} (Page16 R8 = {hex(value)})")
        ok = dse_conn.write_register(16, 8, value)
        if ok:
            logger.info(f"Befehl {cmd_name} erfolgreich")
            results.append({"id": cmd_id, "status": "done"})
        else:
            logger.error(f"Befehl {cmd_name} fehlgeschlagen")
            results.append({"id": cmd_id, "status": "error", "detail": "Write fehlgeschlagen"})
    return results


def cleanup_db(db_conn, max_rows=50000):
    count = db_conn.execute("SELECT COUNT(*) FROM telemetry_buffer WHERE synced=1").fetchone()[0]
    if count > max_rows:
        db_conn.execute(f"DELETE FROM telemetry_buffer WHERE synced=1 AND id NOT IN (SELECT id FROM telemetry_buffer WHERE synced=1 ORDER BY id DESC LIMIT {max_rows})")
        db_conn.commit()


# ============== Main Loop ==============

def main():
    config = configparser.ConfigParser()
    config_path = "/etc/dse5510.conf"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    config.read(config_path)

    section = "dse5510"
    api_url = config.get(section, "api_url", fallback="")
    device_key = config.get(section, "device_key", fallback="")
    device_id = config.get(section, "device_id", fallback="")
    db_path = config.get(section, "db_path", fallback="/var/lib/dse5510/dse5510.sqlite")
    slave_id = config.getint(section, "slave_id", fallback=1)
    read_interval = config.getint(section, "read_interval", fallback=1)
    sync_interval = config.getint(section, "sync_interval", fallback=30)

    if not api_url or not device_key or not device_id:
        logger.error("Config unvollstaendig: api_url, device_key, device_id erforderlich")
        sys.exit(1)

    logger.info(f"DSE USB Sync gestartet (Device: {device_id[:12]}..., Slave: {slave_id})")
    logger.info(f"Portal: {api_url}")

    db_conn = init_db(db_path)
    dse = DseUsbConnection(slave_id=slave_id)
    last_sync = 0
    connected = False

    while True:
        try:
            # Connect / Reconnect
            if not connected:
                try:
                    dse.connect()
                    connected = True
                except Exception as e:
                    logger.error(f"USB Verbindung fehlgeschlagen: {e}")
                    time.sleep(10)
                    continue

            # Read telemetry
            data = read_all_gencomm(dse)
            if data and len(data) > 1:
                buffer_telemetry(db_conn, data)
                bat = data.get("battery_voltage", "?")
                rpm = data.get("engine_speed", "?")
                logger.debug(f"Gelesen: Bat={bat}V RPM={rpm}")

            # Sync to portal
            now = time.time()
            if now - last_sync >= sync_interval:
                synced, pending_cmds = sync_to_portal(db_conn, api_url, device_id, device_key)
                last_sync = now
                if synced > 0:
                    cleanup_db(db_conn)
                # Execute pending commands
                if pending_cmds:
                    cmd_results = execute_commands(dse, pending_cmds)
                    # Report results back on next sync
                    if cmd_results:
                        logger.info(f"Command-Ergebnisse: {cmd_results}")

            time.sleep(read_interval)

        except usb.core.USBError as e:
            logger.error(f"USB Fehler: {e}")
            connected = False
            dse.close()
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Beendet.")
            break
        except Exception as e:
            logger.error(f"Fehler: {e}")
            time.sleep(5)

    dse.close()
    db_conn.close()


if __name__ == "__main__":
    main()
