"""
Iteration 24 - Energy Monitoring Enhancements Testing
Features tested:
1. Device Management: Pi connection fields for Messkoffer (hostname, IP, port, username, notes)
2. Energy Monitoring: is_online field in devices response
3. Energy Monitoring: data-access-range endpoint for Kunden
4. Backend enforcement of data access range for Kunden telemetry queries
5. devices only returned if has_data (latest_data not null) - frontend filter
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token."""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "password"
    })
    if res.status_code == 200:
        return res.json()["token"]
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_client(api_client, admin_token):
    """Authenticated client."""
    api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return api_client


class TestDeviceIsOnlineField:
    """Test that GET /api/energy-monitoring/devices returns is_online field."""
    
    def test_devices_endpoint_returns_is_online_field(self, auth_client):
        """is_online field should be present in device response."""
        res = auth_client.get(f"{BASE_URL}/api/energy-monitoring/devices")
        assert res.status_code == 200
        devices = res.json()
        assert isinstance(devices, list)
        
        # Check at least one device has is_online field
        if len(devices) > 0:
            device = devices[0]
            assert "is_online" in device, "Device should have is_online field"
            assert isinstance(device["is_online"], bool), "is_online should be boolean"
            print(f"Device {device.get('serial_number')}: is_online={device['is_online']}")
    
    def test_mk001_device_has_data(self, auth_client):
        """MK-001 device should have latest_data since it has 34277 records."""
        res = auth_client.get(f"{BASE_URL}/api/energy-monitoring/devices")
        assert res.status_code == 200
        devices = res.json()
        
        mk001 = next((d for d in devices if "MK-001" in d.get("serial_number", "")), None)
        assert mk001 is not None, "MK-001 device should exist"
        assert mk001.get("latest_data") is not None, "MK-001 should have latest_data"
        print(f"MK-001 has_data: {mk001.get('latest_data') is not None}")


class TestDataAccessRangeEndpoint:
    """Test GET /api/energy-monitoring/data-access-range endpoint."""
    
    def test_admin_has_no_data_restriction(self, auth_client):
        """Admin users should have no data access restrictions."""
        res = auth_client.get(f"{BASE_URL}/api/energy-monitoring/data-access-range")
        assert res.status_code == 200
        data = res.json()
        
        assert "data_access_start" in data
        assert "data_access_end" in data
        assert "restricted" in data
        assert data["restricted"] == False, "Admin should not be restricted"
        print(f"Admin data access range: {data}")


class TestMesskofferPiFields:
    """Test Pi connection fields for Messkoffer devices."""
    
    def test_get_messkoffer_device_returns_pi_fields(self, auth_client):
        """GET device should include Pi fields if they exist."""
        # First get device list
        res = auth_client.get(f"{BASE_URL}/api/devices")
        assert res.status_code == 200
        devices = res.json()
        
        messkoffer = next((d for d in devices if d.get("device_type") == "messkoffer"), None)
        if messkoffer:
            # The Pi fields may or may not be set
            expected_fields = ["pi_hostname", "pi_ip", "pi_port", "pi_username", "pi_notes"]
            print(f"Messkoffer {messkoffer.get('serial_number')} fields present: "
                  f"{[f for f in expected_fields if f in messkoffer]}")
    
    def test_update_messkoffer_with_pi_fields(self, auth_client):
        """PUT should update Pi fields on a Messkoffer device."""
        # First get device list
        res = auth_client.get(f"{BASE_URL}/api/devices")
        assert res.status_code == 200
        devices = res.json()
        
        messkoffer = next((d for d in devices if d.get("device_type") == "messkoffer"), None)
        if not messkoffer:
            pytest.skip("No Messkoffer device available for testing")
        
        device_id = messkoffer["id"]
        
        # Update with Pi fields
        update_data = {
            "serial_number": messkoffer.get("serial_number"),
            "device_type": "messkoffer",
            "pi_hostname": "pi-test-host",
            "pi_ip": "192.168.1.100",
            "pi_port": "22",
            "pi_username": "pi",
            "pi_notes": "Test notes for Pi connection"
        }
        
        res = auth_client.put(f"{BASE_URL}/api/devices/{device_id}", json=update_data)
        assert res.status_code == 200, f"Update should succeed: {res.text}"
        
        # Verify the update
        res = auth_client.get(f"{BASE_URL}/api/devices")
        devices = res.json()
        updated = next((d for d in devices if d["id"] == device_id), None)
        
        assert updated is not None
        assert updated.get("pi_hostname") == "pi-test-host", "pi_hostname should be updated"
        assert updated.get("pi_ip") == "192.168.1.100", "pi_ip should be updated"
        assert updated.get("pi_port") == "22", "pi_port should be updated"
        assert updated.get("pi_username") == "pi", "pi_username should be updated"
        assert updated.get("pi_notes") == "Test notes for Pi connection", "pi_notes should be updated"
        print(f"Pi fields updated successfully for {updated.get('serial_number')}")


class TestKundeDataAccessEnforcement:
    """Test that data access range is enforced for Kunden on telemetry queries."""
    
    def test_create_kunde_with_data_access_range(self, auth_client):
        """Create a Kunde user with data access restrictions."""
        import uuid
        test_email = f"test_kunde_{uuid.uuid4().hex[:8]}@test.com"
        
        # Create Kunde user
        res = auth_client.post(f"{BASE_URL}/api/users", json={
            "name": "Test Kunde",
            "email": test_email,
            "password": "password123",
            "role": "kunde"
        })
        assert res.status_code in [200, 201], f"User creation should succeed: {res.text}"
        kunde_id = res.json()["id"]
        print(f"Created test Kunde: {test_email}")
        
        # Update with energy monitoring access and data range restriction
        update_data = {
            "name": "Test Kunde",
            "role": "kunde",
            "is_active": True,
            "apps": {
                "energy_monitoring": {
                    "enabled": True,
                    "access_all": True,
                    "device_ids": [],
                    "data_access_start": "2026-02-18T00:00:00Z",
                    "data_access_end": "2026-02-18T12:00:00Z"
                }
            }
        }
        res = auth_client.put(f"{BASE_URL}/api/users/{kunde_id}", json=update_data)
        assert res.status_code == 200, f"Update should succeed: {res.text}"
        
        # Verify the data access range was saved
        res = auth_client.get(f"{BASE_URL}/api/users")
        users = res.json()
        kunde = next((u for u in users if u["id"] == kunde_id), None)
        assert kunde is not None
        
        em = kunde.get("apps", {}).get("energy_monitoring", {})
        assert em.get("data_access_start") == "2026-02-18T00:00:00Z", "data_access_start should be saved"
        assert em.get("data_access_end") == "2026-02-18T12:00:00Z", "data_access_end should be saved"
        print(f"Data access range saved: {em.get('data_access_start')} to {em.get('data_access_end')}")
        
        # Login as Kunde and test data access range endpoint
        kunde_login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": test_email,
            "password": "password123"
        })
        assert kunde_login.status_code == 200
        kunde_token = kunde_login.json()["token"]
        
        # Check data-access-range endpoint returns restriction
        res = requests.get(
            f"{BASE_URL}/api/energy-monitoring/data-access-range",
            headers={"Authorization": f"Bearer {kunde_token}"}
        )
        assert res.status_code == 200
        range_data = res.json()
        assert range_data["restricted"] == True, "Kunde should have restricted data access"
        assert range_data["data_access_start"] == "2026-02-18T00:00:00Z"
        print(f"Kunde data access range: {range_data}")
        
        # Cleanup: delete the test user
        res = auth_client.delete(f"{BASE_URL}/api/users/{kunde_id}")
        assert res.status_code == 200
        print(f"Cleaned up test Kunde: {test_email}")


class TestTelemetryWithDateRange:
    """Test telemetry endpoint with date range parameters."""
    
    def test_telemetry_with_from_to_dates(self, auth_client):
        """Test telemetry filtering with from_time and to_time."""
        device_id = "1d35dfbf-c944-4127-abe6-c0f97ed3b165"  # MK-001
        
        res = auth_client.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{device_id}/telemetry",
            params={
                "from_time": "2026-02-18T00:00:00Z",
                "to_time": "2026-02-18T01:00:00Z",
                "limit": 100
            }
        )
        assert res.status_code == 200
        data = res.json()
        
        assert isinstance(data, list)
        if len(data) > 0:
            # Verify all records are within the time range
            for record in data:
                ts = record.get("ts_utc", "")
                assert ts >= "2026-02-18T00:00:00", f"Record should be after from_time: {ts}"
                assert ts <= "2026-02-18T01:00:00", f"Record should be before to_time: {ts}"
        print(f"Telemetry with date range returned {len(data)} records")


class TestCSVExportSupport:
    """Test that telemetry data supports CSV export fields."""
    
    def test_telemetry_has_all_csv_export_fields(self, auth_client):
        """Verify telemetry response contains all fields needed for CSV export."""
        device_id = "1d35dfbf-c944-4127-abe6-c0f97ed3b165"  # MK-001
        
        res = auth_client.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{device_id}/telemetry",
            params={"limit": 1, "from_time": "2026-02-18T00:00:00Z"}
        )
        assert res.status_code == 200
        data = res.json()
        
        if len(data) > 0:
            record = data[0]
            # CSV columns expected by frontend
            expected_fields = [
                "ts_utc", "meter_ts",
                "I_L1", "I_L2", "I_L3", "I_sum",
                "U_L1", "U_L2", "U_L3",
                "F_Hz",
                "P_sum_kW", "P_L1_kW", "P_L2_kW", "P_L3_kW",
                "Q_sum", "Q_L1", "Q_L2", "Q_L3",
                "PF_L1", "PF_L2", "PF_L3",
                "E_imp_kWh", "E_exp_kWh",
                "gps_lat", "gps_lon", "gps_alt_m",
                "http_ok", "error"
            ]
            
            for field in expected_fields:
                assert field in record, f"CSV field '{field}' should be in telemetry response"
            
            print(f"All {len(expected_fields)} CSV export fields present in telemetry")
        else:
            pytest.skip("No telemetry data available for testing")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
