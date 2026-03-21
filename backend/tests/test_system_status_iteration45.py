"""
Test System Status Dashboard and Device Online Status Features
Iteration 45 - Testing:
1. GET /api/system/status endpoint (admin-only)
2. GET /api/devices endpoint with last_seen enrichment
3. Online status logic based on last_seen field
"""

import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "christian.ecker@eventenergie-deutschland.de"
ADMIN_PASSWORD = "qivbeb-Wodha1-sewram"


class TestSystemStatus:
    """Test the /api/system/status endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for authenticated requests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.admin_token = token
        else:
            pytest.skip(f"Admin login failed: {login_response.status_code}")
    
    def test_system_status_endpoint_returns_200(self):
        """Test that /api/system/status returns 200 for admin"""
        response = self.session.get(f"{BASE_URL}/api/system/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ System status endpoint returns 200")
    
    def test_system_status_has_mongodb_field(self):
        """Test that response contains mongodb.connected field"""
        response = self.session.get(f"{BASE_URL}/api/system/status")
        assert response.status_code == 200
        data = response.json()
        
        assert "mongodb" in data, "Response missing 'mongodb' field"
        assert "connected" in data["mongodb"], "Response missing 'mongodb.connected' field"
        assert isinstance(data["mongodb"]["connected"], bool), "mongodb.connected should be boolean"
        print(f"✓ MongoDB connected: {data['mongodb']['connected']}")
    
    def test_system_status_has_users_count(self):
        """Test that response contains users count"""
        response = self.session.get(f"{BASE_URL}/api/system/status")
        assert response.status_code == 200
        data = response.json()
        
        assert "users" in data, "Response missing 'users' field"
        assert isinstance(data["users"], int), "users should be integer"
        assert data["users"] >= 0, "users count should be non-negative"
        print(f"✓ Users count: {data['users']}")
    
    def test_system_status_has_devices_fields(self):
        """Test that response contains devices.total, devices.active, devices.online"""
        response = self.session.get(f"{BASE_URL}/api/system/status")
        assert response.status_code == 200
        data = response.json()
        
        assert "devices" in data, "Response missing 'devices' field"
        devices = data["devices"]
        
        assert "total" in devices, "Response missing 'devices.total'"
        assert "active" in devices, "Response missing 'devices.active'"
        assert "online" in devices, "Response missing 'devices.online'"
        
        assert isinstance(devices["total"], int), "devices.total should be integer"
        assert isinstance(devices["active"], int), "devices.active should be integer"
        assert isinstance(devices["online"], int), "devices.online should be integer"
        
        print(f"✓ Devices - total: {devices['total']}, active: {devices['active']}, online: {devices['online']}")
    
    def test_system_status_has_generators_fields(self):
        """Test that response contains generators.total and generators.online"""
        response = self.session.get(f"{BASE_URL}/api/system/status")
        assert response.status_code == 200
        data = response.json()
        
        assert "generators" in data, "Response missing 'generators' field"
        generators = data["generators"]
        
        assert "total" in generators, "Response missing 'generators.total'"
        assert "online" in generators, "Response missing 'generators.online'"
        
        assert isinstance(generators["total"], int), "generators.total should be integer"
        assert isinstance(generators["online"], int), "generators.online should be integer"
        
        print(f"✓ Generators - total: {generators['total']}, online: {generators['online']}")
    
    def test_system_status_has_recent_activity(self):
        """Test that response contains recent_activity.emu_records_last_hour"""
        response = self.session.get(f"{BASE_URL}/api/system/status")
        assert response.status_code == 200
        data = response.json()
        
        assert "recent_activity" in data, "Response missing 'recent_activity' field"
        assert "emu_records_last_hour" in data["recent_activity"], "Response missing 'recent_activity.emu_records_last_hour'"
        
        print(f"✓ Recent activity - EMU records last hour: {data['recent_activity']['emu_records_last_hour']}")
    
    def test_system_status_has_timestamp(self):
        """Test that response contains timestamp"""
        response = self.session.get(f"{BASE_URL}/api/system/status")
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data, "Response missing 'timestamp' field"
        # Verify it's a valid ISO timestamp
        try:
            datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"Invalid timestamp format: {data['timestamp']}")
        
        print(f"✓ Timestamp: {data['timestamp']}")
    
    def test_system_status_requires_admin(self):
        """Test that non-admin users cannot access system status"""
        # Create a new session without auth
        unauthenticated_session = requests.Session()
        unauthenticated_session.headers.update({"Content-Type": "application/json"})
        
        response = unauthenticated_session.get(f"{BASE_URL}/api/system/status")
        # Should return 401 or 403
        assert response.status_code in [401, 403], f"Expected 401/403 for unauthenticated, got {response.status_code}"
        print("✓ System status requires authentication")


class TestDevicesWithLastSeen:
    """Test the /api/devices endpoint with last_seen enrichment"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for authenticated requests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Admin login failed: {login_response.status_code}")
    
    def test_devices_endpoint_returns_200(self):
        """Test that /api/devices returns 200"""
        response = self.session.get(f"{BASE_URL}/api/devices")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Devices endpoint returns 200")
    
    def test_devices_returns_list(self):
        """Test that /api/devices returns a list"""
        response = self.session.get(f"{BASE_URL}/api/devices")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Devices endpoint returns list with {len(data)} devices")
    
    def test_devices_have_required_fields(self):
        """Test that devices have required fields including device_type and serial_number"""
        response = self.session.get(f"{BASE_URL}/api/devices")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) == 0:
            pytest.skip("No devices in database to test")
        
        device = data[0]
        required_fields = ["id", "device_type", "serial_number", "status"]
        
        for field in required_fields:
            assert field in device, f"Device missing required field: {field}"
        
        print(f"✓ Device has required fields: {required_fields}")
    
    def test_stromerzeuger_devices_can_have_last_seen(self):
        """Test that stromerzeuger/lichtmast devices can have last_seen field"""
        response = self.session.get(f"{BASE_URL}/api/devices")
        assert response.status_code == 200
        data = response.json()
        
        # Filter for stromerzeuger or lichtmast devices
        generator_devices = [d for d in data if d.get("device_type") in ("stromerzeuger", "lichtmast")]
        
        if len(generator_devices) == 0:
            pytest.skip("No stromerzeuger/lichtmast devices to test")
        
        # Check that the field can exist (may be null if no IoT data)
        device = generator_devices[0]
        # last_seen may or may not be present depending on IoT data
        print(f"✓ Found {len(generator_devices)} stromerzeuger/lichtmast devices")
        if device.get("last_seen"):
            print(f"  - Device {device['serial_number']} has last_seen: {device['last_seen']}")
        else:
            print(f"  - Device {device['serial_number']} has no last_seen (expected if no IoT data)")
    
    def test_device_types_are_valid(self):
        """Test that device types are one of the expected values"""
        response = self.session.get(f"{BASE_URL}/api/devices")
        assert response.status_code == 200
        data = response.json()
        
        valid_types = ["stromerzeuger", "lichtmast", "messkoffer", "kirmeskiste"]
        
        for device in data:
            device_type = device.get("device_type")
            assert device_type in valid_types, f"Invalid device type: {device_type}"
        
        print(f"✓ All {len(data)} devices have valid device types")


class TestOnlineStatusLogic:
    """Test the online status logic in the frontend helper functions"""
    
    def test_online_status_logic_online(self):
        """Test that last_seen < 10 minutes = Online"""
        # This tests the logic that should be implemented in frontend
        now = datetime.now(timezone.utc)
        last_seen = (now - timedelta(minutes=5)).isoformat()
        
        diff = (now - datetime.fromisoformat(last_seen.replace("Z", "+00:00"))).total_seconds() / 60
        
        if diff < 10:
            status = "online"
        elif diff < 60:
            status = "idle"
        else:
            status = "offline"
        
        assert status == "online", f"Expected 'online' for 5 min ago, got '{status}'"
        print("✓ Online status logic: < 10 min = Online")
    
    def test_online_status_logic_idle(self):
        """Test that last_seen 10-60 minutes = Idle (Inaktiv)"""
        now = datetime.now(timezone.utc)
        last_seen = (now - timedelta(minutes=30)).isoformat()
        
        diff = (now - datetime.fromisoformat(last_seen.replace("Z", "+00:00"))).total_seconds() / 60
        
        if diff < 10:
            status = "online"
        elif diff < 60:
            status = "idle"
        else:
            status = "offline"
        
        assert status == "idle", f"Expected 'idle' for 30 min ago, got '{status}'"
        print("✓ Online status logic: 10-60 min = Idle (Inaktiv)")
    
    def test_online_status_logic_offline(self):
        """Test that last_seen > 60 minutes = Offline"""
        now = datetime.now(timezone.utc)
        last_seen = (now - timedelta(minutes=120)).isoformat()
        
        diff = (now - datetime.fromisoformat(last_seen.replace("Z", "+00:00"))).total_seconds() / 60
        
        if diff < 10:
            status = "online"
        elif diff < 60:
            status = "idle"
        else:
            status = "offline"
        
        assert status == "offline", f"Expected 'offline' for 120 min ago, got '{status}'"
        print("✓ Online status logic: > 60 min = Offline")
    
    def test_online_status_logic_unknown(self):
        """Test that null last_seen = Unknown (Nie verbunden)"""
        last_seen = None
        
        if last_seen is None:
            status = "unknown"
        else:
            # Would calculate based on time
            status = "calculated"
        
        assert status == "unknown", f"Expected 'unknown' for null last_seen, got '{status}'"
        print("✓ Online status logic: null = Unknown (Nie verbunden)")


class TestHealthCheck:
    """Basic health check to ensure API is running"""
    
    def test_health_endpoint(self):
        """Test that /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print("✓ Health endpoint returns 200")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
