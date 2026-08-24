"""
Iteration 87 – HalloPetra Stability Regression Tests

Verifies:
 1) MongoDB connection stable (/api/health 200)
 2) Auto-Sync loop default interval = 1800s (code-level assertion)
 3) MongoDB serverSelectionTimeoutMS = 30000 (code-level assertion)
 4) HalloPetra endpoints still functional for admin
 5) Manual /api/hallopetra/sync-calls completes without crash
 6) Regression: /api/auth/login (admin), /api/tasks
"""

import os
import re
import time
import inspect
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback for CI where env not exported; read from frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(api):
    resp = api.post(f"{BASE_URL}/api/auth/login",
                    json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                    timeout=30)
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text[:200]}"
    data = resp.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"No token in login response: {data}"
    return tok


# ─── Code-level assertions (verify fixes are in the source) ───────────────────

def test_mongo_server_selection_timeout_30000():
    with open("/app/backend/server.py") as f:
        src = f.read()
    m = re.search(r"serverSelectionTimeoutMS\s*=\s*(\d+)", src)
    assert m, "serverSelectionTimeoutMS not found in server.py"
    assert int(m.group(1)) == 30000, f"Expected 30000, got {m.group(1)}"


def test_auto_sync_loop_default_interval_1800():
    with open("/app/backend/routes/hallopetra.py") as f:
        src = f.read()
    m = re.search(r"_auto_sync_loop\(\s*interval_seconds:\s*int\s*=\s*(\d+)", src)
    assert m, "_auto_sync_loop signature not found"
    assert int(m.group(1)) == 1800, f"Expected 1800s, got {m.group(1)}"


def test_start_log_line_mentions_30_min():
    with open("/app/backend/routes/hallopetra.py") as f:
        src = f.read()
    assert "Intervall 30 Min" in src, "Start log should say 'Intervall 30 Min'"


def test_throttling_yields_present_in_heavy_loops():
    with open("/app/backend/routes/hallopetra.py") as f:
        src = f.read()
    # Expect at least 3 asyncio.sleep(0.05) occurrences (calls, contacts, enrich)
    count = len(re.findall(r"_asyncio\.sleep\(0\.05\)", src))
    assert count >= 3, f"Expected >=3 throttling yields, found {count}"


# ─── Runtime API tests ────────────────────────────────────────────────────────

def test_health_endpoint(api):
    # /api/health – standard health check
    r = api.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200, f"health returned {r.status_code}: {r.text[:200]}"


def test_admin_login(admin_token):
    assert isinstance(admin_token, str) and len(admin_token) > 10


def test_tasks_list_regression(api, admin_token):
    r = api.get(f"{BASE_URL}/api/tasks", params={"token": admin_token}, timeout=30)
    # Accept 200 (list) – if endpoint uses different auth, still shouldn't 500
    assert r.status_code < 500, f"/api/tasks server error: {r.status_code} {r.text[:200]}"


def test_hallopetra_status(api, admin_token):
    r = api.get(f"{BASE_URL}/api/hallopetra/status",
                params={"token": admin_token}, timeout=15)
    assert r.status_code == 200, f"status: {r.status_code} {r.text[:200]}"
    data = r.json()
    assert "counts" in data or "config" in data or "webhook_url" in data


def test_hallopetra_recent_calls(api, admin_token):
    r = api.get(f"{BASE_URL}/api/hallopetra/recent-calls",
                params={"token": admin_token, "limit": 5}, timeout=15)
    assert r.status_code == 200, f"recent-calls: {r.status_code} {r.text[:200]}"


def test_hallopetra_calls(api, admin_token):
    r = api.get(f"{BASE_URL}/api/hallopetra/calls",
                params={"token": admin_token, "limit": 5}, timeout=15)
    assert r.status_code == 200, f"calls: {r.status_code} {r.text[:200]}"


def test_hallopetra_contacts(api, admin_token):
    r = api.get(f"{BASE_URL}/api/hallopetra/contacts",
                params={"token": admin_token, "limit": 5}, timeout=15)
    assert r.status_code == 200, f"contacts: {r.status_code} {r.text[:200]}"


def test_hallopetra_manual_sync_calls(api, admin_token):
    # Manual trigger – should complete quickly, not crash backend
    start = time.time()
    r = api.post(f"{BASE_URL}/api/hallopetra/sync-calls",
                 params={"token": admin_token, "limit": 5}, timeout=60)
    elapsed = time.time() - start
    # 400 acceptable if token not configured; server must not 500
    assert r.status_code in (200, 400), \
        f"sync-calls: {r.status_code} {r.text[:300]}"
    assert elapsed < 60, f"sync-calls too slow: {elapsed:.1f}s"


def test_backend_still_alive_after_sync(api):
    # Post-sync sanity: health still 200 -> no crash from sync
    r = api.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200
