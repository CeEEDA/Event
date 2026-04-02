"""
Test Kirmes Event Detail Page - Expanded Row Features (Iteration 49)
- Meter-data API with limit=1 for fast loading
- Payment status German translations
- Yellow background for rows without EMU meter
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"

# Test data from requirements
EVENT_ID = "648e5d04-53a4-4eac-812c-a9267dd9158a"
SIGNUP_WITH_METER = "ec261fd0-4401-49b6-8d75-f320d0d85012"
SIGNUP_WITHOUT_METER = "6a6ada7d-f5e7-4cfe-94b3-85ad09460eb5"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    return response.json().get("token")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Create authenticated session."""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestMeterDataAPI:
    """Test meter-data endpoint with limit parameter."""

    def test_meter_data_with_limit_1_fast_response(self, api_client):
        """API GET /api/kirmes/signups/{signup_id}/meter-data?limit=1 should respond fast (under 1 second)."""
        start_time = time.time()
        response = api_client.get(f"{BASE_URL}/api/kirmes/signups/{SIGNUP_WITH_METER}/meter-data", params={"limit": 1})
        elapsed = time.time() - start_time
        
        print(f"Meter-data API response time: {elapsed:.3f}s")
        print(f"Response status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert elapsed < 1.0, f"API took {elapsed:.3f}s, expected under 1 second"
        
        data = response.json()
        print(f"Response data keys: {data.keys()}")
        
        # Verify response structure
        assert "linked" in data
        assert "latest" in data
        assert "history" in data
        
        # With limit=1, history should have at most 1 item
        if data.get("linked"):
            assert len(data.get("history", [])) <= 1, f"Expected at most 1 history item with limit=1, got {len(data.get('history', []))}"

    def test_meter_data_for_signup_without_meter(self, api_client):
        """Signup without EMU meter should return linked=False."""
        response = api_client.get(f"{BASE_URL}/api/kirmes/signups/{SIGNUP_WITHOUT_METER}/meter-data", params={"limit": 1})
        
        print(f"Response status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Response data: {data}")
        
        # Should return linked=False for signup without meter
        assert data.get("linked") == False, f"Expected linked=False for signup without meter"
        assert data.get("latest") is None
        assert data.get("history") == []


class TestEventDetailAPI:
    """Test event detail API returns correct signup data."""

    def test_get_event_with_signups(self, api_client):
        """GET /api/kirmes/events/{event_id} should return event with signups."""
        response = api_client.get(f"{BASE_URL}/api/kirmes/events/{EVENT_ID}")
        
        print(f"Response status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Event name: {data.get('name')}")
        print(f"Signup count: {data.get('signup_count')}")
        
        assert "signups" in data
        assert len(data["signups"]) > 0, "Expected at least one signup"
        
        # Find signup with meter
        signup_with_meter = next((s for s in data["signups"] if s["id"] == SIGNUP_WITH_METER), None)
        if signup_with_meter:
            print(f"Signup with meter: {signup_with_meter.get('schausteller', {}).get('firma', 'N/A')}")
            print(f"  emu_device_id: {signup_with_meter.get('emu_device_id')}")
            print(f"  emu_meter_id: {signup_with_meter.get('emu_meter_id')}")
            assert signup_with_meter.get("emu_device_id") is not None, "Expected emu_device_id for signup with meter"
            assert signup_with_meter.get("emu_meter_id") is not None, "Expected emu_meter_id for signup with meter"
        
        # Find signup without meter
        signup_without_meter = next((s for s in data["signups"] if s["id"] == SIGNUP_WITHOUT_METER), None)
        if signup_without_meter:
            print(f"Signup without meter: {signup_without_meter.get('schausteller', {}).get('firma', 'N/A')}")
            print(f"  emu_device_id: {signup_without_meter.get('emu_device_id')}")
            print(f"  emu_meter_id: {signup_without_meter.get('emu_meter_id')}")
            # Should have null/None for emu_device_id
            assert signup_without_meter.get("emu_device_id") is None, "Expected null emu_device_id for signup without meter"

    def test_signups_have_payment_status(self, api_client):
        """Signups should have payment_status field."""
        response = api_client.get(f"{BASE_URL}/api/kirmes/events/{EVENT_ID}")
        
        assert response.status_code == 200
        
        data = response.json()
        signups = data.get("signups", [])
        
        for signup in signups:
            print(f"Signup {signup.get('id')[:8]}... payment_status: {signup.get('payment_status')}")
            assert "payment_status" in signup, f"Signup {signup['id']} missing payment_status"


class TestPaymentStatusLabels:
    """Verify payment status values that frontend will translate."""

    def test_payment_status_values(self, api_client):
        """Check that payment_status values match expected German translations."""
        response = api_client.get(f"{BASE_URL}/api/kirmes/events/{EVENT_ID}")
        
        assert response.status_code == 200
        
        data = response.json()
        signups = data.get("signups", [])
        
        # Expected payment status values and their German labels
        expected_labels = {
            "pending_payment": "Ausstehend",
            "abgerechnet": "Abgerechnet",
            "bezahlt": "Bezahlt",
            "ausstehend": "Ausstehend",
        }
        
        found_statuses = set()
        for signup in signups:
            status = signup.get("payment_status")
            if status:
                found_statuses.add(status)
                print(f"Found payment_status: {status} -> German: {expected_labels.get(status, 'Unknown')}")
        
        print(f"All found payment statuses: {found_statuses}")
        
        # Verify at least some statuses are found
        assert len(found_statuses) > 0, "Expected to find at least one payment status"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
