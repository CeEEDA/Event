"""
Test Payment Dashboard APIs for Kirmes Billing System (Iteration 36)

Tests cover:
- GET /api/payments/dashboard - Aggregated payment stats
- GET /api/payments/dashboard?event_id={id} - Filtered stats by event
- GET /api/payments/dashboard/events - Events with payment summary
- POST /api/payments/send-payment-link - Send payment link (requires signup_id or invoice_id)
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"


class TestPaymentDashboardEndpoints:
    """Tests for the new payment dashboard endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and get token"""
        assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_dashboard_returns_aggregated_stats(self):
        """GET /api/payments/dashboard returns deposits/invoices paid/pending with amounts"""
        response = requests.get(
            f"{BASE_URL}/api/payments/dashboard",
            headers=self.headers
        )
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        data = response.json()

        # Verify structure
        assert "deposits" in data, "Missing deposits in dashboard response"
        assert "invoices" in data, "Missing invoices in dashboard response"
        assert "recent_transactions" in data, "Missing recent_transactions in dashboard response"

        # Verify deposits structure
        deposits = data["deposits"]
        assert "total" in deposits, "Missing total in deposits"
        assert "paid" in deposits, "Missing paid in deposits"
        assert "pending" in deposits, "Missing pending in deposits"
        assert "total_amount" in deposits, "Missing total_amount in deposits"
        assert "paid_amount" in deposits, "Missing paid_amount in deposits"
        assert "pending_amount" in deposits, "Missing pending_amount in deposits"

        # Verify invoices structure
        invoices = data["invoices"]
        assert "total" in invoices, "Missing total in invoices"
        assert "paid" in invoices, "Missing paid in invoices"
        assert "pending" in invoices, "Missing pending in invoices"
        assert "total_amount" in invoices, "Missing total_amount in invoices"
        assert "paid_amount" in invoices, "Missing paid_amount in invoices"
        assert "pending_amount" in invoices, "Missing pending_amount in invoices"

        # Verify amounts are numeric
        assert isinstance(deposits["total_amount"], (int, float))
        assert isinstance(invoices["total_amount"], (int, float))

        print(f"Dashboard stats: Deposits total={deposits['total']}, pending={deposits['pending']}")
        print(f"Dashboard stats: Invoices total={invoices['total']}, pending={invoices['pending']}")

    def test_dashboard_filtered_by_event_id(self):
        """GET /api/payments/dashboard?event_id={id} returns filtered stats"""
        # First get events to find one with transactions
        events_resp = requests.get(
            f"{BASE_URL}/api/payments/dashboard/events",
            headers=self.headers
        )
        assert events_resp.status_code == 200
        events = events_resp.json()

        if not events:
            pytest.skip("No events available for filtering test")

        # Find an event with transactions
        event_with_txs = None
        for event in events:
            if event.get("deposits_pending", 0) > 0 or event.get("invoices_pending", 0) > 0:
                event_with_txs = event
                break

        if not event_with_txs:
            event_with_txs = events[0]

        event_id = event_with_txs["id"]

        # Test filtered dashboard
        response = requests.get(
            f"{BASE_URL}/api/payments/dashboard?event_id={event_id}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Filtered dashboard failed: {response.text}"
        data = response.json()

        assert "deposits" in data
        assert "invoices" in data
        assert "recent_transactions" in data

        # Verify transactions are filtered to this event
        for tx in data["recent_transactions"]:
            if tx.get("event_id"):
                assert tx["event_id"] == event_id, f"Transaction event_id mismatch: expected {event_id}, got {tx['event_id']}"

        print(f"Filtered dashboard for event {event_id}: {data['deposits']['total']} deposits, {data['invoices']['total']} invoices")

    def test_dashboard_events_returns_events_with_summary(self):
        """GET /api/payments/dashboard/events returns events with payment summary counts"""
        response = requests.get(
            f"{BASE_URL}/api/payments/dashboard/events",
            headers=self.headers
        )
        assert response.status_code == 200, f"Events endpoint failed: {response.text}"
        events = response.json()

        assert isinstance(events, list), "Events response should be a list"

        if events:
            event = events[0]
            # Verify each event has payment summary fields
            assert "id" in event, "Missing id in event"
            assert "name" in event, "Missing name in event"
            assert "deposits_paid" in event, "Missing deposits_paid in event"
            assert "deposits_pending" in event, "Missing deposits_pending in event"
            assert "invoices_paid" in event, "Missing invoices_paid in event"
            assert "invoices_pending" in event, "Missing invoices_pending in event"
            assert "total_received" in event, "Missing total_received in event"

            # Verify numeric types
            assert isinstance(event["deposits_paid"], int)
            assert isinstance(event["deposits_pending"], int)
            assert isinstance(event["total_received"], (int, float))

            print(f"Event '{event['name']}': {event['deposits_paid']} deposits paid, {event['deposits_pending']} pending")

    def test_dashboard_requires_authentication(self):
        """GET /api/payments/dashboard requires authentication"""
        response = requests.get(f"{BASE_URL}/api/payments/dashboard")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"

    def test_dashboard_events_requires_authentication(self):
        """GET /api/payments/dashboard/events requires authentication"""
        response = requests.get(f"{BASE_URL}/api/payments/dashboard/events")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"


class TestSendPaymentLinkEndpoint:
    """Tests for POST /api/payments/send-payment-link"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and get token"""
        assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_send_payment_link_requires_signup_or_invoice_id(self):
        """POST /api/payments/send-payment-link requires signup_id or invoice_id"""
        response = requests.post(
            f"{BASE_URL}/api/payments/send-payment-link",
            headers=self.headers,
            json={"origin_url": "https://example.com"}
        )
        # Should return 400 because neither signup_id nor invoice_id provided
        assert response.status_code == 400, f"Expected 400 without IDs, got {response.status_code}: {response.text}"

    def test_send_payment_link_invalid_signup_id(self):
        """POST /api/payments/send-payment-link returns 404 for invalid signup_id"""
        response = requests.post(
            f"{BASE_URL}/api/payments/send-payment-link",
            headers=self.headers,
            json={
                "signup_id": "nonexistent-signup-id",
                "origin_url": "https://example.com"
            }
        )
        assert response.status_code == 404, f"Expected 404 for invalid signup, got {response.status_code}: {response.text}"

    def test_send_payment_link_invalid_invoice_id(self):
        """POST /api/payments/send-payment-link returns 404 for invalid invoice_id"""
        response = requests.post(
            f"{BASE_URL}/api/payments/send-payment-link",
            headers=self.headers,
            json={
                "invoice_id": "nonexistent-invoice-id",
                "origin_url": "https://example.com"
            }
        )
        assert response.status_code == 404, f"Expected 404 for invalid invoice, got {response.status_code}: {response.text}"

    def test_send_payment_link_requires_authentication(self):
        """POST /api/payments/send-payment-link requires admin authentication"""
        response = requests.post(
            f"{BASE_URL}/api/payments/send-payment-link",
            json={
                "signup_id": "test",
                "origin_url": "https://example.com"
            }
        )
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"

    def test_send_payment_link_with_valid_signup(self):
        """POST /api/payments/send-payment-link creates Stripe session for valid signup"""
        # Get events to find one with signups
        events_resp = requests.get(
            f"{BASE_URL}/api/kirmes/events",
            headers=self.headers
        )
        if events_resp.status_code != 200:
            pytest.skip("Could not get events")

        events = events_resp.json()
        signup_id = None

        # Find a signup
        for event in events:
            event_detail = requests.get(
                f"{BASE_URL}/api/kirmes/events/{event['id']}",
                headers=self.headers
            )
            if event_detail.status_code == 200:
                detail = event_detail.json()
                if detail.get("signups") and len(detail["signups"]) > 0:
                    signup_id = detail["signups"][0]["id"]
                    break

        if not signup_id:
            pytest.skip("No signups available for testing")

        response = requests.post(
            f"{BASE_URL}/api/payments/send-payment-link",
            headers=self.headers,
            json={
                "signup_id": signup_id,
                "origin_url": "https://kirmeskiste-fix.preview.emergentagent.com"
            },
            timeout=30
        )

        # May succeed or fail based on Schausteller email, but should not be 500
        assert response.status_code != 500, f"Server error: {response.text}"

        if response.status_code == 200:
            data = response.json()
            assert "url" in data or "message" in data, "Response should contain url or message"
            print(f"Send payment link response: {data}")


class TestDashboardNonAdminAccess:
    """Test that non-admin users cannot access dashboard endpoints"""

    def test_dashboard_requires_admin_role(self):
        """Non-admin users should be denied access to dashboard"""
        # First create or login as a non-admin user
        # Using a schausteller login if available
        response = requests.post(
            f"{BASE_URL}/api/kirmes/schausteller-auth/login",
            json={"email": "test_stripe@test.de", "password": "testpass123"}
        )

        if response.status_code != 200:
            pytest.skip("No non-admin user available for testing")

        token = response.json().get("token")
        if not token:
            pytest.skip("Could not get non-admin token")

        headers = {"Authorization": f"Bearer {token}"}

        # Try to access dashboard
        dash_response = requests.get(
            f"{BASE_URL}/api/payments/dashboard",
            headers=headers
        )

        # Should be 403 Forbidden
        assert dash_response.status_code == 403, f"Expected 403 for non-admin, got {dash_response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
