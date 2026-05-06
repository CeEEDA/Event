"""Tests fuer den Fix: 'fuel_type defaultet still auf diesel'.

Bug-Report (Feb 2026): Sening MultiFlow zeigt im Display 'HEL schwefelarm',
aber im Portal landeten 4 Belege als 'Diesel'. Ursache: parse_receipt() und
sync_to_portal() haben fuel_type still auf 'diesel' geforced wenn der
Bitmap-Druck den Kraftstoff nicht erkennen liess.

Diese Tests stellen sicher dass:
1. parse_receipt liefert fuel_type=None wenn Regex nichts findet (kein silent diesel)
2. enrich_receipt_with_heuristics nutzt den konfigurierten default_fuel_type
3. Ohne default_fuel_type: needs_review=True + fuel_type=None
"""
import sys
import tempfile
import os
import pytest

sys.path.insert(0, "/app/backend/static")
import tankbeleg_pi  # noqa: E402


def test_parse_receipt_no_fuel_marker_returns_none():
    """Wenn der Sening-Druck keinen erkennbaren Fuel-Marker enthaelt, darf
    parse_receipt NICHT still 'diesel' setzen."""
    text = "Beleg-Nr.: 16950\nDatum: 06.05.2026\nMenge bei 15 °C 1316 L\n"
    receipt = tankbeleg_pi.parse_receipt(text)
    assert receipt["fuel_type"] is None, "Erwartet None, kein silent 'diesel'"


def test_parse_receipt_recognizes_hel_marker():
    """Korrekter HEL-Druck wird als heizoel_leicht klassifiziert."""
    text = "* HEL schwefelarm *\nMenge bei 15 °C 1316 L\n"
    receipt = tankbeleg_pi.parse_receipt(text)
    assert receipt["fuel_type"] == "heizoel_leicht"


def test_enrich_uses_default_fuel_type():
    """Wenn parser keinen Kraftstoff findet UND default_fuel_type gesetzt ist,
    soll der Default uebernommen werden + needs_review=True (damit der Fahrer
    am Pi-Kiosk noch korrigieren kann falls heute mal Diesel ausgeliefert wird)."""
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "test.sqlite")
        tankbeleg_pi.init_db(db_path)
        conf = {
            "db_path": db_path,
            "abgabe_zeit_pro_liter_sek": 12,
            "abgabe_zeit_einrichtung_sek": 240,
            "default_fuel_type": "heizoel_leicht",
            "beleg_nr_start": "0",
        }
        receipt = {"fuel_type": None, "menge_liter": 1316.0, "needs_review": False, "review_reason": []}
        enriched = tankbeleg_pi.enrich_receipt_with_heuristics(receipt, conf)
        assert enriched["fuel_type"] == "heizoel_leicht", "Default muss greifen"


def test_enrich_no_default_marks_review():
    """Ohne default_fuel_type bleibt fuel_type None und needs_review wird gesetzt
    (damit das Portal den Beleg flagt)."""
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "test.sqlite")
        tankbeleg_pi.init_db(db_path)
        conf = {
            "db_path": db_path,
            "abgabe_zeit_pro_liter_sek": 12,
            "abgabe_zeit_einrichtung_sek": 240,
            "default_fuel_type": "",
            "beleg_nr_start": "0",
        }
        receipt = {"fuel_type": None, "menge_liter": 1316.0, "needs_review": False, "review_reason": []}
        enriched = tankbeleg_pi.enrich_receipt_with_heuristics(receipt, conf)
        assert enriched["fuel_type"] is None
        assert enriched["needs_review"] is True
        assert "Kraftstoff" in (enriched.get("review_reason") or "")


def test_enrich_keeps_existing_fuel_type():
    """Wenn parser bereits 'heizoel_leicht' erkannt hat, darf default_fuel_type
    nichts ueberschreiben (auch wenn anderer Wert konfiguriert)."""
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "test.sqlite")
        tankbeleg_pi.init_db(db_path)
        conf = {
            "db_path": db_path,
            "abgabe_zeit_pro_liter_sek": 12,
            "abgabe_zeit_einrichtung_sek": 240,
            "default_fuel_type": "diesel",  # absichtlich anders
            "beleg_nr_start": "0",
        }
        receipt = {"fuel_type": "heizoel_leicht", "menge_liter": 1316.0, "needs_review": False, "review_reason": []}
        enriched = tankbeleg_pi.enrich_receipt_with_heuristics(receipt, conf)
        assert enriched["fuel_type"] == "heizoel_leicht", "Parser-Wert muss Vorrang haben"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
