"""End-to-End Tests fuer Tankwagen Raw Stream Endpoints (push / tail / clear).
Nutzt die laufende Backend-Instanz ueber REACT_APP_BACKEND_URL.
"""
import os
import time
import requests


BASE = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE:
    # Fallback: lese aus /app/frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass
BASE = (BASE or "").rstrip("/")
PUSH = f"{BASE}/api/system/tankwagen/raw-stream/push"
TAIL = f"{BASE}/api/system/tankwagen/raw-stream/tail"
CLEAR = f"{BASE}/api/system/tankwagen/raw-stream"

PI_ID = "pytest-fork-pi"


def setup_function():
    requests.delete(CLEAR, params={"pi_id": PI_ID}, timeout=10)


def teardown_function():
    requests.delete(CLEAR, params={"pi_id": PI_ID}, timeout=10)


def test_push_single_chunk():
    ts = time.time()
    r = requests.post(PUSH, json={
        "pi_id": PI_ID, "hostname": "fork-test",
        "chunks": [{"ts": ts, "direction": "rx", "hex": "1b b3 ff", "note": "poll"}],
    }, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] == 1


def test_push_normalizes_hex():
    ts = time.time()
    requests.post(PUSH, json={
        "pi_id": PI_ID, "chunks": [{"ts": ts, "direction": "rx", "hex": "1B  B3 ff"}],
    }, timeout=10)
    r = requests.get(TAIL, params={"pi_id": PI_ID}, timeout=10)
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["hex"] == "1bb3ff"


def test_tail_returns_inserted_in_order():
    base_ts = time.time()
    chunks = [
        {"ts": base_ts + 0.0, "direction": "rx", "hex": "10"},
        {"ts": base_ts + 0.1, "direction": "tx", "hex": "12"},
        {"ts": base_ts + 0.2, "direction": "rx", "hex": "1b76"},
    ]
    requests.post(PUSH, json={"pi_id": PI_ID, "chunks": chunks}, timeout=10)
    r = requests.get(TAIL, params={"pi_id": PI_ID}, timeout=10)
    items = r.json()["items"]
    assert [i["hex"] for i in items] == ["10", "12", "1b76"]


def test_tail_since_ts_filter():
    base_ts = time.time()
    chunks = [
        {"ts": base_ts + 0.0, "direction": "rx", "hex": "aa"},
        {"ts": base_ts + 1.0, "direction": "rx", "hex": "bb"},
        {"ts": base_ts + 2.0, "direction": "rx", "hex": "cc"},
    ]
    requests.post(PUSH, json={"pi_id": PI_ID, "chunks": chunks}, timeout=10)
    r = requests.get(TAIL, params={"pi_id": PI_ID, "since_ts": base_ts + 0.5}, timeout=10)
    hexes = [i["hex"] for i in r.json()["items"]]
    assert hexes == ["bb", "cc"], f"only chunks > since_ts should be returned, got {hexes}"


def test_pi_list_in_tail_response():
    requests.post(PUSH, json={
        "pi_id": PI_ID, "hostname": "fork-host",
        "chunks": [{"ts": time.time(), "direction": "rx", "hex": "00"}],
    }, timeout=10)
    r = requests.get(TAIL, params={"pi_id": PI_ID}, timeout=10)
    pis = r.json()["pis"]
    found = next((p for p in pis if p["pi_id"] == PI_ID), None)
    assert found, f"Pi {PI_ID} sollte in 'pis' Liste auftauchen, gefunden: {[p['pi_id'] for p in pis]}"
    assert found["hostname"] == "fork-host"


def test_clear_with_pi_id_only_clears_that_pi():
    ts = time.time()
    requests.post(PUSH, json={"pi_id": PI_ID, "chunks": [{"ts": ts, "direction": "rx", "hex": "aa"}]}, timeout=10)
    requests.post(PUSH, json={"pi_id": "other-pi-keep", "chunks": [{"ts": ts, "direction": "rx", "hex": "bb"}]}, timeout=10)
    try:
        del_resp = requests.delete(CLEAR, params={"pi_id": PI_ID}, timeout=10)
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] >= 1
        # PI_ID soll leer sein
        r = requests.get(TAIL, params={"pi_id": PI_ID}, timeout=10)
        assert r.json()["items"] == []
        # Anderer Pi muss noch da sein
        r = requests.get(TAIL, params={"pi_id": "other-pi-keep"}, timeout=10)
        assert any(i["hex"] == "bb" for i in r.json()["items"])
    finally:
        requests.delete(CLEAR, params={"pi_id": "other-pi-keep"}, timeout=10)


def test_empty_chunks_returns_zero():
    r = requests.post(PUSH, json={"pi_id": PI_ID, "chunks": []}, timeout=10)
    assert r.status_code == 200
    assert r.json()["accepted"] == 0
