"""
Test suite for Device Diagnostics Feature - Iteration 51
Tests the new diagnostics endpoint and quick-info meter_id inclusion
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data from the review request
DEVICE_ID = "e9db7cea-9e65-484a-8f47-3e01603da0e9"  # Kirmeskiste_001
METER_ID = "4b5ad9f6-e5f2-41ca-a799-d63c98037323"   # EMU Zaehler 1
DEVICE_WITHOUT_DATA = "d3a24918-5858-444d-bc7a-e94e928e4b3f"  # Kirmeskiste 002


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "password"}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture
def auth_headers(auth_token):
    """Return headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestDiagnosticsEndpoint:
    """Tests for GET /api/devices/{device_id}/meters/{meter_id}/diagnostics"""
    
    def test_diagnostics_returns_10_measurements(self, auth_headers):
        """Diagnostics endpoint returns last 10 raw measurements"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_ID}/meters/{METER_ID}/diagnostics?limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "meter_id" in data
        assert "meter_name" in data
        assert "device_id" in data
        assert "count" in data
        assert "data" in data
        
        # Verify meter info
        assert data["meter_id"] == METER_ID
        assert data["device_id"] == DEVICE_ID
        assert data["meter_name"] == "EMU Zaehler 1"
        
        # Verify count
        assert data["count"] == 10
        assert len(data["data"]) == 10
    
    def test_diagnostics_contains_required_fields(self, auth_headers):
        """Each measurement contains required diagnostic fields"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_ID}/meters/{METER_ID}/diagnostics?limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check first measurement has all required fields
        first_row = data["data"][0]
        
        # Required fields per spec
        assert "ts_utc" in first_row, "Missing ts_utc (timestamp)"
        assert "E_imp_kWh" in first_row, "Missing E_imp_kWh"
        assert "P_sum_kW" in first_row, "Missing P_sum_kW"
        
        # Voltage fields (may be null but should be in projection)
        # These are optional based on data availability
        print(f"First row fields: {list(first_row.keys())}")
    
    def test_diagnostics_sorted_by_timestamp_desc(self, auth_headers):
        """Measurements are sorted by timestamp descending (newest first)"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_ID}/meters/{METER_ID}/diagnostics?limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        timestamps = [row["ts_utc"] for row in data["data"]]
        # Verify descending order
        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1], \
                f"Timestamps not in descending order: {timestamps[i]} < {timestamps[i + 1]}"
    
    def test_diagnostics_response_time(self, auth_headers):
        """Diagnostics endpoint responds fast (under 1 second)"""
        start_time = time.time()
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_ID}/meters/{METER_ID}/diagnostics?limit=10",
            headers=auth_headers
        )
        elapsed = time.time() - start_time
        
        assert response.status_code == 200
        assert elapsed < 1.0, f"Response took {elapsed:.2f}s, expected < 1s"
        print(f"Diagnostics API response time: {elapsed:.3f}s")
    
    def test_diagnostics_invalid_device(self, auth_headers):
        """Returns 404 for non-existent device"""
        response = requests.get(
            f"{BASE_URL}/api/devices/invalid-device-id/meters/{METER_ID}/diagnostics?limit=10",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    def test_diagnostics_invalid_meter(self, auth_headers):
        """Returns 404 for non-existent meter"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_ID}/meters/invalid-meter-id/diagnostics?limit=10",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    def test_diagnostics_requires_auth(self):
        """Diagnostics endpoint requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_ID}/meters/{METER_ID}/diagnostics?limit=10"
        )
        assert response.status_code in [401, 403]


class TestQuickInfoMeterIdInclusion:
    """Tests for meter_id inclusion in quick-info endpoint"""
    
    def test_quick_info_includes_meter_id(self, auth_headers):
        """Quick-info readings include meter_id for each entry"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_ID}/quick-info",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "readings" in data
        assert len(data["readings"]) > 0
        
        # Each reading should have meter_id
        for reading in data["readings"]:
            assert "meter_id" in reading, f"Reading missing meter_id: {reading}"
            assert "label" in reading
            assert "value" in reading
            print(f"Reading: {reading['label']} - meter_id: {reading['meter_id']}")
    
    def test_quick_info_meter_id_matches_diagnostics(self, auth_headers):
        """meter_id from quick-info can be used to call diagnostics"""
        # Get quick-info
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_ID}/quick-info",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Get first meter_id
        first_reading = data["readings"][0]
        meter_id = first_reading["meter_id"]
        
        # Use it to call diagnostics
        diag_response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_ID}/meters/{meter_id}/diagnostics?limit=5",
            headers=auth_headers
        )
        assert diag_response.status_code == 200
        diag_data = diag_response.json()
        assert diag_data["meter_id"] == meter_id


class TestDeviceManagementPage:
    """Tests for device list endpoint"""
    
    def test_devices_list_loads(self, auth_headers):
        """Device list endpoint returns devices"""
        response = requests.get(
            f"{BASE_URL}/api/devices",
            headers=auth_headers
        )
        assert response.status_code == 200
        devices = response.json()
        
        assert isinstance(devices, list)
        assert len(devices) > 0
        
        # Find Kirmeskiste_001
        kirmeskiste = next((d for d in devices if d["serial_number"] == "Kirmeskiste_001"), None)
        assert kirmeskiste is not None, "Kirmeskiste_001 not found in device list"
        assert kirmeskiste["id"] == DEVICE_ID
        print(f"Found Kirmeskiste_001: {kirmeskiste['serial_number']}")
