#!/usr/bin/env python3
"""
DSE 5510 Register-Scanner via P810
Sucht lesbare Register fuer den Betriebsmodus
"""
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
    time.sleep(0.3)
    r = ser.read(ser.in_waiting or 50)
    if len(r) < 5:
        return None
    if r[0] != slave or r[1] != 0x03:
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

# Kandidaten-Register fuer den Betriebsmodus
candidates = [
    # Page 1: Identification
    ("Page1+0  (256)", 256),
    ("Page1+1  (257)", 257),
    ("Page1+2  (258)", 258),
    ("Page1+14 (270) InstrumentMode", 270),
    ("Page1+15 (271)", 271),
    # Page 3: Status
    ("Page3+0  (768)", 768),
    ("Page3+1  (769)", 769),
    ("Page3+2  (770)", 770),
    ("Page3+3  (771)", 771),
    ("Page3+14 (782) GenAvailable", 782),
    ("Page3+15 (783) BreakerClosed", 783),
    # Page 5: Controller Config
    ("Page5+0  (1280)", 1280),
    ("Page5+1  (1281)", 1281),
    # Page 8: Alarms
    ("Page8+0  (2048)", 2048),
    # Verify working pages still work
    ("Page4+0  (1024) OilPressure", 1024),
    ("Page4+10 (1034) BattVoltage", 1034),
    ("Page7+6  (1798) EngineRunTime", 1798),
]

print(f"DSE 5510 Register-Scan: {port} @ {baud} Baud, Slave {slave}")
print("=" * 60)

for label, reg in candidates:
    result = read_reg(ser, slave, reg)
    if result is not None:
        hex_val = " ".join(f"0x{v:04X}" for v in result)
        print(f"  OK  {label}: {result[0]:6d} ({hex_val})")
    else:
        print(f"  --  {label}: nicht lesbar")
    time.sleep(0.1)

ser.close()
print("\nFertig.")
