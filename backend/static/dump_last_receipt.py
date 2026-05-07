#!/usr/bin/env python3
"""Tankbeleg Diagnostik-Tool.

Nach einem echten Sening-Druck auf dem Pi ausfuehren:
    sudo python3 /opt/tankbeleg_pi/dump_last_receipt.py

Liest den letzten gespeicherten Beleg aus der SQLite-DB und gibt:
- Geparste Werte (beleg_nr, menge_liter, fuel_type, etc.)
- Roh-Hex (alle Bytes wie vom Sening empfangen)
- Roh-ASCII (gleiche Bytes als druckbarer Text + Markierung der Bitmap-Bytes)
- Statistik: ASCII-Bytes vs. Bitmap-Bytes (wenn die Bytecount-Verteilung
  gegen Ende auf 0x80+ kippt, drueckt der Sening Bitmaps statt Text)

Damit sehen wir SOFORT ob die XON/XOFF-Aktivierung wirklich alle Ziffern
liefert oder ob der Sening die Mengen-Endziffern ueberhaupt nicht als
ASCII druckt (was nur Bitmap-Decoding loesen koennte).
"""
import sqlite3
import sys
import os
import argparse
from datetime import datetime

DB_PATH_DEFAULT = "/var/lib/tankbeleg/tankbeleg.sqlite"
# Fallback-Pfade, falls der Default nicht existiert (alte Installationen):
DB_PATH_FALLBACKS = [
    "/var/lib/tankbeleg/tankbeleg.sqlite",
    "/var/lib/tankbeleg_pi/receipts.sqlite",
    "/var/lib/tankbeleg/receipts.sqlite",
    "/opt/tankbeleg/tankbeleg.sqlite",
]


def autodetect_db():
    for p in DB_PATH_FALLBACKS:
        if os.path.exists(p):
            return p
    return DB_PATH_FALLBACKS[0]


def hex_dump(raw_bytes, width=16):
    """Klassischer Hexdump: Offset | Hex | ASCII (nicht-druckbare als '.')."""
    if isinstance(raw_bytes, str):
        try:
            raw_bytes = bytes.fromhex(raw_bytes)
        except ValueError:
            raw_bytes = raw_bytes.encode("latin1", errors="replace")
    lines = []
    for i in range(0, len(raw_bytes), width):
        chunk = raw_bytes[i:i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:06x}  {hex_part:<{width * 3}}  |{ascii_part}|")
    return "\n".join(lines)


def byte_distribution(raw_bytes):
    """Wieviele Bytes sind ASCII (0x20-0x7E)? Wieviele Steuer-Bytes? Wieviele >=0x80 (Bitmap-typisch)?"""
    if isinstance(raw_bytes, str):
        try:
            raw_bytes = bytes.fromhex(raw_bytes)
        except ValueError:
            return {}
    ascii_n = sum(1 for b in raw_bytes if 0x20 <= b <= 0x7E)
    control_n = sum(1 for b in raw_bytes if b < 0x20)
    high_n = sum(1 for b in raw_bytes if b >= 0x80)
    return {
        "total": len(raw_bytes),
        "ascii_printable": ascii_n,
        "control_codes": control_n,
        "high_byte_bitmap": high_n,
        "high_byte_pct": round(high_n / max(len(raw_bytes), 1) * 100, 1),
    }


def find_fuel_markers(raw_bytes):
    """Sucht im ASCII-Anteil nach Kraftstoff-Hinweisen + ihrer Position."""
    if isinstance(raw_bytes, str):
        try:
            raw_bytes = bytes.fromhex(raw_bytes)
        except ValueError:
            return []
    text = "".join(chr(b) if 32 <= b < 127 else " " for b in raw_bytes)
    keywords = ["HEL", "schwefelarm", "Diesel", "HVO", "Heizoel", "Heizoel", "Liter", "L"]
    hits = []
    for kw in keywords:
        idx = text.find(kw)
        if idx >= 0:
            hits.append({"keyword": kw, "byte_offset": idx, "context": text[max(0, idx - 20):idx + len(kw) + 20]})
    return hits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=None, help="Pfad zur SQLite-DB (Auto-Detect wenn weggelassen)")
    parser.add_argument("--limit", type=int, default=1, help="Anzahl Belege rueckwaerts (Default: 1)")
    parser.add_argument("--output", default="/tmp/tankbeleg_dump.txt", help="Datei in die der Dump geschrieben wird")
    args = parser.parse_args()

    db_path = args.db or autodetect_db()

    if not os.path.exists(db_path):
        print(f"ERROR: SQLite-DB nicht gefunden: {db_path}")
        print(f"Auto-Detect Versuche: {DB_PATH_FALLBACKS}")
        print("Pfad pruefen mit: sudo find /var/lib /opt -name '*.sqlite' 2>/dev/null")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM receipts ORDER BY id DESC LIMIT ?", (args.limit,)
    ).fetchall()
    conn.close()

    if not rows:
        print("Keine Belege in der DB gefunden")
        sys.exit(1)

    output_lines = []
    output_lines.append("=" * 78)
    output_lines.append(f"Tankbeleg-Diagnostik · {datetime.now().isoformat()}")
    output_lines.append(f"DB: {db_path} · {len(rows)} Beleg(e)")
    output_lines.append("=" * 78)

    for i, r in enumerate(rows, 1):
        d = dict(r)
        output_lines.append("")
        output_lines.append(f"━━━ Beleg {i} / {len(rows)} ━━━")
        # Geparste Felder
        fields_to_show = [
            "id", "local_id", "beleg_nr", "datum", "abgabe_start", "abgabe_ende",
            "zaehler_nr", "zaehler_vor_start", "menge_liter", "fuel_type",
            "needs_review", "review_reason", "fahrer", "synced",
        ]
        for k in fields_to_show:
            if k in d:
                output_lines.append(f"  {k:<22} = {d.get(k)}")

        # Raw bytes Analyse
        raw_hex = d.get("raw_receipt_hex") or d.get("raw_hex") or ""
        raw_text = d.get("raw_receipt_data") or d.get("raw_data") or ""

        if raw_hex:
            stats = byte_distribution(raw_hex)
            output_lines.append("")
            output_lines.append(f"  Byte-Verteilung: {stats}")
            if stats.get("high_byte_pct", 0) > 5:
                output_lines.append(f"  ⚠ {stats['high_byte_pct']}% Bytes >= 0x80 - Sening hat vermutlich Bitmaps gedruckt")
            else:
                output_lines.append("  ✓ Praktisch kein Bitmap-Druck (<5% High-Bytes)")

            markers = find_fuel_markers(raw_hex)
            if markers:
                output_lines.append("")
                output_lines.append("  Gefundene Schluesselwoerter im ASCII-Strom:")
                for m in markers:
                    output_lines.append(f"    @{m['byte_offset']:>4}: '{m['keyword']}' · '{m['context']}'")
            else:
                output_lines.append("  ⚠ Keine Kraftstoff-Schluesselwoerter im ASCII gefunden")

            output_lines.append("")
            output_lines.append("  --- HEX-DUMP (komplett) ---")
            output_lines.append(hex_dump(raw_hex))

        if raw_text:
            output_lines.append("")
            output_lines.append("  --- ROH-TEXT (parser-eingangsstrom) ---")
            for line in str(raw_text).splitlines():
                output_lines.append(f"  | {line}")

    full_output = "\n".join(output_lines)
    print(full_output)

    try:
        with open(args.output, "w") as f:
            f.write(full_output)
        print("")
        print(f"→ Gespeichert in {args.output}")
        print(f"  Schick mir die Datei: scp {args.output} <dein-host>:")
    except (OSError, IOError) as e:
        print(f"WARN: Datei nicht schreibbar: {e}")


if __name__ == "__main__":
    main()
