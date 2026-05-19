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

Changelog:
  v1.7.9  - Unvollstaendige Belege werden TROTZDEM in DB gespeichert (als
            stub mit needs_review=True). Vorher gingen die Roh-Bytes verloren
            wenn der Parser beleg_nr/datum/menge nicht fand -> Parser konnte
            nicht nachtraeglich gefixt werden weil keine Beweisdaten da waren.
  v1.7.8  - TM-U295-Spec-Konform: Status-Antworten gemaess offizieller Epson
            TM-U295 Spec ueberprueft. Korrekturen:
              - DLE EOT n=4 entfernt (gibt es im TM-U295 nicht; war TM-U220),
                stattdessen n=5 (Slip Paper Status) hinzugefuegt.
              - ESC u jetzt 3 Bytes (ESC u 0 = peripheral status, drawer).
              - ESC c 3 / ESC c 4 (4-Byte Paper-Sensor-Konfig) werden silent
                konsumiert damit sie nicht in den Beleg-Buffer landen.
              - sening_reply_byte Default von 0x00 -> 0x12 (TM-U295-konformer
                "Online + Paper OK", Bit1+4 fixed ON laut Spec).
              - Erweiterte Logs mit Spec-Referenzen.
  v1.7.7  - dsrdtr=False (zurueck): Sening MultiFlow nutzt 3-Wire Null-Modem
            Kabel und treibt DSR/CTS NIE. Bewiesen durch Live-Diagnose.
  v1.7.6  - Live-Raw-Stream RX/TX an /api/system/tankwagen/raw-stream/push.
  v1.7.5  - Hardware-Handshake (dsrdtr=True) Versuch + FTDI-Latency-Timer
            auf 1ms (FIFO-Overrun-Fix).
  v1.7.4  - Timestamp-basierter Buffer-Flush.
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
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover - Pi laeuft mind. Py3.9
    ZoneInfo = None  # type: ignore

import requests


# Skript-Version - wird bei jedem OTA-Check zum Portal gemeldet, damit Admins
# in der Geraete-Uebersicht sehen ob ein Pi noch eine alte Version laeuft.
SCRIPT_VERSION = "1.7.17"

# Zeitzone fuer Belegzeitstempel. Der Pi laeuft systemd-seitig oft auf UTC, der
# Sening-Tankwagen und der Disponent denken aber in lokaler Zeit. Wir erzwingen
# darum 'Europe/Berlin' fuer alle datum/abgabe_*-Felder, damit weder Winter-
# noch Sommerzeit-Sprung zu -1h-/-2h-Verschiebungen auf dem Beleg fuehrt.
BERLIN_TZ = ZoneInfo("Europe/Berlin") if ZoneInfo else None


def now_berlin() -> datetime:
    """Aktuelle Zeit in Europe/Berlin (CET/CEST)."""
    if BERLIN_TZ is not None:
        return datetime.now(BERLIN_TZ)
    # Fallback ohne zoneinfo: nehme Lokalzeit des Pi
    return datetime.now()

# Cloudflare blockt User-Agent "Python-urllib/X.Y" hart (Error 1010). Wir setzen
# einen sprechenden UA, der eindeutig als Pi erkennbar ist und gleichzeitig nicht
# auf der CF-Default-Bot-Liste steht.
PI_HEADERS = {"User-Agent": f"TankbelegPi/{SCRIPT_VERSION} (eventenergie-deutschland)"}


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
    # Sening MultiFlow proprietary poll response.
    # Default 0x00 (empirisch validiert mit Sening Firmware 3.56[3.57]DE).
    # 0x00 ist KORREKT obwohl die TM-U295-Spec fuer DLE EOT 0x12 verlangt -
    # ESC B3 ist nicht in der TM-U295-Spec, sondern proprietaer Sening.
    # Test 12:45:31 mit 0x00 -> 237-Byte-Druckjob kam durch.
    # Test mit 0x12         -> "Drucker antwortet nicht".
    # Override via /etc/tankbeleg_pi.conf key 'sening_reply_byte' (hex).
    "sening_reply_byte": "0x00",
    # FTDI Latency-Timer in Millisekunden. Standard im Linux-Kernel ist 16 ms,
    # was zusammen mit dem 16-Byte UART-FIFO bei langen Sening-Belegen zum
    # Verlust der letzten Ziffer fuehrt (z.B. 1316 L -> 13 L). Wert 1 ms
    # leert den FIFO 16x schneller -> kein Overrun mehr. Bei nicht-FTDI
    # Adaptern wird der Wert ignoriert (nur Log-Hinweis).
    "ftdi_latency_ms": 1,
    # Zaehler-Nr. ist fest und koennte nicht 100% aus Bitmap gelesen werden.
    # Wenn der Parser nur ein Praefix erkennt (z.B. '1146'), wird die hier
    # hinterlegte vollstaendige Nummer genommen (z.B. '11461').
    "fixed_zaehler_nr": "",
    # Beleg-Nr laeuft in der MultiFlow hoch, wird aber als Bitmap gedruckt
    # (letzte 3 Ziffern unlesbar). Wir fuehren einen eigenen Counter ab dem
    # hier hinterlegten Startwert. Bei jedem Beleg +1.
    "beleg_nr_start": "",
    # Abgabezeit-Heuristik (da Minuten aus Bitmap unlesbar):
    # Ende = Pi-Uhrzeit bei Empfang, Start = Ende - (Liter * 0.5 s + 420 s).
    # Lineare Anpassung aus zwei Live-Messungen am Tankwagen (07.05.2026):
    #   104 L in  8 min (480 s) und 1731 L in 20 min (1200 s)
    # -> ~0.5 sec/L Pumpenrate, ~420 sec (7 min) Einrichtung/Anschluss.
    "abgabe_zeit_pro_liter_sek": 0.5,
    "abgabe_zeit_einrichtung_sek": 420,
    # Default-Kraftstoff wenn der Sening-Parser den Typ nicht erkennen kann
    # (Sening druckt "*HEL schwefelarm*" oft als Bitmap). Der Truck laedt in
    # der Regel monatelang nur ein Produkt, daher ist ein Deployment-Default
    # deutlich zuverlaessiger als Rueckfall auf "diesel" - der Wert landet sonst
    # silent falsch im Portal. Erlaubte Werte: "", "heizoel_leicht", "diesel", "hvo".
    # Default = "heizoel_leicht" weil der Tankwagen aktuell ausschliesslich HEL
    # schwefelarm ausliefert. Bei Produktwechsel ueber /etc/tankbeleg_pi.conf
    # umstellen ODER per Pi-Kiosk-UI fuer die Schicht ueberschreiben.
    "default_fuel_type": "heizoel_leicht",
    # Live Raw-Stream zum Backend. Wenn 'true', pusht der Pi alle empfangenen
    # UND gesendeten Bytes (RX/TX) batched in den Tankwagen-Raw-Stream-Endpoint
    # damit man im Portal live mitlesen kann was der Sening sendet und was der
    # Pi antwortet. Default AUS (Datenschutz/Bandbreite); fuer Test-Pis einschalten.
    "raw_stream_enabled": "false",
    # Batch-Flush-Intervall fuer den Raw-Stream. Kuerzer = naeher an Echtzeit
    # aber mehr HTTP-Overhead. 1.5 s ist ein guter Kompromiss bei 9600 Baud.
    "raw_stream_flush_sek": 1.5,
    # Maximale Chunks pro Push - schuetzt vor Endlos-Wachstum des Buffers wenn
    # das Backend mal nicht erreichbar ist.
    "raw_stream_max_batch": 200,
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
            try:
                conf["ftdi_latency_ms"] = int(conf["ftdi_latency_ms"])
            except (ValueError, TypeError):
                conf["ftdi_latency_ms"] = 1

    # Env overrides
    conf["api_url"] = os.environ.get("TANKBELEG_API_URL", conf["api_url"])
    conf["serial_port"] = os.environ.get("TANKBELEG_SERIAL_PORT", conf["serial_port"])
    conf["fahrer_name"] = os.environ.get("TANKBELEG_FAHRER", conf["fahrer_name"])

    return conf


def _api_base(conf):
    """Normalisiert die api_url: haengt /api genau einmal an.

    Erlaubt beide Schreibweisen in /etc/tankbeleg_pi.conf:
      api_url = https://eventenergie.app
      api_url = https://eventenergie.app/api
    """
    url = (conf.get("api_url") or "").rstrip("/")
    if not url:
        return ""
    if url.endswith("/api"):
        return url
    return url + "/api"


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


# ====== Beleg-Nr Counter (persistent in SQLite) ======

def get_next_beleg_nr(db_path: str, start_value: int) -> int:
    """Liefert die naechste Beleg-Nr. Nimmt Maximum aus DB+1 oder Startwert."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("SELECT MAX(CAST(beleg_nr AS INTEGER)) FROM receipts WHERE beleg_nr GLOB '[0-9]*'")
        row = cur.fetchone()
        max_in_db = row[0] if row and row[0] else 0
    except sqlite3.OperationalError:
        max_in_db = 0
    finally:
        conn.close()
    return max(max_in_db + 1, start_value)


# ====== Sening MultiFlow Grafik-Parser ======
# Die Sening MultiFlow druckt fett-markierte Zeichen als Bit-Image,
# normale Zeichen als ASCII-Text. Dadurch sind z.B. "Abgabe-Datum" als
# "bgabek?d?t" und die letzte Ziffer jeder Zahl unleserlich.

def strip_sening_escapes(data: bytes) -> bytes:
    """Aggressives Stripping von ESC-Kommandos inkl. Sening-Grafik-Blöcke."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == 0x1B and i + 1 < n:
            nxt = data[i + 1]
            # Sening-Poll Rest
            if nxt == 0xB3 and i + 2 < n:
                i += 3
                continue
            # ESC + <density> <param> [image bytes]
            if nxt == 0x2B:
                # Alles bis zum nächsten ESC als Grafik verwerfen
                j = i + 2
                while j < n and data[j] != 0x1B:
                    j += 1
                i = j
                continue
            # ESC @ / ESC 03 / ESC 0B etc.
            if nxt in (0x40, 0x03):
                i += 2
                continue
            if nxt == 0x0B:
                # ESC 0B  0c  60  c3  21  00   (line init)
                i += min(7, n - i)
                continue
            # ESC X n (3 bytes default) - feed/bold/font/align/graphics
            if nxt in (0x4A, 0x45, 0x4D, 0x61, 0x56, 0x74, 0x21):
                i += 3
                continue
            # Unknown ESC - skip ESC + 1
            i += 2
            continue
        # Niedrige Steuerzeichen ausser CR/LF/TAB
        if b < 0x20 and b not in (0x09, 0x0A, 0x0D):
            i += 1
            continue
        # Hohe Grafik-Bytes (0x80-0xFF) ausser 0xF8 (°) verwerfen
        if b >= 0x80 and b != 0xF8:
            i += 1
            continue
        out.append(b)
        i += 1
    return bytes(out)


# Marker-basierte Erkennung (robuster als Regex bei Grafik-Korruption)
SENING_MARKERS = {
    "zaehler_nr": [re.compile(r"Z[aä]ehler", re.IGNORECASE), re.compile(r"W3[^0-9]*le")],
    "beleg_nr":   [re.compile(r"Beleg", re.IGNORECASE), re.compile(r"fv[^0-9]*N")],
    "datum":      [re.compile(r"Datum", re.IGNORECASE), re.compile(r"abek[^a-z]*d[^a-z]*t")],
    "start":      [re.compile(r"Start", re.IGNORECASE), re.compile(r"abekle")],
    "ende":       [re.compile(r"Ende", re.IGNORECASE), re.compile(r"abek[^a-z]*t;")],
    "menge":      [re.compile(r"Menge", re.IGNORECASE), re.compile(r"M\+"), re.compile(r"bei.{0,10}15")],
}


def decode_sening_bitmap_digit(four_bytes: bytes):
    """Dekodiert Sening MultiFlow Bitmap-Bytes zu einer Ziffer.

    Sening rendert eichgueltige Mengen-Ziffern manchmal als Bitmap statt ASCII.
    Format A4 (1 Bitmap-Ziffer, 4 Bytes - klassisch): [b1] [b2] 0x72 0xD3
        b1 = 0x83 + d * 8   (d = Ziffer 0..9)
    Format A5 (1 Bitmap-Ziffer, 5 Bytes - neuere Firmware ab 2026):
        [b1] [b2] [b3pad] 0x72 0x{D3 oder C8}
        b1 = 0x83 + d * 8   (gleiches Codier-Schema wie A4)
        b3pad = Pad-Byte (z.B. 0x0c oder 0x0e), abhaengig von Schriftgroesse
        Beispiel-Belege: 0xab 0x2c 0x0c 0x72 0xd3 = Ziffer 5
                         0x9b 0x0c 0x0e 0x72 0xd3 = Ziffer 3
                         0xa3 0x0e 0x72 0xc8       = Ziffer 4 (4-Byte mit C8-Marker)
    Format B (2 Bitmap-Ziffern, 4 Bytes): [b1] [b2] [b3] 0xC8
        b1 = 0x83 + d1 * 8  (erste Bitmap-Ziffer)
        b3 = 0x33 + d2 * 8  (zweite Bitmap-Ziffer)
        b4 = 0xC8           (Endmarker fuer 2-stelliges Format)

    Returns:
        - "X"   wenn Format A4/A5 erkannt (1 Ziffer)
        - "XY"  wenn Format B erkannt (2 Ziffern)
        - None  bei unbekanntem Pattern
    """
    if len(four_bytes) < 4:
        return None
    b1, b2, b3, b4 = four_bytes[0], four_bytes[1], four_bytes[2], four_bytes[3]
    b5 = four_bytes[4] if len(four_bytes) >= 5 else None

    # Format A5: 5 Bytes [b1][b2][pad] 0x72 0x{D3|C8} - hoechste Prio, da
    # neuere Firmware. Pad-Byte (b3) typisch 0x0C oder 0x0E (Schriftgroessen-Hint),
    # wir akzeptieren jeden Wert unter 0x20 (Control-Byte).
    if b5 is not None and b4 == 0x72 and b5 in (0xD3, 0xC8) and b3 < 0x20:
        if 0x83 <= b1 <= 0xCB and (b1 - 0x83) % 8 == 0:
            d_from_b1 = (b1 - 0x83) // 8
            if 0 <= d_from_b1 <= 9:
                return str(d_from_b1)

    # Format A4: byte3=0x72, byte4 in (0xD3, 0xC8) - klassisch + erweitert
    # 0xC8 als Endmarker fuer Format A4 ist eine neuere Sening-Variante,
    # zu unterscheiden von Format B durch b3=0x72 vs b3=0x33+d*8.
    if b3 == 0x72 and b4 in (0xD3, 0xC8):
        if b1 < 0x83 or b1 > 0xCB or (b1 - 0x83) % 8 != 0:
            return None
        d_from_b1 = (b1 - 0x83) // 8
        if not (0 <= d_from_b1 <= 9):
            return None
        return str(d_from_b1)

    # Format B: byte4=0xC8, byte3 NICHT 0x72 (sonst waere Format A4)
    if b4 == 0xC8 and b3 != 0x72:
        if b1 < 0x83 or b1 > 0xCB or (b1 - 0x83) % 8 != 0:
            return None
        d1 = (b1 - 0x83) // 8
        if not (0 <= d1 <= 9):
            return None
        if b3 < 0x33 or b3 > 0x33 + 9 * 8 or (b3 - 0x33) % 8 != 0:
            return None
        d2 = (b3 - 0x33) // 8
        if not (0 <= d2 <= 9):
            return None
        return f"{d1}{d2}"

    return None


def detect_quantity_in_raw(raw: bytes) -> tuple:
    """Sucht im RAW-Bytestream die Menge nach dem '*M+'-Marker und erkennt
    ob die letzte(n) Ziffer(n) als Sening-Bitmap encodiert sind.

    Sening MultiFlow druckt die Mengenzeile als:
        *M+ <bitmap header> <"v beK5 °C" mix> <whitespace> <ASCII-Ziffern> [Suffix] <whitespace>

    Suffix-Varianten:
        a) ' L  ' / ' L  *' -> ASCII komplett, keine fehlende Ziffer
        b) '03 8e 3a c8' (Eichende-Marker) -> ASCII komplett
        c) 'XX YY 72 d3' wo XX/YY eine Ziffer encoden -> 1+ Ziffer als Bitmap
           Bei MEHREREN Bitmap-Ziffern (z.B. >=10000 L) wiederholt sich dieses
           4-Byte-Pattern. Wir dekodieren so viele konsekutive Quadrupel wie moeglich.

    Returns:
        (ascii_digits, decoded_digits, has_unknown_bitmap)
        - ascii_digits: str | None - ASCII-Ziffern aus dem Stream
        - decoded_digits: str | None - dekodierte Ziffer(n) aus Bitmap (z.B. "6" oder "56")
        - has_unknown_bitmap: bool - True wenn ein nicht-dekodierbarer Bitmap-Suffix existiert
    """
    idx = raw.find(b"*M+")
    if idx < 0:
        idx = raw.find(b"M+")
        if idx < 0:
            return None, None, False, ""
    # Segment-Ende: zuerst nach \x1b\x4a (Form Feed), dann Sening-Line-End-
    # Marker \x1b\x0b\x0c\x60\xc3\x21 (Print-Engine-Reset). Letzteres ist
    # WICHTIG, weil Sening direkt nach diesem Marker oft Bytes wie ...\x31
    # (= ASCII '1') sendet, die sonst faelschlich als Mengen-Ziffer interpretiert
    # werden und den Bitmap-Decoder vom richtigen Suffix wegziehen.
    # Beleg 16980 (31 L Diesel): Sening-Reset bei +37 enthielt '\x31\xc0',
    # was die '1' nach hinten verschoben und den '3' + Bitmap-'1' Decode brach.
    end_candidates = []
    e1 = raw.find(b"\x1b\x4a", idx + 2)
    if e1 > 0:
        end_candidates.append(e1)
    e2 = raw.find(b"\x1b\x0b\x0c\x60\xc3\x21", idx + 2)
    if e2 > 0:
        end_candidates.append(e2)
    if end_candidates:
        end = min(end_candidates)
    else:
        end = idx + 100
    segment = raw[idx:end]

    # Sammle alle ASCII-Ziffernlaeufe mit Position
    digit_runs = []
    i = 0
    while i < len(segment):
        if 0x30 <= segment[i] <= 0x39:
            j = i
            while j < len(segment) and 0x30 <= segment[j] <= 0x39:
                j += 1
            digit_runs.append((i, j, segment[i:j].decode("ascii")))
            i = j
        else:
            i += 1
    if not digit_runs:
        return None, None, False, ""
    candidates = [(s, e, d) for (s, e, d) in digit_runs if len(d) >= 2]
    if not candidates:
        candidates = digit_runs
    last_pos, last_end, last_digits = candidates[-1]

    # Schleife: dekodiere konsekutive Bitmap-Quadrupel (4-Byte ODER 5-Byte
    # je nach Format A4/A5/B). Bei 5-Byte-Format (neuere Sening-Firmware ab
    # 2026) ist zwischen [b2] und [0x72] ein Pad-Byte (0x0c/0x0e) eingefuegt.
    decoded_digits = []
    pos = last_end
    has_unknown_bitmap = False
    unknown_bytes_hex = ""  # Forensik: welche Bytes konnten wir nicht parsen
    while pos + 4 <= len(segment):
        # Erst 5-Byte (Format A5) probieren - hat Vorrang vor 4-Byte
        chunk5 = segment[pos:pos + 5] if pos + 5 <= len(segment) else b""
        chunk4 = segment[pos:pos + 4]
        digit = None
        consumed = 0
        if len(chunk5) == 5:
            d5 = decode_sening_bitmap_digit(chunk5)
            if d5 is not None and chunk5[3] == 0x72 and chunk5[4] in (0xD3, 0xC8) and chunk5[2] < 0x20:
                # eindeutig A5 (3.Byte ist Pad, 4./5. sind 0x72 + Endmarker)
                digit = d5
                consumed = 5
        if digit is None:
            d4 = decode_sening_bitmap_digit(chunk4)
            if d4 is not None:
                digit = d4
                consumed = 4
        if digit is None:
            # Pruefe ob hier ueberhaupt ein Bitmap-Suffix beginnt (= unknown)
            if not decoded_digits:
                # Erstes Quadrupel ist nicht dekodierbar
                first = chunk4[0]
                # Bekannter Endemarker (03 8e 3a c8) oder ASCII " L" -> nichts unbekannt
                if first == 0x03 and chunk4[1] == 0x8E:
                    pass  # Standard-Endemarker, alles OK
                elif first == 0x20 or first == 0x4C:
                    pass  # Whitespace oder " L" (ASCII-Ende)
                elif first >= 0x80 or (first < 0x20 and first not in (0x09, 0x0A, 0x0D)):
                    has_unknown_bitmap = True
                    # Logge die naechsten 12 Bytes als Hex damit wir spaeter
                    # neue Bitmap-Patterns reverse engineeren koennen.
                    forensic_chunk = segment[pos:min(pos + 12, len(segment))]
                    unknown_bytes_hex = " ".join(f"{b:02x}" for b in forensic_chunk)
                    log.warning(
                        f"BITMAP-PATTERN UNBEKANNT nach ASCII '{last_digits}': {unknown_bytes_hex} "
                        f"(bitte an Backend melden fuer Decoder-Erweiterung)"
                    )
            break
        decoded_digits.append(digit)
        pos += consumed
        # Sicherheits-Limit: max 5 Quadrupel (= bis 10 Bitmap-Ziffern)
        if len(decoded_digits) >= 5:
            break

    decoded_str = "".join(decoded_digits) if decoded_digits else None
    return last_digits, decoded_str, has_unknown_bitmap, unknown_bytes_hex


def parse_receipt_sening(raw: bytes, fixed_zaehler_nr: str = "") -> dict:
    """Parser fuer Sening MultiFlow mit Bit-Image Mischdruck.
    Extrahiert so viel wie moeglich, markiert fehlende Felder.

    fixed_zaehler_nr: Falls gesetzt und der Parser erkennt nur ein Praefix,
    wird dieser volle Wert verwendet (z.B. '11461' wenn Parser '1146' liefert).
    """
    # Raw-Stream-Analyse fuer Menge mit Bitmap-Decode (mehrere Ziffern moeglich)
    raw_qty_digits, raw_qty_bitmap_digits, raw_qty_unknown_bitmap, raw_qty_unknown_hex = detect_quantity_in_raw(raw)
    if raw_qty_digits:
        log.info(f"  RAW-Menge: ASCII='{raw_qty_digits}' bitmap_digits={raw_qty_bitmap_digits!r} unknown_bitmap={raw_qty_unknown_bitmap}")

    stripped = strip_sening_escapes(raw)
    try:
        text = stripped.decode("cp437", errors="replace")
    except Exception:
        text = stripped.decode("latin-1", errors="replace")

    # Text in "Zeilen" zerhacken (an Whitespace-Häufungen splitten)
    # Jede Label-Zeile hat typischerweise:  <marker text>  <spaces>  <zahl>
    segments = re.split(r"m1\??|\n", text)

    result = {
        "zaehler_nr": None,
        "beleg_nr": None,
        "datum": None,
        "abgabe_start": None,
        "abgabe_ende": None,
        "zaehler_vor_start": None,
        "fuel_type": None,
        "menge_liter": None,
        "raw_text": text,
        "needs_review": False,
        "review_reason": [],
    }

    def find_number_after(segment: str, pattern, max_after: int = 100, min_digits: int = 2):
        """Nimmt die LÄNGSTE Zahl nach dem Marker (nicht die erste kleine)."""
        m = pattern.search(segment)
        if not m:
            return None
        tail = segment[m.end(): m.end() + max_after]
        nums = re.findall(r"\d+", tail)
        if not nums:
            return None
        # Priorisiere längste Zahl mit min_digits Ziffern
        candidates = [n for n in nums if len(n) >= min_digits]
        if candidates:
            candidates.sort(key=len, reverse=True)
            return candidates[0]
        # Fallback: letzte Zahl (meist der echte Wert, nicht Line-ID)
        return nums[-1]

    def find_quantity_after(segment: str, pattern, max_after: int = 80, min_digits: int = 2):
        """Spezial fuer die Menge: nimmt die LETZTE Zahl im Tail (rechtsbuendig).
        Sening druckt die Menge immer rechtsbuendig vor dem 'r'-Bitmap-Rest, also
        ist die LETZTE Zahl im Tail die korrekte. Tail wird am Segment-Ende
        (m1, *, Newline) abgeschnitten, damit Werte aus Folgezeilen nicht eingeschleppt werden.
        Plausibilitaets-Check: 1..99999 Liter."""
        m = pattern.search(segment)
        if not m:
            return None
        tail = segment[m.end(): m.end() + max_after]
        # Tail abschneiden am naechsten Segment-Trenner (Sening druckt m1\r am Zeilenende)
        end_marker = re.search(r"m1|\n", tail)
        if end_marker:
            tail = tail[:end_marker.start()]
        nums = re.findall(r"\d+", tail)
        if not nums:
            return None
        candidates = [n for n in nums if len(n) >= min_digits and 1 <= int(n) <= 99999]
        log.info(f"  Menge-Tail nach '{pattern.pattern}': {tail!r} -> Kandidaten {nums} (gefiltert {candidates})")
        if candidates:
            # LETZTE qualifizierende Zahl (rechtsbuendig) - das ist die Menge
            return candidates[-1]
        # Fallback: letzte Zahl mit Plausibilitaet
        plausible = [n for n in nums if 1 <= int(n) <= 99999]
        return plausible[-1] if plausible else None

    def find_time_after(segment: str, pattern, max_after: int = 100):
        """Findet Zeiten HH:MM:SS, auch bei fehlenden Minuten (Sening-Bitmap)."""
        m = pattern.search(segment)
        if not m:
            return None
        tail = segment[m.end(): m.end() + max_after]
        # Volltreffer HH:MM:SS oder HH:MM
        t = re.search(r"(\d{2}):(\d{2})(?::(\d{2}))?", tail)
        if t:
            ss = t.group(3) or "00"
            return f"{t.group(1)}:{t.group(2)}:{ss}"
        # Teiltreffer: HH: <Grafik/Trenner> SS  -> "14:??:05"
        t = re.search(r"(\d{2}):[^0-9\n]{0,6}(\d{2})\b", tail)
        if t:
            return f"{t.group(1)}:??:{t.group(2)}"
        # Minimal: nur HH:
        t = re.search(r"(\d{2}):", tail)
        if t:
            return f"{t.group(1)}:??:??"
        return None

    for seg in segments:
        if not seg.strip():
            continue
        # Zaehler-Nr (4-6 Ziffern erwartet)
        if result["zaehler_nr"] is None:
            for pat in SENING_MARKERS["zaehler_nr"]:
                v = find_number_after(seg, pat, min_digits=3)
                if v and len(v) >= 3:
                    result["zaehler_nr"] = v
                    break
        # Beleg-Nr (mindestens 2 Ziffern - meist 4-5)
        if result["beleg_nr"] is None:
            for pat in SENING_MARKERS["beleg_nr"]:
                v = find_number_after(seg, pat, min_digits=2)
                if v:
                    result["beleg_nr"] = v
                    break
        # Datum (vollstaendig unwahrscheinlich, aber wenn Glueck)
        if result["datum"] is None:
            m = re.search(r"(\d{2}\.\d{2}\.\d{2,4})", seg)
            if m:
                result["datum"] = m.group(1)
        # Start / Ende: beide erkennen, Reihenfolge nach Position
        if result["abgabe_start"] is None:
            for pat in SENING_MARKERS["start"]:
                t = find_time_after(seg, pat)
                if t:
                    result["abgabe_start"] = t
                    break
        if result["abgabe_ende"] is None:
            for pat in SENING_MARKERS["ende"]:
                t = find_time_after(seg, pat)
                if t:
                    result["abgabe_ende"] = t
                    break
        # Menge (Zahl nach "Menge" oder "M+" oder "bei 15") - SPEZIAL: rechtsbuendig, letzte Zahl
        if result["menge_liter"] is None:
            for pat in SENING_MARKERS["menge"]:
                v = find_quantity_after(seg, pat, max_after=80)
                if v:
                    try:
                        result["menge_liter"] = float(v)
                        log.info(f"  -> Menge gewaehlt: {v} L (Marker: {pat.pattern})")
                    except ValueError:
                        pass
                    break

    # ====== Bitmap-Digit-Decode fuer Sening-Eichbelege ======
    # Sening MultiFlow druckt die letzte(n) Ziffer(n) der Menge MANCHMAL als Bitmap
    # (Eichgueltigkeits-Marker). Wir erkennen das im Raw-Stream und dekodieren
    # die Ziffer(n) nach der Formel:
    #   bitmap = [byte1] [byte2] 0x72 0xd3
    #   byte1 = 0x83 + d * 8,  byte2 = 0x12 - d
    # Bei MEHREREN Bitmap-Ziffern wiederholt sich das Pattern (z.B. fuer >=10000 L).
    # Beispiele aus echten Belegen:
    #   154 L: ASCII "15" + bitmap 'a3 0e 72 d3' -> dekodiert: "4" -> 154 ✓
    #   1296 L: ASCII "129" + bitmap 'b3 0c 72 d3' -> dekodiert: "6" -> 1296 ✓
    if raw_qty_digits and raw_qty_bitmap_digits:
        try:
            full_qty_str = raw_qty_digits + raw_qty_bitmap_digits
            full_qty = int(full_qty_str)
            current_qty = result.get("menge_liter")
            if current_qty is None or float(current_qty) == float(raw_qty_digits):
                result["menge_liter"] = float(full_qty)
                log.info(f"  -> Sening-Bitmap-Decode: ASCII '{raw_qty_digits}' + Bitmap '{raw_qty_bitmap_digits}' = {full_qty} L")
        except (ValueError, TypeError) as e:
            log.warning(f"  Bitmap-Decode fehlgeschlagen: {e}")
    elif raw_qty_unknown_bitmap and raw_qty_digits:
        # Bitmap-Suffix vorhanden, aber Pattern nicht erkannt -> needs_review
        result["needs_review"] = True
        ascii_val = int(raw_qty_digits)
        reason = (f"Sening-Bitmap-Suffix erkannt aber nicht dekodierbar - "
                  f"ASCII-Wert: {ascii_val} L. "
                  f"Forensic-Hex (12 Bytes): {raw_qty_unknown_hex or '(leer)'}. "
                  f"Bitte an Entwickler senden zur Pattern-Erweiterung.")
        # Hex auch als eigenes Feld, damit Frontend es Copy-Paste-freundlich
        # anzeigen kann (review_bitmap_hex Liste, falls mehrere Belege).
        existing_hex = result.get("review_bitmap_hex") or []
        if isinstance(existing_hex, list):
            existing_hex.append(raw_qty_unknown_hex)
        else:
            existing_hex = [raw_qty_unknown_hex]
        result["review_bitmap_hex"] = existing_hex
        log.warning(f"  [REVIEW] {reason}")
        if isinstance(result.get("review_reason"), list):
            result["review_reason"].append(reason)
        else:
            result["review_reason"] = [reason]

    # Fuel-Type Heuristik
    # Stufe 1 (Binaer-Marker, validiert anhand Live-Belegen Mai 2026):
    #   Sening druckt im Roh-Stream einen "*X..."-Code wo X den Kraftstoff
    #   bezeichnet, gefolgt von einer Bitmap-Sequenz mit dem Produktnamen:
    #     *H+...    -> HEL (Heizoel) - bestaetigt durch 15 Heizoel-Belege
    #     *DKV...   -> Diesel - bestaetigt durch Beleg 16979 (42L Diesel-Test)
    #                 ("DKV" = vermutl. DKV-Tankkarten-Brand-Praefix)
    #     *V+...    -> mutmasslich HVO (Sening-Konvention, noch nicht verifiziert)
    #   Andere *-Marker im Stream (*Z, *B+, *M+) sind KEINE Kraftstoff-Marker.
    #   Robuste Regex: '*' + (H|D|V) + (Buchstabe ODER '+'), so dass weder *Z
    #   (Zaehler) noch *B+ (Beleg) noch *M+ (Menge) faelschlich greifen.
    fuel_match = re.search(rb"\*(H|D|V)[A-Z+]", raw)
    if fuel_match:
        c = fuel_match.group(1)
        if c == b"H":
            result["fuel_type"] = "heizoel_leicht"
            log.info(f"  Sening-Binary-Marker '*H{chr(raw[fuel_match.end()-1])}' gefunden -> fuel_type=heizoel_leicht")
        elif c == b"D":
            result["fuel_type"] = "diesel"
            log.info(f"  Sening-Binary-Marker '*D{chr(raw[fuel_match.end()-1])}' gefunden -> fuel_type=diesel")
        elif c == b"V":
            result["fuel_type"] = "hvo"
            log.info(f"  Sening-Binary-Marker '*V{chr(raw[fuel_match.end()-1])}' gefunden -> fuel_type=hvo")
    else:
        # Stufe 2 (ASCII-Marker im Klartext): *HEL/Diesel/HVO via Bitmap-Decode.
        # Sening druckt das tatsaechlich abgegebene Produkt mit fuehrendem * + Whitespace,
        # waehrend andere konfigurierte Fuels meist NICHT mit * markiert sind.
        # WICHTIG: NIEMALS blind auf "Diesel" fallen wenn der *-Marker fehlt - der
        # Sening-Header kann das Wort "Diesel" als Geraete-Bezeichnung enthalten
        # auch wenn aktuell HEL ausgeliefert wird. Bei Mehrdeutigkeit lassen wir
        # fuel_type = None und vertrauen dem Config-Default (default_fuel_type).
        fuel_marker = re.search(r"\*\s*(HEL[\s\w]*schwefelarm|Diesel|HVO)\b", text, re.IGNORECASE)
        if fuel_marker:
            fm_raw = fuel_marker.group(1).lower()
            if "hel" in fm_raw:
                result["fuel_type"] = "heizoel_leicht"
            elif "diesel" in fm_raw:
                result["fuel_type"] = "diesel"
            elif "hvo" in fm_raw:
                result["fuel_type"] = "hvo"
        else:
            # Kein eindeutiger Marker -> Config-Default greift in enrich_receipt_*.
            result["fuel_type"] = None
            log.info(
                "  Kein '*H?/*D?/*V?'-Binary-Marker und kein '*HEL/Diesel/HVO'-Klartext "
                "gefunden - fuel_type bleibt offen, Config-Default wird angewendet."
            )

    # Feste Zaehler-Nr aus Config anwenden (falls Parser nur Praefix hatte)
    if fixed_zaehler_nr:
        if result["zaehler_nr"] and fixed_zaehler_nr.startswith(result["zaehler_nr"]):
            # Parser-Praefix matcht -> nimm den vollen Wert
            result["zaehler_nr"] = fixed_zaehler_nr
        elif not result["zaehler_nr"]:
            # Parser hat nichts gefunden -> nimm trotzdem den festen Wert
            result["zaehler_nr"] = fixed_zaehler_nr

    # Review-Flag wird jetzt ausserhalb gesetzt (nach Counter/Zeit-Heuristik)
    return result


def enrich_receipt_with_heuristics(receipt: dict, conf: dict) -> dict:
    """Ergaenzt fehlende Felder durch feste Werte + Pi-Uhrzeit/Zeitberechnung:
    - datum = Pi-NTP Datum heute
    - abgabe_ende = aktuelle Pi-Uhrzeit
    - abgabe_start = Ende minus (Liter*Sek/L + Einrichtung)
    - beleg_nr = Auto-Counter ab Startwert
    """
    now = now_berlin()
    # 1) Datum immer = heute (Pi-NTP, Europe/Berlin)
    receipt["datum"] = now.strftime("%d.%m.%Y")

    # 2) Abgabe-Ende = jetzt (falls nicht oder nur partial aus Bitmap)
    receipt["abgabe_ende"] = now.strftime("%H:%M:%S")

    # 3) Abgabe-Start berechnen aus Menge + Einrichtung
    #    Linear-Fit aus zwei Live-Messungen (07.05.2026):
    #      104 L  ->  8 min (480 s)
    #     1731 L  -> 20 min (1200 s)
    #    -> ca. 0.5 sec/L + 420 sec Einrichtung. Float-Werte erlaubt.
    try:
        sek_pro_l = float(conf.get("abgabe_zeit_pro_liter_sek", 0.5))
        einrichtung = float(conf.get("abgabe_zeit_einrichtung_sek", 420))
    except (ValueError, TypeError):
        sek_pro_l = 0.5
        einrichtung = 420.0
    menge = receipt.get("menge_liter") or 0
    try:
        menge_f = float(menge)
    except (TypeError, ValueError):
        menge_f = 0
    duration_sek = int(menge_f * sek_pro_l + einrichtung)
    from datetime import timedelta as _td
    start_dt = now - _td(seconds=duration_sek)
    receipt["abgabe_start"] = start_dt.strftime("%H:%M:%S")

    # 4) Beleg-Nr als Counter (aus DB ableiten)
    try:
        start_val = int(str(conf.get("beleg_nr_start", "")).strip() or "0")
    except (ValueError, TypeError):
        start_val = 0
    if start_val > 0:
        try:
            next_nr = get_next_beleg_nr(conf["db_path"], start_val)
            receipt["beleg_nr"] = str(next_nr)
        except Exception as e:
            log.warning(f"Beleg-Nr-Counter fehlgeschlagen: {e}")

    # 5) Default-Kraftstoff anwenden wenn Parser nichts erkannt hat.
    # Sening druckt "*HEL schwefelarm*" oft als Bitmap -> Parser findet nix.
    # Der Truck fuehrt ueblicherweise monatelang nur ein Produkt; darum ist
    # der Deployment-Default (z.B. "heizoel_leicht") verlaesslicher als stiller
    # Rueckfall auf "diesel". Trotzdem als needs_review flaggen, damit der
    # Fahrer die Zuordnung auf dem Pi-Kiosk noch korrigieren kann falls heute
    # mal ausnahmsweise Diesel ausgeliefert wurde.
    default_fuel = (conf.get("default_fuel_type") or "").strip()
    if not receipt.get("fuel_type") and default_fuel:
        receipt["fuel_type"] = default_fuel
        log.info(f"  Kraftstoff aus Default-Config uebernommen: {default_fuel}")

    # 6) Review-Flag bereinigen: Datum ist via NTP gesichert, Zeiten berechnet,
    #    Beleg-Nr per Counter. Nur noch Menge ist Pflicht.
    #    WICHTIG: Bestehende review_reasons (z.B. Bitmap-Suffix-Detection) erhalten!
    existing_reasons = receipt.get("review_reason") or []
    if isinstance(existing_reasons, str):
        existing_reasons = [existing_reasons]
    elif not isinstance(existing_reasons, list):
        existing_reasons = []
    existing_review = bool(receipt.get("needs_review"))

    missing = []
    if not receipt.get("menge_liter"):
        missing.append("Menge")
    if not receipt.get("fuel_type"):
        missing.append("Kraftstoff")
    if missing:
        existing_reasons.append(", ".join(missing) + " aus Bitmap nicht lesbar")

    receipt["needs_review"] = bool(missing) or existing_review
    receipt["review_reason"] = "; ".join(existing_reasons) if existing_reasons else None
    return receipt


# ====== Bitmap-Rendering: Roh-Beleg als PNG ======

def render_receipt_png(raw: bytes, parsed: dict) -> bytes:
    """Rendert den empfangenen Beleg als PNG-Bild.
    Nutzt Pillow falls verfuegbar, sonst minimalen PNG-Writer mit Text."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log.warning("Pillow nicht installiert - keine PNG-Generierung")
        return b""

    # Strukturiere Inhalt
    lines = [
        "Tankbeleg (Sening MultiFlow Capture)",
        "=" * 40,
        f"Zaehler-Nr.  : {parsed.get('zaehler_nr') or '???'}",
        f"Beleg-Nr.    : {parsed.get('beleg_nr') or '???'}",
        f"Datum        : {parsed.get('datum') or '???'}",
        f"Abgabe-Start : {parsed.get('abgabe_start') or '???'}",
        f"Abgabe-Ende  : {parsed.get('abgabe_ende') or '???'}",
        f"Kraftstoff   : {parsed.get('fuel_type') or '???'}",
        f"Menge Liter  : {parsed.get('menge_liter') or '???'} L",
        "=" * 40,
    ]
    if parsed.get("needs_review"):
        lines.append(f"! Review: {parsed.get('review_reason','')}")
        lines.append("")
    lines.append("Original-Rohdaten (Hex):")

    # 48 Byte pro Zeile => 144 Zeichen (mit Leerz.) => wir bauen 16 Byte/Zeile
    for i in range(0, len(raw), 16):
        chunk = raw[i:i + 16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        asc_part = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in chunk)
        lines.append(f"{i:04x}  {hex_part:<48}  {asc_part}")

    # Bild-Größe berechnen
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 11)
    except (OSError, IOError):
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

    char_w, char_h = 7, 14
    if font:
        try:
            bbox = font.getbbox("M")
            char_w = bbox[2] - bbox[0] + 1
            char_h = bbox[3] - bbox[1] + 4
        except Exception:
            pass

    width = max(len(line) for line in lines) * char_w + 30
    height = len(lines) * char_h + 30

    img = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(img)
    y = 15
    for line in lines:
        draw.text((15, y), line, fill=0, font=font)
        y += char_h

    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


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
        # KEIN stiller Default auf "diesel" - unbekannte Werte = None
        # (sonst landen HEL-Belege falsch als Diesel im Portal, wenn der Regex
        # etwas matcht was nicht im Mapping steht).
        receipt["fuel_type"] = fuel_map.get(fuel_raw.lower())

    m = RE_MENGE.search(text)
    if m:
        receipt["menge_liter"] = float(m.group(1))

    return receipt


def is_complete_receipt(receipt: dict) -> bool:
    """Prueft ob GENUG Pflichtfelder da sind um den Beleg zu sichern.
    Bei Sening-Grafik-Druck koennen einzelne Felder fehlen -> needs_review=True,
    aber der Beleg wird trotzdem gespeichert + manuell komplettiert."""
    # Menge ist Pflicht - ohne geht gar nichts
    if not receipt.get("menge_liter"):
        return False
    # Datum wird ggf. auf heute gesetzt im parse_receipt_sening
    return receipt.get("datum") is not None


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
    # Neue Spalten fuer Sening Bitmap-Capture
    for col_ddl in (
        "ADD COLUMN raw_receipt_hex TEXT",
        "ADD COLUMN bitmap_png_base64 TEXT",
        "ADD COLUMN needs_review INTEGER DEFAULT 0",
        "ADD COLUMN review_reason TEXT",
    ):
        try:
            conn.execute(f"ALTER TABLE receipts {col_ddl}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
    log.info(f"Datenbank initialisiert: {db_path}")


def store_receipt(db_path, receipt, gps_lat, gps_lon, fahrer, raw_bytes=None, bitmap_png=None):
    """Speichert einen geparsten Beleg in der lokalen DB.
    raw_bytes: Die Original-Bytes vom Drucker (fuer Beweiskraft)
    bitmap_png: Gerendertes PNG als bytes (optional, wird base64-kodiert gespeichert)"""
    import base64 as _b64
    local_id = str(uuid.uuid4())
    # Zeit aus abgabe_start oder aktueller Zeit
    zeit = receipt.get("abgabe_start", now_berlin().strftime("%H:%M:%S"))
    raw_hex = raw_bytes.hex() if raw_bytes else None
    png_b64 = _b64.b64encode(bitmap_png).decode("ascii") if bitmap_png else None

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            INSERT INTO receipts (local_id, zaehler_nr, beleg_nr, datum, zeit,
                abgabe_start, abgabe_ende, zaehler_vor_start,
                fuel_type, menge_liter, gps_lat, gps_lon, fahrer, raw_text,
                raw_receipt_hex, bitmap_png_base64, needs_review, review_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            raw_hex,
            png_b64,
            1 if receipt.get("needs_review") else 0,
            receipt.get("review_reason") or None,
        ))
        conn.commit()
        review_flag = " [REVIEW]" if receipt.get("needs_review") else ""
        log.info(f"Beleg gespeichert{review_flag}: Nr. {receipt.get('beleg_nr')}, "
                 f"{receipt.get('menge_liter')} L {receipt.get('fuel_type')}, "
                 f"PNG={'ja' if png_b64 else 'nein'}")
    except sqlite3.IntegrityError:
        log.warning(f"Beleg bereits vorhanden: {local_id}")
    finally:
        conn.close()

    return local_id


def get_unsynced(db_path, limit=50):
    """Holt ungesyncte Belege aus der lokalen DB.
    Nur Belege mit einer Zuordnung (assigned=1) werden uebertragen, damit im
    Portal keine leeren Belege ohne Auftrag/Fahrer landen. Belege ohne
    Zuordnung bleiben lokal gepuffert, bis der Bediener sie auf dem
    Touchscreen einem Auftrag zuweist."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM receipts WHERE synced=0 AND COALESCE(assigned,0)=1 ORDER BY id ASC LIMIT ?",
            (limit,)
        ).fetchall()
    except sqlite3.OperationalError:
        # Fallback falls Spalte 'assigned' (noch) nicht existiert
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

# OTA Update State (modul-global, persistent ueber Sync-Cycles)
_OTA_PI_ID = None        # Eindeutige Pi-Identitaet (UUID, in /var/lib/tankbeleg/pi_id gespeichert)


def _get_or_create_pi_id(db_path: str) -> str:
    """Liefert eine persistente, eindeutige Pi-ID. Wird einmalig generiert
    und neben der SQLite-DB als Datei abgelegt."""
    global _OTA_PI_ID
    if _OTA_PI_ID:
        return _OTA_PI_ID
    id_file = Path(os.path.dirname(db_path)) / "pi_id"
    try:
        if id_file.exists():
            content = id_file.read_text().strip()
            if content:
                _OTA_PI_ID = content
                return _OTA_PI_ID
        new_id = str(uuid.uuid4())
        id_file.parent.mkdir(parents=True, exist_ok=True)
        id_file.write_text(new_id)
        _OTA_PI_ID = new_id
        return _OTA_PI_ID
    except Exception as e:
        log.warning(f"Pi-ID-Datei nicht schreibbar: {e}")
        _OTA_PI_ID = str(uuid.uuid4())
        return _OTA_PI_ID


def _self_script_hash() -> str:
    """SHA-256 des aktuell laufenden Skripts."""
    try:
        with open(__file__, "rb") as f:
            import hashlib
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return ""


def _collect_pi_status_for_otacheck(conf: dict) -> dict:
    """Sammelt LTE/GPS/Signal Status fuer das Portal-Dashboard.
    Wird bei jedem OTA-Check als URL-Parameter mitgesendet (best-effort, fuer
    Probleme einfach ignorieren -> Update-Pfad bleibt unbeeintraechtigt).
    """
    import subprocess
    status = {}

    # 1. LTE-IP aus 'ip addr show ppp0'
    try:
        r = subprocess.run(["ip", "-4", "addr", "show", "ppp0"],
                           capture_output=True, text=True, timeout=2)
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                status["lte_ip"] = line.split()[1].split("/")[0]
                break
    except Exception:
        pass

    # 2. CSQ + Operator via AT-Befehl an SIM7600 (best-effort, falls Port frei)
    at_candidates = ["/dev/sim7600-at2", "/dev/sim7600-at",
                     "/dev/ttyUSB3", "/dev/ttyUSB2"]
    port = next((p for p in at_candidates if os.path.exists(p)), None)
    if port:
        try:
            lsof = subprocess.run(["lsof", "-t", port],
                                  capture_output=True, text=True, timeout=2)
            port_busy = bool(lsof.stdout.strip())
        except Exception:
            port_busy = True
        if not port_busy:
            try:
                subprocess.run(["stty", "-F", port, "115200", "raw", "-echo"],
                               capture_output=True, timeout=2)
                for cmd, key in [("AT+CSQ", "csq"), ("AT+COPS?", "operator")]:
                    try:
                        subprocess.run(["bash", "-c", f"printf '{cmd}\\r' > {port}"],
                                       capture_output=True, timeout=2)
                        time.sleep(0.4)
                        r = subprocess.run(
                            ["bash", "-c", f"timeout 1 cat {port} || true"],
                            capture_output=True, text=True, timeout=2,
                        )
                        out = r.stdout
                        if key == "csq":
                            m = re.search(r"\+CSQ:\s*(\d+)", out)
                            if m:
                                csq = int(m.group(1))
                                status["lte_csq"] = csq
                                # CSQ -> dBm Annaeherung: dBm = -113 + 2*csq
                                if 0 <= csq <= 31:
                                    status["lte_dbm"] = -113 + 2 * csq
                        elif key == "operator":
                            m = re.search(r'\+COPS:\s*\d+,\d+,"([^"]+)"(?:,(\d+))?', out)
                            if m:
                                status["lte_operator"] = m.group(1)
                                act_map = {"0": "GSM", "2": "UMTS", "7": "LTE", "13": "LTE-NB"}
                                if m.group(2):
                                    status["lte_act"] = act_map.get(m.group(2), m.group(2))
                    except Exception:
                        pass
            except Exception:
                pass

    # 3. GPS Position (best-effort)
    try:
        lat, lon = get_gps_position(host=conf.get("gps_host", "127.0.0.1"),
                                    port=int(conf.get("gps_port", 2947)),
                                    timeout=2)
        if lat is not None and lon is not None:
            status["gps_lat"] = f"{lat:.6f}"
            status["gps_lon"] = f"{lon:.6f}"
    except Exception:
        pass

    return status


def check_and_apply_ota_update(conf: dict) -> bool:
    """Prueft beim Backend ob ein neueres tankbeleg_pi.py verfuegbar ist.
    Wenn ja: laed es runter, validiert via Hash, ersetzt das laufende Skript
    und beendet den Prozess (systemd startet automatisch neu).

    Returns True wenn ein Update angewendet wurde (Prozess wird gleich beendet).
    """
    base = _api_base(conf)
    if not base:
        return False
    pi_id = _get_or_create_pi_id(conf.get("db_path", "/var/lib/tankbeleg/tankbeleg.sqlite"))
    current_hash = _self_script_hash()
    try:
        import socket
        hostname = socket.gethostname()
    except Exception:
        hostname = ""

    # ===== Pi-Status-Daten fuer das Portal-Dashboard mitsenden =====
    extra_status = _collect_pi_status_for_otacheck(conf)

    try:
        params = {
            "pi_id": pi_id,
            "hostname": hostname,
            "hash": current_hash,
            "version": SCRIPT_VERSION,
            **extra_status,
        }
        # None-Werte rauswerfen, damit URL nicht mit lte_ip= verschmutzt wird
        params = {k: v for k, v in params.items() if v not in (None, "")}
        resp = requests.get(f"{base}/system/ota/tankwagen/check", params=params, timeout=10, headers=PI_HEADERS)
        if resp.status_code != 200:
            log.debug(f"OTA-Check Fehler {resp.status_code}: {resp.text[:200]}")
            return False
        info = resp.json()
        if not info.get("update_available"):
            log.debug("OTA: kein Update verfuegbar")
            return False
        log.info(f"OTA: Update verfuegbar (neuer Hash {info.get('file_hash','?')[:12]})")

        # Download
        resp2 = requests.get(f"{base}/system/ota/tankwagen/download", params={"pi_id": pi_id}, timeout=30, headers=PI_HEADERS)
        if resp2.status_code != 200:
            log.warning(f"OTA-Download Fehler {resp2.status_code}")
            return False
        new_content = resp2.content
        # Hash-Validierung
        import hashlib
        new_hash = hashlib.sha256(new_content).hexdigest()
        expected = info.get("file_hash") or resp2.headers.get("X-Hash", "")
        if expected and new_hash != expected:
            log.warning(f"OTA-Hash-Mismatch: erhalten {new_hash[:12]}, erwartet {expected[:12]}")
            return False
        # Sanity: Skript muss eine Mindestgroesse haben und 'def main' enthalten
        if len(new_content) < 1000 or b"def main" not in new_content:
            log.warning("OTA: Heruntergeladenes Skript wirkt unvollstaendig - abbrechen")
            return False
        # Backup + atomic replace
        script_path = os.path.realpath(__file__)
        backup_path = script_path + ".bak"
        try:
            import shutil
            shutil.copy2(script_path, backup_path)
        except Exception as e:
            log.warning(f"OTA-Backup fehlgeschlagen: {e}")
        tmp_path = script_path + ".new"
        with open(tmp_path, "wb") as f:
            f.write(new_content)
        os.replace(tmp_path, script_path)
        log.info(f"OTA: Skript aktualisiert ({len(new_content)} Bytes). Beende Prozess fuer Neustart durch systemd...")
        # Sanftes Sync der Logs
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        # Beenden -> systemd startet automatisch neu (Restart=always)
        os._exit(0)
    except requests.RequestException as e:
        log.debug(f"OTA-Check nicht erreichbar: {e}")
    except Exception as e:
        log.warning(f"OTA-Update Fehler: {e}")
    return False


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
            "fuel_type": row.get("fuel_type"),
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
            "raw_receipt_hex": row.get("raw_receipt_hex") or None,
            "bitmap_png_base64": row.get("bitmap_png_base64") or None,
            "needs_review": bool(row.get("needs_review")),
            "review_reason": row.get("review_reason") or None,
            "order_pk": row.get("order_pk") or None,
            "order_name": row.get("order_name") or "",
            "notes": row.get("notes") or f"Pi-Sync {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        }
        api_receipts.append(api_receipt)
        local_ids.append(row["local_id"])

    try:
        base = _api_base(conf)
        if not base:
            log.warning("api_url nicht konfiguriert, Sync uebersprungen")
            return 0
        sync_url = f"{base}/fuel-receipts/sync"
        resp = requests.post(
            sync_url,
            json=api_receipts,
            timeout=30,
            headers=PI_HEADERS,
        )
        if resp.status_code == 200:
            result = resp.json()
            created = result.get("created", 0)
            updated = result.get("updated", 0)
            skipped = result.get("skipped", 0)
            mark_synced(conf["db_path"], local_ids)
            log.info(f"Sync OK: {created} neu, {updated} aktualisiert, {skipped} uebersprungen")
            return created + updated
        else:
            log.warning(f"Sync Fehler {resp.status_code} (URL={sync_url}): {resp.text[:200]}")
    except requests.ConnectionError:
        log.warning("Portal nicht erreichbar, Belege bleiben lokal gepuffert")
    except Exception as e:
        log.error(f"Sync Fehler: {e}")

    return 0


# ====== Serielle Schnittstelle ======

class RawStreamPusher:
    """Async-Pusher: sammelt RX/TX-Bytes mit Timestamp und sendet sie batched
    an den Backend-Endpoint /api/system/tankwagen/raw-stream/push.

    Best-effort: Wenn das Backend nicht erreichbar ist, wird der Buffer
    irgendwann gekappt (max_batch * 5 Eintraege gespeichert), Pi-Hauptlogik
    laeuft trotzdem unbeeintraechtigt weiter.

    Threading: ein einzelner Daemon-Thread tut den Flush. Push() ist nicht
    blockierend - es haengt nur an die in-memory Liste an.
    """

    def __init__(self, conf: dict, pi_id: str, hostname: str):
        self.conf = conf
        self.pi_id = pi_id
        self.hostname = hostname
        self.enabled = str(conf.get("raw_stream_enabled", "false")).strip().lower() in ("1", "true", "yes", "ja", "on")
        try:
            self.flush_sek = float(conf.get("raw_stream_flush_sek", 1.5))
        except (TypeError, ValueError):
            self.flush_sek = 1.5
        try:
            self.max_batch = int(conf.get("raw_stream_max_batch", 200))
        except (TypeError, ValueError):
            self.max_batch = 200
        self.max_buffer = self.max_batch * 5  # ~1000 Eintraege als Hard-Limit

        import threading
        self._lock = threading.Lock()
        self._buf = []  # type: list[dict]
        self._stop = threading.Event()
        self._thread = None
        if self.enabled:
            self._thread = threading.Thread(target=self._run, daemon=True, name="RawStreamPusher")
            self._thread.start()
            log.info(f"RawStream aktiv -> {_api_base(conf)}/system/tankwagen/raw-stream/push (flush={self.flush_sek}s)")
        else:
            log.info("RawStream deaktiviert (raw_stream_enabled=false)")

    def push(self, data: bytes, direction: str, note: str = None):
        """Nicht-blockierend: schiebe einen Chunk in den Buffer.
        direction: 'rx' = vom Sening empfangen, 'tx' = vom Pi gesendet.
        """
        if not self.enabled or not data:
            return
        entry = {
            "ts": time.time(),
            "direction": direction,
            "hex": data.hex(),
        }
        if note:
            entry["note"] = note
        with self._lock:
            self._buf.append(entry)
            # Hard-Cap: bei dauerhaft offline Backend nicht unendlich wachsen
            if len(self._buf) > self.max_buffer:
                drop = len(self._buf) - self.max_buffer
                self._buf = self._buf[drop:]

    def _drain(self) -> list:
        with self._lock:
            if not self._buf:
                return []
            batch = self._buf[: self.max_batch]
            self._buf = self._buf[self.max_batch:]
            return batch

    def _run(self):
        while not self._stop.is_set():
            time.sleep(self.flush_sek)
            try:
                batch = self._drain()
                if not batch:
                    continue
                base = _api_base(self.conf)
                if not base:
                    continue
                payload = {
                    "pi_id": self.pi_id,
                    "hostname": self.hostname,
                    "chunks": batch,
                }
                r = requests.post(
                    f"{base}/system/tankwagen/raw-stream/push",
                    json=payload,
                    timeout=5,
                    headers=PI_HEADERS,
                )
                if r.status_code != 200:
                    log.debug(f"RawStream push HTTP {r.status_code}: {r.text[:120]}")
                    # Bei Fehler: Batch zurueck in den Buffer (am Anfang) -
                    # aber nur wenn dadurch nicht das Hard-Cap gerissen wird,
                    # sonst lieber verwerfen damit der Hauptbetrieb laeuft.
                    with self._lock:
                        if len(self._buf) + len(batch) <= self.max_buffer:
                            self._buf = batch + self._buf
            except requests.RequestException as e:
                log.debug(f"RawStream push exception: {e}")
            except Exception as e:
                log.debug(f"RawStream Fehler: {e}")

    def stop(self):
        self._stop.set()


class SerialReceiptReader:
    """Liest serielle Daten und erkennt vollstaendige Belege."""

    def __init__(self, port, baud=9600, bytesize=8, parity='N', stopbits=1, sening_reply_byte=0x00, ftdi_latency_ms=1, raw_stream=None):
        self.port = port
        self.baud = baud
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.sening_reply_byte = sening_reply_byte
        self.ftdi_latency_ms = ftdi_latency_ms
        self.raw_stream = raw_stream  # RawStreamPusher | None
        self.ser = None
        self.buffer = bytearray()
        # Holds incomplete status-query prefixes across chunked serial reads
        # so we don't accidentally leak them into the receipt buffer.
        self.pending_prefix = bytearray()
        # Timeout: wenn X Sekunden keine Daten kommen, ist der Beleg komplett
        self.receipt_timeout = 3.0
        self.last_data_time = 0

    def _set_ftdi_latency_timer(self):
        """Setzt den FTDI USB-Serial Latency-Timer auf wenige ms.

        Hintergrund: Der FTDI-Treiber im Linux-Kernel verwendet per Default
        einen Latency-Timer von 16 ms, d.h. der Chip wartet bis zu 16 ms bevor
        er den USB-Bulk-Endpoint flusht. Zusammen mit dem 16-Byte UART-FIFO
        bedeutet das: kommen mehr als 16 Bytes in <16 ms (durchaus normal bei
        9600 Baud Burst-Druck), laeuft der FIFO ueber und einzelne Bytes
        gehen verloren. Symptom: "Menge bei 15 C" wird statt 1316 L nur als
        13 L empfangen, weil die letzten Ziffern (Bitmap-encoded) beim Flush
        verloren gingen.

        Fix: latency_timer auf 1 ms setzen -> der Chip flusht praktisch sofort,
        FIFO bleibt nie voll. Erfordert root oder passende udev-Rule
        (siehe install_tankwagen_pi.sh).

        Best-effort: Wenn der Adapter kein FTDI ist, gibt es keinen
        latency_timer-Pfad. Dann nur Hinweis im Log, kein Fehler.
        """
        if not self.ftdi_latency_ms:
            return
        try:
            # Resolve /dev/ttyUSB0 -> /sys/class/tty/ttyUSB0/device
            tty_name = os.path.basename(os.path.realpath(self.port))
            sysfs_device = f"/sys/class/tty/{tty_name}/device"
            if not os.path.exists(sysfs_device):
                log.info(f"FTDI-Latency: kein sysfs-device fuer {self.port} (kein FTDI?)")
                return
            # FTDI latency_timer liegt direkt im device-Dir
            latency_path = os.path.join(sysfs_device, "latency_timer")
            if not os.path.exists(latency_path):
                # Manche Kernel haengen es eine Stufe tiefer (../driver/...) -> probieren
                alt = os.path.realpath(os.path.join(sysfs_device, "..", "latency_timer"))
                if os.path.exists(alt):
                    latency_path = alt
                else:
                    log.info(f"FTDI-Latency: kein latency_timer-Knoten unter {sysfs_device} - vermutlich kein FTDI-Adapter")
                    return
            with open(latency_path, "w") as f:
                f.write(str(int(self.ftdi_latency_ms)))
            # Verifizieren
            try:
                with open(latency_path, "r") as f:
                    actual = f.read().strip()
                log.info(f"FTDI-Latency-Timer: {latency_path} = {actual} ms (Soll {self.ftdi_latency_ms} ms)")
            except OSError:
                log.info(f"FTDI-Latency-Timer auf {self.ftdi_latency_ms} ms gesetzt ({latency_path})")
        except PermissionError:
            log.warning(
                f"FTDI-Latency-Timer nicht setzbar (Permission denied). "
                f"Bitte als root ausfuehren oder udev-Rule installieren: "
                f"echo 'SUBSYSTEM==\"usb-serial\", DRIVER==\"ftdi_sio\", ATTR{{latency_timer}}=\"{self.ftdi_latency_ms}\"' "
                f"> /etc/udev/rules.d/50-ftdi-latency.rules"
            )
        except Exception as e:
            log.debug(f"FTDI-Latency-Setzen fehlgeschlagen (ignoriert): {e}")

    def connect(self):
        """Oeffnet die serielle Verbindung."""
        parity_map = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}
        stopbits_map = {1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}

        # Flow-Control-Strategie v1.7.7 (final, durch Live-Diagnose bestaetigt):
        #   xonxoff=False    -> Software-Flow AUS. Sening sendet 0x11/0x13 als
        #                       reine Datenbytes, NICHT als XON/XOFF. Mit
        #                       xonxoff=True hat pyserial das missverstanden
        #                       und Schreibvorgaenge blockiert -> Sening:
        #                       "Drucker antwortet nicht".
        #   dsrdtr=False     -> Hardware-Flow AUS. Beweis: Live-Diagnose hat
        #                       DSR=False, CTS=False, CD=False, RI=False
        #                       gezeigt - Sening nutzt 3-Wire Null-Modem-Kabel
        #                       (nur TXD/RXD/GND). Mit dsrdtr=True wartet
        #                       pyserial auf DSR=High vor jedem write() und
        #                       blockiert deshalb dauerhaft -> unsere
        #                       Status-Replies kamen nie an -> Sening:
        #                       "Drucker nicht erreichbar".
        #   rtscts=False     -> RTS/CTS-Handshake AUS, gleicher Grund.
        # DTR und RTS werden trotzdem manuell auf HIGH gesetzt (siehe unten)
        # damit der Sening-Empfangsstrom nicht durch RS-232-Floating gestoert
        # wird. FIFO-Overrun loesen wir via FTDI-Latency-Timer = 1 ms.
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
        # FTDI Latency-Timer auf 1 ms setzen -> kein FIFO-Overrun bei Burst-Druck
        self._set_ftdi_latency_timer()
        log.info(f"Serielle Verbindung geoeffnet: {self.port} @ {self.baud}")
        # Diagnose-Log: Erwartet sind xonxoff=False, dsrdtr=False, rtscts=False
        # (3-Wire Sening MultiFlow). Wenn dsrdtr=True hier auftaucht laeuft
        # noch eine alte Version - dann blockieren writes -> Sening sieht
        # "Drucker nicht erreichbar".
        try:
            log.info(f"FLOW-CONTROL: xonxoff={self.ser.xonxoff} rtscts={self.ser.rtscts} dsrdtr={self.ser.dsrdtr}")
        except (AttributeError, Exception):
            pass

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
                # Live-Stream: kompletten RX-Chunk an das Backend pushen
                if self.raw_stream:
                    self.raw_stream.push(data, "rx")
                # Status-Queries INLINE beantworten, aus dem Print-Stream entfernen
                data = self._handle_status_queries(data)
                if data:
                    self.buffer.extend(data)
                    self.last_data_time = time.time()

            # WICHTIG: Timeout-Check IMMER ausfuehren, NICHT als elif!
            # Sening pollt alle ~1.5s mit ESC B3 FF. Ein elif wuerde bedeuten:
            # solange Polls reinkommen ist data nicht-leer und der Timeout-Branch
            # wird NIE erreicht -> Buffer-Flush passiert nicht -> Beleg geht
            # verloren obwohl er komplett im Buffer steht. Genau dieser Bug
            # hat den 1153 L Beleg im Mai 2026 verschluckt.
            if self.buffer and (time.time() - self.last_data_time) > self.receipt_timeout:
                raw = bytes(self.buffer)
                self.buffer.clear()
                text = strip_escpos(raw)
                log.info(f"BUFFER-FLUSH nach {self.receipt_timeout}s Stille: {len(raw)} Bytes")
                return raw, text

            if not data and not self.buffer:
                # Kein Buffer, nichts zu tun -> kurz schlafen und raus, damit
                # die main loop andere Tasks (OTA, Sync) bedienen kann.
                return None, None

            if not data:
                # Buffer vorhanden, noch kein Timeout - kurz warten
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

    def _reply(self, data: bytes, note: str = None):
        """Sendet eine Antwort an den Sening und streamt sie zugleich an das
        Backend (best-effort). Konsolidiert ser.write + flush + raw_stream.push.
        """
        try:
            self.ser.write(data)
            self.ser.flush()
        except (OSError, IOError) as e:
            log.warning(f"Status-Antwort fehlgeschlagen: {e}")
            return
        if self.raw_stream:
            self.raw_stream.push(data, "tx", note=note)

    def _handle_status_queries(self, data: bytes) -> bytes:
        """Parst eingehende Bytes und beantwortet Epson TM-U295 Status-Queries.
        Gibt die Bytes ZURUECK ohne die Status-Queries (damit sie nicht im
        Print-Buffer / Beleg landen).

        Status-Antworten gemaess offizieller TM-U295-Spec
        (https://www.jarltech.com/.../TM-U295_spc_I.pdf):

          DLE EOT n  (0x10 0x04 n) - Real-time Status Transmission:
            n=1 (printer status)   -> 0x12 (Bit1+4 fixed=ON, online, drawer LOW)
            n=2 (offline status)   -> 0x12 (Bit1+4 fixed=ON, kein paper-end, kein error)
            n=3 (error status)     -> 0x12 (Bit1+4 fixed=ON, kein unrecoverable error)
            n=5 (slip paper status)-> 0x12 (Bit1+4 fixed=ON, slip selected & detected
                                            durch BOF+TOF Sensoren)
            HINWEIS: TM-U295 hat KEIN n=4 (das war TM-U220 receipt printer).
                     n=5 ist Slip-spezifisch fuer TM-U295.

          DLE ENQ n  (0x10 0x05 n) - Realtime Request -> 0x00 (no error)

          ESC v       (0x1B 0x76)  - Transmit Paper Sensor Status:
            -> 0x00 (Bit0=BOF detected, Bit1=TOF detected = paper present;
                     Bit4+7 fixed=OFF; rest undefined)

          ESC u 0     (0x1B 0x75 0x00) - Transmit Peripheral Device Status (drawer)
            -> 0x00 (drawer pin 3 LOW)

          GS r n      (0x1D 0x72 n):
            n=1, 49 -> 0x00 (paper sensor status, identisch ESC v)
            n=2, 50 -> 0x00 (drawer kick-out connector status)

          ESC c 3 n / ESC c 4 n (4 bytes):
            Konfigurationsbefehle vom Sening fuer Paper-Sensor-Auswahl. KEINE
            Antwort erforderlich, aber Bytes muessen aus dem Print-Stream
            entfernt werden damit sie nicht in den Beleg landen.

          Sening proprietary  ESC B3 n  (0x1B 0xB3 n) - 3 bytes:
            -> sening_reply_byte (default 0x12, konfigurierbar)
            Nicht in TM-U295-Spec. Sening pollt damit "ist Drucker bereit?".
        """
        # Spec-konforme TM-U295-Status-Antworten. Bit 1 (0x02) und Bit 4 (0x10)
        # sind laut Spec FIXED ON in jeder DLE EOT Antwort - daher 0x12 als
        # Mindest-Wert. Weitere Bits sind 0 = "alles ok".
        # n=4 ist im TM-U295-Spec NICHT definiert (war TM-U220 receipt printer)
        # aber Sening 3.56[3.57]DE schickt das eventuell trotzdem aus alten
        # TM-U220-Profilen. Wir antworten safety-wise mit 0x12 fuer alle vier.
        STATUS_OK = {1: 0x12, 2: 0x12, 3: 0x12, 4: 0x12, 5: 0x12}

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
            #   DLE EOT/ENQ n : 3 bytes -> wenn remaining < 3 und Praefix passt, puffern
            #   ESC B3 n      : 3 bytes -> wenn remaining < 3, puffern
            #   ESC c 3/4 n   : 4 bytes -> wenn remaining < 4, puffern
            #   GS r n        : 3 bytes -> wenn remaining < 3, puffern
            #   ESC v / ESC u : 2 bytes -> nur puffern wenn remaining < 2
            if b == 0x10 and remaining < 3 and (remaining < 2 or data[i + 1] in (0x04, 0x05)):
                self.pending_prefix.extend(data[i:])
                return bytes(out)
            if b == 0x1B and remaining < 3 and remaining >= 2 and data[i + 1] == 0xB3:
                self.pending_prefix.extend(data[i:])
                return bytes(out)
            if b == 0x1B and remaining >= 2 and data[i + 1] == 0x63 and remaining < 4:
                # ESC c 3 / ESC c 4 ist 4 Bytes lang
                self.pending_prefix.extend(data[i:])
                return bytes(out)
            if b == 0x1B and remaining < 2:
                # ESC am Ende des Chunks ohne Folgebyte -> noch nicht entscheidbar
                self.pending_prefix.extend(data[i:])
                return bytes(out)
            if b == 0x1D and remaining < 3 and (remaining < 2 or data[i + 1] == 0x72):
                self.pending_prefix.extend(data[i:])
                return bytes(out)

            # DLE EOT n (0x10 0x04 n) - Epson printer status query
            if b == 0x10 and remaining >= 3 and data[i + 1] == 0x04:
                n = data[i + 2]
                if n in STATUS_OK:
                    reply = bytes([STATUS_OK[n]])
                    self._reply(reply, note=f"DLE EOT {n} -> 0x{STATUS_OK[n]:02X}")
                    log.info(f"Status-Query DLE EOT {n} -> 0x{STATUS_OK[n]:02X} (TM-U295 spec, online/paper OK)")
                    i += 3
                    continue
                else:
                    # Unbekannter n-Wert - log + skip (nicht in Buffer)
                    log.info(f"DLE EOT {n} -> KEINE Antwort (n nicht in TM-U295 Spec)")
                    i += 3
                    continue
            # DLE ENQ n (real-time status request, 0x10 0x05 n)
            if b == 0x10 and remaining >= 3 and data[i + 1] == 0x05:
                self._reply(b"\x00", note=f"DLE ENQ {data[i+2]} -> 0x00")
                log.debug(f"Realtime ENQ n={data[i+2]} -> 0x00 (ok)")
                i += 3
                continue
            # ESC v (0x1B 0x76) - Transmit Paper Sensor Status (TM-U295 Spec)
            # Reply Bit 0=BOF detected (paper), Bit 1=TOF detected (paper),
            # Bit 4+7 fixed OFF -> 0x00 = "Slip paper present at both sensors"
            if b == 0x1B and remaining >= 2 and data[i + 1] == 0x76:
                self._reply(b"\x00", note="ESC v -> 0x00 (paper present BOF+TOF)")
                log.info("Status-Query ESC v -> 0x00 (slip paper present at BOF+TOF)")
                i += 2
                continue
            # ESC u 0 (0x1B 0x75 0x00) - Peripheral Device Status (drawer)
            # Reply: Bit 0=0 (drawer pin 3 LOW = drawer closed)
            if b == 0x1B and remaining >= 3 and data[i + 1] == 0x75:
                self._reply(b"\x00", note="ESC u -> 0x00 (drawer closed)")
                log.info("Status-Query ESC u -> 0x00 (drawer pin 3 LOW)")
                i += 3
                continue
            # GS r n (0x1D 0x72 n) - Transmit Status (TM-U295 Spec)
            # n=1 oder 49 -> paper sensor status (identisch ESC v) -> 0x00
            # n=2 oder 50 -> drawer kick-out connector status -> 0x00
            if b == 0x1D and remaining >= 3 and data[i + 1] == 0x72:
                n = data[i + 2]
                self._reply(b"\x00", note=f"GS r {n} -> 0x00")
                if n in (1, 49):
                    log.info(f"Status-Query GS r {n} -> 0x00 (paper sensor: BOF+TOF detected)")
                elif n in (2, 50):
                    log.info(f"Status-Query GS r {n} -> 0x00 (drawer pin 3 LOW)")
                else:
                    log.info(f"Status-Query GS r {n} -> 0x00 (unbekanntes n, default ok)")
                i += 3
                continue
            # ESC c 3 n / ESC c 4 n (0x1B 0x63 0x33|0x34 n) - Paper-Sensor Config
            # Diese 4-Byte-Commands setzen welche Sensoren paper-end signal
            # ausgeben bzw. Druck stoppen. KEINE Antwort - aber raus aus dem
            # Print-Buffer damit sie nicht in den Beleg landen.
            if b == 0x1B and remaining >= 4 and data[i + 1] == 0x63 and data[i + 2] in (0x33, 0x34):
                cmd = "ESC c 3" if data[i + 2] == 0x33 else "ESC c 4"
                n = data[i + 3]
                log.info(f"Sening Config {cmd} n=0x{n:02X} (Paper-Sensor-Auswahl, no reply)")
                i += 4
                continue
            # Sening MultiFlow proprietary poll:  ESC (0x1B) 0xB3 <n>
            # NICHT in TM-U295-Spec dokumentiert - Sening-spezifisch.
            # Sehr wahrscheinlich ein "Hallo Drucker, bist du da?" Probe.
            # Default-Antwort 0x12 = TM-U295 "online + paper OK" status byte.
            if b == 0x1B and remaining >= 3 and data[i + 1] == 0xB3:
                zone = data[i + 2]
                reply = bytes([self.sening_reply_byte])
                self._reply(reply, note=f"ESC B3 {zone:02X} -> 0x{self.sening_reply_byte:02X}")
                log.info(f"Sening-Poll ESC B3 {zone:02X} -> 0x{self.sening_reply_byte:02X}")
                i += 3
                continue
            # Unbekannte ESC-Sequenzen: Loggen damit wir neue Polls erkennen
            # koennen (Sening hat z.T. undokumentierte Varianten je Firmware).
            # Wir loggen nur den Header, lassen die Bytes aber im Buffer
            # damit der Parser den eigentlichen Beleg-Inhalt nicht verliert.
            if b == 0x1B and remaining >= 2 and data[i + 1] not in (0xB3, 0x76, 0x75, 0x63):
                # Sammle naechste 4 Bytes fuer Forensik-Log
                preview = data[i:min(i + 6, len(data))]
                log.debug(f"ESC-Sequenz unbekannt (kein Status-Query, weiter im Print-Stream): {preview.hex(' ')}")
            out.append(b)
            i += 1
        return bytes(out)


# ====== Hauptprogramm ======

def main():
    conf = load_config()

    log.info("=" * 60)
    log.info("  Tankbeleg Pi - Eventenergie Portal")
    log.info("  Epson TM-U295 Drucker-Emulator")
    log.info(f"  Skript-Version: {SCRIPT_VERSION}")
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

    # Live-Raw-Stream Pusher (best-effort, default off). Erlaubt Live-Debug
    # via /api/system/tankwagen/raw-stream/tail im Portal.
    try:
        import socket
        _hostname = socket.gethostname()
    except Exception:
        _hostname = ""
    pi_id_for_stream = _get_or_create_pi_id(conf["db_path"])
    raw_stream = RawStreamPusher(conf, pi_id_for_stream, _hostname)

    reader = SerialReceiptReader(
        port=conf["serial_port"],
        baud=conf["serial_baud"],
        bytesize=conf["serial_bytesize"],
        parity=conf["serial_parity"],
        stopbits=conf["serial_stopbits"],
        sening_reply_byte=reply_byte,
        ftdi_latency_ms=int(conf.get("ftdi_latency_ms", 1) or 1),
        raw_stream=raw_stream,
    )

    try:
        reader.connect()
    except Exception as e:
        log.error(f"Serielle Verbindung fehlgeschlagen: {e}")
        log.info("Starte im Offline-Modus (nur Sync bereits vorhandener Belege)")
        reader = None

    last_sync_time = 0
    consecutive_errors = 0

    # OTA-Check beim Start ausfuehren (damit sich der Pi sofort beim Portal meldet
    # und im Update-Dashboard erscheint - nicht erst nach erstem sync_interval).
    if conf.get("api_url"):
        log.info("OTA-Pruefung beim Start...")
        try:
            updated = check_and_apply_ota_update(conf)
            if updated:
                # check_and_apply_ota_update() ruft bei Erfolg sys.exit(0) auf,
                # systemd startet dann mit dem neuen Skript neu. Hier nur safety-net:
                log.info("Update angewendet - beende fuer systemd-Restart")
                return
        except Exception as ota_e:
            log.warning(f"OTA-Check beim Start fehlgeschlagen: {ota_e}")
        last_sync_time = time.time()  # Doppel-Check im Loop verhindern

    log.info("Warte auf Belegdaten...")

    while True:
        try:
            # Serielle Daten lesen
            if reader:
                raw, text = reader.read_receipt()
                if text:
                    log.info(f"Empfangene Daten ({len(raw)} Bytes)")
                    log.debug(f"Text:\n{text}")

                    # Zuerst Standard-Parser (saubere ESC/POS-Texte)
                    log.info("PARSE1: Standard-Parser...")
                    receipt = parse_receipt(text)

                    # Falls wenig Felder erkannt: Sening-Grafik-Parser auf Rohdaten
                    recognized = sum(1 for k in ("zaehler_nr", "beleg_nr", "menge_liter", "abgabe_start") if receipt.get(k))
                    if recognized < 2:
                        log.info("PARSE2: Sening-Grafik-Parser...")
                        try:
                            receipt = parse_receipt_sening(raw, fixed_zaehler_nr=conf.get("fixed_zaehler_nr", ""))
                            log.info(f"PARSE2 OK: menge={receipt.get('menge_liter')} zaehler={receipt.get('zaehler_nr')}")
                        except Exception as e:
                            log.error(f"PARSE2 Fehler: {e}", exc_info=True)
                            raise
                        # Heuristik: Datum/Zeiten/Beleg-Nr aus Pi + Counter ergaenzen
                        log.info("PARSE3: Heuristik...")
                        try:
                            receipt = enrich_receipt_with_heuristics(receipt, conf)
                            log.info(f"PARSE3 OK: beleg={receipt.get('beleg_nr')} datum={receipt.get('datum')} start={receipt.get('abgabe_start')}")
                        except Exception as e:
                            log.error(f"PARSE3 Fehler: {e}", exc_info=True)
                            raise

                    if is_complete_receipt(receipt):
                        log.info("STEP1: is_complete=True, hole GPS...")
                        # GPS Position erfassen
                        gps_lat, gps_lon = None, None
                        if conf["gps_enabled"].lower() == "true":
                            try:
                                gps_lat, gps_lon = get_gps_position(
                                    conf["gps_host"], int(conf["gps_port"])
                                )
                                if gps_lat:
                                    log.info(f"STEP2: GPS OK: {gps_lat:.6f}, {gps_lon:.6f}")
                                else:
                                    log.info("STEP2: GPS kein Fix")
                            except Exception as e:
                                log.warning(f"STEP2: GPS Fehler: {e}")
                        else:
                            log.info("STEP2: GPS deaktiviert")

                        # PNG rendern (Best-Effort, falls Pillow da ist)
                        log.info("STEP3: Rendere PNG...")
                        png_bytes = b""
                        try:
                            png_bytes = render_receipt_png(raw, receipt)
                            if png_bytes:
                                log.info(f"STEP3: PNG OK: {len(png_bytes)} Bytes")
                            else:
                                log.info("STEP3: PNG leer")
                        except Exception as e:
                            log.warning(f"STEP3: PNG-Rendering fehlgeschlagen: {e}")

                        # Lokal speichern (inkl. Roh-Hex + PNG)
                        log.info("STEP4: Speichere Beleg in SQLite...")
                        try:
                            store_receipt(
                                conf["db_path"],
                                receipt,
                                gps_lat,
                                gps_lon,
                                conf["fahrer_name"],
                                raw_bytes=raw,
                                bitmap_png=png_bytes or None,
                            )
                            log.info("STEP5: Store OK")
                        except Exception as e:
                            log.error(f"STEP4: Store Fehler: {e}", exc_info=True)
                        consecutive_errors = 0
                    else:
                        missing = [f for f in ["beleg_nr", "datum", "menge_liter"]
                                   if receipt.get(f) is None]
                        log.warning(f"Unvollstaendiger Beleg, fehlende Felder: {', '.join(missing)}")
                        log.debug(f"Geparste Felder: {receipt}")

                        # Plausibilitaets-Filter gegen Phantom-Belege:
                        # Sening-Eichbelege sind ca. 500-700 Bytes lang und enthalten
                        # ein charakteristisches Init-Pattern (1b 03 b7 d8 cc 9a 30 db
                        # bzw. die generelle 1b 0b 0c 60 c3 21 Sequenz vom Sening-
                        # Print-Engine). Kurze Status-/Polling-Bursts darunter
                        # unterscheiden wir um keine 0-Liter-Geister-Belege mit
                        # neuer Counter-Nummer zu erzeugen.
                        is_plausible_print = (
                            len(raw) >= 200
                            and (b"\x1b\x0b\x0c\x60\xc3\x21" in raw or b"\x1b\x03\xb7\xd8" in raw)
                        )

                        # Zweite Stufe gegen Sening-Test-/Diagnose-Drucke:
                        # Ein echter Tankbeleg hat im *M+-Bereich mindestens eine
                        # mehrstellige ASCII-Zahl (= Mengenanzeige). Ein leerer
                        # Test-/Selbsttestdruck enthaelt zwar Sening-Header, aber
                        # keine Mengenangabe - der wuerde sonst als "0L-Geist"
                        # mit neuer Counter-Beleg-Nr im UI auftauchen.
                        # v1.7.13: Strikter - die ASCII-Ziffernfolge nach M+
                        # muss eine Zahl > 0 ergeben. Ein '0' oder ' 00.0 ' ist
                        # ein Probedruck, kein echter Beleg.
                        has_real_menge = False
                        m_plus_value = 0.0
                        if is_plausible_print:
                            mp = raw.find(b"M+")
                            if mp >= 0:
                                end = raw.find(b"\x1b\x4a", mp + 2)
                                if end < 0:
                                    end = mp + 80
                                seg = raw[mp:end]
                                import re as _re
                                # Suche nach allen Zahlen (auch Dezimal) und nimm
                                # die groesste - das ist die echte Menge.
                                nums = _re.findall(rb"\d+(?:[.,]\d+)?", seg)
                                for n in nums:
                                    try:
                                        v = float(n.replace(b",", b"."))
                                        if v > m_plus_value:
                                            m_plus_value = v
                                    except (ValueError, TypeError):
                                        continue
                                has_real_menge = m_plus_value > 0.0

                        # v1.7.13: zusaetzliche letzte Pruefung - menge_liter aus
                        # parse_receipt_sening MUSS > 0 sein. Sonst kein Stub.
                        parsed_menge = receipt.get("menge_liter")
                        try:
                            parsed_menge_f = float(parsed_menge) if parsed_menge is not None else 0.0
                        except (TypeError, ValueError):
                            parsed_menge_f = 0.0

                        if not is_plausible_print:
                            log.info(
                                f"PHANTOM-FILTER: Ignoriere kurzen/atypischen Stream "
                                f"({len(raw)} Bytes, kein Sening-Header) - kein Stub angelegt."
                            )
                            consecutive_errors = 0
                        elif not has_real_menge:
                            log.info(
                                f"PHANTOM-FILTER: Sening-Header vorhanden ({len(raw)} B), "
                                f"aber Mengen-Wert im *M+-Bereich = {m_plus_value} L "
                                f"(<=0) -> Test-/Probedruck, kein Stub angelegt."
                            )
                            consecutive_errors = 0
                        elif parsed_menge_f <= 0.0:
                            log.info(
                                f"PHANTOM-FILTER: M+-Region hat Menge {m_plus_value} L, "
                                f"aber parse_receipt_sening lieferte menge_liter={parsed_menge} "
                                f"-> kein Stub, sonst landet 0L-Geist im UI."
                            )
                            consecutive_errors = 0
                        else:
                            # WICHTIG: Roh-Bytes trotzdem speichern damit wir den
                            # Druckstrom nicht verlieren - sonst kann man den Parser
                            # nicht nachtraeglich fixen. Markiere als needs_review.
                            try:
                                _now_b = now_berlin()
                                stub = {
                                    "beleg_nr": receipt.get("beleg_nr") or f"INCOMPLETE_{int(time.time())}",
                                    "datum": receipt.get("datum") or _now_b.strftime("%d.%m.%Y"),
                                    "abgabe_start": receipt.get("abgabe_start") or "",
                                    "abgabe_ende": receipt.get("abgabe_ende") or _now_b.strftime("%H:%M:%S"),
                                    "zaehler_nr": receipt.get("zaehler_nr") or "",
                                    "zaehler_vor_start": receipt.get("zaehler_vor_start"),
                                    "menge_liter": parsed_menge_f,
                                    "fuel_type": receipt.get("fuel_type"),
                                    "needs_review": True,
                                    "review_reason": f"Unvollstaendiger Beleg - fehlende Felder: {', '.join(missing)}. {len(raw)} Bytes RAW gespeichert. Hex-Dump an Entwickler senden.",
                                }
                                store_receipt(
                                    conf["db_path"], stub, gps_lat, gps_lon,
                                    conf["fahrer_name"], raw_bytes=raw,
                                    bitmap_png=None,
                                )
                                log.info(f"INCOMPLETE: Roh-Bytes ({len(raw)}) trotzdem in DB gespeichert fuer spaetere Analyse")
                            except Exception as e:
                                log.error(f"INCOMPLETE: Store fehlgeschlagen: {e}", exc_info=True)
                            consecutive_errors = 0

            # Periodisch zum Portal syncen
            now = time.time()
            if conf["api_url"] and (now - last_sync_time) >= int(conf["sync_interval"]):
                # OTA-Update-Check (vor dem Sync, damit der neue Parser direkt greift)
                try:
                    check_and_apply_ota_update(conf)
                except Exception as ota_e:
                    log.debug(f"OTA-Check fehlgeschlagen (ignoriert): {ota_e}")
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
