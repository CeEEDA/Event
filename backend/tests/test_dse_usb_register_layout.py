"""
Regressions-Test fuer die DSE GenComm Register-Offsets im dse_usb_sync.py.
Simuliert eine USB-BULK Antwort und prueft dass die richtigen Register die richtigen
Felder treffen (kein Off-by-Many wie in v1).

Bezug: GenComm.docx Page 4 (Basic Instrumentation), Page 7 (Accumulated).
"""
import importlib.util
import os
import sys
import pytest


def _load_dse_module():
    """Lade das Skript als Modul, ohne main() zu starten."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "static", "dse_usb_sync.py"
    )
    path = os.path.abspath(path)
    spec = importlib.util.spec_from_file_location("dse_usb_sync", path)
    mod = importlib.util.module_from_spec(spec)
    # usb.core ist optional auf dem Build-Server -> stub einfuegen falls noetig
    if "usb" not in sys.modules:
        import types
        usb = types.ModuleType("usb")
        usb.core = types.ModuleType("usb.core")
        usb.util = types.ModuleType("usb.util")
        usb.core.USBError = Exception
        sys.modules["usb"] = usb
        sys.modules["usb.core"] = usb.core
        sys.modules["usb.util"] = usb.util
    spec.loader.exec_module(mod)
    return mod


class FakeConn:
    """Mockt DseUsbConnection.read_registers / read_32bit mit einer Register-Map."""

    def __init__(self, pages: dict):
        # pages: {(page, start_offset_in_block): [u16, u16, ...]}
        self.pages = pages

    def read_registers(self, page, offset, count):
        """Liefere genau das, was das Skript fuer den gegebenen Block angefordert hat."""
        key = (page, offset)
        if key in self.pages:
            return self.pages[key]
        return None

    def read_32bit(self, page, offset):
        block = self.pages.get((page, offset))
        if block and len(block) >= 2:
            return (block[0] << 16) | block[1]
        return None


def test_page4_register_layout_voltages_currents_watts():
    mod = _load_dse_module()
    # Erwartet (laut GenComm-Doku):
    #   Reg 0 = oil_pressure (kPa)     -> 550 → snapshot 550
    #   Reg 1 = coolant_temp           -> 40
    #   Reg 2 = oil_temp               -> 35
    #   Reg 3 = fuel_level             -> 75
    #   Reg 4 = charge_alt_voltage*10  -> 142 → 14.2 V
    #   Reg 5 = battery_voltage*10     -> 140 → 14.0 V
    #   Reg 6 = engine_speed (rpm)     -> 1500
    #   Reg 7 = frequency*10           -> 500 → 50.0 Hz
    #   Reg 8-9   = L1-N voltage*10 (32-bit)   -> 0x0000_08F4 = 2292 → 229.2 V
    #   Reg 10-11 = L2-N voltage*10            -> 0x0000_08F8 = 2296 → 229.6 V
    #   Reg 12-13 = L3-N voltage*10            -> 0x0000_08FC = 2300 → 230.0 V
    #   Reg 14-15 = L1-L2 voltage*10           -> 0x0000_0F8C = 3980 → 398.0 V
    #   Reg 16-17 = L2-L3 voltage*10           -> 0x0000_0F90 = 3984 → 398.4 V
    #   Reg 18-19 = L3-L1 voltage*10           -> 0x0000_0F94 = 3988 → 398.8 V
    # Block 2 (offset 20, count 14):
    #   Reg 20-21 = L1 current*10              -> 0x0000_0064 = 100 → 10.0 A
    #   Reg 22-23 = L2 current*10              -> 0x0000_0066 = 102 → 10.2 A
    #   Reg 24-25 = L3 current*10              -> 0x0000_0068 = 104 → 10.4 A
    #   Reg 26-27 = earth current*10           -> 0x0000_0000 = 0   → 0.0 A
    #   Reg 28-29 = L1 watts (signed)          -> 0x0000_08FC = 2300 W
    #   Reg 30-31 = L2 watts                   -> 0x0000_0906 = 2310 W
    #   Reg 32-33 = L3 watts                   -> 0x0000_0910 = 2320 W
    page4_block_a = [
        550, 40, 35, 75, 142, 140, 1500, 500,
        0x0000, 0x08F4,   # 8-9   L1-N
        0x0000, 0x08F8,   # 10-11 L2-N
        0x0000, 0x08FC,   # 12-13 L3-N
        0x0000, 0x0F8C,   # 14-15 L1-L2
        0x0000, 0x0F90,   # 16-17 L2-L3
        0x0000, 0x0F94,   # 18-19 L3-L1
    ]
    page4_block_b = [
        0x0000, 0x0064,   # 20-21 L1 current
        0x0000, 0x0066,   # 22-23 L2 current
        0x0000, 0x0068,   # 24-25 L3 current
        0x0000, 0x0000,   # 26-27 Earth current
        0x0000, 0x08FC,   # 28-29 L1 watts
        0x0000, 0x0906,   # 30-31 L2 watts
        0x0000, 0x0910,   # 32-33 L3 watts
    ]
    # Page 3 status + Page 6 + Page 7 + Page 8 leer/minimal
    page3 = [0] * 10
    page3[4] = 2  # manual mode
    page3[6] = 0
    page6 = [0x0000, 0x1B40] + [0] * 20  # total_w = 0x1B40 = 6976 W, power_factor = 0
    page7_engine_hours = (3600 * 100)  # 360000s = 100h -> 32-bit
    page7_starts = 12
    page7_kwh = 1000  # 0.1 scale -> 100.0 kWh
    page8 = [0] * 7

    pages = {
        (3, 0): page3,
        (4, 0): page4_block_a,
        (4, 20): page4_block_b,
        (6, 0): page6,
        # Page 7 32-bit reads at offsets 6 (engine hours), 16 (starts), 8 (kwh)
        (7, 6): [(page7_engine_hours >> 16) & 0xFFFF, page7_engine_hours & 0xFFFF],
        (7, 16): [(page7_starts >> 16) & 0xFFFF, page7_starts & 0xFFFF],
        (7, 8): [(page7_kwh >> 16) & 0xFFFF, page7_kwh & 0xFFFF],
        (8, 1): page8,
    }

    conn = FakeConn(pages)
    data = mod.read_all_gencomm(conn)

    # Basic instrumentation
    assert data["oil_pressure"] == 550
    assert data["coolant_temp"] == 40
    assert data["battery_voltage"] == pytest.approx(14.0)
    assert data["frequency"] == pytest.approx(50.0)
    assert data["engine_speed"] == 1500

    # Voltages L-N (must be 229.2 / 229.6 / 230.0 - NOT 0.0 / 220 / 0.0 wie in v1)
    assert data["gen_l1_voltage"] == pytest.approx(229.2)
    assert data["gen_l2_voltage"] == pytest.approx(229.6)
    assert data["gen_l3_voltage"] == pytest.approx(230.0)
    # Voltages L-L (neu in v2)
    assert data["gen_l1_l2_voltage"] == pytest.approx(398.0)
    assert data["gen_l2_l3_voltage"] == pytest.approx(398.4)
    assert data["gen_l3_l1_voltage"] == pytest.approx(398.8)
    # Currents (must be 10.0/10.2/10.4 - NOT 398 / 398 / 398 wie in v1)
    assert data["gen_l1_current"] == pytest.approx(10.0)
    assert data["gen_l2_current"] == pytest.approx(10.2)
    assert data["gen_l3_current"] == pytest.approx(10.4)
    # Watts (must be 2300/2310/2320 - NOT die Strom-Register wie in v1)
    assert data["gen_l1_watts"] == 2300
    assert data["gen_l2_watts"] == 2310
    assert data["gen_l3_watts"] == 2320
    # Total Watts (Page 6 unchanged)
    assert data["gen_total_watts"] == 6976
    # Page 7 - kWh jetzt richtiges Register, Skalierung 0.1
    assert data["energy_kwh"] == pytest.approx(100.0)
    # Hours
    assert data["hours_run"] == pytest.approx(100.0)
    assert data["engine_starts"] == 12
