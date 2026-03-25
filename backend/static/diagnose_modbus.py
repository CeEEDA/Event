#!/usr/bin/env python3
"""
DSE 5510 Modbus RTU Diagnose-Tool
===================================
Testet automatisch verschiedene Slave-IDs, Baudraten und Paritaeten,
um die korrekte Konfiguration des DSE 5510 Controllers zu finden.

Verwendung auf dem Raspberry Pi:
  sudo python3 /opt/dse5510/diagnose_modbus.py

Optionale Parameter:
  --port /dev/ttyUSB0    (Standard: /dev/ttyUSB0)
"""

import sys
import time
import struct
import argparse

try:
    from pymodbus.client import ModbusSerialClient
except ImportError:
    print("FEHLER: pymodbus nicht installiert.")
    print("  pip3 install pymodbus pyserial")
    sys.exit(1)

# DSE 5510 GenComm Register - Page 4 (Basic Instrumentation)
# Battery Voltage ist ein guter Test-Wert (sollte ~12-14V sein)
REG_BATTERY_VOLTAGE = 4 * 256 + 5   # 1029, 16bit, scale 0.1
REG_ENGINE_SPEED    = 4 * 256 + 6   # 1030, RPM
REG_OIL_PRESSURE    = 4 * 256 + 0   # 1024, kPa
REG_COOLANT_TEMP    = 4 * 256 + 1   # 1025, Grad C

# Page 7 - Engine Run Time (guter Test ob Kommunikation steht)
REG_ENGINE_RUN_TIME = 7 * 256 + 6   # 1798, 32bit, Sekunden

BAUD_RATES = [9600, 19200, 38400, 115200, 4800, 2400, 1200]
PARITIES   = [("N", "Keine"), ("E", "Even/Gerade"), ("O", "Odd/Ungerade")]
SLAVE_IDS  = list(range(1, 21))  # 1 bis 20

# Farben fuer Terminal
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def try_read(client, register, count, slave_id):
    """Versucht ein Register zu lesen, gibt (success, registers) zurueck."""
    try:
        import pymodbus
        version = tuple(int(x) for x in pymodbus.__version__.split(".")[:2])
        if version >= (3, 8):
            result = client.read_holding_registers(register, count=count, device_id=slave_id)
        else:
            try:
                result = client.read_holding_registers(register, count, slave=slave_id)
            except TypeError:
                result = client.read_holding_registers(register, count, unit=slave_id)

        if result.isError():
            return False, None
        return True, result.registers
    except Exception:
        return False, None


def test_combination(port, baud, parity, slave_id, timeout=1.5):
    """Testet eine einzelne Kombination aus Baudrate/Paritaet/SlaveID."""
    client = ModbusSerialClient(
        port=port,
        baudrate=baud,
        bytesize=8,
        parity=parity,
        stopbits=1,
        timeout=timeout,
    )

    if not client.connect():
        return None

    # Test 1: Battery Voltage (16bit)
    ok, regs = try_read(client, REG_BATTERY_VOLTAGE, 1, slave_id)
    if ok and regs:
        batt_v = round(regs[0] * 0.1, 1)
        # Test 2: Engine Speed
        ok2, regs2 = try_read(client, REG_ENGINE_SPEED, 1, slave_id)
        rpm = regs2[0] if ok2 and regs2 else "?"
        # Test 3: Coolant Temp
        ok3, regs3 = try_read(client, REG_COOLANT_TEMP, 1, slave_id)
        coolant = regs3[0] if ok3 and regs3 else "?"
        # Test 4: Oil Pressure
        ok4, regs4 = try_read(client, REG_OIL_PRESSURE, 1, slave_id)
        oil = regs4[0] if ok4 and regs4 else "?"
        # Test 5: Run Time (32bit)
        ok5, regs5 = try_read(client, REG_ENGINE_RUN_TIME, 2, slave_id)
        if ok5 and regs5 and len(regs5) == 2:
            raw = struct.pack(">HH", regs5[0], regs5[1])
            run_s = struct.unpack(">I", raw)[0]
            run_h = round(run_s / 3600.0, 1)
        else:
            run_h = "?"

        client.close()
        return {
            "battery_v": batt_v,
            "rpm": rpm,
            "coolant_temp": coolant,
            "oil_pressure_kpa": oil,
            "run_hours": run_h,
        }

    client.close()
    return None


def scan_all(port):
    """Scannt alle Kombinationen und findet die richtige Konfiguration."""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  DSE 5510 Modbus RTU Diagnose{RESET}")
    print(f"{BOLD}  Port: {port}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    # Phase 1: Schnelltest mit gaengigsten Einstellungen
    print(f"{CYAN}Phase 1: Schnelltest (haeufigste Einstellungen){RESET}")
    print(f"{'─'*50}")

    quick_combos = [
        (9600, "N", 10),   # DSE Standard
        (9600, "N", 1),    # Modbus Standard
        (19200, "N", 10),
        (19200, "N", 1),
        (9600, "E", 10),
        (9600, "E", 1),
        (19200, "E", 10),
        (19200, "E", 1),
        (38400, "N", 10),
        (38400, "N", 1),
    ]

    for baud, parity, sid in quick_combos:
        parity_name = dict(PARITIES).get(parity, parity)
        label = f"  Baud={baud} Paritaet={parity_name} SlaveID={sid}"
        sys.stdout.write(f"{label} ... ")
        sys.stdout.flush()

        result = test_combination(port, baud, parity, sid)
        if result:
            print(f"{GREEN}GEFUNDEN!{RESET}")
            print_result(baud, parity, parity_name, sid, result)
            return baud, parity, sid

        print(f"{RED}Keine Antwort{RESET}")
        time.sleep(0.2)

    # Phase 2: Vollstaendiger Scan
    print(f"\n{CYAN}Phase 2: Vollstaendiger Scan (alle Kombinationen){RESET}")
    print(f"{'─'*50}")

    total = len(BAUD_RATES) * len(PARITIES) * len(SLAVE_IDS)
    count = 0

    for baud in BAUD_RATES:
        for parity_code, parity_name in PARITIES:
            for sid in SLAVE_IDS:
                count += 1
                # Ueberspringe bereits in Phase 1 getestete Kombinationen
                if any(b == baud and p == parity_code and s == sid for b, p, s in quick_combos):
                    continue

                label = f"  [{count}/{total}] Baud={baud} P={parity_code} SID={sid}"
                sys.stdout.write(f"\r{label:<55}")
                sys.stdout.flush()

                result = test_combination(port, baud, parity_code, sid, timeout=1.0)
                if result:
                    print(f" {GREEN}GEFUNDEN!{RESET}")
                    print_result(baud, parity_code, parity_name, sid, result)
                    return baud, parity_code, sid

                time.sleep(0.1)

    print(f"\n\n{RED}{BOLD}KEINE VERBINDUNG GEFUNDEN{RESET}")
    print(f"\n{YELLOW}Moegliche Ursachen:{RESET}")
    print(f"  1. Kabel nicht am RS232-Port des DSE 5510 angeschlossen")
    print(f"  2. TX/RX am Kabel vertauscht (Crossover noetig)")
    print(f"  3. USB-RS232-Adapter defekt oder falscher Treiber")
    print(f"  4. DSE 5510 RS232-Schnittstelle deaktiviert")
    print(f"  5. Falscher serieller Port (aktuell: {port})")
    print(f"\n{YELLOW}Diagnose-Tipps:{RESET}")
    print(f"  - Pruefen: ls -la /dev/ttyUSB* /dev/ttyAMA*")
    print(f"  - DSE 5510 Modbus-Einstellungen im Controller-Menue pruefen")
    print(f"  - TX/RX am RS232-Kabel tauschen und erneut testen")
    print(f"  - Anderes USB-RS232-Kabel probieren")
    return None


def print_result(baud, parity_code, parity_name, sid, data):
    """Gibt die gefundene Konfiguration und Messwerte aus."""
    print(f"\n{GREEN}{BOLD}{'='*60}{RESET}")
    print(f"{GREEN}{BOLD}  VERBINDUNG ERFOLGREICH!{RESET}")
    print(f"{GREEN}{BOLD}{'='*60}{RESET}")
    print(f"\n{BOLD}  Konfiguration:{RESET}")
    print(f"    Baudrate:   {CYAN}{baud}{RESET}")
    print(f"    Paritaet:   {CYAN}{parity_name} ({parity_code}){RESET}")
    print(f"    Slave-ID:   {CYAN}{sid}{RESET}")
    print(f"    Format:     {CYAN}8{parity_code}1{RESET}")
    print(f"\n{BOLD}  Aktuelle Messwerte:{RESET}")
    print(f"    Batterie:        {CYAN}{data['battery_v']} V{RESET}")
    print(f"    Drehzahl:        {CYAN}{data['rpm']} RPM{RESET}")
    print(f"    Kuehlmittel:     {CYAN}{data['coolant_temp']} C{RESET}")
    print(f"    Oeldruck:        {CYAN}{data['oil_pressure_kpa']} kPa{RESET}")
    print(f"    Betriebsstunden: {CYAN}{data['run_hours']} h{RESET}")

    print(f"\n{BOLD}  Naechste Schritte:{RESET}")
    print(f"    Die Konfigurationsdatei anpassen:")
    print(f"    {YELLOW}sudo nano /etc/dse5510.conf{RESET}")
    print(f"    Folgende Werte setzen:")
    print(f"    {CYAN}baud_rate = {baud}{RESET}")
    print(f"    {CYAN}slave_id = {sid}{RESET}")
    if parity_code != "N":
        print(f"    {CYAN}parity = {parity_code}{RESET}")
    print(f"\n    Danach den Service neu starten:")
    print(f"    {YELLOW}sudo systemctl restart dse5510_sync{RESET}")
    print(f"{GREEN}{'='*60}{RESET}\n")


def single_test(port, baud, parity, slave_id):
    """Testet eine einzelne Konfiguration detailliert."""
    parity_name = dict(PARITIES).get(parity, parity)
    print(f"\n{BOLD}Einzeltest:{RESET}")
    print(f"  Port:     {port}")
    print(f"  Baud:     {baud}")
    print(f"  Paritaet: {parity_name} ({parity})")
    print(f"  Slave-ID: {slave_id}")
    print(f"{'─'*40}")

    result = test_combination(port, baud, parity, slave_id, timeout=3)
    if result:
        print_result(baud, parity, parity_name, slave_id, result)
    else:
        print(f"\n{RED}Keine Antwort vom DSE 5510{RESET}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DSE 5510 Modbus RTU Diagnose")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serieller Port (Standard: /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, help="Nur diese Baudrate testen")
    parser.add_argument("--parity", choices=["N", "E", "O"], help="Nur diese Paritaet testen")
    parser.add_argument("--slave-id", type=int, help="Nur diese Slave-ID testen")
    args = parser.parse_args()

    if args.baud and args.parity and args.slave_id:
        single_test(args.port, args.baud, args.parity, args.slave_id)
    else:
        scan_all(args.port)
