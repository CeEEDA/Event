#!/usr/bin/env python3
"""DSE 5510 - Schneller Register-Scan mit Fortschritt."""
import serial, struct, time, sys

def crc(d):
    c = 0xFFFF
    for b in d:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return struct.pack("<H", c)

def read_reg(ser, slave, register):
    f = struct.pack(">BBHH", slave, 0x03, register, 1)
    f += crc(f)
    ser.reset_input_buffer()
    ser.write(f)
    time.sleep(0.15)
    r = ser.read(ser.in_waiting or 50)
    if len(r) < 5 or r[0] != slave or r[1] != 0x03 or r[2] != 2:
        return None
    return struct.unpack(">H", r[3:5])[0]

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 19200
slave = int(sys.argv[3]) if len(sys.argv) > 3 else 10

ser = serial.Serial(port, baud, bytesize=8, parity='N', stopbits=1, timeout=1)
time.sleep(0.5)

# Nur unbekannte Pages scannen (1,3,4,6,7 kennen wir schon)
pages = [0, 2, 5, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
total = len(pages)

for idx, page in enumerate(pages):
    base = page * 256
    sys.stdout.write(f"[{idx+1}/{total}] Page {page}...")
    sys.stdout.flush()
    found = []
    for offset in range(21):
        val = read_reg(ser, slave, base + offset)
        if val is not None:
            na = " [NA]" if val in (0xFFFF, 0xFFFE, 0xFFFD, 0xFFFB, 0x7FFF, 0x7FFB) else ""
            found.append(f"  +{offset:2d} ({base+offset:5d}): {val:6d}  0x{val:04X}{na}")
    if found:
        print(f" {len(found)} Register gefunden:")
        for f in found:
            print(f)
    else:
        print(" leer")

ser.close()
print("Fertig.")
