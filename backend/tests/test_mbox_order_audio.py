# M-Box Auftrags-Durchsagen: Upload/ffmpeg-Verarbeitung, Rauschen, Rename/Stream/Delete, Manifest+Pi, Gruppenstart, Kundenzugang
import os
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
T = 60
ORDER = 999901
TESTMP3 = "/app/backend/mbox_service/audio/testansage.mp3"
# Dateien liegen in MongoDB GridFS (Bucket mbox_audio), nicht auf der Platte
S = {}


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=T)
    assert r.status_code == 200, r.text
    d = r.json()
    tok = d.get("token") or d.get("access_token")
    return d, tok, {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin():
    return login("admin@test.com", "password")[2]


@pytest.fixture(scope="module")
def ma1():
    return login("ma1@test.com", "Anna2026!")[2]


@pytest.fixture(scope="module")
def kunde_all():
    return login("kunde.meier@test.com", "Meier2026!")


@pytest.fixture(scope="module")
def kunde(kunde_all):
    return kunde_all[2]


@pytest.fixture(scope="module")
def dev_id(admin):
    r = requests.get(f"{API}/mbox/devices", headers=admin, timeout=T)
    return next(d for d in r.json()["devices"] if d.get("serial_number") == "MBOX-TEST-1")["id"]


def upload(h, path, name, fname=None):
    with open(path, "rb") as f:
        return requests.post(f"{API}/mbox/orders/{ORDER}/audio", headers=h,
                             files={"file": (fname or os.path.basename(path), f, "audio/mpeg")}, data={"name": name}, timeout=T)


def wait_ready(h, fid, timeout=25):
    end = time.time() + timeout
    while time.time() < end:
        r = requests.get(f"{API}/mbox/orders/{ORDER}/audio", headers=h, timeout=T)
        f = next((x for x in r.json()["files"] if x["id"] == fid), None)
        if f and f["status"] != "processing":
            return f, r.json()
        time.sleep(1.5)
    return f, r.json()


def sync(did, key):
    return requests.post(f"{API}/mbox/pi/{did}/sync", json={"api_key": key, "version": "1.3.0", "files": ["testansage.mp3"],
                                                            "gps": {"fix": False}, "hostname": "pi-qa"}, timeout=T)


class TestUpload:
    def test_kunde_upload_and_process(self, kunde):
        r = upload(kunde, TESTMP3, "QA Durchsage")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "processing" and d["name"] == "QA Durchsage"
        assert re.fullmatch(rf"order{ORDER}_[0-9a-f]{{8}}\.mp3", d["stored"])
        S["kfile"] = d
        f, full = wait_ready(kunde, d["id"])
        assert f["status"] == "ready", f
        assert 144 < f["duration_sec"] < 147
        assert -1 <= f["analysis"]["after"]["max_volume_db"] <= 0
        assert f["analysis"]["noise_reduction"] is False
        assert any(x.get("serial_number") == "MBOX-TEST-1" or x.get("name") == "Lichtmast Test 1" for x in full["devices"]), full["devices"]
        assert full["ffmpeg"] is True and full["kunde"] is True

    def test_upload_txt_400(self, kunde):
        r = requests.post(f"{API}/mbox/orders/{ORDER}/audio", headers=kunde, files={"file": ("x.txt", b"hello", "text/plain")}, data={"name": "x"}, timeout=T)
        assert r.status_code == 400

    def test_ma1_upload_allowed(self, ma1):
        r = upload(ma1, TESTMP3, "QA MA1")
        assert r.status_code == 200, r.text
        S["mafile"] = r.json()

    def test_kunde_foreign_order_403(self, kunde):
        with open(TESTMP3, "rb") as f:
            r = requests.post(f"{API}/mbox/orders/3/audio", headers=kunde, files={"file": ("a.mp3", f, "audio/mpeg")}, data={"name": "x"}, timeout=T)
        assert r.status_code == 403
        assert requests.get(f"{API}/mbox/orders/3/audio", headers=kunde, timeout=T).status_code == 403


class TestNoise:
    def test_noisy_upload_admin(self, admin):
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-f", "lavfi", "-i",
                        "anoisesrc=color=white:amplitude=0.02:duration=4", "-filter_complex",
                        "[0]volume=-20dB[a];[a][1]amix=inputs=2:normalize=0", "-codec:a", "libmp3lame", "/tmp/noisy.mp3"],
                       capture_output=True, check=True)
        r = upload(admin, "/tmp/noisy.mp3", "QA Noisy")
        assert r.status_code == 200, r.text
        d = r.json()
        f, _ = wait_ready(admin, d["id"])
        assert f["status"] == "ready", f
        a = f["analysis"]
        print("noise analysis", a)
        assert a["noise_reduction"] is True
        assert -1 <= a["after"]["max_volume_db"] <= 0
        assert a["gain_db"] > 20
        # Datei liegt in GridFS -> ueber den Stream-Endpoint abrufbar
        tok = admin["Authorization"].split(" ", 1)[1]
        s = requests.get(f"{API}/mbox/orders/{ORDER}/audio/{d['id']}/stream", params={"token": tok}, timeout=T)
        assert s.status_code == 200 and s.headers.get("content-type", "").startswith("audio/")
        S["noisy"] = d

    def test_noisy_delete(self, admin):
        d = S["noisy"]
        r = requests.delete(f"{API}/mbox/orders/{ORDER}/audio/{d['id']}", headers=admin, timeout=T)
        assert r.status_code == 200
        lst = requests.get(f"{API}/mbox/orders/{ORDER}/audio", headers=admin, timeout=T).json()["files"]
        assert not any(x["id"] == d["id"] for x in lst)
        tok = admin["Authorization"].split(" ", 1)[1]
        s = requests.get(f"{API}/mbox/orders/{ORDER}/audio/{d['id']}/stream", params={"token": tok}, timeout=T)
        assert s.status_code == 404


class TestRenameStreamDelete:
    def test_rename(self, kunde):
        fid = S["kfile"]["id"]
        r = requests.patch(f"{API}/mbox/orders/{ORDER}/audio/{fid}", headers=kunde, json={"name": "Evakuierung QA"}, timeout=T)
        assert r.status_code == 200 and r.json()["name"] == "Evakuierung QA"
        lst = requests.get(f"{API}/mbox/orders/{ORDER}/audio", headers=kunde, timeout=T).json()["files"]
        assert next(x for x in lst if x["id"] == fid)["name"] == "Evakuierung QA"
        assert requests.patch(f"{API}/mbox/orders/{ORDER}/audio/{fid}", headers=kunde, json={"name": " "}, timeout=T).status_code == 400

    def test_stream(self, kunde_all):
        fid = S["kfile"]["id"]
        r = requests.get(f"{API}/mbox/orders/{ORDER}/audio/{fid}/stream", params={"token": kunde_all[1]}, timeout=T)
        assert r.status_code == 200 and "audio/mpeg" in r.headers["content-type"] and len(r.content) > 10000
        r2 = requests.get(f"{API}/mbox/orders/{ORDER}/audio/{fid}/stream", timeout=T)
        assert r2.status_code in (401, 422)
        r3 = requests.get(f"{API}/mbox/orders/{ORDER}/audio/{fid}/stream", params={"token": "garbage"}, timeout=T)
        print("garbage token status", r3.status_code)
        assert r3.status_code in (401, 403)

    def test_kunde_cannot_delete_foreign(self, kunde, ma1):
        f, _ = wait_ready(ma1, S["mafile"]["id"])
        r = requests.delete(f"{API}/mbox/orders/{ORDER}/audio/{S['mafile']['id']}", headers=kunde, timeout=T)
        assert r.status_code == 403


class TestManifestPlay:
    def test_pi_setup(self, admin, dev_id):
        r = requests.post(f"{API}/mbox/{dev_id}/pi-setup", json={"audio_device": "", "volume": 80}, headers=admin, timeout=T)
        assert r.status_code == 200, r.text
        txt = requests.get(r.json()["download_url"], timeout=T).text
        S["key"] = re.search(r"^device_key = ([0-9a-f]+)$", txt, re.M).group(1)

    def test_manifest(self, dev_id):
        r = sync(dev_id, S["key"])
        assert r.status_code == 200, r.text
        man = r.json()["audio_manifest"]
        names = {m["name"]: m for m in man}
        assert "testansage.mp3" in names
        k = names.get(S["kfile"]["stored"])
        assert k and k["label"] == "Evakuierung QA" and k["order_pk"] == str(ORDER), man
        dl = requests.get(f"{API}/mbox/pi/{dev_id}/audio/{S['kfile']['stored']}", params={"api_key": S["key"]}, timeout=T)
        assert dl.status_code == 200 and len(dl.content) > 10000
        bad = requests.get(f"{API}/mbox/pi/{dev_id}/audio/{S['kfile']['stored']}", params={"api_key": "wrong"}, timeout=T)
        assert bad.status_code in (401, 403)

    def test_group_play(self, kunde, dev_id):
        sync(dev_id, S["key"])  # Queue leeren
        r = requests.post(f"{API}/mbox/orders/{ORDER}/audio/{S['kfile']['id']}/play", headers=kunde, timeout=T)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] and d["lead_sec"] == 6 and d["devices"] >= 1 and isinstance(d["offline"], list)
        delta = (datetime.fromisoformat(d["start_at"]) - datetime.now(timezone.utc)).total_seconds()
        assert 2 < delta <= 7, delta
        cmds = sync(dev_id, S["key"]).json()["pending_commands"]
        play = [c for c in cmds if c["command"] == "play"]
        assert play, cmds
        p = play[-1]
        assert p["params"]["file"] == S["kfile"]["stored"] and p["params"]["start_at"] == d["start_at"]
        assert p["params"]["label"] == "Evakuierung QA" and p["order_pk"] == str(ORDER)

    def test_group_stop(self, kunde, dev_id):
        r = requests.post(f"{API}/mbox/orders/{ORDER}/audio/stop", headers=kunde, timeout=T)
        assert r.status_code == 200 and r.json()["ok"] and r.json()["devices"] >= 1
        cmds = sync(dev_id, S["key"]).json()["pending_commands"]
        assert any(c["command"] == "stop" for c in cmds), cmds

    def test_play_processing_409(self, kunde):
        r = upload(kunde, TESTMP3, "QA Processing")
        fid = r.json()["id"]
        S["proc"] = r.json()
        p = requests.post(f"{API}/mbox/orders/{ORDER}/audio/{fid}/play", headers=kunde, timeout=T)
        assert p.status_code == 409, p.text


class TestLoopSelectTimers:
    """Einmal/Schleife, Masten-Auswahl, Stopp einzeln, Timer-CRUD + Sofortstart, Minuten-Logik."""

    def test_loop_on_selected_mast(self, kunde, dev_id):
        sync(dev_id, S["key"])
        r = requests.post(f"{API}/mbox/orders/{ORDER}/audio/{S['kfile']['id']}/play", headers=kunde,
                          json={"loop": True, "device_ids": [dev_id]}, timeout=T)
        assert r.status_code == 200, r.text
        assert r.json()["loop"] is True and r.json()["devices"] == 1
        p = [c for c in sync(dev_id, S["key"]).json()["pending_commands"] if c["command"] == "play"][-1]
        assert p["params"]["loop"] is True and p["params"]["file"] == S["kfile"]["stored"]

    def test_foreign_device_ids_ignored(self, kunde, dev_id):
        r = requests.post(f"{API}/mbox/orders/{ORDER}/audio/{S['kfile']['id']}/play", headers=kunde,
                          json={"loop": False, "device_ids": ["gibt-es-nicht"]}, timeout=T)
        assert r.status_code == 409, r.text
        sync(dev_id, S["key"])

    def test_stop_selected(self, kunde, dev_id):
        r = requests.post(f"{API}/mbox/orders/{ORDER}/audio/stop", headers=kunde, json={"device_ids": [dev_id]}, timeout=T)
        assert r.status_code == 200 and r.json()["devices"] == 1
        assert any(c["command"] == "stop" for c in sync(dev_id, S["key"]).json()["pending_commands"])

    def test_timer_crud(self, kunde, admin, dev_id):
        fid = S["kfile"]["id"]
        bad = requests.post(f"{API}/mbox/orders/{ORDER}/audio/{fid}/timers", headers=kunde, json={"time": "25:99"}, timeout=T)
        assert bad.status_code == 400
        r = requests.post(f"{API}/mbox/orders/{ORDER}/audio/{fid}/timers", headers=kunde,
                          json={"time": "18:30", "days": [4, 5, 6], "loop": True, "device_ids": [dev_id]}, timeout=T)
        assert r.status_code == 200, r.text
        t = r.json()
        S["timer"] = t
        assert t["time"] == "18:30" and t["days"] == [4, 5, 6] and t["loop"] is True and t["enabled"] is True and t["file_name"]
        r2 = requests.post(f"{API}/mbox/orders/{ORDER}/audio/{fid}/timers", headers=admin, json={"time": "09:00", "date": "2027-06-01"}, timeout=T)
        assert r2.status_code == 200 and r2.json()["date"] == "2027-06-01" and r2.json()["days"] == []
        S["timer2"] = r2.json()
        lst = requests.get(f"{API}/mbox/orders/{ORDER}/audio", headers=kunde, timeout=T).json()
        ids = {x["id"] for x in lst["timers"]}
        assert t["id"] in ids and S["timer2"]["id"] in ids and lst["active"] is True
        u = requests.patch(f"{API}/mbox/orders/{ORDER}/timers/{t['id']}", headers=kunde, json={"enabled": False, "time": "19:00"}, timeout=T)
        assert u.status_code == 200 and u.json()["enabled"] is False and u.json()["time"] == "19:00"

    def test_timer_run_now(self, kunde, dev_id):
        sync(dev_id, S["key"])
        r = requests.post(f"{API}/mbox/orders/{ORDER}/timers/{S['timer']['id']}/run-now", headers=kunde, timeout=T)
        assert r.status_code == 200, r.text
        assert r.json()["loop"] is True and r.json()["devices"] == 1
        p = [c for c in sync(dev_id, S["key"]).json()["pending_commands"] if c["command"] == "play"][-1]
        assert p["params"]["loop"] is True and p["user_name"] == "Test Meier"

    def test_timer_due_logic(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from routes.mbox_audio import _timer_due
        from datetime import datetime
        fr = datetime(2026, 6, 19, 18, 30)  # Freitag
        assert _timer_due({"enabled": True, "time": "18:30", "days": [4]}, fr)
        assert _timer_due({"enabled": True, "time": "18:30", "days": []}, fr)
        assert not _timer_due({"enabled": True, "time": "18:30", "days": [0]}, fr)
        assert not _timer_due({"enabled": True, "time": "18:31", "days": []}, fr)
        assert not _timer_due({"enabled": False, "time": "18:30", "days": []}, fr)
        assert _timer_due({"enabled": True, "time": "18:30", "date": "2026-06-19"}, fr)
        assert not _timer_due({"enabled": True, "time": "18:30", "date": "2026-06-20"}, fr)

    def test_timer_delete_with_file(self, kunde, admin):
        d = requests.delete(f"{API}/mbox/orders/{ORDER}/timers/{S['timer2']['id']}", headers=admin, timeout=T)
        assert d.status_code == 200
        assert requests.delete(f"{API}/mbox/orders/{ORDER}/timers/{S['timer2']['id']}", headers=admin, timeout=T).status_code == 404


class TestCustomerAccess:
    def test_list_customers(self, admin, kunde):
        r = requests.get(f"{API}/mbox/customers", headers=admin, timeout=T)
        assert r.status_code == 200
        assert any(c["email"] == "kunde.meier@test.com" for c in r.json())
        assert requests.get(f"{API}/mbox/customers", headers=kunde, timeout=T).status_code == 403

    def test_order_customers(self, admin):
        r = requests.get(f"{API}/mbox/orders/{ORDER}/customers", headers=admin, timeout=T)
        assert r.status_code == 200
        d = r.json()
        S["orig_ids"] = d["user_ids"]
        assert any(a["name"] == "Test Meier" for a in d["auto_by_customer_no"])

    def test_override_flow(self, admin):
        email = f"test_kunde_{uuid.uuid4().hex[:6]}@test.com"
        r = requests.post(f"{API}/users", headers=admin, json={"email": email, "name": "TEST Kunde2", "password": "Test2026!", "role": "kunde"}, timeout=T)
        assert r.status_code == 200, r.text
        S["k2id"] = r.json()["id"]
        h = login(email, "Test2026!")[2]
        assert requests.get(f"{API}/mbox/my/orders", headers=h, timeout=T).json() == []
        assert requests.get(f"{API}/mbox/orders/{ORDER}/audio", headers=h, timeout=T).status_code == 403
        try:
            r = requests.put(f"{API}/mbox/orders/{ORDER}/customers", headers=admin, json={"user_ids": S["orig_ids"] + [S["k2id"]]}, timeout=T)
            assert r.status_code == 200
            mo = requests.get(f"{API}/mbox/my/orders", headers=h, timeout=T).json()
            assert any(str(o["order_pk"]) == str(ORDER) for o in mo), mo
            assert requests.get(f"{API}/mbox/orders/{ORDER}/audio", headers=h, timeout=T).status_code == 200
            dv = requests.get(f"{API}/mbox/devices", headers=h, timeout=T)
            # BUG (iteration 90): mbox_level() gibt 'none' fuer Kunden ohne customer_no -> 403
            assert dv.status_code == 200, dv.text
            assert any(x.get("serial_number") == "MBOX-TEST-1" for x in dv.json()["devices"])
        finally:
            requests.put(f"{API}/mbox/orders/{ORDER}/customers", headers=admin, json={"user_ids": S["orig_ids"]}, timeout=T)
        assert requests.get(f"{API}/mbox/my/orders", headers=h, timeout=T).json() == []
        assert requests.get(f"{API}/mbox/orders/{ORDER}/audio", headers=h, timeout=T).status_code == 403

    def test_staff_order_assignment(self, admin):
        r = requests.get(f"{API}/mbox/orders/{ORDER}", headers=admin, timeout=T)
        assert r.status_code == 200 and any(d.get("name") == "Lichtmast Test 1" for d in r.json()["devices"]), r.json()


class TestCleanup:
    def test_cleanup(self, admin, kunde):
        time.sleep(3)
        for k in ("kfile", "mafile", "proc"):
            if k in S:
                h = kunde if k != "mafile" else admin
                f, _ = wait_ready(admin, S[k]["id"])
                r = requests.delete(f"{API}/mbox/orders/{ORDER}/audio/{S[k]['id']}", headers=h, timeout=T)
                assert r.status_code == 200, (k, r.text)
        if "timer" in S:  # Timer wurden mit der Datei geloescht
            lst = requests.get(f"{API}/mbox/orders/{ORDER}/audio", headers=admin, timeout=T).json()
            assert all(t["id"] != S["timer"]["id"] for t in lst["timers"])
        if "k2id" in S:
            requests.delete(f"{API}/users/{S['k2id']}", headers=admin, timeout=T)
