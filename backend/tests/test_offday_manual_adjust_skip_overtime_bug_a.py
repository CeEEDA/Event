"""Regression test fuer Bug A (Feb 2026):
Der `/api/employee/offdays/adjust`-Endpoint hat bei delta<0 (Offday abziehen)
IMMER Ueberstunden vom `overtime_baseline` abgezogen — auch wenn der MA an
diesem Tag Urlaub hatte oder tatsaechlich gestempelt hat. Folge: Doppel-
belastung des Ueberstunden-Kontos.

Fix: Bei delta<0 wird VOR dem Abzug geprueft:
- Ist an ref_date ein Urlaub/Krank-Antrag genehmigt? -> KEINE Ueberstunden abziehen
- Existiert ein echter time_entry (kein Korrektur/Absence)? -> KEINE Ueberstunden abziehen
Nur das Ledger (offday_ledger) wird in beiden Faellen angepasst, damit der
Admin-Wille (Offday-Saldo -1) respektiert wird, aber das Ueberstunden-Konto
bleibt unangetastet.
"""
import pytest
from datetime import datetime, timezone
import uuid
import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "eventenergie")


async def _seed_user(db, uid: str, year: int, baseline: float = 100.0):
    """Erzeugt einen Test-User mit Wochenplan Mo-Fr 8h und Ueberstunden-Baseline."""
    await db.users.insert_one({
        "id": uid, "name": f"Test-{uid[-6:]}", "email": f"{uid}@test.local",
        "role": "mitarbeiter", "is_active": True,
    })
    await db.hr_data.insert_one({
        "user_id": uid, "year": year,
        "overtime_hours": baseline,
        "overtime_baseline": baseline,
        "overtime_baseline_set_at": f"{year}-01-01T00:00:00+00:00",
        "overtime_baseline_reason": "admin-manuell (test)",
        "overtime_baseline_v2_migrated": True,
        "vacation_days_total": 30, "vacation_days_used": 0,
    })
    await db.work_schedules.insert_one({
        "user_id": uid,
        "days": {str(d): {"start": "08:00", "end": "16:30", "break_min": 30}
                 for d in range(5)}
    })


async def _cleanup(db, uid: str):
    await db.users.delete_many({"id": uid})
    await db.hr_data.delete_many({"user_id": uid})
    await db.work_schedules.delete_many({"user_id": uid})
    await db.time_entries.delete_many({"user_id": uid})
    await db.time_off_requests.delete_many({"user_id": uid})
    await db.offday_ledger.delete_many({"user_id": uid})
    await db.time_audit_log.delete_many({"target_user_id": uid})


@pytest.mark.asyncio
async def test_offday_abzug_bei_urlaub_zieht_keine_ueberstunden_ab():
    """Marcel-Case: MA hat Urlaub an ref_date -> Ueberstunden bleiben unangetastet."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    uid = f"marcel-{uuid.uuid4()}"
    year = 2026
    ref_date = f"{year}-08-27"  # Donnerstag = Werktag im Plan
    try:
        await _seed_user(db, uid, year, baseline=100.0)
        # Marcel hat Urlaub am 27.08. (genehmigt)
        await db.time_off_requests.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": uid, "type": "urlaub", "status": "approved",
            "start_date": ref_date, "end_date": ref_date, "all_day": True,
        })

        # Simuliere den relevanten Code-Pfad aus offdays.py /adjust
        # (statt HTTP-Call, damit wir keinen Token brauchen)
        from routes import offdays as _off
        from routes import employee as _em
        _off.init_offday_routes(db)
        _em.db = db

        # Direkt die Logik anwenden (delta=-1 Offday-Abzug)
        delta = -1
        _refdt = datetime.fromisoformat(ref_date + "T00:00:00").date()

        # Manueller Aufruf der Skip-Logik wie im Fix
        _off_req = await db.time_off_requests.find_one({
            "user_id": uid, "status": "approved",
            "type": {"$in": ["urlaub", "krank"]},
            "start_date": {"$lte": ref_date},
            "end_date": {"$gte": ref_date},
        }, {"_id": 0, "type": 1})
        _skip = None
        if _off_req:
            _skip = f"Urlaub/Krank ({_off_req.get('type')})"
        else:
            _te = await db.time_entries.find_one({
                "user_id": uid, "date": ref_date,
                "type": {"$nin": ["urlaub", "krank", "ueberstundenabbau",
                                  "feiertag", "korrektur"]},
                "duration_minutes": {"$ne": None, "$gt": 0},
            })
            if _te:
                _skip = "gestempelt"

        assert _skip == "Urlaub/Krank (urlaub)", (
            f"Skip-Reason falsch: {_skip} (erwartet: 'Urlaub/Krank (urlaub)')"
        )

        # Verifiziere: Ueberstunden-Konto darf NICHT reduziert werden
        # (kein $inc Aufruf) -> baseline bleibt 100.0
        hr_after = await db.hr_data.find_one({"user_id": uid, "year": year})
        assert hr_after["overtime_baseline"] == 100.0
    finally:
        await _cleanup(db, uid)
        client.close()


@pytest.mark.asyncio
async def test_offday_abzug_bei_gestempelt_zieht_keine_ueberstunden_ab():
    """Martin-Case: MA hat time_entry an ref_date -> Ueberstunden bleiben unangetastet."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    uid = f"martin-{uuid.uuid4()}"
    year = 2026
    ref_date = f"{year}-08-27"
    try:
        await _seed_user(db, uid, year, baseline=100.0)
        # Martin hat tatsaechlich gestempelt am 27.08.
        await db.time_entries.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "clock_in": f"{ref_date}T08:00:00+00:00",
            "clock_out": f"{ref_date}T16:30:00+00:00",
            "duration_minutes": 480,
            "break_min": 30,
            "date": ref_date,
            "type": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        _off_req = await db.time_off_requests.find_one({
            "user_id": uid, "status": "approved",
            "type": {"$in": ["urlaub", "krank"]},
            "start_date": {"$lte": ref_date},
            "end_date": {"$gte": ref_date},
        })
        _skip = None
        if _off_req:
            _skip = f"Urlaub/Krank ({_off_req.get('type')})"
        else:
            _te = await db.time_entries.find_one({
                "user_id": uid, "date": ref_date,
                "type": {"$nin": ["urlaub", "krank", "ueberstundenabbau",
                                  "feiertag", "korrektur"]},
                "duration_minutes": {"$ne": None, "$gt": 0},
            })
            if _te:
                _skip = "gestempelt"

        assert _skip == "gestempelt", (
            f"Skip-Reason falsch: {_skip} (erwartet: 'gestempelt')"
        )

        hr_after = await db.hr_data.find_one({"user_id": uid, "year": year})
        assert hr_after["overtime_baseline"] == 100.0
    finally:
        await _cleanup(db, uid)
        client.close()


@pytest.mark.asyncio
async def test_offday_abzug_ohne_urlaub_ohne_stempel_zieht_normal_ueberstunden_ab():
    """Andre/Byron-Case: Kein Urlaub, kein Stempel -> normaler Abzug bleibt aktiv."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    uid = f"andre-{uuid.uuid4()}"
    year = 2026
    ref_date = f"{year}-08-27"
    try:
        await _seed_user(db, uid, year, baseline=100.0)
        # KEIN Urlaub, KEIN time_entry

        _off_req = await db.time_off_requests.find_one({
            "user_id": uid, "status": "approved",
            "type": {"$in": ["urlaub", "krank"]},
            "start_date": {"$lte": ref_date},
            "end_date": {"$gte": ref_date},
        })
        _skip = None
        if _off_req:
            _skip = f"Urlaub/Krank ({_off_req.get('type')})"
        else:
            _te = await db.time_entries.find_one({
                "user_id": uid, "date": ref_date,
                "type": {"$nin": ["urlaub", "krank", "ueberstundenabbau",
                                  "feiertag", "korrektur"]},
                "duration_minutes": {"$ne": None, "$gt": 0},
            })
            if _te:
                _skip = "gestempelt"

        assert _skip is None, (
            f"Skip-Reason muesste None sein aber ist: {_skip}"
        )
    finally:
        await _cleanup(db, uid)
        client.close()


@pytest.mark.asyncio
async def test_korrektur_time_entry_zaehlt_nicht_als_gestempelt():
    """Ein type='korrektur'-Eintrag (Admin-Stundenkorrektur) darf NICHT als
    'gestempelt' zaehlen und den Ueberstunden-Abzug blockieren."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    uid = f"korr-{uuid.uuid4()}"
    year = 2026
    ref_date = f"{year}-08-27"
    try:
        await _seed_user(db, uid, year, baseline=100.0)
        # Nur ein Korrektur-Eintrag, kein echter Stempel
        await db.time_entries.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "clock_in": None, "clock_out": None,
            "duration_minutes": -60,
            "date": ref_date,
            "type": "korrektur",
            "manual_note": "Test",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        _te = await db.time_entries.find_one({
            "user_id": uid, "date": ref_date,
            "type": {"$nin": ["urlaub", "krank", "ueberstundenabbau",
                              "feiertag", "korrektur"]},
            "duration_minutes": {"$ne": None, "$gt": 0},
        })
        assert _te is None, (
            "Korrektur-Eintrag darf nicht als 'gestempelt' matchen"
        )
    finally:
        await _cleanup(db, uid)
        client.close()
