"""
Kirmes Module - Backend API Tests (Updated for Email+Password Auth)
Tests for Veranstaltungsverwaltung (Event Management) and Schausteller Registration

Connection Types: Schuko, 16A, 32A, 63A, 125A, Festanschluss
Event Statuses: entwurf, freigegeben, aktiv, abgeschlossen, abgerechnet

New Authentication Flow:
1. Register with email+password (sends verification code via email)
2. Verify email with 6-digit code
3. Login with email+password (only works for verified accounts with password)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data prefixes
TEST_PREFIX = "TEST_KIRMES_"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "password"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def mitarbeiter_token(api_client):
    """Get mitarbeiter (staff) authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "ma1@test.com",
        "password": "password"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Mitarbeiter authentication failed")


@pytest.fixture
def admin_client(api_client, admin_token):
    """Session with admin auth header"""
    api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return api_client


@pytest.fixture
def staff_client(api_client, mitarbeiter_token):
    """Session with mitarbeiter auth header"""
    api_client.headers.update({"Authorization": f"Bearer {mitarbeiter_token}"})
    return api_client


# ===================== Standard Prices Tests =====================

class TestStandardPrices:
    """Test standard price list management"""
    
    def test_get_standard_prices_requires_auth(self, api_client):
        """Standard prices endpoint requires staff auth"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/kirmes/standard-prices")
        assert response.status_code in [401, 403], "Expected auth error without token"
    
    def test_get_standard_prices_as_staff(self, admin_client):
        """Staff can get standard prices"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/standard-prices")
        assert response.status_code == 200
        
        data = response.json()
        assert "prices" in data
        prices = data["prices"]
        assert isinstance(prices, list)
        # Should have connection types including Schuko
        connection_types = [p["connection_type"] for p in prices]
        assert "Schuko" in connection_types
        assert "16A" in connection_types
        assert "32A" in connection_types
        assert "63A" in connection_types
        assert "125A" in connection_types
        assert "Festanschluss" in connection_types
    
    def test_update_standard_prices_requires_admin(self, staff_client):
        """Only admin can update standard prices"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "ma1@test.com",
            "password": "password"
        })
        if login_response.status_code != 200:
            pytest.skip("Mitarbeiter login failed")
        
        token = login_response.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        payload = {"prices": [{"connection_type": "16A", "price": 10.0, "avg_kwh": 0.0}]}
        response = session.put(f"{BASE_URL}/api/kirmes/standard-prices", json=payload)
        assert response.status_code in [403, 405], f"Expected forbidden for mitarbeiter, got {response.status_code}"
    
    def test_update_standard_prices_as_admin(self, admin_client):
        """Admin can update standard prices"""
        get_response = admin_client.get(f"{BASE_URL}/api/kirmes/standard-prices")
        assert get_response.status_code == 200
        
        new_prices = [
            {"connection_type": "Schuko", "price": 30.00, "avg_kwh": 0.0},
            {"connection_type": "16A", "price": 50.00, "avg_kwh": 0.0},
            {"connection_type": "32A", "price": 100.00, "avg_kwh": 0.0},
            {"connection_type": "63A", "price": 200.00, "avg_kwh": 0.0},
            {"connection_type": "125A", "price": 350.00, "avg_kwh": 0.0},
            {"connection_type": "Festanschluss", "price": 500.00, "avg_kwh": 0.0},
        ]
        
        response = admin_client.put(f"{BASE_URL}/api/kirmes/standard-prices", json={"prices": new_prices})
        assert response.status_code == 200
        
        verify_response = admin_client.get(f"{BASE_URL}/api/kirmes/standard-prices")
        assert verify_response.status_code == 200
        updated = verify_response.json()
        
        for p in updated["prices"]:
            if p["connection_type"] == "16A":
                assert p["price"] == 50.00
            elif p["connection_type"] == "32A":
                assert p["price"] == 100.00


# ===================== Events Tests =====================

class TestEvents:
    """Test event CRUD operations"""
    
    def test_list_events_requires_auth(self, api_client):
        """Events list requires staff auth"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/kirmes/events")
        assert response.status_code in [401, 403]
    
    def test_create_event(self, admin_client):
        """Create new event with standard prices"""
        event_name = f"{TEST_PREFIX}Testveranstaltung_{uuid.uuid4().hex[:6]}"
        payload = {
            "name": event_name,
            "location": "Teststadt",
            "start_date": "2026-06-01",
            "end_date": "2026-06-10",
            "notes": "Testnotiz",
            "use_standard_prices": True
        }
        
        response = admin_client.post(f"{BASE_URL}/api/kirmes/events", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == event_name
        assert data["location"] == "Teststadt"
        assert data["status"] == "entwurf"
        assert "id" in data
        assert "prices" in data
        assert isinstance(data["prices"], list)
        
        return data
    
    def test_list_events(self, admin_client):
        """List all events"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/events")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            event = data[0]
            assert "id" in event
            assert "name" in event
            assert "status" in event
            assert "signup_count" in event
    
    def test_list_events_filter_by_status(self, admin_client):
        """Filter events by status"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/events?status=entwurf")
        assert response.status_code == 200
        
        data = response.json()
        for event in data:
            assert event["status"] == "entwurf"
    
    def test_get_event_by_id(self, admin_client):
        """Get single event with signups"""
        list_response = admin_client.get(f"{BASE_URL}/api/kirmes/events")
        assert list_response.status_code == 200
        events = list_response.json()
        
        if len(events) == 0:
            pytest.skip("No events to test")
        
        event_id = events[0]["id"]
        
        response = admin_client.get(f"{BASE_URL}/api/kirmes/events/{event_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == event_id
        assert "signups" in data
        assert isinstance(data["signups"], list)
    
    def test_update_event(self, admin_client):
        """Update event details"""
        create_payload = {
            "name": f"{TEST_PREFIX}UpdateTest_{uuid.uuid4().hex[:6]}",
            "location": "Old Location",
            "start_date": "2026-07-01",
            "end_date": "2026-07-05",
            "use_standard_prices": True
        }
        
        create_response = admin_client.post(f"{BASE_URL}/api/kirmes/events", json=create_payload)
        assert create_response.status_code == 200
        event_id = create_response.json()["id"]
        
        update_payload = {
            "name": f"{TEST_PREFIX}UpdateTest_UPDATED",
            "location": "New Location",
            "notes": "Updated notes"
        }
        
        update_response = admin_client.put(f"{BASE_URL}/api/kirmes/events/{event_id}", json=update_payload)
        assert update_response.status_code == 200
        
        updated = update_response.json()
        assert updated["location"] == "New Location"
        assert updated["notes"] == "Updated notes"
        
        get_response = admin_client.get(f"{BASE_URL}/api/kirmes/events/{event_id}")
        assert get_response.status_code == 200
        assert get_response.json()["location"] == "New Location"


class TestEventRelease:
    """Test event release workflow"""
    
    def test_release_event(self, admin_client):
        """Release event changes status to freigegeben"""
        create_payload = {
            "name": f"{TEST_PREFIX}ReleaseTest_{uuid.uuid4().hex[:6]}",
            "location": "Release Stadt",
            "start_date": "2026-08-01",
            "end_date": "2026-08-10",
            "use_standard_prices": True
        }
        
        create_response = admin_client.post(f"{BASE_URL}/api/kirmes/events", json=create_payload)
        assert create_response.status_code == 200
        event_id = create_response.json()["id"]
        
        release_response = admin_client.post(f"{BASE_URL}/api/kirmes/events/{event_id}/release")
        assert release_response.status_code == 200
        
        release_data = release_response.json()
        assert release_data["status"] == "freigegeben"
        
        get_response = admin_client.get(f"{BASE_URL}/api/kirmes/events/{event_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "freigegeben"
        
        return event_id


class TestEventDelete:
    """Test event deletion"""
    
    def test_delete_entwurf_event(self, admin_client):
        """Can delete event in entwurf status"""
        create_payload = {
            "name": f"{TEST_PREFIX}DeleteTest_{uuid.uuid4().hex[:6]}",
            "location": "Delete Stadt",
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
            "use_standard_prices": True
        }
        
        create_response = admin_client.post(f"{BASE_URL}/api/kirmes/events", json=create_payload)
        assert create_response.status_code == 200
        event_id = create_response.json()["id"]
        
        delete_response = admin_client.delete(f"{BASE_URL}/api/kirmes/events/{event_id}")
        assert delete_response.status_code == 200
        
        get_response = admin_client.get(f"{BASE_URL}/api/kirmes/events/{event_id}")
        assert get_response.status_code == 404
    
    def test_cannot_delete_aktiv_event(self, admin_client):
        """Cannot delete event in aktiv status"""
        create_payload = {
            "name": f"{TEST_PREFIX}NoDeleteTest_{uuid.uuid4().hex[:6]}",
            "location": "NoDelete Stadt",
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
            "use_standard_prices": True
        }
        
        create_response = admin_client.post(f"{BASE_URL}/api/kirmes/events", json=create_payload)
        assert create_response.status_code == 200
        event_id = create_response.json()["id"]
        
        update_response = admin_client.put(f"{BASE_URL}/api/kirmes/events/{event_id}", json={"status": "aktiv"})
        assert update_response.status_code == 200
        
        delete_response = admin_client.delete(f"{BASE_URL}/api/kirmes/events/{event_id}")
        assert delete_response.status_code == 400


# ===================== Public API Tests =====================

class TestPublicAPI:
    """Test public endpoints (no auth required)"""
    
    def test_public_events_list_only_released(self, api_client):
        """Public events endpoint only returns freigegeben/aktiv events"""
        response = api_client.get(f"{BASE_URL}/api/kirmes/public/events")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        for event in data:
            assert event["status"] in ["freigegeben", "aktiv"], f"Event {event['name']} has invalid status {event['status']}"
    
    def test_connection_types_endpoint(self, api_client):
        """Get available connection types (public)"""
        response = api_client.get(f"{BASE_URL}/api/kirmes/connection-types")
        assert response.status_code == 200
        
        data = response.json()
        assert "Schuko" in data
        assert "16A" in data
        assert "32A" in data
        assert "63A" in data
        assert "125A" in data
        assert "Festanschluss" in data


# ===================== Schausteller Registration with Password Tests =====================

class TestSchaustellerRegistration:
    """Test schausteller registration flow with email+password authentication"""
    
    def test_register_schausteller_with_password(self, api_client):
        """Register new schausteller with email+password (public, no auth)"""
        unique_email = f"test_{uuid.uuid4().hex[:8]}@test.de"
        
        payload = {
            "firma": f"{TEST_PREFIX}TestFirma",
            "name": "Max Mustermann",
            "strasse": "Teststrasse 123",
            "plz": "40210",
            "ort": "Dusseldorf",
            "steuernummer": "DE123456789",
            "email": unique_email,
            "password": "securepass123",
            "telefon": "+49 211 123456",
            "rechnungs_email": unique_email
        }
        
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["firma"] == f"{TEST_PREFIX}TestFirma"
        assert data["email"] == unique_email
        assert "id" in data
        # IMPORTANT: password_hash should NOT be in response
        assert "password_hash" not in data, "password_hash should not be exposed in API response"
        # IMPORTANT: verification_code should NOT be in response
        assert "verification_code" not in data, "verification_code should not be exposed in API response"
        assert data.get("email_verified") == False
        
        return data
    
    def test_register_requires_password(self, api_client):
        """Registration without password should fail"""
        unique_email = f"nopw_{uuid.uuid4().hex[:8]}@test.de"
        
        payload = {
            "firma": "NoPwFirma",
            "name": "No Password",
            "strasse": "Str 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DE111",
            "email": unique_email,
            # No password field
            "telefon": "123",
            "rechnungs_email": unique_email
        }
        
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=payload)
        assert response.status_code == 422, "Should fail validation without password"
    
    def test_register_password_too_short(self, api_client):
        """Registration with password < 6 chars should fail"""
        unique_email = f"shortpw_{uuid.uuid4().hex[:8]}@test.de"
        
        payload = {
            "firma": "ShortPwFirma",
            "name": "Short Password",
            "strasse": "Str 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DE222",
            "email": unique_email,
            "password": "12345",  # Only 5 chars
            "telefon": "123",
            "rechnungs_email": unique_email
        }
        
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=payload)
        assert response.status_code == 400, "Should fail with short password"
        assert "6" in response.json().get("detail", ""), "Error should mention 6 character requirement"
    
    def test_register_duplicate_email_fails(self, api_client):
        """Cannot register with duplicate email that is already verified"""
        # Use the pre-existing verified test schausteller
        payload = {
            "firma": "Duplicate Firma",
            "name": "Hans Test",
            "strasse": "Strasse 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DE987654321",
            "email": "test-verify@example.com",  # Pre-existing verified schausteller
            "password": "password123",
            "telefon": "123456",
            "rechnungs_email": "test-verify@example.com"
        }
        
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=payload)
        assert response.status_code == 400
        assert "bereits registriert" in response.json().get("detail", "").lower()


class TestSchaustellerLogin:
    """Test schausteller login with email+password"""
    
    def test_login_verified_schausteller(self, api_client):
        """Login verified schausteller with email+password"""
        # test-verify@example.com / test1234 is pre-seeded as verified
        payload = {"email": "test-verify@example.com", "password": "test1234"}
        
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/login", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["email"] == "test-verify@example.com"
        assert "id" in data
        # IMPORTANT: password_hash should NOT be in response
        assert "password_hash" not in data, "password_hash should not be exposed in API response"
        # IMPORTANT: verification_code should NOT be in response  
        assert "verification_code" not in data, "verification_code should not be exposed in API response"
    
    def test_login_wrong_password_fails(self, api_client):
        """Login with wrong password should fail"""
        payload = {"email": "test-verify@example.com", "password": "wrongpassword"}
        
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/login", json=payload)
        assert response.status_code == 401
        assert "passwort" in response.json().get("detail", "").lower()
    
    def test_login_unverified_email_fails(self, api_client):
        """Login with unverified email should fail"""
        # First register a new user (unverified)
        unique_email = f"unverified_{uuid.uuid4().hex[:8]}@test.de"
        reg_payload = {
            "firma": "Unverified Firma",
            "name": "Unverified User",
            "strasse": "Str 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DE333",
            "email": unique_email,
            "password": "testpass123",
            "telefon": "123",
            "rechnungs_email": unique_email
        }
        api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=reg_payload)
        
        # Try to login - should fail because not verified
        login_payload = {"email": unique_email, "password": "testpass123"}
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/login", json=login_payload)
        assert response.status_code == 403
        assert "nicht best" in response.json().get("detail", "").lower()
    
    def test_login_no_password_schausteller_fails(self, api_client):
        """Login for schausteller without password should show clear error"""
        # hans@test.de exists but has no password_hash AND is not verified
        # The system checks verification first, then password
        # This is correct security behavior - don't reveal password status to unverified accounts
        payload = {"email": "hans@test.de", "password": "anypassword"}
        
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/login", json=payload)
        # Should return 401 or 403 with error message
        assert response.status_code in [401, 403]
        detail = response.json().get("detail", "").lower()
        # Since hans@test.de is NOT verified, it should return verification error first
        # OR if it was verified, it should return password error
        assert ("passwort" in detail or "registr" in detail or "best" in detail), \
            f"Expected clear error about verification or password, got: {detail}"
    
    def test_login_nonexistent_email_fails(self, api_client):
        """Login with non-existent email fails"""
        payload = {"email": "nonexistent@test.de", "password": "anypassword"}
        
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/login", json=payload)
        assert response.status_code == 404


class TestEmailVerification:
    """Test email verification flow"""
    
    def test_verify_email_wrong_code_fails(self, api_client):
        """Verify with wrong code should fail"""
        # Register new user
        unique_email = f"verify_test_{uuid.uuid4().hex[:8]}@test.de"
        reg_payload = {
            "firma": "Verify Firma",
            "name": "Verify User",
            "strasse": "Str 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DE444",
            "email": unique_email,
            "password": "verifypass123",
            "telefon": "123",
            "rechnungs_email": unique_email
        }
        api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=reg_payload)
        
        # Try wrong code
        verify_payload = {"email": unique_email, "code": "000000"}
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/verify-email", json=verify_payload)
        assert response.status_code == 400
        assert "ung" in response.json().get("detail", "").lower()  # "ungültig"
    
    def test_verify_email_nonexistent_email_fails(self, api_client):
        """Verify with non-existent email should fail"""
        verify_payload = {"email": "doesnotexist@test.de", "code": "123456"}
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/verify-email", json=verify_payload)
        assert response.status_code == 404
    
    def test_verify_email_response_no_sensitive_data(self, api_client):
        """Verify email response should not contain password_hash or verification_code"""
        # Verify an already verified user (should return user data)
        verify_payload = {"email": "test-verify@example.com", "code": "anything"}
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/verify-email", json=verify_payload)
        
        if response.status_code == 200:
            data = response.json()
            assert "password_hash" not in data, "password_hash should not be in verify response"
            assert "verification_code" not in data, "verification_code should not be in verify response"


class TestResendCode:
    """Test resend verification code flow"""
    
    def test_resend_code_endpoint(self, api_client):
        """Resend code endpoint should work"""
        # Register a new unverified user
        unique_email = f"resend_{uuid.uuid4().hex[:8]}@test.de"
        reg_payload = {
            "firma": "Resend Firma",
            "name": "Resend User",
            "strasse": "Str 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DE555",
            "email": unique_email,
            "password": "resendpass123",
            "telefon": "123",
            "rechnungs_email": unique_email
        }
        api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=reg_payload)
        
        # Resend code (GET request)
        response = api_client.get(f"{BASE_URL}/api/kirmes/public/resend-code?email={unique_email}")
        assert response.status_code == 200
        assert "gesendet" in response.json().get("message", "").lower() or "sent" in response.json().get("message", "").lower()
    
    def test_resend_code_already_verified(self, api_client):
        """Resend code for already verified user should return appropriate message"""
        response = api_client.get(f"{BASE_URL}/api/kirmes/public/resend-code?email=test-verify@example.com")
        assert response.status_code == 200
        # Should say already verified
        assert "bereits" in response.json().get("message", "").lower()
    
    def test_resend_code_nonexistent_email_fails(self, api_client):
        """Resend code for non-existent email should fail"""
        response = api_client.get(f"{BASE_URL}/api/kirmes/public/resend-code?email=doesnotexist@test.de")
        assert response.status_code == 404


# ===================== Public Signup Tests =====================

class TestPublicSignup:
    """Test public event signup flow"""
    
    def test_signup_for_event(self, api_client, admin_client):
        """Schausteller can sign up for released event"""
        # 1. Create and release an event
        event_payload = {
            "name": f"{TEST_PREFIX}SignupTest_{uuid.uuid4().hex[:6]}",
            "location": "Signup Stadt",
            "start_date": "2026-11-01",
            "end_date": "2026-11-10",
            "use_standard_prices": True
        }
        
        create_response = admin_client.post(f"{BASE_URL}/api/kirmes/events", json=event_payload)
        assert create_response.status_code == 200
        event_id = create_response.json()["id"]
        
        release_response = admin_client.post(f"{BASE_URL}/api/kirmes/events/{event_id}/release")
        assert release_response.status_code == 200
        
        # 2. Register a new schausteller with password
        unique_email = f"signup_test_{uuid.uuid4().hex[:8]}@test.de"
        sch_payload = {
            "firma": f"{TEST_PREFIX}SignupFirma",
            "name": "Signup Tester",
            "strasse": "Signupstrasse 1",
            "plz": "50000",
            "ort": "Signupstadt",
            "steuernummer": "DE111222333",
            "email": unique_email,
            "password": "signuppass123",
            "telefon": "555-1234",
            "rechnungs_email": unique_email
        }
        
        reg_response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=sch_payload)
        assert reg_response.status_code == 200
        schausteller_id = reg_response.json()["id"]
        
        # 3. Sign up for the event
        signup_payload = {
            "event_id": event_id,
            "schausteller_id": schausteller_id,
            "platznummer": "A42",
            "fahrgeschaeft": "Achterbahn",
            "connection_type": "32A",
            "payment_method": "kreditkarte"
        }
        
        signup_response = api_client.post(f"{BASE_URL}/api/kirmes/public/signup", json=signup_payload)
        assert signup_response.status_code == 200
        
        signup_data = signup_response.json()
        assert signup_data["event_id"] == event_id
        assert signup_data["platznummer"] == "A42"
        assert signup_data["connection_type"] == "32A"
        assert signup_data["payment_status"] == "ausstehend"
        assert "schausteller" in signup_data
    
    def test_signup_invalid_connection_type_fails(self, api_client, admin_client):
        """Signup with invalid connection type fails"""
        event_payload = {
            "name": f"{TEST_PREFIX}InvalidConnTest_{uuid.uuid4().hex[:6]}",
            "location": "Test Stadt",
            "start_date": "2026-12-01",
            "end_date": "2026-12-05",
            "use_standard_prices": True
        }
        
        create_response = admin_client.post(f"{BASE_URL}/api/kirmes/events", json=event_payload)
        assert create_response.status_code == 200
        event_id = create_response.json()["id"]
        
        admin_client.post(f"{BASE_URL}/api/kirmes/events/{event_id}/release")
        
        unique_email = f"invalid_conn_{uuid.uuid4().hex[:8]}@test.de"
        reg_response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json={
            "firma": "Invalid Test",
            "name": "Invalid Tester",
            "strasse": "Str 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DE999",
            "email": unique_email,
            "password": "invalidpass123",
            "telefon": "123",
            "rechnungs_email": unique_email
        })
        schausteller_id = reg_response.json()["id"]
        
        signup_payload = {
            "event_id": event_id,
            "schausteller_id": schausteller_id,
            "platznummer": "B1",
            "fahrgeschaeft": "Test",
            "connection_type": "INVALID_TYPE",
            "payment_method": "kreditkarte"
        }
        
        signup_response = api_client.post(f"{BASE_URL}/api/kirmes/public/signup", json=signup_payload)
        assert signup_response.status_code == 400
    
    def test_signup_duplicate_fails(self, api_client, admin_client):
        """Cannot sign up twice for same event"""
        event_payload = {
            "name": f"{TEST_PREFIX}DuplicateTest_{uuid.uuid4().hex[:6]}",
            "location": "Duplicate Stadt",
            "start_date": "2027-01-01",
            "end_date": "2027-01-05",
            "use_standard_prices": True
        }
        
        create_response = admin_client.post(f"{BASE_URL}/api/kirmes/events", json=event_payload)
        event_id = create_response.json()["id"]
        admin_client.post(f"{BASE_URL}/api/kirmes/events/{event_id}/release")
        
        unique_email = f"duplicate_{uuid.uuid4().hex[:8]}@test.de"
        reg_response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json={
            "firma": "Duplicate Firma",
            "name": "Duplicate Tester",
            "strasse": "Str 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DE888",
            "email": unique_email,
            "password": "duplicatepass123",
            "telefon": "123",
            "rechnungs_email": unique_email
        })
        schausteller_id = reg_response.json()["id"]
        
        signup_payload = {
            "event_id": event_id,
            "schausteller_id": schausteller_id,
            "platznummer": "C1",
            "fahrgeschaeft": "Test",
            "connection_type": "16A",
            "payment_method": "paypal"
        }
        
        first_signup = api_client.post(f"{BASE_URL}/api/kirmes/public/signup", json=signup_payload)
        assert first_signup.status_code == 200
        
        signup_payload["platznummer"] = "C2"
        second_signup = api_client.post(f"{BASE_URL}/api/kirmes/public/signup", json=signup_payload)
        assert second_signup.status_code == 400
        assert "bereits" in second_signup.json().get("detail", "").lower()


# ===================== Staff Schausteller Management =====================

class TestSchaustellerManagement:
    """Test staff schausteller management endpoints"""
    
    def test_list_schausteller_requires_auth(self, api_client):
        """Schausteller list requires staff auth"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/kirmes/schausteller")
        assert response.status_code in [401, 403]
    
    def test_list_schausteller(self, admin_client):
        """Staff can list all schausteller"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/schausteller")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        # Verify no sensitive data in list response
        for sch in data:
            assert "password_hash" not in sch, "password_hash should not be exposed in list response"
            assert "verification_code" not in sch, "verification_code should not be exposed in list response"
    
    def test_search_schausteller(self, admin_client):
        """Search schausteller by name/firma/email"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/schausteller?search=hans")
        assert response.status_code == 200
    
    def test_get_schausteller_no_sensitive_data(self, admin_client):
        """Get single schausteller should not expose sensitive data"""
        list_response = admin_client.get(f"{BASE_URL}/api/kirmes/schausteller")
        if list_response.status_code != 200 or len(list_response.json()) == 0:
            pytest.skip("No schausteller to test")
        
        sch_id = list_response.json()[0]["id"]
        response = admin_client.get(f"{BASE_URL}/api/kirmes/schausteller/{sch_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "password_hash" not in data, "password_hash should not be exposed"
        assert "verification_code" not in data, "verification_code should not be exposed"


# ===================== Admin Set Schausteller Password Tests =====================

class TestSchaustellerSetPassword:
    """Test admin/staff set password for schausteller (POST /api/kirmes/schausteller/{id}/set-password)"""
    
    def test_set_password_requires_auth(self, api_client):
        """Set password endpoint requires staff auth"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.post(f"{BASE_URL}/api/kirmes/schausteller/some-id/set-password", json={"password": "test123"})
        assert response.status_code in [401, 403], "Should require authentication"
    
    def test_set_password_as_admin(self, admin_client, api_client):
        """Admin can set password for schausteller"""
        # 1. Create a new schausteller (unverified)
        unique_email = f"setpw_admin_{uuid.uuid4().hex[:8]}@test.de"
        reg_payload = {
            "firma": f"{TEST_PREFIX}SetPwAdminFirma",
            "name": "SetPw Admin Test",
            "strasse": "Str 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DESETPW1",
            "email": unique_email,
            "password": "initialpass",
            "telefon": "123",
            "rechnungs_email": unique_email
        }
        reg_response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=reg_payload)
        assert reg_response.status_code == 200
        sch_id = reg_response.json()["id"]
        
        # Verify initially not verified
        sch_data = reg_response.json()
        assert sch_data.get("email_verified") == False
        
        # 2. Admin sets password
        new_password = "newadminset123"
        set_response = admin_client.post(f"{BASE_URL}/api/kirmes/schausteller/{sch_id}/set-password", json={"password": new_password})
        assert set_response.status_code == 200
        
        response_data = set_response.json()
        assert "message" in response_data
        assert "gesetzt" in response_data["message"].lower() or "set" in response_data["message"].lower()
        
        # 3. Verify schausteller is now verified and can login
        login_response = api_client.post(f"{BASE_URL}/api/kirmes/public/login", json={
            "email": unique_email,
            "password": new_password
        })
        assert login_response.status_code == 200, f"Should login with new password, got {login_response.status_code}: {login_response.text}"
        
        login_data = login_response.json()
        assert login_data["email"] == unique_email
        assert "password_hash" not in login_data
    
    def test_set_password_as_mitarbeiter(self, staff_client, api_client):
        """Mitarbeiter (staff) can also set password for schausteller"""
        # Create a new schausteller
        unique_email = f"setpw_staff_{uuid.uuid4().hex[:8]}@test.de"
        reg_payload = {
            "firma": f"{TEST_PREFIX}SetPwStaffFirma",
            "name": "SetPw Staff Test",
            "strasse": "Str 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DESETPW2",
            "email": unique_email,
            "password": "initialpass",
            "telefon": "123",
            "rechnungs_email": unique_email
        }
        reg_response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=reg_payload)
        assert reg_response.status_code == 200
        sch_id = reg_response.json()["id"]
        
        # Staff sets password
        new_password = "staffsetpw123"
        set_response = staff_client.post(f"{BASE_URL}/api/kirmes/schausteller/{sch_id}/set-password", json={"password": new_password})
        assert set_response.status_code == 200
    
    def test_set_password_too_short_fails(self, admin_client, api_client):
        """Set password with < 6 chars should fail"""
        # Create schausteller
        unique_email = f"setpw_short_{uuid.uuid4().hex[:8]}@test.de"
        reg_payload = {
            "firma": f"{TEST_PREFIX}SetPwShortFirma",
            "name": "SetPw Short Test",
            "strasse": "Str 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DESETPW3",
            "email": unique_email,
            "password": "initialpass",
            "telefon": "123",
            "rechnungs_email": unique_email
        }
        reg_response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=reg_payload)
        sch_id = reg_response.json()["id"]
        
        # Try to set short password
        short_password = "12345"  # Only 5 chars
        set_response = admin_client.post(f"{BASE_URL}/api/kirmes/schausteller/{sch_id}/set-password", json={"password": short_password})
        assert set_response.status_code == 400
        assert "6" in set_response.json().get("detail", ""), "Error should mention 6 character requirement"
    
    def test_set_password_nonexistent_schausteller_fails(self, admin_client):
        """Set password for non-existent schausteller returns 404"""
        fake_id = f"nonexistent_{uuid.uuid4().hex}"
        set_response = admin_client.post(f"{BASE_URL}/api/kirmes/schausteller/{fake_id}/set-password", json={"password": "somepassword123"})
        assert set_response.status_code == 404
    
    def test_set_password_marks_email_verified(self, admin_client, api_client):
        """Setting password via admin should mark email as verified"""
        # Create unverified schausteller
        unique_email = f"setpw_verify_{uuid.uuid4().hex[:8]}@test.de"
        reg_payload = {
            "firma": f"{TEST_PREFIX}SetPwVerifyFirma",
            "name": "SetPw Verify Test",
            "strasse": "Str 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DESETPW4",
            "email": unique_email,
            "password": "initialpass",
            "telefon": "123",
            "rechnungs_email": unique_email
        }
        reg_response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=reg_payload)
        sch_id = reg_response.json()["id"]
        
        # Try to login before set-password (should fail - not verified)
        login_before = api_client.post(f"{BASE_URL}/api/kirmes/public/login", json={
            "email": unique_email,
            "password": "initialpass"
        })
        assert login_before.status_code == 403, "Should fail login because not verified"
        
        # Admin sets password
        admin_client.post(f"{BASE_URL}/api/kirmes/schausteller/{sch_id}/set-password", json={"password": "adminset123"})
        
        # Now login should work (email verified by set-password)
        login_after = api_client.post(f"{BASE_URL}/api/kirmes/public/login", json={
            "email": unique_email,
            "password": "adminset123"
        })
        assert login_after.status_code == 200, "Should login after admin set password (email now verified)"


# ===================== Booking Confirmation Email Test =====================

class TestBookingConfirmationEmail:
    """Test that signup sends booking confirmation email (no error returned)"""
    
    def test_signup_sends_confirmation_email_no_error(self, api_client, admin_client):
        """Signup for event should send confirmation email (check no API error)"""
        # 1. Create and release an event
        event_payload = {
            "name": f"{TEST_PREFIX}EmailConfirmTest_{uuid.uuid4().hex[:6]}",
            "location": "Email Stadt",
            "start_date": "2027-02-01",
            "end_date": "2027-02-10",
            "use_standard_prices": True
        }
        create_response = admin_client.post(f"{BASE_URL}/api/kirmes/events", json=event_payload)
        assert create_response.status_code == 200
        event_id = create_response.json()["id"]
        
        admin_client.post(f"{BASE_URL}/api/kirmes/events/{event_id}/release")
        
        # 2. Register schausteller with valid email (for email sending)
        unique_email = f"emailconfirm_{uuid.uuid4().hex[:8]}@test.de"
        sch_payload = {
            "firma": f"{TEST_PREFIX}EmailConfirmFirma",
            "name": "Email Confirm Tester",
            "strasse": "Emailstr 1",
            "plz": "50000",
            "ort": "Emailstadt",
            "steuernummer": "DEEMAIL1",
            "email": unique_email,
            "password": "emailpass123",
            "telefon": "555-9999",
            "rechnungs_email": unique_email
        }
        reg_response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=sch_payload)
        assert reg_response.status_code == 200
        schausteller_id = reg_response.json()["id"]
        
        # 3. Sign up for the event (this should trigger confirmation email)
        signup_payload = {
            "event_id": event_id,
            "schausteller_id": schausteller_id,
            "platznummer": "EMAIL1",
            "fahrgeschaeft": "Testriesenrad",
            "connection_type": "32A",
            "payment_method": "kreditkarte"
        }
        
        signup_response = api_client.post(f"{BASE_URL}/api/kirmes/public/signup", json=signup_payload)
        
        # The signup should succeed even if email sending fails (wrapped in try/except)
        assert signup_response.status_code == 200, f"Signup should succeed, got {signup_response.status_code}: {signup_response.text}"
        
        signup_data = signup_response.json()
        assert signup_data["event_id"] == event_id
        assert signup_data["platznummer"] == "EMAIL1"
        # Verify the response contains expected data (email is sent async, but signup succeeds)


# ===================== Cleanup =====================

class TestCleanup:
    """Clean up test data after all tests"""
    
    def test_cleanup_test_events(self, admin_client):
        """Delete test events created during testing"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/events")
        if response.status_code != 200:
            return
        
        events = response.json()
        deleted_count = 0
        
        for event in events:
            if event["name"].startswith(TEST_PREFIX):
                if event["status"] != "entwurf":
                    admin_client.put(f"{BASE_URL}/api/kirmes/events/{event['id']}", json={"status": "entwurf"})
                
                delete_response = admin_client.delete(f"{BASE_URL}/api/kirmes/events/{event['id']}")
                if delete_response.status_code == 200:
                    deleted_count += 1
        
        print(f"Cleaned up {deleted_count} test events")
