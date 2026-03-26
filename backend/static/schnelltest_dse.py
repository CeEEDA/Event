#!/usr/bin/env python3
"""
DSE 5510 Schnelltest - Liest alle wichtigen Register aus
Konfiguration: Baud=19200, Parity=N, SlaveID=10 (via P810)
"""
import sys
import struct

try:
    from pymodbus.client import ModbusSerialClient
except ImportError:
    print("pip3 install pymodbus pyserial")
    sys.exit(1)

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"

GREEN  = "\033[92m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# GenComm Register: (page * 256 + offset, count, label, scale, unit, signed)
REGS = [
    # Page 0 - Identification
    (0*256+0,  1, "Modul-ID",              1, "",    False),
    (0*256+1,  1, "Modul-ID 2",            1, "",    False),
    # Page 4 - Instrumentation
    (4*256+0,  1, "Oeldruck",              1, "kPa", True),
    (4*256+1,  1, "Kuehlmitteltemp",       1, "C",   True),
    (4*256+2,  1, "Oeltemperatur",          1, "C",   True),
    (4*256+3,  1, "Kraftstoff-Fuellstand", 1, "%",   False),
    (4*256+5,  1, "Batteriespannung",     0.1, "V",   False),
    (4*256+6,  1, "Drehzahl",              1, "RPM", False),
    (4*256+7,  1, "Generator Frequenz",   0.1, "Hz",  False),
    (4*256+8,  1, "Generator L1-N Spannung", 0.1, "V", False),
    (4*256+9,  1, "Generator L2-N Spannung", 0.1, "V", False),
    (4*256+10, 1, "Generator L3-N Spannung", 0.1, "V", False),
    (4*256+11, 1, "Generator L1-L2 Spannung", 0.1, "V", False),
    (4*256+14, 1, "Generator L1 Strom",   0.1, "A",  False),
    (4*256+15, 1, "Generator L2 Strom",   0.1, "A",  False),
    (4*256+16, 1, "Generator L3 Strom",   0.1, "A",  False),
    (4*256+20, 1, "Generator Erde Strom", 0.1, "A",  False),
    (4*256+24, 1, "Generator kW Gesamt",    1, "kW",  True),
    # Page 5 - Extended Instrumentation
    (5*256+0,  1, "Netz L1-N Spannung",   0.1, "V",  False),
    (5*256+1,  1, "Netz L2-N Spannung",   0.1, "V",  False),
    (5*256+2,  1, "Netz L3-N Spannung",   0.1, "V",  False),
    (5*256+6,  1, "Netz Frequenz",        0.1, "Hz",  False),
    # Page 7 - Run Time / kWh
    (7*256+6,  2, "Betriebsstunden",        1, "s",   False),  # 32-bit
]

def read_reg(client, addr, count, slave):
    try:
        try:
            r = client.read_holding_registers(addr, count=count, slave=slave)
        except TypeError:
            r = client.read_holding_registers(addr, count, unit=slave)
        if r and not r.isError() and r.registers:
            return r.registers
    except:
        pass
    return None


def main():
    print(f"\n{BOLD}DSE 5510 Register-Auslese via P810{RESET}")
    print(f"Port: {PORT} | Baud: 19200 | Paritaet: N | Slave-ID: 10\n")

    client = ModbusSerialClient(
        port=PORT,
        baudrate=19200,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=2,
    )

    if not client.connect():
        print(f"{RED}Port konnte nicht geoeffnet werden{RESET}")
        sys.exit(1)

    print(f"{'Register':<30} {'Adresse':>8} {'Roh':>8} {'Wert':>12}")
    print(f"{'─'*65}")

    success = 0
    total = 0

    for entry in REGS:
        addr, count, label, scale, unit, signed = entry
        total += 1
        regs = read_reg(client, addr, count, 10)

        if regs is None:
            print(f"  {label:<28} {addr:>8}   {RED}---{RESET}")
            continue

        if count == 2 and len(regs) == 2:
            raw = struct.pack(">HH", regs[0], regs[1])
            val_raw = struct.unpack(">I", raw)[0]
        else:
            val_raw = regs[0]
            if signed and val_raw > 32767:
                val_raw = val_raw - 65536

        # 0xFFFF = nicht implementiert
        if val_raw == 65535 or (count == 2 and val_raw == 0xFFFFFFFF):
            print(f"  {label:<28} {addr:>8}   {CYAN}n/a (0xFFFF){RESET}")
            success += 1  # Connection works, just not implemented
            continue

        val = val_raw * scale
        if scale < 1:
            val_str = f"{val:.1f} {unit}"
        elif count == 2 and unit == "s":
            hours = val_raw / 3600.0
            val_str = f"{hours:.1f} h ({val_raw} s)"
        else:
            val_str = f"{int(val)} {unit}"

        success += 1
        print(f"  {label:<28} {addr:>8} {val_raw:>8}   {GREEN}{val_str}{RESET}")

    client.close()

    print(f"\n{'─'*65}")
    print(f"  {success}/{total} Register gelesen")

    if success > 0:
        print(f"\n{GREEN}{BOLD}VERBINDUNG ERFOLGREICH!{RESET}")
        print(f"\n{BOLD}Konfiguration fuer /etc/dse5510.conf:{RESET}")
        print(f"  {CYAN}baud_rate = 19200{RESET}")
        print(f"  {CYAN}slave_id = 10{RESET}")
        print(f"  {CYAN}parity = N{RESET}")
        print(f"\n  {BOLD}sudo nano /etc/dse5510.conf{RESET}")
        print(f"  {BOLD}sudo systemctl restart dse5510_sync{RESET}")
    else:
        print(f"\n{RED}Keine Register konnten gelesen werden{RESET}")


if __name__ == "__main__":
    main()
