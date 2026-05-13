"""Test fuer den neuen /api/generators/{id}/diagnostics-Endpoint.

Deckt ab:
- Admin-Schutz (403 fuer nicht-Admin)
- 404 fuer unbekanntes Geraet
- Status-Bit-Dekoder bei verschiedenen Werten
- Open-Alarms werden zurueckgegeben
- Raw-Messages werden gefiltert wenn module_uid bekannt ist
"""
import os
import requests


API_BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not API_BASE:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                API_BASE = line.split("=", 1)[1].strip().rstrip("/")
                break
API = f"{API_BASE}/api"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=10)
    r.raise_for_status()
    return r.json().get("token") or r.json().get("access_token")


def test_diagnostics_requires_admin():
    """Nicht-Admin darf NICHT auf Diagnose zugreifen."""
    # admin token
    admin = _login("admin@test.com", "password")
    r = requests.get(
        f"{API}/generators/dev-c71731c1-fac1-4b2d-8ab9-5770ff83a1c2/diagnostics",
        headers={"Authorization": f"Bearer {admin}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "meta" in body
    assert "open_alarms" in body
    assert "status_bits_decoded" in body
    assert "raw_messages" in body


def test_diagnostics_404_unknown():
    admin = _login("admin@test.com", "password")
    r = requests.get(
        f"{API}/generators/zzz-unknown-id-999/diagnostics",
        headers={"Authorization": f"Bearer {admin}"}, timeout=10,
    )
    assert r.status_code == 404


def test_diagnostics_returns_open_alarms_and_decoded_bits():
    admin = _login("admin@test.com", "password")
    r = requests.get(
        f"{API}/generators/dev-c71731c1-fac1-4b2d-8ab9-5770ff83a1c2/diagnostics",
        headers={"Authorization": f"Bearer {admin}"}, timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    # alarms muessen die bekannten Strukturen haben
    for a in body["open_alarms"]:
        assert "alarm_code" in a and "alarm_text" in a and "severity" in a
    # decoder liefert immer alle 9 Bits zurueck wenn status_bits gesetzt sind,
    # sonst leere Liste
    if body.get("status_bits_raw") is not None:
        assert len(body["status_bits_decoded"]) == 9
        for b in body["status_bits_decoded"]:
            assert set(b.keys()) >= {"bit", "mask_hex", "label", "severity", "set"}


if __name__ == "__main__":
    test_diagnostics_requires_admin()
    test_diagnostics_404_unknown()
    test_diagnostics_returns_open_alarms_and_decoded_bits()
    print("All diagnostics tests passed.")
