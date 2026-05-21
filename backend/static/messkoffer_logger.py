#!/usr/bin/env python3
"""
Messkoffer Logger + Sync - Eventenergie Portal
================================================
Liest Rayleigh RI-F100-C Energy Meter ueber Waveshare USB-RS485-Adapter
(Modbus RTU), kombiniert mit USB-GPS, speichert lokal in SQLite und
synchronisiert mit dem Portal alle 20 Minuten (Batch-Modus).

Hardware-Setup ab Mai 2026:
  - Raspberry Pi (gleicher Pi wie vorher)
  - Waveshare USB → RS485-Adapter (CH340 / CP2102 / FT232)
  - Rayleigh RI-F100-C MID-Energiezaehler (Modbus RTU @ 9600 8N1, Slave 1)
  - USB-GPS (gpsd) - optional, bleibt wie vorher

Frueher: Shelly Pro 3EM via WLAN/HTTP (deprecated, einzelner Altbestand
wurde vorerst nicht migriert).

Voraussetzungen (werden vom Setup-Skript installiert):
  - python3, python3-minimalmodbus, python3-serial, python3-gps, requests
  - gpsd

Konfiguration: /etc/messkoffer.conf
Logs:          sudo journalctl -u messkoffer -f
"""

import configparser
import hashlib
import logging
import os
import sqlite3
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

# Skript-Version - wird bei jedem OTA-Check zum Portal gemeldet
SCRIPT_VERSION = "2.1.3"

# Modbus (minimalmodbus, klein und stabil)
try:
    import minimalmodbus  # type: ignore
    import serial  # type: ignore
    MODBUS_AVAILABLE = True
except ImportError:
    MODBUS_AVAILABLE = False

# GPS (gpsd)
try:
    from gps import gps as gpsd_connect, WATCH_ENABLE, WATCH_NEWSTYLE
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False


# =========================================================================
# Konfiguration
# =========================================================================

def load_config():
    config = {
        # Modbus
        "modbus_port": "/dev/rayleigh",      # via udev-Rule symlink, fallback /dev/ttyUSB0
        "modbus_baudrate": 9600,
        "modbus_slave_id": 1,
        "modbus_parity": "N",                # N=None, E=Even, O=Odd
        "modbus_stopbits": 1,
        "modbus_bytesize": 8,
        "modbus_timeout": 2.0,
        "modbus_float_format": "cdab",   # auto | abcd | cdab | badc | dcba
                                          # Empirisch verifiziert per Diag v2: CDAB ist korrekt
                                          # fuer den RI-F100-C (V1-N @ 0x00 FC4 CDAB liefert ~230V).
        # Adress-Offset: Datenblatt-Hex direkt verwenden (KEIN +1). Diag v2 hat
        # bestaetigt dass der Meter mit Offset=0 antwortet.
        "modbus_address_offset": 0,
        # Function Code: Der RI-F100-C liefert die Float-Reverse-Word Mess-
        # register ueber FC04 (Input Registers), NICHT FC03 (Holding Registers)
        # wie das Datenblatt schreibt. FC03 liefert FC04-Setup-Daten zurueck.
        # Empirisch per Diag v2 verifiziert.
        "modbus_function_code": 4,
        # Inter-Transaction-Delay: Pause in Sekunden ZWISCHEN aufeinanderfolgenden
        # Modbus-Reads. Empirisch erforderlich beim RI-F100-C: bei <100ms Pause
        # antwortet der Meter sporadisch nicht (NoResponseError). Default 0.1s
        # ist ein konservativer Wert; bei stabilem Bus kann man auf 0.05 runter.
        "modbus_inter_read_delay_s": 0.1,
        # Portal
        "api_url": "",
        "device_key": "",
        "device_id": "",
        "meter_id": "",
        # Storage
        "db_path": "/var/lib/messkoffer/messkoffer.sqlite",
        "log_interval": 1,                   # 1 Sek Polling lokal
        "sync_interval": 1200,               # 20 Min Batch-Upload
        "sync_batch_size": 2000,             # 2000 Zeilen pro Batch = 33 Min Daten
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

    # Env-Vars ueberschreiben (gleiche MK_* Praefixe wie vorher fuer
    # Rueckwaerts-Kompatibilitaet, plus neue MK_MODBUS_*).
    env_map = {
        "MK_MODBUS_PORT": "modbus_port",
        "MK_MODBUS_BAUDRATE": "modbus_baudrate",
        "MK_MODBUS_SLAVE_ID": "modbus_slave_id",
        "MK_MODBUS_PARITY": "modbus_parity",
        "MK_API_URL": "api_url",
        "MK_DEVICE_KEY": "device_key",
        "MK_DEVICE_ID": "device_id",
        "MK_METER_ID": "meter_id",
        "MK_DB_PATH": "db_path",
        "MK_SYNC_INTERVAL": "sync_interval",
    }
    for env_key, conf_key in env_map.items():
        val = os.environ.get(env_key)
        if val:
            if isinstance(config[conf_key], int):
                try:
                    config[conf_key] = int(val)
                except ValueError:
                    pass
            elif isinstance(config[conf_key], float):
                try:
                    config[conf_key] = float(val)
                except ValueError:
                    pass
            else:
                config[conf_key] = val

    return config


CFG = load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("messkoffer")

# Globaler GPS-Zustand
gps_data = {"lat": None, "lon": None, "alt": None, "speed": None, "fix": 0}
gps_lock = threading.Lock()


# =========================================================================
# Datenbank
# =========================================================================

def init_db():
    db_dir = os.path.dirname(CFG["db_path"])
    os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(CFG["db_path"])
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            voltage_l1 REAL, voltage_l2 REAL, voltage_l3 REAL,
            current_l1 REAL, current_l2 REAL, current_l3 REAL,
            power_l1_kw REAL, power_l2_kw REAL, power_l3_kw REAL,
            total_kw REAL, total_kva REAL,
            avg_pf REAL, frequency REAL,
            energy_imp_kwh REAL, energy_exp_kwh REAL,
            gps_lat REAL, gps_lon REAL, gps_alt REAL, gps_speed REAL, gps_fix INTEGER DEFAULT 0,
            sent INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_measurements_ts ON measurements(ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_measurements_sent ON measurements(sent, id)")
    conn.commit()
    conn.close()
    log.info(f"Datenbank bereit: {CFG['db_path']}")


def get_db_size_gb():
    try:
        return os.path.getsize(CFG["db_path"]) / (1024 ** 3)
    except OSError:
        return 0


def cleanup_db():
    size_gb = get_db_size_gb()
    if size_gb <= CFG["max_db_size_gb"]:
        return
    log.warning(f"DB ist {size_gb:.1f} GB (Limit: {CFG['max_db_size_gb']} GB), loesche aelteste Daten...")
    try:
        conn = sqlite3.connect(CFG["db_path"])
        total = conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
        delete_count = max(int(total * 0.05), 10000)
        # Nur synchronisierte Datensaetze loeschen damit nichts verloren geht
        conn.execute(f"""
            DELETE FROM measurements WHERE id IN (
                SELECT id FROM measurements WHERE sent=1 ORDER BY id ASC LIMIT {delete_count}
            )
        """)
        conn.commit()
        conn.execute("VACUUM")
        conn.commit()
        conn.close()
        new_size = get_db_size_gb()
        log.info(f"Bereinigt: ~{delete_count} synchr. Datensaetze geloescht, DB jetzt {new_size:.1f} GB")
    except Exception as e:
        log.error(f"DB-Bereinigung Fehler: {e}")


# =========================================================================
# Rayleigh RI-F100-C - Modbus RTU
# =========================================================================
# Register-Map laut RI-F100-C-COMM-V01.pdf, Float-Reverse-Word (MSB.LSB).
# Bei FC03 (Read Holding Register) ist +1 Offset zur Doku-Adresse noetig.
# minimalmodbus.read_float kann das nicht direkt -> wir lesen Roh-Register
# und konvertieren selbst.
REGISTERS = {
    "voltage_l1":     (0x00, 2),   # V
    "voltage_l2":     (0x02, 2),   # V
    "voltage_l3":     (0x04, 2),   # V
    "current_l1":     (0x10, 2),   # A
    "current_l2":     (0x12, 2),   # A
    "current_l3":     (0x14, 2),   # A
    "power_l1_kw":    (0x18, 2),   # kW
    "power_l2_kw":    (0x1A, 2),   # kW
    "power_l3_kw":    (0x1C, 2),   # kW
    "total_kw":       (0x2A, 2),   # kW (Total Active Power)
    "total_kva":      (0x2C, 2),   # kVA (Total Apparent Power)
    "frequency":      (0x38, 2),   # Hz - laut RI-F100-C-COMM-V01.pdf an 0x38, NICHT 0x36!
    "energy_imp_kwh": (0x60, 2),   # kWh Import (siehe Hinweis: Summe der Phasen oder Total kWh)
    "energy_exp_kwh": (0x62, 2),   # kWh Export
}
# Average PF liegt laut Datenblatt an 0x36 (Float Reverse Word, 2 Register),
# NICHT an 0x41D (das war eine falsche Annahme einer anderen Meter-Firmware).
PF_REGISTER = (0x36, 2)  # Average PF (Float Reverse Word)


_detected_float_format = None  # nach erster erfolgreicher Erkennung gemerkt


def _try_all_float_formats(words):
    """Probiert alle 4 Byte/Word-Orderings durch und gibt Liste (fmt, value)
    fuer die Heuristik zurueck."""
    import struct
    if len(words) != 2:
        return []
    w0, w1 = words[0] & 0xFFFF, words[1] & 0xFFFF
    w0b = ((w0 & 0xFF) << 8) | ((w0 >> 8) & 0xFF)
    w1b = ((w1 & 0xFF) << 8) | ((w1 >> 8) & 0xFF)
    candidates = {
        "abcd": (w0 << 16) | w1,
        "cdab": (w1 << 16) | w0,
        "badc": (w0b << 16) | w1b,
        "dcba": (w1b << 16) | w0b,
    }
    out = []
    for fmt, raw in candidates.items():
        try:
            v = struct.unpack(">f", raw.to_bytes(4, "big"))[0]
            out.append((fmt, v))
        except Exception:
            pass
    return out


def _autodetect_float_format(freq_words):
    """Probe-Heuristik: anhand der Frequenz-Register (sollte ~50 Hz sein)
    ermitteln welches Byte/Word-Ordering verwendet wird. Wird einmalig
    aufgerufen und das Ergebnis gecached. Fallback: 'cdab' (laut RI-F100-C
    Datenblatt = "FLOAT REVERSE WORD").
    """
    global _detected_float_format
    for fmt, val in _try_all_float_formats(freq_words):
        if val is not None and 45.0 <= val <= 65.0:
            _detected_float_format = fmt
            log.info(f"Float-Format erkannt: {fmt.upper()} (Frequenz-Probe = {val:.2f} Hz)")
            return fmt
    log.warning(f"Float-Format Auto-Detect fehlgeschlagen aus Frequenz-Words {freq_words}, fallback CDAB (Datenblatt-Default)")
    _detected_float_format = "cdab"
    return "cdab"


def _decode_float_reverse_word(words):
    """IEEE754 32-bit Float aus 2 Modbus 16-bit Registern dekodieren.

    Das Byte-/Word-Ordering wird ueber CFG['modbus_float_format'] gesteuert
    ('auto' | 'abcd' | 'cdab' | 'badc' | 'dcba'). Im Modus 'auto' wird beim
    ersten Read das Format anhand der Frequenz-Register (sollte ~50 Hz sein)
    automatisch erkannt und gecached.
    """
    import struct
    if len(words) != 2:
        return None
    fmt = (CFG.get("modbus_float_format") or "auto").lower()
    if fmt == "auto":
        fmt = _detected_float_format or "cdab"
    w0, w1 = words[0] & 0xFFFF, words[1] & 0xFFFF
    if fmt == "abcd":
        raw32 = (w0 << 16) | w1
    elif fmt == "cdab":
        raw32 = (w1 << 16) | w0
    elif fmt == "badc":
        w0 = ((w0 & 0xFF) << 8) | ((w0 >> 8) & 0xFF)
        w1 = ((w1 & 0xFF) << 8) | ((w1 >> 8) & 0xFF)
        raw32 = (w0 << 16) | w1
    elif fmt == "dcba":
        w0 = ((w0 & 0xFF) << 8) | ((w0 >> 8) & 0xFF)
        w1 = ((w1 & 0xFF) << 8) | ((w1 >> 8) & 0xFF)
        raw32 = (w1 << 16) | w0
    else:
        raw32 = (w0 << 16) | w1
    try:
        return struct.unpack(">f", raw32.to_bytes(4, "big"))[0]
    except (struct.error, OverflowError):
        return None


def _candidate_serial_ports() -> list:
    """Liefert eine geordnete Liste moeglicher Ports fuer Auto-Detection.
    Reihenfolge: /dev/rayleigh (udev-Symlink), dann alle /dev/ttyUSB*, dann
    alle /dev/ttyACM* (CH343/CH9102 melden sich als ACM).
    """
    import glob
    cands = []
    if os.path.exists("/dev/rayleigh"):
        cands.append("/dev/rayleigh")
    cands.extend(sorted(glob.glob("/dev/ttyUSB*")))
    cands.extend(sorted(glob.glob("/dev/ttyACM*")))
    # Doppelte vermeiden (z.B. wenn /dev/rayleigh schon auf /dev/ttyACM1 zeigt)
    seen, uniq = set(), []
    for p in cands:
        try:
            real = os.path.realpath(p)
        except Exception:
            real = p
        if real not in seen:
            seen.add(real)
            uniq.append(p)
    return uniq


def _probe_port(port: str) -> bool:
    """Versucht einen FC03 Read von Reg 1 (Voltage L1) auf dem Port.
    Returns True wenn Slave antwortet (egal welcher Wert)."""
    if not MODBUS_AVAILABLE:
        return False
    try:
        instr = minimalmodbus.Instrument(port, CFG["modbus_slave_id"])
        instr.serial.baudrate = CFG["modbus_baudrate"]
        instr.serial.bytesize = CFG["modbus_bytesize"]
        parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}
        instr.serial.parity = parity_map.get(CFG["modbus_parity"], serial.PARITY_NONE)
        instr.serial.stopbits = CFG["modbus_stopbits"]
        instr.serial.timeout = 0.5  # kurz halten beim Probing
        instr.mode = minimalmodbus.MODE_RTU
        instr.clear_buffers_before_each_transaction = True
        # Voltage L1 lesen (2 Register, FC03, +1 Offset)
        words = instr.read_registers(1, 2, functioncode=3)
        try:
            instr.serial.close()
        except Exception:
            pass
        return isinstance(words, list) and len(words) == 2
    except Exception as e:
        log.debug(f"Probe {port} fehlgeschlagen: {e}")
        return False


def _auto_detect_modbus_port() -> str:
    """Sucht ueber alle /dev/ttyACM* + /dev/ttyUSB* nach einem Port der auf
    Slave 1 antwortet. Cached das Ergebnis fuer den naechsten Aufruf (CFG
    wird ueberschrieben, sodass weitere Lese-Versuche direkt klappen)."""
    cands = _candidate_serial_ports()
    if not cands:
        log.warning("Keine /dev/ttyUSB*/ttyACM* Ports gefunden - USB-Adapter angesteckt?")
        return ""
    log.info(f"Auto-Detect Modbus: probiere {len(cands)} Port(s): {cands}")
    for port in cands:
        if _probe_port(port):
            log.info(f"Modbus-Slave gefunden auf {port} (Slave {CFG['modbus_slave_id']})")
            CFG["modbus_port"] = port
            return port
    log.warning(
        f"Auto-Detect: kein Port hat geantwortet. Geprueft: {cands}. "
        f"Pruefe RS485-Verkabelung (A/B nicht vertauscht), Slave-ID am Geraet."
    )
    return ""


def _create_modbus_client():
    if not MODBUS_AVAILABLE:
        return None
    port = CFG.get("modbus_port") or ""

    # Robust: nicht nur pruefen ob File-Path existiert, sondern auch ob der
    # Slave tatsaechlich antwortet. Wenn /dev/rayleigh z.B. als Stub-Symlink
    # angelegt wurde oder auf das GPS-Geraet zeigt, wuerden Reads dauerhaft
    # fehlschlagen ohne dass Auto-Detect ausgeloest wird.
    port_works = False
    if port and os.path.exists(port):
        log.debug(f"Pruefe konfigurierten Port: {port}")
        port_works = _probe_port(port)
        if not port_works:
            log.warning(f"Konfigurierter Port '{port}' antwortet nicht - starte Auto-Detect ueber alle USB-Seriell-Ports")

    if not port_works:
        if port and not os.path.exists(port):
            log.warning(f"Konfigurierter Port '{port}' existiert nicht - starte Auto-Detect")
        detected = _auto_detect_modbus_port()
        if detected:
            port = detected
        else:
            return None

    try:
        instr = minimalmodbus.Instrument(port, CFG["modbus_slave_id"])
        instr.serial.baudrate = CFG["modbus_baudrate"]
        instr.serial.bytesize = CFG["modbus_bytesize"]
        parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}
        instr.serial.parity = parity_map.get(CFG["modbus_parity"], serial.PARITY_NONE)
        instr.serial.stopbits = CFG["modbus_stopbits"]
        instr.serial.timeout = CFG["modbus_timeout"]
        instr.mode = minimalmodbus.MODE_RTU
        instr.clear_buffers_before_each_transaction = True
        log.debug(f"Modbus-Verbindung aktiv: {port} @ {CFG['modbus_baudrate']} Slave {CFG['modbus_slave_id']}")
        return instr
    except Exception as e:
        log.error(f"Modbus-Init Fehler ({port}): {e}")
        return None


# Modbus-Client wird einmal global gehalten, bei Fehler neu erzeugt
_modbus_client = None

# Status-Tracking fuer OTA-Heartbeat-Telemetrie (damit der Admin remote sieht
# wieso noch keine Daten ankommen, auch wenn der Pi keine Ingests sendet).
_pi_status = {
    "modbus_ok": False,
    "modbus_error": "",
    "last_read_ts": "",
    "last_sync_ts": "",
}


def _ensure_modbus_client():
    global _modbus_client
    if _modbus_client is None:
        _modbus_client = _create_modbus_client()
    return _modbus_client


def _reset_modbus_client():
    global _modbus_client
    try:
        if _modbus_client and _modbus_client.serial and _modbus_client.serial.is_open:
            _modbus_client.serial.close()
    except Exception:
        pass
    _modbus_client = None


def read_rayleigh():
    """Liest alle relevanten Register vom RI-F100-C in kleinen Bloecken und
    einem zusaetzlichen PF-Read. Gibt None zurueck bei Modbus-Fehler.

    WICHTIG: Wir lesen in mehreren kleinen Bloecken (max 8 Register je Read),
    da Energiezaehler wie der RI-F100-C oft nicht mehr als ~16-32 Register
    pro FC03-Anfrage beantworten. Ein einziger 46-Register-Block scheitert
    am Slave (kommt nur per Probe-Test von 2 Reg durch).
    """
    instr = _ensure_modbus_client()
    if not instr:
        return None

    def _safe_read(start_addr_offset, count):
        """Liest count Register ab Adresse mit konfigurierbarem Wire-Offset
        und konfigurierbarem Function Code.

        Per Datenblatt RI-F100-C-COMM-V01.pdf ist die Hex-Adresse der finale
        0-basierte Wire-Offset (0x00 = V1-N). Default modbus_address_offset=0.
        Function Code ist FC04 (Input Registers, ueber Diag v2 verifiziert),
        per CFG umschaltbar auf FC03 falls eine Firmware abweicht.

        Wartet `modbus_inter_read_delay_s` Sekunden NACH jedem Read, damit der
        Meter Zeit hat sich zwischen Anfragen zu erholen (RI-F100-C antwortet
        sonst sporadisch nicht).

        Returns list of int oder None bei Fehler.
        """
        try:
            wire_addr = start_addr_offset + int(CFG.get("modbus_address_offset", 0))
            fc = int(CFG.get("modbus_function_code", 4))
            result = instr.read_registers(wire_addr, count, functioncode=fc)
            return result
        except Exception as e:
            log.debug(f"read_registers({hex(start_addr_offset)}, {count}) fehlgeschlagen: {e}")
            return None
        finally:
            # Inter-Transaction-Delay - WICHTIG fuer den RI-F100-C!
            try:
                delay = float(CFG.get("modbus_inter_read_delay_s", 0.1))
                if delay > 0:
                    time.sleep(delay)
            except Exception:
                pass

    out = {}
    try:
        # WICHTIG: Diag v2 hat empirisch gezeigt, dass der RI-F100-C ueber FC04
        # nur Einzel-Float-Reads (2 Register pro Read) beantwortet. Block-Reads
        # mit mehr als 2 Registern wurden hier frueher genutzt (Block A=6,
        # Block B=6, ...) aber fuehrten zu kompletten Timeouts/Fehlern auf
        # dem realen Meter. Daher: jedes Float einzeln lesen.

        def _read_float(addr):
            words = _safe_read(addr, 2)
            if not words or len(words) < 2:
                return None
            return _decode_float_reverse_word(words)

        # Frequenz (0x38) ZUERST: optional fuer Auto-Detect des Float-Formats.
        # WICHTIG: Frequenz liegt an 0x38 (30056), NICHT an 0x36 (das ist Avg PF)!
        be = _safe_read(0x38, 2)
        if be and len(be) >= 2:
            if (CFG.get("modbus_float_format") or "auto").lower() == "auto" and _detected_float_format is None:
                _autodetect_float_format(be)
            out["frequency"] = _decode_float_reverse_word(be)
            try:
                fmt = _detected_float_format or "?"
                log.debug(f"Probe-Read Freq @0x38 raw={be} fmt={fmt} -> {out['frequency']!r}")
            except Exception:
                pass

        # Spannung L1/L2/L3 (einzeln je 2 Register)
        out["voltage_l1"] = _read_float(0x00)
        out["voltage_l2"] = _read_float(0x02)
        out["voltage_l3"] = _read_float(0x04)

        # Strom L1/L2/L3
        out["current_l1"] = _read_float(0x10)
        out["current_l2"] = _read_float(0x12)
        out["current_l3"] = _read_float(0x14)

        # Leistung L1/L2/L3 (kW)
        out["power_l1_kw"] = _read_float(0x18)
        out["power_l2_kw"] = _read_float(0x1A)
        out["power_l3_kw"] = _read_float(0x1C)

        # Total kW + Total kVA
        out["total_kw"] = _read_float(0x2A)
        out["total_kva"] = _read_float(0x2C)

        # Energie kWh Import (0x60) + Export (0x62) - existiert evtl. nicht
        # auf jedem Meter, _safe_read fangt das Exception silent ab.
        out["energy_imp_kwh"] = _read_float(0x60)
        out["energy_exp_kwh"] = _read_float(0x62)

        # Average Power Factor (Float Reverse Word @ 0x36)
        try:
            pf_val = _read_float(0x36)
            if pf_val is not None and -1.5 <= pf_val <= 1.5:
                out["avg_pf"] = pf_val
            else:
                out["avg_pf"] = None
        except Exception as pf_e:
            log.debug(f"PF-Decode fehlgeschlagen (ignoriert): {pf_e}")
            out["avg_pf"] = None

        # Wenn KEINE der primaeren Bloecke geantwortet hat, ist die Verbindung
        # praktisch tot - signal an Caller als komplett-Fehler.
        primary_keys = ("voltage_l1", "current_l1", "power_l1_kw", "frequency", "energy_imp_kwh")
        if not any(out.get(k) is not None for k in primary_keys):
            log.warning("Alle Primaer-Bloecke fehlgeschlagen - vermutlich Slave nicht erreichbar")
            _pi_status["modbus_ok"] = False
            _pi_status["modbus_error"] = "Alle Modbus-Bloecke timed out"
            _reset_modbus_client()
            return None

        _pi_status["modbus_ok"] = True
        _pi_status["modbus_error"] = ""
        _pi_status["last_read_ts"] = datetime.now(timezone.utc).isoformat()
        return out
    except (minimalmodbus.NoResponseError, minimalmodbus.InvalidResponseError, OSError) as e:
        log.debug(f"Modbus-Lesefehler: {e}")
        _pi_status["modbus_ok"] = False
        _pi_status["modbus_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        _reset_modbus_client()
        return None
    except Exception as e:
        log.warning(f"Modbus-Lesefehler unerwartet: {e}")
        _pi_status["modbus_ok"] = False
        _pi_status["modbus_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        _reset_modbus_client()
        return None


# =========================================================================
# GPS-Thread (unveraendert)
# =========================================================================

def gps_thread():
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
    with gps_lock:
        return dict(gps_data)


# =========================================================================
# Logger-Hauptschleife: 1 Hz Polling lokal
# =========================================================================

def logger_loop():
    conn = sqlite3.connect(CFG["db_path"])
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    read_count = 0
    error_count = 0
    last_cleanup = time.time()

    log.info(
        f"Logger gestartet: Rayleigh konfiguriert={CFG['modbus_port']} @ "
        f"{CFG['modbus_baudrate']} 8{CFG['modbus_parity']}{CFG['modbus_stopbits']} "
        f"Slave {CFG['modbus_slave_id']} - {CFG['log_interval']}s Polling (Auto-Detect aktiv)"
    )

    while True:
        start = time.time()
        m = read_rayleigh()
        gps = get_gps()
        ts = datetime.now(timezone.utc).isoformat()

        if m:
            try:
                conn.execute("""
                    INSERT INTO measurements (
                        ts,
                        voltage_l1, voltage_l2, voltage_l3,
                        current_l1, current_l2, current_l3,
                        power_l1_kw, power_l2_kw, power_l3_kw,
                        total_kw, total_kva, avg_pf, frequency,
                        energy_imp_kwh, energy_exp_kwh,
                        gps_lat, gps_lon, gps_alt, gps_speed, gps_fix
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    ts,
                    m.get("voltage_l1"), m.get("voltage_l2"), m.get("voltage_l3"),
                    m.get("current_l1"), m.get("current_l2"), m.get("current_l3"),
                    m.get("power_l1_kw"), m.get("power_l2_kw"), m.get("power_l3_kw"),
                    m.get("total_kw"), m.get("total_kva"), m.get("avg_pf"), m.get("frequency"),
                    m.get("energy_imp_kwh"), m.get("energy_exp_kwh"),
                    gps["lat"], gps["lon"], gps["alt"], gps["speed"], gps["fix"],
                ))
                conn.commit()
                read_count += 1
                error_count = 0
                if read_count % 60 == 0:
                    log.info(
                        f"Logging OK: {read_count} Datensaetze | "
                        f"P={(m.get('total_kw') or 0):.2f}kW | "
                        f"V={(m.get('voltage_l1') or 0):.0f}/{(m.get('voltage_l2') or 0):.0f}/{(m.get('voltage_l3') or 0):.0f}V | "
                        f"PF={(m.get('avg_pf') or 0):.2f} | "
                        f"GPS={'Fix' if gps['fix'] >= 2 else 'kein Fix'}"
                    )
            except Exception as e:
                log.error(f"SQLite Schreibfehler: {e}")
        else:
            error_count += 1
            if error_count <= 3 or error_count % 30 == 0:
                log.warning(
                    f"Rayleigh nicht erreichbar ({error_count}x) - "
                    f"Port {CFG['modbus_port']}, Slave {CFG['modbus_slave_id']}"
                )

        if time.time() - last_cleanup > CFG["cleanup_check_interval"]:
            cleanup_db()
            last_cleanup = time.time()

        elapsed = time.time() - start
        time.sleep(max(0, CFG["log_interval"] - elapsed))


# =========================================================================
# Sync-Thread: alle 20 Min Batch zum Portal
# =========================================================================

def map_to_portal(row):
    """SQLite-Zeile -> Portal /energy-monitoring/ingest Format.
    Felder die der Rayleigh nicht liefert (n_current, PF_L1/L2/L3 separat,
    Apparent pro Phase) werden 0 gesetzt - das Portal-Schema bleibt
    rueckwaerts-kompatibel.

    ALLE Messwerte werden auf 2 Nachkommastellen gerundet damit das Portal
    keine "223.0500030517578"-Float32-Artefakte mehr anzeigt. Energy-Werte
    behalten 3 Stellen (Wh-Aufloesung).
    """
    def safe(val):
        try:
            return float(val) if val is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    def r2(val):
        """Plausibilitaets-Filter + Rundung auf 2 Stellen. Sehr kleine
        Beträge (|x| < 1e-6) werden als 0.0 zurueckgegeben - das eliminiert
        die denormalisierten Float32-Artefakte (e-40, e-44).
        """
        v = safe(val)
        if abs(v) < 1e-6:
            return 0.0
        return round(v, 2)

    def r3(val):
        v = safe(val)
        if abs(v) < 1e-6:
            return 0.0
        return round(v, 3)

    p_l1 = r2(row["power_l1_kw"])
    p_l2 = r2(row["power_l2_kw"])
    p_l3 = r2(row["power_l3_kw"])
    total_kw = r2(row["total_kw"]) or round(p_l1 + p_l2 + p_l3, 2)
    total_kva = r2(row["total_kva"])

    i_l1 = r2(row["current_l1"])
    i_l2 = r2(row["current_l2"])
    i_l3 = r2(row["current_l3"])

    avg_pf = r2(row["avg_pf"])

    return {
        "id": row["id"],
        "ts_utc": row["ts"],
        "meter_ts": 0,
        "I_L1": i_l1, "I_L2": i_l2, "I_L3": i_l3,
        "I_sum": round(i_l1 + i_l2 + i_l3, 2),
        "U_L1": r2(row["voltage_l1"]),
        "U_L2": r2(row["voltage_l2"]),
        "U_L3": r2(row["voltage_l3"]),
        "F_Hz": r2(row["frequency"]),
        "P_sum_kW": total_kw,
        "P_L1_kW": p_l1,
        "P_L2_kW": p_l2,
        "P_L3_kW": p_l3,
        "Q_sum": total_kva,
        "Q_L1": 0, "Q_L2": 0, "Q_L3": 0,
        "PF_L1": avg_pf, "PF_L2": avg_pf, "PF_L3": avg_pf,
        "PF_total": avg_pf,
        "E_imp_kWh": r3(row["energy_imp_kwh"]),
        "E_exp_kWh": r3(row["energy_exp_kwh"]),
        "gps_lat": row["gps_lat"],
        "gps_lon": row["gps_lon"],
        "gps_alt_m": row["gps_alt"],
        "gps_speed_mps": row["gps_speed"],
        "gps_fix": row["gps_fix"],
    }


def get_last_sync_id():
    try:
        resp = requests.get(
            f"{CFG['api_url']}/energy-monitoring/ingest/sync-state",
            params={
                "device_id": CFG["device_id"],
                "meter_id": CFG["meter_id"],
                "api_key": CFG["device_key"],
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("last_sync_id", 0)
    except Exception:
        pass
    return None


def push_batch(records, last_id):
    resp = requests.post(
        f"{CFG['api_url']}/energy-monitoring/ingest",
        json={
            "api_key": CFG["device_key"],
            "device_id": CFG["device_id"],
            "meter_id": CFG["meter_id"],
            "records": records,
            "last_sync_id": last_id,
        },
        timeout=120,
    )
    if resp.status_code == 200:
        return resp.json()
    raise Exception(f"Server {resp.status_code}: {resp.text}")


def mark_synced(max_id):
    try:
        conn = sqlite3.connect(CFG["db_path"])
        conn.execute("UPDATE measurements SET sent=1 WHERE id<=? AND sent=0", (max_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"mark_synced Fehler: {e}")


# ============================ OTA-Update ===================================

def _get_or_create_pi_id() -> str:
    id_file = "/var/lib/messkoffer/pi_id"
    try:
        if os.path.exists(id_file):
            with open(id_file, "r") as f:
                v = f.read().strip()
            if v:
                return v
        os.makedirs(os.path.dirname(id_file), exist_ok=True)
        new_id = str(uuid.uuid4())
        with open(id_file, "w") as f:
            f.write(new_id)
        return new_id
    except Exception:
        return str(uuid.uuid4())


def _self_script_hash() -> str:
    try:
        with open(__file__, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return ""


def _check_and_apply_ota_update():
    base = CFG.get("api_url")
    if not base:
        return False
    pi_id = _get_or_create_pi_id()
    current_hash = _self_script_hash()
    try:
        import socket
        hostname = socket.gethostname()
    except Exception:
        hostname = ""
    try:
        # DB-Status mitschicken (damit der Admin remote sieht wieso noch
        # keine Daten ankommen - z.B. wenn Modbus klappt aber Sync hakt)
        db_rows_total = -1
        db_rows_unsynced = -1
        try:
            db_path = CFG.get("db_path") or ""
            if db_path and os.path.exists(db_path):
                _conn = sqlite3.connect(db_path)
                row = _conn.execute("SELECT COUNT(*), COALESCE(SUM(CASE WHEN sent=0 THEN 1 ELSE 0 END),0) FROM measurements").fetchone()
                _conn.close()
                if row:
                    db_rows_total = int(row[0] or 0)
                    db_rows_unsynced = int(row[1] or 0)
        except Exception as _db_e:
            log.debug(f"DB-Status-Read fehlgeschlagen: {_db_e}")

        params = {
            "pi_id": pi_id,
            "hostname": hostname,
            "hash": current_hash,
            "version": SCRIPT_VERSION,
            "modbus_ok": "1" if _pi_status.get("modbus_ok") else "0",
            "modbus_port": CFG.get("modbus_port") or "",
            "modbus_error": _pi_status.get("modbus_error") or "",
            "db_rows_total": str(db_rows_total) if db_rows_total >= 0 else "",
            "db_rows_unsynced": str(db_rows_unsynced) if db_rows_unsynced >= 0 else "",
            "last_read_ts": _pi_status.get("last_read_ts") or "",
            "last_sync_ts": _pi_status.get("last_sync_ts") or "",
        }
        resp = requests.get(f"{base}/system/ota/pi/messkoffer/check", params=params, timeout=10)
        if resp.status_code != 200:
            return False
        info = resp.json()
        if not info.get("update_available"):
            return False
        log.info(f"OTA: Update verfuegbar (Hash {info.get('file_hash','?')[:12]})")
        resp2 = requests.get(f"{base}/system/ota/pi/messkoffer/download", params={"pi_id": pi_id}, timeout=30)
        if resp2.status_code != 200:
            log.warning(f"OTA-Download Fehler {resp2.status_code}")
            return False
        new_content = resp2.content
        new_hash = hashlib.sha256(new_content).hexdigest()
        expected = info.get("file_hash") or resp2.headers.get("X-Hash", "")
        if expected and new_hash != expected:
            log.warning("OTA-Hash-Mismatch - Update abgebrochen")
            return False
        if len(new_content) < 1000 or b"def main" not in new_content:
            log.warning("OTA: Skript wirkt unvollstaendig - abgebrochen")
            return False
        script_path = os.path.realpath(__file__)
        try:
            import shutil
            shutil.copy2(script_path, script_path + ".bak")
        except Exception:
            pass
        tmp_path = script_path + ".new"
        with open(tmp_path, "wb") as f:
            f.write(new_content)
        os.replace(tmp_path, script_path)
        log.info(f"OTA: Skript aktualisiert ({len(new_content)} Bytes). Beende fuer systemd-Neustart...")
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(0)
    except requests.RequestException as e:
        log.debug(f"OTA-Check nicht erreichbar: {e}")
    except Exception as e:
        log.warning(f"OTA-Update Fehler: {e}")
    return False


def sync_loop():
    """Synchronisiert alle 20 Minuten - oder beim Wiederverbinden wenn vorher
    offline (catchup). Speichert weiter lokal wenn keine Verbindung da ist.
    """
    if not CFG["api_url"] or not CFG["device_key"]:
        log.warning("Sync deaktiviert: api_url oder device_key nicht gesetzt")
        return

    consecutive_errors = 0
    log.info(f"Sync-Thread gestartet (Intervall {CFG['sync_interval']}s = {CFG['sync_interval']//60} Min)")
    last_ota_check = 0
    last_status_heartbeat = 0

    while True:
        try:
            # OTA-Update-Check alle 5 Min (versucht Skript-Update)
            # Status-Heartbeat alle 60 s (sendet modbus_ok + db_rows zum Backend)
            now = time.time()
            if now - last_ota_check > 300:
                try:
                    _check_and_apply_ota_update()
                except Exception as ota_e:
                    log.debug(f"OTA-Check fehlgeschlagen (ignoriert): {ota_e}")
                last_ota_check = now
                last_status_heartbeat = now
            elif now - last_status_heartbeat > 60:
                # Reiner Status-Heartbeat - gleiche URL, aber wenn Hash gleich
                # bleibt der Backend-Aufwand minimal (kein Update wird gepullt).
                try:
                    _check_and_apply_ota_update()
                except Exception:
                    pass
                last_status_heartbeat = now

            last_id = get_last_sync_id()
            if last_id is None:
                consecutive_errors += 1
                delay = min(CFG["retry_delay"] * consecutive_errors, 300)
                if consecutive_errors <= 3 or consecutive_errors % 10 == 0:
                    log.info(f"Portal nicht erreichbar, warte {delay}s (Catch-up sobald online)...")
                time.sleep(delay)
                continue

            # Alles ab last_id schicken (also auch alte Daten die noch offline
            # eingesammelt wurden) - in Batches a sync_batch_size
            while True:
                conn = sqlite3.connect(CFG["db_path"])
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM measurements WHERE id > ? ORDER BY id ASC LIMIT ?",
                    (last_id, CFG["sync_batch_size"]),
                ).fetchall()
                conn.close()
                if not rows:
                    break
                records = [map_to_portal(dict(r)) for r in rows]
                new_last_id = records[-1]["id"]
                result = push_batch(records, new_last_id)
                inserted = result.get("inserted", 0)
                mark_synced(new_last_id)
                last_id = new_last_id
                _pi_status["last_sync_ts"] = datetime.now(timezone.utc).isoformat()
                log.info(f"Sync OK: {inserted} Datensaetze (bis ID {new_last_id})")
                if len(records) < CFG["sync_batch_size"]:
                    break

            consecutive_errors = 0
            time.sleep(CFG["sync_interval"])

        except requests.ConnectionError:
            consecutive_errors += 1
            delay = min(CFG["retry_delay"] * consecutive_errors, 300)
            time.sleep(delay)
        except Exception as e:
            consecutive_errors += 1
            delay = min(CFG["retry_delay"] * consecutive_errors, 300)
            log.error(f"Sync Fehler: {e}")
            time.sleep(delay)


# =========================================================================
# Hauptprogramm
# =========================================================================

def main():
    # Selbsttest-Modus: einmal lesen, Rohwerte ausgeben, beenden.
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        print("=== Messkoffer Modbus-Selbsttest ===")
        print(f"  Skript-Version: {SCRIPT_VERSION}")
        print(f"  Port:           {CFG['modbus_port']}")
        print(f"  Baudrate:       {CFG['modbus_baudrate']}")
        print(f"  Slave-ID:       {CFG['modbus_slave_id']}")
        if not MODBUS_AVAILABLE:
            print("  FEHLER: minimalmodbus nicht installiert!")
            sys.exit(2)
        m = read_rayleigh()
        if not m:
            print("  FEHLER: Modbus-Read fehlgeschlagen.")
            print("  Pruefe: ls -la /dev/rayleigh, RS485 A/B Anschluss, Slave-ID am Geraet")
            sys.exit(3)
        print("  --- Werte ---")
        for k, v in m.items():
            if v is None:
                print(f"  {k:20s} = None")
            elif isinstance(v, float):
                print(f"  {k:20s} = {v:.3f}")
            else:
                print(f"  {k:20s} = {v}")
        sys.exit(0)

    log.info("=" * 60)
    log.info(f"  Messkoffer Logger v{SCRIPT_VERSION} - Eventenergie Portal")
    log.info("  Hardware: Waveshare USB-RS485 -> Rayleigh RI-F100-C")
    log.info("=" * 60)
    log.info(f"  Modbus:      {CFG['modbus_port']} @ {CFG['modbus_baudrate']} "
             f"8{CFG['modbus_parity']}{CFG['modbus_stopbits']} Slave={CFG['modbus_slave_id']}")
    log.info(f"  DB:          {CFG['db_path']}")
    log.info(f"  Max. DB:     {CFG['max_db_size_gb']} GB")
    log.info(f"  Polling:     {CFG['log_interval']}s")
    log.info(f"  Sync:        alle {CFG['sync_interval']}s ({CFG['sync_interval']//60} Min)")
    log.info(f"  Server:      {CFG['api_url'] or '(kein Sync)'}")
    log.info(f"  Device-ID:   {CFG['device_id'] or '(nicht gesetzt)'}")
    log.info(f"  GPS:         {'verfuegbar' if GPS_AVAILABLE else 'nicht installiert'}")
    log.info(f"  Modbus-lib:  {'verfuegbar' if MODBUS_AVAILABLE else 'FEHLT (apt install python3-minimalmodbus)'}")
    log.info("=" * 60)

    if not MODBUS_AVAILABLE:
        log.error("minimalmodbus/pyserial nicht installiert. Abbruch.")
        sys.exit(1)

    init_db()

    t_gps = threading.Thread(target=gps_thread, daemon=True)
    t_gps.start()

    t_sync = threading.Thread(target=sync_loop, daemon=True)
    t_sync.start()

    logger_loop()


if __name__ == "__main__":
    main()
