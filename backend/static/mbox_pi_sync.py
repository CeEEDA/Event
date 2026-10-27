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
import re
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
VERSION = "1.2.0"

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
    """Position von gpsd (JSON-WATCH, entspricht 'gpspipe -w'). NICHT direkt /dev/ttyACM0 lesen.
    mode: 1 = kein Fix, 2 = 2D, 3 = 3D; lat/lon nur ab mode >= 2 gueltig."""
    result = {"lat": None, "lon": None, "fix": False, "mode": 0, "sats": None, "sats_visible": None,
              "epx": None, "epy": None, "alt": None, "speed": None, "time": None, "gpsd": False}
    try:
        s = socket.create_connection(("127.0.0.1", 2947), timeout=2)
    except Exception:
        return result
    result["gpsd"] = True
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
                    result["mode"] = max(result["mode"], mode)
                    if mode >= 2 and msg.get("lat") is not None and msg.get("lon") is not None:
                        result.update({
                            "lat": float(msg["lat"]), "lon": float(msg["lon"]), "fix": True, "mode": mode,
                            "epx": msg.get("epx"), "epy": msg.get("epy"),
                            "alt": msg.get("altMSL", msg.get("alt")), "speed": msg.get("speed"), "time": msg.get("time"),
                        })
                elif msg.get("class") == "SKY":
                    sats = msg.get("satellites", [])
                    result["sats_visible"] = msg.get("nSat", len(sats))
                    result["sats"] = msg.get("uSat", len([x for x in sats if x.get("used")]))
            if result["mode"] >= 3 and result["sats"] is not None:
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

def list_cards():
    """ALSA-Karten per 'aplay -l' -> [{"card":1,"name":"USB Audio","device":"plughw:1,0"}]"""
    out = []
    try:
        r = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=5)
        for m in re.finditer(r"^card (\d+): ([^\[]+)\[([^\]]+)\], device (\d+)", r.stdout, re.M):
            out.append({"card": int(m.group(1)), "name": m.group(3).strip(), "id": m.group(2).strip(),
                        "device": f"plughw:{m.group(1)},{m.group(4)}"})
    except Exception as e:
        log.debug(f"aplay -l: {e}")
    return out


class Player:
    def __init__(self, conf):
        self.conf = conf
        self.proc = None
        self.file = None
        self.since = None
        self.loop = False
        self.lock = threading.Lock()
        self.last_error = None
        self.used_device = None
        self._err_file = None

    def set_volume(self, pct):
        pct = max(0, min(100, int(pct)))
        dev = self.conf.get("audio_device") or ""
        ctl_dev = ""
        m = re.match(r"^(?:plug)?hw:(\d+)", dev)
        if m:
            ctl_dev = f"hw:{m.group(1)}"
        for ctl in ("PCM", "Master", "Speaker", "Headphone", "Digital"):
            try:
                args = ["amixer"]
                if ctl_dev:
                    args += ["-D", ctl_dev]
                r = subprocess.run(args + ["sset", ctl, f"{pct}%"], capture_output=True, timeout=5)
                if r.returncode == 0:
                    return True
            except Exception:
                pass
        return False

    def _candidates(self):
        """Konfiguriertes Geraet zuerst, sonst Standard + jede gefundene Karte (USB zuerst)."""
        if self.conf.get("audio_device"):
            return [self.conf["audio_device"]]
        cards = list_cards()
        usb = [c["device"] for c in cards if "usb" in (c["name"] + c["id"]).lower()]
        rest = [c["device"] for c in cards if c["device"] not in usb]
        return [""] + usb + rest

    def _try_start(self, path, loop, device):
        cmd = ["mpg123", "-q"]
        if device:
            cmd += ["-a", device]
        if loop:
            cmd += ["--loop", "-1"]
        cmd.append(path)
        import tempfile
        err = tempfile.TemporaryFile()
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=err)
        except FileNotFoundError:
            return None, "mpg123 nicht installiert"
        time.sleep(1.5)
        if proc.poll() is not None:
            err.seek(0)
            msg = err.read().decode("utf-8", "replace").strip().splitlines()
            return None, (msg[-1] if msg else f"mpg123 beendet mit Code {proc.returncode}")
        self._err_file = err
        return proc, None

    def play(self, filename, loop=False):
        path = os.path.join(AUDIO_DIR, os.path.basename(filename))
        if not os.path.exists(path):
            return False, f"Datei fehlt auf dem Pi: {filename}"
        with self.lock:
            self._stop_locked()
            fehler = []
            for dev in self._candidates():
                proc, err = self._try_start(path, loop, dev)
                if proc:
                    self.proc, self.used_device = proc, (dev or "default")
                    self.file, self.since, self.loop = os.path.basename(path), time.time(), loop
                    self.last_error = None
                    log.info(f"Audio START {self.file} loop={loop} device={self.used_device}")
                    return True, f"gestartet ({self.used_device})"
                fehler.append(f"{dev or 'default'}: {err}")
                log.warning(f"Audio Start fehlgeschlagen auf {dev or 'default'}: {err}")
            self.last_error = " | ".join(fehler)[:400]
            return False, self.last_error or "kein Audiogeraet gefunden"

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
                return {"file": self.file, "since": self.since, "loop": self.loop, "device": self.used_device}
            if self.proc is not None:
                if self.proc.returncode not in (0, None, -15) and self._err_file:
                    try:
                        self._err_file.seek(0)
                        tail = self._err_file.read().decode("utf-8", "replace").strip().splitlines()
                        self.last_error = f"mpg123 abgebrochen (Code {self.proc.returncode}): {tail[-1] if tail else ''}"[:400]
                        log.warning(self.last_error)
                    except Exception:
                        pass
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


# ---------------- Selbst-Update ----------------

def self_update(conf, want_sha):
    """Portal liefert SHA-256 des aktuellen Skripts; bei Abweichung laden und neu starten."""
    try:
        me = os.path.abspath(__file__)
        with open(me, "rb") as f:
            have = hashlib.sha256(f.read()).hexdigest()
        if not want_sha or have == want_sha:
            return
        r = requests.get(f"{conf['api_url']}/mbox/pi/{conf['device_id']}/script", params={"api_key": conf["device_key"]}, timeout=30)
        if r.status_code != 200 or hashlib.sha256(r.content).hexdigest() != want_sha:
            log.warning(f"Script-Update: HTTP {r.status_code} / Hash passt nicht")
            return
        with open(me + ".new", "wb") as f:
            f.write(r.content)
        os.replace(me + ".new", me)
        log.info("Skript aktualisiert - Neustart")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        log.warning(f"Script-Update: {e}")


# ---------------- Hauptschleife ----------------

def main():
    conf = load_conf()
    player = Player(conf)
    player.set_volume(conf["volume"])
    log.info(f"M-Box Pi Sync v{VERSION} gestartet -> {conf['api_url']} ({conf['device_id'][:8]}...)")
    last_gps, last_gps_t, last_files_t, have = None, 0, 0, {}
    cards, last_cards_t = [], 0
    while True:
        t0 = time.time()
        try:
            if t0 - last_gps_t > 10:
                last_gps, last_gps_t = read_gps(), t0
            if t0 - last_files_t > 60 or not have:
                have, last_files_t = local_files(), t0
            if t0 - last_cards_t > 60:
                cards, last_cards_t = list_cards(), t0
            payload = {
                "api_key": conf["device_key"],
                "version": VERSION,
                "gps": last_gps,
                "playing": player.state(),
                "files": sorted(have.keys()),
                "volume": conf["volume"],
                "audio_device": conf.get("audio_device") or "",
                "audio_cards": cards,
                "last_error": player.last_error,
                "hostname": socket.gethostname(),
            }
            r = requests.post(f"{conf['api_url']}/mbox/pi/{conf['device_id']}/sync", json=payload, timeout=15)
            if r.status_code != 200:
                log.warning(f"Sync HTTP {r.status_code}: {r.text[:200]}")
            else:
                data = r.json()
                cfg = data.get("config") or {}
                if "audio_device" in cfg and (cfg.get("audio_device") or "") != (conf.get("audio_device") or ""):
                    conf["audio_device"] = cfg.get("audio_device") or ""
                    log.info(f"Audiogeraet vom Portal: '{conf['audio_device'] or 'auto'}'")
                    player.set_volume(conf["volume"])
                if cfg.get("volume") is not None and int(cfg["volume"]) != conf["volume"]:
                    conf["volume"] = int(cfg["volume"])
                    player.set_volume(conf["volume"])
                self_update(conf, data.get("script_sha256"))
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
