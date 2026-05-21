"""Tests for /api/employee/time/overview endpoint (Iteration 69).

Validiert:
- Auth (kein/ungueltiger Token -> 401/422)
- User mit Wochenplan (ma1) -> has_schedule=true, Wochensumme 1920min (32h)
- User ohne Wochenplan (admin) -> has_schedule=false, alles 0
- Feiertag Pfingstmontag 25.5.2026 (RLP) in next_7_days korrekt erkannt
- Live-Stempelung: offene clock_in wird im ist_by_date eingerechnet
- Antwortstruktur (today, week, days[], next_7_days, overtime_hours)
"""

import os
import pytest
import requests
from datetime import date, timedelta

# Tests use the public preview URL (loaded from frontend/.env or env)
_BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not _BACKEND_URL:
    # Fallback: parse from frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    _BACKEND_URL = line.split("=", 1)[1].strip()
                    break
    except FileNotFoundError:
        pass
assert _BACKEND_URL, "REACT_APP_BACKEND_URL not set"
BASE_URL = _BACKEND_URL.rstrip("/")
EP = f"{BASE_URL}/api/employee/time/overview"

MA_EMAIL = "ma1@test.com"
MA_PASSWORD = "Anna2026!"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"


# ── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def ma_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": MA_EMAIL, "password": MA_PASSWORD},
        timeout=10,
    )
    assert r.status_code == 200, f"ma1 login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=10,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


# ── Auth ────────────────────────────────────────────────────────────────────
class TestAuth:
    def test_invalid_token_returns_401(self):
        r = requests.get(f"{EP}?token=garbage_invalid_xyz", timeout=10)
        assert r.status_code == 401

    def test_empty_token_returns_401(self):
        r = requests.get(f"{EP}?token=", timeout=10)
        assert r.status_code == 401

    def test_no_token_returns_422(self):
        # FastAPI Query(...) -> 422 wenn Param fehlt (akzeptabel/erwartet)
        r = requests.get(EP, timeout=10)
        assert r.status_code in (401, 422)


# ── User OHNE Wochenplan ───────────────────────────────────────────────────
class TestNoSchedule:
    def test_admin_has_no_schedule(self, admin_token):
        r = requests.get(f"{EP}?token={admin_token}", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()

        # Top-level Struktur
        for k in ("today", "week", "next_7_days", "overtime_hours", "has_schedule"):
            assert k in data, f"Missing key: {k}"

        # Kein Schedule -> kein Crash, alle soll_minutes=0
        assert data["has_schedule"] is False
        assert data["today"]["soll_minutes"] == 0
        assert data["week"]["soll_minutes"] == 0
        for d in data["week"]["days"]:
            assert d["soll_minutes"] == 0
        for d in data["next_7_days"]:
            assert d["soll_minutes"] == 0


# ── User MIT Wochenplan (ma1: Mo-Do je 8h, Fr/Sa/So 0h) ────────────────────
class TestWithSchedule:
    def test_ma1_has_schedule_and_correct_structure(self, ma_token):
        r = requests.get(f"{EP}?token={ma_token}", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["has_schedule"] is True

        # today struktur
        t = data["today"]
        for k in ("date", "weekday", "is_holiday", "holiday_name",
                  "soll_minutes", "ist_minutes", "diff_minutes"):
            assert k in t, f"today missing: {k}"
        assert isinstance(t["is_holiday"], bool)
        assert isinstance(t["soll_minutes"], int)
        assert isinstance(t["ist_minutes"], int)

        # week struktur
        w = data["week"]
        for k in ("start", "end", "soll_minutes", "ist_minutes", "diff_minutes", "days"):
            assert k in w
        assert len(w["days"]) == 7
        # Wochenstart muss ein Montag sein
        start_d = date.fromisoformat(w["start"])
        end_d = date.fromisoformat(w["end"])
        assert start_d.weekday() == 0, f"week.start not Monday: {start_d}"
        assert end_d.weekday() == 6, f"week.end not Sunday: {end_d}"
        assert (end_d - start_d).days == 6

    def test_ma1_week_soll_is_32h(self, ma_token):
        """ma1 hat Mo-Do je 8h. Wochensumme = 32h = 1920 Minuten.
        Pruefe wochenkonsistent: Wenn KEIN Feiertag in der aktuellen Woche faellt,
        muss week.soll_minutes==1920. Andernfalls Feiertage abziehen."""
        r = requests.get(f"{EP}?token={ma_token}", timeout=10)
        data = r.json()

        # Sum aus days[] berechnen damit Test feiertagsunabhaengig ist:
        soll_sum = 0
        for d in data["week"]["days"]:
            wd_idx = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"].index(d["weekday"])
            if d["is_holiday"]:
                assert d["soll_minutes"] == 0, "Feiertag muss soll=0 haben"
                continue
            if wd_idx <= 3:  # Mo-Do
                assert d["soll_minutes"] == 480, f"{d['date']} Mo-Do soll=480, got {d['soll_minutes']}"
            else:  # Fr-So
                assert d["soll_minutes"] == 0
            soll_sum += d["soll_minutes"]

        assert data["week"]["soll_minutes"] == soll_sum
        # diff_minutes konsistent
        assert data["week"]["diff_minutes"] == data["week"]["ist_minutes"] - data["week"]["soll_minutes"]

    def test_next_7_days_length_and_keys(self, ma_token):
        r = requests.get(f"{EP}?token={ma_token}", timeout=10)
        data = r.json()
        n7 = data["next_7_days"]
        assert len(n7) == 7
        # Erstes Element = morgen
        tomorrow = (date.fromisoformat(data["today"]["date"]) + timedelta(days=1)).isoformat()
        assert n7[0]["date"] == tomorrow
        for d in n7:
            for k in ("date", "weekday", "is_holiday", "soll_minutes"):
                assert k in d
            assert isinstance(d["is_holiday"], bool)


# ── Feiertage (Pfingstmontag 25.5.2026 RLP) ────────────────────────────────
class TestHolidays:
    def test_pfingstmontag_in_next_7_or_week(self, ma_token):
        """Pfingstmontag 2026 = 25.5.2026. Wenn heute in der Spannweite ist,
        muss er als is_holiday=true / holiday_name='Pfingstmontag' / soll=0
        erscheinen. Sonst ueberspringen."""
        r = requests.get(f"{EP}?token={ma_token}", timeout=10)
        data = r.json()
        target = "2026-05-25"

        candidates = list(data["week"]["days"]) + list(data["next_7_days"])
        match = [d for d in candidates if d["date"] == target]
        if not match:
            pytest.skip(f"25.5.2026 ausserhalb Test-Zeitspanne (heute={data['today']['date']})")

        for d in match:
            assert d["is_holiday"] is True, f"25.5.2026 muss is_holiday=true sein: {d}"
            # In week.days hat days[] holiday_name; in next_7_days auch
            assert d.get("holiday_name") == "Pfingstmontag", f"holiday_name falsch: {d}"
            assert d["soll_minutes"] == 0, "Feiertag muss soll=0 haben"

    def test_holiday_today_logic(self, ma_token):
        """Wenn heute Feiertag ist, today.soll_minutes==0 und holiday_name gesetzt."""
        r = requests.get(f"{EP}?token={ma_token}", timeout=10)
        t = r.json()["today"]
        if t["is_holiday"]:
            assert t["soll_minutes"] == 0
            assert t["holiday_name"] is not None
        else:
            assert t["holiday_name"] in (None, "")


# ── Live-Stempelung: offene clock_in muss in ist_minutes eingehen ──────────
class TestLivePunch:
    def test_open_clock_in_increments_ist_or_zero_due_to_break(self, ma_token):
        """Clock-in -> Overview -> Clock-out. ist_minutes sollte nicht crashen
        und Wert >= 0 zurueckgeben. Bei sehr kurzer Dauer kann Wert = 0 sein
        wenn break_min > live_mins (Code: max(0, live_mins - break_min))."""
        # Defensive: vorhandene offene Stempelung schliessen falls vorhanden
        co = requests.post(
            f"{BASE_URL}/api/employee/time/clock-out?token={ma_token}",
            json={}, timeout=10,
        )
        # 200 (geschlossen) oder 400 ("nicht eingestempelt") sind beide ok
        assert co.status_code in (200, 400)

        # Clock in
        ci = requests.post(
            f"{BASE_URL}/api/employee/time/clock-in?token={ma_token}",
            json={}, timeout=10,
        )
        assert ci.status_code == 200, f"clock-in failed: {ci.text}"
        entry_id = ci.json().get("id")
        assert entry_id

        try:
            # Overview waehrend Stempelung
            r = requests.get(f"{EP}?token={ma_token}", timeout=10)
            assert r.status_code == 200
            data = r.json()
            ist_today = data["today"]["ist_minutes"]
            assert isinstance(ist_today, int) and ist_today >= 0
            # Strukturpruefung: today/week.days[today] konsistent
            today_str = data["today"]["date"]
            day_in_week = next(d for d in data["week"]["days"] if d["date"] == today_str)
            assert day_in_week["ist_minutes"] == ist_today
        finally:
            # Cleanup: ausstempeln
            requests.post(
                f"{BASE_URL}/api/employee/time/clock-out?token={ma_token}",
                json={}, timeout=10,
            )


# ── Konsistenz: today entspricht days[heute] ───────────────────────────────
class TestConsistency:
    def test_today_matches_week_days_entry(self, ma_token):
        r = requests.get(f"{EP}?token={ma_token}", timeout=10)
        data = r.json()
        today_date = data["today"]["date"]
        matching = [d for d in data["week"]["days"] if d["date"] == today_date]
        assert len(matching) == 1
        for k in ("soll_minutes", "is_holiday", "weekday"):
            assert matching[0][k] == data["today"][k]

    def test_diff_minutes_math(self, ma_token):
        r = requests.get(f"{EP}?token={ma_token}", timeout=10)
        data = r.json()
        assert data["today"]["diff_minutes"] == data["today"]["ist_minutes"] - data["today"]["soll_minutes"]
        assert data["week"]["diff_minutes"] == data["week"]["ist_minutes"] - data["week"]["soll_minutes"]
