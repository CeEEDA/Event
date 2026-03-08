"""
Kirmes Module - Backend API Tests
Tests for Veranstaltungsverwaltung (Event Management) and Schausteller Registration

Connection Types: 16A, 32A, 63A, 125A, Festanschluss
Event Statuses: entwurf, freigegeben, aktiv, abgeschlossen, abgerechnet
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
        response = api_client.get(f"{BASE_URL}/api/kirmes/standard-prices")
        assert response.status_code in [401, 403], "Expected auth error without token"
    
    def test_get_standard_prices_as_staff(self, admin_client):
        """Staff can get standard prices"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/standard-prices")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        # Should have 5 connection types
        connection_types = [p["connection_type"] for p in data]
        assert "16A" in connection_types
        assert "32A" in connection_types
        assert "63A" in connection_types
        assert "125A" in connection_types
        assert "Festanschluss" in connection_types
    
    def test_update_standard_prices_requires_admin(self, staff_client):
        """Only admin can update standard prices"""
        # First get a fresh staff client (re-auth as mitarbeiter)
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
        
        payload = {"prices": [{"connection_type": "16A", "price": 10.0}]}
        response = session.post(f"{BASE_URL}/api/kirmes/standard-prices", json=payload)
        # Mitarbeiter should not be able to update (method not allowed or forbidden)
        assert response.status_code in [403, 405], f"Expected forbidden for mitarbeiter, got {response.status_code}"
    
    def test_update_standard_prices_as_admin(self, admin_client):
        """Admin can update standard prices"""
        # Get current prices first
        get_response = admin_client.get(f"{BASE_URL}/api/kirmes/standard-prices")
        assert get_response.status_code == 200
        original_prices = get_response.json()
        
        # Update prices
        new_prices = [
            {"connection_type": "16A", "price": 50.00},
            {"connection_type": "32A", "price": 100.00},
            {"connection_type": "63A", "price": 200.00},
            {"connection_type": "125A", "price": 350.00},
            {"connection_type": "Festanschluss", "price": 500.00},
        ]
        
        response = admin_client.put(f"{BASE_URL}/api/kirmes/standard-prices", json={"prices": new_prices})
        assert response.status_code == 200
        
        # Verify update persisted
        verify_response = admin_client.get(f"{BASE_URL}/api/kirmes/standard-prices")
        assert verify_response.status_code == 200
        updated_prices = verify_response.json()
        
        for p in updated_prices:
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
        
        # Store for cleanup
        return data
    
    def test_list_events(self, admin_client):
        """List all events"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/events")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        # Should have at least the pre-existing 'Rheinkirmes 2026' event
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
        # First list events to get an ID
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
        # Create an event first
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
        
        # Update it
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
        
        # Verify persistence
        get_response = admin_client.get(f"{BASE_URL}/api/kirmes/events/{event_id}")
        assert get_response.status_code == 200
        assert get_response.json()["location"] == "New Location"


class TestEventRelease:
    """Test event release workflow"""
    
    def test_release_event(self, admin_client):
        """Release event changes status to freigegeben"""
        # Create a new event
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
        
        # Release it
        release_response = admin_client.post(f"{BASE_URL}/api/kirmes/events/{event_id}/release")
        assert release_response.status_code == 200
        
        release_data = release_response.json()
        assert release_data["status"] == "freigegeben"
        
        # Verify event status changed
        get_response = admin_client.get(f"{BASE_URL}/api/kirmes/events/{event_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "freigegeben"
        
        return event_id  # Return for use in public tests


class TestEventDelete:
    """Test event deletion"""
    
    def test_delete_entwurf_event(self, admin_client):
        """Can delete event in entwurf status"""
        # Create an event
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
        
        # Delete it
        delete_response = admin_client.delete(f"{BASE_URL}/api/kirmes/events/{event_id}")
        assert delete_response.status_code == 200
        
        # Verify deleted
        get_response = admin_client.get(f"{BASE_URL}/api/kirmes/events/{event_id}")
        assert get_response.status_code == 404
    
    def test_cannot_delete_aktiv_event(self, admin_client):
        """Cannot delete event in aktiv status"""
        # Create and set to aktiv
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
        
        # Set status to aktiv
        update_response = admin_client.put(f"{BASE_URL}/api/kirmes/events/{event_id}", json={"status": "aktiv"})
        assert update_response.status_code == 200
        
        # Try to delete - should fail
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
        
        # All events should be freigegeben or aktiv
        for event in data:
            assert event["status"] in ["freigegeben", "aktiv"], f"Event {event['name']} has invalid status {event['status']}"
    
    def test_connection_types_endpoint(self, api_client):
        """Get available connection types (public)"""
        response = api_client.get(f"{BASE_URL}/api/kirmes/connection-types")
        assert response.status_code == 200
        
        data = response.json()
        assert "16A" in data
        assert "32A" in data
        assert "63A" in data
        assert "125A" in data
        assert "Festanschluss" in data


class TestSchaustellerRegistration:
    """Test schausteller registration flow"""
    
    def test_register_schausteller(self, api_client):
        """Register new schausteller (public, no auth)"""
        unique_email = f"test_{uuid.uuid4().hex[:8]}@test.de"
        
        payload = {
            "firma": f"{TEST_PREFIX}TestFirma",
            "name": "Max Mustermann",
            "strasse": "Teststraße 123",
            "plz": "40210",
            "ort": "Düsseldorf",
            "steuernummer": "DE123456789",
            "email": unique_email,
            "telefon": "+49 211 123456",
            "rechnungs_email": unique_email
        }
        
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["firma"] == f"{TEST_PREFIX}TestFirma"
        assert data["email"] == unique_email
        assert "id" in data
        
        return data
    
    def test_register_duplicate_email_fails(self, api_client):
        """Cannot register with duplicate email"""
        # Use existing test schausteller email
        payload = {
            "firma": "Duplicate Firma",
            "name": "Hans Test",
            "strasse": "Straße 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DE987654321",
            "email": "hans@test.de",  # Pre-existing test schausteller
            "telefon": "123456",
            "rechnungs_email": "hans@test.de"
        }
        
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=payload)
        assert response.status_code == 400
        assert "bereits registriert" in response.json().get("detail", "").lower()
    
    def test_login_schausteller(self, api_client):
        """Login existing schausteller by email"""
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/login?email=hans@test.de")
        assert response.status_code == 200
        
        data = response.json()
        assert data["email"] == "hans@test.de"
        assert "id" in data
    
    def test_login_nonexistent_email_fails(self, api_client):
        """Login with non-existent email fails"""
        response = api_client.post(f"{BASE_URL}/api/kirmes/public/login?email=nonexistent@test.de")
        assert response.status_code == 404


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
        
        # Release the event
        release_response = admin_client.post(f"{BASE_URL}/api/kirmes/events/{event_id}/release")
        assert release_response.status_code == 200
        
        # 2. Register a new schausteller
        unique_email = f"signup_test_{uuid.uuid4().hex[:8]}@test.de"
        sch_payload = {
            "firma": f"{TEST_PREFIX}SignupFirma",
            "name": "Signup Tester",
            "strasse": "Signupstraße 1",
            "plz": "50000",
            "ort": "Signupstadt",
            "steuernummer": "DE111222333",
            "email": unique_email,
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
        # Create and release an event
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
        
        # Register schausteller
        unique_email = f"invalid_conn_{uuid.uuid4().hex[:8]}@test.de"
        reg_response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json={
            "firma": "Invalid Test",
            "name": "Invalid Tester",
            "strasse": "Str 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DE999",
            "email": unique_email,
            "telefon": "123",
            "rechnungs_email": unique_email
        })
        schausteller_id = reg_response.json()["id"]
        
        # Try invalid connection type
        signup_payload = {
            "event_id": event_id,
            "schausteller_id": schausteller_id,
            "platznummer": "B1",
            "connection_type": "INVALID_TYPE",
            "payment_method": "kreditkarte"
        }
        
        signup_response = api_client.post(f"{BASE_URL}/api/kirmes/public/signup", json=signup_payload)
        assert signup_response.status_code == 400
    
    def test_signup_duplicate_fails(self, api_client, admin_client):
        """Cannot sign up twice for same event"""
        # Create and release event
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
        
        # Register schausteller
        unique_email = f"duplicate_{uuid.uuid4().hex[:8]}@test.de"
        reg_response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json={
            "firma": "Duplicate Firma",
            "name": "Duplicate Tester",
            "strasse": "Str 1",
            "plz": "12345",
            "ort": "Stadt",
            "steuernummer": "DE888",
            "email": unique_email,
            "telefon": "123",
            "rechnungs_email": unique_email
        })
        schausteller_id = reg_response.json()["id"]
        
        # First signup - should succeed
        signup_payload = {
            "event_id": event_id,
            "schausteller_id": schausteller_id,
            "platznummer": "C1",
            "connection_type": "16A",
            "payment_method": "paypal"
        }
        
        first_signup = api_client.post(f"{BASE_URL}/api/kirmes/public/signup", json=signup_payload)
        assert first_signup.status_code == 200
        
        # Second signup - should fail
        signup_payload["platznummer"] = "C2"  # Different platz, same event
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
    
    def test_search_schausteller(self, admin_client):
        """Search schausteller by name/firma/email"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/schausteller?search=hans")
        assert response.status_code == 200


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
                # Set to entwurf first if needed (only entwurf can be deleted)
                if event["status"] != "entwurf":
                    admin_client.put(f"{BASE_URL}/api/kirmes/events/{event['id']}", json={"status": "entwurf"})
                
                delete_response = admin_client.delete(f"{BASE_URL}/api/kirmes/events/{event['id']}")
                if delete_response.status_code == 200:
                    deleted_count += 1
        
        print(f"Cleaned up {deleted_count} test events")
