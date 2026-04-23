#!/usr/bin/env python3
"""
Tankbeleg Reply Tuner
======================
Automatischer Test zum Ermitteln des korrekten Status-Antwort-Bytes fuer
den Sening MultiFlow Printer-Emulator.

Ablauf:
  1. Stoppt den tankbeleg_pi Service (Port freigeben)
  2. Iteriert ueber Kandidaten-Bytes (0x00, 0x12, ...)
  3. Sendet pro Kandidat N Sekunden lang die Antwort auf jeden
     ESC B3 FF Poll der MultiFlow
  4. Erkennt automatisch, wenn die MultiFlow echte Belegdaten
     schickt (non-poll Bytes, in der Regel lange Burst-Sequenz)
  5. Meldet den Gewinner-Wert und bleibt dann auf diesem Wert
     stehen, damit der Beleg komplett empfangen werden kann

Verwendung:
  sudo systemctl stop tankbeleg_pi
  sudo python3 /opt/tankbeleg/tankbeleg_reply_tuner.py
"""

import serial
import time
import sys
import subprocess


PORT = "/dev/ttyUSB0"
BAUD = 9600
SECONDS_PER_CANDIDATE = 15   # Wie lange pro Byte getestet wird
BYTES_FOR_SUCCESS = 20       # Mehr als N Nicht-Poll-Bytes = echter Beleg
CAPTURE_SECONDS = 30         # Nach Erfolg so lange Daten sammeln

# Reihenfolge nach Wahrscheinlichkeit (Epson-Standard zuerst)
CANDIDATES = [
    0x12,  # Epson TM-U295 Standard "online/idle/paper present"
    0x00,  # Alle Flags clear (generisches OK)
    0x10,  # DLE
    0x06,  # ACK
    0x7F,  # Low bits gesetzt
    0xFF,  # Alle Bits (Mirror-Antwort)
    0x01,  # Minimal
    0x02,
    0x04,
    0x08,
    0x20,
    0x40,  # '@' - Epson Init-Byte
    0x30,  # '0'
    0x11,  # DC1 / XON
    0x13,  # DC3 / XOFF
    0x18,  # CAN
]


def stop_service():
    try:
        subprocess.run(["systemctl", "stop", "tankbeleg_pi"],
                       check=False, capture_output=True)
        print("[INFO] tankbeleg_pi Service gestoppt.")
        time.sleep(1)
    except Exception as e:
        print(f"[WARN] systemctl stop fehlgeschlagen: {e}")


def restart_service():
    try:
        subprocess.run(["systemctl", "start", "tankbeleg_pi"],
                       check=False, capture_output=True)
        print("[INFO] tankbeleg_pi Service neu gestartet.")
    except Exception as e:
        print(f"[WARN] systemctl start fehlgeschlagen: {e}")


def is_poll(chunk: bytes) -> bool:
    """Prueft ob der Chunk nur aus Sening-Polls (ESC B3 xx) besteht."""
    if len(chunk) == 0:
        return False
    i = 0
    while i < len(chunk):
        if i + 2 < len(chunk) and chunk[i] == 0x1B and chunk[i + 1] == 0xB3:
            i += 3
            continue
        return False
    return True


def test_byte(ser: serial.Serial, reply: int, duration: int) -> dict:
    """Testet ein Antwort-Byte fuer duration Sekunden.
    Gibt Statistik zurueck inkl. Anzahl echter Nicht-Poll-Bytes."""
    poll_count = 0
    real_bytes = bytearray()
    buf = bytearray()
    start = time.time()
    deadline = start + duration
    reply_bytes = bytes([reply])

    print(f"\n{'='*60}")
    print(f"  Teste Antwort-Byte: 0x{reply:02X} ({duration}s)")
    print(f"{'='*60}")

    while time.time() < deadline:
        data = ser.read(256)
        if not data:
            continue
        buf.extend(data)

        # Sening-Polls konsumieren, alles andere als 'echte Daten' werten
        while len(buf) >= 3:
            if buf[0] == 0x1B and buf[1] == 0xB3:
                # Poll erkannt -> antworten
                ser.write(reply_bytes)
                ser.flush()
                poll_count += 1
                del buf[:3]
                print(".", end="", flush=True)
            elif buf[0] == 0x1B and len(buf) < 3:
                # ESC am Ende - warten auf mehr Bytes
                break
            else:
                # Kein Poll -> echte Belegdaten!
                # Ersten Byte als "real" zaehlen, Rest der while-Schleife machen lassen
                real_bytes.append(buf[0])
                del buf[:1]

        # Early-Exit bei genug echten Bytes
        if len(real_bytes) >= BYTES_FOR_SUCCESS:
            print(f"\n[ERFOLG] Echte Belegdaten empfangen ({len(real_bytes)} Bytes)!")
            return {
                "reply": reply,
                "polls": poll_count,
                "real_bytes": len(real_bytes),
                "success": True,
                "sample": bytes(real_bytes[:64]),
            }

    print(f"\n  -> {poll_count} Polls, {len(real_bytes)} echte Bytes.")
    return {
        "reply": reply,
        "polls": poll_count,
        "real_bytes": len(real_bytes),
        "success": len(real_bytes) >= 5,
        "sample": bytes(real_bytes[:64]),
    }


def capture_full_receipt(ser: serial.Serial, reply: int, duration: int) -> bytes:
    """Nach Erfolg: Komplette Belegdaten sammeln."""
    print(f"\n{'='*60}")
    print(f"  CAPTURE MODE: Sammle Beleg fuer {duration}s mit Antwort 0x{reply:02X}")
    print(f"{'='*60}")

    captured = bytearray()
    buf = bytearray()
    reply_bytes = bytes([reply])
    deadline = time.time() + duration
    last_data = time.time()

    while time.time() < deadline:
        data = ser.read(256)
        if data:
            last_data = time.time()
            buf.extend(data)
            while len(buf) >= 3:
                if buf[0] == 0x1B and buf[1] == 0xB3:
                    ser.write(reply_bytes)
                    ser.flush()
                    del buf[:3]
                else:
                    captured.append(buf[0])
                    del buf[:1]
        else:
            # Nach 3s Stille -> Beleg wahrscheinlich komplett
            if captured and (time.time() - last_data) > 3.0:
                break
            time.sleep(0.05)

    return bytes(captured)


def main():
    print("=" * 60)
    print("  Tankbeleg Reply Tuner")
    print("=" * 60)
    print(f"  Port:        {PORT} @ {BAUD}")
    print(f"  Dauer/Byte:  {SECONDS_PER_CANDIDATE}s")
    print(f"  Kandidaten:  {', '.join(f'0x{x:02X}' for x in CANDIDATES)}")
    print("=" * 60)
    print("\n[INFO] Die MultiFlow steht auf 'Papier einlegen'.")
    print("[INFO] Falls dort noch ein fertiger Tankvorgang wartet, wird er")
    print("       automatisch gedruckt sobald das richtige Byte gefunden ist.")
    print("\n>>> In 5 Sekunden geht's los... <<<\n")
    time.sleep(5)

    stop_service()

    try:
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUD,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        ser.dtr = True
        ser.rts = True
    except Exception as e:
        print(f"[FEHLER] Serial-Port nicht verfuegbar: {e}")
        restart_service()
        sys.exit(1)

    results = []
    winner = None

    try:
        for byte_val in CANDIDATES:
            result = test_byte(ser, byte_val, SECONDS_PER_CANDIDATE)
            results.append(result)
            if result["success"]:
                winner = result
                break

        print("\n" + "=" * 60)
        print("  ERGEBNIS-UEBERSICHT")
        print("=" * 60)
        for r in results:
            marker = "✅ GEWINNER" if r["success"] else "   "
            sample = r["sample"].hex(" ") if r["sample"] else "(keine)"
            print(f"  {marker} 0x{r['reply']:02X}: {r['polls']:4d} Polls, {r['real_bytes']:4d} echte Bytes")
            if r["sample"]:
                print(f"              Sample: {sample}")
        print("=" * 60)

        if winner:
            print(f"\n🎯 KORREKTES ANTWORT-BYTE: 0x{winner['reply']:02X}")
            print(f"\nJetzt in /etc/tankbeleg_pi.conf eintragen:")
            print(f"   sening_reply_byte = 0x{winner['reply']:02X}\n")

            receipt = capture_full_receipt(ser, winner["reply"], CAPTURE_SECONDS)
            if receipt:
                print(f"\n[CAPTURE] {len(receipt)} Bytes Beleg empfangen:")
                print(f"[CAPTURE] HEX:\n{receipt.hex(' ')}")
                try:
                    text = receipt.decode("cp437", errors="replace")
                    print(f"\n[CAPTURE] TEXT (CP437):")
                    print("-" * 60)
                    print(text)
                    print("-" * 60)
                except Exception:
                    pass

                # Beleg als Datei speichern
                filename = f"/tmp/tankbeleg_sample_{int(time.time())}.bin"
                with open(filename, "wb") as f:
                    f.write(receipt)
                print(f"\n[INFO] Roh-Daten gespeichert: {filename}")
        else:
            print("\n❌ KEIN passendes Antwort-Byte gefunden.")
            print("   Moeglicherweise erwartet die MultiFlow ein 2-Byte-Reply")
            print("   oder ein anderes Protokoll. Logs teilen fuer weitere Analyse.")

    except KeyboardInterrupt:
        print("\n[INFO] Abbruch durch Benutzer.")
    finally:
        ser.close()
        print("\n[INFO] Serial-Port geschlossen.")
        restart_service()


if __name__ == "__main__":
    main()
