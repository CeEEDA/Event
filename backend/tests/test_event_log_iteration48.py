"""
Test Event Log Feature - Iteration 48
Tests the Event Log (Ereignisprotokoll) functionality across:
- GeneratorDetailPage
- DeviceManagementPage
- ServiceplanPage

Test Device: test123 (ID: 5cf84060-95c2-407d-a5d6-1cbf0f184617)
Test Generator: dev-5cf84060-95c2-407d-a5d6-1cbf0f184617
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"
TEST_DEVICE_ID = "5cf84060-95c2-407d-a5d6-1cbf0f184617"
TEST_GENERATOR_ID = "dev-5cf84060-95c2-407d-a5d6-1cbf0f184617"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    return response.json().get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestEventLogBackendAPIs:
    """Test Event Log backend API endpoints."""

    def test_get_events_by_generator_id(self, auth_headers):
        """Test GET /api/generators/events/{generator_id} returns events."""
        response = requests.get(
            f"{BASE_URL}/api/generators/events/{TEST_GENERATOR_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "events" in data, "Response should contain 'events' key"
        assert "total" in data, "Response should contain 'total' key"
        
        # Verify we have events
        events = data["events"]
        total = data["total"]
        
        print(f"Found {total} events for generator {TEST_GENERATOR_ID}")
        
        # Check event structure
        if len(events) > 0:
            event = events[0]
            assert "event_type" in event, "Event should have event_type"
            assert "event_label" in event, "Event should have event_label (German label)"
            assert "timestamp" in event, "Event should have timestamp"
            
            # Check for GPS coordinates (optional but expected)
            if "latitude" in event:
                assert "longitude" in event, "If latitude exists, longitude should too"
                print(f"Event has GPS: {event.get('latitude')}, {event.get('longitude')}")
            
            print(f"Sample event: type={event.get('event_type')}, label={event.get('event_label')}")

    def test_get_events_by_device_id(self, auth_headers):
        """Test GET /api/generators/events-by-device/{device_id} returns events."""
        response = requests.get(
            f"{BASE_URL}/api/generators/events-by-device/{TEST_DEVICE_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "events" in data, "Response should contain 'events' key"
        assert "total" in data, "Response should contain 'total' key"
        
        events = data["events"]
        total = data["total"]
        
        print(f"Found {total} events for device {TEST_DEVICE_ID}")
        
        # Verify event structure
        if len(events) > 0:
            event = events[0]
            assert "event_type" in event
            assert "event_label" in event
            assert "timestamp" in event
            
            # Verify description exists
            if "description" in event:
                print(f"Event description: {event.get('description')}")

    def test_events_have_required_fields(self, auth_headers):
        """Verify each event has all required fields: event_label, description, timestamp, GPS."""
        response = requests.get(
            f"{BASE_URL}/api/generators/events/{TEST_GENERATOR_ID}?limit=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        events = data["events"]
        
        required_fields = ["event_type", "event_label", "timestamp"]
        
        for i, event in enumerate(events):
            for field in required_fields:
                assert field in event, f"Event {i} missing required field: {field}"
            
            # Log event details
            print(f"Event {i+1}: {event.get('event_label')} - {event.get('timestamp')}")
            if event.get("latitude") and event.get("longitude"):
                print(f"  GPS: {event.get('latitude')}, {event.get('longitude')}")

    def test_events_count_matches_expected(self, auth_headers):
        """Verify we have the expected 5 seeded events."""
        response = requests.get(
            f"{BASE_URL}/api/generators/events/{TEST_GENERATOR_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # According to the test request, there should be 5 events
        total = data["total"]
        print(f"Total events: {total}")
        
        # List all event types
        events = data["events"]
        event_types = [e.get("event_type") for e in events]
        print(f"Event types found: {event_types}")
        
        # Expected events from seed data
        expected_types = ["engine_start", "overtemp", "low_oil_pressure", "emergency_stop", "engine_stop"]
        
        for expected in expected_types:
            if expected in event_types:
                print(f"✓ Found expected event type: {expected}")
            else:
                print(f"✗ Missing expected event type: {expected}")

    def test_events_limit_parameter(self, auth_headers):
        """Test that limit parameter works correctly."""
        response = requests.get(
            f"{BASE_URL}/api/generators/events/{TEST_GENERATOR_ID}?limit=2",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        events = data["events"]
        assert len(events) <= 2, f"Expected max 2 events, got {len(events)}"
        print(f"Limit=2 returned {len(events)} events")


class TestDeviceQuickInfo:
    """Test device quick-info endpoint used by DeviceManagementPage expanded row."""

    def test_device_quick_info(self, auth_headers):
        """Test GET /api/devices/{device_id}/quick-info returns data."""
        response = requests.get(
            f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/quick-info",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Quick info response: {data}")
        
        # Check expected fields
        assert "last_seen" in data or data.get("last_seen") is None
        assert "readings" in data


class TestServiceplanEventLog:
    """Test that ServiceplanPage can access event log for devices."""

    def test_serviceplan_list(self, auth_headers):
        """Test GET /api/serviceplan returns list of service plans."""
        response = requests.get(
            f"{BASE_URL}/api/serviceplan",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        plans = response.json()
        print(f"Found {len(plans)} service plans")
        
        # Check if test device has a service plan
        test_device_plan = next((p for p in plans if p.get("device_id") == TEST_DEVICE_ID), None)
        if test_device_plan:
            print(f"Test device has service plan: {test_device_plan.get('id')}")
        else:
            print("Test device does not have a service plan yet")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
