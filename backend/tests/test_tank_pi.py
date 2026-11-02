"""Tankgeber: Geraet anlegen -> Pi-Setup -> Skript -> Ingest (Prozent/Liter/Alarm/GPS) -> Liste/Detail/Verlauf."""
import os
import re
import subprocess
import time

import pytest
import requests

API = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") + "/api"
T = 30
S = {}


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=T)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


@pytest.fixture(scope="module")
def admin():
    return _login("admin@test.com", "password")


@pytest.fixture(scope="module")
def tank(admin):
    serial = f"TANK-QA-{int(time.time())}"
    r = requests.post(f"{API}/devices", headers=admin, json={"device_type": "tank", "serial_number": serial, "user_field": "QA Tank",
                                                              "tank_capacity": "3.000 L", "tank_warn_pct": 30, "tank_crit_pct": 15}, timeout=T)
    assert r.status_code in (200, 201), r.text
    d = r.json()
    yield d
    requests.delete(f"{API}/devices/{d['id']}", headers=admin, timeout=T)


def ingest(dev_id, key, pct, ohm=95.0, fehler=None, gps=None):
    rd = {"ts": time.time(), "pi_version": "1.0.0", "samples": 50}
    if pct is not None:
        rd["fuellstand_pct"] = pct
        rd["ohm"] = ohm
    if fehler:
        rd["fehler"] = fehler
    return requests.post(f"{API}/tank/ingest", json={"device_id": dev_id, "api_key": key, "readings": [rd],
                                                     "gps": gps or {"fix": True, "lat": 50.4335, "lon": 7.472, "mode": 3}, "health": {"ppp0": True, "cpu_temp_c": 44.1}}, timeout=T)


class TestSetup:
    def test_device_has_tank_fields(self, admin, tank):
        assert tank["tank_capacity"] == "3.000 L" and tank["tank_warn_pct"] == 30 and tank["tank_crit_pct"] == 15

    def test_pi_setup_script(self, admin, tank):
        r = requests.post(f"{API}/tank/{tank['id']}/pi-setup", headers=admin, json={"enable_lte": True, "lte_apn": "internet.m2mportal.de", "interval": 60}, timeout=T)
        assert r.status_code == 200, r.text
        script = requests.get(r.json()["download_url"], timeout=T).text
        S["key"] = re.search(r"^device_key = ([0-9a-f]+)$", script, re.M).group(1)
        assert len(S["key"]) == 48
        for must in ("tank_pi_sync.service", "ADC(26)", "R_VOLL = 190.0", "RPI-RP2", "/dev/tank-pico", "lte-failover.service",
                     "internet.m2mportal.de", "[7/7]", "/tank/ingest", "gpspipe", "SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"2e8a\""):
            assert must in script, must
        assert "{{" not in script.replace("${{", "") or "{{\"fehler\"" not in script  # f-string-Reste
        chk = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
        assert chk.returncode == 0, chk.stderr
        # eingebettetes Python-Skript syntaktisch pruefen
        py = script.split("<< 'SYNC_SCRIPT'\n")[1].split("\nSYNC_SCRIPT")[0]
        compile(py, "tank_pi_sync.py", "exec")
        pico = script.split("<< 'PICO'\n")[1].split("\nPICO")[0]
        compile(pico, "main.py", "exec")

    def test_setup_without_lte(self, admin, tank):
        r = requests.post(f"{API}/tank/{tank['id']}/pi-setup", headers=admin, json={"enable_lte": False}, timeout=T)
        script = requests.get(r.json()["download_url"], timeout=T).text
        assert "[6/6]" in script and "lte-failover" not in script
        S["key"] = re.search(r"^device_key = ([0-9a-f]+)$", script, re.M).group(1)

    def test_setup_requires_admin(self, tank):
        r = requests.post(f"{API}/tank/{tank['id']}/pi-setup", headers=_login("kunde.meier@test.com", "Meier2026!"), json={}, timeout=T)
        assert r.status_code == 403


class TestIngest:
    def test_bad_key(self, tank):
        assert ingest(tank["id"], "falsch", 50).status_code == 401

    def test_ok_reading(self, admin, tank):
        r = ingest(tank["id"], S["key"], 62.5, ohm=118.8)
        assert r.status_code == 200, r.text
        assert r.json()["liters"] == 1875 and r.json()["alarm_state"] == "ok"
        d = requests.get(f"{API}/tank/{tank['id']}", headers=admin, timeout=T).json()
        assert d["fuel_level_pct"] == 62.5 and d["liters"] == 1875 and d["capacity_l"] == 3000 and d["ohm"] == 118.8
        assert d["pi"]["online"] is True and d["latitude"] == 50.4335 and d["gps"]["fix"] is True
        assert d["pi"]["health"]["ppp0"] is True and d["pi"]["version"] == "1.0.0"

    def test_warn_then_crit_then_recover(self, admin, tank):
        assert ingest(tank["id"], S["key"], 28).json()["alarm_state"] == "warn"
        assert ingest(tank["id"], S["key"], 27).json()["alarm_state"] == "warn"  # kein Doppel-Alarm
        assert ingest(tank["id"], S["key"], 12).json()["alarm_state"] == "crit"
        assert ingest(tank["id"], S["key"], 33).json()["alarm_state"] == "crit"  # Hysterese (< warn+5)
        assert ingest(tank["id"], S["key"], 40).json()["alarm_state"] == "ok"
        d = requests.get(f"{API}/tank/{tank['id']}", headers=admin, timeout=T).json()
        al = d["alarms"]
        assert len(al) == 2, al
        assert {a["severity"] for a in al} == {"warning", "alarm"}
        assert all(a["resolved_at"] for a in al)
        assert "Fuellstand 12 %" in next(a["alarm_text"] for a in al if a["severity"] == "alarm")

    def test_sensor_error(self, admin, tank):
        r = ingest(tank["id"], S["key"], None, fehler="Geber offen / Kabelbruch", gps={"fix": False})
        assert r.status_code == 200
        d = requests.get(f"{API}/tank/{tank['id']}", headers=admin, timeout=T).json()
        assert d["sensor_error"] == "Geber offen / Kabelbruch" and d["latitude"] == 50.4335  # alte Position bleibt

    def test_telemetry_history(self, admin, tank):
        r = requests.get(f"{API}/tank/{tank['id']}/telemetry", headers=admin, params={"hours": 24}, timeout=T)
        assert r.status_code == 200
        pts = r.json()["points"]
        assert len(pts) >= 7 and pts[0]["fuel_level_pct"] == 62.5 and pts[0]["liters"] == 1875

    def test_in_lists(self, admin, tank):
        lst = requests.get(f"{API}/tank/devices", headers=admin, timeout=T).json()["devices"]
        me = next(x for x in lst if x["id"] == tank["id"])
        assert me["pi"]["online"] and me["alarm_state"] == "ok"
        kunde = _login("kunde.meier@test.com", "Meier2026!")
        assert requests.get(f"{API}/tank/devices", headers=kunde, timeout=T).json()["devices"] == []
        assert requests.get(f"{API}/tank/{tank['id']}", headers=kunde, timeout=T).status_code == 403
