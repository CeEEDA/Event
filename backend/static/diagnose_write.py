#!/usr/bin/env python3
"""
DSE 5510 Write-Diagnose
Testet verschiedene Schreibmethoden auf dem DSE 5510 via P810 RS232.
"""
import serial
import struct
import time
import sys

def calc_crc(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack("<H", crc)

def raw_read(ser, slave, register, count):
    frame = struct.pack(">BBHH", slave, 0x03, register, count)
    frame += calc_crc(frame)
    ser.reset_input_buffer()
    ser.write(frame)
    time.sleep(0.3)
    resp = ser.read(ser.in_waiting or 50)
    return resp

def raw_write_fc16(ser, slave, register, values):
    count = len(values)
    frame = struct.pack(">BBHHB", slave, 0x10, register, count, count * 2)
    for v in values:
        frame += struct.pack(">H", v)
    frame += calc_crc(frame)
    print(f"  TX FC16: {frame.hex()}")
    ser.reset_input_buffer()
    ser.write(frame)
    time.sleep(1.5)
    resp = ser.read(ser.in_waiting or 50)
    print(f"  RX:      {resp.hex() if resp else 'LEER'} ({len(resp)} bytes)")
    return resp

def raw_write_fc06(ser, slave, register, value):
    frame = struct.pack(">BBH", slave, 0x06, register)
    frame += struct.pack(">H", value)
    frame += calc_crc(frame)
    print(f"  TX FC06: {frame.hex()}")
    ser.reset_input_buffer()
    ser.write(frame)
    time.sleep(1.5)
    resp = ser.read(ser.in_waiting or 50)
    print(f"  RX:      {resp.hex() if resp else 'LEER'} ({len(resp)} bytes)")
    return resp

def raw_write_fc05(ser, slave, coil, on=True):
    """FC05 Write Single Coil"""
    value = 0xFF00 if on else 0x0000
    frame = struct.pack(">BBHH", slave, 0x05, coil, value)
    frame += calc_crc(frame)
    print(f"  TX FC05: {frame.hex()}")
    ser.reset_input_buffer()
    ser.write(frame)
    time.sleep(1.5)
    resp = ser.read(ser.in_waiting or 50)
    print(f"  RX:      {resp.hex() if resp else 'LEER'} ({len(resp)} bytes)")
    return resp

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    slave = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    print(f"DSE 5510 Write-Diagnose")
    print(f"Port: {port}, Slave: {slave}")
    print("=" * 60)

    ser = serial.Serial(port, 19200, bytesize=8, parity='N', stopbits=1, timeout=2)
    time.sleep(0.5)

    # Test 1: Lesen zur Bestaetigung der Verbindung
    print("\n[1] LESE-Test (Page 4 RPM) - Bestaetigt Verbindung")
    resp = raw_read(ser, slave, 1024, 1)
    if resp and len(resp) >= 5:
        print(f"  OK: Verbindung funktioniert ({resp.hex()})")
    else:
        print(f"  FEHLER: Keine Leseantwort!")
        return

    # Test 2: Page 16 LESEN - Existiert die Control-Page?
    print("\n[2] LESE Page 16 Register 4096-4110 (Control Page)")
    for reg in [4096, 4098, 4100, 4102, 4104, 4106, 4108, 4110]:
        resp = raw_read(ser, slave, reg, 1)
        if resp and len(resp) >= 5 and not (resp[1] & 0x80):
            val = struct.unpack(">H", resp[3:5])[0]
            print(f"  Reg {reg}: {val} (0x{val:04X}) - LESBAR")
        elif resp and resp[1] & 0x80:
            print(f"  Reg {reg}: Modbus Exception 0x{resp[2]:02X}")
        else:
            print(f"  Reg {reg}: Keine Antwort ({len(resp)} bytes)")

    # Test 3: Verschiedene Write-Methoden
    KEY_STOP = 35700
    COMP_STOP = 29835

    print(f"\n[3] SCHREIBE Stop-Befehl (Key={KEY_STOP}, Comp={COMP_STOP})")

    print(f"\n  3a) FC16 @4104 Slave {slave}:")
    raw_write_fc16(ser, slave, 4104, [KEY_STOP, COMP_STOP])
    time.sleep(0.5)

    print(f"\n  3b) FC06 @4104 Slave {slave}:")
    raw_write_fc06(ser, slave, 4104, KEY_STOP)
    time.sleep(0.5)

    print(f"\n  3c) FC16 @4096 Slave {slave}:")
    raw_write_fc16(ser, slave, 4096, [KEY_STOP, COMP_STOP])
    time.sleep(0.5)

    print(f"\n  3d) FC05 Coil 4104 Slave {slave}:")
    raw_write_fc05(ser, slave, 4104, True)
    time.sleep(0.5)

    # Test 4: Broadcast (Slave 0)
    print(f"\n[4] BROADCAST (Slave 0)")
    print(f"  4a) FC16 @4104 Slave 0:")
    raw_write_fc16(ser, 0, 4104, [KEY_STOP, COMP_STOP])
    time.sleep(0.5)

    # Test 5: Slave 1
    if slave != 1:
        print(f"\n[5] Slave 1")
        print(f"  5a) FC16 @4104 Slave 1:")
        raw_write_fc16(ser, 1, 4104, [KEY_STOP, COMP_STOP])
        time.sleep(0.5)

    # Test 6: GenComm Seite 4, Register 4104 mit offset
    print(f"\n[6] Alternative Register-Adressen")
    for reg in [0x1008, 0x0008, 0x4008, 0x1000, 0x4000]:
        print(f"\n  FC16 @{reg} (0x{reg:04X}) Slave {slave}:")
        raw_write_fc16(ser, slave, reg, [KEY_STOP, COMP_STOP])
        time.sleep(0.3)

    print("\n" + "=" * 60)
    print("Diagnose abgeschlossen.")
    print("Bitte Log-Ausgabe an den Entwickler senden.")
    ser.close()

if __name__ == "__main__":
    main()
