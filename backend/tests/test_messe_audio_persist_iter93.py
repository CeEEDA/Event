# Messe-Audio: Standard-Upload dauerhaft (temporary=False), nur temporary=1 vergaenglich; oeffentliche Liste; Regression
import os
import time
from datetime import datetime, timezone, timedelta
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"
AUDIO = "/app/backend/mbox_service/audio/testansage.mp3"
MBOX_TEST = "ee277308-711d-48c2-acfd-3ac9d20ff8be"


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@test.com", "password": "password"}, timeout=20)
    if r.status_code != 200:
        pytest.skip("admin login failed")
    t = r.json().get("token") or r.json().get("access_token")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {t}"})
    return s


@pytest.fixture(scope="module")
def messe(admin):
    r = admin.post(f"{API}/messe", json={"name": "TEST_Messe Iter93"})
    assert r.status_code == 200, r.text
    m = r.json()
    yield m
    admin.delete(f"{API}/messe/{m['id']}")  # soft-delete/archive


def _upload(admin, mid, data):
    with open(AUDIO, "rb") as fh:
        return admin.post(f"{API}/messe/{mid}/audio", files={"file": ("testansage.mp3", fh, "audio/mpeg")}, data=data, timeout=120)


class TestAudioPersistence:
    def test_default_upload_not_temporary(self, admin, messe):
        r = _upload(admin, messe["id"], {"name": "TEST_Dauer", "source": "upload", "enhance": "", "temporary": "", "keep_minutes": "15"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["temporary"] is False and d["expires_at"] is None
        fid = d["id"]
        f = None
        for _ in range(40):
            time.sleep(1.5)
            f = next(x for x in admin.get(f"{API}/messe/{messe['id']}").json()["audio"] if x["id"] == fid)
            if f["status"] != "processing":
                break
        assert f["status"] in ("ready", "ready_unprocessed")
        assert f["temporary"] is False and f["expires_at"] is None
        pub = requests.get(f"{API}/messe/public/{messe['public_token']}").json()
        pf = next(a for a in pub["audio"] if a["id"] == fid)
        assert pf["temporary"] is False and pf["own"] is False

    def test_temporary_upload_expires(self, admin, messe):
        r = _upload(admin, messe["id"], {"name": "TEST_Gast", "temporary": "1", "keep_minutes": "15"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["temporary"] is True and d["expires_at"]
        exp = datetime.fromisoformat(d["expires_at"])
        delta = exp - datetime.now(timezone.utc)
        assert timedelta(minutes=13) < delta < timedelta(minutes=16), delta
        g = admin.get(f"{API}/messe/{messe['id']}").json()
        assert next(x for x in g["audio"] if x["id"] == d["id"])["temporary"] is True
        admin.delete(f"{API}/messe/{messe['id']}/audio/{d['id']}")

    def test_no_audio_messe_public(self, admin):
        m = admin.post(f"{API}/messe", json={"name": "TEST_Messe Iter93 leer"}).json()
        try:
            admin.patch(f"{API}/messe/{m['id']}", json={"device_ids": [MBOX_TEST]})
            pub = requests.get(f"{API}/messe/public/{m['public_token']}")
            assert pub.status_code == 200
            d = pub.json()
            assert d["audio"] == [] and len(d["devices"]) == 1
        finally:
            admin.delete(f"{API}/messe/{m['id']}")


class TestRegression:
    def test_mbox_devices(self, admin):
        assert admin.get(f"{API}/mbox/devices").status_code == 200
