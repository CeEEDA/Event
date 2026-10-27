# M-Box Ausbaustufe: Pi-Setup/Sync/Audio, Auftrags-Zuweisung, Kunden-Rechte, Kundennummer
import os
import re
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
T = 40
ORDER = 999901
STATE = {}


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=T)
    assert r.status_code == 200, r.text
    d = r.json()
    return d, {"Authorization": f"Bearer {d.get('token') or d.get('access_token')}"}


@pytest.fixture(scope="module")
def admin():
    return login("admin@test.com", "password")[1]


@pytest.fixture(scope="module")
def ma1():
    return login("ma1@test.com", "Anna2026!")[1]


@pytest.fixture(scope="module")
def kunde_login():
    return login("kunde.meier@test.com", "Meier2026!")


@pytest.fixture(scope="module")
def kunde(kunde_login):
    return kunde_login[1]


@pytest.fixture(scope="module")
def ids(admin):
    r = requests.get(f"{API}/mbox/devices", headers=admin, timeout=T)
    assert r.status_code == 200
    devs = r.json()["devices"]
    test1 = next(d for d in devs if d.get("serial_number") == "MBOX-TEST-1")
    other = next((d for d in devs if d["id"] != test1["id"]), None)
    return {"test1": test1["id"], "other": other["id"] if other else None}


def sync(did, key, playing=None):
    return requests.post(f"{API}/mbox/pi/{did}/sync", json={
        "api_key": key, "version": "1.0.0", "gps": {"lat": 50.43, "lon": 7.47, "fix": True, "mode": 3, "sats": 8},
        "playing": playing, "files": [], "volume": 80, "hostname": "pi-qa"}, timeout=T)


# ---------- Pi-Setup ----------
class TestPiSetup:
    def test_setup_ma1_forbidden(self, ma1, ids):
        r = requests.post(f"{API}/mbox/{ids['test1']}/pi-setup", json={"audio_device": "", "volume": 80}, headers=ma1, timeout=T)
        assert r.status_code == 403

    def test_setup_admin_and_download(self, admin, ids):
        r = requests.post(f"{API}/mbox/{ids['test1']}/pi-setup", json={"audio_device": "", "volume": 80}, headers=admin, timeout=T)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["download_token"] and "/api/mbox/pi-setup-download/" in d["download_url"]
        s = requests.get(d["download_url"], timeout=T)
        assert s.status_code == 200
        assert "text/plain" in s.headers.get("content-type", "")
        txt = s.text
        for needle in ("device_key = ", "/etc/mbox_pi.conf", "mbox_pi.service", "mpg123", "gpsd"):
            assert needle in txt, needle
        m = re.search(r"^device_key = ([0-9a-f]+)$", txt, re.M)
        assert m
        STATE["key"] = m.group(1)
        assert f"device_id = {ids['test1']}" in txt

    def test_download_invalid_token(self):
        r = requests.get(f"{API}/mbox/pi-setup-download/invalidtoken", timeout=T)
        assert r.status_code == 410


# ---------- Pi-Sync ----------
class TestPiSync:
    def test_sync_ok(self, ids):
        r = sync(ids["test1"], STATE["key"])
        assert r.status_code == 200, r.text
        d = r.json()
        # Hinweis: alte, offline eingereihte Befehle (z.B. stop) werden hier noch ausgeliefert
        assert isinstance(d["pending_commands"], list)
        names = [m["name"] for m in d["audio_manifest"]]
        assert "testansage.mp3" in names
        m = next(m for m in d["audio_manifest"] if m["name"] == "testansage.mp3")
        assert len(m["sha256"]) == 64 and m["size"] > 1_000_000
        assert d["server_time"]

    def test_sync_wrong_key(self, ids):
        assert sync(ids["test1"], "deadbeef").status_code == 401

    def test_status_after_sync(self, admin, ids):
        r = requests.get(f"{API}/mbox/{ids['test1']}/status", headers=admin, timeout=T)
        assert r.status_code == 200
        dev = r.json()["device"]
        assert dev["pi"]["online"] is True
        assert dev["pi"]["gps"]["lat"] == 50.43
        assert list(dev["position"]) == [50.43, 7.47]
        assert dev["latitude"] == 50.43 and dev["longitude"] == 7.47
        assert "mbox_pi_key_hash" not in dev
        assert "mbox_password" not in dev


# ---------- Audio ----------
class TestAudio:
    def test_audio_status(self, admin, ids):
        r = requests.get(f"{API}/mbox/{ids['test1']}/audio", headers=admin, timeout=T)
        assert r.status_code == 200
        d = r.json()
        assert d["pi"]["configured"] is True
        assert any(f["name"] == "testansage.mp3" for f in d["files"])
        assert isinstance(d["commands"], list)

    def test_play_flow(self, admin, ids):
        did = ids["test1"]
        sync(did, STATE["key"])
        r = requests.post(f"{API}/mbox/{did}/audio/play", json={"file": "testansage.mp3"}, headers=admin, timeout=T)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True and d["command_id"] and d["pi_online"] is True
        cid = d["command_id"]
        s = sync(did, STATE["key"]).json()
        cmd = next(c for c in s["pending_commands"] if c["id"] == cid)
        assert cmd["command"] == "play" and cmd["params"] == {"file": "testansage.mp3", "loop": False}
        # second sync must not resend
        s2 = sync(did, STATE["key"]).json()
        assert all(c["id"] != cid for c in s2["pending_commands"])
        cr = requests.post(f"{API}/mbox/pi/{did}/command-result", json={
            "api_key": STATE["key"], "command_id": cid, "success": True, "message": "gestartet"}, timeout=T)
        assert cr.status_code == 200 and cr.json() == {"ok": True}
        a = requests.get(f"{API}/mbox/{did}/audio", headers=admin, timeout=T).json()
        assert a["commands"][0]["id"] == cid and a["commands"][0]["status"] == "done"
        sync(did, STATE["key"], playing={"file": "testansage.mp3", "since": 1})
        a = requests.get(f"{API}/mbox/{did}/audio", headers=admin, timeout=T).json()
        assert a["pi"]["playing"]["file"] == "testansage.mp3"

    def test_command_result_wrong_key(self, ids):
        r = requests.post(f"{API}/mbox/pi/{ids['test1']}/command-result", json={"api_key": "x", "command_id": "y", "success": True}, timeout=T)
        assert r.status_code == 401

    def test_play_unknown_file(self, admin, ids):
        r = requests.post(f"{API}/mbox/{ids['test1']}/audio/play", json={"file": "gibtsnicht.mp3"}, headers=admin, timeout=T)
        assert r.status_code == 404

    def test_play_path_traversal(self, admin, ids):
        r = requests.post(f"{API}/mbox/{ids['test1']}/audio/play", json={"file": "../../server.py"}, headers=admin, timeout=T)
        assert r.status_code == 404

    def test_stop_and_volume(self, admin, ids):
        r = requests.post(f"{API}/mbox/{ids['test1']}/audio/stop", headers=admin, timeout=T)
        assert r.status_code == 200 and r.json()["ok"] is True
        r = requests.post(f"{API}/mbox/{ids['test1']}/audio/volume", json={"volume": 50}, headers=admin, timeout=T)
        assert r.status_code == 200 and r.json()["ok"] is True
        a = requests.get(f"{API}/mbox/{ids['test1']}/audio", headers=admin, timeout=T).json()
        assert a["pi"]["volume"] == 50
        assert a["commands"][0]["command"] == "volume" and a["commands"][0]["params"] == {"volume": 50}

    def test_ma1_play_forbidden(self, ma1, ids):
        r = requests.post(f"{API}/mbox/{ids['test1']}/audio/play", json={"file": "testansage.mp3"}, headers=ma1, timeout=T)
        assert r.status_code == 403

    def test_audio_download(self, ids):
        did = ids["test1"]
        r = requests.get(f"{API}/mbox/pi/{did}/audio/testansage.mp3", params={"api_key": STATE["key"]}, timeout=60)
        assert r.status_code == 200
        assert 2_000_000 < len(r.content) < 2_700_000
        assert requests.get(f"{API}/mbox/pi/{did}/audio/testansage.mp3", timeout=T).status_code == 401
        assert requests.get(f"{API}/mbox/pi/{did}/audio/testansage.mp3", params={"api_key": "bad"}, timeout=T).status_code == 401


# ---------- Auftrags-Zuweisung ----------
class TestOrderAssignment:
    def test_get_order(self, admin, ids):
        sync(ids["test1"], STATE["key"])
        r = requests.get(f"{API}/mbox/orders/{ORDER}", headers=admin, timeout=T)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["center"]["lat"] and d["center"]["lng"]
        assert d["radius_km"] == 1.0
        dev = next(x for x in d["devices"] if x["id"] == ids["test1"])
        assert dev["serial_number"] == "MBOX-TEST-1" and dev["mode"] == "auto"
        assert 0.3 < dev["distance_km"] < 0.5
        assert d["blocked_ids"] == []
        assert len(d["candidates"]) >= 1

    def test_ma1_get_order(self, ma1):
        assert requests.get(f"{API}/mbox/orders/{ORDER}", headers=ma1, timeout=T).status_code == 200

    def test_kunde_forbidden(self, kunde):
        assert requests.get(f"{API}/mbox/orders/{ORDER}", headers=kunde, timeout=T).status_code == 403
        assert requests.put(f"{API}/mbox/orders/{ORDER}/config", json={"expected_count": 3}, headers=kunde, timeout=T).status_code == 403

    def test_expected_count_growth(self, admin):
        r = requests.put(f"{API}/mbox/orders/{ORDER}/config", json={"expected_count": 3}, headers=admin, timeout=T)
        assert r.status_code == 200
        assert r.json()["radius_used_km"] == 10.0 and r.json()["expected_count"] == 3
        r = requests.put(f"{API}/mbox/orders/{ORDER}/config", json={"expected_count": 1}, headers=admin, timeout=T)
        assert r.status_code == 200 and r.json()["radius_used_km"] == 1.0

    def test_overrides(self, admin, ids):
        u = f"{API}/mbox/orders/{ORDER}/override"
        r = requests.post(u, json={"device_id": ids["test1"], "action": "remove"}, headers=admin, timeout=T).json()
        assert all(x["id"] != ids["test1"] for x in r["devices"]) and ids["test1"] in r["blocked_ids"]
        r = requests.post(u, json={"device_id": ids["test1"], "action": "reset"}, headers=admin, timeout=T).json()
        assert any(x["id"] == ids["test1"] and x["mode"] == "auto" for x in r["devices"])
        if ids["other"]:
            r = requests.post(u, json={"device_id": ids["other"], "action": "add"}, headers=admin, timeout=T).json()
            o = next(x for x in r["devices"] if x["id"] == ids["other"])
            assert o["mode"] == "manuell"
            STATE["other_dist"] = o["distance_km"]
            r = requests.post(u, json={"device_id": ids["other"], "action": "reset"}, headers=admin, timeout=T).json()
            assert all(x["id"] != ids["other"] for x in r["devices"])
        r = requests.post(u, json={"device_id": ids["test1"], "action": "quatsch"}, headers=admin, timeout=T)
        assert r.status_code == 400


# ---------- Kunde ----------
class TestKunde:
    def test_login_and_me_customer_no(self, kunde_login, kunde):
        d = kunde_login[0]
        assert (d.get("user") or d).get("customer_no") == "TM-4711"
        me = requests.get(f"{API}/auth/me", headers=kunde, timeout=T).json()
        assert me.get("customer_no") == "TM-4711"

    def test_devices(self, kunde, ids):
        r = requests.get(f"{API}/mbox/devices", headers=kunde, timeout=T)
        assert r.status_code == 200
        d = r.json()
        assert d["level"] == "kunde"
        assert [x["id"] for x in d["devices"]] == [ids["test1"]]

    def test_status(self, kunde, ids):
        r = requests.get(f"{API}/mbox/{ids['test1']}/status", headers=kunde, timeout=T)
        assert r.status_code == 200 and r.json()["level"] == "kunde"

    def test_other_device_forbidden(self, kunde, ids):
        if ids["other"]:
            assert requests.get(f"{API}/mbox/{ids['other']}/status", headers=kunde, timeout=T).status_code == 403

    @pytest.mark.parametrize("cmd", ["Lampen_Ein", "Schnellstart"])
    def test_allowed_befehl(self, kunde, ids, cmd):
        r = requests.post(f"{API}/mbox/{ids['test1']}/befehl/{cmd}", headers=kunde, timeout=60)
        assert r.status_code == 200
        assert "ok" in r.json()

    @pytest.mark.parametrize("method,path,body", [
        ("post", "befehl/Gen_Start", None), ("post", "befehl/Netzbetrieb", None), ("post", "befehl/Kundenzaehler_Reset", None),
        ("post", "einstellung", {}), ("post", "uhr/woche", {}), ("get", "knoten", None),
        ("post", "audio/volume", {"volume": 10}), ("get", "audit", None), ("post", "restart", None), ("get", "log", None),
    ])
    def test_forbidden(self, kunde, ids, method, path, body):
        r = getattr(requests, method)(f"{API}/mbox/{ids['test1']}/{path}", json=body, headers=kunde, timeout=T)
        assert r.status_code == 403, f"{path}: {r.status_code}"

    def test_audio_play_stop(self, kunde, ids):
        r = requests.post(f"{API}/mbox/{ids['test1']}/audio/play", json={"file": "testansage.mp3"}, headers=kunde, timeout=T)
        assert r.status_code == 200 and r.json()["ok"] is True
        r = requests.post(f"{API}/mbox/{ids['test1']}/audio/stop", headers=kunde, timeout=T)
        assert r.status_code == 200
        assert requests.get(f"{API}/mbox/{ids['test1']}/audio", headers=kunde, timeout=T).status_code == 200

    def test_remove_override_revokes(self, admin, kunde, ids):
        u = f"{API}/mbox/orders/{ORDER}/override"
        requests.post(u, json={"device_id": ids["test1"], "action": "remove"}, headers=admin, timeout=T)
        try:
            assert requests.get(f"{API}/mbox/{ids['test1']}/status", headers=kunde, timeout=T).status_code == 403
            # weitere Masten (z.B. echter Pi im Preview) koennen per Radius-Wachstum nachruecken -> nur test1 darf fehlen
            assert all(d["id"] != ids["test1"] for d in requests.get(f"{API}/mbox/devices", headers=kunde, timeout=T).json()["devices"])
        finally:
            requests.post(u, json={"device_id": ids["test1"], "action": "reset"}, headers=admin, timeout=T)
        assert requests.get(f"{API}/mbox/{ids['test1']}/status", headers=kunde, timeout=T).status_code == 200

    def test_generators_leak_fix(self, kunde):
        r = requests.get(f"{API}/generators", headers=kunde, timeout=T)
        assert r.status_code == 200 and r.json() == [], r.text[:300]
        r = requests.get(f"{API}/generators/stats/overview", headers=kunde, timeout=T)
        assert r.status_code == 200 and r.json().get("total") == 0, r.text[:300]


# ---------- Kundennummer ----------
class TestCustomerNo:
    def test_customer_no_update(self, admin, kunde_login, kunde):
        uid = (kunde_login[0].get("user") or kunde_login[0])["id"]
        try:
            r = requests.put(f"{API}/users/{uid}", json={"customer_no": "TM-4711"}, headers=admin, timeout=T)
            assert r.status_code == 200 and r.json()["customer_no"] == "TM-4711"
            r = requests.put(f"{API}/users/{uid}", json={"customer_no": ""}, headers=admin, timeout=T)
            assert r.status_code == 200
            # Kunde ohne Kundennr. und ohne Freigabe: 200 mit leerer Liste (kein 403, damit Freigabe-Kunden ohne Kundennr. funktionieren)
            r = requests.get(f"{API}/mbox/devices", headers=kunde, timeout=T)
            assert r.status_code == 200 and r.json()["devices"] == [], r.text[:200]
        finally:
            r = requests.put(f"{API}/users/{uid}", json={"customer_no": "TM-4711"}, headers=admin, timeout=T)
            assert r.json()["customer_no"] == "TM-4711"
        assert requests.get(f"{API}/mbox/devices", headers=kunde, timeout=T).status_code == 200


# ---------- Offline nach 20 s ----------
class TestOffline:
    def test_offline_after_20s(self, admin, ids):
        time.sleep(22)
        a = requests.get(f"{API}/mbox/{ids['test1']}/audio", headers=admin, timeout=T).json()
        assert a["pi"]["online"] is False and a["pi"]["playing"] is None
        r = requests.post(f"{API}/mbox/{ids['test1']}/audio/stop", headers=admin, timeout=T).json()
        assert r["pi_online"] is False and r["hinweis"]
        # Key fuer weitere Tests sichern
        with open("/tmp/mbox_pi_key.txt", "w") as f:
            f.write(STATE["key"])
