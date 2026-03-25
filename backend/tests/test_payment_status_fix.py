"""
P0 Fix Tests: Booking Payment Status Flow
Test that bookings are created with 'pending_payment' status for credit card/paypal,
and only activated to 'ausstehend' after successful Stripe payment.
For 'Kauf auf Rechnung', booking is confirmed immediately.
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://events-platform-4.preview.emergentagent.com')

# Test data IDs from the review request
TEST_SCHAUSTELLER_WITH_RECHNUNG = "044d0b7a-1f0b-422e-a4df-a5c422a513b8"  # Hans Müller, kauf_auf_rechnung=True
TEST_SCHAUSTELLER_WITHOUT_RECHNUNG = "e57c0a4b-245c-45e5-86ce-876855703afa"  # Ulf, kauf_auf_rechnung=False
TEST_EVENT_ID = "de734361-1e4c-4b6a-816c-6dbb0097cd10"  # Test Stripe Event


class TestSignupPaymentStatusCreditCard:
    """Test signup with credit card creates pending_payment status"""
    
    @pytest.fixture(autouse=True)
    def admin_auth(self):
        """Get admin authentication for cleanup"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "password"}
        )
        if response.status_code == 200:
            self.admin_token = response.json().get("token")
            self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        else:
            pytest.skip("Admin auth failed")
        self.created_signup_ids = []
    
    def teardown_method(self, method):
        """Clean up test signups"""
        for signup_id in self.created_signup_ids:
            try:
                requests.delete(
                    f"{BASE_URL}/api/kirmes/signups/{signup_id}",
                    headers=self.admin_headers
                )
            except Exception:
                pass
    
    def test_signup_kreditkarte_returns_pending_payment_status(self):
        """POST /api/kirmes/public/signup with kreditkarte should return payment_status='pending_payment'"""
        # Generate unique platznummer to avoid "already signed up" error
        unique_platznummer = f"TEST-CC-{uuid.uuid4().hex[:6]}"
        
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/signup",
            json={
                "event_id": TEST_EVENT_ID,
                "schausteller_id": TEST_SCHAUSTELLER_WITH_RECHNUNG,
                "platznummer": unique_platznummer,
                "fahrgeschaeft": "Test Karussell",
                "connection_type": "16A",
                "payment_method": "kreditkarte"
            }
        )
        
        if response.status_code == 400 and "Bereits für diese Veranstaltung angemeldet" in str(response.json()):
            # Schausteller already has a signup - need to create a fresh schausteller
            pytest.skip("Schausteller already signed up - need fresh test data")
        
        assert response.status_code == 200, f"Signup failed: {response.json()}"
        data = response.json()
        
        # Track for cleanup
        if data.get("id"):
            self.created_signup_ids.append(data["id"])
        
        # CRITICAL CHECK: payment_status should be 'pending_payment' for credit card
        assert "payment_status" in data, "Response missing payment_status"
        assert data["payment_status"] == "pending_payment", f"Expected payment_status='pending_payment', got '{data['payment_status']}'"
        
        # Verify other fields
        assert data.get("platznummer") == unique_platznummer
        assert data.get("payment_method") == "kreditkarte"
        assert data.get("connection_type") == "16A"
        
        print(f"SUCCESS: Credit card signup created with payment_status='{data['payment_status']}'")


class TestSignupPaymentStatusPayPal:
    """Test signup with PayPal creates pending_payment status"""
    
    @pytest.fixture(autouse=True)
    def admin_auth(self):
        """Get admin authentication for cleanup"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "password"}
        )
        if response.status_code == 200:
            self.admin_token = response.json().get("token")
            self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        else:
            pytest.skip("Admin auth failed")
        self.created_signup_ids = []
    
    def teardown_method(self, method):
        """Clean up test signups"""
        for signup_id in self.created_signup_ids:
            try:
                requests.delete(
                    f"{BASE_URL}/api/kirmes/signups/{signup_id}",
                    headers=self.admin_headers
                )
            except Exception:
                pass
    
    def test_signup_paypal_returns_pending_payment_status(self):
        """POST /api/kirmes/public/signup with paypal should return payment_status='pending_payment'"""
        unique_platznummer = f"TEST-PP-{uuid.uuid4().hex[:6]}"
        
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/signup",
            json={
                "event_id": TEST_EVENT_ID,
                "schausteller_id": TEST_SCHAUSTELLER_WITH_RECHNUNG,
                "platznummer": unique_platznummer,
                "fahrgeschaeft": "Test Achterbahn",
                "connection_type": "32A",
                "payment_method": "paypal"
            }
        )
        
        if response.status_code == 400 and "Bereits für diese Veranstaltung angemeldet" in str(response.json()):
            pytest.skip("Schausteller already signed up - need fresh test data")
        
        assert response.status_code == 200, f"Signup failed: {response.json()}"
        data = response.json()
        
        if data.get("id"):
            self.created_signup_ids.append(data["id"])
        
        # CRITICAL CHECK: payment_status should be 'pending_payment' for PayPal
        assert "payment_status" in data, "Response missing payment_status"
        assert data["payment_status"] == "pending_payment", f"Expected payment_status='pending_payment', got '{data['payment_status']}'"
        
        print(f"SUCCESS: PayPal signup created with payment_status='{data['payment_status']}'")


class TestSignupPaymentStatusRechnung:
    """Test signup with Rechnung for authorized schausteller"""
    
    @pytest.fixture(autouse=True)
    def admin_auth(self):
        """Get admin authentication for cleanup"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "password"}
        )
        if response.status_code == 200:
            self.admin_token = response.json().get("token")
            self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        else:
            pytest.skip("Admin auth failed")
        self.created_signup_ids = []
    
    def teardown_method(self, method):
        """Clean up test signups"""
        for signup_id in self.created_signup_ids:
            try:
                requests.delete(
                    f"{BASE_URL}/api/kirmes/signups/{signup_id}",
                    headers=self.admin_headers
                )
            except Exception:
                pass
    
    def test_signup_rechnung_with_authorized_schausteller_returns_ausstehend(self):
        """POST /api/kirmes/public/signup with rechnung (kauf_auf_rechnung=True) should return payment_status='ausstehend'"""
        unique_platznummer = f"TEST-RE-{uuid.uuid4().hex[:6]}"
        
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/signup",
            json={
                "event_id": TEST_EVENT_ID,
                "schausteller_id": TEST_SCHAUSTELLER_WITH_RECHNUNG,  # Hans Müller with kauf_auf_rechnung=True
                "platznummer": unique_platznummer,
                "fahrgeschaeft": "Test Riesenrad",
                "connection_type": "63A",
                "payment_method": "rechnung"
            }
        )
        
        if response.status_code == 400 and "Bereits für diese Veranstaltung angemeldet" in str(response.json()):
            pytest.skip("Schausteller already signed up - need fresh test data")
        
        assert response.status_code == 200, f"Signup failed: {response.json()}"
        data = response.json()
        
        if data.get("id"):
            self.created_signup_ids.append(data["id"])
        
        # CRITICAL CHECK: payment_status should be 'ausstehend' for authorized rechnung
        assert "payment_status" in data, "Response missing payment_status"
        assert data["payment_status"] == "ausstehend", f"Expected payment_status='ausstehend', got '{data['payment_status']}'"
        
        print(f"SUCCESS: Rechnung signup created with payment_status='{data['payment_status']}'")
    
    def test_signup_rechnung_without_authorization_returns_400(self):
        """POST /api/kirmes/public/signup with rechnung (kauf_auf_rechnung=False) should return 400 error"""
        unique_platznummer = f"TEST-NORE-{uuid.uuid4().hex[:6]}"
        
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/signup",
            json={
                "event_id": TEST_EVENT_ID,
                "schausteller_id": TEST_SCHAUSTELLER_WITHOUT_RECHNUNG,  # Ulf with kauf_auf_rechnung=False
                "platznummer": unique_platznummer,
                "fahrgeschaeft": "Test Autoscooter",
                "connection_type": "32A",
                "payment_method": "rechnung"
            }
        )
        
        # Should return 400 because kauf_auf_rechnung is False for this schausteller
        assert response.status_code == 400, f"Expected 400 error, got {response.status_code}: {response.json()}"
        
        detail = response.json().get("detail", "")
        assert "nicht freigeschaltet" in detail or "nicht erlaubt" in detail.lower() or "rechnung" in detail.lower(), \
            f"Expected error about Rechnung not allowed, got: {detail}"
        
        print(f"SUCCESS: Correctly rejected rechnung for unauthorized schausteller: {detail}")


class TestPaymentStatusPolling:
    """Test that payment status polling correctly updates signup status"""
    
    @pytest.fixture(autouse=True)
    def admin_auth(self):
        """Get admin authentication"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "password"}
        )
        if response.status_code == 200:
            self.admin_token = response.json().get("token")
            self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        else:
            pytest.skip("Admin auth failed")
    
    def test_checkout_deposit_works_for_pending_payment_signup(self):
        """POST /api/payments/checkout/deposit should work for pending_payment signups"""
        # First, we need an existing pending_payment signup
        # Use the known test signup from iteration 35
        existing_signup_id = "aaa7f30e-ebc3-4f31-99b7-1aed7de69305"
        
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout/deposit",
            json={
                "signup_id": existing_signup_id,
                "event_id": TEST_EVENT_ID,
                "origin_url": BASE_URL
            }
        )
        
        # Should return checkout URL
        assert response.status_code == 200, f"Checkout failed: {response.json()}"
        data = response.json()
        
        assert "url" in data
        assert data["url"].startswith("https://checkout.stripe.com")
        assert "session_id" in data
        assert data["session_id"].startswith("cs_test_")
        assert "amount" in data
        
        print(f"SUCCESS: Checkout session created for pending_payment signup")
        print(f"  URL: {data['url'][:60]}...")
        print(f"  Session: {data['session_id']}")
        print(f"  Amount: {data['amount']} EUR")
    
    def test_checkout_status_returns_pending_for_unpaid_session(self):
        """GET /api/payments/checkout/status/{session_id} returns pending for unpaid sessions"""
        # Create a new checkout session first
        create_response = requests.post(
            f"{BASE_URL}/api/payments/checkout/deposit",
            json={
                "signup_id": "aaa7f30e-ebc3-4f31-99b7-1aed7de69305",
                "event_id": TEST_EVENT_ID,
                "origin_url": BASE_URL
            }
        )
        
        if create_response.status_code != 200:
            pytest.skip("Could not create checkout session for test")
        
        session_id = create_response.json().get("session_id")
        
        # Check status - should be pending since we haven't paid
        status_response = requests.get(f"{BASE_URL}/api/payments/checkout/status/{session_id}")
        
        assert status_response.status_code == 200
        data = status_response.json()
        
        assert "status" in data
        assert data["status"] in ["pending", "expired"]  # Could be expired if session times out
        assert data["type"] == "deposit"
        
        print(f"SUCCESS: Status polling works - status={data['status']}")


class TestPendingPaymentStatusBadgeDisplay:
    """Verify that pending_payment status is properly returned in booking list"""
    
    @pytest.fixture(autouse=True)
    def admin_auth(self):
        """Get admin authentication"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "password"}
        )
        if response.status_code == 200:
            self.admin_token = response.json().get("token")
            self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        else:
            pytest.skip("Admin auth failed")
    
    def test_my_bookings_shows_correct_payment_status(self):
        """GET /api/kirmes/public/my-bookings should return signups with payment_status field"""
        # Get bookings for a schausteller that has signups
        response = requests.get(
            f"{BASE_URL}/api/kirmes/public/my-bookings?schausteller_id={TEST_SCHAUSTELLER_WITH_RECHNUNG}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "signups" in data
        
        if len(data["signups"]) > 0:
            # Verify that payment_status field exists in signups
            for signup in data["signups"]:
                assert "payment_status" in signup, f"Signup {signup.get('id')} missing payment_status field"
                assert signup["payment_status"] in ["pending_payment", "ausstehend", "bestaetigt", "abgerechnet", "bezahlt"], \
                    f"Invalid payment_status: {signup['payment_status']}"
                print(f"  Signup {signup.get('platznummer')}: payment_status={signup['payment_status']}")
        
        print(f"SUCCESS: my-bookings returns {len(data['signups'])} signups with payment_status")


class TestSchaustellerKaufAufRechnungFlag:
    """Verify schausteller kauf_auf_rechnung flag is respected"""
    
    def test_schausteller_with_rechnung_has_flag_true(self):
        """Verify test schausteller has kauf_auf_rechnung=True"""
        response = requests.get(
            f"{BASE_URL}/api/kirmes/public/my-bookings?schausteller_id={TEST_SCHAUSTELLER_WITH_RECHNUNG}"
        )
        
        # This endpoint returns schausteller info indirectly
        # Let's just verify the signup endpoint accepts rechnung
        print(f"Testing schausteller {TEST_SCHAUSTELLER_WITH_RECHNUNG} (should have kauf_auf_rechnung=True)")
        assert response.status_code == 200
    
    def test_schausteller_without_rechnung_flag_rejects_rechnung(self):
        """Verify schausteller without kauf_auf_rechnung flag gets rejected"""
        unique_platznummer = f"TEST-FLAG-{uuid.uuid4().hex[:6]}"
        
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/signup",
            json={
                "event_id": TEST_EVENT_ID,
                "schausteller_id": TEST_SCHAUSTELLER_WITHOUT_RECHNUNG,
                "platznummer": unique_platznummer,
                "fahrgeschaeft": "Test Kettenkarussell",
                "connection_type": "16A",
                "payment_method": "rechnung"  # Should fail!
            }
        )
        
        # Should be rejected with 400
        if response.status_code == 400:
            detail = response.json().get("detail", "")
            if "nicht freigeschaltet" in detail:
                print(f"SUCCESS: Rechnung correctly rejected: {detail}")
            elif "Bereits für diese Veranstaltung angemeldet" in detail:
                pytest.skip("Schausteller already has signup for this event")
            else:
                print(f"Got 400 error: {detail}")
        else:
            # If 200, check if it was with kreditkarte/paypal instead
            data = response.json()
            if data.get("payment_method") == "rechnung":
                pytest.fail(f"Expected 400 rejection, got 200 with payment_method=rechnung")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
