#!/usr/bin/env python3
"""
DSE 5510 Register-Auslese via Raw Serial (ohne pymodbus)
Nutzt direkte Modbus RTU Frames ueber serial.
Konfiguration: Baud=19200, Parity=N, SlaveID=10 (via P810)
"""
import sys
import struct
import time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
BAUD = int(sys.argv[2]) if len(sys.argv) > 2 else 19200
SLAVE = 10

GREEN  = "\033[92m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# GenComm Register: (page * 256 + offset, count, label, scale, unit, signed)
REGS = [
    (0*256+0,  1, "Modul-ID",              1, "",    False),
    (0*256+1,  1, "Modul-ID 2",            1, "",    False),
    (4*256+0,  1, "Oeldruck",              1, "kPa", True),
    (4*256+1,  1, "Kuehlmitteltemp",       1, "C",   True),
    (4*256+2,  1, "Oeltemperatur",          1, "C",   True),
    (4*256+3,  1, "Kraftstoff",            1, "%",   False),
    (4*256+5,  1, "Batteriespannung",     0.1, "V",   False),
    (4*256+6,  1, "Drehzahl",              1, "RPM", False),
    (4*256+7,  1, "Gen Frequenz",         0.1, "Hz",  False),
    (4*256+8,  1, "Gen L1-N Spannung",    0.1, "V",  False),
    (4*256+9,  1, "Gen L2-N Spannung",    0.1, "V",  False),
    (4*256+10, 1, "Gen L3-N Spannung",    0.1, "V",  False),
    (4*256+11, 1, "Gen L1-L2 Spannung",   0.1, "V",  False),
    (4*256+12, 1, "Gen L2-L3 Spannung",   0.1, "V",  False),
    (4*256+13, 1, "Gen L3-L1 Spannung",   0.1, "V",  False),
    (4*256+14, 1, "Gen L1 Strom",         0.1, "A",  False),
    (4*256+15, 1, "Gen L2 Strom",         0.1, "A",  False),
    (4*256+16, 1, "Gen L3 Strom",         0.1, "A",  False),
    (4*256+20, 1, "Gen Erde Strom",       0.1, "A",  False),
    (4*256+24, 1, "Gen kW Gesamt",          1, "kW",  True),
    (5*256+0,  1, "Netz L1-N Spannung",   0.1, "V",  False),
    (5*256+1,  1, "Netz L2-N Spannung",   0.1, "V",  False),
    (5*256+2,  1, "Netz L3-N Spannung",   0.1, "V",  False),
    (5*256+6,  1, "Netz Frequenz",        0.1, "Hz",  False),
    (7*256+6,  2, "Betriebsstunden",        1, "s",   False),
]


def calc_crc(data):
    """Modbus RTU CRC16"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack("<H", crc)


def read_register(ser, slave, addr, count):
    """Liest Modbus Holding Register via rohem Serial."""
    # FC03 Read Holding Registers
    frame = struct.pack(">BBHH", slave, 0x03, addr, count)
    frame += calc_crc(frame)

    ser.reset_input_buffer()
    ser.write(frame)

    # Warten auf Antwort (DSE braucht etwas Zeit)
    time.sleep(0.15)

    # Erwartete Antwortlaenge: slave(1) + fc(1) + byte_count(1) + data(count*2) + crc(2)
    expected = 3 + count * 2 + 2
    response = ser.read(expected + 10)  # etwas mehr lesen fuer Sicherheit

    if len(response) < 5:
        return None

    # Pruefen: Slave-ID und Function Code
    if response[0] != slave:
        return None

    # Error Response?
    if response[1] & 0x80:
        return None

    if response[1] != 0x03:
        return None

    byte_count = response[2]
    if byte_count != count * 2:
        return None

    # CRC pruefen
    data_len = 3 + byte_count
    if len(response) < data_len + 2:
        return None

    payload = response[:data_len]
    crc_recv = response[data_len:data_len+2]
    crc_calc = calc_crc(payload)
    if crc_recv != crc_calc:
        return None

    # Register-Werte extrahieren
    regs = []
    for i in range(count):
        val = struct.unpack(">H", response[3 + i*2 : 5 + i*2])[0]
        regs.append(val)

    return regs


def main():
    print(f"\n{BOLD}DSE 5510 Register-Auslese (Raw Serial){RESET}")
    print(f"Port: {PORT} | Baud: {BAUD} | Paritaet: N | Slave-ID: {SLAVE}\n")

    try:
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUD,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=1,
        )
    except Exception as e:
        print(f"{RED}Port-Fehler: {e}{RESET}")
        sys.exit(1)

    # Port oeffnen und kurz warten
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.5)

    print(f"  {'Register':<28} {'Adr':>6} {'Roh':>8}   {'Wert'}")
    print(f"  {'─'*62}")

    success = 0
    total = 0

    for addr, count, label, scale, unit, signed in REGS:
        total += 1
        regs = read_register(ser, SLAVE, addr, count)

        if regs is None:
            print(f"  {label:<28} {addr:>6}          {RED}Keine Antwort{RESET}")
            continue

        if count == 2 and len(regs) == 2:
            raw = struct.pack(">HH", regs[0], regs[1])
            val_raw = struct.unpack(">I", raw)[0]
        else:
            val_raw = regs[0]
            if signed and val_raw > 32767:
                val_raw = val_raw - 65536

        # GenComm n/a Sentinel-Werte
        NA_UNSIGNED = {65535, 65534, 65533, 65531}  # 0xFFFF, 0xFFFE, 0xFFFD, 0xFFFB
        NA_SIGNED = {32763, 32764, 32765, 32766, 32767}  # 0x7FFB-0x7FFF

        if val_raw in NA_UNSIGNED or (count == 2 and val_raw >= 0xFFFFFFFE):
            print(f"  {label:<28} {addr:>6}   0x{regs[0]:04X}   {CYAN}n/a{RESET}")
            success += 1
            continue

        if signed and regs[0] in NA_SIGNED:
            print(f"  {label:<28} {addr:>6}   0x{regs[0]:04X}   {CYAN}n/a (Sensor inaktiv){RESET}")
            success += 1
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
        print(f"  {label:<28} {addr:>6} {val_raw:>8}   {GREEN}{val_str}{RESET}")

    ser.close()

    print(f"\n  {'─'*62}")
    print(f"  {GREEN}{success}{RESET}/{total} Register gelesen\n")

    if success > 0:
        print(f"  {GREEN}{BOLD}VERBINDUNG ERFOLGREICH!{RESET}")
        print(f"\n  Konfiguration fuer /etc/dse5510.conf:")
        print(f"    {CYAN}baud_rate = {BAUD}{RESET}")
        print(f"    {CYAN}slave_id = {SLAVE}{RESET}")
        print(f"    {CYAN}parity = N{RESET}")
        print(f"\n  Danach:")
        print(f"    sudo systemctl restart dse5510_sync\n")
    else:
        print(f"  {RED}Keine Register gelesen{RESET}\n")


if __name__ == "__main__":
    main()
