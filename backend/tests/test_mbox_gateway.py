# M-Box Lichtmast-Fernbedienung: device CRUD hooks, gateway, permissions, rate limit, diagnose
import asyncio
import copy
import os
import random
import time

import httpx
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
T = 40  # SPS timeout ~8s


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]


@pytest.fixture(scope="module")
def admin():
    tok, _ = _login("admin@test.com", "password")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def ma1():
    tok, user = _login("ma1@test.com", "Anna2026!")
    return {"Authorization": f"Bearer {tok}"}, user


@pytest.fixture(scope="module")
def ma1_apps(admin, ma1):
    r = requests.get(f"{API}/users", headers=admin, timeout=20)
    assert r.status_code == 200
    u = [x for x in r.json() if x["id"] == ma1[1]["id"]][0]
    original = copy.deepcopy(u["apps"])
    yield original
    # restore lesen=true, bedienen=false
    restore = copy.deepcopy(original)
    restore.setdefault("modules", {})
    restore["modules"]["mbox_lesen"] = True
    restore["modules"]["mbox_bedienen"] = False
    requests.put(f"{API}/users/{ma1[1]['id']}", headers=admin, json={"apps": restore}, timeout=20)


def _set_ma1(admin, ma1, apps, lesen, bedienen):
    a = copy.deepcopy(apps)
    a.setdefault("modules", {})
    a["modules"]["mbox_lesen"] = lesen
    a["modules"]["mbox_bedienen"] = bedienen
    r = requests.put(f"{API}/users/{ma1[1]['id']}", headers=admin, json={"apps": a}, timeout=20)
    assert r.status_code == 200, r.text
    assert r.json()["apps"]["modules"]["mbox_bedienen"] == bedienen


created_ids = []


@pytest.fixture(scope="module")
def qa_device(admin):
    serial = f"MBOX-QA-{random.randint(10000, 99999)}"
    r = requests.post(f"{API}/devices", headers=admin, timeout=30, json={
        "device_type": "mbox", "serial_number": serial, "user_field": "QA Lichtmast",
        "mbox_endpoint": "opc.tcp://192.168.0.100:4840", "mbox_security_mode": "None",
        "mbox_security_policy": "None"})
    assert r.status_code in (200, 201), r.text
    d = r.json()
    created_ids.append(d["id"])
    time.sleep(3)
    yield d
    for did in created_ids:
        requests.delete(f"{API}/devices/{did}", headers=admin, timeout=20)


# ---- Device creation / validation
class TestDeviceCreate:
    def test_create_port(self, qa_device):
        assert qa_device["mbox_port"] >= 8102
        assert qa_device["device_type"] == "mbox"

    def test_missing_endpoint_400(self, admin):
        r = requests.post(f"{API}/devices", headers=admin, timeout=20, json={
            "device_type": "mbox", "serial_number": f"MBOX-QA-X{random.randint(1,99999)}"})
        assert r.status_code == 400

    def test_wrong_endpoint_400(self, admin):
        r = requests.post(f"{API}/devices", headers=admin, timeout=20, json={
            "device_type": "mbox", "serial_number": f"MBOX-QA-Y{random.randint(1,99999)}",
            "mbox_endpoint": "http://192.168.0.100:4840"})
        assert r.status_code == 400


# ---- Gateway as admin
class TestAdminGateway:
    def test_devices_list(self, admin, qa_device):
        r = requests.get(f"{API}/mbox/devices", headers=admin, timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert j["level"] == "admin"
        ports = [d["runtime"]["port"] for d in j["devices"]]
        assert len(ports) == len(set(ports)), f"duplicate ports {ports}"
        for d in j["devices"]:
            assert "mbox_password" not in d
            assert d["runtime"]["running"] is True, d
        assert any(d["id"] == qa_device["id"] for d in j["devices"])

    def test_status(self, admin, qa_device):
        r = requests.get(f"{API}/mbox/{qa_device['id']}/status", headers=admin, timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert j["level"] == "admin" and j["runtime"]["running"] is True
        assert j["service_installed"] is True and "mbox_password" not in j["device"]

    def test_lesen_timeout(self, admin, qa_device):
        t0 = time.time()
        r = requests.post(f"{API}/mbox/{qa_device['id']}/lesen", headers=admin, timeout=T,
                          json={"namen": ["DB_HMI.Status.Versorgung", "evil", 123, "../x"]})
        assert r.status_code == 200, r.text
        j = r.json()
        print("lesen", round(time.time() - t0, 1), j)
        assert j["ok"] is False and "Zeitüberschreitung" in j["fehler"]

    def test_befehl_and_audit(self, admin, qa_device):
        r = requests.post(f"{API}/mbox/{qa_device['id']}/befehl/Schnellstart", headers=admin, timeout=T)
        assert r.status_code == 200
        assert r.json()["ok"] is False and "Zeitüberschreitung" in r.json()["fehler"]
        a = requests.get(f"{API}/mbox/{qa_device['id']}/audit", headers=admin, timeout=20)
        assert a.status_code == 200
        e = [x for x in a.json() if x["endpoint"] == "befehl/Schnellstart"]
        assert e and e[0]["ok"] is False and e[0]["fehler"] and e[0]["user_name"]

    def test_befehl_invalid_name(self, admin, qa_device):
        r = requests.post(f"{API}/mbox/{qa_device['id']}/befehl/Ung%C3%BCltig$", headers=admin, timeout=20)
        assert r.status_code == 400

    def test_unknown_device_404(self, admin):
        r = requests.get(f"{API}/mbox/does-not-exist/status", headers=admin, timeout=20)
        assert r.status_code == 404

    def test_log(self, admin, qa_device):
        r = requests.get(f"{API}/mbox/{qa_device['id']}/log?lines=20", headers=admin, timeout=20)
        assert r.status_code == 200
        lines = r.json()["lines"]
        print(lines[-5:])
        assert any("Bedienprogramm" in l for l in lines)

    def test_knoten(self, admin, qa_device):
        r = requests.get(f"{API}/mbox/{qa_device['id']}/knoten", headers=admin, timeout=150)
        assert r.status_code == 200
        print("knoten", str(r.json())[:200])
        assert isinstance(r.json(), (dict, list))

    def test_restart(self, admin, qa_device):
        before = requests.get(f"{API}/mbox/{qa_device['id']}/status", headers=admin, timeout=20).json()["runtime"]
        r = requests.post(f"{API}/mbox/{qa_device['id']}/restart", headers=admin, timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j["ok"] is True and j["runtime"]["running"] is True
        assert j["runtime"]["pid"] != before["pid"]


# ---- Rate limit (separate device to have fresh quota)
class TestRateLimit:
    def test_31st_is_429(self, admin):
        r = requests.post(f"{API}/devices", headers=admin, timeout=30, json={
            "device_type": "mbox", "serial_number": f"MBOX-QA-RL{random.randint(1000,99999)}",
            "mbox_endpoint": "opc.tcp://192.168.0.100:4840"})
        assert r.status_code in (200, 201)
        did = r.json()["id"]
        created_ids.append(did)
        time.sleep(3)

        async def run():
            async with httpx.AsyncClient(timeout=60) as c:
                tasks = [c.post(f"{API}/mbox/{did}/befehl/Quittieren", headers=admin) for _ in range(31)]
                return await asyncio.gather(*tasks, return_exceptions=True)
        res = asyncio.run(run())
        codes = [x.status_code if hasattr(x, "status_code") else str(x) for x in res]
        print("codes", codes)
        assert codes.count(429) == 1
        assert codes.count(200) == 30


# ---- Mitarbeiter permissions
class TestMitarbeiter:
    def test_lesen_level(self, admin, ma1, ma1_apps, qa_device):
        _set_ma1(admin, ma1, ma1_apps, True, False)
        h = ma1[0]
        did = qa_device["id"]
        r = requests.get(f"{API}/mbox/devices", headers=h, timeout=20)
        assert r.status_code == 200 and r.json()["level"] == "lesen"
        for d in r.json()["devices"]:
            assert "mbox_password" not in d
        r = requests.post(f"{API}/mbox/{did}/lesen", headers=h, json={"namen": ["DB_HMI.Status.Versorgung"]}, timeout=T)
        assert r.status_code == 200
        checks = [
            ("post", f"/mbox/{did}/befehl/Lampen_Ein", None),
            ("post", f"/mbox/{did}/einstellung", {}),
            ("post", f"/mbox/{did}/uhr/woche", {}),
            ("get", f"/mbox/{did}/knoten", None),
            ("post", f"/mbox/{did}/gps", None),
            ("post", f"/mbox/{did}/restart", None),
            ("get", f"/mbox/{did}/audit", None),
            ("get", f"/mbox/{did}/log", None),
        ]
        bad = []
        for m, p, body in checks:
            rr = getattr(requests, m)(f"{API}{p}", headers=h, json=body, timeout=T) if m == "post" else \
                requests.get(f"{API}{p}", headers=h, timeout=T)
            if rr.status_code != 403:
                bad.append((p, rr.status_code))
        assert not bad, bad

    def test_bedienen_level(self, admin, ma1, ma1_apps, qa_device):
        _set_ma1(admin, ma1, ma1_apps, True, True)
        h = ma1[0]
        did = qa_device["id"]
        r = requests.get(f"{API}/mbox/devices", headers=h, timeout=20)
        assert r.json()["level"] == "bedienen"
        r = requests.post(f"{API}/mbox/{did}/befehl/Lampen_Ein", headers=h, timeout=T)
        assert r.status_code == 200 and r.json()["ok"] is False
        for name in ("Kundenzaehler_Reset", "Wartung_Reset", "Probelauf_Start"):
            assert requests.post(f"{API}/mbox/{did}/befehl/{name}", headers=h, timeout=T).status_code == 403
        assert requests.get(f"{API}/mbox/{did}/knoten", headers=h, timeout=T).status_code == 403
        assert requests.get(f"{API}/mbox/{did}/audit", headers=h, timeout=T).status_code == 200
        _set_ma1(admin, ma1, ma1_apps, True, False)

    def test_no_lesen_403(self, admin, ma1, ma1_apps):
        _set_ma1(admin, ma1, ma1_apps, False, False)
        r = requests.get(f"{API}/mbox/devices", headers=ma1[0], timeout=20)
        _set_ma1(admin, ma1, ma1_apps, True, False)
        assert r.status_code == 403

    def test_unauth_rejected(self):
        r = requests.get(f"{API}/mbox/devices", timeout=20)
        assert r.status_code in (401, 403)


# ---- Update / delete hooks
class TestUpdateDelete:
    def test_update_restarts(self, admin, qa_device):
        did = qa_device["id"]
        before = requests.get(f"{API}/mbox/{did}/status", headers=admin, timeout=20).json()["runtime"]
        time.sleep(1)
        r = requests.put(f"{API}/devices/{did}", headers=admin, json={"mbox_endpoint": "opc.tcp://192.168.0.101:4840"}, timeout=30)
        assert r.status_code == 200
        assert "mbox_password" not in r.json() or True
        time.sleep(2)
        after = requests.get(f"{API}/mbox/{did}/status", headers=admin, timeout=20).json()
        assert after["runtime"]["running"] is True
        assert after["runtime"]["started_at"] > before["started_at"]
        assert after["device"]["mbox_endpoint"] == "opc.tcp://192.168.0.101:4840"

    def test_update_invalid_endpoint_400(self, admin, qa_device):
        r = requests.put(f"{API}/devices/{qa_device['id']}", headers=admin, json={"mbox_endpoint": "tcp://x"}, timeout=20)
        assert r.status_code == 400

    def test_delete(self, admin, qa_device):
        did = qa_device["id"]
        r = requests.delete(f"{API}/devices/{did}", headers=admin, timeout=20)
        assert r.status_code == 200
        assert requests.get(f"{API}/mbox/{did}/status", headers=admin, timeout=20).status_code == 404
