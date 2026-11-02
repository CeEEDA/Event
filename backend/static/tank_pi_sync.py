#!/usr/bin/env python3
"""Tankgeber-Pi: liest den Pico (JSON-Zeilen auf /dev/ttyACM0), GPS ueber gpsd und meldet
alle INTERVAL Sekunden an das Eventenergie-Portal. Offline-Puffer bis 48 h.
Konfiguration: /etc/tank_pi.conf  (api_url, device_key, device_id, interval)"""
import configparser
import json
import logging
import os
import subprocess
import threading
import time
from collections import deque
from statistics import median

import requests
import serial

VERSION = "1.0.0"
CONF = "/etc/tank_pi.conf"
BUFFER_FILE = "/var/lib/tank_pi/buffer.json"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tank_pi")


def load_conf():
    cp = configparser.ConfigParser()
    cp.read(CONF)
    s = cp["tank"]
    return {"api_url": s["api_url"].rstrip("/"), "device_key": s["device_key"], "device_id": s["device_id"],
            "interval": s.getint("interval", 60), "serial": s.get("serial", "/dev/ttyACM0")}


# ---------------- Pico (Tankgeber) ----------------
_lock = threading.Lock()
_samples = []           # (ts, pct, ohm) seit letztem Senden
_last = {"fehler": "Noch keine Daten vom Pico", "ts": 0}


def pico_reader(port):
    global _last
    while True:
        try:
            with serial.Serial(port, 115200, timeout=3) as ser:
                log.info(f"Pico verbunden: {port}")
                while True:
                    line = ser.readline().decode(errors="ignore").strip()
                    if not line.startswith("{"):
                        continue
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    d["ts"] = time.time()
                    with _lock:
                        _last = d
                        if "fuellstand" in d:
                            _samples.append((d["ts"], float(d["fuellstand"]), float(d.get("ohm") or 0)))
                            if len(_samples) > 600:
                                del _samples[:-600]
        except serial.SerialException as e:
            with _lock:
                _last = {"fehler": f"Pico nicht verbunden ({e})", "ts": 0}
            time.sleep(5)
        except Exception as e:
            log.warning(f"Pico-Leser: {e}")
            time.sleep(5)


def take_reading():
    """Median der Messwerte seit dem letzten Senden (glaettet Schwappen im Tank)."""
    with _lock:
        s = list(_samples)
        _samples.clear()
        last = dict(_last)
    out = {"ts": time.time(), "pi_version": VERSION}
    if s:
        out["fuellstand_pct"] = round(median(x[1] for x in s), 1)
        out["ohm"] = round(median(x[2] for x in s), 1)
        out["samples"] = len(s)
    if last.get("fehler") and (time.time() - last.get("ts", 0) < 30 or not s):
        out["fehler"] = last["fehler"]
    elif not s:
        out["fehler"] = "Keine aktuellen Daten vom Pico"
    return out


# ---------------- GPS (gpsd) ----------------
def read_gps():
    try:
        r = subprocess.run(["gpspipe", "-w", "-n", "12"], capture_output=True, text=True, timeout=8)
        best = None
        for line in r.stdout.splitlines():
            if '"class":"TPV"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("mode", 0) >= 2 and "lat" in d and "lon" in d:
                best = {"fix": True, "lat": d["lat"], "lon": d["lon"], "mode": d.get("mode"),
                        "alt": d.get("altMSL", d.get("alt")), "speed": d.get("speed"), "time": d.get("time"),
                        "epx": d.get("epx"), "epy": d.get("epy")}
        return best or {"fix": False}
    except Exception as e:
        return {"fix": False, "error": str(e)[:80]}


# ---------------- Pi-Gesundheit (LTE etc.) ----------------
def health():
    h = {"version": VERSION}
    try:
        h["uptime_s"] = int(float(open("/proc/uptime").read().split()[0]))
    except Exception:
        pass
    try:
        h["cpu_temp_c"] = round(int(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000, 1)
    except Exception:
        pass
    try:
        h["ppp0"] = os.path.exists("/sys/class/net/ppp0")
        r = subprocess.run(["ip", "route", "get", "8.8.8.8"], capture_output=True, text=True, timeout=3)
        h["route"] = r.stdout.split("dev")[1].split()[0] if "dev" in r.stdout else None
    except Exception:
        pass
    return h


# ---------------- Puffer ----------------
def load_buffer():
    try:
        with open(BUFFER_FILE) as f:
            return deque(json.load(f), maxlen=2880)
    except Exception:
        return deque(maxlen=2880)


def save_buffer(buf):
    try:
        os.makedirs(os.path.dirname(BUFFER_FILE), exist_ok=True)
        with open(BUFFER_FILE, "w") as f:
            json.dump(list(buf), f)
    except Exception as e:
        log.warning(f"Puffer speichern: {e}")


def main():
    conf = load_conf()
    threading.Thread(target=pico_reader, args=(conf["serial"],), daemon=True).start()
    buf = load_buffer()
    log.info(f"Tankgeber-Sync v{VERSION} gestartet, Intervall {conf['interval']} s, Puffer {len(buf)}")
    time.sleep(min(15, conf["interval"]))  # erste Messwerte sammeln
    while True:
        reading = take_reading()
        buf.append(reading)
        payload = {"device_id": conf["device_id"], "api_key": conf["device_key"], "gps": read_gps(), "health": health(),
                   "readings": list(buf)}
        try:
            r = requests.post(f"{conf['api_url']}/tank/ingest", json=payload, timeout=30)
            if r.status_code == 200:
                buf.clear()
                save_buffer(buf)
                resp = r.json()
                log.info(f"gesendet: {reading.get('fuellstand_pct', '-')} % / {reading.get('ohm', '-')} Ohm"
                         f"{' / ' + reading['fehler'] if reading.get('fehler') else ''} -> {resp.get('liters', '-')} L")
            else:
                log.warning(f"Portal {r.status_code}: {r.text[:120]} (Puffer {len(buf)})")
                save_buffer(buf)
        except Exception as e:
            log.warning(f"Portal nicht erreichbar: {e} (Puffer {len(buf)})")
            save_buffer(buf)
        time.sleep(conf["interval"])


if __name__ == "__main__":
    main()
