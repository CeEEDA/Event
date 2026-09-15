"""Regression test: Clock-Out darf durch tagsüber-Admin-Korrekturen ausgeloeste
Recompute-Aufrufe NICHT die Ueberstunden verfaelschen.

Bug-Historie (Feb 2026):
  MA stempelt morgens ein (offener Eintrag, duration_minutes=None).
  Admin editiert tagsüber irgendeinen anderen Eintrag -> _recompute_overtime_for_year
  laeuft. Heute wird als Ist=0 vs Soll=8h verbucht (Filter schliesst offenen
  Eintrag aus). Bei erstmaliger baseline (None) berechnet der Recompute
  `baseline = current - diff + ded` und speichert damit +8h als Baseline,
  sodass overtime_hours 0h bleibt.
  Am Abend stempelt MA aus, Recompute laeuft erneut, heute jetzt diff=0h,
  aber baseline=+8h bleibt -> overtime_hours = 8h obwohl es 0h sein muesste.

Der Fix ueberspringt den Tag mit dem offenen Eintrag in der Bilanz-Schleife,
sodass keine kuenstliche baseline-Kompensation entsteht.

Dieser Test ruft direkt die _recompute_overtime_for_year Funktion auf und
simuliert das Szenario Schritt fuer Schritt mit einem Test-User.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

# Backend-Pfad
sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


async def run() -> None:
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    assert mongo_url and db_name, "MONGO_URL / DB_NAME nicht gesetzt"
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Import lazy nach sys.path-Setup
    from routes import employee as employee_module  # noqa: WPS433
    employee_module.db = db
    _recompute_overtime_for_year = employee_module._recompute_overtime_for_year

    # Test-User anlegen (isoliert)
    user_id = f"test-clockout-{uuid.uuid4()}"
    year = datetime.now(timezone.utc).year
    today_utc = datetime.now(timezone.utc).date()
    today_str = today_utc.isoformat()

    # Wochenplan mit 8h Soll fuer JEDEN Wochentag (damit heute egal welcher Tag
    # sicher als Plan-Arbeitstag zaehlt)
    await db.work_schedules.delete_many({"user_id": user_id})
    await db.work_schedules.insert_one({
        "user_id": user_id,
        "days": {
            d: {"start": "08:00", "end": "16:30", "break_min": 30, "soll_hours": 8.0}
            for d in ("montag", "dienstag", "mittwoch", "donnerstag",
                      "freitag", "samstag", "sonntag")
        }
    })
    await db.hr_data.delete_many({"user_id": user_id})
    await db.time_entries.delete_many({"user_id": user_id})
    await db.time_audit_log.delete_many({"target_user_id": user_id})

    # HR-Data initial mit overtime_hours=0 (wie bei Neuanlage nach Migration)
    await db.hr_data.insert_one({
        "user_id": user_id, "year": year,
        "overtime_hours": 0.0,
        "vacation_days_total": 0, "vacation_days_used": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # ── Schritt 1: MA stempelt heute morgen ein (offener Eintrag)
    clock_in = datetime.now(timezone.utc) - timedelta(hours=9)
    open_entry_id = str(uuid.uuid4())
    await db.time_entries.insert_one({
        "id": open_entry_id,
        "user_id": user_id,
        "clock_in": clock_in.isoformat(),
        "clock_out": None,
        "duration_minutes": None,
        "date": today_str,
    })

    # ── Schritt 2: Admin editiert tagsüber -> Recompute wird getriggert
    ot_after_daytime = await _recompute_overtime_for_year(user_id, year)
    hr_after_daytime = await db.hr_data.find_one({"user_id": user_id, "year": year}, {"_id": 0})
    baseline_after_daytime = hr_after_daytime.get("overtime_baseline")

    assert abs(ot_after_daytime - 0.0) < 0.05, (
        f"Nach Admin-Edit tagsüber sollte overtime_hours ~0h sein, ist {ot_after_daytime}h"
    )

    # ── Schritt 3: MA stempelt abends aus (echte Arbeit: 8h = 480min duration
    #    entspricht Soll -> diff sollte 0h sein)
    clock_out = datetime.now(timezone.utc)
    await db.time_entries.update_one(
        {"id": open_entry_id},
        {"$set": {
            "clock_out": clock_out.isoformat(),
            "duration_minutes": 480.0,
            "break_min": 30,
        }}
    )

    # ── Schritt 4: Zweiter Recompute nach Ausstempeln
    ot_after_clockout = await _recompute_overtime_for_year(user_id, year)
    hr_after_clockout = await db.hr_data.find_one({"user_id": user_id, "year": year}, {"_id": 0})
    baseline_after_clockout = hr_after_clockout.get("overtime_baseline")

    # Der Kern-Assert: overtime_hours darf nach Ausstempeln nicht "geschenkte"
    # 8h Ueberstunden zeigen, weil MA genau sein Soll gearbeitet hat.
    assert abs(ot_after_clockout - 0.0) < 0.05, (
        f"FEHLER: Nach Clock-Out zeigt overtime_hours {ot_after_clockout}h, "
        f"erwartet ~0h. Baseline={baseline_after_clockout}h "
        f"(vorher {baseline_after_daytime}h). Der Fix hat NICHT gegriffen."
    )

    print("=" * 60)
    print("BUG-FIX VERIFIZIERT ✓")
    print("  Nach Admin-Edit tagsüber:  overtime_hours =",
          ot_after_daytime, "h, baseline =", baseline_after_daytime, "h")
    print("  Nach Clock-Out abends:     overtime_hours =",
          ot_after_clockout, "h, baseline =", baseline_after_clockout, "h")
    print("=" * 60)

    # ── Bonus-Fall: MA arbeitet 1h ueber sein Soll (9h statt 8h) -> +1h
    await db.time_entries.update_one(
        {"id": open_entry_id},
        {"$set": {"duration_minutes": 540.0}}  # 9h
    )
    ot_plus_1h = await _recompute_overtime_for_year(user_id, year)
    assert abs(ot_plus_1h - 1.0) < 0.05, (
        f"Extra-Stunde nicht korrekt: erwartet ~1h, tatsaechlich {ot_plus_1h}h"
    )
    print("  Bonus (9h Arbeit, 8h Soll): overtime_hours =", ot_plus_1h, "h ✓")

    # Cleanup
    await db.work_schedules.delete_many({"user_id": user_id})
    await db.hr_data.delete_many({"user_id": user_id})
    await db.time_entries.delete_many({"user_id": user_id})
    await db.time_audit_log.delete_many({"target_user_id": user_id})
    client.close()


if __name__ == "__main__":
    asyncio.run(run())
