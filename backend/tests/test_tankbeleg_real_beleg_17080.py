"""Regressionstest fuer den realen Beleg vom 21.05.2026 (Beleg-Nr 17080,
ID cca1350e-3ae3-45d5-b20b-4bd717a4d85d) der mit einer alten Pi-Version
(< v1.7.13) als "15 L" statt korrekt "150 L" erkannt wurde.

Das Bitmap-Suffix '83 2c 0c 72 d3' (Format A5, 5-Byte) hinter ASCII '15' muss
zur Ziffer '0' dekodiert werden, so dass die Gesamtmenge 150,0 L ergibt.

Wenn dieser Test FAILS, hat sich entweder die Pi-Parser-Logik regressed oder
das Sening-Bitmap-Format hat sich geaendert.
"""

import os
import sys

# Pi-Skript ist in /app/backend/static
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "static"))


def test_real_beleg_17080_150L():
    """Echter Hex-Dump aus dem Hardware-Test 21.05.2026 - 150 L Heizoel leicht.

    Pattern: ASCII '15' + Bitmap [83 2c 0c 72 d3] = '0' -> Gesamt 150 L.
    """
    from tankbeleg_pi import parse_receipt_sening, SCRIPT_VERSION  # noqa

    hex_str = (
        "11 ff 11 ff 1b 03 b7 d8 cc 9a 30 db 6c 66 8d 00"
        " ff 1b 0b 0c 60 c3 21 00 6d 16 31 c0 1b 4a 1c 0d"
        " 1b 0b 0c 60 c3 21 00 ff 2a 5a 0b 57 33 ed 6c 65"
        " 93 d6 31 32 ce 2e 20 20 20 3a 03 0e 72 c8 20 20"
        " 20 20 20 20 20 20 20 31 31 34 36 8b 4e f9 1b"
        " 0b 0c 60 c3 21 00 6d 16 31 c0 1b 4a 0c 6b 6e 58"
        " c4 00 1b 0b 0c e0 2a 42 2b c6 b3 66 76 8b 4e 93"
        " e6 31 e4 20 20 20 20 3a 03 0e 72 c8 20 20 20 20"
        " 20 20 20 20 20 20 31 37 30 b3 cc 63 e5 1b 0b 0c"
        " 60 c3 21 00 6d 16 31 c0 1b 4a 0a 6b 6e 58 c4 00"
        " 1b 0b 0c 60 90 62 67 61 62 65 6b 8c 64 d8 74 ab"
        " d7 3b e4 20 3a 03 0e 72 c8 20 20 20 20 20 32 31"
        " 2e 83 ac 63 31 e6 30 32 36 ff 1b 0b 0c 60 c3 21"
        " 00 6d 16 31 c0 1b 4a 09 6b 6e 58 c4 00 1b 0b 0c"
        " 60 90 62 67 61 62 65 6b 6c 65 9d 61 72 a3 06 39"
        " e4 3a 20 20 20 20 20 20 20 20 20 31 30 d3 4c"
        " 73 63 1d 32 36 ff 1b 0b 0c 60 c3 21 00 6d 16 31"
        " c0 1b 4a 0c 6b 6e 58 c4 00 1b 0b 0c 60 90 62 67"
        " 61 62 65 6b ac 74 3b d9 65 03 0e 72 c8 3a 03 0e"
        " 72 c8 20 20 20 20 20 20 20 31 30 d3 ac 63 e6 3a"
        " 32 39 ff 1b 0b 0c 60 c3 21 00 6d 16 31 c0 1b 4a"
        " 09 6b 6e 58 c4 00 1b 0b 0c f1 2a 5a 0b 57 33 ed"
        " 6c 65 93 06 39 77 33 ce 20 53 a3 16 3b ce 74 3a"
        " 03 0e 63 c8 4c 2a 1b 0b 0c 60 c3 21 00 6d 16 31"
        " c0 1b 4a 16 0d 1b 0b 0c 60 c3 21 00 ff 2a 48 2b"
        " c7 3a e4 73 63 43 77 56 33 66 99 6c 0b 27 d6 3b"
        " e4 20 20 20 20 20 20 20 20 20 20 20 20 20 20 20"
        " 20 20 2a 1b 0b 0c 60 c3 21 00 6d 16 31 c0 1b 4a"
        " 09 6b fe 1b 0b 0c 60 c3 21 00 6d 16 31 c0 0d 1b"
        " 0b 0c 60 c3 21 10 2a 4d 2b e6 bb 76 99 20 62 65"
        " 4b 06 b9 e6 35 20 f8 43 20 20 20 20 20 20 20 20"
        " 20 20 31 35 83 2c 0c 72 d3 20 20 2a 1b 0b 0c 60"
        " c3 21 00 6d 16 31 c0 1b 4a 13 0d 1b 0b 0c 60 c3"
        " 21 10 1b 0b 0c 60 c3 21 00 6d 16 31 c0 1b 4a 13"
        " 0d 1b 0b 0c 60 c3 21 00 6d 16 31 c0 1b 4a 05 6b"
        " 6e 98 74 c0 0c ff 58 c4 00 1b 0b 0c e0"
    )
    raw = bytes.fromhex(hex_str)
    result = parse_receipt_sening(raw)

    assert result["menge_liter"] == 150.0, (
        f"Erwartete 150.0 L, bekommen {result['menge_liter']!r}. "
        f"Pi-Skript-Version: {SCRIPT_VERSION}"
    )
    assert result["needs_review"] is False, (
        f"Beleg sollte ohne Review-Flag durchgehen, ist aber: "
        f"{result.get('review_reason')}"
    )


def test_a5_pattern_83_2c_0c_72_d3_decodes_to_zero():
    """Direkter Unit-Test des Sening A5-Bitmap-Patterns aus dem realen Beleg."""
    from tankbeleg_pi import decode_sening_bitmap_digit

    digit = decode_sening_bitmap_digit(bytes([0x83, 0x2c, 0x0c, 0x72, 0xd3]))
    assert digit == "0", f"Erwartet '0', bekommen {digit!r}"
