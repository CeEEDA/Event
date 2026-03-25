#!/usr/bin/env python3
"""
DSE 5510 Modbus RTU Tiefendiagnose v2
========================================
Erweiterte Diagnose:
  1. Roher Seriell-Test (pruefen ob ueberhaupt Daten ankommen)
  2. Function Code 3 (Holding Registers) UND 4 (Input Registers)
  3. GenComm Page 0 (Identifikation) + Page 4 (Messwerte)
  4. Verschiedene Register-Offsets (0-basiert und 1-basiert)
  5. Null-Modem Erkennung

Auf dem Pi ausfuehren:
  sudo systemctl stop dse5510_sync
  sudo /opt/dse5510/venv/bin/python3 /opt/dse5510/diagnose_modbus.py
"""

import sys
import time
import struct
import argparse
import serial

try:
    from pymodbus.client import ModbusSerialClient
except ImportError:
    print("FEHLER: pymodbus nicht installiert.")
    print("  pip3 install pymodbus pyserial")
    sys.exit(1)

# Farben
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"


# =============================================
# Phase 0: Roher Seriell-Test
# =============================================
def raw_serial_test(port, baud, parity):
    """Sendet ein rohes Modbus-Request-Frame und prueft ob Bytes zurueckkommen."""
    parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}

    # Modbus RTU Frame: SlaveID=10, FC=03, StartReg=0x0400(1024), Count=1
    # CRC wird berechnet
    frame_sid10 = bytes([0x0A, 0x03, 0x04, 0x00, 0x00, 0x01])
    frame_sid1  = bytes([0x01, 0x03, 0x04, 0x00, 0x00, 0x01])

    def calc_crc(data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return struct.pack("<H", crc)

    try:
        ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=8,
            parity=parity_map.get(parity, serial.PARITY_NONE),
            stopbits=1,
            timeout=2,
        )
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        results = []
        for label, frame in [("SlaveID=10", frame_sid10), ("SlaveID=1", frame_sid1)]:
            full_frame = frame + calc_crc(frame)
            ser.write(full_frame)
            time.sleep(0.5)
            response = ser.read(256)
            results.append((label, full_frame, response))

        ser.close()
        return results
    except Exception as e:
        return [("Fehler", b"", str(e).encode())]


# =============================================
# Phase 1: Modbus Scan mit FC3 + FC4
# =============================================

# GenComm Register-Adressen
REGISTERS = {
    "Page0_ModuleID":     (0 * 256 + 0, 1, "Modul-Identifikation"),
    "Page0_Ident1":       (0 * 256 + 5, 1, "Ident Register 5"),
    "Page4_OilPress":     (4 * 256 + 0, 1, "Oeldruck (kPa)"),
    "Page4_CoolantTemp":  (4 * 256 + 1, 1, "Kuehlmitteltemp (C)"),
    "Page4_BattVoltage":  (4 * 256 + 5, 1, "Batteriespannung (x0.1V)"),
    "Page4_RPM":          (4 * 256 + 6, 1, "Drehzahl (RPM)"),
    "Page4_Frequency":    (4 * 256 + 9, 1, "Frequenz (x0.1Hz)"),
    "Page4_VoltageL1":    (4 * 256 + 10, 1, "Spannung L1 (x0.1V)"),
    "Reg0":               (0, 1, "Register 0 (Adresse 0)"),
    "Reg1":               (1, 1, "Register 1 (Adresse 1)"),
    "Reg40001":           (0, 1, "40001 (Holding Reg 0)"),
}

BAUD_RATES = [9600, 19200, 38400, 115200, 4800]
PARITIES   = [("N", "Keine"), ("E", "Even"), ("O", "Odd")]
SLAVE_IDS  = [10, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 15, 16, 20]


def try_read_fc3(client, register, count, slave_id):
    """Holding Registers (Function Code 3)"""
    try:
        try:
            result = client.read_holding_registers(register, count=count, slave=slave_id)
        except TypeError:
            try:
                result = client.read_holding_registers(register, count, slave=slave_id)
            except TypeError:
                result = client.read_holding_registers(register, count, unit=slave_id)
        if result and not result.isError():
            return True, result.registers
    except Exception:
        pass
    return False, None


def try_read_fc4(client, register, count, slave_id):
    """Input Registers (Function Code 4)"""
    try:
        try:
            result = client.read_input_registers(register, count=count, slave=slave_id)
        except TypeError:
            try:
                result = client.read_input_registers(register, count, slave=slave_id)
            except TypeError:
                result = client.read_input_registers(register, count, unit=slave_id)
        if result and not result.isError():
            return True, result.registers
    except Exception:
        pass
    return False, None


def scan_modbus(port):
    """Hauptscan: Alle Kombinationen mit FC3 und FC4."""
    total_combos = len(BAUD_RATES) * len(PARITIES) * len(SLAVE_IDS) * 2  # x2 fuer FC3+FC4
    count = 0

    for baud in BAUD_RATES:
        for parity_code, parity_name in PARITIES:
            client = ModbusSerialClient(
                port=port,
                baudrate=baud,
                bytesize=8,
                parity=parity_code,
                stopbits=1,
                timeout=1.5,
            )
            if not client.connect():
                print(f"  {RED}Port konnte nicht geoeffnet werden: {port}{RESET}")
                continue

            for sid in SLAVE_IDS:
                count += 1
                label = f"[{count}/{total_combos}] Baud={baud} P={parity_code} SID={sid}"

                # FC3: Holding Registers
                for reg_name, (reg_addr, reg_count, reg_desc) in REGISTERS.items():
                    sys.stdout.write(f"\r  {DIM}{label} FC3 {reg_name:<25}{RESET}")
                    sys.stdout.flush()

                    ok, regs = try_read_fc3(client, reg_addr, reg_count, sid)
                    if ok and regs:
                        print(f"\r  {GREEN}GEFUNDEN! FC3 | Baud={baud} P={parity_name} SID={sid} | {reg_desc} = {regs[0]}{RESET}")
                        # Lese weitere Register
                        print_full_readout(client, baud, parity_code, parity_name, sid, "FC3", try_read_fc3)
                        client.close()
                        return baud, parity_code, sid, "FC3"

                # FC4: Input Registers
                for reg_name, (reg_addr, reg_count, reg_desc) in REGISTERS.items():
                    sys.stdout.write(f"\r  {DIM}{label} FC4 {reg_name:<25}{RESET}")
                    sys.stdout.flush()

                    ok, regs = try_read_fc4(client, reg_addr, reg_count, sid)
                    if ok and regs:
                        print(f"\r  {GREEN}GEFUNDEN! FC4 | Baud={baud} P={parity_name} SID={sid} | {reg_desc} = {regs[0]}{RESET}")
                        print_full_readout(client, baud, parity_code, parity_name, sid, "FC4", try_read_fc4)
                        client.close()
                        return baud, parity_code, sid, "FC4"

                time.sleep(0.05)

            client.close()

    print(f"\r{'':60}")
    return None


def print_full_readout(client, baud, parity_code, parity_name, sid, fc_label, read_fn):
    """Gibt alle lesbaren Register aus."""
    print(f"\n{GREEN}{BOLD}{'='*60}{RESET}")
    print(f"{GREEN}{BOLD}  VERBINDUNG ERFOLGREICH!{RESET}")
    print(f"{GREEN}{BOLD}{'='*60}{RESET}")
    print(f"\n{BOLD}  Konfiguration:{RESET}")
    print(f"    Baudrate:       {CYAN}{baud}{RESET}")
    print(f"    Paritaet:       {CYAN}{parity_name} ({parity_code}){RESET}")
    print(f"    Slave-ID:       {CYAN}{sid}{RESET}")
    print(f"    Function Code:  {CYAN}{fc_label}{RESET}")
    print(f"    Format:         {CYAN}8{parity_code}1{RESET}")

    print(f"\n{BOLD}  Messwerte:{RESET}")
    for reg_name, (reg_addr, reg_count, reg_desc) in REGISTERS.items():
        ok, regs = read_fn(client, reg_addr, reg_count, sid)
        val = regs[0] if ok and regs else "---"
        marker = f"{GREEN}{val}{RESET}" if ok else f"{RED}{val}{RESET}"
        print(f"    {reg_desc:30s}: {marker}")

    print(f"\n{BOLD}  Naechste Schritte:{RESET}")
    print(f"    {YELLOW}sudo nano /etc/dse5510.conf{RESET}")
    print(f"    {CYAN}baud_rate = {baud}{RESET}")
    print(f"    {CYAN}slave_id = {sid}{RESET}")
    if parity_code != "N":
        print(f"    {CYAN}parity = {parity_code}{RESET}")
    if fc_label == "FC4":
        print(f"    {YELLOW}WICHTIG: Das Sync-Skript muss auf FC4 (Input Registers) umgestellt werden!{RESET}")
    print(f"\n    {YELLOW}sudo systemctl restart dse5510_sync{RESET}")
    print(f"{GREEN}{'='*60}{RESET}\n")


# =============================================
# Hauptprogramm
# =============================================
def main():
    parser = argparse.ArgumentParser(description="DSE 5510 Modbus RTU Tiefendiagnose v2")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serieller Port (Standard: /dev/ttyUSB0)")
    args = parser.parse_args()
    port = args.port

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  DSE 5510 Modbus RTU Tiefendiagnose v2{RESET}")
    print(f"{BOLD}  Port: {port}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    # ── Phase 0: Roher Seriell-Test ──
    print(f"\n{CYAN}{BOLD}Phase 0: Roher Seriell-Test{RESET}")
    print(f"{'─'*50}")
    print(f"  Sende rohe Modbus-Frames und pruefe ob Antwort kommt...\n")

    any_response = False
    for baud in [9600, 19200]:
        for parity_code, parity_name in [("N", "Keine"), ("E", "Even")]:
            results = raw_serial_test(port, baud, parity_code)
            for label, sent, response in results:
                if isinstance(response, bytes) and len(response) > 0:
                    hex_resp = response.hex(" ")
                    print(f"  {GREEN}ANTWORT bei Baud={baud} P={parity_name} {label}:{RESET}")
                    print(f"    Gesendet:  {sent.hex(' ')}")
                    print(f"    Empfangen: {hex_resp} ({len(response)} Bytes)")

                    # Modbus Error Response?
                    if len(response) >= 5 and (response[1] & 0x80):
                        error_code = response[2]
                        error_names = {1: "Illegal Function", 2: "Illegal Data Address", 3: "Illegal Data Value", 4: "Slave Device Failure"}
                        ename = error_names.get(error_code, f"Code {error_code}")
                        print(f"    {YELLOW}Modbus Fehler-Antwort: {ename}{RESET}")
                        if error_code == 2:
                            print(f"    {YELLOW}-> Register-Adresse ungueltig. Anderer Register-Bereich noetig.{RESET}")

                    any_response = True
                else:
                    sys.stdout.write(f"  {DIM}Baud={baud} P={parity_name} {label}: Keine Antwort{RESET}\n")

    if not any_response:
        print(f"\n  {RED}{BOLD}KEINE ROHDATEN EMPFANGEN!{RESET}")
        print(f"\n  {YELLOW}Das bedeutet: Es kommen keine Daten ueber RS232 an.{RESET}")
        print(f"  {YELLOW}Moegliche Ursachen:{RESET}")
        print(f"    1. {BOLD}TX/RX vertauscht{RESET} → Null-Modem-Adapter oder Crossover-Kabel noetig")
        print(f"    2. {BOLD}DSE RS232 ist deaktiviert{RESET} → Im DSE-Menue unter 'Communications' pruefen")
        print(f"    3. {BOLD}DSE steht auf 'DSE Config Suite' Protokoll{RESET} statt 'Modbus RTU'")
        print(f"       → Am DSE: Menue → Editor Mode → Communications → RS232 → Protocol = Modbus")
        print(f"    4. {BOLD}USB-RS232-Adapter defekt{RESET} oder falscher Chipsatz-Treiber")
        print(f"    5. {BOLD}Kabel/Stecker locker{RESET}")
        print(f"\n  {CYAN}Tipp: Am DSE Controller pruefen:{RESET}")
        print(f"    - Menue → Instrumentierung → Seite 'Communications'")
        print(f"    - RS232 Protocol = {BOLD}Modbus RTU{RESET}")
        print(f"    - Baudrate und Slave-ID notieren")
        print(f"\n  Trotzdem weiter mit vollstaendigem Scan? (Strg+C zum Abbrechen)")
        print(f"{'─'*50}")
    else:
        print(f"\n  {GREEN}Rohdaten empfangen! Physische Verbindung steht.{RESET}")
        print(f"  Starte vollstaendigen Modbus-Scan...")
        print(f"{'─'*50}")

    # ── Phase 1: Vollstaendiger Modbus Scan ──
    print(f"\n{CYAN}{BOLD}Phase 1: Modbus Scan (FC3 + FC4, alle Kombinationen){RESET}")
    print(f"{'─'*50}")
    print(f"  Teste {len(BAUD_RATES)} Baudraten × {len(PARITIES)} Paritaeten × {len(SLAVE_IDS)} Slave-IDs × 2 Function Codes × {len(REGISTERS)} Register")
    print(f"  = {len(BAUD_RATES) * len(PARITIES) * len(SLAVE_IDS) * 2 * len(REGISTERS)} Anfragen\n")

    result = scan_modbus(port)

    if not result:
        print(f"\n{RED}{BOLD}{'='*60}{RESET}")
        print(f"{RED}{BOLD}  KEINE MODBUS-VERBINDUNG GEFUNDEN{RESET}")
        print(f"{RED}{BOLD}{'='*60}{RESET}")
        print(f"\n{YELLOW}Zusammenfassung:{RESET}")
        if any_response:
            print(f"  {GREEN}+ Rohdaten wurden empfangen{RESET} → Physische Verbindung OK")
            print(f"  {RED}- Aber kein gueltiges Modbus-Register lesbar{RESET}")
            print(f"\n  {YELLOW}Wahrscheinlich:{RESET}")
            print(f"    → DSE RS232 steht auf {BOLD}'DSE Config Suite'{RESET} Protokoll")
            print(f"    → Umstellen am DSE: Communications → RS232 → Protocol = {BOLD}Modbus RTU{RESET}")
        else:
            print(f"  {RED}- Keine Rohdaten empfangen{RESET} → Physisches Problem")
            print(f"\n  {YELLOW}Pruefen:{RESET}")
            print(f"    1. TX/RX tauschen (Null-Modem-Adapter)")
            print(f"    2. RS232 am DSE aktivieren")
            print(f"    3. Anderes USB-RS232-Kabel testen")
            print(f"    4. DSE RS232-Protokoll auf 'Modbus RTU' stellen")

        print(f"\n{CYAN}  DSE 5510 RS232 Konfiguration pruefen:{RESET}")
        print(f"    Am Controller: Menue-Taste → Editor-Modus → Communications")
        print(f"    → RS232 Settings:")
        print(f"      Protocol:  Modbus RTU")
        print(f"      Baud Rate: (notieren)")
        print(f"      Parity:    (notieren)")
        print(f"      Slave ID:  (notieren)")
        print(f"\n")


if __name__ == "__main__":
    main()
