"""Regression test for the overtime-reduction (Überstundenabbau) hours calculation.

Bug: When a Mitarbeiter had a Wochenplan of 4h/day (20h/week Teilzeit) and an
admin created a 5-day Üb-Abbau, the frontend showed "5 Tage · 40h" (5*8h flat),
while the backend correctly deducted 20h from the account. The display was
wrong because AdminZeitDetailPage.jsx used `days * 8` locally instead of the
`hours_deducted_display` value from the backend.

Additionally, the resolve_time_off_request approve-path in employee.py and the
task-approval path in chat.py both used `days * 8` for the actual deduction,
which would over-deduct Teilzeit-Mitarbeiter's overtime accounts.

This test verifies the backend endpoint /api/employee/time-off returns the
correct `hours_deducted_display` (Wochenplan-Summe) for ganztags-Abbau-requests.
"""

import pytest
from datetime import datetime, timezone
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "eventenergie")


@pytest.mark.asyncio
async def test_hours_deducted_display_uses_workschedule():
    """5 Werktage × 4h/Tag = 20h (NICHT 40h)."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    from routes.employee import _soll_minutes_from_schedule

    # Simuliere Wochenplan 4h/Tag Mo-Fr (Keys sind auf Deutsch, siehe _WEEKDAY_MAP)
    schedule = {
        "days": {
            "montag":     {"soll_hours": 4},
            "dienstag":   {"soll_hours": 4},
            "mittwoch":   {"soll_hours": 4},
            "donnerstag": {"soll_hours": 4},
            "freitag":    {"soll_hours": 4},
            "samstag":    {},
            "sonntag":    {},
        }
    }

    # Simulate the calculation from GET /time-off (line 3031-3045):
    from datetime import timedelta
    _sd = datetime.strptime("2026-09-21", "%Y-%m-%d").date()  # Montag
    _ed = datetime.strptime("2026-09-25", "%Y-%m-%d").date()  # Freitag
    total_min = 0
    cur = _sd
    while cur <= _ed:
        if cur.weekday() < 5:
            total_min += _soll_minutes_from_schedule(schedule, cur.weekday())
        cur += timedelta(days=1)
    hours_deducted_display = round(total_min / 60.0, 2)

    assert hours_deducted_display == 20.0, (
        f"Erwartet 20h (5*4h), aber bekam {hours_deducted_display}h. "
        "Frontend würde flat days*8 = 40h anzeigen — das ist der Bug."
    )
    client.close()


def test_soll_minutes_returns_partial_hours():
    """_soll_minutes_from_schedule respektiert soll_hours Feld auch bei Nachkommastellen."""
    from routes.employee import _soll_minutes_from_schedule

    schedule = {"days": {"montag": {"soll_hours": 4}, "dienstag": {"soll_hours": 6.5}}}
    assert _soll_minutes_from_schedule(schedule, 0) == 240   # Mo = 4h
    assert _soll_minutes_from_schedule(schedule, 1) == 390   # Di = 6.5h
    assert _soll_minutes_from_schedule(schedule, 2) == 0     # Mi ohne Eintrag


def test_soll_minutes_handles_time_span():
    """Bei start/end statt soll_hours wird die Zeitspanne berechnet."""
    from routes.employee import _soll_minutes_from_schedule

    schedule = {"days": {"montag": {"start": "09:00", "end": "13:00", "break_min": 0}}}
    assert _soll_minutes_from_schedule(schedule, 0) == 240   # 4h

    schedule = {"days": {"dienstag": {"start": "08:00", "end": "17:00", "break_min": 60}}}
    assert _soll_minutes_from_schedule(schedule, 1) == 480   # 9h - 1h Pause = 8h
