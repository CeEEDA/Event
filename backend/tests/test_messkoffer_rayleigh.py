"""Tests fuer Rayleigh RI-F100-C Modbus-Dekodierung im Messkoffer-Logger.

Kritisch ist das Float-Reverse-Word-Format (Doku sagt MSB.LSB), das bei
pymodbus/minimalmodbus nicht direkt von .read_float() abgebildet wird.
Wir lesen Rohregister und konvertieren selbst - dieser Test verriegelt
die korrekte Reihenfolge gegen Regression.

Plus: Sicherstellen dass die Register-Map die Werte enthaelt die der User
verlangt hat:
  Strom L1/L2/L3, Spannung L1/L2/L3, Leistung L1/L2/L3,
  Total kW, Total kVA, Total Cos Phi, Frequenz, kWh.
"""

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "static"))


def test_decode_float_reverse_word_230v():
    """230.0 V als FLOAT REVERSE WORD (MSB.LSB) -> Word-Swap = CDAB.
    Big-Endian-Float fuer 230.0 = 0x43660000.
    Reverse-Word => words = [0x0000, 0x4366] (low word first).
    """
    from messkoffer_logger import _decode_float_reverse_word

    expected = 230.0
    # Standard IEEE754 big-endian: ABCD = 43 66 00 00
    # word_high = 0x4366, word_low = 0x0000
    # Reverse-Word in Modbus = (low_word, high_word) -> [0x0000, 0x4366]
    val = _decode_float_reverse_word([0x0000, 0x4366])
    assert abs(val - expected) < 0.01, f"230V erwartet, bekommen {val}"


def test_decode_float_reverse_word_50hz():
    from messkoffer_logger import _decode_float_reverse_word
    expected = 50.0
    # 50.0 = 0x42480000 -> word_high=0x4248, word_low=0x0000
    val = _decode_float_reverse_word([0x0000, 0x4248])
    assert abs(val - expected) < 0.01, f"50Hz erwartet, bekommen {val}"


def test_decode_float_reverse_word_15_5_kw():
    """Nicht-runder Wert um Genauigkeit zu testen."""
    from messkoffer_logger import _decode_float_reverse_word
    expected = 15.5
    # 15.5 = 0x41780000
    val = _decode_float_reverse_word([0x0000, 0x4178])
    assert abs(val - expected) < 0.01


def test_decode_float_reverse_word_invalid_length():
    from messkoffer_logger import _decode_float_reverse_word
    assert _decode_float_reverse_word([0x1234]) is None
    assert _decode_float_reverse_word([]) is None
    assert _decode_float_reverse_word([1, 2, 3]) is None


def test_register_map_completeness():
    """Alle vom User explizit verlangten Werte muessen in REGISTERS sein."""
    from messkoffer_logger import REGISTERS, PF_REGISTER

    required = [
        "voltage_l1", "voltage_l2", "voltage_l3",
        "current_l1", "current_l2", "current_l3",
        "power_l1_kw", "power_l2_kw", "power_l3_kw",
        "total_kw", "total_kva",
        "frequency",
        "energy_imp_kwh", "energy_exp_kwh",
    ]
    for key in required:
        assert key in REGISTERS, f"Register-Map fehlt: {key}"

    # Average PF (= Total Cos Phi) ist separat im Integer-Set
    assert PF_REGISTER == (0x41D, 1)


def test_register_addresses_match_datasheet():
    """Adressen muessen exakt mit RI-F100-C-COMM-V01.pdf uebereinstimmen."""
    from messkoffer_logger import REGISTERS

    expected = {
        "voltage_l1": 0x00,
        "voltage_l2": 0x02,
        "voltage_l3": 0x04,
        "current_l1": 0x10,
        "current_l2": 0x12,
        "current_l3": 0x14,
        "power_l1_kw": 0x18,
        "power_l2_kw": 0x1A,
        "power_l3_kw": 0x1C,
        "total_kw": 0x2A,
        "total_kva": 0x2C,
        "frequency": 0x36,
        "energy_imp_kwh": 0x60,
        "energy_exp_kwh": 0x62,
    }
    for key, addr in expected.items():
        actual_addr, _wlen = REGISTERS[key]
        assert actual_addr == addr, (
            f"{key}: Datenblatt 0x{addr:02X}, Code 0x{actual_addr:02X}"
        )


def test_map_to_portal_compatibility():
    """map_to_portal muss das identische Portal-Schema produzieren wie der
    alte Shelly-Logger - sonst bricht /energy-monitoring/ingest.
    """
    from messkoffer_logger import map_to_portal

    row = {
        "id": 42,
        "ts": "2026-05-21T12:00:00+00:00",
        "voltage_l1": 230.5, "voltage_l2": 229.8, "voltage_l3": 231.2,
        "current_l1": 12.3, "current_l2": 11.8, "current_l3": 12.1,
        "power_l1_kw": 2.835, "power_l2_kw": 2.71, "power_l3_kw": 2.798,
        "total_kw": 8.343, "total_kva": 8.6,
        "avg_pf": 0.97, "frequency": 50.02,
        "energy_imp_kwh": 12345.67, "energy_exp_kwh": 12.3,
        "gps_lat": 50.1, "gps_lon": 8.7, "gps_alt": 120, "gps_speed": 0, "gps_fix": 3,
    }
    out = map_to_portal(row)

    # Verlangte Felder muessen vorhanden + korrekt sein
    assert out["id"] == 42
    assert out["U_L1"] == 230.5
    assert out["U_L2"] == 229.8
    assert out["U_L3"] == 231.2
    assert out["I_L1"] == 12.3
    assert out["I_L2"] == 11.8
    assert out["I_L3"] == 12.1
    assert abs(out["I_sum"] - 36.2) < 0.01
    assert out["P_L1_kW"] == 2.835
    assert out["P_L2_kW"] == 2.71
    assert out["P_L3_kW"] == 2.798
    assert abs(out["P_sum_kW"] - 8.343) < 0.001
    assert out["Q_sum"] == 8.6
    assert out["F_Hz"] == 50.02
    assert out["PF_total"] == 0.97
    assert out["E_imp_kWh"] == 12345.67
    assert out["E_exp_kWh"] == 12.3
    # GPS
    assert out["gps_lat"] == 50.1
    assert out["gps_lon"] == 8.7
    assert out["gps_alt_m"] == 120
    assert out["gps_speed_mps"] == 0
    assert out["gps_fix"] == 3


def test_map_to_portal_handles_none_values():
    """Wenn Modbus-Read fehlschlaegt, kommen None-Werte rein -> map muss 0
    zurueckgeben statt zu crashen.
    """
    from messkoffer_logger import map_to_portal

    row = {
        "id": 1, "ts": "2026-05-21T12:00:00+00:00",
        "voltage_l1": None, "voltage_l2": None, "voltage_l3": None,
        "current_l1": None, "current_l2": None, "current_l3": None,
        "power_l1_kw": None, "power_l2_kw": None, "power_l3_kw": None,
        "total_kw": None, "total_kva": None,
        "avg_pf": None, "frequency": None,
        "energy_imp_kwh": None, "energy_exp_kwh": None,
        "gps_lat": None, "gps_lon": None, "gps_alt": None, "gps_speed": None, "gps_fix": 0,
    }
    out = map_to_portal(row)
    assert out["U_L1"] == 0 and out["I_L1"] == 0 and out["P_sum_kW"] == 0


def test_script_version_bumped_for_modbus_migration():
    """Major-Bump auf 2.x, da Shelly-HTTP-Migration ein Breaking-Change ist."""
    from messkoffer_logger import SCRIPT_VERSION
    major = int(SCRIPT_VERSION.split(".")[0])
    assert major >= 2, f"Erwartet >=2.x.x fuer Rayleigh-Migration, bekommen {SCRIPT_VERSION}"


def test_struct_format_invariant():
    """Sanity-Check: Big-Endian-Float 230.0 = 0x43660000 - sonst stimmt unser
    Reverse-Word-Algorithmus nicht mehr."""
    raw = struct.pack(">f", 230.0)
    assert raw.hex() == "43660000", f"230.0 als BE-float sollte 43660000 sein, ist {raw.hex()}"
