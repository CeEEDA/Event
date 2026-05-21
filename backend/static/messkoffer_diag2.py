#!/usr/bin/env python3
"""
Messkoffer-Diagnose v2: Sucht die richtigen Mess-Register
==========================================================

Erkenntnis aus Diag v1: Der Meter antwortet auf FC03 an 0x00-0x39 mit den
FC04-Setup-Registern (Slave ID, Page Address Sequence usw.). Die echten
Messdaten muessen woanders liegen.

Dieses Diag v2 testet GEZIELT die Alternativ-Adressen:
  A) FC04 (Input Registers) an den Float-Reverse-Word-Adressen 0x00..0x3A
  B) FC03 an den HEX-Skaliert-Adressen 0x3E8..0x42E (Doc-Tabelle 2)
  C) FC04 an den HEX-Skaliert-Adressen
  D) Slave-ID-Scan an V1-N: 1, 2, 5, 10, 247 (gaengige Defaults)

Damit finden wir die richtige Kombination (Function-Code + Register-Bereich
+ Slave-ID) in EINEM Lauf.

NUTZUNG auf dem Pi:
    sudo systemctl stop messkoffer
    curl -sL https://fuel-truck-deploy.preview.emergentagent.com/api/system/ota/tools/messkoffer_diag2.py -o /tmp/diag2.py
    sudo python3 /tmp/diag2.py
    sudo systemctl start messkoffer
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
    sys.exit(1)


def load_modbus_config():
    cfg = {"port": "/dev/rayleigh", "baudrate": 9600, "slave_id": 1, "parity": "N",
           "stopbits": 1, "bytesize": 8, "timeout": 2.0}
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
    if not Path(cfg["port"]).exists():
        import glob
        cands = sorted(glob.glob("/dev/ttyUSB*")) + sorted(glob.glob("/dev/ttyACM*"))
        if cands:
            cfg["port"] = cands[0]
    return cfg


def make_instrument(cfg, slave_override=None):
    sid = slave_override if slave_override is not None else cfg["slave_id"]
    instr = minimalmodbus.Instrument(cfg["port"], sid, mode=minimalmodbus.MODE_RTU)
    instr.serial.baudrate = cfg["baudrate"]
    instr.serial.parity = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}[cfg["parity"]]
    instr.serial.bytesize = cfg["bytesize"]
    instr.serial.stopbits = cfg["stopbits"]
    instr.serial.timeout = cfg["timeout"]
    instr.clear_buffers_before_each_transaction = True
    return instr


def decode_float(words, fmt):
    if len(words) != 2:
        return None
    w0, w1 = words[0] & 0xFFFF, words[1] & 0xFFFF
    w0b = ((w0 & 0xFF) << 8) | ((w0 >> 8) & 0xFF)
    w1b = ((w1 & 0xFF) << 8) | ((w1 >> 8) & 0xFF)
    raw = {"abcd": (w0 << 16) | w1, "cdab": (w1 << 16) | w0,
           "badc": (w0b << 16) | w1b, "dcba": (w1b << 16) | w0b}[fmt]
    try:
        return struct.unpack(">f", raw.to_bytes(4, "big"))[0]
    except Exception:
        return None


def decode_uint32(words):
    if len(words) != 2:
        return None
    return (words[0] << 16) | words[1]


def try_read(instr, addr, count, fc):
    try:
        return instr.read_registers(addr, count, functioncode=fc), None
    except Exception as e:
        return None, str(e).splitlines()[0][:60]


def fmt_floats(words):
    if not words or len(words) != 2:
        return ""
    parts = []
    for fmt in ("abcd", "cdab", "badc", "dcba"):
        v = decode_float(words, fmt)
        if v is None:
            parts.append(f"{fmt}=?")
        else:
            parts.append(f"{fmt}={v:.4g}")
    return " | ".join(parts)


def main():
    cfg = load_modbus_config()
    print("=" * 80)
    print(" Messkoffer Diagnose v2 - Such-Modus fuer Mess-Register")
    print("=" * 80)
    print(f"  Port:     {cfg['port']}")
    print(f"  Baud:     {cfg['baudrate']} {cfg['bytesize']}{cfg['parity']}{cfg['stopbits']}")
    print(f"  Timeout:  {cfg['timeout']}s")
    print("=" * 80)

    # Test A: FC04 an den Float-Reverse-Word Adressen ===================
    print()
    print(">>> TEST A: FC04 (Input Register) an Mess-Adressen 0x00..0x3A <<<")
    print("    Vermutung: Meter hat FC03/FC04 vertauscht ggue. Doku")
    print()
    try:
        instr = make_instrument(cfg)
    except Exception as e:
        print(f"FEHLER serieller Port: {e}")
        sys.exit(2)

    params_a = [
        ("V1-N",      0x00),
        ("V2-N",      0x02),
        ("V3-N",      0x04),
        ("I1",        0x10),
        ("Total kW",  0x2A),
        ("Avg PF",    0x36),
        ("Frequency", 0x38),
    ]
    for label, addr in params_a:
        for off in (0, 1):
            wire = addr + off
            words, err = try_read(instr, wire, 2, fc=4)
            if err:
                print(f"  {label:14s} off=+{off}  wire=0x{wire:03X} FC4  FEHLER: {err}")
            else:
                hex_words = f"[{words[0]:04X} {words[1]:04X}]"
                print(f"  {label:14s} off=+{off}  wire=0x{wire:03X} FC4  {hex_words}  {fmt_floats(words)}")

    # Test B: FC03 am HEX-skalierten Bereich 0x3E8+ ====================
    print()
    print(">>> TEST B: FC03 an HEX-Skaliert-Bereich 0x3E8..0x428 <<<")
    print("    Doku-Tabelle 2: V1-N in mV, I1 in mA, kW1 in W, Hz int direkt")
    print()
    params_b = [
        ("V1-N (mV)",          0x3E8, "u32"),  # 2 reg HEX
        ("V2-N (mV)",          0x3EA, "u32"),
        ("V3-N (mV)",          0x3EC, "u32"),
        ("Avg V L-N (mV)",     0x3EE, "u32"),
        ("I1 (mA)",            0x3F8, "u32"),
        ("I2 (mA)",            0x3FA, "u32"),
        ("I3 (mA)",            0x3FC, "u32"),
        ("Total kW (W)",       0x412, "u32"),
        ("PF1 (1reg)",         0x41A, "u16"),
        ("Avg PF (1reg)",      0x41D, "u16"),
        ("Frequency (1reg Hz)",0x427, "u16"),
    ]
    for label, addr, typ in params_b:
        for off in (0, 1):
            wire = addr + off
            count = 2 if typ == "u32" else 1
            words, err = try_read(instr, wire, count, fc=3)
            if err:
                print(f"  {label:22s} off=+{off}  wire=0x{wire:03X} FC3  FEHLER: {err}")
            else:
                hex_words = " ".join(f"{w:04X}" for w in words)
                if typ == "u32":
                    u32_be = (words[0] << 16) | words[1]
                    u32_le = (words[1] << 16) | words[0]
                    print(f"  {label:22s} off=+{off}  wire=0x{wire:03X} FC3  [{hex_words}]  u32_be={u32_be}  u32_le={u32_le}")
                else:
                    u16 = words[0]
                    # Frequenz wird oft als Hz*10 oder Hz*100 abgelegt
                    print(f"  {label:22s} off=+{off}  wire=0x{wire:03X} FC3  [{hex_words}]  u16={u16}  Hz?/10={u16/10:.2f}  Hz?/100={u16/100:.2f}  PF?/1000={u16/1000:.3f}")

    # Test C: FC04 am HEX-skalierten Bereich ===========================
    print()
    print(">>> TEST C: FC04 (Input Register) an HEX-Skaliert-Bereich 0x3E8..0x428 <<<")
    print()
    for label, addr, typ in params_b[:5]:  # nur die wichtigsten
        for off in (0, 1):
            wire = addr + off
            count = 2 if typ == "u32" else 1
            words, err = try_read(instr, wire, count, fc=4)
            if err:
                print(f"  {label:22s} off=+{off}  wire=0x{wire:03X} FC4  FEHLER: {err}")
            else:
                hex_words = " ".join(f"{w:04X}" for w in words)
                if typ == "u32":
                    u32_be = (words[0] << 16) | words[1]
                    print(f"  {label:22s} off=+{off}  wire=0x{wire:03X} FC4  [{hex_words}]  u32_be={u32_be}")
                else:
                    print(f"  {label:22s} off=+{off}  wire=0x{wire:03X} FC4  [{hex_words}]  u16={words[0]}")

    # Test D: Slave-ID-Scan ============================================
    print()
    print(">>> TEST D: Slave-ID-Scan an V1-N (0x00, FC3, off=0 und off=+1) <<<")
    print()
    for sid in (1, 2, 3, 5, 10, 247):
        try:
            ti = make_instrument(cfg, slave_override=sid)
        except Exception as e:
            print(f"  Slave={sid:3d}: FEHLER beim Verbinden: {e}")
            continue
        # off=0
        w0, e0 = try_read(ti, 0x00, 2, fc=3)
        # off=+1
        w1, e1 = try_read(ti, 0x01, 2, fc=3)
        # FC4 off=0
        wf, ef = try_read(ti, 0x00, 2, fc=4)
        # Zusammenfassen
        s0 = e0 if e0 else f"[{w0[0]:04X} {w0[1]:04X}] {fmt_floats(w0)}"
        s1 = e1 if e1 else f"[{w1[0]:04X} {w1[1]:04X}] {fmt_floats(w1)}"
        sf = ef if ef else f"[{wf[0]:04X} {wf[1]:04X}] {fmt_floats(wf)}"
        print(f"  Slave={sid:3d}:")
        print(f"    FC3 off=0  -> {s0}")
        print(f"    FC3 off=+1 -> {s1}")
        print(f"    FC4 off=0  -> {sf}")

    print()
    print("HINWEISE ZUR INTERPRETATION:")
    print("  - Plausibler V1-N-Wert ~230 V (abcd/cdab) oder ~230000 (u32 in mV)")
    print("  - Plausibler Frequency-Wert ~50 (Float) oder ~500 (u16 / 10 = 50 Hz)")
    print("  - Plausibler PF-Wert 0..1 (Float) oder 0..1000 (u16 / 1000)")
    print("  - 'Slave reported illegal data address' = Register existiert nicht")
    print("  - 'No communication' = Slave-ID oder Verkabelung falsch")
    print()
    print("Bitte komplette Ausgabe zurueck ans Portal-Team schicken.")


if __name__ == "__main__":
    main()
