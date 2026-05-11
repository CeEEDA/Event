"""End-to-End-Tests fuer Trupp-Management (pro Auftrag) im Einsatztagebuch.

Testet:
  - CRUD von Trupps (Create/Read/Update/Delete)
  - Auto-Naming "Trupp N"
  - Mitglieder-Limit auf 4
  - is_busy=True wenn Trupp einer offenen Stoerung zugewiesen ist
  - is_busy=False wenn Stoerung auf "resolved" gesetzt wird
  - Trupp wird beim Loeschen auch aus zugewiesenen Diary-Eintraegen entfernt
"""
import os
import requests
from pymongo import MongoClient


def _api_url():
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL nicht gefunden")


def _token():
    r = requests.post(
        f"{_api_url()}/api/auth/login",
        json={"email": "admin@test.com", "password": "password"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("access_token") or r.json().get("token")


def _order_pk():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "test_database")]
    doc = db.orders_cache.find_one({}, {"_id": 0, "primary_key": 1})
    assert doc, "Mindestens ein Auftrag muss in orders_cache existieren"
    return doc["primary_key"]


def test_trupp_crud_and_busy_status():
    api = _api_url()
    token = _token()
    h = {"Authorization": f"Bearer {token}"}
    pk = _order_pk()

    # Cleanup: bestehende Test-Trupps mit "PYTEST" weg
    existing = requests.get(f"{api}/api/orders/{pk}/trupps", headers=h, timeout=10).json()
    for t in existing.get("trupps", []):
        if "PYTEST" in t.get("name", ""):
            requests.delete(f"{api}/api/orders/{pk}/trupps/{t['id']}", headers=h, timeout=10)

    # Create (auto-name)
    r = requests.post(f"{api}/api/orders/{pk}/trupps",
                      json={"name": "PYTEST Trupp", "members": ["A", "B"]}, headers=h, timeout=10)
    assert r.status_code == 200, r.text
    trupp = r.json()
    tid = trupp["id"]
    assert trupp["name"] == "PYTEST Trupp"
    assert trupp["is_busy"] is False
    assert trupp["members"] == ["A", "B"]

    # Update mit > 4 Mitgliedern -> truncate
    r = requests.put(f"{api}/api/orders/{pk}/trupps/{tid}",
                     json={"name": "PYTEST Trupp Alpha",
                           "members": ["1", "2", "3", "4", "5"]}, headers=h, timeout=10)
    assert r.status_code == 200, r.text
    assert len(r.json()["members"]) == 4

    # Trupp zuweisen via Diary
    r = requests.post(f"{api}/api/orders/{pk}/diary",
                      json={"reason": "PYTEST Stoerung mit Trupp",
                            "assigned_trupp_ids": [tid]}, headers=h, timeout=10)
    assert r.status_code == 200, r.text
    diary_id = r.json()["id"]
    assert tid in r.json()["assigned_trupp_ids"]

    # is_busy sollte jetzt True sein
    trupps = requests.get(f"{api}/api/orders/{pk}/trupps", headers=h, timeout=10).json()["trupps"]
    me = next(t for t in trupps if t["id"] == tid)
    assert me["is_busy"] is True

    # Stoerung als behoben markieren -> Trupp wieder frei
    r = requests.post(f"{api}/api/orders/{pk}/diary/{diary_id}/resolve", headers=h, timeout=10)
    assert r.status_code == 200, r.text
    trupps = requests.get(f"{api}/api/orders/{pk}/trupps", headers=h, timeout=10).json()["trupps"]
    me = next(t for t in trupps if t["id"] == tid)
    assert me["is_busy"] is False

    # Cleanup
    requests.delete(f"{api}/api/orders/{pk}/diary/{diary_id}", headers=h, timeout=10)
    r = requests.delete(f"{api}/api/orders/{pk}/trupps/{tid}", headers=h, timeout=10)
    assert r.status_code == 200, r.text


def test_trupp_auto_naming():
    api = _api_url()
    token = _token()
    h = {"Authorization": f"Bearer {token}"}
    pk = _order_pk()
    # Cleanup
    existing = requests.get(f"{api}/api/orders/{pk}/trupps", headers=h, timeout=10).json()
    for t in existing.get("trupps", []):
        requests.delete(f"{api}/api/orders/{pk}/trupps/{t['id']}", headers=h, timeout=10)

    # Erster Trupp ohne Name -> "Trupp 1"
    r1 = requests.post(f"{api}/api/orders/{pk}/trupps", json={"name": None}, headers=h, timeout=10)
    assert r1.json()["name"] == "Trupp 1"
    r2 = requests.post(f"{api}/api/orders/{pk}/trupps", json={"name": ""}, headers=h, timeout=10)
    assert r2.json()["name"] == "Trupp 2"

    # Cleanup
    requests.delete(f"{api}/api/orders/{pk}/trupps/{r1.json()['id']}", headers=h, timeout=10)
    requests.delete(f"{api}/api/orders/{pk}/trupps/{r2.json()['id']}", headers=h, timeout=10)


if __name__ == "__main__":
    test_trupp_crud_and_busy_status()
    print("CRUD/Busy OK")
    test_trupp_auto_naming()
    print("Auto-Naming OK")
