"""
Iteration 23 - Energy Monitoring Extended Tests
Tests for: GPS/Location endpoints, Ingest API, Pi sync script download, Account-level time access
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"

# Device IDs from real data
DEVICE_ID_MK001 = "1d35dfbf-c944-4127-abe6-c0f97ed3b165"  # Messkoffer Baustelle A


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def api_headers(admin_token):
    """Headers with admin auth token"""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestGPSLocationEndpoints:
    """Tests for GPS/Location API endpoints"""
    
    def test_get_all_device_locations(self, api_headers):
        """GET /api/energy-monitoring/locations returns GPS coordinates for all devices"""
        resp = requests.get(f"{BASE_URL}/api/energy-monitoring/locations", headers=api_headers)
        assert resp.status_code == 200
        locations = resp.json()
        assert isinstance(locations, list)
        
        # Should have at least one device with GPS data (MK-001)
        if len(locations) > 0:
            loc = locations[0]
            assert "device_id" in loc
            assert "gps_lat" in loc
            assert "gps_lon" in loc
            # Verify coordinates are near Neuwied, Germany (around 50.43 N, 7.42 E)
            if loc.get("gps_lat"):
                assert 50.0 < loc["gps_lat"] < 51.0, "GPS lat should be near 50.43"
                assert 7.0 < loc["gps_lon"] < 8.0, "GPS lon should be near 7.42"
    
    def test_get_single_device_location(self, api_headers):
        """GET /api/energy-monitoring/devices/{id}/location returns latest GPS for one device"""
        resp = requests.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}/location",
            headers=api_headers
        )
        assert resp.status_code == 200
        location = resp.json()
        
        # Should have GPS data
        assert "gps_lat" in location or location == {}
        if location:
            assert "gps_lon" in location
            assert "ts_utc" in location
            # Verify altitude if present
            if location.get("gps_alt_m"):
                assert location["gps_alt_m"] > 0, "Altitude should be positive"
    
    def test_location_returns_power_info(self, api_headers):
        """GET /api/energy-monitoring/locations includes P_sum_kW for map popups"""
        resp = requests.get(f"{BASE_URL}/api/energy-monitoring/locations", headers=api_headers)
        assert resp.status_code == 200
        locations = resp.json()
        
        if len(locations) > 0:
            loc = locations[0]
            assert "P_sum_kW" in loc, "Location should include power info for map popup"


class TestIngestAPI:
    """Tests for HTTPS Ingest API (Pi sync)"""
    
    @pytest.fixture(scope="class")
    def ingest_api_key(self, api_headers):
        """Get or create ingest API key"""
        resp = requests.get(f"{BASE_URL}/api/energy-monitoring/ingest/api-key", headers=api_headers)
        if resp.status_code == 200 and resp.json().get("api_key"):
            return resp.json()["api_key"]
        
        # Generate new key if none exists
        resp = requests.post(f"{BASE_URL}/api/energy-monitoring/ingest/generate-key", headers=api_headers)
        assert resp.status_code == 200
        return resp.json()["api_key"]
    
    @pytest.fixture(scope="class")
    def meter_id(self, api_headers):
        """Get meter ID for MK-001"""
        resp = requests.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}/meters",
            headers=api_headers
        )
        assert resp.status_code == 200
        meters = resp.json()
        assert len(meters) > 0, "MK-001 should have at least one meter"
        return meters[0]["id"]
    
    def test_get_sync_state(self, ingest_api_key, meter_id):
        """GET /api/energy-monitoring/ingest/sync-state returns last_sync_id"""
        resp = requests.get(
            f"{BASE_URL}/api/energy-monitoring/ingest/sync-state",
            params={
                "device_id": DEVICE_ID_MK001,
                "meter_id": meter_id,
                "api_key": ingest_api_key
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "last_sync_id" in data
        assert isinstance(data["last_sync_id"], int)
    
    def test_sync_state_requires_api_key(self, meter_id):
        """GET /api/energy-monitoring/ingest/sync-state fails without API key"""
        resp = requests.get(
            f"{BASE_URL}/api/energy-monitoring/ingest/sync-state",
            params={
                "device_id": DEVICE_ID_MK001,
                "meter_id": meter_id,
                "api_key": "invalid-key"
            }
        )
        assert resp.status_code == 401
    
    def test_ingest_batch_data(self, ingest_api_key, meter_id):
        """POST /api/energy-monitoring/ingest accepts batch data"""
        test_ts = datetime.utcnow().isoformat() + "Z"
        resp = requests.post(
            f"{BASE_URL}/api/energy-monitoring/ingest",
            json={
                "api_key": ingest_api_key,
                "device_id": DEVICE_ID_MK001,
                "meter_id": meter_id,
                "records": [
                    {
                        "ts_utc": test_ts,
                        "meter_ts": int(datetime.utcnow().timestamp()),
                        "I_L1": 10.5,
                        "I_L2": 11.2,
                        "I_L3": 9.8,
                        "I_sum": 31.5,
                        "U_L1": 230.1,
                        "U_L2": 230.5,
                        "U_L3": 229.8,
                        "F_Hz": 50.02,
                        "P_sum_kW": 7.25,
                        "gps_lat": 50.432,
                        "gps_lon": 7.427,
                        "gps_alt_m": 63.0,
                        "id": 100001
                    }
                ],
                "last_sync_id": 100001
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["inserted"] == 1
        assert "Datensätze empfangen" in data["message"]
    
    def test_ingest_requires_api_key(self, meter_id):
        """POST /api/energy-monitoring/ingest fails without valid API key"""
        resp = requests.post(
            f"{BASE_URL}/api/energy-monitoring/ingest",
            json={
                "api_key": "invalid-key",
                "device_id": DEVICE_ID_MK001,
                "meter_id": meter_id,
                "records": []
            }
        )
        assert resp.status_code == 401
    
    def test_ingest_empty_batch_returns_message(self, ingest_api_key, meter_id):
        """POST /api/energy-monitoring/ingest with empty records returns appropriate message"""
        resp = requests.post(
            f"{BASE_URL}/api/energy-monitoring/ingest",
            json={
                "api_key": ingest_api_key,
                "device_id": DEVICE_ID_MK001,
                "meter_id": meter_id,
                "records": []
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["inserted"] == 0
    
    def test_generate_api_key_admin_only(self, api_headers):
        """POST /api/energy-monitoring/ingest/generate-key requires admin auth"""
        resp = requests.post(
            f"{BASE_URL}/api/energy-monitoring/ingest/generate-key",
            headers=api_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "api_key" in data
        assert len(data["api_key"]) == 32  # UUID without dashes


class TestPiSyncScript:
    """Tests for Pi sync script download endpoint"""
    
    def test_download_sync_script(self):
        """GET /api/download-sync-script returns Python script"""
        resp = requests.get(f"{BASE_URL}/api/download-sync-script")
        assert resp.status_code == 200
        
        # Check content type
        assert "python" in resp.headers.get("content-type", "").lower() or \
               "text" in resp.headers.get("content-type", "").lower()
        
        # Check content is valid Python script
        content = resp.text
        assert "#!/usr/bin/env python3" in content
        assert "EMU Pi Sync Script" in content
        assert "def main():" in content
        assert "API_URL" in content
        assert "API_KEY" in content


class TestAccountLevelTimeAccess:
    """Tests for account-level time-based access control"""
    
    @pytest.fixture(scope="class")
    def test_kunde_id(self, api_headers):
        """Get or create test kunde user"""
        # Get users list
        resp = requests.get(f"{BASE_URL}/api/users", headers=api_headers)
        assert resp.status_code == 200
        users = resp.json()
        
        # Find a kunde user
        kunde = next((u for u in users if u["role"] == "kunde"), None)
        if kunde:
            return kunde["id"]
        pytest.skip("No kunde user available for testing")
    
    def test_user_response_includes_access_fields(self, api_headers, test_kunde_id):
        """GET /api/users returns access_type, access_start, access_end fields"""
        resp = requests.get(f"{BASE_URL}/api/users", headers=api_headers)
        assert resp.status_code == 200
        users = resp.json()
        
        kunde = next((u for u in users if u["id"] == test_kunde_id), None)
        assert kunde is not None
        
        # Check access fields exist (may be null/permanent)
        assert "access_type" in kunde
        assert kunde["access_type"] in ["permanent", "temporary", None]
    
    def test_update_user_temporary_access(self, api_headers, test_kunde_id):
        """PUT /api/users/:id updates access_type to temporary with dates"""
        start_date = datetime.utcnow().isoformat() + "Z"
        end_date = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"
        
        resp = requests.put(
            f"{BASE_URL}/api/users/{test_kunde_id}",
            headers=api_headers,
            json={
                "access_type": "temporary",
                "access_start": start_date,
                "access_end": end_date
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["access_type"] == "temporary"
        assert data["access_start"] is not None
        assert data["access_end"] is not None
    
    def test_update_user_permanent_access(self, api_headers, test_kunde_id):
        """PUT /api/users/:id can reset to permanent access"""
        resp = requests.put(
            f"{BASE_URL}/api/users/{test_kunde_id}",
            headers=api_headers,
            json={
                "access_type": "permanent",
                "access_start": None,
                "access_end": None
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["access_type"] == "permanent"


class TestTelemetryWithRealData:
    """Tests verifying real EMU data (34,277 records from emu.db)"""
    
    def test_telemetry_has_data(self, api_headers):
        """GET telemetry returns records for MK-001"""
        resp = requests.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}/telemetry",
            headers=api_headers,
            params={"limit": 100}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0, "MK-001 should have telemetry data"
    
    def test_telemetry_includes_gps_fields(self, api_headers):
        """Telemetry records include GPS data from real EMU import"""
        resp = requests.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}/telemetry",
            headers=api_headers,
            params={"limit": 10}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # At least some records should have GPS data
        has_gps = any(r.get("gps_lat") is not None for r in data)
        assert has_gps, "Real EMU data should include GPS coordinates"
    
    def test_alle_daten_time_range_works(self, api_headers):
        """Requesting all data (no time filter) returns historical data"""
        # Request without time filter should return all data
        resp = requests.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}/telemetry",
            headers=api_headers,
            params={"limit": 2000}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Real data is from Feb 18-19, 2026
        if len(data) > 0:
            # Check we have historical data, not just today's
            timestamps = [r.get("ts_utc") for r in data if r.get("ts_utc")]
            if timestamps:
                oldest = min(timestamps)
                # Should have data older than today
                assert "2026-02" in oldest or "2026-03" in oldest


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
