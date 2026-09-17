"""Regression-Test (Feb 2026): Offday-Anlage triggert Recompute mit
`force=True` (bypass 5h-Sprung-Safety) und schreibt Audit-Log-Eintraege.

Bewusst NICHT im Test: Semantik-Aenderung "Offday zieht -9h aus Ueberstunden"
- die braucht Baseline-Migration fuer Bestandsuser und laeuft in Phase 2.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient


TEST_USER_ID = f"test-offday-bug-{uuid.uuid4().hex[:8]}"


async def _setup(db):
    await db.users.insert_one({
        "id": TEST_USER_ID, "email": f"{TEST_USER_ID}@test.local",
        "name": "Test Offday", "role": "mitarbeiter", "is_active": True,
    })
    await db.work_schedules.insert_one({
        "user_id": TEST_USER_ID,
        "days": {
            "montag": {"soll_hours": 9, "pause_min": 30},
            "dienstag": {"soll_hours": 9, "pause_min": 30},
            "mittwoch": {"soll_hours": 9, "pause_min": 30},
            "donnerstag": {"soll_hours": 9, "pause_min": 30},
            "freitag": {"soll_hours": 9, "pause_min": 30},
            "samstag": {"soll_hours": 0, "pause_min": 0},
            "sonntag": {"soll_hours": 0, "pause_min": 0},
        },
    })
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.hr_data.insert_one({
        "user_id": TEST_USER_ID, "year": 2026,
        "overtime_hours": 200.0, "overtime_baseline": 200.0,
        "overtime_baseline_set_at": now_iso,
        "overtime_baseline_reason": "test-setup",
        "overtime_baseline_v2_migrated": True,
        "vacation_days_total": 0, "vacation_days_used": 0,
    })


async def _cleanup(db):
    await db.users.delete_many({"id": TEST_USER_ID})
    await db.work_schedules.delete_many({"user_id": TEST_USER_ID})
    await db.hr_data.delete_many({"user_id": TEST_USER_ID})
    await db.shift_assignments.delete_many({"user_id": TEST_USER_ID})
    await db.offday_ledger.delete_many({"user_id": TEST_USER_ID})
    await db.time_entries.delete_many({"user_id": TEST_USER_ID})
    await db.time_audit_log.delete_many({"target_user_id": TEST_USER_ID})


async def run():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    from routes import employee as em
    em.db = db
    from routes import offdays as offdays_module
    offdays_module.db = db

    await _cleanup(db)
    await _setup(db)

    print("=" * 60)
    print("TEST 1: force=False blockiert bei Sprung >5h (baseline recent)")
    print("=" * 60)
    await db.hr_data.update_one(
        {"user_id": TEST_USER_ID, "year": 2026},
        {"$set": {"overtime_baseline": 100.0}},
    )
    await em._recompute_overtime_for_year(TEST_USER_ID, 2026)  # force=False
    hr = await db.hr_data.find_one({"user_id": TEST_USER_ID, "year": 2026}, {"_id": 0})
    print(f"OHNE force: overtime_hours = {hr.get('overtime_hours')} (Safety blockiert)")
    assert abs(hr.get("overtime_hours") - 200.0) < 0.5

    print("\n" + "=" * 60)
    print("TEST 2: force=True erlaubt Sprung")
    print("=" * 60)
    await em._recompute_overtime_for_year(TEST_USER_ID, 2026, force=True)
    hr = await db.hr_data.find_one({"user_id": TEST_USER_ID, "year": 2026}, {"_id": 0})
    print(f"MIT force=True: overtime_hours = {hr.get('overtime_hours')}")
    assert hr.get("overtime_hours") < 195.0, "force=True muss den Sprung durchlassen"

    print("\n" + "=" * 60)
    print("TEST 3: Audit-Log Helper funktioniert fuer Offdays")
    print("=" * 60)
    caller = {"id": "test-admin", "name": "TestAdmin", "role": "admin"}
    await em._log_audit(TEST_USER_ID, "offday_create", caller,
        after={"date": "2026-09-20", "is_offday": True},
        summary="Offday 2026-09-20 eingetragen")
    await em._log_audit(TEST_USER_ID, "offday_create", caller,
        after={"dates": ["2026-11-16", "2026-11-17"], "count": 2, "is_offday": True},
        summary="Offday 2026-11-16 - 2026-11-17 eingetragen (2 Tage)")
    await em._log_audit(TEST_USER_ID, "offday_delete", caller,
        before={"date": "2026-09-20", "is_offday": True},
        summary="Offday 2026-09-20 geloescht")
    audit = await db.time_audit_log.find(
        {"target_user_id": TEST_USER_ID,
         "action": {"$in": ["offday_create", "offday_delete", "offday_update"]}},
    ).to_list(50)
    print(f"Audit-Eintraege: {len(audit)} (erwartet: 3)")
    assert len(audit) == 3

    print("\n" + "=" * 60)
    print("ALLE TESTS BESTANDEN")
    print("=" * 60)

    await _cleanup(db)
    client.close()


if __name__ == "__main__":
    asyncio.run(run())
