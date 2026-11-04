# Messe-Modul: Admin CRUD, Audio, oeffentliche QR-Endpunkte, Berechtigungen, Regression
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"
MBOX1 = "bcd7198b-d414-4be0-836f-a725aaf8bb24"
MBOX_TEST = "ee277308-711d-48c2-acfd-3ac9d20ff8be"
AUDIO = "/app/backend/mbox_service/audio/testansage.mp3"
EXIST_ID = "6d5d1ee0-59fd-4ed7-8096-ee09a526783a"
EXIST_TOKEN = "OzHkUWvd8vqy70_eugKCYplX"
EXIST_FID = "be40347a-9dd0-4d32-a96a-e4a0c581109b"


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_login('admin@test.com', 'password')}"})
    s.token = s.headers["Authorization"].split(" ")[1]
    return s


@pytest.fixture(scope="module")
def messe(admin):
    r = admin.post(f"{API}/messe", json={"name": "TEST_Messe Pytest", "location": "Halle 3",
                                         "start_date": "2026-03-01", "end_date": "2026-03-05", "note": "TEST"})
    assert r.status_code == 200, r.text
    m = r.json()
    yield m
    admin.delete(f"{API}/messe/{m['id']}")


# --- Verwaltung CRUD ---
class TestMesseAdmin:
    def test_create_and_get(self, admin, messe):
        assert messe["name"] == "TEST_Messe Pytest" and messe["active"] is True
        assert isinstance(messe["public_token"], str) and len(messe["public_token"]) > 10
        g = admin.get(f"{API}/messe/{messe['id']}")
        assert g.status_code == 200
        d = g.json()
        assert d["location"] == "Halle 3" and d["start_date"] == "2026-03-01" and d["audio"] == []
        assert "_id" not in d

    def test_list_contains(self, admin, messe):
        r = admin.get(f"{API}/messe")
        assert r.status_code == 200
        assert any(x["id"] == messe["id"] for x in r.json())

    def test_create_without_name_400(self, admin):
        assert admin.post(f"{API}/messe", json={"name": "  "}).status_code == 400

    def test_patch_fields_and_device_filter(self, admin, messe):
        r = admin.patch(f"{API}/messe/{messe['id']}", json={
            "name": "TEST_Messe Pytest2", "location": "Halle 4", "note": "n2", "end_date": "2026-03-06",
            "device_ids": [MBOX_TEST, "fremd-id-123", MBOX1]})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == "TEST_Messe Pytest2" and d["location"] == "Halle 4"
        assert d["device_ids"] == [MBOX_TEST, MBOX1]
        assert [x["id"] for x in d["devices"]] == [MBOX_TEST, MBOX1]
        g = admin.get(f"{API}/messe/{messe['id']}").json()
        assert g["device_ids"] == [MBOX_TEST, MBOX1] and g["end_date"] == "2026-03-06"

    def test_patch_empty_name_400(self, admin, messe):
        assert admin.patch(f"{API}/messe/{messe['id']}", json={"name": ""}).status_code == 400

    def test_get_unknown_404(self, admin):
        assert admin.get(f"{API}/messe/does-not-exist").status_code == 404


# --- Audio ---
class TestMesseAudio:
    def test_wrong_type_400(self, admin, messe):
        r = admin.post(f"{API}/messe/{messe['id']}/audio", files={"file": ("x.txt", b"hello", "text/plain")}, data={"name": "x"})
        assert r.status_code == 400

    def test_upload_process_rename_stream_delete(self, admin, messe):
        with open(AUDIO, "rb") as fh:
            r = admin.post(f"{API}/messe/{messe['id']}/audio", files={"file": ("testansage.mp3", fh, "audio/mpeg")},
                           data={"name": "TEST_Ansage"})
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["status"] == "processing" and doc["name"] == "TEST_Ansage"
        fid = doc["id"]
        f = None
        for _ in range(40):
            time.sleep(1.5)
            f = next(x for x in admin.get(f"{API}/messe/{messe['id']}").json()["audio"] if x["id"] == fid)
            if f["status"] != "processing":
                break
        assert f["status"] in ("ready", "ready_unprocessed"), f
        assert f["sha256"] and len(f["sha256"]) == 64
        if f["status"] == "ready":
            assert f.get("duration_sec") and f["duration_sec"] > 0
        assert admin.patch(f"{API}/messe/{messe['id']}/audio/{fid}", json={"name": "TEST_Renamed"}).status_code == 200
        assert next(x for x in admin.get(f"{API}/messe/{messe['id']}").json()["audio"] if x["id"] == fid)["name"] == "TEST_Renamed"
        s = requests.get(f"{API}/messe/{messe['id']}/audio/{fid}/stream", params={"token": admin.token})
        assert s.status_code == 200 and s.headers["content-type"].startswith("audio/mpeg") and len(s.content) > 1000
        # public listing contains ready file
        pub = requests.get(f"{API}/messe/public/{messe['public_token']}").json()
        assert any(a["id"] == fid for a in pub["audio"])
        # public play
        p = requests.post(f"{API}/messe/public/{messe['public_token']}/{MBOX1}/play", json={"fid": fid})
        assert p.status_code == 200 and p.json()["ok"] is True, p.text
        d = admin.delete(f"{API}/messe/{messe['id']}/audio/{fid}")
        assert d.status_code == 200
        assert all(x["id"] != fid for x in admin.get(f"{API}/messe/{messe['id']}").json()["audio"])
        assert admin.delete(f"{API}/messe/{messe['id']}/audio/{fid}").status_code == 404


# --- Oeffentlich (ohne Auth) auf vorhandener Messe ---
class TestMessePublic:
    def test_public_overview(self):
        r = requests.get(f"{API}/messe/public/{EXIST_TOKEN}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] and any(x["id"] == MBOX1 for x in d["devices"])
        assert any(a["id"] == EXIST_FID for a in d["audio"])
        assert "public_token" not in d and "device_ids" not in d

    def test_invalid_token_404(self):
        assert requests.get(f"{API}/messe/public/invalid_token_xyz").status_code == 404

    def test_status(self):
        r = requests.get(f"{API}/messe/public/{EXIST_TOKEN}/{MBOX1}/status", timeout=40)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["sps_ok"] is False and d["sps_fehler"] and d["lampen"] == []
        assert "pi_online" in d

    def test_foreign_device_404(self):
        assert requests.get(f"{API}/messe/public/{EXIST_TOKEN}/{MBOX_TEST}/status").status_code == 404

    def test_lampe_index_and_actions(self):
        for body in ({"index": 1}, {"action": "ein"}, {"action": "aus"}):
            r = requests.post(f"{API}/messe/public/{EXIST_TOKEN}/{MBOX1}/lampe", json=body, timeout=40)
            assert r.status_code == 200, r.text
            assert r.json()["ok"] is False and r.json().get("fehler")

    def test_lampe_invalid_400(self):
        for body in ({"index": 9}, {}, {"index": "1"}):
            assert requests.post(f"{API}/messe/public/{EXIST_TOKEN}/{MBOX1}/lampe", json=body).status_code == 400

    def test_play_stop(self):
        r = requests.post(f"{API}/messe/public/{EXIST_TOKEN}/{MBOX1}/play", json={"fid": EXIST_FID})
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True and "pi_online" in r.json()
        assert requests.post(f"{API}/messe/public/{EXIST_TOKEN}/{MBOX1}/play", json={"fid": "nope"}).status_code == 404
        s = requests.post(f"{API}/messe/public/{EXIST_TOKEN}/{MBOX1}/stop")
        assert s.status_code == 200 and s.json()["ok"] is True


# --- Berechtigungen ---
class TestMessePerms:
    def test_kunde_403(self):
        t = _login("kunde.meier@test.com", "Meier2026!")
        assert requests.get(f"{API}/messe", headers={"Authorization": f"Bearer {t}"}).status_code == 403

    def test_no_token(self):
        assert requests.get(f"{API}/messe").status_code in (401, 403)
        assert requests.post(f"{API}/messe", json={"name": "x"}).status_code in (401, 403)


# --- Geraete-Monitor + Regression ---
class TestMesseRegression:
    def test_device_audio_excludes_messe(self, admin):
        r = admin.get(f"{API}/mbox/{MBOX1}/audio")
        assert r.status_code == 200
        assert all(not f.get("messe_id") for f in r.json()["files"])
        assert all(not f["name"].startswith("messe") for f in r.json()["files"])

    def test_mbox_devices(self, admin):
        r = admin.get(f"{API}/mbox/devices")
        assert r.status_code == 200


# --- Destruktiv: Active/New-Link/Archiv auf eigener Messe ---
class TestMesseLifecycle:
    def test_lifecycle(self, admin):
        m = admin.post(f"{API}/messe", json={"name": "TEST_Messe Lifecycle"}).json()
        mid, tok = m["id"], m["public_token"]
        try:
            assert requests.get(f"{API}/messe/public/{tok}").status_code == 200
            assert admin.patch(f"{API}/messe/{mid}", json={"active": False}).json()["active"] is False
            assert requests.get(f"{API}/messe/public/{tok}").status_code == 410
            admin.patch(f"{API}/messe/{mid}", json={"active": True})
            n = admin.post(f"{API}/messe/{mid}/new-link")
            assert n.status_code == 200
            tok2 = n.json()["public_token"]
            assert tok2 != tok
            assert requests.get(f"{API}/messe/public/{tok}").status_code == 404
            assert requests.get(f"{API}/messe/public/{tok2}").status_code == 200
        finally:
            assert admin.delete(f"{API}/messe/{mid}").status_code == 200
        assert admin.get(f"{API}/messe/{mid}").status_code == 404
        assert requests.get(f"{API}/messe/public/{tok2}").status_code == 404
        assert all(x["id"] != mid for x in admin.get(f"{API}/messe").json())
