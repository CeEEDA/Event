#!/usr/bin/env python3
"""DSE 5510 - Erweiterter Register-Scan. Liest ALLE erreichbaren Register."""
import serial, struct, time, sys

def crc(d):
    c = 0xFFFF
    for b in d:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return struct.pack("<H", c)

def read_reg(ser, slave, register, count=1):
    f = struct.pack(">BBHH", slave, 0x03, register, count)
    f += crc(f)
    ser.reset_input_buffer()
    ser.write(f)
    time.sleep(0.25)
    r = ser.read(ser.in_waiting or 50)
    if len(r) < 5 or r[0] != slave or r[1] != 0x03:
        return None
    bc = r[2]
    if bc != count * 2:
        return None
    vals = []
    for i in range(count):
        vals.append(struct.unpack(">H", r[3+i*2:5+i*2])[0])
    return vals

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 19200
slave = int(sys.argv[3]) if len(sys.argv) > 3 else 10

ser = serial.Serial(port, baud, bytesize=8, parity='N', stopbits=1, timeout=2)
time.sleep(0.5)

print(f"Erweiterter Scan: {port} @ {baud}, Slave {slave}")
print("=" * 60)

# Alle GenComm Pages 0-18, Offsets 0-30
for page in range(19):
    base = page * 256
    found = []
    for offset in range(31):
        reg = base + offset
        result = read_reg(ser, slave, reg)
        if result is not None:
            found.append((offset, reg, result[0]))
        time.sleep(0.05)
    if found:
        print(f"\nPage {page} (Base {base}):")
        for off, reg, val in found:
            na = " [NA]" if val in (0xFFFF, 0xFFFE, 0xFFFD, 0xFFFB, 0x7FFF, 0x7FFB) else ""
            print(f"  +{off:2d} ({reg:5d}): {val:6d}  0x{val:04X}{na}")

ser.close()
print("\nFertig.")
