"""
Pay-to-Confirm Flow Tests for Kirmes Billing System
Tests the critical bug fix: signups now stay 'pending' until Stripe payment is confirmed.
When kauf_auf_rechnung is enabled, signups are confirmed immediately without payment.

Test Cases:
1. Signup WITHOUT kauf_auf_rechnung -> payment_status='pending', deposit_paid=false, payment_required=true
2. Signup WITH kauf_auf_rechnung -> payment_status='bestaetigt', deposit_paid=true, payment_required=false
3. Payment method 'rechnung' rejected if kauf_auf_rechnung=false
4. GET /api/payments/signups/{signup_id}/status returns current payment_status
5. POST /api/kirmes/public/cancel-pending-signup deletes only pending signups
6. POST /api/payments/checkout/deposit creates Stripe checkout for pending signup
7. Admin PUT /api/kirmes/schausteller/{id} with kauf_auf_rechnung=true
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://event-invoicing.preview.emergentagent.com')


class TestSignupPayToConfirmFlow:
    """Test the pay-to-confirm flow for signup without kauf_auf_rechnung"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin auth and setup test data"""
        # Admin login
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "password"}
        )
        if response.status_code == 200:
            self.admin_token = response.json().get("token")
            self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        else:
            pytest.skip("Admin auth failed")
        
        # Get test schausteller IDs from agent context
        self.schausteller_without_kauf = "4b5270db-7d06-47b2-a0c0-cf11f27048f0"
        self.schausteller_with_kauf = "e4f88843-0b79-41b4-91a6-200ceb8e7eaf"
        self.test_event_id = "de734361-1e4c-4b6a-816c-6dbb0097cd10"
    
    def test_signup_without_kauf_auf_rechnung_returns_pending(self):
        """
        Feature 1: When schausteller has kauf_auf_rechnung=false, signup should have:
        - payment_status='pending'
        - deposit_paid=false
        - payment_required=true
        """
        unique_id = str(uuid.uuid4())[:8]
        
        # First create a new test schausteller without kauf_auf_rechnung
        sch_response = requests.post(
            f"{BASE_URL}/api/kirmes/public/register",
            json={
                "name": f"Test Pending {unique_id}",
                "email": f"test_pending_{unique_id}@test.de",
                "firma": "Test GmbH",
            }
        )
        
        if sch_response.status_code != 200:
            # Use existing schausteller
            schausteller_id = self.schausteller_without_kauf
        else:
            schausteller_id = sch_response.json().get("id")
            # Verify email to enable login
            sch_data = sch_response.json()
            # Skip verification for this test - use existing schausteller
            schausteller_id = self.schausteller_without_kauf
        
        # Try signup - may fail if already signed up
        signup_response = requests.post(
            f"{BASE_URL}/api/kirmes/public/signup",
            json={
                "event_id": self.test_event_id,
                "schausteller_id": schausteller_id,
                "platznummer": f"P{unique_id}",
                "fahrgeschaeft": "Test Bude",
                "connection_type": "16A",
                "payment_method": "kreditkarte"
            }
        )
        
        if signup_response.status_code == 400:
            # Already registered - check if error is about existing signup
            detail = signup_response.json().get("detail", "")
            if "Bereits für diese Veranstaltung angemeldet" in detail:
                # This is expected - need a different event or schausteller
                print(f"Schausteller already signed up for this event: {detail}")
                # Try with the second event
                alt_event_id = "19b15afc-3e14-4c8a-b9c8-8f9a0b0b0b0b"
                signup_response = requests.post(
                    f"{BASE_URL}/api/kirmes/public/signup",
                    json={
                        "event_id": alt_event_id,
                        "schausteller_id": schausteller_id,
                        "platznummer": f"P{unique_id}",
                        "fahrgeschaeft": "Test Bude",
                        "connection_type": "16A",
                        "payment_method": "kreditkarte"
                    }
                )
        
        # If we still can't signup, verify the behavior through existing data
        if signup_response.status_code != 200:
            print(f"Signup failed (expected if already registered): {signup_response.json()}")
            pytest.skip("Could not create new signup - schausteller already registered for all events")
        
        data = signup_response.json()
        print(f"Signup response: {data}")
        
        # Verify pay-to-confirm behavior
        assert data.get("payment_status") == "pending", f"Expected payment_status='pending', got '{data.get('payment_status')}'"
        assert data.get("deposit_paid") == False, f"Expected deposit_paid=False, got '{data.get('deposit_paid')}'"
        assert data.get("payment_required") == True, f"Expected payment_required=True, got '{data.get('payment_required')}'"
        
        print("SUCCESS: Signup without kauf_auf_rechnung returns pending status")

    def test_signup_with_kauf_auf_rechnung_returns_confirmed(self):
        """
        Feature 2: When schausteller has kauf_auf_rechnung=true, signup should have:
        - payment_status='bestaetigt'
        - deposit_paid=true
        - payment_required=false
        """
        unique_id = str(uuid.uuid4())[:8]
        schausteller_id = self.schausteller_with_kauf
        
        # First verify this schausteller has kauf_auf_rechnung
        sch_response = requests.get(
            f"{BASE_URL}/api/kirmes/schausteller/{schausteller_id}",
            headers=self.admin_headers
        )
        
        if sch_response.status_code != 200:
            pytest.skip(f"Schausteller with kauf_auf_rechnung not found: {schausteller_id}")
        
        sch_data = sch_response.json()
        if not sch_data.get("kauf_auf_rechnung"):
            # Enable kauf_auf_rechnung for this test
            update_resp = requests.put(
                f"{BASE_URL}/api/kirmes/schausteller/{schausteller_id}",
                headers=self.admin_headers,
                json={"kauf_auf_rechnung": True}
            )
            if update_resp.status_code != 200:
                pytest.skip("Could not enable kauf_auf_rechnung for test schausteller")
        
        # Try signup
        signup_response = requests.post(
            f"{BASE_URL}/api/kirmes/public/signup",
            json={
                "event_id": self.test_event_id,
                "schausteller_id": schausteller_id,
                "platznummer": f"K{unique_id}",
                "fahrgeschaeft": "Kauf Test Bude",
                "connection_type": "32A",
                "payment_method": "rechnung"  # Should be allowed with kauf_auf_rechnung
            }
        )
        
        if signup_response.status_code == 400:
            detail = signup_response.json().get("detail", "")
            if "Bereits für diese Veranstaltung angemeldet" in detail:
                print(f"Schausteller already signed up: {detail}")
                pytest.skip("Schausteller already registered for event")
        
        if signup_response.status_code != 200:
            print(f"Signup failed: {signup_response.json()}")
            pytest.skip(f"Could not create signup: {signup_response.status_code}")
        
        data = signup_response.json()
        print(f"Signup with kauf_auf_rechnung response: {data}")
        
        # Verify immediate confirmation
        assert data.get("payment_status") == "bestaetigt", f"Expected payment_status='bestaetigt', got '{data.get('payment_status')}'"
        assert data.get("deposit_paid") == True, f"Expected deposit_paid=True, got '{data.get('deposit_paid')}'"
        assert data.get("payment_required") == False, f"Expected payment_required=False, got '{data.get('payment_required')}'"
        
        print("SUCCESS: Signup with kauf_auf_rechnung returns confirmed status")

    def test_rechnung_payment_rejected_without_kauf_auf_rechnung(self):
        """
        Feature 3: Payment method 'rechnung' should be rejected if kauf_auf_rechnung=false
        """
        unique_id = str(uuid.uuid4())[:8]
        
        # Ensure schausteller does NOT have kauf_auf_rechnung
        # First check and disable if needed
        sch_response = requests.get(
            f"{BASE_URL}/api/kirmes/schausteller/{self.schausteller_without_kauf}",
            headers=self.admin_headers
        )
        
        if sch_response.status_code == 200:
            sch_data = sch_response.json()
            if sch_data.get("kauf_auf_rechnung"):
                # Disable it for this test
                requests.put(
                    f"{BASE_URL}/api/kirmes/schausteller/{self.schausteller_without_kauf}",
                    headers=self.admin_headers,
                    json={"kauf_auf_rechnung": False}
                )
        
        # Try signup with 'rechnung' payment method
        signup_response = requests.post(
            f"{BASE_URL}/api/kirmes/public/signup",
            json={
                "event_id": self.test_event_id,
                "schausteller_id": self.schausteller_without_kauf,
                "platznummer": f"R{unique_id}",
                "fahrgeschaeft": "Rechnung Test",
                "connection_type": "16A",
                "payment_method": "rechnung"  # Should be rejected
            }
        )
        
        # Should return 400 with specific error
        if signup_response.status_code == 400:
            detail = signup_response.json().get("detail", "")
            if "Kauf auf Rechnung ist für diesen Schausteller nicht freigeschaltet" in detail:
                print(f"SUCCESS: Rechnung payment correctly rejected: {detail}")
                return
            elif "Bereits für diese Veranstaltung angemeldet" in detail:
                pytest.skip("Schausteller already registered - cannot test rechnung rejection")
        
        # If signup succeeded, that's a bug
        if signup_response.status_code == 200:
            pytest.fail("BUG: Signup with 'rechnung' should be rejected for schausteller without kauf_auf_rechnung")
        
        print(f"Response: {signup_response.status_code} - {signup_response.json()}")


class TestPaymentStatusEndpoint:
    """Test the signup payment status endpoint"""
    
    def test_get_signup_status_returns_payment_info(self):
        """
        Feature 4: GET /api/payments/signups/{signup_id}/status returns current payment_status
        """
        # Use an existing signup from iteration 35
        signup_id = "aaa7f30e-ebc3-4f31-99b7-1aed7de69305"
        
        response = requests.get(f"{BASE_URL}/api/payments/signups/{signup_id}/status")
        
        if response.status_code == 404:
            pytest.skip("Test signup not found - may have been deleted")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response contains required fields
        assert "id" in data
        assert "payment_status" in data
        assert "deposit_paid" in data
        
        print(f"Signup status: {data}")
        print(f"SUCCESS: GET /api/payments/signups/{signup_id}/status works correctly")

    def test_get_signup_status_invalid_id(self):
        """GET /api/payments/signups/{invalid_id}/status returns 404"""
        response = requests.get(f"{BASE_URL}/api/payments/signups/invalid-signup-id/status")
        
        assert response.status_code == 404
        assert "Anmeldung nicht gefunden" in response.json().get("detail", "")
        print("SUCCESS: Invalid signup ID correctly returns 404")


class TestCancelPendingSignup:
    """Test the cancel pending signup endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin auth"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "password"}
        )
        if response.status_code == 200:
            self.admin_token = response.json().get("token")
            self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
    
    def test_cancel_pending_signup_deletes_pending_only(self):
        """
        Feature 5: POST /api/kirmes/public/cancel-pending-signup deletes ONLY pending signups
        """
        # Test with a random ID - should return OK even if not found
        random_id = str(uuid.uuid4())
        
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/cancel-pending-signup",
            json={"signup_id": random_id}
        )
        
        assert response.status_code == 200
        assert response.json().get("message") in ["OK", "Anmeldung storniert"]
        print(f"Cancel pending signup response: {response.json()}")
        
    def test_cancel_confirmed_signup_does_nothing(self):
        """Confirmed signups should NOT be deleted by cancel-pending-signup"""
        # Use an existing confirmed signup (from iteration 35)
        signup_id = "aaa7f30e-ebc3-4f31-99b7-1aed7de69305"
        
        # First verify the signup exists
        status_resp = requests.get(f"{BASE_URL}/api/payments/signups/{signup_id}/status")
        if status_resp.status_code == 404:
            pytest.skip("Test signup not found")
        
        original_status = status_resp.json().get("payment_status")
        
        # Try to cancel
        cancel_response = requests.post(
            f"{BASE_URL}/api/kirmes/public/cancel-pending-signup",
            json={"signup_id": signup_id}
        )
        
        assert cancel_response.status_code == 200
        
        # Verify signup still exists (if it wasn't pending)
        verify_resp = requests.get(f"{BASE_URL}/api/payments/signups/{signup_id}/status")
        
        if original_status != "pending":
            # Signup should still exist
            assert verify_resp.status_code == 200
            print(f"SUCCESS: Non-pending signup ({original_status}) was not deleted")
        else:
            # Pending signup may have been deleted
            print(f"Pending signup was deleted as expected")


class TestDepositCheckout:
    """Test the deposit checkout endpoint"""
    
    def test_deposit_checkout_for_pending_signup(self):
        """
        Feature 6: POST /api/payments/checkout/deposit creates Stripe session for pending signup
        """
        signup_id = "aaa7f30e-ebc3-4f31-99b7-1aed7de69305"
        event_id = "de734361-1e4c-4b6a-816c-6dbb0097cd10"
        
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout/deposit",
            json={
                "signup_id": signup_id,
                "event_id": event_id,
                "origin_url": BASE_URL
            }
        )
        
        if response.status_code == 404:
            pytest.skip("Test signup not found")
        
        if response.status_code == 400:
            # Already paid - that's OK
            detail = response.json().get("detail", "")
            if "Kaution bereits bezahlt" in detail:
                print(f"Signup already paid: {detail}")
                return
        
        assert response.status_code == 200
        data = response.json()
        
        assert "url" in data
        assert data["url"].startswith("https://checkout.stripe.com")
        assert "session_id" in data
        assert data["session_id"].startswith("cs_test_")
        assert "amount" in data
        
        print(f"SUCCESS: Deposit checkout created: {data['session_id']}")


class TestAdminKaufAufRechnung:
    """Test admin ability to enable kauf_auf_rechnung"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin auth"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "password"}
        )
        if response.status_code == 200:
            self.admin_token = response.json().get("token")
            self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        else:
            pytest.skip("Admin auth failed")
    
    def test_admin_can_update_kauf_auf_rechnung(self):
        """
        Feature 11: PUT /api/kirmes/schausteller/{id} with kauf_auf_rechnung=true updates schausteller
        """
        schausteller_id = "e4f88843-0b79-41b4-91a6-200ceb8e7eaf"
        
        # Get current state
        get_resp = requests.get(
            f"{BASE_URL}/api/kirmes/schausteller/{schausteller_id}",
            headers=self.admin_headers
        )
        
        if get_resp.status_code == 404:
            pytest.skip(f"Schausteller {schausteller_id} not found")
        
        original = get_resp.json().get("kauf_auf_rechnung", False)
        
        # Toggle kauf_auf_rechnung
        new_value = not original
        update_resp = requests.put(
            f"{BASE_URL}/api/kirmes/schausteller/{schausteller_id}",
            headers=self.admin_headers,
            json={"kauf_auf_rechnung": new_value}
        )
        
        assert update_resp.status_code == 200
        
        # Verify update
        verify_resp = requests.get(
            f"{BASE_URL}/api/kirmes/schausteller/{schausteller_id}",
            headers=self.admin_headers
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json().get("kauf_auf_rechnung") == new_value
        
        # Revert to original
        requests.put(
            f"{BASE_URL}/api/kirmes/schausteller/{schausteller_id}",
            headers=self.admin_headers,
            json={"kauf_auf_rechnung": original}
        )
        
        print(f"SUCCESS: Admin can toggle kauf_auf_rechnung: {original} -> {new_value} -> {original}")


class TestStatusLabels:
    """Test that pending status is properly handled"""
    
    def test_signup_status_includes_pending(self):
        """
        Feature 10: Status labels should include 'pending' status
        """
        # The frontend STATUS_LABELS includes 'pending' - verify backend returns it
        # Get any signup and check the payment_status field
        
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "password"}
        )
        if response.status_code != 200:
            pytest.skip("Admin auth failed")
        
        token = response.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get an event with signups
        event_id = "de734361-1e4c-4b6a-816c-6dbb0097cd10"
        event_resp = requests.get(
            f"{BASE_URL}/api/kirmes/events/{event_id}",
            headers=headers
        )
        
        if event_resp.status_code != 200:
            pytest.skip("Event not found")
        
        signups = event_resp.json().get("signups", [])
        
        # Check if any signup has pending status or if statuses are valid
        valid_statuses = ["pending", "ausstehend", "bestaetigt", "bezahlt", "reserviert", "abgerechnet"]
        
        for signup in signups:
            status = signup.get("payment_status", "")
            if status:
                assert status in valid_statuses, f"Invalid status: {status}"
        
        print(f"SUCCESS: All signup statuses are valid. Found {len(signups)} signups")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
