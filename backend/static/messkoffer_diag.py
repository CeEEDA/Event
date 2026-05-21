#!/usr/bin/env python3
"""
Messkoffer-Diagnose: Rayleigh RI-F100-C Modbus Live-Test
=========================================================

Liest direkt vom Modbus alle relevanten Register UND zeigt fuer JEDES Register
alle 8 Kombinationen aus:
  - Adress-Offset: 0 (Datenblatt-konform) vs +1 (Doc-Hinweis)
  - Float-Format:  ABCD, CDAB, BADC, DCBA

Damit findest du in 5 Sekunden die richtige Kombination ohne weitere OTA-Zyklen.

NUTZUNG auf dem Pi:
    sudo python3 /opt/messkoffer_diag.py

Oder direkt herunterladen:
    curl -s https://<portal>/static/messkoffer_diag.py > /tmp/diag.py
    sudo python3 /tmp/diag.py

KEINE Konfiguration noetig - liest /etc/messkoffer.conf falls vorhanden,
sonst Defaults (port=/dev/rayleigh, slave=1, 9600 8N1).
"""

import configparser
import struct
import sys
from pathlib import Path

try:
    import minimalmodbus  # type: ignore
    import serial  # type: ignore
except ImportError:
    print("FEHLER: python3-minimalmodbus + python3-serial muessen installiert sein.")
    print("       sudo apt install python3-minimalmodbus python3-serial")
    sys.exit(1)


def load_modbus_config():
    cfg = {
        "port": "/dev/rayleigh",
        "baudrate": 9600,
        "slave_id": 1,
        "parity": "N",
        "stopbits": 1,
        "bytesize": 8,
        "timeout": 2.0,
    }
    p = Path("/etc/messkoffer.conf")
    if p.exists():
        cp = configparser.ConfigParser()
        cp.read(str(p))
        if "messkoffer" in cp:
            s = cp["messkoffer"]
            cfg["port"] = s.get("modbus_port", cfg["port"])
            cfg["baudrate"] = int(s.get("modbus_baudrate", cfg["baudrate"]))
            cfg["slave_id"] = int(s.get("modbus_slave_id", cfg["slave_id"]))
            cfg["parity"] = s.get("modbus_parity", cfg["parity"])
            cfg["stopbits"] = int(s.get("modbus_stopbits", cfg["stopbits"]))
            cfg["bytesize"] = int(s.get("modbus_bytesize", cfg["bytesize"]))
            cfg["timeout"] = float(s.get("modbus_timeout", cfg["timeout"]))
    # Falls /dev/rayleigh nicht existiert: erste ttyACM oder ttyUSB
    if not Path(cfg["port"]).exists():
        import glob
        cands = sorted(glob.glob("/dev/ttyUSB*")) + sorted(glob.glob("/dev/ttyACM*"))
        if cands:
            cfg["port"] = cands[0]
    return cfg


def make_instrument(cfg):
    instr = minimalmodbus.Instrument(cfg["port"], cfg["slave_id"], mode=minimalmodbus.MODE_RTU)
    instr.serial.baudrate = cfg["baudrate"]
    instr.serial.parity = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}[cfg["parity"]]
    instr.serial.bytesize = cfg["bytesize"]
    instr.serial.stopbits = cfg["stopbits"]
    instr.serial.timeout = cfg["timeout"]
    instr.clear_buffers_before_each_transaction = True
    return instr


def decode(words, fmt):
    """Decodiert 2x 16-bit Words als IEEE-754 32-bit Float in gewuenschtem
    Byte-/Word-Order (abcd, cdab, badc, dcba). Returns float oder None.
    """
    if len(words) != 2:
        return None
    w0, w1 = words[0] & 0xFFFF, words[1] & 0xFFFF
    w0b = ((w0 & 0xFF) << 8) | ((w0 >> 8) & 0xFF)
    w1b = ((w1 & 0xFF) << 8) | ((w1 >> 8) & 0xFF)
    raw = {
        "abcd": (w0 << 16) | w1,
        "cdab": (w1 << 16) | w0,
        "badc": (w0b << 16) | w1b,
        "dcba": (w1b << 16) | w0b,
    }[fmt]
    try:
        return struct.unpack(">f", raw.to_bytes(4, "big"))[0]
    except Exception:
        return None


PARAMS = [
    # (Name, Datenblatt-Hex, expected unit/range hint)
    ("V1-N",         0x00, "V"),
    ("V2-N",         0x02, "V"),
    ("V3-N",         0x04, "V"),
    ("Avg V L-N",    0x06, "V"),
    ("I1",           0x10, "A"),
    ("I2",           0x12, "A"),
    ("I3",           0x14, "A"),
    ("Avg I",        0x16, "A"),
    ("kW1",          0x18, "kW"),
    ("Total kW",     0x2A, "kW"),
    ("Total kVA",    0x2C, "kVA"),
    ("Avg PF",       0x36, "(-1..1)"),
    ("Frequency",    0x38, "Hz"),
    ("Total kWh Imp",0x60, "kWh"),
    ("Total kWh Exp",0x62, "kWh"),
]


def main():
    cfg = load_modbus_config()
    print("=" * 76)
    print(" Messkoffer Diagnose - Rayleigh RI-F100-C Live-Modbus-Test")
    print("=" * 76)
    print(f"  Port:     {cfg['port']}")
    print(f"  Baud:     {cfg['baudrate']} {cfg['bytesize']}{cfg['parity']}{cfg['stopbits']}")
    print(f"  Slave:    {cfg['slave_id']}")
    print(f"  Timeout:  {cfg['timeout']}s")
    print("=" * 76)
    try:
        instr = make_instrument(cfg)
    except Exception as e:
        print(f"FEHLER: konnte serielle Verbindung nicht oeffnen: {e}")
        sys.exit(2)

    print()
    print("Lese alle Register zweimal: einmal mit Offset=0 (Datenblatt-konform),")
    print("einmal mit Offset=+1 (Doc-Hinweis 'apply offset of +1'). Fuer jedes")
    print("Ergebnis werden alle 4 Float-Byte-Orderings dekodiert. Plausibler")
    print("Wert ist markiert mit *** wenn er in der erwarteten Groessenordnung")
    print("liegt (z.B. V in 0..300, Hz in 45..65, PF in -1..1).")
    print()
    print(f"{'Param':18s} {'Off':>3s} {'Wire':>5s} {'Words':>13s}  {'abcd':>12s} {'cdab':>12s} {'badc':>12s} {'dcba':>12s}")
    print("-" * 110)

    def plausible(name, val):
        if val is None or not (val == val):  # NaN
            return False
        a = abs(val)
        if "Frequency" in name:
            return 40.0 <= a <= 70.0
        if name.startswith("V") or "L-N" in name:
            return 50.0 <= a <= 280.0
        if name.startswith("I") or "Avg I" in name:
            return 0.0 <= a <= 2000.0
        if "kW" in name and "kWh" not in name:
            return 0.0 <= a <= 5000.0
        if "kVA" in name:
            return 0.0 <= a <= 5000.0
        if "kWh" in name:
            return 0.0 <= a <= 1e9
        if "PF" in name:
            return 0.0 <= a <= 1.5
        return False

    def fmt_val(v, mark):
        if v is None:
            return "    -"
        s = f"{v:.4g}"
        return (s + (" *" if mark else "")).rjust(12)

    for label, addr, unit in PARAMS:
        for off in (0, 1):
            wire = addr + off
            try:
                words = instr.read_registers(wire, 2, functioncode=3)
            except Exception as e:
                # Auf eine Zeile zusammen
                err = str(e).splitlines()[0][:50]
                print(f"{label:18s} {off:>3d} 0x{wire:03X} {'-':>13s}  Modbus-Fehler: {err}")
                continue
            vals = {fmt: decode(words, fmt) for fmt in ("abcd", "cdab", "badc", "dcba")}
            marks = {fmt: plausible(label, vals[fmt]) for fmt in vals}
            words_str = f"[{words[0]:04X} {words[1]:04X}]"
            print(
                f"{label:18s} {off:>3d} 0x{wire:03X} {words_str:>13s}  "
                f"{fmt_val(vals['abcd'], marks['abcd'])}"
                f"{fmt_val(vals['cdab'], marks['cdab'])}"
                f"{fmt_val(vals['badc'], marks['badc'])}"
                f"{fmt_val(vals['dcba'], marks['dcba'])}"
            )

    print()
    print("LEGENDE:")
    print("  Off=0   Wire-Adresse = Datenblatt-Hex (Default des aktuellen Loggers)")
    print("  Off=+1  Wire-Adresse = Datenblatt-Hex + 1 (Doc-Hinweis)")
    print("  *       Wert liegt im plausiblen Bereich fuer diese Messgroesse")
    print()
    print("ERWARTET fuer 230 V Spannung + 50 Hz:")
    print("  V1-N abcd/cdab um die 230, Frequency abcd/cdab um die 50")
    print()
    print("Die Spalte mit den meisten Sternchen ist die korrekte Kombination.")
    print()
    print("Bitte schicke die KOMPLETTE Tabelle zurueck ans Portal-Team.")


if __name__ == "__main__":
    main()
