#!/usr/bin/env python3
"""
Tankbeleg Capture Analyzer
============================
Analysiert eine mit tankbeleg_capture.py aufgenommene .bin-Datei.
Extrahiert Text, identifiziert Bit-Image Bloecke und versucht den
Beleg zu parsen.

Verwendung:
  python3 tankbeleg_analyze.py /tmp/tankbeleg_capture_XYZ.bin
  # oder:
  python3 tankbeleg_analyze.py           # nimmt neueste Datei aus /tmp
"""

import sys
import os
import re
import glob


def strip_escape_sequences(data: bytes) -> bytes:
    """Entfernt ALLE bekannten ESC/POS Kommandos aggressiv."""
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        # ESC (0x1B) - diverse Kommandos
        if b == 0x1B and i + 1 < len(data):
            nxt = data[i + 1]
            # ESC + m n [image] - Bit Image Mode
            if nxt == 0x2B and i + 3 < len(data):
                # m = density, n = bytes per line -> skip
                # Unklar wie viele Bytes folgen - wir skippen bis naechstes ESC
                j = i + 2
                while j < len(data) and data[j] != 0x1B:
                    j += 1
                i = j
                continue
            # ESC @ - init (2 bytes)
            if nxt == 0x40:
                i += 2
                continue
            # ESC J n - feed n dots (3 bytes)
            if nxt == 0x4A:
                i += 3
                continue
            # ESC E n - bold (3 bytes)
            if nxt == 0x45:
                i += 3
                continue
            # ESC M n - font (3 bytes)
            if nxt == 0x4D:
                i += 3
                continue
            # ESC a n - align (3 bytes)
            if nxt == 0x61:
                i += 3
                continue
            # ESC 0B - vertical tab set
            if nxt == 0x0B:
                # Variable laenge - skip bis naechster Whitespace oder ESC
                j = i + 2
                # Heuristik: skip bis 7 bytes (meist 0c 60 c3 21 00)
                i = min(j + 5, len(data))
                continue
            # ESC 03 - end of text
            if nxt == 0x03:
                i += 2
                continue
            # Fallback: ESC + 1 byte
            i += 2
            continue
        # Sening poll Reste
        if b == 0x1B and i + 2 < len(data) and data[i + 1] == 0xB3:
            i += 3
            continue
        # Control chars (< 0x20 ausser CR/LF/TAB) entfernen
        if b < 0x20 and b not in (0x09, 0x0A, 0x0D):
            i += 1
            continue
        # Graphics range 0x80-0xFF: meist Bit-Image-Muell, aber 0xF8 (°) behalten
        if b >= 0x80 and b != 0xF8:
            # Ersetze durch Marker fuer spaetere Analyse
            out.append(ord("?"))
            i += 1
            continue
        out.append(b)
        i += 1
    return bytes(out)


def extract_text_runs(data: bytes, min_len: int = 3) -> list:
    """Findet zusammenhaengende ASCII-Text-Sequenzen."""
    runs = []
    current = bytearray()
    for b in data:
        if 0x20 <= b < 0x7F or b == 0xF8:  # 0xF8 = ° in CP437
            current.append(b)
        else:
            if len(current) >= min_len:
                try:
                    runs.append(bytes(current).decode("cp437", errors="replace"))
                except Exception:
                    pass
            current = bytearray()
    if len(current) >= min_len:
        try:
            runs.append(bytes(current).decode("cp437", errors="replace"))
        except Exception:
            pass
    return runs


def parse_receipt_fields(text: str) -> dict:
    """Versucht Belegfelder zu erkennen."""
    result = {}

    # Zaehler-Nr - 4-5 stellige Zahl, oft von Spaces umgeben
    m = re.search(r"\b(\d{4,6})\b", text)
    if m:
        result["maybe_zaehler_nr"] = m.group(1)

    # Alle Zahlen mit Kontext
    all_numbers = re.findall(r"\d+", text)
    result["all_numbers"] = all_numbers

    # Liter-Angabe
    m = re.search(r"(\d+)\s*L\b", text)
    if m:
        result["menge_liter"] = int(m.group(1))

    # Datum DD.MM.YYYY
    m = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
    if m:
        result["datum"] = m.group(1)

    # Zeiten HH:MM oder HH:MM:SS
    times = re.findall(r"\d{1,2}:\d{2}(?::\d{2})?", text)
    if times:
        result["zeiten"] = times

    # Temperatur
    if "°C" in text or "\xf8C" in text:
        result["has_temp"] = True

    # Fuel-Typ
    for fuel in ["HEL", "Diesel", "HVO", "Heiz"]:
        if fuel.lower() in text.lower():
            result["fuel_hint"] = fuel
            break

    return result


def dump_hex(data: bytes, max_bytes: int = 2048):
    """Hex-Dump im xxd-Stil."""
    print(f"\nHEX-DUMP ({min(len(data), max_bytes)} von {len(data)} Bytes):")
    print("-" * 76)
    for i in range(0, min(len(data), max_bytes), 16):
        chunk = data[i:i + 16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
        print(f"  {i:04x}  {hex_part:<48}  {ascii_part}")
    print("-" * 76)


def main():
    # Datei bestimmen
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        files = sorted(glob.glob("/tmp/tankbeleg_capture_*.bin"),
                       key=os.path.getmtime, reverse=True)
        if not files:
            print("Keine Capture-Datei in /tmp gefunden.")
            sys.exit(1)
        path = files[0]
        print(f"[INFO] Verwende neueste Datei: {path}")

    with open(path, "rb") as f:
        raw = f.read()

    print("=" * 76)
    print(f"  Tankbeleg Analyzer - {path}")
    print("=" * 76)
    print(f"  Groesse: {len(raw)} Bytes")

    # 1. ESC/POS Kommandos strippen
    stripped = strip_escape_sequences(raw)
    print(f"  Nach Escape-Stripping: {len(stripped)} Bytes")

    # 2. Text-Runs extrahieren
    runs = extract_text_runs(stripped, min_len=2)
    print(f"  Text-Fragmente (>=2 Zeichen): {len(runs)}")

    print("\n" + "=" * 76)
    print("  TEXT-FRAGMENTE")
    print("=" * 76)
    for i, r in enumerate(runs):
        cleaned = r.strip()
        if cleaned:
            print(f"  [{i:2d}] '{cleaned}'")

    # 3. Gesamt-Text zusammenfuegen fuer Regex-Matching
    full_text = " ".join(runs)
    print("\n" + "=" * 76)
    print("  ZUSAMMENGEFUEHRTER TEXT")
    print("=" * 76)
    print(full_text)

    # 4. Beleg-Felder parsen
    fields = parse_receipt_fields(full_text)
    print("\n" + "=" * 76)
    print("  ERKANNTE FELDER")
    print("=" * 76)
    for k, v in fields.items():
        print(f"  {k:25s} = {v}")

    # 5. Hex-Dump
    dump_hex(raw)

    # 6. Stripped Hex-Dump
    print("\nSTRIPPED HEX-DUMP:")
    dump_hex(stripped, max_bytes=512)


if __name__ == "__main__":
    main()
