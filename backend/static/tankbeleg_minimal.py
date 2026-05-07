#!/usr/bin/env python3
"""Tankbeleg-Pi MINIMAL-Mode (Diagnose).

Standalone-Skript ohne Service. Lauscht auf /dev/ttyUSB0, antwortet auf
Sening-Polls (ESC B3 n) mit 0x00 und speichert kompletten Druckstrom
als raw_<timestamp>.bin nach /var/lib/tankbeleg/.

Aufruf:
    sudo systemctl stop tankbeleg_pi
    sudo python3 tankbeleg_minimal.py
    # Strg+C zum beenden
"""
import os
import serial
import time
import sys

OUT_DIR = "/var/lib/tankbeleg"
os.makedirs(OUT_DIR, exist_ok=True)

s = serial.Serial(
    "/dev/ttyUSB0", 9600, bytesize=8, parity="N", stopbits=1,
    timeout=0.1, xonxoff=False, rtscts=False, dsrdtr=False,
)
s.dtr = True
s.rts = True
print(f"Tankbeleg MINIMAL: 8N1 DTR=True port=/dev/ttyUSB0")
print(f"DSR={s.dsr} CTS={s.cts}  --  Sening Print druecken!")
print(f"Strg+C zum Beenden.\n", flush=True)

REPLY = b"\x00"        # <- WIRD JETZT GARANTIERT GESENDET
POLL = b"\x1b\xb3"     # ESC B3

buf = bytearray()
last = 0.0
poll_count = 0
beleg_count = 0

try:
    while True:
        d = s.read(256)
        if d:
            i = 0
            while i < len(d):
                if d[i:i+2] == POLL and i + 3 <= len(d):
                    # Kompletter 3-Byte Poll: ESC B3 <zone> -> Reply 0x00
                    s.write(REPLY)
                    s.flush()
                    poll_count += 1
                    if poll_count <= 3 or poll_count % 50 == 0:
                        print(f"[poll #{poll_count}] {d[i:i+3].hex(' ')} -> reply 0x00", flush=True)
                    i += 3
                else:
                    buf.append(d[i])
                    i += 1
            last = time.time()
        elif buf and time.time() - last > 2.0:
            beleg_count += 1
            fn = os.path.join(OUT_DIR, f"raw_{int(time.time())}_{len(buf)}B.bin")
            with open(fn, "wb") as f:
                f.write(buf)
            print(f"\n*** BELEG #{beleg_count} GESPEICHERT: {len(buf)} Bytes -> {fn} ***\n", flush=True)
            buf = bytearray()
except KeyboardInterrupt:
    print(f"\nBeendet. {poll_count} Polls beantwortet, {beleg_count} Belege gespeichert.")
finally:
    s.close()
