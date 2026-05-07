#!/usr/bin/env python3
"""
Sening Reply-Byte-Cycler
========================
Diagnose-Tool: probiert systematisch verschiedene Reply-Bytes auf den
Sening-Poll (0x1B 0xB3 0xFF) durch und schaut ob Sening dann den Druckjob
sendet. Sobald nach einem Reply mehr als ~50 Bytes vom Sening kommen,
haben wir den richtigen Byte gefunden.

Aufruf (Tankbeleg-Service muss vorher gestoppt werden):
    sudo systemctl stop tankbeleg_pi
    sudo python3 sening_reply_cycler.py

Wenn ein Kandidat funktioniert (Sening sendet Beleg), wird das Skript
gestoppt und gibt den richtigen Wert aus. Den dann in
/etc/tankbeleg_pi.conf unter 'sening_reply_byte' eintragen und
Service starten.
"""
import serial
import time
import sys

# Kandidaten-Liste (in Reihenfolge der Wahrscheinlichkeit nach Epson-Doku):
CANDIDATES = [
    (0x00, "0x00 - alle Flags 0"),
    (0x12, "0x12 - online + paper OK (Standard DLE EOT Reply)"),
    (0x14, "0x14 - drawer + paper OK"),
    (0x16, "0x16 - online + paper OK + drawer"),
    (0x10, "0x10 - paper OK only"),
    (0x18, "0x18 - cover closed + paper"),
    (0x1A, "0x1A - online + cover + paper"),
    (0x06, "0x06 - ACK"),
    (0x90, "0x90 - ASB header (printer status, online)"),
    (0x80, "0x80 - bit 7 set (some printers)"),
    (0x40, "0x40 - inverse"),
    (0x7F, "0x7F - all but high bit"),
    (0xFF, "0xFF - alle Flags 1"),
]

POLL_PREFIX = b"\x1b\xb3"  # ESC B3
SECONDS_PER_CANDIDATE = 8  # wie lange jeden Wert testen
PRINT_JOB_THRESHOLD = 50   # wenn nach Reply X Bytes empfangen werden -> Treffer


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    print(f"Sening-Reply-Byte-Cycler auf {port}")
    print(f"  Jeder Kandidat wird {SECONDS_PER_CANDIDATE}s getestet.")
    print(f"  Treffer-Heuristik: nach Reply > {PRINT_JOB_THRESHOLD} weitere Bytes vom Sening.")
    print()
    s = serial.Serial(port, 9600, 8, "N", 1,
                      timeout=0.2, xonxoff=False, rtscts=False, dsrdtr=False)
    s.dtr = True
    s.rts = True
    print(f"  DSR={s.dsr}  CTS={s.cts}  CD={s.cd}  RI={s.ri}")
    print()

    found = None
    try:
        for value, label in CANDIDATES:
            print(f"[Test] {label}")
            # Wenn vorher noch Bytes im Buffer liegen, leeren
            s.reset_input_buffer()
            end = time.time() + SECONDS_PER_CANDIDATE
            polls_seen = 0
            bytes_after_reply = 0
            buf = bytearray()
            last_reply_at = 0
            while time.time() < end:
                d = s.read(256)
                if not d:
                    continue
                buf.extend(d)
                # Auf ESC B3 n antworten (Sening-Poll)
                while True:
                    idx = buf.find(POLL_PREFIX)
                    if idx < 0:
                        # Buffer-Inhalt ohne Poll - das sind Print-Daten oder
                        # Status-Antworten, gut fuer "Treffer"-Erkennung
                        if buf:
                            bytes_after_reply += len(buf)
                        buf = bytearray()
                        break
                    # Bytes vor dem Poll sind potenzielle Druckdaten
                    if idx > 0:
                        bytes_after_reply += idx
                        buf = buf[idx:]
                    if len(buf) < 3:
                        break  # 'n' fehlt noch
                    # Kompletter Poll empfangen -> antworten
                    polls_seen += 1
                    s.write(bytes([value]))
                    s.flush()
                    last_reply_at = time.time()
                    buf = buf[3:]
                if bytes_after_reply >= PRINT_JOB_THRESHOLD:
                    print(f"    >> TREFFER! Sening hat nach Reply {bytes_after_reply} Bytes gesendet.")
                    print(f"    >> Setze in /etc/tankbeleg_pi.conf:  sening_reply_byte = 0x{value:02X}")
                    found = value
                    break
            print(f"    Polls beantwortet: {polls_seen}, Bytes nach Reply: {bytes_after_reply}")
            if found is not None:
                break
    finally:
        s.close()

    if found is not None:
        print()
        print(f"=== ERGEBNIS: 0x{found:02X} funktioniert ===")
        print(f"In /etc/tankbeleg_pi.conf eintragen:")
        print(f"  sening_reply_byte = 0x{found:02X}")
        print(f"Dann: sudo systemctl restart tankbeleg_pi")
        return 0
    print()
    print("=== Kein Kandidat hat einen Druckjob ausgeloest. ===")
    print("Naechste Schritte:")
    print(" - Sening-Anzeige pruefen (steht da 'Drucker bereit'?)")
    print(" - Manuell einen kleinen Tankvorgang (1-2 L) starten waehrend dieses Tool laeuft")
    print(" - Im Portal Live-Stream pruefen ob Sening jetzt anders pollt")
    return 1


if __name__ == "__main__":
    sys.exit(main())
