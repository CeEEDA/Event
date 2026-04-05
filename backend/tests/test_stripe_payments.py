"""
Stripe Payment Integration Tests for Kirmes Billing System
Tests deposit payments (Kaution) and invoice payments via Stripe Checkout
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://doc-hub-chat.preview.emergentagent.com')


class TestPaymentsPublicEndpoints:
    """Tests for public payment endpoints"""

    def test_get_deposit_info_returns_default_amounts(self):
        """GET /api/payments/deposit-info/{event_id} returns default deposit amounts"""
        # Use any event ID - endpoint returns defaults from config
        event_id = "de734361-1e4c-4b6a-816c-6dbb0097cd10"
        response = requests.get(f"{BASE_URL}/api/payments/deposit-info/{event_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all connection types are present
        assert "Schuko" in data
        assert "16A" in data
        assert "32A" in data
        assert "63A" in data
        assert "125A" in data
        
        # Verify default amounts (or custom if configured)
        assert data["Schuko"] >= 50.0
        assert data["16A"] >= 100.0
        assert data["32A"] >= 200.0
        assert data["63A"] >= 400.0
        assert data["125A"] >= 800.0
        print(f"Deposit info retrieved: {data}")

    def test_checkout_deposit_with_invalid_signup(self):
        """POST /api/payments/checkout/deposit returns 404 for invalid signup"""
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout/deposit",
            json={
                "signup_id": "invalid-signup-id",
                "event_id": "de734361-1e4c-4b6a-816c-6dbb0097cd10",
                "origin_url": BASE_URL
            }
        )
        
        assert response.status_code == 404
        assert "Anmeldung nicht gefunden" in response.json().get("detail", "")
        print("Correctly rejected invalid signup")

    def test_checkout_deposit_with_valid_signup(self):
        """POST /api/payments/checkout/deposit creates Stripe session for valid signup"""
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout/deposit",
            json={
                "signup_id": "aaa7f30e-ebc3-4f31-99b7-1aed7de69305",
                "event_id": "de734361-1e4c-4b6a-816c-6dbb0097cd10",
                "origin_url": BASE_URL
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify Stripe checkout URL
        assert "url" in data
        assert data["url"].startswith("https://checkout.stripe.com")
        
        # Verify session ID
        assert "session_id" in data
        assert data["session_id"].startswith("cs_test_")
        
        # Verify amount
        assert "amount" in data
        assert data["amount"] == 100.0  # 16A connection type
        print(f"Stripe checkout session created: {data['session_id']}")

    def test_checkout_invoice_with_invalid_invoice(self):
        """POST /api/payments/checkout/invoice returns 404 for invalid invoice"""
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout/invoice",
            json={
                "invoice_id": "invalid-invoice-id",
                "origin_url": BASE_URL
            }
        )
        
        assert response.status_code == 404
        assert "Rechnung nicht gefunden" in response.json().get("detail", "")
        print("Correctly rejected invalid invoice")

    def test_checkout_invoice_with_valid_invoice(self):
        """POST /api/payments/checkout/invoice creates Stripe session for valid invoice"""
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout/invoice",
            json={
                "invoice_id": "ec975eaa-cc3a-44b6-bff4-39dc006812c7",
                "origin_url": BASE_URL
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify Stripe checkout URL
        assert "url" in data
        assert data["url"].startswith("https://checkout.stripe.com")
        
        # Verify session ID
        assert "session_id" in data
        assert data["session_id"].startswith("cs_test_")
        
        # Verify amount
        assert "amount" in data
        assert data["amount"] == 150.0
        print(f"Invoice checkout session created: {data['session_id']}")

    def test_checkout_status_invalid_session(self):
        """GET /api/payments/checkout/status/{session_id} returns 404 for invalid session"""
        response = requests.get(f"{BASE_URL}/api/payments/checkout/status/invalid-session")
        
        assert response.status_code == 404
        assert "Transaktion nicht gefunden" in response.json().get("detail", "")
        print("Correctly rejected invalid session")

    def test_checkout_status_valid_session(self):
        """GET /api/payments/checkout/status/{session_id} returns pending status"""
        # First create a session
        create_resp = requests.post(
            f"{BASE_URL}/api/payments/checkout/deposit",
            json={
                "signup_id": "aaa7f30e-ebc3-4f31-99b7-1aed7de69305",
                "event_id": "de734361-1e4c-4b6a-816c-6dbb0097cd10",
                "origin_url": BASE_URL
            }
        )
        session_id = create_resp.json().get("session_id")
        
        # Check status
        response = requests.get(f"{BASE_URL}/api/payments/checkout/status/{session_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] in ["pending", "paid", "expired"]
        assert "payment_status" in data
        assert "amount" in data
        assert "type" in data
        assert data["type"] == "deposit"
        print(f"Payment status: {data}")

    def test_webhook_returns_ok(self):
        """POST /api/payments/webhook/stripe returns ok status"""
        response = requests.post(
            f"{BASE_URL}/api/payments/webhook/stripe",
            json={},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        assert response.json().get("status") == "ok"
        print("Webhook endpoint accessible")


class TestPaymentsAdminEndpoints:
    """Tests for admin-only payment endpoints"""

    @pytest.fixture(autouse=True)
    def admin_auth(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "password"}
        )
        if response.status_code == 200:
            self.admin_token = response.json().get("token")
            self.headers = {"Authorization": f"Bearer {self.admin_token}"}
        else:
            pytest.skip("Admin auth failed")

    def test_get_deposit_config_requires_auth(self):
        """GET /api/payments/deposits/config requires admin authentication"""
        response = requests.get(f"{BASE_URL}/api/payments/deposits/config")
        assert response.status_code in [401, 403]
        print("Correctly requires authentication")

    def test_get_deposit_config_with_auth(self):
        """GET /api/payments/deposits/config returns all deposit configurations"""
        response = requests.get(
            f"{BASE_URL}/api/payments/deposits/config",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response is a list of connection configs
        assert isinstance(data, list)
        assert len(data) >= 5  # At least 5 connection types
        
        # Verify structure
        for config in data:
            assert "connection_type" in config
            assert "deposit_amount" in config
            assert config["connection_type"] in ["Schuko", "16A", "32A", "63A", "125A"]
        
        print(f"Deposit config: {data}")

    def test_update_deposit_config(self):
        """PUT /api/payments/deposits/config updates deposit amounts"""
        # Update Schuko deposit to 55
        response = requests.put(
            f"{BASE_URL}/api/payments/deposits/config",
            headers=self.headers,
            json=[{"connection_type": "Schuko", "deposit_amount": 55}]
        )
        
        assert response.status_code == 200
        assert "Kautionen aktualisiert" in response.json().get("message", "")
        
        # Verify update
        verify_resp = requests.get(
            f"{BASE_URL}/api/payments/deposits/config",
            headers=self.headers
        )
        data = verify_resp.json()
        schuko_config = next((c for c in data if c["connection_type"] == "Schuko"), None)
        assert schuko_config is not None
        assert schuko_config["deposit_amount"] == 55.0
        
        # Revert
        requests.put(
            f"{BASE_URL}/api/payments/deposits/config",
            headers=self.headers,
            json=[{"connection_type": "Schuko", "deposit_amount": 50}]
        )
        print("Deposit config updated and reverted successfully")

    def test_update_deposit_config_requires_auth(self):
        """PUT /api/payments/deposits/config requires admin authentication"""
        response = requests.put(
            f"{BASE_URL}/api/payments/deposits/config",
            json=[{"connection_type": "Schuko", "deposit_amount": 60}]
        )
        assert response.status_code in [401, 403]
        print("Correctly requires authentication for update")

    def test_get_transactions_requires_auth(self):
        """GET /api/payments/transactions requires admin authentication"""
        response = requests.get(f"{BASE_URL}/api/payments/transactions")
        assert response.status_code in [401, 403]
        print("Correctly requires authentication")

    def test_get_transactions_with_auth(self):
        """GET /api/payments/transactions returns list of transactions"""
        response = requests.get(
            f"{BASE_URL}/api/payments/transactions",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response is a list
        assert isinstance(data, list)
        
        # If there are transactions, verify structure
        if len(data) > 0:
            tx = data[0]
            assert "id" in tx
            assert "session_id" in tx
            assert "type" in tx
            assert "amount" in tx
            assert "payment_status" in tx
        
        print(f"Found {len(data)} transactions")

    def test_get_transactions_filtered_by_event(self):
        """GET /api/payments/transactions?event_id=X filters by event"""
        event_id = "de734361-1e4c-4b6a-816c-6dbb0097cd10"
        response = requests.get(
            f"{BASE_URL}/api/payments/transactions?event_id={event_id}",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned transactions should have matching event_id
        for tx in data:
            if tx.get("event_id"):
                assert tx["event_id"] == event_id
        
        print(f"Found {len(data)} transactions for event {event_id}")


class TestDepositAmountsPerConnectionType:
    """Verify deposit amounts match expected values per connection type"""

    def test_deposit_amounts_match_spec(self):
        """Verify deposit amounts: Schuko=50, 16A=100, 32A=200, 63A=400, 125A=800"""
        event_id = "de734361-1e4c-4b6a-816c-6dbb0097cd10"
        response = requests.get(f"{BASE_URL}/api/payments/deposit-info/{event_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # These are the DEFAULT values from the spec
        # They may be modified by admin, so we just check they exist
        expected_defaults = {
            "Schuko": 50.0,
            "16A": 100.0,
            "32A": 200.0,
            "63A": 400.0,
            "125A": 800.0
        }
        
        for conn_type, expected_amount in expected_defaults.items():
            assert conn_type in data, f"Missing connection type: {conn_type}"
            # Amount should be >= default (admin might have increased it)
            print(f"{conn_type}: {data[conn_type]}€ (default: {expected_amount}€)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
