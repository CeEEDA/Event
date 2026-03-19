#!/usr/bin/env python3
"""
Tankbeleg Pi - Simulator & Test Suite
=======================================
Simuliert den Druckdaten-Output des Sening MultiFlow Messgeraets
ueber eine virtuelle serielle Schnittstelle und testet den Parser.

Verwendung:
  1) Nur Parser testen:     python3 tankbeleg_simulator.py --test-parser
  2) Virtuelle Ports:       python3 tankbeleg_simulator.py --virtual-serial
  3) Vollstaendiger Test:   python3 tankbeleg_simulator.py --full-test

Voraussetzungen fuer virtuelle Ports:
  sudo apt install socat
"""

import sys
import os
import time
import struct
import tempfile
import subprocess
import threading
import sqlite3
import json

# Den Pi-Script-Pfad hinzufuegen
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from tankbeleg_pi import (
    strip_escpos,
    parse_receipt,
    is_complete_receipt,
    init_db,
    store_receipt,
    get_unsynced,
    mark_synced,
    get_stats,
    load_config,
)


# ====== ESC/POS Beleg-Generator ======
# Simuliert den Output des Sening MultiFlow an den Epson TM-U295

class ReceiptGenerator:
    """Erzeugt realistische ESC/POS Belegdaten wie vom Sening MultiFlow."""

    # ESC/POS Kommandos
    ESC = b'\x1b'
    GS = b'\x1d'
    LF = b'\x0a'
    CR = b'\x0d'

    def _cmd_init(self):
        """ESC @ - Drucker initialisieren"""
        return self.ESC + b'@'

    def _cmd_bold_on(self):
        """ESC E 1 - Fettdruck an"""
        return self.ESC + b'E\x01'

    def _cmd_bold_off(self):
        """ESC E 0 - Fettdruck aus"""
        return self.ESC + b'E\x00'

    def _cmd_font_a(self):
        """ESC M 0 - Font A (Standard)"""
        return self.ESC + b'M\x00'

    def _cmd_font_b(self):
        """ESC M 1 - Font B (Schmal)"""
        return self.ESC + b'M\x01'

    def _cmd_align_left(self):
        """ESC a 0 - Linksbuendig"""
        return self.ESC + b'a\x00'

    def _cmd_align_center(self):
        """ESC a 1 - Zentriert"""
        return self.ESC + b'a\x01'

    def _cmd_double_width_on(self):
        """SO (0x0E) - Doppelte Breite an"""
        return b'\x0e'

    def _cmd_double_width_off(self):
        """DC4 (0x14) - Doppelte Breite aus"""
        return b'\x14'

    def _cmd_cut(self):
        """GS V 0 - Papier abschneiden"""
        return self.GS + b'V\x00'

    def _line(self, text):
        """Textzeile mit CR+LF"""
        return text.encode('cp437', errors='replace') + self.CR + self.LF

    def generate_receipt(self,
                         zaehler_nr="11461",
                         beleg_nr="16912",
                         datum="17.09.2025",
                         abgabe_start="13:21:31",
                         abgabe_ende="13:42:43",
                         zaehler_vor_start=0,
                         fuel_type="HEL schwefelarm",
                         menge=183):
        """Erzeugt einen vollstaendigen Beleg als ESC/POS Byte-Stream.

        Das Format basiert auf dem realen Belegbild des Epson TM-U295:

        *Zaehler-Nr. :     11461*
        *Beleg-Nr.   :     16912*
        Abgabe-Datum :  17.09.2025
        Abgabe-Start :    13:21:31
        Abgabe-Ende  :    13:42:43
        *Zaehler vor Start:    0 L*
        *HEL schwefelarm
        Menge bei 15 °C     183 L
        """
        data = bytearray()

        # Drucker initialisieren
        data += self._cmd_init()
        data += self._cmd_font_a()
        data += self._cmd_align_left()

        # Leerzeilen am Anfang (wie beim echten Drucker)
        data += self.LF
        data += self.LF

        # Zaehler-Nr (fett)
        data += self._cmd_bold_on()
        data += self._line(f"*Zaehler-Nr. :     {zaehler_nr}*")
        data += self._cmd_bold_off()

        # Beleg-Nr (fett)
        data += self._cmd_bold_on()
        data += self._line(f"*Beleg-Nr.   :     {beleg_nr}*")
        data += self._cmd_bold_off()

        # Datum
        data += self._line(f"Abgabe-Datum :  {datum}")

        # Abgabe-Start
        data += self._line(f"Abgabe-Start :    {abgabe_start}")

        # Abgabe-Ende
        data += self._line(f"Abgabe-Ende  :    {abgabe_ende}")

        # Zaehler vor Start (fett)
        data += self._cmd_bold_on()
        data += self._line(f"*Zaehler vor Start:    {zaehler_vor_start} L*")
        data += self._cmd_bold_off()

        # Kraftstoffart (fett)
        data += self._cmd_bold_on()
        data += self._line(f"*{fuel_type}")
        data += self._cmd_bold_off()

        # Menge - Grad-Zeichen ist in CP437 Byte 0xF8, wird als raw byte geschrieben
        menge_line = bytearray(f"Menge bei 15 ".encode('cp437'))
        menge_line.append(0xF8)  # Grad-Zeichen in CP437
        menge_line.extend(f"C     {menge} L".encode('cp437'))
        menge_line.extend(self.CR + self.LF)
        data += bytes(menge_line)

        # Leerzeilen und Schnitt
        data += self.LF
        data += self.LF
        data += self._cmd_cut()

        return bytes(data)

    def generate_partial_receipt(self):
        """Erzeugt einen unvollstaendigen Beleg (z.B. Abbruch waehrend Abgabe)."""
        data = bytearray()
        data += self._cmd_init()
        data += self.LF
        data += self._cmd_bold_on()
        data += self._line("*Zaehler-Nr. :     99999*")
        data += self._cmd_bold_off()
        data += self._line("Abgabe-Datum :  01.01.2026")
        # Kein Beleg-Nr, keine Menge => unvollstaendig
        data += self.LF
        data += self._cmd_cut()
        return bytes(data)

    def generate_diesel_receipt(self):
        """Erzeugt einen Diesel-Beleg."""
        return self.generate_receipt(
            zaehler_nr="22501",
            beleg_nr="44001",
            datum="15.03.2026",
            abgabe_start="08:15:00",
            abgabe_ende="08:35:22",
            zaehler_vor_start=15420,
            fuel_type="Diesel",
            menge=950,
        )


# ====== Tests ======

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name):
        self.passed += 1
        print(f"  [OK]  {name}")

    def fail(self, name, reason=""):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  [FEHLER]  {name}: {reason}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"  Ergebnis: {self.passed}/{total} Tests bestanden")
        if self.errors:
            print(f"  Fehlgeschlagen:")
            for name, reason in self.errors:
                print(f"    - {name}: {reason}")
        print(f"{'='*50}")
        return self.failed == 0


def test_escpos_stripping(results):
    """Testet das Entfernen von ESC/POS Steuerzeichen."""
    print("\n--- Test: ESC/POS Steuerzeichen entfernen ---")

    gen = ReceiptGenerator()

    # Test 1: Init-Kommando
    data = gen._cmd_init() + b'Hallo Welt\r\n'
    text = strip_escpos(data)
    if "Hallo Welt" in text:
        results.ok("Init-Kommando wird entfernt")
    else:
        results.fail("Init-Kommando wird entfernt", f"Got: {repr(text)}")

    # Test 2: Bold On/Off
    data = gen._cmd_bold_on() + b'*Test*' + gen._cmd_bold_off() + b'\r\n'
    text = strip_escpos(data)
    if "*Test*" in text:
        results.ok("Bold-Kommandos werden entfernt")
    else:
        results.fail("Bold-Kommandos werden entfernt", f"Got: {repr(text)}")

    # Test 3: Vollstaendiger Beleg-Stream
    receipt_bytes = gen.generate_receipt()
    text = strip_escpos(receipt_bytes)
    if "Zaehler-Nr" in text and "Beleg-Nr" in text and "183 L" in text:
        results.ok("Vollstaendiger Beleg-Stream lesbar")
    else:
        results.fail("Vollstaendiger Beleg-Stream lesbar", f"Missing fields in: {text[:200]}")

    # Test 4: Grad-Zeichen
    data = b'Menge bei 15 \xf8C     500 L\r\n'
    text = strip_escpos(data)
    if "500 L" in text:
        results.ok("CP437 Grad-Zeichen korrekt")
    else:
        results.fail("CP437 Grad-Zeichen korrekt", f"Got: {repr(text)}")


def test_receipt_parsing(results):
    """Testet den Beleg-Parser mit verschiedenen Eingaben."""
    print("\n--- Test: Beleg-Parser ---")

    gen = ReceiptGenerator()

    # Test 1: Standard-HEL-Beleg
    receipt_bytes = gen.generate_receipt()
    text = strip_escpos(receipt_bytes)
    parsed = parse_receipt(text)

    checks = [
        ("zaehler_nr", "11461"),
        ("beleg_nr", "16912"),
        ("datum", "17.09.2025"),
        ("abgabe_start", "13:21:31"),
        ("abgabe_ende", "13:42:43"),
        ("zaehler_vor_start", 0),
        ("fuel_type", "heizoel_leicht"),
        ("menge_liter", 183.0),
    ]
    for field, expected in checks:
        actual = parsed.get(field)
        if actual == expected:
            results.ok(f"HEL-Beleg: {field} = {expected}")
        else:
            results.fail(f"HEL-Beleg: {field}", f"Erwartet {expected}, bekommen {actual}")

    # Test 2: Diesel-Beleg
    diesel_bytes = gen.generate_diesel_receipt()
    text = strip_escpos(diesel_bytes)
    parsed = parse_receipt(text)
    if parsed["fuel_type"] == "diesel":
        results.ok("Diesel-Beleg: fuel_type = diesel")
    else:
        results.fail("Diesel-Beleg: fuel_type", f"Got: {parsed['fuel_type']}")
    if parsed["menge_liter"] == 950.0:
        results.ok("Diesel-Beleg: menge = 950 L")
    else:
        results.fail("Diesel-Beleg: menge", f"Got: {parsed['menge_liter']}")
    if parsed["zaehler_vor_start"] == 15420:
        results.ok("Diesel-Beleg: zaehler_vor_start = 15420")
    else:
        results.fail("Diesel-Beleg: zaehler_vor_start", f"Got: {parsed['zaehler_vor_start']}")

    # Test 3: Vollstaendigkeit
    if is_complete_receipt(parsed):
        results.ok("Diesel-Beleg ist vollstaendig")
    else:
        results.fail("Diesel-Beleg ist vollstaendig")

    # Test 4: Unvollstaendiger Beleg
    partial_bytes = gen.generate_partial_receipt()
    text = strip_escpos(partial_bytes)
    parsed = parse_receipt(text)
    if not is_complete_receipt(parsed):
        results.ok("Unvollstaendiger Beleg korrekt erkannt")
    else:
        results.fail("Unvollstaendiger Beleg korrekt erkannt")

    # Test 5: Reiner Text (ohne ESC/POS)
    raw_text = """
*Zaehler-Nr. :     55555*
*Beleg-Nr.   :     77777*
Abgabe-Datum :  25.12.2025
Abgabe-Start :    10:00:00
Abgabe-Ende  :    10:30:00
*Zaehler vor Start:    100 L*
*HEL schwefelarm
Menge bei 15 °C     500 L
"""
    parsed = parse_receipt(raw_text)
    if parsed["beleg_nr"] == "77777" and parsed["menge_liter"] == 500.0:
        results.ok("Reiner Text ohne ESC/POS parsbar")
    else:
        results.fail("Reiner Text ohne ESC/POS parsbar", f"Got: {parsed}")


def test_sqlite_storage(results):
    """Testet die lokale SQLite-Speicherung."""
    print("\n--- Test: SQLite Speicherung ---")

    # Temporaere DB
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = f.name

    try:
        # Test 1: DB initialisieren
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        if any("receipts" in t[0] for t in tables):
            results.ok("Datenbank-Tabelle erstellt")
        else:
            results.fail("Datenbank-Tabelle erstellt")

        # Test 2: Beleg speichern
        receipt = {
            "zaehler_nr": "11461",
            "beleg_nr": "16912",
            "datum": "17.09.2025",
            "abgabe_start": "13:21:31",
            "abgabe_ende": "13:42:43",
            "zaehler_vor_start": 0,
            "fuel_type": "heizoel_leicht",
            "menge_liter": 183.0,
            "raw_text": "test receipt",
        }
        local_id = store_receipt(db_path, receipt, 50.1234, 8.5678, "Max Mustermann")
        if local_id:
            results.ok("Beleg gespeichert")
        else:
            results.fail("Beleg gespeichert")

        # Test 3: Ungesyncte Belege abrufen
        unsynced = get_unsynced(db_path)
        if len(unsynced) == 1 and unsynced[0]["beleg_nr"] == "16912":
            results.ok("Ungesyncte Belege abrufbar")
        else:
            results.fail("Ungesyncte Belege abrufbar", f"Got: {len(unsynced)}")

        # Test 4: GPS-Daten gespeichert
        if abs(unsynced[0]["gps_lat"] - 50.1234) < 0.001:
            results.ok("GPS-Daten gespeichert")
        else:
            results.fail("GPS-Daten gespeichert")

        # Test 5: Fahrer gespeichert
        if unsynced[0]["fahrer"] == "Max Mustermann":
            results.ok("Fahrer gespeichert")
        else:
            results.fail("Fahrer gespeichert")

        # Test 6: Als synchronisiert markieren
        mark_synced(db_path, [local_id])
        unsynced = get_unsynced(db_path)
        if len(unsynced) == 0:
            results.ok("Beleg als synchronisiert markiert")
        else:
            results.fail("Beleg als synchronisiert markiert")

        # Test 7: Statistiken
        stats = get_stats(db_path)
        if stats["total"] == 1 and stats["unsynced"] == 0:
            results.ok("Statistiken korrekt")
        else:
            results.fail("Statistiken korrekt", f"Got: {stats}")

        # Test 8: Mehrere Belege
        for i in range(5):
            r = dict(receipt)
            r["beleg_nr"] = str(17000 + i)
            store_receipt(db_path, r, 50.0 + i * 0.01, 8.0, "Fahrer")
        stats = get_stats(db_path)
        if stats["total"] == 6 and stats["unsynced"] == 5:
            results.ok("Mehrere Belege gespeichert und gezaehlt")
        else:
            results.fail("Mehrere Belege gespeichert", f"Got: {stats}")

    finally:
        os.unlink(db_path)


def test_sync_payload_format(results):
    """Testet ob das Sync-Payload das richtige Format fuer die API hat."""
    print("\n--- Test: Sync-Payload Format ---")

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = f.name

    try:
        init_db(db_path)

        receipt = {
            "zaehler_nr": "11461",
            "beleg_nr": "16912",
            "datum": "17.09.2025",
            "abgabe_start": "13:21:31",
            "abgabe_ende": "13:42:43",
            "zaehler_vor_start": 0,
            "fuel_type": "heizoel_leicht",
            "menge_liter": 183.0,
            "raw_text": "test",
        }
        store_receipt(db_path, receipt, 50.1234, 8.5678, "Fahrer Test")

        unsynced = get_unsynced(db_path)
        row = unsynced[0]

        # Simuliere die Konvertierung wie in sync_to_portal
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
        }

        # Pruefe das Format
        if api_receipt["fuel_type"] == "heizoel_leicht":
            results.ok("Sync: fuel_type korrekt")
        else:
            results.fail("Sync: fuel_type", f"Got: {api_receipt['fuel_type']}")

        if api_receipt["quantity_liters"] == 183.0:
            results.ok("Sync: quantity_liters korrekt")
        else:
            results.fail("Sync: quantity_liters", f"Got: {api_receipt['quantity_liters']}")

        if api_receipt["date"] == "2025-09-17":
            results.ok("Sync: Datum DD.MM.YYYY -> YYYY-MM-DD")
        else:
            results.fail("Sync: Datum-Konvertierung", f"Got: {api_receipt['date']}")

        if api_receipt["beleg_nr"] == "16912":
            results.ok("Sync: beleg_nr korrekt")
        else:
            results.fail("Sync: beleg_nr", f"Got: {api_receipt['beleg_nr']}")

        if api_receipt["gps_lat"] and abs(api_receipt["gps_lat"] - 50.1234) < 0.001:
            results.ok("Sync: GPS-Daten korrekt")
        else:
            results.fail("Sync: GPS-Daten", f"Got: {api_receipt['gps_lat']}")

        if api_receipt["fahrer"] == "Fahrer Test":
            results.ok("Sync: Fahrer korrekt")
        else:
            results.fail("Sync: Fahrer", f"Got: {api_receipt['fahrer']}")

        if api_receipt["pi_local_id"]:
            results.ok("Sync: pi_local_id vorhanden")
        else:
            results.fail("Sync: pi_local_id fehlt")

        # JSON-Serialisierbarkeit
        try:
            json.dumps(api_receipt)
            results.ok("Sync: Payload JSON-serialisierbar")
        except Exception as e:
            results.fail("Sync: JSON-Serialisierung", str(e))

    finally:
        os.unlink(db_path)


def test_config_loading(results):
    """Testet das Laden der Konfiguration."""
    print("\n--- Test: Konfiguration ---")

    conf = load_config()

    # Standardwerte pruefen
    if conf["serial_baud"] == 9600:
        results.ok("Standard-Baudrate 9600")
    else:
        results.fail("Standard-Baudrate", f"Got: {conf['serial_baud']}")

    if conf["serial_port"] == "/dev/ttyUSB0":
        results.ok("Standard-Port /dev/ttyUSB0")
    else:
        results.fail("Standard-Port", f"Got: {conf['serial_port']}")

    if conf["gps_enabled"] == "true":
        results.ok("GPS standardmaessig aktiv")
    else:
        results.fail("GPS standardmaessig aktiv", f"Got: {conf['gps_enabled']}")

    # Umgebungsvariablen testen
    os.environ["TANKBELEG_API_URL"] = "https://test.example.com"
    os.environ["TANKBELEG_FAHRER"] = "Test Fahrer"
    conf = load_config()
    if conf["api_url"] == "https://test.example.com":
        results.ok("Env-Override: api_url")
    else:
        results.fail("Env-Override: api_url", f"Got: {conf['api_url']}")
    if conf["fahrer_name"] == "Test Fahrer":
        results.ok("Env-Override: fahrer_name")
    else:
        results.fail("Env-Override: fahrer_name", f"Got: {conf['fahrer_name']}")

    # Aufraeumen
    del os.environ["TANKBELEG_API_URL"]
    del os.environ["TANKBELEG_FAHRER"]


def test_edge_cases(results):
    """Testet Grenzfaelle des Parsers."""
    print("\n--- Test: Grenzfaelle ---")

    # Test 1: Leerer Input
    parsed = parse_receipt("")
    if not is_complete_receipt(parsed):
        results.ok("Leerer Input = unvollstaendig")
    else:
        results.fail("Leerer Input")

    # Test 2: Nur Muell-Daten
    parsed = parse_receipt("xxx yyy zzz 123 abc")
    if not is_complete_receipt(parsed):
        results.ok("Muell-Daten = unvollstaendig")
    else:
        results.fail("Muell-Daten")

    # Test 3: Grosse Menge
    text = """
*Beleg-Nr.   :     99999*
Abgabe-Datum :  01.01.2026
Menge bei 15 °C     9999 L
"""
    parsed = parse_receipt(text)
    if parsed["menge_liter"] == 9999.0:
        results.ok("Grosse Menge (9999 L) erkannt")
    else:
        results.fail("Grosse Menge", f"Got: {parsed['menge_liter']}")

    # Test 4: Verschiedene Schreibweisen
    text_variants = [
        ("Abgabe-Datum :  01.01.2026", "01.01.2026"),  # Standard
        ("Absabe-Datum :  15.06.2025", "15.06.2025"),   # Tippfehler wie im echten Beleg
    ]
    for text_line, expected in text_variants:
        parsed = parse_receipt(text_line)
        if parsed["datum"] == expected:
            results.ok(f"Datum-Variante: '{text_line[:20]}...'")
        else:
            results.fail(f"Datum-Variante: '{text_line[:20]}...'", f"Got: {parsed['datum']}")


def test_virtual_serial(results):
    """Testet die virtuelle serielle Kommunikation mit socat."""
    print("\n--- Test: Virtuelle Serielle Schnittstelle ---")

    # Pruefen ob socat verfuegbar ist
    try:
        subprocess.run(["which", "socat"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("  [SKIP] socat nicht installiert (sudo apt install socat)")
        return

    # Virtuelle Ports erstellen
    port_a = "/tmp/vport_pi"
    port_b = "/tmp/vport_sim"

    socat_proc = subprocess.Popen(
        ["socat", "-d",
         f"PTY,raw,echo=0,link={port_a}",
         f"PTY,raw,echo=0,link={port_b}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)

    try:
        if os.path.exists(port_a) and os.path.exists(port_b):
            results.ok("Virtuelle Ports erstellt")
        else:
            results.fail("Virtuelle Ports erstellt")
            return

        import serial

        # Pi-Reader zuerst verbinden
        from tankbeleg_pi import SerialReceiptReader
        reader = SerialReceiptReader(port_a, 9600)
        reader.connect()
        reader.receipt_timeout = 2.0

        # Kurz warten, dann Simulator sendet Daten auf port_b
        time.sleep(0.3)
        gen = ReceiptGenerator()
        receipt_data = gen.generate_receipt()

        sender = serial.Serial(port_b, 9600, timeout=1)
        sender.write(receipt_data)
        sender.flush()

        # Daten lesen (mit Timeout)
        start = time.time()
        raw_data = None
        text_data = None
        while time.time() - start < 8:
            raw, text = reader.read_receipt()
            if text:
                raw_data = raw
                text_data = text
                break
            time.sleep(0.05)

        if text_data:
            results.ok("Daten ueber virtuelle Ports empfangen")

            # Parsen
            parsed = parse_receipt(text_data)
            if parsed["beleg_nr"] == "16912" and parsed["menge_liter"] == 183.0:
                results.ok("Virtuelle Daten korrekt geparst")
            else:
                results.fail("Virtuelle Daten korrekt geparst", f"Got: {parsed}")
        else:
            results.fail("Daten ueber virtuelle Ports empfangen", "Timeout")

        reader.close()
        sender.close()

    finally:
        socat_proc.terminate()
        socat_proc.wait()


def test_api_sync_live(results, api_url):
    """Testet den tatsaechlichen Sync mit dem Portal-Backend."""
    print(f"\n--- Test: Live API Sync ({api_url}) ---")

    import requests

    test_receipt = [{
        "fuel_type": "heizoel_leicht",
        "quantity_liters": 100.0,
        "date": "2026-03-19",
        "time": "14:00:00",
        "beleg_nr": "SIM-TEST-001",
        "abgabe_start": "14:00:00",
        "abgabe_ende": "14:15:00",
        "zaehler_vor_start": 0,
        "fahrer": "Simulator Test",
        "gps_lat": 50.1109,
        "gps_lng": 8.6821,
        "pi_local_id": "simulator-test-001",
        "raw_receipt_data": "Simulator-generierter Testbeleg",
        "notes": "Pi Simulator Test",
    }]

    try:
        resp = requests.post(
            f"{api_url}/api/fuel-receipts/sync",
            json=test_receipt,
            timeout=10,
        )
        if resp.status_code == 200:
            result = resp.json()
            results.ok(f"API Sync: Status 200, created={result.get('created')}, skipped={result.get('skipped')}")
        else:
            results.fail("API Sync", f"Status {resp.status_code}: {resp.text[:100]}")
    except requests.ConnectionError:
        results.fail("API Sync", "Verbindung fehlgeschlagen")
    except Exception as e:
        results.fail("API Sync", str(e))


# ====== Main ======

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Tankbeleg Pi Simulator & Test Suite")
    parser.add_argument("--test-parser", action="store_true", help="Nur Parser testen")
    parser.add_argument("--virtual-serial", action="store_true", help="Virtuelle serielle Ports testen")
    parser.add_argument("--full-test", action="store_true", help="Alle Tests ausfuehren")
    parser.add_argument("--api-url", type=str, default="", help="Portal-URL fuer Live-API-Test")
    parser.add_argument("--generate-sample", action="store_true", help="Beispiel-Beleg auf stdout ausgeben")
    args = parser.parse_args()

    if args.generate_sample:
        gen = ReceiptGenerator()
        data = gen.generate_receipt()
        sys.stdout.buffer.write(data)
        return

    results = TestResults()

    print("=" * 50)
    print("  Tankbeleg Pi - Test Suite")
    print("=" * 50)

    if args.test_parser or args.full_test or not any(vars(args).values()):
        test_escpos_stripping(results)
        test_receipt_parsing(results)
        test_edge_cases(results)
        test_config_loading(results)
        test_sqlite_storage(results)
        test_sync_payload_format(results)

    if args.virtual_serial or args.full_test:
        test_virtual_serial(results)

    if args.api_url:
        test_api_sync_live(results, args.api_url)

    success = results.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
