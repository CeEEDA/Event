#!/usr/bin/env python3
"""
Tankbeleg Pi - Eventenergie Portal
====================================
Emuliert einen Drucker (Epson TM-U295) ueber serielle Schnittstelle,
parst ESC/POS Belegdaten und synchronisiert sie mit dem Portal.

Hardware:
  - Raspberry Pi mit Touchscreen
  - USB-zu-RS232 Adapter (z.B. FTDI)
  - Optional: GPS-Modul (USB oder UART) via gpsd

Voraussetzungen:
  sudo apt install python3-pip gpsd gpsd-clients python3-gps
  pip3 install pyserial requests

Konfiguration:
  Datei /etc/tankbeleg_pi.conf erstellen oder Setup-Skript verwenden.

Status pruefen:
  sudo systemctl status tankbeleg_pi
  sudo journalctl -u tankbeleg_pi -f
"""

import serial
import time
import json
import logging
import os
import sys
import re
import sqlite3
import uuid
import configparser
from pathlib import Path
from datetime import datetime, timezone

import requests


# ====== Konfiguration ======

DEFAULT_CONF = {
    "api_url": "",
    "serial_port": "/dev/ttyUSB0",
    "serial_baud": 9600,
    "serial_bytesize": 8,
    "serial_parity": "N",
    "serial_stopbits": 1,
    "db_path": "/var/lib/tankbeleg/tankbeleg.sqlite",
    "sync_interval": 60,
    "retry_delay": 30,
    "gps_enabled": "true",
    "gps_host": "127.0.0.1",
    "gps_port": 2947,
    "fahrer_name": "",
    # Sening MultiFlow poll response. 0x00 = "all flags OK / paper present".
    # If MultiFlow still reports 'paper out', try 0x01, 0x10, 0x12, 0x7F.
    # Override via /etc/tankbeleg_pi.conf key 'sening_reply_byte' (hex, e.g. 0x00).
    "sening_reply_byte": "0x00",
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
            # Numerische Werte konvertieren
            conf["serial_baud"] = int(conf["serial_baud"])
            conf["serial_bytesize"] = int(conf["serial_bytesize"])
            conf["serial_stopbits"] = int(conf["serial_stopbits"])
            conf["sync_interval"] = int(conf["sync_interval"])
            conf["retry_delay"] = int(conf["retry_delay"])
            conf["gps_port"] = int(conf["gps_port"])

    # Env overrides
    conf["api_url"] = os.environ.get("TANKBELEG_API_URL", conf["api_url"])
    conf["serial_port"] = os.environ.get("TANKBELEG_SERIAL_PORT", conf["serial_port"])
    conf["fahrer_name"] = os.environ.get("TANKBELEG_FAHRER", conf["fahrer_name"])

    return conf


# ====== Logging ======

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("tankbeleg_pi")


# ====== ESC/POS Parser ======

# Regex fuer Epson TM-U295 Belegdaten
RE_ZAEHLER_NR = re.compile(r"\*?\s*Zaehler-Nr\.?\s*[:=]\s*(\d+)\s*\*?", re.IGNORECASE)
RE_BELEG_NR = re.compile(r"\*?\s*Beleg-Nr\.?\s*[:=]\s*(\d+)\s*\*?", re.IGNORECASE)
RE_DATUM = re.compile(r"Ab[sg]abe-Datum\s*[:=]\s*(\d{2}\.\d{2}\.\d{4})", re.IGNORECASE)
RE_START = re.compile(r"Ab[sg]abe-Start\s*[:=]\s*(\d{2}:\d{2}:\d{2})", re.IGNORECASE)
RE_ENDE = re.compile(r"Ab[sg]abe-Ende\s*[:=]\s*(\d{2}:\d{2}:\d{2})", re.IGNORECASE)
RE_ZAEHLER_VOR = re.compile(r"\*?\s*Zaehler\s+vor\s+Start\s*[:=]?\s*(\d+)\s*L?\s*\*?", re.IGNORECASE)
RE_MENGE = re.compile(r"Menge\s+bei\s+15\s*.?C\s+(\d+)\s*L", re.IGNORECASE)
RE_FUEL_TYPE = re.compile(r"\*\s*(HEL\s+schwefelarm|Diesel|HVO)\s*\*?\s*$", re.IGNORECASE | re.MULTILINE)

# ESC/POS Steuerzeichen entfernen
ESCPOS_PATTERN = re.compile(
    rb'\x1b[@-~]'            # ESC + Byte
    rb'|\x1b\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]'  # CSI Sequenzen
    rb'|\x1b[()][A-Z0-9]'   # Zeichensatz-Auswahl
    rb'|\x1b\x21.'          # Print Mode
    rb'|\x1b\x24..'         # Absolute Position
    rb'|\x1b\x2a...'        # Bit Image Mode (min)
    rb'|\x1b\x61.'          # Justification
    rb'|\x1b\x45.'          # Emphasis (bold)
    rb'|\x1b\x47.'          # Double-strike
    rb'|\x1b\x4d.'          # Font selection
    rb'|\x1b\x56.'          # Turn 90° CW rotation
    rb'|\x1b\x74.'          # Character code table
    rb'|\x0e'               # SO - double width
    rb'|\x0f'               # SI - condensed
    rb'|\x10'               # DLE
    rb'|\x12'               # DC2
    rb'|\x14'               # DC4 - cancel double width
    rb'|\x18'               # CAN - clear buffer
)


def strip_escpos(data: bytes) -> str:
    """Entfernt ESC/POS Steuerzeichen und gibt reinen Text zurueck."""
    # Steuerzeichen entfernen
    cleaned = ESCPOS_PATTERN.sub(b'', data)
    # Verbleibende Steuerzeichen (< 0x20) durch Newlines ersetzen, ausser Tab
    result = bytearray()
    for b in cleaned:
        if b == 0x09:  # Tab
            result.extend(b'    ')
        elif b == 0x0A or b == 0x0D:  # LF, CR
            result.append(0x0A)
        elif b < 0x20:
            continue  # Andere Steuerzeichen ignorieren
        else:
            result.append(b)
    # Versuche mehrere Encodings
    for enc in ['cp437', 'cp850', 'latin-1', 'utf-8']:
        try:
            return bytes(result).decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return bytes(result).decode('latin-1', errors='replace')


def parse_receipt(text: str) -> dict:
    """Parst einen Tankbeleg-Text und extrahiert die Felder."""
    receipt = {
        "zaehler_nr": None,
        "beleg_nr": None,
        "datum": None,
        "abgabe_start": None,
        "abgabe_ende": None,
        "zaehler_vor_start": None,
        "fuel_type": None,
        "menge_liter": None,
        "raw_text": text,
    }

    m = RE_ZAEHLER_NR.search(text)
    if m:
        receipt["zaehler_nr"] = m.group(1)

    m = RE_BELEG_NR.search(text)
    if m:
        receipt["beleg_nr"] = m.group(1)

    m = RE_DATUM.search(text)
    if m:
        receipt["datum"] = m.group(1)

    m = RE_START.search(text)
    if m:
        receipt["abgabe_start"] = m.group(1)

    m = RE_ENDE.search(text)
    if m:
        receipt["abgabe_ende"] = m.group(1)

    m = RE_ZAEHLER_VOR.search(text)
    if m:
        receipt["zaehler_vor_start"] = int(m.group(1))

    m = RE_FUEL_TYPE.search(text)
    if m:
        fuel_raw = m.group(1).strip()
        # Mapping auf Backend-Werte
        fuel_map = {
            "hel schwefelarm": "heizoel_leicht",
            "diesel": "diesel",
            "hvo": "hvo",
        }
        receipt["fuel_type"] = fuel_map.get(fuel_raw.lower(), "diesel")

    m = RE_MENGE.search(text)
    if m:
        receipt["menge_liter"] = float(m.group(1))

    return receipt


def is_complete_receipt(receipt: dict) -> bool:
    """Prueft ob alle Pflichtfelder eines Belegs vorhanden sind."""
    required = ["beleg_nr", "datum", "menge_liter"]
    return all(receipt.get(f) is not None for f in required)


# ====== GPS ======

def get_gps_position(host="127.0.0.1", port=2947, timeout=5):
    """Liest die aktuelle GPS-Position von gpsd.
    Gibt (lat, lon) oder (None, None) zurueck."""
    try:
        from gps import gps, WATCH_ENABLE, WATCH_NEWSTYLE
        session = gps(host=host, port=port, mode=WATCH_ENABLE | WATCH_NEWSTYLE)

        deadline = time.time() + timeout
        while time.time() < deadline:
            report = session.next()
            if report.get("class") == "TPV":
                lat = report.get("lat")
                lon = report.get("lon")
                if lat is not None and lon is not None:
                    session.close()
                    return float(lat), float(lon)
        session.close()
    except ImportError:
        log.debug("GPS: python3-gps nicht installiert, ueberspringe GPS")
    except Exception as e:
        log.debug(f"GPS: Fehler beim Lesen: {e}")

    return None, None


# ====== Lokale SQLite Datenbank ======

def init_db(db_path):
    """Erstellt die lokale SQLite-Datenbank fuer Zwischenspeicherung."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            local_id TEXT UNIQUE NOT NULL,
            zaehler_nr TEXT,
            beleg_nr TEXT,
            datum TEXT,
            zeit TEXT,
            abgabe_start TEXT,
            abgabe_ende TEXT,
            zaehler_vor_start REAL,
            fuel_type TEXT,
            menge_liter REAL,
            gps_lat REAL,
            gps_lon REAL,
            fahrer TEXT,
            order_pk TEXT,
            order_name TEXT,
            notes TEXT DEFAULT '',
            raw_text TEXT,
            synced INTEGER DEFAULT 0,
            assigned INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_synced ON receipts(synced)")
    # Migrate: add new columns if missing
    try:
        conn.execute("ALTER TABLE receipts ADD COLUMN order_pk TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE receipts ADD COLUMN order_name TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE receipts ADD COLUMN notes TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE receipts ADD COLUMN assigned INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()
    log.info(f"Datenbank initialisiert: {db_path}")


def store_receipt(db_path, receipt, gps_lat, gps_lon, fahrer):
    """Speichert einen geparsten Beleg in der lokalen DB."""
    local_id = str(uuid.uuid4())
    # Zeit aus abgabe_start oder aktueller Zeit
    zeit = receipt.get("abgabe_start", datetime.now().strftime("%H:%M:%S"))

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            INSERT INTO receipts (local_id, zaehler_nr, beleg_nr, datum, zeit,
                abgabe_start, abgabe_ende, zaehler_vor_start,
                fuel_type, menge_liter, gps_lat, gps_lon, fahrer, raw_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            local_id,
            receipt.get("zaehler_nr"),
            receipt.get("beleg_nr"),
            receipt.get("datum"),
            zeit,
            receipt.get("abgabe_start"),
            receipt.get("abgabe_ende"),
            receipt.get("zaehler_vor_start"),
            receipt.get("fuel_type"),
            receipt.get("menge_liter"),
            gps_lat,
            gps_lon,
            fahrer,
            receipt.get("raw_text", ""),
        ))
        conn.commit()
        log.info(f"Beleg gespeichert: Nr. {receipt.get('beleg_nr')}, {receipt.get('menge_liter')} L {receipt.get('fuel_type')}")
    except sqlite3.IntegrityError:
        log.warning(f"Beleg bereits vorhanden: {local_id}")
    finally:
        conn.close()

    return local_id


def get_unsynced(db_path, limit=50):
    """Holt ungesyncte Belege aus der lokalen DB."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM receipts WHERE synced=0 ORDER BY id ASC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_synced(db_path, local_ids):
    """Markiert Belege als synchronisiert."""
    if not local_ids:
        return
    conn = sqlite3.connect(db_path)
    for lid in local_ids:
        conn.execute("UPDATE receipts SET synced=1 WHERE local_id=?", (lid,))
    conn.commit()
    conn.close()


def get_stats(db_path):
    """Gibt Statistiken ueber die lokale DB zurueck."""
    conn = sqlite3.connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
    unsynced = conn.execute("SELECT COUNT(*) FROM receipts WHERE synced=0").fetchone()[0]
    conn.close()
    return {"total": total, "unsynced": unsynced}


# ====== Portal Sync ======

def sync_to_portal(conf):
    """Sendet ungesyncte Belege an das Portal."""
    unsynced = get_unsynced(conf["db_path"])
    if not unsynced:
        return 0

    # Konvertiere in das API-Format
    api_receipts = []
    local_ids = []
    for row in unsynced:
        # Datum von DD.MM.YYYY in YYYY-MM-DD konvertieren
        datum = row.get("datum", "")
        if datum and "." in datum:
            parts = datum.split(".")
            if len(parts) == 3:
                datum = f"{parts[2]}-{parts[1]}-{parts[0]}"

        api_receipt = {
            "fuel_type": row.get("fuel_type") or "diesel",
            "quantity_liters": row.get("menge_liter") or 0,
            "date": datum,
            "time": row.get("zeit") or "",
            "beleg_nr": row.get("beleg_nr") or "",
            "abgabe_start": row.get("abgabe_start"),
            "abgabe_ende": row.get("abgabe_ende"),
            "zaehler_vor_start": row.get("zaehler_vor_start"),
            "fahrer": row.get("fahrer") or "",
            "gps_lat": row.get("gps_lat"),
            "gps_lng": row.get("gps_lon"),
            "pi_local_id": row.get("local_id"),
            "raw_receipt_data": row.get("raw_text") or "",
            "order_pk": row.get("order_pk") or None,
            "order_name": row.get("order_name") or "",
            "notes": row.get("notes") or f"Pi-Sync {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        }
        api_receipts.append(api_receipt)
        local_ids.append(row["local_id"])

    try:
        resp = requests.post(
            f"{conf['api_url']}/api/fuel-receipts/sync",
            json=api_receipts,
            timeout=30,
        )
        if resp.status_code == 200:
            result = resp.json()
            created = result.get("created", 0)
            skipped = result.get("skipped", 0)
            mark_synced(conf["db_path"], local_ids)
            log.info(f"Sync OK: {created} neu, {skipped} uebersprungen")
            return created
        else:
            log.warning(f"Sync Fehler {resp.status_code}: {resp.text[:200]}")
    except requests.ConnectionError:
        log.warning("Portal nicht erreichbar, Belege bleiben lokal gepuffert")
    except Exception as e:
        log.error(f"Sync Fehler: {e}")

    return 0


# ====== Serielle Schnittstelle ======

class SerialReceiptReader:
    """Liest serielle Daten und erkennt vollstaendige Belege."""

    def __init__(self, port, baud=9600, bytesize=8, parity='N', stopbits=1, sening_reply_byte=0x00):
        self.port = port
        self.baud = baud
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.sening_reply_byte = sening_reply_byte
        self.ser = None
        self.buffer = bytearray()
        # Holds incomplete status-query prefixes across chunked serial reads
        # so we don't accidentally leak them into the receipt buffer.
        self.pending_prefix = bytearray()
        # Timeout: wenn X Sekunden keine Daten kommen, ist der Beleg komplett
        self.receipt_timeout = 3.0
        self.last_data_time = 0

    def connect(self):
        """Oeffnet die serielle Verbindung."""
        parity_map = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}
        stopbits_map = {1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}

        # dsrdtr=False: Sening MultiFlow uses 3-wire null-modem cable (no DSR/DTR handshake).
        # With dsrdtr=True pyserial blocks writes while DSR is low, which prevents status replies.
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baud,
            bytesize=self.bytesize,
            parity=parity_map.get(self.parity, serial.PARITY_NONE),
            stopbits=stopbits_map.get(self.stopbits, serial.STOPBITS_ONE),
            timeout=0.1,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        # DTR und RTS dauerhaft auf HIGH (MultiFlow erwartet beide Handshake-Leitungen)
        try:
            self.ser.dtr = True
            self.ser.rts = True
        except (OSError, IOError):
            log.debug("DTR/RTS nicht unterstuetzt (z.B. virtuelle Ports)")
        log.info(f"Serielle Verbindung geoeffnet: {self.port} @ {self.baud}")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def read_receipt(self):
        """Liest Daten bis ein vollstaendiger Beleg erkannt wird.
        Beantwortet dabei Epson TM-U295 Status-Queries inline, damit die
        FMC MultiFlow den Pi als 'Drucker online' erkennt.

        Gibt (raw_bytes, parsed_text) zurueck oder (None, None) wenn kein Beleg."""
        if not self.ser or not self.ser.is_open:
            return None, None

        # Handshake-Leitungen periodisch loggen (alle 5 Sek)
        self._dump_handshake_state()

        while True:
            data = self.ser.read(256)
            if data:
                log.info(f"SERIAL RX ({len(data)} bytes): {data.hex(' ')}")
                # Status-Queries INLINE beantworten, aus dem Print-Stream entfernen
                data = self._handle_status_queries(data)
                if data:
                    self.buffer.extend(data)
                    self.last_data_time = time.time()
            elif self.buffer and (time.time() - self.last_data_time) > self.receipt_timeout:
                # Timeout - Buffer verarbeiten
                raw = bytes(self.buffer)
                self.buffer.clear()
                text = strip_escpos(raw)
                return raw, text
            elif not self.buffer:
                # Kein Buffer, nichts zu tun
                return None, None
            else:
                # Buffer vorhanden, noch kein Timeout
                time.sleep(0.05)

    def _dump_handshake_state(self):
        """Log current RS232 control line state (DSR/CTS/DTR/RTS) once every 5 seconds."""
        now = time.time()
        if not hasattr(self, "_last_handshake_log") or (now - self._last_handshake_log) > 5:
            self._last_handshake_log = now
            try:
                log.info(
                    "HANDSHAKE DTR=%s RTS=%s | DSR=%s CTS=%s CD=%s RI=%s",
                    getattr(self.ser, "dtr", "?"),
                    getattr(self.ser, "rts", "?"),
                    self.ser.dsr if hasattr(self.ser, "dsr") else "?",
                    self.ser.cts if hasattr(self.ser, "cts") else "?",
                    self.ser.cd if hasattr(self.ser, "cd") else "?",
                    self.ser.ri if hasattr(self.ser, "ri") else "?",
                )
            except Exception as e:
                log.debug(f"Handshake-Status nicht lesbar: {e}")

    def _handle_status_queries(self, data: bytes) -> bytes:
        """Parse incoming bytes for Epson DLE EOT status queries and respond to them.
        Returns the bytes WITHOUT the status queries (so they don't land in the receipt).

        Epson TM-U295 status bytes (respond 'online, no errors, paper OK'):
          DLE EOT n  (0x10 0x04 n)  n = 1..4
            n=1: printer status   -> 0x12  (online, drawer OK, cover closed, no feed)
            n=2: offline status   -> 0x12  (no offline conditions)
            n=3: error status     -> 0x12  (no errors, no auto-recoverable error)
            n=4: paper sensor     -> 0x12  (paper OK / slip inserted)

        Also handles ESC/POS Real-time status requests.
        """
        STATUS_OK = {1: 0x12, 2: 0x12, 3: 0x12, 4: 0x12}

        # Prepend any leftover status-query prefix from a previous read.
        if self.pending_prefix:
            data = bytes(self.pending_prefix) + data
            self.pending_prefix = bytearray()

        out = bytearray()
        i = 0
        while i < len(data):
            b = data[i]
            remaining = len(data) - i

            # Partial status-query prefixes at the tail of the chunk: buffer them
            # for the next read instead of leaking into the receipt buffer.
            if b == 0x10 and remaining < 3 and (remaining < 2 or data[i + 1] in (0x04, 0x05)):
                self.pending_prefix.extend(data[i:])
                return bytes(out)
            if b == 0x1B and remaining < 3 and (remaining < 2 or data[i + 1] == 0xB3):
                self.pending_prefix.extend(data[i:])
                return bytes(out)

            # DLE EOT n (0x10 0x04 n) - Epson printer status query
            if b == 0x10 and remaining >= 3 and data[i + 1] == 0x04:
                n = data[i + 2]
                if n in STATUS_OK:
                    try:
                        self.ser.write(bytes([STATUS_OK[n]]))
                        self.ser.flush()
                        log.debug(f"Status-Query DLE EOT {n} -> 0x{STATUS_OK[n]:02X}")
                    except (OSError, IOError) as e:
                        log.warning(f"Status-Antwort fehlgeschlagen: {e}")
                    i += 3
                    continue
            # Check for DLE ENQ n (real-time status request, 0x10 0x05 n)
            if b == 0x10 and remaining >= 3 and data[i + 1] == 0x05:
                # Respond with 'no error' status byte
                try:
                    self.ser.write(bytes([0x00]))
                    self.ser.flush()
                    log.debug("Realtime ENQ -> 0x00 (ok)")
                except (OSError, IOError):
                    pass
                i += 3
                continue
            # Sening MultiFlow proprietary poll:  ESC (0x1B) 0xB3 <n>
            # Observed every ~550ms as '1b b3 ff'. MultiFlow waits for a status reply
            # before it will transmit the slip print job. The reply byte controls whether
            # MultiFlow thinks the printer is ready (paper present) or reports an error.
            # Configurable via /etc/tankbeleg_pi.conf key 'sening_reply_byte'.
            if b == 0x1B and remaining >= 3 and data[i + 1] == 0xB3:
                zone = data[i + 2]
                try:
                    self.ser.write(bytes([self.sening_reply_byte]))
                    self.ser.flush()
                    log.info(f"Sening-Poll ESC B3 {zone:02X} -> 0x{self.sening_reply_byte:02X}")
                except (OSError, IOError) as e:
                    log.warning(f"Sening-Reply fehlgeschlagen: {e}")
                i += 3
                continue
            out.append(b)
            i += 1
        return bytes(out)


# ====== Hauptprogramm ======

def main():
    conf = load_config()

    log.info("=" * 60)
    log.info("  Tankbeleg Pi - Eventenergie Portal")
    log.info("  Epson TM-U295 Drucker-Emulator")
    log.info("=" * 60)
    log.info(f"  Server:        {conf['api_url']}")
    log.info(f"  Seriell:       {conf['serial_port']} @ {conf['serial_baud']}")
    log.info(f"  GPS:           {'aktiv' if conf['gps_enabled'].lower() == 'true' else 'deaktiviert'}")
    log.info(f"  Fahrer:        {conf['fahrer_name'] or '(nicht gesetzt)'}")
    log.info(f"  Datenbank:     {conf['db_path']}")
    log.info(f"  Sync-Intervall: {conf['sync_interval']}s")
    log.info("=" * 60)

    # Validierung
    errors = []
    if not conf["api_url"]:
        log.warning("api_url nicht gesetzt - Belege werden nur lokal gespeichert")
    if not Path(conf["serial_port"]).exists():
        log.warning(f"Serieller Port {conf['serial_port']} nicht gefunden")

    # DB initialisieren
    init_db(conf["db_path"])

    # Serielle Verbindung
    try:
        reply_byte = int(str(conf.get("sening_reply_byte", "0x00")), 0)
    except (ValueError, TypeError):
        reply_byte = 0x00
    log.info(f"  Sening-Reply: 0x{reply_byte:02X}")
    reader = SerialReceiptReader(
        port=conf["serial_port"],
        baud=conf["serial_baud"],
        bytesize=conf["serial_bytesize"],
        parity=conf["serial_parity"],
        stopbits=conf["serial_stopbits"],
        sening_reply_byte=reply_byte,
    )

    try:
        reader.connect()
    except Exception as e:
        log.error(f"Serielle Verbindung fehlgeschlagen: {e}")
        log.info("Starte im Offline-Modus (nur Sync bereits vorhandener Belege)")
        reader = None

    last_sync_time = 0
    consecutive_errors = 0

    log.info("Warte auf Belegdaten...")

    while True:
        try:
            # Serielle Daten lesen
            if reader:
                raw, text = reader.read_receipt()
                if text:
                    log.info(f"Empfangene Daten ({len(raw)} Bytes)")
                    log.debug(f"Text:\n{text}")

                    receipt = parse_receipt(text)

                    if is_complete_receipt(receipt):
                        # GPS Position erfassen
                        gps_lat, gps_lon = None, None
                        if conf["gps_enabled"].lower() == "true":
                            gps_lat, gps_lon = get_gps_position(
                                conf["gps_host"], int(conf["gps_port"])
                            )
                            if gps_lat:
                                log.info(f"GPS: {gps_lat:.6f}, {gps_lon:.6f}")

                        # Lokal speichern
                        store_receipt(
                            conf["db_path"],
                            receipt,
                            gps_lat,
                            gps_lon,
                            conf["fahrer_name"],
                        )
                        consecutive_errors = 0
                    else:
                        missing = [f for f in ["beleg_nr", "datum", "menge_liter"]
                                   if receipt.get(f) is None]
                        log.warning(f"Unvollstaendiger Beleg, fehlende Felder: {', '.join(missing)}")
                        log.debug(f"Geparste Felder: {receipt}")

            # Periodisch zum Portal syncen
            now = time.time()
            if conf["api_url"] and (now - last_sync_time) >= int(conf["sync_interval"]):
                stats = get_stats(conf["db_path"])
                if stats["unsynced"] > 0:
                    log.info(f"Starte Sync ({stats['unsynced']} ungesyncte Belege)...")
                    synced = sync_to_portal(conf)
                last_sync_time = now

        except KeyboardInterrupt:
            log.info("Beendet durch Benutzer")
            break
        except serial.SerialException as e:
            consecutive_errors += 1
            log.error(f"Serieller Fehler: {e}")
            if consecutive_errors > 5:
                delay = min(int(conf["retry_delay"]) * 2, 300)
                log.warning(f"Zu viele Fehler, warte {delay}s...")
                time.sleep(delay)
            else:
                time.sleep(2)
            # Versuche Reconnect
            try:
                if reader:
                    reader.close()
                    reader.connect()
                    log.info("Serielle Verbindung wiederhergestellt")
            except Exception:
                pass
        except Exception as e:
            consecutive_errors += 1
            log.error(f"Fehler: {e}")
            time.sleep(1)

        time.sleep(0.1)

    # Aufraumen
    if reader:
        reader.close()
    log.info("Tankbeleg Pi beendet")


if __name__ == "__main__":
    main()
