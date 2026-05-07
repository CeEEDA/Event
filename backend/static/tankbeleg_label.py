#!/usr/bin/env python3
"""Tankbeleg Ground-Truth Sniffer / Labeler.

Workflow:
  1. Tanke am Sening (mit der echten Liter-Anzeige im Auge!)
  2. Pi empfaengt Druckdaten und legt einen Beleg in der lokalen SQLite an
  3. Du startest dieses Skript - es zeigt Dir die letzten 5 Belege
  4. Tippst beim juengsten ein: "323" (Liter laut Sening-Display)
  5. Skript schickt Beleg-Nr + tatsaechliche Liter + raw-Hex an das Backend
  6. Wir koennen jetzt den Parser gegen den Ist-Wert vergleichen und tunen

Aufruf (auf dem Pi):
    sudo python3 /opt/tankbeleg_label.py
    # oder oneliner mit Beleg-Nr + Liter:
    sudo python3 /opt/tankbeleg_label.py --beleg 16955 --liter 323

Voraussetzungen:
  - /etc/tankbeleg_pi.conf vorhanden (api_url + db_path)
  - bcrypt, requests installiert
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request

CONF_PATH = "/etc/tankbeleg_pi.conf"
HTTP_HEADERS = {
    "User-Agent": "TankbelegPi-Label/1.0 (eventenergie-deutschland)",
    "Content-Type": "application/json",
}


def load_conf():
    cp = configparser.ConfigParser()
    if not os.path.exists(CONF_PATH):
        sys.exit(f"FEHLER: {CONF_PATH} fehlt.")
    cp.read(CONF_PATH)
    sec = cp["tankbeleg"] if "tankbeleg" in cp else {}
    api_url = sec.get("api_url", "").rstrip("/")
    if not api_url.endswith("/api"):
        api_url += "/api"
    return {
        "api_url": api_url,
        "db_path": sec.get("db_path", "/var/lib/tankbeleg/tankbeleg.sqlite"),
    }


def list_recent_receipts(db_path, limit=8):
    if not os.path.exists(db_path):
        return []
    conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT local_id, beleg_nr, menge_liter, fuel_type, datum, zeit, "
        "       LENGTH(raw_receipt_hex) AS hex_len "
        "FROM receipts WHERE beleg_nr IS NOT NULL AND beleg_nr <> '' "
        "ORDER BY local_id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def post_label(api_url, beleg_nr, actual_liters, actual_fuel="diesel",
               actual_beleg=None, note=None, pi_id=""):
    url = f"{api_url}/fuel-receipts/label/{beleg_nr}"
    body = {
        "actual_liters": float(actual_liters),
        "actual_fuel_type": actual_fuel,
        "actual_beleg_nr": actual_beleg,
        "note": note,
        "pi_id": pi_id,
    }
    body = {k: v for k, v in body.items() if v not in (None, "")}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers=HTTP_HEADERS, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}", "detail": e.read().decode("utf-8", "ignore")[:300]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def read_pi_id():
    for p in ("/var/lib/tankbeleg/pi_id", "/etc/tankbeleg/pi_id"):
        try:
            return open(p).read().strip()
        except Exception:
            pass
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beleg", help="Beleg-Nr (sonst interaktiv)")
    ap.add_argument("--liter", type=float, help="Tatsaechliche Liter laut Sening-Display")
    ap.add_argument("--fuel", default="diesel", help="diesel|hvo|heizoel_leicht")
    ap.add_argument("--note", default="", help="Optionale Notiz")
    args = ap.parse_args()

    conf = load_conf()
    pi_id = read_pi_id()
    print(f"API : {conf['api_url']}")
    print(f"DB  : {conf['db_path']}")
    print(f"PI  : {pi_id or '(unbekannt)'}\n")

    if args.beleg and args.liter is not None:
        beleg = args.beleg
        liter = args.liter
        note = args.note
        fuel = args.fuel
    else:
        receipts = list_recent_receipts(conf["db_path"])
        if not receipts:
            sys.exit("Keine Belege in der lokalen DB - erst tanken!")
        print("Letzte Belege:")
        print(f"  {'#':<3} {'BELEG_NR':<10} {'LITER':<8} {'KRAFTSTOFF':<10} {'DATUM':<12} {'ZEIT':<10} {'HEX':<7}")
        for i, r in enumerate(receipts, 1):
            print(f"  {i:<3} {str(r['beleg_nr']):<10} {str(r.get('menge_liter') or 0):<8} {str(r.get('fuel_type') or '-'):<10} {str(r.get('datum') or '-'):<12} {str(r.get('zeit') or '-'):<10} {(r['hex_len'] or 0)//2}B")
        sel = input("\nWelche Nummer (1-N) oder direkt Beleg-Nr [Enter=1]: ").strip() or "1"
        if sel.isdigit() and 1 <= int(sel) <= len(receipts):
            beleg = str(receipts[int(sel)-1]["beleg_nr"])
        else:
            beleg = sel
        liter_raw = input(f"Tatsaechliche Liter fuer Beleg {beleg} (Sening-Display): ").strip()
        try:
            liter = float(liter_raw.replace(",", "."))
        except ValueError:
            sys.exit("FEHLER: Keine gueltige Zahl.")
        fuel_raw = input(f"Kraftstoff [{args.fuel}]: ").strip().lower() or args.fuel
        fuel = fuel_raw if fuel_raw in ("diesel", "hvo", "heizoel_leicht") else "diesel"
        note = input("Notiz (optional): ").strip()

    print(f"\n>>> Sende Ground-Truth: Beleg {beleg} = {liter} L {fuel}")
    res = post_label(conf["api_url"], beleg, liter, fuel, note=note, pi_id=pi_id)
    print(json.dumps(res, indent=2, ensure_ascii=False))

    if res.get("ok"):
        if res.get("match"):
            print(f"\n*** PERFEKT: Pi-Parser hat {res['parsed_liters']} L erkannt - matched Sening-Display ({liter} L).")
        else:
            print(f"\n*** ABWEICHUNG: Pi-Parser={res['parsed_liters']} L vs. Sening-Display={liter} L  (Delta {res['delta']} L)")
            print("    Hex-Dump ({} Bytes) wurde im Backend mit Ground-Truth verknuepft.".format(res['raw_hex_bytes']))
            print("    Wir koennen jetzt den Parser gegen diese Daten tunen.")
    else:
        print(f"\nFEHLER: {res.get('error')}")
        sys.exit(2)


if __name__ == "__main__":
    main()
