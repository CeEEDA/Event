"""
Backend tests for the Lieferschein (Delivery Note) prefill endpoint.

Verifies BUG 3 fix: prefill returns amount = amount_total (full quantity)
instead of remaining quantity. Also checks all required fields are present
in each non-heading item (primary_key, amount, amount_total,
amount_delivered, amount_remaining, weight_net).

NOTE: This hits the LIVE EpiRent integration, which can take 60-120 seconds
per request. We therefore run against http://localhost:8001 directly to
bypass the preview ingress 60s timeout.
"""
import os
import pytest
import requests

# Direct backend URL - EpiRent prefill exceeds preview ingress 60s timeout
BACKEND_URL = "http://localhost:8001"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"

PREFILL_TIMEOUT = 180  # seconds


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(
        f"{BACKEND_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("token")
    assert token and len(token) > 20
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ---- Prefill endpoint ----

class TestDeliveryNotePrefill:
    """GET /api/orders/epirent/{order_pk}/delivery-notes/prefill"""

    def test_prefill_order_12_returns_200(self, auth_headers):
        r = requests.get(
            f"{BACKEND_URL}/api/orders/epirent/12/delivery-notes/prefill",
            headers=auth_headers,
            timeout=PREFILL_TIMEOUT,
        )
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
        data = r.json()
        # top-level shape
        assert data.get("order_no_fmt") == "251008-01"
        assert "groups" in data and isinstance(data["groups"], list)
        assert "delivery_address" in data
        assert "suggested_delivery_note_no" in data

    def test_prefill_order_128_returns_200(self, auth_headers):
        r = requests.get(
            f"{BACKEND_URL}/api/orders/epirent/128/delivery-notes/prefill",
            headers=auth_headers,
            timeout=PREFILL_TIMEOUT,
        )
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert data.get("order_no_fmt") == "260095-01"
        assert isinstance(data.get("groups"), list)

    def test_prefill_unauthorized_without_token(self):
        r = requests.get(
            f"{BACKEND_URL}/api/orders/epirent/12/delivery-notes/prefill",
            timeout=30,
        )
        # FastAPI w/ HTTPBearer returns 403 when missing, 401 when invalid
        assert r.status_code in (401, 403), f"got {r.status_code}"

    def test_prefill_item_required_fields(self, auth_headers):
        """BUG 3: every non-heading item must contain amount, amount_total,
        amount_delivered, amount_remaining, primary_key, weight_net."""
        r = requests.get(
            f"{BACKEND_URL}/api/orders/epirent/12/delivery-notes/prefill",
            headers=auth_headers,
            timeout=PREFILL_TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        required = {
            "primary_key",
            "amount",
            "amount_total",
            "amount_delivered",
            "amount_remaining",
            "weight_net",
        }
        non_heading_items = []
        for g in data.get("groups", []):
            for it in g.get("items", []):
                if not it.get("is_heading"):
                    non_heading_items.append(it)

        # If EpiRent returns zero concrete articles we cannot make claim.
        # Skip in that case so this test stays meaningful for both orders.
        if not non_heading_items:
            pytest.skip("EpiRent returned no non-heading articles for order 12")

        for it in non_heading_items:
            missing = required - set(it.keys())
            assert not missing, f"item '{it.get('title')}' missing fields: {missing}"

    def test_prefill_amount_equals_amount_total_bug3(self, auth_headers):
        """BUG 3 fix: 'amount' must equal 'amount_total' (full qty), NOT
        the remaining qty. This is what populates the Menge input on the
        UI side on a fresh prefill."""
        r = requests.get(
            f"{BACKEND_URL}/api/orders/epirent/12/delivery-notes/prefill",
            headers=auth_headers,
            timeout=PREFILL_TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()

        mismatches = []
        checked = 0
        for g in data.get("groups", []):
            for it in g.get("items", []):
                if it.get("is_heading"):
                    continue
                checked += 1
                amt = float(it.get("amount") or 0)
                tot = float(it.get("amount_total") or 0)
                if abs(amt - tot) > 1e-6:
                    mismatches.append(
                        {
                            "title": it.get("title"),
                            "amount": amt,
                            "amount_total": tot,
                            "amount_delivered": it.get("amount_delivered"),
                            "amount_remaining": it.get("amount_remaining"),
                        }
                    )
        if checked == 0:
            pytest.skip("No non-heading articles in EpiRent response")

        assert not mismatches, (
            f"BUG 3 regression: amount != amount_total for {len(mismatches)}"
            f" items: {mismatches[:3]}"
        )

    def test_prefill_amount_remaining_derivation(self, auth_headers):
        """amount_remaining == max(0, amount_total - amount_delivered)"""
        r = requests.get(
            f"{BACKEND_URL}/api/orders/epirent/12/delivery-notes/prefill",
            headers=auth_headers,
            timeout=PREFILL_TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        checked = 0
        for g in data.get("groups", []):
            for it in g.get("items", []):
                if it.get("is_heading"):
                    continue
                checked += 1
                expected = max(
                    0.0,
                    float(it.get("amount_total") or 0) - float(it.get("amount_delivered") or 0),
                )
                got = float(it.get("amount_remaining") or 0)
                assert abs(got - expected) < 1e-6, (
                    f"amount_remaining wrong for {it.get('title')}: "
                    f"got {got}, expected {expected}"
                )
        if checked == 0:
            pytest.skip("No non-heading articles to validate")
