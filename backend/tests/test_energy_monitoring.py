"""
Energy Monitoring API Tests - Iteration 22
Tests for the Energy Monitoring feature for Messkoffer devices:
- Device listing, detail, telemetry endpoints
- Permission checking (enabled/disabled, time-based access)
- Admin permission management via user update
- Seed demo data endpoint
"""
import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"
KUNDE_EMAIL = "kunde@test.com"
KUNDE_PASSWORD = "password"


class TestSetup:
    """Setup: Get auth tokens and basic info"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert res.status_code == 200, f"Admin login failed: {res.text}"
        return res.json()["token"]
    
    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    @pytest.fixture(scope="class")
    def kunde_token(self):
        """Get or create kunde user and get token"""
        # Try to login
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": KUNDE_EMAIL,
            "password": KUNDE_PASSWORD
        })
        if res.status_code == 200:
            return res.json()["token"]
        # If login fails, kunde doesn't exist - return None
        return None
    
    @pytest.fixture(scope="class")
    def kunde_headers(self, kunde_token):
        if kunde_token:
            return {"Authorization": f"Bearer {kunde_token}"}
        return None


class TestEnergyMonitoringDevicesEndpoint:
    """Test GET /api/energy-monitoring/devices endpoint"""
    
    def test_admin_can_list_energy_devices(self):
        """Admin should be able to list Messkoffer devices"""
        # Login as admin
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        assert login_res.status_code == 200
        token = login_res.json()["token"]
        
        # Get energy devices
        res = requests.get(
            f"{BASE_URL}/api/energy-monitoring/devices",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200, f"Failed: {res.text}"
        devices = res.json()
        assert isinstance(devices, list)
        print(f"Found {len(devices)} Messkoffer devices")
        
        # Verify device structure if devices exist
        if len(devices) > 0:
            device = devices[0]
            assert "id" in device
            assert "serial_number" in device
            assert "device_type" in device or device.get("device_type") == "messkoffer"
            assert "meter_count" in device
            print(f"First device: {device.get('serial_number')}, meters: {device.get('meter_count')}")
    
    def test_user_without_energy_monitoring_gets_403(self):
        """User without energy_monitoring enabled should get 403"""
        # Login as kunde (who doesn't have energy_monitoring enabled by default)
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": KUNDE_EMAIL, "password": KUNDE_PASSWORD
        })
        if login_res.status_code != 200:
            pytest.skip("Kunde user not available for testing")
        
        token = login_res.json()["token"]
        user = login_res.json()["user"]
        
        # Check if energy_monitoring is disabled for this user
        em_enabled = user.get("apps", {}).get("energy_monitoring", {}).get("enabled", False)
        if em_enabled:
            pytest.skip("Kunde already has energy_monitoring enabled")
        
        # Try to access energy devices
        res = requests.get(
            f"{BASE_URL}/api/energy-monitoring/devices",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
        print(f"Correctly blocked user without energy_monitoring access")


class TestEnergyMonitoringDeviceDetail:
    """Test GET /api/energy-monitoring/devices/{device_id} endpoint"""
    
    def test_admin_can_get_device_detail(self):
        """Admin should be able to get device details"""
        # Login as admin
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # First get device list
        list_res = requests.get(f"{BASE_URL}/api/energy-monitoring/devices", headers=headers)
        devices = list_res.json()
        
        if len(devices) == 0:
            pytest.skip("No Messkoffer devices available for testing")
        
        device_id = devices[0]["id"]
        
        # Get device detail
        res = requests.get(f"{BASE_URL}/api/energy-monitoring/devices/{device_id}", headers=headers)
        assert res.status_code == 200, f"Failed: {res.text}"
        
        device = res.json()
        assert device["id"] == device_id
        assert "meters" in device  # Detail includes meters list
        print(f"Device detail: {device.get('serial_number')}, meters: {len(device.get('meters', []))}")
    
    def test_nonexistent_device_returns_404(self):
        """Requesting a nonexistent device should return 404"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        token = login_res.json()["token"]
        
        res = requests.get(
            f"{BASE_URL}/api/energy-monitoring/devices/nonexistent-device-id",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"


class TestEnergyMonitoringTelemetry:
    """Test telemetry endpoints"""
    
    def test_get_device_telemetry(self):
        """Admin should be able to get telemetry data"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get devices
        list_res = requests.get(f"{BASE_URL}/api/energy-monitoring/devices", headers=headers)
        devices = list_res.json()
        
        if len(devices) == 0:
            pytest.skip("No Messkoffer devices available")
        
        device_id = devices[0]["id"]
        
        # Get telemetry
        res = requests.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{device_id}/telemetry",
            headers=headers,
            params={"limit": 100}
        )
        assert res.status_code == 200, f"Failed: {res.text}"
        
        data = res.json()
        assert isinstance(data, list)
        print(f"Got {len(data)} telemetry records for device {device_id}")
        
        # Verify telemetry structure if data exists
        if len(data) > 0:
            record = data[0]
            # Check for expected EMU data fields
            expected_fields = ["ts_utc", "device_id"]
            for field in expected_fields:
                assert field in record, f"Missing field: {field}"
            print(f"Telemetry fields present: {list(record.keys())[:10]}...")
    
    def test_get_latest_telemetry_per_meter(self):
        """Get latest telemetry data per meter"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get devices
        list_res = requests.get(f"{BASE_URL}/api/energy-monitoring/devices", headers=headers)
        devices = list_res.json()
        
        if len(devices) == 0:
            pytest.skip("No Messkoffer devices available")
        
        device_id = devices[0]["id"]
        
        # Get latest per meter
        res = requests.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{device_id}/telemetry/latest",
            headers=headers
        )
        assert res.status_code == 200, f"Failed: {res.text}"
        
        data = res.json()
        assert isinstance(data, list)
        print(f"Got latest data for {len(data)} meters")
        
        # Verify structure
        if len(data) > 0:
            item = data[0]
            assert "meter" in item
            assert "latest" in item
            print(f"Meter: {item['meter'].get('meter_name')}, has_data: {item['latest'] is not None}")


class TestSeedDemoData:
    """Test seed demo data endpoint"""
    
    def test_admin_can_seed_demo_data(self):
        """Admin should be able to seed demo data"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Seed demo data
        res = requests.post(f"{BASE_URL}/api/energy-monitoring/seed-demo", headers=headers)
        assert res.status_code == 200, f"Failed: {res.text}"
        
        result = res.json()
        assert "message" in result
        print(f"Seed demo result: {result}")


class TestAdminPermissionManagement:
    """Test admin updating user permissions for Energy Monitoring"""
    
    def test_admin_can_update_user_energy_monitoring_permissions(self):
        """Admin should be able to enable/disable energy_monitoring for a user"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get list of users
        users_res = requests.get(f"{BASE_URL}/api/users", headers=headers)
        assert users_res.status_code == 200
        users = users_res.json()
        
        # Find a kunde user
        kunde_users = [u for u in users if u["role"] == "kunde"]
        if not kunde_users:
            pytest.skip("No kunde users available for testing")
        
        test_user = kunde_users[0]
        user_id = test_user["id"]
        
        # Get current apps config
        current_apps = test_user.get("apps", {})
        current_em = current_apps.get("energy_monitoring", {})
        
        # Toggle the enabled state
        new_enabled = not current_em.get("enabled", False)
        
        # Update user with new energy_monitoring config
        update_payload = {
            "apps": {
                **current_apps,
                "energy_monitoring": {
                    "enabled": new_enabled,
                    "access_all": True,
                    "device_ids": [],
                    "access_type": "permanent",
                    "access_start": None,
                    "access_end": None
                }
            }
        }
        
        update_res = requests.put(
            f"{BASE_URL}/api/users/{user_id}",
            headers=headers,
            json=update_payload
        )
        assert update_res.status_code == 200, f"Update failed: {update_res.text}"
        
        updated_user = update_res.json()
        updated_em = updated_user.get("apps", {}).get("energy_monitoring", {})
        assert updated_em.get("enabled") == new_enabled, "Energy monitoring enabled state not updated"
        print(f"Successfully updated user {test_user['email']} energy_monitoring.enabled to {new_enabled}")
        
        # Restore original state
        restore_payload = {
            "apps": {
                **current_apps,
                "energy_monitoring": current_em
            }
        }
        requests.put(f"{BASE_URL}/api/users/{user_id}", headers=headers, json=restore_payload)
    
    def test_admin_can_set_time_based_access(self):
        """Admin should be able to set temporary access with date range"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get users
        users_res = requests.get(f"{BASE_URL}/api/users", headers=headers)
        users = users_res.json()
        
        # Find a kunde user
        kunde_users = [u for u in users if u["role"] == "kunde"]
        if not kunde_users:
            pytest.skip("No kunde users available")
        
        test_user = kunde_users[0]
        user_id = test_user["id"]
        current_apps = test_user.get("apps", {})
        
        # Set temporary access
        now = datetime.now(timezone.utc)
        start_date = now.isoformat()
        end_date = (now + timedelta(days=30)).isoformat()
        
        update_payload = {
            "apps": {
                **current_apps,
                "energy_monitoring": {
                    "enabled": True,
                    "access_all": True,
                    "device_ids": [],
                    "access_type": "temporary",
                    "access_start": start_date,
                    "access_end": end_date
                }
            }
        }
        
        update_res = requests.put(
            f"{BASE_URL}/api/users/{user_id}",
            headers=headers,
            json=update_payload
        )
        assert update_res.status_code == 200, f"Update failed: {update_res.text}"
        
        updated_user = update_res.json()
        updated_em = updated_user.get("apps", {}).get("energy_monitoring", {})
        assert updated_em.get("access_type") == "temporary"
        assert updated_em.get("access_start") is not None
        assert updated_em.get("access_end") is not None
        print(f"Successfully set temporary access for user {test_user['email']}: {start_date} to {end_date}")
        
        # Restore original state
        original_em = current_apps.get("energy_monitoring", {})
        restore_payload = {
            "apps": {
                **current_apps,
                "energy_monitoring": original_em
            }
        }
        requests.put(f"{BASE_URL}/api/users/{user_id}", headers=headers, json=restore_payload)
    
    def test_admin_can_set_individual_device_access(self):
        """Admin should be able to grant access to specific devices only"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get devices list first
        devices_res = requests.get(f"{BASE_URL}/api/energy-monitoring/devices", headers=headers)
        devices = devices_res.json()
        
        if not devices:
            pytest.skip("No Messkoffer devices available")
        
        device_ids = [d["id"] for d in devices[:2]]  # Take first 2 devices
        
        # Get users
        users_res = requests.get(f"{BASE_URL}/api/users", headers=headers)
        users = users_res.json()
        
        # Find a kunde user
        kunde_users = [u for u in users if u["role"] == "kunde"]
        if not kunde_users:
            pytest.skip("No kunde users available")
        
        test_user = kunde_users[0]
        user_id = test_user["id"]
        current_apps = test_user.get("apps", {})
        
        # Set individual device access
        update_payload = {
            "apps": {
                **current_apps,
                "energy_monitoring": {
                    "enabled": True,
                    "access_all": False,
                    "device_ids": device_ids,
                    "access_type": "permanent",
                    "access_start": None,
                    "access_end": None
                }
            }
        }
        
        update_res = requests.put(
            f"{BASE_URL}/api/users/{user_id}",
            headers=headers,
            json=update_payload
        )
        assert update_res.status_code == 200, f"Update failed: {update_res.text}"
        
        updated_user = update_res.json()
        updated_em = updated_user.get("apps", {}).get("energy_monitoring", {})
        assert updated_em.get("access_all") == False
        assert len(updated_em.get("device_ids", [])) == len(device_ids)
        print(f"Successfully set individual device access for user {test_user['email']}: {device_ids}")
        
        # Restore original state
        original_em = current_apps.get("energy_monitoring", {})
        restore_payload = {
            "apps": {
                **current_apps,
                "energy_monitoring": original_em
            }
        }
        requests.put(f"{BASE_URL}/api/users/{user_id}", headers=headers, json=restore_payload)


class TestUserEnergyColumnInAdminTable:
    """Test that users API returns correct energy_monitoring status"""
    
    def test_users_list_contains_energy_monitoring_status(self):
        """Users list should contain energy_monitoring app status"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get users
        users_res = requests.get(f"{BASE_URL}/api/users", headers=headers)
        assert users_res.status_code == 200
        users = users_res.json()
        
        # Check that apps field exists with energy_monitoring
        for user in users:
            apps = user.get("apps", {})
            assert "energy_monitoring" in apps or user["role"] == "admin", \
                f"User {user['email']} missing energy_monitoring in apps"
            
            em = apps.get("energy_monitoring", {})
            print(f"User {user['email']} (role={user['role']}): energy_monitoring.enabled={em.get('enabled', 'N/A')}")


class TestMeterEndpoints:
    """Test meter-specific endpoints"""
    
    def test_list_meters_for_device(self):
        """Admin should be able to list meters for a device"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get devices
        devices_res = requests.get(f"{BASE_URL}/api/energy-monitoring/devices", headers=headers)
        devices = devices_res.json()
        
        if not devices:
            pytest.skip("No Messkoffer devices available")
        
        device_id = devices[0]["id"]
        
        # Get meters
        res = requests.get(f"{BASE_URL}/api/energy-monitoring/devices/{device_id}/meters", headers=headers)
        assert res.status_code == 200, f"Failed: {res.text}"
        
        meters = res.json()
        assert isinstance(meters, list)
        print(f"Found {len(meters)} meters for device {device_id}")
        
        if meters:
            meter = meters[0]
            assert "id" in meter
            assert "meter_name" in meter
            assert "meter_ip" in meter
            print(f"First meter: {meter.get('meter_name')} at {meter.get('meter_ip')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
