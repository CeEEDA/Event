#!/usr/bin/env python3
"""Tankbeleg-UI Login-Diagnose.

Loest 3 Klassen-Probleme:
  1. bcrypt nicht installiert -> verify_driver_pin gibt immer False
  2. drivers_cache veraltet (kein pin_hash, weil bei letztem Sync
     noch kein date_of_birth im Backend stand)
  3. Falsches PIN-Format (User probiert TTMMJJJJ statt TTMMJJ)

Aufruf:
    sudo python3 tankbeleg_login_check.py
    sudo python3 tankbeleg_login_check.py --pin 101104 --name "Anna Weber"

Was wird gemacht:
  - Prueft ob bcrypt importierbar ist
  - Liest /etc/tankbeleg_pi.conf -> api_url + db_path
  - Zeigt alle gecacheten Fahrer (id, name, pin_hash-Status)
  - Forciert frischen Sync vom Backend (curl /api/fuel-receipts/pi/drivers)
  - Schreibt frische pin_hash-Werte in den lokalen SQLite-Cache
  - (Optional) Validiert einen PIN-Versuch direkt gegen den frisch
    geladenen Hash
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone

CONF_PATH = "/etc/tankbeleg_pi.conf"

def err(msg, code=1):
    print(f"FEHLER: {msg}", file=sys.stderr)
    sys.exit(code)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pin", help="PIN-Versuch (6 Ziffern) zum Validieren")
    ap.add_argument("--name", help="Fahrername fuer PIN-Test (Substring)")
    ap.add_argument("--no-sync", action="store_true", help="Cache nicht refreshen")
    args = ap.parse_args()

    # ---- 1. bcrypt vorhanden? ----
    print("[1/5] Pruefe bcrypt-Installation...")
    try:
        import bcrypt  # noqa
        print(f"      OK: bcrypt {bcrypt.__version__ if hasattr(bcrypt,'__version__') else '(version unknown)'}")
    except ImportError:
        print("      FEHLT! Bitte installieren:")
        print("         sudo pip3 install --break-system-packages bcrypt")
        sys.exit(2)

    # ---- 2. Konfig lesen ----
    print(f"[2/5] Lese {CONF_PATH}...")
    if not os.path.exists(CONF_PATH):
        err(f"{CONF_PATH} existiert nicht.")
    cp = configparser.ConfigParser()
    cp.read(CONF_PATH)
    sec = cp["tankbeleg"] if "tankbeleg" in cp else {}
    api_url = sec.get("api_url", "").rstrip("/")
    db_path = sec.get("db_path", "/var/lib/tankbeleg/tankbeleg.db")
    if not api_url:
        err("api_url fehlt in der Konfig.")
    if not api_url.endswith("/api"):
        api_url += "/api"
    print(f"      api_url = {api_url}")
    print(f"      db_path = {db_path}")

    # ---- 3. Lokalen Cache anzeigen ----
    print(f"[3/5] Lokaler Cache (drivers_cache)...")
    if not os.path.exists(db_path):
        print("      Cache-DB existiert noch nicht - wird beim ersten UI-Start angelegt.")
    else:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, name, email, role, "
                "       CASE WHEN pin_hash IS NULL OR pin_hash='' THEN 0 ELSE 1 END AS has_pin, "
                "       cached_at "
                "FROM drivers_cache ORDER BY name"
            ).fetchall()
            if not rows:
                print("      (Cache leer)")
            else:
                print(f"      {'NAME':<22} {'EMAIL':<32} {'ROLE':<14} PIN  CACHED_AT")
                for r in rows:
                    pin_marker = "JA " if r["has_pin"] else "NEIN"
                    print(f"      {r['name'][:21]:<22} {(r['email'] or '')[:31]:<32} {(r['role'] or '')[:13]:<14} {pin_marker}  {r['cached_at']}")
        except sqlite3.OperationalError as e:
            print(f"      Tabelle fehlt? {e}")
        conn.close()

    # ---- 4. Frischer Sync vom Backend ----
    if args.no_sync:
        print("[4/5] Sync uebersprungen (--no-sync)")
        drivers = []
    else:
        print(f"[4/5] Frischer Sync von {api_url}/fuel-receipts/pi/drivers ...")
        try:
            with urllib.request.urlopen(f"{api_url}/fuel-receipts/pi/drivers", timeout=10) as r:
                payload = json.load(r)
        except Exception as e:
            err(f"Sync fehlgeschlagen: {e}")
        drivers = payload.get("drivers", [])
        print(f"      Backend liefert {len(drivers)} Fahrer:")
        for d in drivers:
            ph = d.get("pin_hash", "")
            print(f"         {d['name']:<22} role={d['role']:<12} pin_hash_len={len(ph)}")
        if drivers:
            conn = sqlite3.connect(db_path)
            # Sicherstellen dass die Tabelle/Spalten da sind
            conn.execute("""CREATE TABLE IF NOT EXISTS drivers_cache(
                id TEXT PRIMARY KEY, name TEXT, email TEXT, role TEXT,
                password_hash TEXT, pin_hash TEXT, cached_at TEXT)""")
            for col in ("password_hash", "pin_hash"):
                try:
                    conn.execute(f"ALTER TABLE drivers_cache ADD COLUMN {col} TEXT")
                except sqlite3.OperationalError:
                    pass
            conn.execute("DELETE FROM drivers_cache")
            now = datetime.now(timezone.utc).isoformat()
            for d in drivers:
                conn.execute(
                    "INSERT OR REPLACE INTO drivers_cache "
                    "(id,name,email,role,password_hash,pin_hash,cached_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (d.get("id",""), d.get("name",""), d.get("email",""),
                     d.get("role","mitarbeiter"), d.get("password_hash",""),
                     d.get("pin_hash",""), now))
            conn.commit(); conn.close()
            print(f"      Cache neu geschrieben.")

    # ---- 5. Optional: PIN-Versuch validieren ----
    print("[5/5] PIN-Validierung...")
    if args.pin:
        if not drivers:
            print("      Kein Sync gemacht -> nichts zu pruefen.")
        else:
            target = None
            if args.name:
                target = next((d for d in drivers
                               if args.name.lower() in d["name"].lower()), None)
            if target is None:
                print("      Pruefe PIN gegen ALLE Fahrer...")
                for d in drivers:
                    ok = False
                    try:
                        ok = bcrypt.checkpw(args.pin.encode(),
                                            d.get("pin_hash","").encode())
                    except Exception as e:
                        print(f"         {d['name']}: ERROR {e}")
                        continue
                    print(f"         {d['name']:<22} -> {'OK <- MATCH' if ok else 'no'}")
            else:
                ok = bcrypt.checkpw(args.pin.encode(),
                                    target.get("pin_hash","").encode())
                print(f"      {target['name']}  PIN={args.pin}  -> {'OK' if ok else 'FALSCH'}")
    else:
        print("      Kein --pin uebergeben.")
        print("      Erwartetes PIN-Format: TTMMJJ (6 Ziffern, Jahr ZWEISTELLIG)")
        print("        z.B. Geburtsdatum 10.11.2004 -> PIN '101104'")
        print("        z.B. Geburtsdatum 26.02.1984 -> PIN '260284'")
        print()
        print("      Test gegen den frischen Cache mit:")
        print("        sudo python3 tankbeleg_login_check.py --pin 101104 --name Anna")

    print("\nFertig.")

if __name__ == "__main__":
    main()
