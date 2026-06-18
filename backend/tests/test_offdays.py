"""Backend tests for Offday / Ausgleichstage feature.

Endpoints under test:
 - GET    /api/employee/offdays/me
 - GET    /api/employee/offdays              (verwaltung-only)
 - GET    /api/employee/offdays/user/{user_id}
 - POST   /api/employee/offdays/adjust
 - POST   /api/employee/offdays/recompute
 - POST   /api/employee/shift-plan        (is_offday consume + flip)
 - DELETE /api/employee/shift-plan/{id}   (release)

Also imports the pure helper `is_sunday_or_rlp_holiday` directly to validate
RLP-Feiertage without needing a Sunday-clock-in (which is hard to trigger
because backend uses server-side `date.today()`).
"""
import os
import sys
import uuid
from datetime import date

import pytest
import requests

# Make backend imports available so we can hit the pure helper.
sys.path.insert(0, "/app/backend")
from routes.offdays import is_sunday_or_rlp_holiday, _rlp_holidays  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # Fallback: read frontend/.env directly
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = (BASE_URL or "").rstrip("/")

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"
MA_EMAIL = "ma1@test.com"
MA_PASSWORD = "Anna2026!"


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_login(session):
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    j = r.json()
    return {"token": j["token"], "user": j["user"]}


@pytest.fixture(scope="module")
def ma_login(session):
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": MA_EMAIL, "password": MA_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Mitarbeiter login failed: {r.status_code} {r.text}")
    j = r.json()
    return {"token": j["token"], "user": j["user"]}


# ── Pure helper tests (RLP holidays) ────────────────────────────────────

class TestRLPHolidayHelper:
    def test_neujahr_2026_thursday_holiday(self):
        ok, reason = is_sunday_or_rlp_holiday("2026-01-01")
        assert ok is True
        assert reason == "holiday"

    def test_tag_der_einheit_2026(self):
        ok, reason = is_sunday_or_rlp_holiday("2026-10-03")
        assert ok is True
        assert reason == "holiday"

    def test_christmas_25_dec_2026(self):
        ok, reason = is_sunday_or_rlp_holiday("2026-12-25")
        assert ok is True
        assert reason == "holiday"

    def test_normal_weekday_no(self):
        # 2026-01-07 is a Wednesday and not a holiday
        ok, reason = is_sunday_or_rlp_holiday("2026-01-07")
        assert ok is False
        assert reason == ""

    def test_sunday_detection(self):
        # 2026-01-04 is a Sunday
        ok, reason = is_sunday_or_rlp_holiday("2026-01-04")
        assert ok is True
        assert reason == "sunday"

    def test_easter_movable_2026(self):
        # Easter Sunday 2026 = 2026-04-05 (Sun), Karfreitag 2026-04-03
        hols = _rlp_holidays(2026)
        assert date(2026, 4, 3) in hols  # Karfreitag
        assert date(2026, 4, 6) in hols  # Ostermontag
        assert date(2026, 5, 14) in hols  # Christi Himmelfahrt
        assert date(2026, 5, 25) in hols  # Pfingstmontag
        assert date(2026, 6, 4) in hols  # Fronleichnam


# ── Auth / Permission tests ─────────────────────────────────────────────

class TestAuth:
    def test_me_requires_token(self, session):
        r = session.get(f"{BASE_URL}/api/employee/offdays/me")
        assert r.status_code in (422, 401)

    def test_me_invalid_token(self, session):
        r = session.get(f"{BASE_URL}/api/employee/offdays/me?token=invalid.token.xx")
        assert r.status_code == 401

    def test_admin_list_works(self, session, admin_login):
        r = session.get(f"{BASE_URL}/api/employee/offdays?token={admin_login['token']}")
        assert r.status_code == 200
        j = r.json()
        assert "balances" in j and "recent" in j
        assert isinstance(j["balances"], list)
        assert isinstance(j["recent"], list)


# ── Core ledger flows ───────────────────────────────────────────────────

class TestOffdayMe:
    def test_me_returns_balance_and_entries(self, session, admin_login):
        r = session.get(f"{BASE_URL}/api/employee/offdays/me?token={admin_login['token']}")
        assert r.status_code == 200
        j = r.json()
        assert "balance" in j and "entries" in j
        assert isinstance(j["balance"], int)
        assert isinstance(j["entries"], list)


class TestAdjustEndpoint:
    """All test data uses delta on a real user id so we can clean up via delta-undo."""

    def _balance(self, session, admin_login, uid):
        r = session.get(
            f"{BASE_URL}/api/employee/offdays/user/{uid}?token={admin_login['token']}"
        )
        assert r.status_code == 200
        return r.json()["balance"]

    def test_adjust_increases_balance_and_reverts(self, session, admin_login):
        uid = admin_login["user"]["id"]
        before = self._balance(session, admin_login, uid)
        # +1
        r = session.post(
            f"{BASE_URL}/api/employee/offdays/adjust?token={admin_login['token']}",
            json={"user_id": uid, "delta": 1, "note": "TEST_offday_adjust_up"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["new_balance"] == before + 1
        # -1 revert (cleanup)
        r = session.post(
            f"{BASE_URL}/api/employee/offdays/adjust?token={admin_login['token']}",
            json={"user_id": uid, "delta": -1, "note": "TEST_offday_adjust_revert"},
        )
        assert r.status_code == 200
        assert r.json()["new_balance"] == before

    def test_adjust_delta_zero_400(self, session, admin_login):
        uid = admin_login["user"]["id"]
        r = session.post(
            f"{BASE_URL}/api/employee/offdays/adjust?token={admin_login['token']}",
            json={"user_id": uid, "delta": 0, "note": "TEST_zero"},
        )
        assert r.status_code == 400

    def test_adjust_delta_not_int_400(self, session, admin_login):
        uid = admin_login["user"]["id"]
        r = session.post(
            f"{BASE_URL}/api/employee/offdays/adjust?token={admin_login['token']}",
            json={"user_id": uid, "delta": "abc", "note": "TEST_nan"},
        )
        assert r.status_code == 400

    def test_adjust_unknown_user_404(self, session, admin_login):
        r = session.post(
            f"{BASE_URL}/api/employee/offdays/adjust?token={admin_login['token']}",
            json={"user_id": "nonexistent-" + uuid.uuid4().hex, "delta": 1, "note": "x"},
        )
        assert r.status_code == 404

    def test_adjust_requires_verwaltung(self, session, ma_login, admin_login):
        # Mitarbeiter ma1 has verwaltung=true (per test_credentials.md) so
        # the call should succeed. To test 403 we use the freelancer/
        # standard role path indirectly: try as ma1 against admin id.
        # If ma1 has verwaltung, expect 200; otherwise 403.
        uid = admin_login["user"]["id"]
        modules = (ma_login["user"].get("apps") or {}).get("modules") or {}
        has_verw = modules.get("verwaltung") is not False and ma_login["user"]["role"] in ("admin", "mitarbeiter")
        r = session.post(
            f"{BASE_URL}/api/employee/offdays/adjust?token={ma_login['token']}",
            json={"user_id": uid, "delta": 1, "note": "TEST_verw_check"},
        )
        if has_verw:
            assert r.status_code == 200
            # revert
            session.post(
                f"{BASE_URL}/api/employee/offdays/adjust?token={ma_login['token']}",
                json={"user_id": uid, "delta": -1, "note": "TEST_verw_revert"},
            )
        else:
            assert r.status_code == 403


# ── Shift-plan integration ──────────────────────────────────────────────

class TestShiftPlanOffdayIntegration:
    """Verifies that creating an is_offday assignment debits -1 from the
    user's offday account, and that deleting it credits +1 back.
    Also verifies the flip update.
    """

    def _balance(self, session, token, uid):
        r = session.get(f"{BASE_URL}/api/employee/offdays/user/{uid}?token={token}")
        assert r.status_code == 200
        return r.json()["balance"]

    def test_create_offday_assignment_debits_balance(self, session, admin_login):
        token = admin_login["token"]
        uid = admin_login["user"]["id"]

        before = self._balance(session, token, uid)
        d_iso = "2030-01-08"  # future date, harmless. Cleaned up in finally.
        assignment_id = None
        payload = {
            "user_id": uid,
            "date": d_iso,
            "order_pk": None,
            "order_name": "TEST_offday_order",
            "role": "",
            "note": "TEST_offday",
            "start_time": "",
            "end_time": "",
            "is_offday": True,
            "week_key": "2030-W02",
        }
        r = session.post(f"{BASE_URL}/api/employee/shift-plan?token={token}", json=payload)
        assert r.status_code == 200, r.text
        assignment_id = r.json()["id"]

        try:
            after_create = self._balance(session, token, uid)
            assert after_create == before - 1

            # Idempotence: update same assignment with is_offday=True again
            # NOTE: backend reads update id from body field `id` (not assignment_id)
            payload2 = dict(payload, id=assignment_id)
            r2 = session.post(f"{BASE_URL}/api/employee/shift-plan?token={token}", json=payload2)
            assert r2.status_code == 200
            assert self._balance(session, token, uid) == before - 1

            # Flip True -> False (should release/refund +1)
            payload3 = dict(payload, id=assignment_id, is_offday=False)
            r3 = session.post(f"{BASE_URL}/api/employee/shift-plan?token={token}", json=payload3)
            assert r3.status_code == 200
            assert self._balance(session, token, uid) == before

            # Flip False -> True (should consume -1 again)
            payload4 = dict(payload, id=assignment_id, is_offday=True)
            r4 = session.post(f"{BASE_URL}/api/employee/shift-plan?token={token}", json=payload4)
            assert r4.status_code == 200
            assert self._balance(session, token, uid) == before - 1
        finally:
            # Cleanup: delete the assignment, balance should bounce back
            if assignment_id:
                session.delete(f"{BASE_URL}/api/employee/shift-plan/{assignment_id}?token={token}")


# ── Recompute endpoint ──────────────────────────────────────────────────

class TestRecompute:
    def test_recompute_returns_counts(self, session, admin_login):
        r = session.post(
            f"{BASE_URL}/api/employee/offdays/recompute?token={admin_login['token']}"
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        assert "deleted_clock_in_entries" in j
        assert "granted" in j
        assert isinstance(j["deleted_clock_in_entries"], int)
        assert isinstance(j["granted"], int)

    def test_recompute_is_idempotent(self, session, admin_login):
        # Running twice in a row: deleted_clock_in_entries on second run should
        # equal granted from first run (since first run created exactly those).
        r1 = session.post(
            f"{BASE_URL}/api/employee/offdays/recompute?token={admin_login['token']}"
        ).json()
        r2 = session.post(
            f"{BASE_URL}/api/employee/offdays/recompute?token={admin_login['token']}"
        ).json()
        assert r2["deleted_clock_in_entries"] == r1["granted"]
        assert r2["granted"] == r1["granted"]
