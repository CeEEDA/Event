"""
Test file for Kirmes EMU Meter Integration
Tests: GET /api/kirmes/emu-meters, PUT/DELETE /api/kirmes/signups/{id}/link-meter, GET meter-data
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"

# Known test data from the database
EVENT_WITH_LINKED_METER = "e1fdc56a-cb3f-4ad0-8ae9-586e38a59ac0"  # Küss Kirmes 26
SIGNUP_WITH_LINKED_METER = "d52ab189-28a4-424a-9b81-5421f27a8276"
LINKED_DEVICE_ID = "1d35dfbf-c944-4127-abe6-c0f97ed3b165"
LINKED_METER_ID = "82ae1943-bed4-48b8-9375-0b79a34e49a4"

EVENT_WITHOUT_LINKED_METERS = "20de118d-9be2-42ef-8473-7683b0d7b1af"  # Testkirmes 3/26
SIGNUP_WITHOUT_METER = "d84ed7f9-f8fd-49c8-bb74-be8230fd388a"

# Available meter for linking test
AVAILABLE_DEVICE_ID = "a194a38f-1e60-4fdf-a95f-8c1bc8e8f76b"
AVAILABLE_METER_ID = "765dac53-d9e0-4d1d-ba2a-d4f6d1084293"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ============== EMU Meters List Tests ==============

class TestEmuMetersList:
    """Tests for GET /api/kirmes/emu-meters endpoint."""

    def test_list_emu_meters_returns_200(self, auth_headers):
        """Test that listing EMU meters returns 200."""
        response = requests.get(f"{BASE_URL}/api/kirmes/emu-meters", headers=auth_headers)
        assert response.status_code == 200

    def test_list_emu_meters_returns_array(self, auth_headers):
        """Test that EMU meters response is an array."""
        response = requests.get(f"{BASE_URL}/api/kirmes/emu-meters", headers=auth_headers)
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one meter"

    def test_list_emu_meters_has_required_fields(self, auth_headers):
        """Test that each meter has required fields."""
        response = requests.get(f"{BASE_URL}/api/kirmes/emu-meters", headers=auth_headers)
        data = response.json()
        for meter in data:
            assert "id" in meter, "Meter should have id"
            assert "device_id" in meter, "Meter should have device_id"
            assert "meter_name" in meter, "Meter should have meter_name"
            assert "meter_ip" in meter, "Meter should have meter_ip"

    def test_list_emu_meters_unauthorized_fails(self):
        """Test that unauthorized request fails."""
        response = requests.get(f"{BASE_URL}/api/kirmes/emu-meters")
        assert response.status_code in [401, 403]


# ============== Meter Data Tests ==============

class TestMeterData:
    """Tests for GET /api/kirmes/signups/{id}/meter-data endpoint."""

    def test_get_meter_data_linked_signup(self, auth_headers):
        """Test getting meter data for a signup with linked meter."""
        response = requests.get(
            f"{BASE_URL}/api/kirmes/signups/{SIGNUP_WITH_LINKED_METER}/meter-data",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert data["linked"] == True, "Should be linked"
        assert "meter_name" in data, "Should have meter_name"
        assert data["meter_name"] == "EMU Zähler 1", "Should have correct meter name"
        assert "is_online" in data, "Should have is_online status"
        assert "latest" in data, "Should have latest reading"
        assert "history" in data, "Should have history"

    def test_get_meter_data_has_telemetry_fields(self, auth_headers):
        """Test that latest reading has telemetry fields."""
        response = requests.get(
            f"{BASE_URL}/api/kirmes/signups/{SIGNUP_WITH_LINKED_METER}/meter-data?limit=10",
            headers=auth_headers
        )
        data = response.json()
        latest = data.get("latest")
        
        assert latest is not None, "Should have latest reading"
        # Verify telemetry fields
        assert "P_sum_kW" in latest, "Should have power (P_sum_kW)"
        assert "U_L1" in latest, "Should have voltage (U_L1)"
        assert "I_sum" in latest, "Should have current (I_sum)"
        assert "F_Hz" in latest, "Should have frequency (F_Hz)"
        assert "ts_utc" in latest, "Should have timestamp"

    def test_get_meter_data_unlinked_signup(self, auth_headers):
        """Test getting meter data for a signup without linked meter."""
        response = requests.get(
            f"{BASE_URL}/api/kirmes/signups/{SIGNUP_WITHOUT_METER}/meter-data",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["linked"] == False, "Should not be linked"
        assert data["latest"] is None, "Should have no latest reading"
        assert data["history"] == [], "Should have empty history"

    def test_get_meter_data_invalid_signup_404(self, auth_headers):
        """Test that invalid signup ID returns 404."""
        response = requests.get(
            f"{BASE_URL}/api/kirmes/signups/invalid-signup-id/meter-data",
            headers=auth_headers
        )
        assert response.status_code == 404


# ============== Link Meter Tests ==============

class TestLinkMeter:
    """Tests for PUT /api/kirmes/signups/{id}/link-meter endpoint."""

    def test_link_meter_success(self, auth_headers):
        """Test linking a meter to a signup."""
        # First ensure no meter is linked
        requests.delete(
            f"{BASE_URL}/api/kirmes/signups/{SIGNUP_WITHOUT_METER}/link-meter",
            headers=auth_headers
        )
        
        # Link meter
        response = requests.put(
            f"{BASE_URL}/api/kirmes/signups/{SIGNUP_WITHOUT_METER}/link-meter",
            headers=auth_headers,
            json={
                "emu_device_id": AVAILABLE_DEVICE_ID,
                "emu_meter_id": AVAILABLE_METER_ID
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["emu_device_id"] == AVAILABLE_DEVICE_ID
        assert data["emu_meter_id"] == AVAILABLE_METER_ID
        assert data["emu_meter_name"] == "Shelly Pro 3EM"

    def test_link_meter_updates_signup_data(self, auth_headers):
        """Test that linking meter updates signup in event data."""
        # Verify via meter-data endpoint
        response = requests.get(
            f"{BASE_URL}/api/kirmes/signups/{SIGNUP_WITHOUT_METER}/meter-data",
            headers=auth_headers
        )
        data = response.json()
        
        assert data["linked"] == True
        assert data["meter_name"] == "Shelly Pro 3EM"

    def test_link_meter_invalid_meter_404(self, auth_headers):
        """Test that linking an invalid meter returns 404."""
        response = requests.put(
            f"{BASE_URL}/api/kirmes/signups/{SIGNUP_WITHOUT_METER}/link-meter",
            headers=auth_headers,
            json={
                "emu_device_id": "invalid-device-id",
                "emu_meter_id": "invalid-meter-id"
            }
        )
        assert response.status_code == 404

    def test_link_meter_invalid_signup_404(self, auth_headers):
        """Test that linking to invalid signup returns 404."""
        response = requests.put(
            f"{BASE_URL}/api/kirmes/signups/invalid-signup-id/link-meter",
            headers=auth_headers,
            json={
                "emu_device_id": AVAILABLE_DEVICE_ID,
                "emu_meter_id": AVAILABLE_METER_ID
            }
        )
        assert response.status_code == 404


# ============== Unlink Meter Tests ==============

class TestUnlinkMeter:
    """Tests for DELETE /api/kirmes/signups/{id}/link-meter endpoint."""

    def test_unlink_meter_success(self, auth_headers):
        """Test unlinking a meter from a signup."""
        response = requests.delete(
            f"{BASE_URL}/api/kirmes/signups/{SIGNUP_WITHOUT_METER}/link-meter",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "Verknüpfung entfernt" in data["message"]

    def test_unlink_meter_updates_signup_data(self, auth_headers):
        """Test that unlinking meter updates signup data."""
        # Verify via meter-data endpoint
        response = requests.get(
            f"{BASE_URL}/api/kirmes/signups/{SIGNUP_WITHOUT_METER}/meter-data",
            headers=auth_headers
        )
        data = response.json()
        
        assert data["linked"] == False
        assert data["latest"] is None

    def test_unlink_meter_invalid_signup_404(self, auth_headers):
        """Test that unlinking from invalid signup returns 404."""
        response = requests.delete(
            f"{BASE_URL}/api/kirmes/signups/invalid-signup-id/link-meter",
            headers=auth_headers
        )
        assert response.status_code == 404


# ============== Full Flow Tests ==============

class TestEmuMeterFullFlow:
    """End-to-end tests for the EMU meter integration flow."""

    def test_full_link_unlink_flow(self, auth_headers):
        """Test complete link → verify → unlink → verify flow."""
        signup_id = SIGNUP_WITHOUT_METER
        
        # 1. Ensure clean state
        requests.delete(f"{BASE_URL}/api/kirmes/signups/{signup_id}/link-meter", headers=auth_headers)
        
        # 2. Verify unlinked state
        r = requests.get(f"{BASE_URL}/api/kirmes/signups/{signup_id}/meter-data", headers=auth_headers)
        assert r.json()["linked"] == False, "Should start unlinked"
        
        # 3. Link meter
        r = requests.put(
            f"{BASE_URL}/api/kirmes/signups/{signup_id}/link-meter",
            headers=auth_headers,
            json={"emu_device_id": AVAILABLE_DEVICE_ID, "emu_meter_id": AVAILABLE_METER_ID}
        )
        assert r.status_code == 200, f"Link should succeed: {r.text}"
        
        # 4. Verify linked state
        r = requests.get(f"{BASE_URL}/api/kirmes/signups/{signup_id}/meter-data", headers=auth_headers)
        assert r.json()["linked"] == True, "Should be linked"
        assert r.json()["meter_name"] == "Shelly Pro 3EM"
        
        # 5. Unlink meter
        r = requests.delete(f"{BASE_URL}/api/kirmes/signups/{signup_id}/link-meter", headers=auth_headers)
        assert r.status_code == 200, "Unlink should succeed"
        
        # 6. Verify unlinked state
        r = requests.get(f"{BASE_URL}/api/kirmes/signups/{signup_id}/meter-data", headers=auth_headers)
        assert r.json()["linked"] == False, "Should be unlinked"

    def test_existing_linked_meter_has_data(self, auth_headers):
        """Test that the pre-linked signup has real meter data."""
        response = requests.get(
            f"{BASE_URL}/api/kirmes/signups/{SIGNUP_WITH_LINKED_METER}/meter-data?limit=100",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify has real data
        assert data["linked"] == True
        assert data["meter_name"] == "EMU Zähler 1"
        assert data["latest"] is not None
        assert len(data["history"]) > 0, "Should have historical data"
        
        # Verify data quality
        latest = data["latest"]
        assert latest["P_sum_kW"] >= 0, "Power should be non-negative"
        assert 200 <= latest["U_L1"] <= 250, f"Voltage should be in reasonable range: {latest['U_L1']}"
        assert 49 <= latest["F_Hz"] <= 51, f"Frequency should be around 50Hz: {latest['F_Hz']}"
