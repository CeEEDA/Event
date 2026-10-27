#!/usr/bin/env python3
"""
M-Box Pi Sync - Eventenergie Portal
===================================
Laeuft auf dem Raspberry Pi im Lichtmast (Soundkarte + USB-GPS).
Meldet sich alle paar Sekunden beim Portal, liefert GPS-Position und
Abspiel-Status und holt sich Befehle (Durchsage starten/stoppen) sowie
neue Audiodateien ab.

Konfiguration: /etc/mbox_pi.conf (wird vom Setup-Skript erstellt)
Status:        sudo systemctl status mbox_pi
Log:           sudo journalctl -u mbox_pi -f
"""
import configparser
import hashlib
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time

import requests

CONF_PATH = "/etc/mbox_pi.conf"
AUDIO_DIR = "/opt/mbox_audio"
POLL_SEC = 3
VERSION = "1.0.0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mbox_pi")


def load_conf():
    cp = configparser.ConfigParser()
    cp.read(CONF_PATH)
    s = cp["mbox_pi"]
    return {
        "api_url": s.get("api_url").rstrip("/"),
        "device_id": s.get("device_id"),
        "device_key": s.get("device_key"),
        "audio_device": s.get("audio_device", fallback=""),
        "volume": s.getint("volume", fallback=85),
    }


# ---------------- GPS (gpsd Socket, wie dse5510_sync) ----------------

def read_gps(timeout=4.0):
    result = {"lat": None, "lon": None, "fix": False, "mode": 0, "sats": None}
    try:
        s = socket.create_connection(("127.0.0.1", 2947), timeout=2)
    except Exception:
        return result
    try:
        s.settimeout(timeout)
        s.sendall(b'?WATCH={"enable":true,"json":true}\n')
        buf = b""
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                chunk = s.recv(8192)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    msg = json.loads(line.decode("utf-8", "replace"))
                except Exception:
                    continue
                if msg.get("class") == "TPV":
                    mode = int(msg.get("mode", 0))
                    if mode >= 2 and msg.get("lat") is not None and mode >= result["mode"]:
                        result.update({"lat": float(msg["lat"]), "lon": float(msg["lon"]), "fix": True, "mode": mode})
                elif msg.get("class") == "SKY":
                    result["sats"] = len([x for x in msg.get("satellites", []) if x.get("used")])
            if result["mode"] >= 3:
                break
    except Exception as e:
        log.debug(f"GPS: {e}")
    finally:
        try:
            s.close()
        except Exception:
            pass
    return result


# ---------------- Audio ----------------

class Player:
    def __init__(self, conf):
        self.conf = conf
        self.proc = None
        self.file = None
        self.since = None
        self.loop = False
        self.lock = threading.Lock()

    def set_volume(self, pct):
        pct = max(0, min(100, int(pct)))
        for ctl in ("PCM", "Master", "Speaker", "Headphone"):
            try:
                args = ["amixer"]
                if self.conf.get("audio_device"):
                    args += ["-D", self.conf["audio_device"]]
                r = subprocess.run(args + ["sset", ctl, f"{pct}%"], capture_output=True, timeout=5)
                if r.returncode == 0:
                    return True
            except Exception:
                pass
        return False

    def play(self, filename, loop=False):
        path = os.path.join(AUDIO_DIR, os.path.basename(filename))
        if not os.path.exists(path):
            return False, f"Datei fehlt auf dem Pi: {filename}"
        with self.lock:
            self._stop_locked()
            cmd = ["mpg123", "-q"]
            if self.conf.get("audio_device"):
                cmd += ["-a", self.conf["audio_device"]]
            if loop:
                cmd += ["--loop", "-1"]
            cmd.append(path)
            try:
                self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                return False, "mpg123 nicht installiert"
            self.file, self.since, self.loop = os.path.basename(path), time.time(), loop
        log.info(f"Audio START {self.file} loop={loop}")
        return True, "gestartet"

    def _stop_locked(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.proc, self.file, self.since, self.loop = None, None, None, False

    def stop(self):
        with self.lock:
            was = self.file
            self._stop_locked()
        log.info(f"Audio STOP ({was})")
        return True, "gestoppt"

    def state(self):
        with self.lock:
            if self.proc and self.proc.poll() is None:
                return {"file": self.file, "since": self.since, "loop": self.loop}
            if self.proc is not None:
                self.proc, self.file, self.since, self.loop = None, None, None, False
            return None


# ---------------- Dateien ----------------

def local_files():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    out = {}
    for n in os.listdir(AUDIO_DIR):
        p = os.path.join(AUDIO_DIR, n)
        if os.path.isfile(p):
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            out[n] = h.hexdigest()
    return out


def sync_files(conf, manifest, have):
    """Laedt fehlende/geaenderte Dateien, loescht entfernte."""
    wanted = {m["name"]: m for m in manifest}
    for name, meta in wanted.items():
        if have.get(name) == meta.get("sha256"):
            continue
        try:
            url = f"{conf['api_url']}/mbox/pi/{conf['device_id']}/audio/{requests.utils.quote(name)}"
            with requests.get(url, params={"api_key": conf["device_key"]}, stream=True, timeout=120) as r:
                r.raise_for_status()
                tmp = os.path.join(AUDIO_DIR, "." + name + ".part")
                with open(tmp, "wb") as f:
                    shutil.copyfileobj(r.raw, f)
                os.replace(tmp, os.path.join(AUDIO_DIR, name))
            log.info(f"Audio geladen: {name}")
        except Exception as e:
            log.warning(f"Download {name}: {e}")
    for name in list(have):
        if name not in wanted:
            try:
                os.remove(os.path.join(AUDIO_DIR, name))
                log.info(f"Audio entfernt: {name}")
            except Exception:
                pass


# ---------------- Hauptschleife ----------------

def main():
    conf = load_conf()
    player = Player(conf)
    player.set_volume(conf["volume"])
    log.info(f"M-Box Pi Sync v{VERSION} gestartet -> {conf['api_url']} ({conf['device_id'][:8]}...)")
    last_gps, last_gps_t, last_files_t, have = None, 0, 0, {}
    while True:
        t0 = time.time()
        try:
            if t0 - last_gps_t > 20:
                last_gps, last_gps_t = read_gps(), t0
            if t0 - last_files_t > 60 or not have:
                have, last_files_t = local_files(), t0
            payload = {
                "api_key": conf["device_key"],
                "version": VERSION,
                "gps": last_gps,
                "playing": player.state(),
                "files": sorted(have.keys()),
                "volume": conf["volume"],
                "hostname": socket.gethostname(),
            }
            r = requests.post(f"{conf['api_url']}/mbox/pi/{conf['device_id']}/sync", json=payload, timeout=15)
            if r.status_code != 200:
                log.warning(f"Sync HTTP {r.status_code}: {r.text[:200]}")
            else:
                data = r.json()
                for cmd in data.get("pending_commands", []):
                    ok, msg = False, "unbekannter Befehl"
                    typ, p = cmd.get("command"), cmd.get("params") or {}
                    if typ == "play":
                        ok, msg = player.play(p.get("file", ""), bool(p.get("loop")))
                    elif typ == "stop":
                        ok, msg = player.stop()
                    elif typ == "volume":
                        conf["volume"] = int(p.get("volume", conf["volume"]))
                        ok, msg = player.set_volume(conf["volume"]), f"Lautstaerke {conf['volume']}%"
                    elif typ == "sync_files":
                        have = local_files()
                        sync_files(conf, data.get("audio_manifest", []), have)
                        have = local_files()
                        ok, msg = True, f"{len(have)} Dateien"
                    try:
                        requests.post(f"{conf['api_url']}/mbox/pi/{conf['device_id']}/command-result",
                                      json={"api_key": conf["device_key"], "command_id": cmd.get("id"), "success": ok, "message": msg}, timeout=10)
                    except Exception as e:
                        log.warning(f"Result senden: {e}")
                manifest = data.get("audio_manifest")
                if manifest is not None:
                    names = {m["name"]: m.get("sha256") for m in manifest}
                    if names != have:
                        sync_files(conf, manifest, have)
                        have, last_files_t = local_files(), time.time()
        except requests.RequestException as e:
            log.warning(f"Portal nicht erreichbar: {e}")
        except Exception as e:
            log.exception(f"Fehler in Schleife: {e}")
        time.sleep(max(0.5, POLL_SEC - (time.time() - t0)))


if __name__ == "__main__":
    if not os.path.exists(CONF_PATH):
        print(f"Konfiguration fehlt: {CONF_PATH}")
        sys.exit(1)
    main()
