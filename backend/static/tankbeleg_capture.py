#!/usr/bin/env python3
"""
Tankbeleg Capture
==================
Reines Aufzeichnungs-Skript. Beantwortet Sening-Polls (ESC B3 FF) mit 0x00
und schreibt alle anderen Bytes live in eine Datei. Beendet automatisch
wenn 10 Sekunden keine Daten mehr kommen.

Verwendung:
  sudo systemctl stop tankbeleg_pi
  sudo python3 /opt/tankbeleg/tankbeleg_capture.py

Dann an der MultiFlow den Beleg drucken.
"""

import serial
import time
import sys
import subprocess
import os

PORT = "/dev/ttyUSB0"
BAUD = 9600
REPLY = b"\x00"
SILENCE_EXIT = 10.0   # Sekunden Stille -> beenden
MAX_RUNTIME = 300.0   # Hard-Limit 5 Minuten

OUT_FILE = f"/tmp/tankbeleg_capture_{int(time.time())}.bin"
LOG_FILE = OUT_FILE.replace(".bin", ".log")


def main():
    print("=" * 60)
    print("  Tankbeleg Capture")
    print("=" * 60)
    print(f"  Port:       {PORT} @ {BAUD}")
    print(f"  Reply:      0x{REPLY[0]:02X}")
    print(f"  Output:     {OUT_FILE}")
    print(f"  Log:        {LOG_FILE}")
    print(f"  Silence:    {SILENCE_EXIT}s -> Auto-Exit")
    print("=" * 60)

    # Service stoppen
    print("\n[INFO] Stoppe tankbeleg_pi Service...")
    subprocess.run(["systemctl", "stop", "tankbeleg_pi"], check=False, capture_output=True)
    time.sleep(1)

    # Serial oeffnen
    try:
        ser = serial.Serial(
            port=PORT, baudrate=BAUD, bytesize=8,
            parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
            timeout=0.1, xonxoff=False, rtscts=False, dsrdtr=False,
        )
        ser.dtr = True
        ser.rts = True
    except Exception as e:
        print(f"[FEHLER] Serial nicht verfuegbar: {e}")
        subprocess.run(["systemctl", "start", "tankbeleg_pi"], check=False)
        sys.exit(1)

    print("\n>>> Jetzt an der MultiFlow Beleg drucken! <<<")
    print(f">>> Datei waechst unter: {OUT_FILE} <<<\n")
    print("Legende: '.' = Poll beantwortet   'X' = echte Daten (Bytes)\n")

    poll_count = 0
    total_bytes = 0
    buf = bytearray()
    last_data = time.time()
    start = time.time()
    fout = open(OUT_FILE, "wb")
    flog = open(LOG_FILE, "w")

    try:
        while True:
            now = time.time()
            if now - last_data > SILENCE_EXIT and total_bytes > 0:
                print(f"\n[INFO] {SILENCE_EXIT}s Stille - Capture beendet.")
                break
            if now - start > MAX_RUNTIME:
                print(f"\n[INFO] Max-Laufzeit {MAX_RUNTIME}s erreicht.")
                break

            data = ser.read(256)
            if not data:
                continue
            last_data = now
            buf.extend(data)
            flog.write(f"{now:.3f} RX {data.hex(' ')}\n")
            flog.flush()

            # Polls konsumieren, alles andere -> Datei
            while len(buf) >= 1:
                if len(buf) >= 3 and buf[0] == 0x1B and buf[1] == 0xB3:
                    ser.write(REPLY)
                    ser.flush()
                    poll_count += 1
                    del buf[:3]
                    print(".", end="", flush=True)
                elif buf[0] == 0x1B and len(buf) < 3:
                    # ESC am Ende -> warte auf mehr
                    break
                else:
                    fout.write(bytes([buf[0]]))
                    fout.flush()
                    total_bytes += 1
                    del buf[:1]
                    if total_bytes % 50 == 0:
                        print(f"\n  [{total_bytes} Bytes gespeichert]", flush=True)
                    else:
                        print("X", end="", flush=True)
    except KeyboardInterrupt:
        print("\n[INFO] Abbruch durch Benutzer.")
    finally:
        ser.close()
        fout.close()
        flog.close()
        # letzte Byte im Buffer auch speichern (incomplete ESC am Ende)
        if buf:
            with open(OUT_FILE, "ab") as f:
                f.write(bytes(buf))
            total_bytes += len(buf)

        print(f"\n\n{'='*60}")
        print(f"  ERGEBNIS")
        print(f"{'='*60}")
        print(f"  Polls beantwortet:  {poll_count}")
        print(f"  Echte Daten:        {total_bytes} Bytes")
        print(f"  Datei:              {OUT_FILE}")
        print(f"  Log:                {LOG_FILE}")
        print(f"{'='*60}")

        # Hex-Dump der ersten 512 Bytes
        if total_bytes > 0:
            with open(OUT_FILE, "rb") as f:
                raw = f.read(512)
            print(f"\n  HEX-DUMP (erste {min(512,total_bytes)} Bytes):")
            print("-" * 60)
            for i in range(0, len(raw), 16):
                chunk = raw[i:i+16]
                hex_part = " ".join(f"{b:02x}" for b in chunk)
                ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                print(f"  {i:04x}  {hex_part:<48}  {ascii_part}")
            print("-" * 60)

            # Text-Versuche
            print("\n  TEXT-VERSUCH (CP437):")
            print("-" * 60)
            try:
                txt = raw.decode("cp437", errors="replace")
                print(txt)
            except Exception as e:
                print(f"  (nicht dekodierbar: {e})")
            print("-" * 60)

            print(f"\n  Datei liegt unter: {OUT_FILE}")
            print(f"  Log liegt unter:   {LOG_FILE}")
            print(f"  Groesse: {os.path.getsize(OUT_FILE)} Bytes")
        else:
            print("\n  [WARN] Keine echten Daten empfangen.")

        print("\n[INFO] Starte tankbeleg_pi Service wieder...")
        subprocess.run(["systemctl", "start", "tankbeleg_pi"], check=False)


if __name__ == "__main__":
    main()
