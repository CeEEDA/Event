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


# Skript-Version - wird bei jedem OTA-Check zum Portal gemeldet, damit Admins
# in der Geraete-Uebersicht sehen ob ein Pi noch eine alte Version laeuft.
SCRIPT_VERSION = "1.7.0"


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
    # Zaehler-Nr. ist fest und koennte nicht 100% aus Bitmap gelesen werden.
    # Wenn der Parser nur ein Praefix erkennt (z.B. '1146'), wird die hier
    # hinterlegte vollstaendige Nummer genommen (z.B. '11461').
    "fixed_zaehler_nr": "",
    # Beleg-Nr laeuft in der MultiFlow hoch, wird aber als Bitmap gedruckt
    # (letzte 3 Ziffern unlesbar). Wir fuehren einen eigenen Counter ab dem
    # hier hinterlegten Startwert. Bei jedem Beleg +1.
    "beleg_nr_start": "",
    # Abgabezeit-Heuristik (da Minuten aus Bitmap unlesbar):
    # Ende = Pi-Uhrzeit bei Empfang, Start = Ende - (Liter * 12 s + 240 s).
    "abgabe_zeit_pro_liter_sek": 12,
    "abgabe_zeit_einrichtung_sek": 240,
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
    Format: [byte1] [byte2] 0x72 0xd3
        byte1 = 0x83 + d * 8   (d = Ziffer 0..9)
        byte2 = 0x12 - d
    Beispiele aus echten Belegen:
        a3 0e 72 d3 = Ziffer 4 (Beleg 16943, echt 154 L, ASCII zeigt nur "15")
        b3 0c 72 d3 = Ziffer 6 (Beleg 16944, echt 1296 L, ASCII zeigt nur "129")

    Returns:
        str(d) wenn beide Bytes konsistent eine Ziffer 0..9 ergeben, sonst None.
    """
    if len(four_bytes) < 4:
        return None
    if four_bytes[2] != 0x72 or four_bytes[3] != 0xD3:
        return None
    b1, b2 = four_bytes[0], four_bytes[1]
    # Pruefung: byte1 muss 0x83 + d*8 sein -> (b1 - 0x83) % 8 == 0
    if b1 < 0x83 or b1 > 0xCB:
        return None
    if (b1 - 0x83) % 8 != 0:
        return None
    d_from_b1 = (b1 - 0x83) // 8
    d_from_b2 = 0x12 - b2
    # Beide Berechnungen muessen uebereinstimmen
    if d_from_b1 != d_from_b2:
        return None
    if not (0 <= d_from_b1 <= 9):
        return None
    return str(d_from_b1)


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
            return None, None, False
    end = raw.find(b"\x1b\x4a", idx + 2)
    if end < 0:
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
        return None, None, False
    candidates = [(s, e, d) for (s, e, d) in digit_runs if len(d) >= 2]
    if not candidates:
        candidates = digit_runs
    last_pos, last_end, last_digits = candidates[-1]

    # Schleife: dekodiere konsekutive 4-Byte-Bitmap-Quadrupel
    decoded_digits = []
    pos = last_end
    has_unknown_bitmap = False
    while pos + 4 <= len(segment):
        chunk = segment[pos:pos + 4]
        digit = decode_sening_bitmap_digit(chunk)
        if digit is None:
            # Pruefe ob hier ueberhaupt ein Bitmap-Suffix beginnt (= unknown)
            if not decoded_digits:
                # Erstes Quadrupel ist nicht dekodierbar
                first = chunk[0]
                # Bekannter Endemarker (03 8e 3a c8) oder ASCII " L" -> nichts unbekannt
                if first == 0x03 and chunk[1] == 0x8E:
                    pass  # Standard-Endemarker, alles OK
                elif first == 0x20 or first == 0x4C:
                    pass  # Whitespace oder " L" (ASCII-Ende)
                elif first >= 0x80 or (first < 0x20 and first not in (0x09, 0x0A, 0x0D)):
                    has_unknown_bitmap = True
            break
        decoded_digits.append(digit)
        pos += 4
        # Sicherheits-Limit: max 5 Bitmap-Digits (= bis 99999 L)
        if len(decoded_digits) >= 5:
            break

    decoded_str = "".join(decoded_digits) if decoded_digits else None
    return last_digits, decoded_str, has_unknown_bitmap


def parse_receipt_sening(raw: bytes, fixed_zaehler_nr: str = "") -> dict:
    """Parser fuer Sening MultiFlow mit Bit-Image Mischdruck.
    Extrahiert so viel wie moeglich, markiert fehlende Felder.

    fixed_zaehler_nr: Falls gesetzt und der Parser erkennt nur ein Praefix,
    wird dieser volle Wert verwendet (z.B. '11461' wenn Parser '1146' liefert).
    """
    # Raw-Stream-Analyse fuer Menge mit Bitmap-Decode (mehrere Ziffern moeglich)
    raw_qty_digits, raw_qty_bitmap_digits, raw_qty_unknown_bitmap = detect_quantity_in_raw(raw)
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
                  f"Bitte Hex-Dump an Entwickler senden zur Pattern-Erweiterung.")
        log.warning(f"  [REVIEW] {reason}")
        if isinstance(result.get("review_reason"), list):
            result["review_reason"].append(reason)
        else:
            result["review_reason"] = [reason]

    # Fuel-Type Heuristik
    # Sening druckt das tatsaechlich abgegebene Produkt mit fuehrendem * + Whitespace,
    # waehrend andere konfigurierte Fuels meist NICHT mit * markiert sind. Wir suchen
    # darum zuerst die "*Marker"-Zeile (wenn der Bitmap-Decoder sie erhalten hat),
    # erst danach einen reinen Substring-Fallback.
    fuel_marker = re.search(r"\*\s*(HEL[\s\w]*schwefelarm|Diesel|HVO)\b", text, re.IGNORECASE)
    if fuel_marker:
        raw = fuel_marker.group(1).lower()
        if "hel" in raw:
            result["fuel_type"] = "heizoel_leicht"
        elif "diesel" in raw:
            result["fuel_type"] = "diesel"
        elif "hvo" in raw:
            result["fuel_type"] = "hvo"
    else:
        # Kein eindeutiger Marker -> manuell pruefen statt blind "HEL" zu matchen
        # (vorher fuehrte der Header-Eintrag "HEL schwefelarm" auch auf Diesel-Belegen
        # zu Fehlklassifikation, weil "hel" als Substring vorkam)
        diesel_only = re.search(r"\bDiesel\b", text, re.IGNORECASE) and not re.search(r"\bHEL\b", text, re.IGNORECASE)
        hvo_only = re.search(r"\bHVO\b", text) and not re.search(r"\bDiesel\b", text, re.IGNORECASE)
        if diesel_only:
            result["fuel_type"] = "diesel"
        elif hvo_only:
            result["fuel_type"] = "hvo"
        else:
            # Mehrdeutig -> NICHT raten, sondern manuelle Pruefung erzwingen
            result["fuel_type"] = None
            reason = "Kraftstoff konnte aus dem Bitmap nicht eindeutig erkannt werden - bitte manuell pruefen."
            log.warning(f"  [REVIEW] {reason}")
            if isinstance(result.get("review_reason"), list):
                result["review_reason"].append(reason)
            else:
                result["review_reason"] = [reason]

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
    now = datetime.now()
    # 1) Datum immer = heute (Pi-NTP)
    receipt["datum"] = now.strftime("%d.%m.%Y")

    # 2) Abgabe-Ende = jetzt (falls nicht oder nur partial aus Bitmap)
    receipt["abgabe_ende"] = now.strftime("%H:%M:%S")

    # 3) Abgabe-Start berechnen aus Menge + Einrichtung
    try:
        sek_pro_l = int(conf.get("abgabe_zeit_pro_liter_sek", 12))
        einrichtung = int(conf.get("abgabe_zeit_einrichtung_sek", 240))
    except (ValueError, TypeError):
        sek_pro_l = 12
        einrichtung = 240
    menge = receipt.get("menge_liter") or 0
    try:
        menge_f = float(menge)
    except (TypeError, ValueError):
        menge_f = 0
    duration_sek = int(menge_f * sek_pro_l + einrichtung)
    start_dt = now.timestamp() - duration_sek
    from datetime import datetime as _dt
    receipt["abgabe_start"] = _dt.fromtimestamp(start_dt).strftime("%H:%M:%S")

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

    # 5) Review-Flag bereinigen: Datum ist via NTP gesichert, Zeiten berechnet,
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
        receipt["fuel_type"] = fuel_map.get(fuel_raw.lower(), "diesel")

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
    zeit = receipt.get("abgabe_start", datetime.now().strftime("%H:%M:%S"))
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
        resp = requests.get(f"{base}/system/ota/tankwagen/check", params=params, timeout=10)
        if resp.status_code != 200:
            log.debug(f"OTA-Check Fehler {resp.status_code}: {resp.text[:200]}")
            return False
        info = resp.json()
        if not info.get("update_available"):
            log.debug("OTA: kein Update verfuegbar")
            return False
        log.info(f"OTA: Update verfuegbar (neuer Hash {info.get('file_hash','?')[:12]})")

        # Download
        resp2 = requests.get(f"{base}/system/ota/tankwagen/download", params={"pi_id": pi_id}, timeout=30)
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
