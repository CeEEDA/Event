"""Regression test (Jun 2026): Mitarbeiter konnten sich morgens nicht einstempeln
("Bereits eingestempelt"), sobald der Admin eine Stunden-Korrektur
(type='korrektur', clock_in=None, clock_out=None) fuer sie gebucht hatte.
Die Query `{"user_id", "clock_out": None}` matchte diese Korrektur als
"offenen Stempel-Eintrag".

Fix: alle Open-Entry-Queries filtern zusaetzlich auf `clock_in: {$ne: None}`.
"""
import os
import uuid
import pytest
import requests
import jwt as pyjwt
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "eventenergie")
BASE = os.environ.get("TEST_BACKEND_URL", "http://localhost:8001")
JWT_SECRET = os.environ.get("JWT_SECRET", "eventenergie-fileshare-secret-key-2024")


@pytest.mark.asyncio
async def test_clock_in_works_despite_korrektur_entry():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    uid = f"test-clockin-korr-{uuid.uuid4()}"
    token = pyjwt.encode({"user_id": uid}, JWT_SECRET, algorithm="HS256")
    try:
        await db.users.insert_one({
            "id": uid, "email": f"{uid}@test.local", "name": "Korrektur Tester",
            "role": "mitarbeiter", "is_active": True,
        })
        await db.time_entries.insert_one({
            "id": str(uuid.uuid4()), "user_id": uid, "user_name": "Korrektur Tester",
            "clock_in": None, "clock_out": None, "duration_minutes": -1320.0,
            "break_min": 0, "date": "2026-05-20", "manual": True, "type": "korrektur",
            "manual_note": "Test -22h",
        })

        # Status darf NICHT "eingestempelt" melden
        r = requests.get(f"{BASE}/api/employee/time/status", params={"token": token})
        assert r.status_code == 200, r.text
        assert r.json()["clocked_in"] is False

        # Einstempeln muss funktionieren
        r = requests.post(f"{BASE}/api/employee/time/clock-in", params={"token": token}, json={})
        assert r.status_code == 200, f"Einstempeln blockiert: {r.status_code} {r.text}"
        entry_id = r.json()["id"]
        assert r.json()["clock_in"] is not None

        # Zweites Einstempeln -> jetzt korrekt blockiert
        r = requests.post(f"{BASE}/api/employee/time/clock-in", params={"token": token}, json={})
        assert r.status_code == 400 and "Bereits" in r.text

        # Ausstempeln schliesst den ECHTEN Eintrag, nicht die Korrektur
        r = requests.post(f"{BASE}/api/employee/time/clock-out", params={"token": token}, json={})
        assert r.status_code == 200, r.text
        assert r.json()["id"] == entry_id and r.json()["clock_out"] is not None

        korr = await db.time_entries.find_one({"user_id": uid, "type": "korrektur"}, {"_id": 0})
        assert korr["clock_in"] is None and korr["clock_out"] is None
        assert korr["duration_minutes"] == -1320.0
    finally:
        await db.users.delete_many({"id": uid})
        await db.time_entries.delete_many({"user_id": uid})
        await db.hr_data.delete_many({"user_id": uid})
        await db.offday_ledger.delete_many({"user_id": uid})
        client.close()
