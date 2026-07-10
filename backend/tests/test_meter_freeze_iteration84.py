"""Backend tests for iteration 84: Meter-Freeze + Invoice Payment-Link.

Covers three features requested by the main agent:
  1. POST /api/kirmes/events/{event_id}/freeze-meters
     * auth guard (401/403 without token)
     * 404 for unknown event
     * happy path: unlinks emu_* fields, sets kwh_ausbau / meter_end /
       kwh_used and event.meters_frozen_at
     * idempotency: 2nd call returns already-frozen message
  2. POST /api/kirmes/invoices/{invoice_id}/send
     * auth guard
     * even if SMTP delivery fails, payment_link_url and
       payment_link_session_id must be persisted on the invoice document
       and a payment_transactions row (type='invoice', status='pending')
       is inserted BEFORE the mail step
  3. GET /rechnung/bezahlt & /rechnung/abgebrochen are public frontend
     routes (no auth redirect)  - verified via HTTP status only.

Run:
  pytest /app/backend/tests/test_meter_freeze_iteration84.py -v \
      --tb=short --junitxml=/app/test_reports/pytest/iteration_84_meter_freeze.xml
"""

import os
import uuid
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fuel-truck-deploy.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"

TEST_PREFIX = "TEST_it84_"


# ---------------- fixtures ----------------

@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------------- seed helpers ----------------

def _seed_event_with_linked_signup(db, with_meter_reading=True):
    """Create a Kirmes event with an emu meter reading + a signup linked to it."""
    event_id = f"{TEST_PREFIX}evt_{uuid.uuid4()}"
    signup_id = f"{TEST_PREFIX}sup_{uuid.uuid4()}"
    device_id = f"{TEST_PREFIX}dev_{uuid.uuid4().hex[:8]}"
    meter_id = "M1"
    now = datetime.now(timezone.utc)
    yesterday_iso = (now - timedelta(days=1)).date().isoformat()

    db.kirmes_events.insert_one({
        "id": event_id,
        "name": f"{TEST_PREFIX}Testkirmes",
        "location": "Testort",
        "start_date": (now - timedelta(days=5)).date().isoformat(),
        "end_date": yesterday_iso,
        "status": "active",
        "kwh_price": 0.55,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    })

    db.kirmes_signups.insert_one({
        "id": signup_id,
        "event_id": event_id,
        "schausteller_id": f"{TEST_PREFIX}sch",
        "platznummer": "12",
        "fahrgeschaeft": "Autoscooter",
        "connection_type": "63A",
        "price": 220.0,
        "payment_method": "auf_rechnung",
        "payment_status": None,
        "emu_device_id": device_id,
        "emu_meter_id": meter_id,
        "emu_meter_name": "Zaehler 12",
        "kwh_einbau": 100.0,
        "meter_start": 100.0,
        "created_at": now.isoformat(),
    })

    if with_meter_reading:
        db.emu_data.insert_one({
            "device_id": device_id,
            "meter_id": meter_id,
            "E_imp_kWh": 175.5,
            "ts_utc": now.isoformat(),
        })

    return event_id, signup_id, device_id, meter_id


def _cleanup(db, event_id):
    """Remove all TEST_it84_ data for a given event."""
    signups = list(db.kirmes_signups.find({"event_id": event_id}, {"_id": 0, "emu_device_id": 1, "meter_final_device_id": 1}))
    device_ids = {s.get("emu_device_id") or s.get("meter_final_device_id") for s in signups}
    device_ids.discard(None)
    db.kirmes_events.delete_many({"id": event_id})
    db.kirmes_signups.delete_many({"event_id": event_id})
    for dev in device_ids:
        db.emu_data.delete_many({"device_id": dev})


# ---------------- 1. Meter Freeze ----------------

class TestMeterFreeze:

    def test_freeze_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/kirmes/events/nonexistent/freeze-meters", timeout=10)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code} {r.text}"

    def test_freeze_404_for_unknown_event(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/kirmes/events/does-not-exist-xyz/freeze-meters",
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 404
        assert "nicht gefunden" in r.json().get("detail", "").lower()

    def test_freeze_happy_path_and_idempotent(self, db, auth_headers):
        event_id, signup_id, device_id, meter_id = _seed_event_with_linked_signup(db, with_meter_reading=True)
        try:
            # sanity: signup starts with the meter linked
            pre = db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
            assert pre["emu_device_id"] == device_id
            assert pre["emu_meter_id"] == meter_id

            # 1st call: should freeze 1 meter
            r = requests.post(
                f"{BASE_URL}/api/kirmes/events/{event_id}/freeze-meters",
                headers=auth_headers,
                timeout=30,
            )
            assert r.status_code == 200, f"freeze failed: {r.status_code} {r.text}"
            body = r.json()
            assert body.get("frozen") == 1, f"expected 1 frozen, got {body}"
            assert "eingefroren" in body.get("message", "").lower()

            # verify signup: meter unlinked, readings frozen
            post = db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
            assert "emu_device_id" not in post, f"emu_device_id still present: {post}"
            assert "emu_meter_id" not in post
            assert "emu_meter_name" not in post
            assert post.get("kwh_ausbau") == 175.5
            assert post.get("meter_end") == 175.5
            # kwh_einbau was 100.0 -> kwh_used = 75.5
            assert post.get("kwh_used") == 75.5
            assert post.get("meter_final_device_id") == device_id
            assert post.get("meter_final_meter_id") == meter_id
            assert post.get("meter_frozen_at")

            # verify event marked frozen
            evt = db.kirmes_events.find_one({"id": event_id}, {"_id": 0})
            assert evt.get("meters_frozen_at")
            assert evt.get("meters_frozen_count") == 1

            # 2nd call: idempotent -> already frozen
            r2 = requests.post(
                f"{BASE_URL}/api/kirmes/events/{event_id}/freeze-meters",
                headers=auth_headers,
                timeout=15,
            )
            assert r2.status_code == 200
            body2 = r2.json()
            assert body2.get("frozen") == 0
            assert "bereits" in body2.get("message", "").lower()
        finally:
            _cleanup(db, event_id)

    def test_freeze_without_reading_still_unlinks(self, db, auth_headers):
        """If emu_data has no telemetry yet, unlinking must still happen; kwh_ausbau omitted."""
        event_id, signup_id, device_id, meter_id = _seed_event_with_linked_signup(db, with_meter_reading=False)
        try:
            r = requests.post(
                f"{BASE_URL}/api/kirmes/events/{event_id}/freeze-meters",
                headers=auth_headers,
                timeout=30,
            )
            assert r.status_code == 200
            body = r.json()
            assert body.get("frozen") == 1

            post = db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
            assert "emu_device_id" not in post
            assert "emu_meter_id" not in post
            # No reading => kwh_ausbau should not have been overwritten with garbage
            assert "kwh_ausbau" not in post or post.get("kwh_ausbau") is None
            assert post.get("meter_frozen_at")
        finally:
            _cleanup(db, event_id)


# ---------------- 2. Invoice Payment Link ----------------

class TestInvoicePaymentLink:

    def test_send_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/kirmes/invoices/does-not-exist/send", timeout=10)
        assert r.status_code in (401, 403)

    def test_send_404_for_unknown_invoice(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/kirmes/invoices/does-not-exist-xyz/send",
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 404

    def test_send_creates_payment_link_even_if_smtp_fails(self, db, auth_headers):
        """Pick an invoice with an open balance, call /send, then verify the
        payment_link_url + payment_transactions row exist BEFORE SMTP fails."""
        inv = db.kirmes_invoices.find_one(
            {
                "$and": [
                    {"$or": [{"payment_status": {"$ne": "bezahlt"}}, {"payment_status": None}]},
                    {"brutto": {"$gte": 1.0}},
                ]
            },
            {"_id": 0},
        )
        if not inv:
            pytest.skip("No open-balance invoice available for testing")

        # ensure invoice has an email address (required by endpoint before SMTP call)
        sch = inv.get("schausteller") or {}
        rechnungs_email = sch.get("rechnungs_email") or inv.get("schausteller_email")
        if not rechnungs_email:
            pytest.skip(f"Invoice {inv['invoice_number']} has no email")

        # Clear any pre-existing payment_link so we can check it gets set now
        db.kirmes_invoices.update_one(
            {"id": inv["id"]},
            {"$unset": {"payment_link_url": "", "payment_link_session_id": "", "payment_link_amount": "", "payment_link_created_at": ""}},
        )
        # Remove existing test payment_transactions for this invoice for a clean check
        db.payment_transactions.delete_many({"invoice_id": inv["id"], "type": "invoice"})

        r = requests.post(
            f"{BASE_URL}/api/kirmes/invoices/{inv['id']}/send",
            headers=auth_headers,
            timeout=45,
        )
        # SMTP will likely fail (500) or succeed (200) - both are OK.
        # The critical assertion is that the payment_link was persisted regardless.
        print(f"[/send] status={r.status_code} body={r.text[:400]}")

        # Give backend a moment for async writes
        time.sleep(1)

        updated = db.kirmes_invoices.find_one({"id": inv["id"]}, {"_id": 0})
        assert updated.get("payment_link_url"), f"payment_link_url NOT saved after /send call (status={r.status_code}): {updated.get('payment_link_url')} | payment_link_error={updated.get('payment_link_error')}"
        assert updated.get("payment_link_session_id"), "payment_link_session_id missing"
        assert updated["payment_link_url"].startswith("https://"), f"unexpected url: {updated['payment_link_url']}"
        # payment_link_created_at must be set
        assert updated.get("payment_link_created_at"), "payment_link_created_at missing"
        # payment_link_amount should match the open balance
        expected_amount = round(float(inv["brutto"]) - float(inv.get("deposit_applied") or 0), 2)
        assert updated.get("payment_link_amount") == expected_amount, (
            f"payment_link_amount={updated.get('payment_link_amount')} != expected {expected_amount}"
        )
        # payment_link_error must NOT be set on success
        assert not updated.get("payment_link_error"), (
            f"payment_link_error should be absent on success, got: {updated.get('payment_link_error')}"
        )

        # Verify payment_transactions row created with correct fields
        tx = db.payment_transactions.find_one({"invoice_id": inv["id"], "type": "invoice"}, {"_id": 0})
        assert tx is not None, "payment_transactions row not created"
        assert tx.get("payment_status") == "pending"
        assert tx.get("session_id") == updated["payment_link_session_id"]
        assert tx.get("type") == "invoice"
        assert tx.get("amount") == expected_amount


# ---------------- 3. Public frontend routes (light check via HTTP) ----------------

class TestPublicPaymentRoutes:
    """Frontend routes should serve the SPA HTML (200) - never redirect to /login."""

    def test_rechnung_bezahlt_public(self):
        r = requests.get(
            f"{BASE_URL}/rechnung/bezahlt?session_id=test123",
            timeout=15,
            allow_redirects=False,
        )
        # SPA returns the same index.html for all routes -> 200 or 304
        assert r.status_code in (200, 304), f"unexpected status {r.status_code}"
        # And must NOT redirect (would indicate an auth-guard misconfig)
        assert not (300 <= r.status_code < 400)

    def test_rechnung_abgebrochen_public(self):
        r = requests.get(
            f"{BASE_URL}/rechnung/abgebrochen",
            timeout=15,
            allow_redirects=False,
        )
        assert r.status_code in (200, 304)
        assert not (300 <= r.status_code < 400)
