"""
Test suite for Meter Diagnostics Detail Page - Iteration 52
Tests the new MeterDiagnosticsPage at /devices/:deviceId/meters/:meterId

Features tested:
- Backend GET /api/devices/{device_id}/meters/{meter_id}/diagnostics with date filters
- Backend GET /api/devices/{device_id}/meters/{meter_id}/history for assignment history
- Diagnostics endpoint works for devices NOT in devices collection (only emu_meters)
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data
DEVICE_WITH_DATA = "e9db7cea-9e65-484a-8f47-3e01603da0e9"
METER_WITH_DATA = "4b5ad9f6-e5f2-41ca-a799-d63c98037323"

DEVICE_WITH_HISTORY = "1d35dfbf-c944-4127-abe6-c0f97ed3b165"
METER_WITH_HISTORY = "82ae1943-bed4-48b8-9375-0b79a34e49a4"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "password"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestDiagnosticsEndpoint:
    """Tests for GET /api/devices/{device_id}/meters/{meter_id}/diagnostics"""
    
    def test_diagnostics_returns_data(self, auth_headers):
        """Test that diagnostics endpoint returns measurement data"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_DATA}/meters/{METER_WITH_DATA}/diagnostics",
            headers=auth_headers,
            params={"limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "meter_id" in data
        assert "meter_name" in data
        assert "device_id" in data
        assert "count" in data
        assert "data" in data
        assert data["meter_id"] == METER_WITH_DATA
    
    def test_diagnostics_with_date_filter(self, auth_headers):
        """Test that date filter works correctly"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_DATA}/meters/{METER_WITH_DATA}/diagnostics",
            headers=auth_headers,
            params={
                "date_from": "2026-03-25",
                "date_to": "2026-03-28",
                "limit": 50
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["count"] > 0, "Expected data in date range 2026-03-25 to 2026-03-28"
        
        # Verify all data is within date range
        for row in data["data"]:
            ts = row.get("ts_utc", "")
            assert ts >= "2026-03-25", f"Timestamp {ts} is before date_from"
            assert ts <= "2026-03-29", f"Timestamp {ts} is after date_to"
    
    def test_diagnostics_returns_required_fields(self, auth_headers):
        """Test that diagnostics returns all required measurement fields"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_DATA}/meters/{METER_WITH_DATA}/diagnostics",
            headers=auth_headers,
            params={"date_from": "2026-03-25", "date_to": "2026-03-28", "limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["count"] > 0, "Need data to verify fields"
        
        first_row = data["data"][0]
        required_fields = ["ts_utc", "E_imp_kWh", "P_sum_kW", "U_L1", "U_L2", "U_L3", 
                          "I_L1", "I_L2", "I_L3", "I_sum", "F_Hz"]
        
        for field in required_fields:
            assert field in first_row, f"Missing required field: {field}"
    
    def test_diagnostics_sorted_descending(self, auth_headers):
        """Test that data is sorted by timestamp descending (newest first)"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_DATA}/meters/{METER_WITH_DATA}/diagnostics",
            headers=auth_headers,
            params={"date_from": "2026-03-25", "date_to": "2026-03-28", "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] >= 2:
            timestamps = [row["ts_utc"] for row in data["data"]]
            assert timestamps == sorted(timestamps, reverse=True), "Data should be sorted descending"
    
    def test_diagnostics_invalid_device(self, auth_headers):
        """Test that invalid device returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/devices/invalid-device-id/meters/{METER_WITH_DATA}/diagnostics",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    def test_diagnostics_invalid_meter(self, auth_headers):
        """Test that invalid meter returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_DATA}/meters/invalid-meter-id/diagnostics",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    def test_diagnostics_requires_auth(self):
        """Test that diagnostics endpoint requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_DATA}/meters/{METER_WITH_DATA}/diagnostics"
        )
        assert response.status_code in [401, 403]


class TestHistoryEndpoint:
    """Tests for GET /api/devices/{device_id}/meters/{meter_id}/history"""
    
    def test_history_returns_assignments(self, auth_headers):
        """Test that history endpoint returns assignment data"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_HISTORY}/meters/{METER_WITH_HISTORY}/history",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "meter_id" in data
        assert "meter_name" in data
        assert "assignments" in data
        assert len(data["assignments"]) > 0, "Expected at least one assignment"
    
    def test_history_assignment_fields(self, auth_headers):
        """Test that assignment contains all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_HISTORY}/meters/{METER_WITH_HISTORY}/history",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["assignments"]) > 0
        assignment = data["assignments"][0]
        
        required_fields = [
            "event_name", "event_start", "event_end", "firma", "kunde",
            "fahrgeschaeft", "platznummer", "kwh_einbau", "kwh_ausbau",
            "kwh_used", "invoice_number", "is_current"
        ]
        
        for field in required_fields:
            assert field in assignment, f"Missing required field: {field}"
    
    def test_history_assignment_values(self, auth_headers):
        """Test that assignment has expected values"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_HISTORY}/meters/{METER_WITH_HISTORY}/history",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assignment = data["assignments"][0]
        
        # Verify expected values from test data
        assert assignment["event_name"] == "Herbstkirmes Musterstadt 2026"
        assert assignment["platznummer"] == "A12"
        assert assignment["kwh_used"] == 500.5
        assert assignment["invoice_number"] == "R26-K-0001"
    
    def test_history_requires_auth(self):
        """Test that history endpoint requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_HISTORY}/meters/{METER_WITH_HISTORY}/history"
        )
        assert response.status_code in [401, 403]


class TestDiagnosticsForDeviceNotInCollection:
    """Test that diagnostics works for devices only in emu_meters (not in devices collection)"""
    
    def test_diagnostics_works_without_device_record(self, auth_headers):
        """Test diagnostics endpoint works even when device is not in devices collection"""
        # Device 1d35dfbf-c944-4127-abe6-c0f97ed3b165 is NOT in devices collection
        # but has emu_meters records
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_HISTORY}/meters/{METER_WITH_HISTORY}/diagnostics",
            headers=auth_headers,
            params={"limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "meter_id" in data
        assert "meter_name" in data
        assert data["meter_id"] == METER_WITH_HISTORY
    
    def test_history_works_without_device_record(self, auth_headers):
        """Test history endpoint works even when device is not in devices collection"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_HISTORY}/meters/{METER_WITH_HISTORY}/history",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "assignments" in data
        assert len(data["assignments"]) > 0


class TestDateFilterEdgeCases:
    """Test date filter edge cases"""
    
    def test_empty_date_range(self, auth_headers):
        """Test that empty date range returns no data"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_DATA}/meters/{METER_WITH_DATA}/diagnostics",
            headers=auth_headers,
            params={
                "date_from": "2020-01-01",
                "date_to": "2020-01-02",
                "limit": 50
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
    
    def test_no_date_filter(self, auth_headers):
        """Test that no date filter returns recent data"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{DEVICE_WITH_DATA}/meters/{METER_WITH_DATA}/diagnostics",
            headers=auth_headers,
            params={"limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        # Should return some data (default behavior)
        assert "data" in data
