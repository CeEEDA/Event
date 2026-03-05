"""
Generator Monitoring API Tests
Tests for DSE Generator Monitoring Dashboard - Phase 1

Modules tested:
- Generator CRUD (admin-only create/update/delete)
- Generator list/detail (authenticated users)
- Telemetry ingestion (API key auth)
- Telemetry query (authenticated users)
- Alarms CRUD (authenticated users, ack/resolve non-admin restricted for kunde)
- Stats overview
- Authorization (admin vs kunde vs mitarbeiter roles)
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"

# Track created test resources for cleanup
created_generators = []


class TestAuth:
    """Authentication helper fixture tests"""
    
    def test_admin_login(self):
        """Verify admin can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"


class TestGeneratorStats:
    """Test stats/overview endpoint"""
    
    @pytest.fixture(autouse=True)
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_stats_overview(self):
        """GET /api/generators/stats/overview - Should return status counts"""
        response = requests.get(f"{BASE_URL}/api/generators/stats/overview", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "total" in data
        assert "running" in data
        assert "standby" in data
        assert "alarm" in data
        assert "offline" in data
        assert "active_alarms" in data
        assert "active_warnings" in data
        
        # Values should be non-negative integers
        assert isinstance(data["total"], int) and data["total"] >= 0
        assert isinstance(data["running"], int) and data["running"] >= 0


class TestGeneratorList:
    """Test generator listing endpoints"""
    
    @pytest.fixture(autouse=True)
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_list_generators(self):
        """GET /api/generators - List all generators with latest telemetry"""
        response = requests.get(f"{BASE_URL}/api/generators", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # We should have demo generators
        assert len(data) >= 1
        
        # Validate generator structure
        gen = data[0]
        assert "id" in gen
        assert "name" in gen
        assert "serial_number" in gen
        assert "status" in gen
        assert "latest_telemetry" in gen
        
        # Admin should see api_key
        assert "api_key" in gen
    
    def test_list_generators_without_auth(self):
        """GET /api/generators - Should require authentication"""
        response = requests.get(f"{BASE_URL}/api/generators")
        assert response.status_code in [401, 403]


class TestGeneratorDetail:
    """Test single generator detail endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get first generator for testing
        gen_response = requests.get(f"{BASE_URL}/api/generators", headers=self.headers)
        self.generators = gen_response.json()
        if len(self.generators) > 0:
            self.test_gen_id = self.generators[0]["id"]
        else:
            self.test_gen_id = None
    
    def test_get_generator_detail(self):
        """GET /api/generators/{id} - Get single generator with telemetry and alarms"""
        if not self.test_gen_id:
            pytest.skip("No generators available")
        
        response = requests.get(f"{BASE_URL}/api/generators/{self.test_gen_id}", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == self.test_gen_id
        assert "name" in data
        assert "serial_number" in data
        assert "model" in data
        assert "status" in data
        assert "latest_telemetry" in data
        assert "active_alarms" in data
        assert isinstance(data["active_alarms"], list)
    
    def test_get_nonexistent_generator(self):
        """GET /api/generators/{id} - Should return 404 for invalid ID"""
        response = requests.get(f"{BASE_URL}/api/generators/nonexistent-id-123", headers=self.headers)
        assert response.status_code == 404


class TestGeneratorCRUD:
    """Test generator CRUD operations (admin only)"""
    
    @pytest.fixture(autouse=True)
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_create_generator(self):
        """POST /api/generators - Create new generator (admin only)"""
        unique_serial = f"TEST-GEN-{uuid.uuid4().hex[:8].upper()}"
        payload = {
            "name": "TEST Generator Unit Test",
            "serial_number": unique_serial,
            "model": "DSE8610MK2",
            "location_name": "Test Location",
            "latitude": 50.1109,
            "longitude": 8.6821,
            "dse_module_type": "DSE890",
            "notes": "Created by pytest"
        }
        
        response = requests.post(f"{BASE_URL}/api/generators", json=payload, headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == payload["name"]
        assert data["serial_number"] == unique_serial
        assert "id" in data
        assert "api_key" in data
        assert data["api_key"].startswith("dse_")
        assert data["status"] == "offline"
        
        # Store for cleanup
        created_generators.append(data["id"])
        
        # Verify persistence with GET
        get_response = requests.get(f"{BASE_URL}/api/generators/{data['id']}", headers=self.headers)
        assert get_response.status_code == 200
        assert get_response.json()["serial_number"] == unique_serial
    
    def test_create_duplicate_serial(self):
        """POST /api/generators - Should reject duplicate serial numbers"""
        # First get an existing serial number
        gen_response = requests.get(f"{BASE_URL}/api/generators", headers=self.headers)
        generators = gen_response.json()
        if len(generators) == 0:
            pytest.skip("No generators to test duplicate")
        
        existing_serial = generators[0]["serial_number"]
        
        payload = {
            "name": "Duplicate Test",
            "serial_number": existing_serial,
            "model": "DSE8610MK2"
        }
        
        response = requests.post(f"{BASE_URL}/api/generators", json=payload, headers=self.headers)
        assert response.status_code == 400
    
    def test_update_generator(self):
        """PUT /api/generators/{id} - Update generator (admin only)"""
        # First create a generator to update
        unique_serial = f"TEST-UPD-{uuid.uuid4().hex[:8].upper()}"
        create_response = requests.post(f"{BASE_URL}/api/generators", json={
            "name": "Generator For Update Test",
            "serial_number": unique_serial,
            "model": "DSE8610MK2"
        }, headers=self.headers)
        
        assert create_response.status_code == 200
        gen_id = create_response.json()["id"]
        created_generators.append(gen_id)
        
        # Update
        update_payload = {
            "name": "Updated Generator Name",
            "location_name": "Updated Location",
            "notes": "Updated by pytest"
        }
        
        response = requests.put(f"{BASE_URL}/api/generators/{gen_id}", json=update_payload, headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Updated Generator Name"
        assert data["location_name"] == "Updated Location"
        
        # Verify persistence
        get_response = requests.get(f"{BASE_URL}/api/generators/{gen_id}", headers=self.headers)
        assert get_response.json()["name"] == "Updated Generator Name"
    
    def test_delete_generator(self):
        """DELETE /api/generators/{id} - Delete generator (admin only)"""
        # Create a generator to delete
        unique_serial = f"TEST-DEL-{uuid.uuid4().hex[:8].upper()}"
        create_response = requests.post(f"{BASE_URL}/api/generators", json={
            "name": "Generator To Delete",
            "serial_number": unique_serial,
            "model": "DSE8610MK2"
        }, headers=self.headers)
        
        assert create_response.status_code == 200
        gen_id = create_response.json()["id"]
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/generators/{gen_id}", headers=self.headers)
        assert response.status_code == 200
        
        # Verify deletion
        get_response = requests.get(f"{BASE_URL}/api/generators/{gen_id}", headers=self.headers)
        assert get_response.status_code == 404


class TestTelemetryIngestion:
    """Test telemetry data ingestion (API key auth)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Create a generator for telemetry testing
        unique_serial = f"TEST-TEL-{uuid.uuid4().hex[:8].upper()}"
        create_response = requests.post(f"{BASE_URL}/api/generators", json={
            "name": "Telemetry Test Generator",
            "serial_number": unique_serial,
            "model": "DSE8610MK2"
        }, headers=self.headers)
        
        if create_response.status_code == 200:
            self.test_gen = create_response.json()
            created_generators.append(self.test_gen["id"])
        else:
            self.test_gen = None
    
    def test_ingest_telemetry_valid_api_key(self):
        """POST /api/generators/{id}/telemetry - Ingest telemetry with valid API key"""
        if not self.test_gen:
            pytest.skip("No test generator available")
        
        payload = {
            "api_key": self.test_gen["api_key"],
            "voltage_l1": 230.5,
            "voltage_l2": 229.8,
            "voltage_l3": 231.2,
            "current_l1": 125.0,
            "current_l2": 128.5,
            "current_l3": 126.3,
            "frequency": 50.02,
            "power_kw": 85.5,
            "power_kva": 92.0,
            "power_factor": 0.93,
            "load_percent": 65.5,
            "rpm": 1500,
            "oil_pressure": 4.2,
            "coolant_temp": 82.5,
            "fuel_level": 75.0,
            "battery_voltage": 13.8,
            "hours_run": 1234.5,
            "engine_running": True,
            "mode": "auto"
        }
        
        # No auth header needed - uses API key
        response = requests.post(f"{BASE_URL}/api/generators/{self.test_gen['id']}/telemetry", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "id" in data
        
        # Verify generator status updated
        gen_response = requests.get(f"{BASE_URL}/api/generators/{self.test_gen['id']}", headers=self.headers)
        assert gen_response.status_code == 200
        gen_data = gen_response.json()
        assert gen_data["status"] == "running"
        assert gen_data["latest_telemetry"] is not None
    
    def test_ingest_telemetry_invalid_api_key(self):
        """POST /api/generators/{id}/telemetry - Should reject invalid API key"""
        if not self.test_gen:
            pytest.skip("No test generator available")
        
        payload = {
            "api_key": "invalid_api_key_123",
            "voltage_l1": 230.0
        }
        
        response = requests.post(f"{BASE_URL}/api/generators/{self.test_gen['id']}/telemetry", json=payload)
        assert response.status_code == 401
    
    def test_ingest_telemetry_with_alarms(self):
        """POST /api/generators/{id}/telemetry - Ingest telemetry with alarms"""
        if not self.test_gen:
            pytest.skip("No test generator available")
        
        payload = {
            "api_key": self.test_gen["api_key"],
            "voltage_l1": 230.0,
            "engine_running": True,
            "alarms": ["High Temperature", "Low Oil Pressure"]
        }
        
        response = requests.post(f"{BASE_URL}/api/generators/{self.test_gen['id']}/telemetry", json=payload)
        assert response.status_code == 200
        
        # Verify generator status is alarm
        gen_response = requests.get(f"{BASE_URL}/api/generators/{self.test_gen['id']}", headers=self.headers)
        gen_data = gen_response.json()
        assert gen_data["status"] == "alarm"


class TestTelemetryQuery:
    """Test telemetry query endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get first generator with telemetry
        gen_response = requests.get(f"{BASE_URL}/api/generators", headers=self.headers)
        generators = gen_response.json()
        self.test_gen_id = generators[0]["id"] if len(generators) > 0 else None
    
    def test_get_telemetry_history(self):
        """GET /api/generators/{id}/telemetry - Get telemetry history"""
        if not self.test_gen_id:
            pytest.skip("No generators available")
        
        response = requests.get(f"{BASE_URL}/api/generators/{self.test_gen_id}/telemetry?hours=24&limit=50", 
                               headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        if len(data) > 0:
            # Validate telemetry structure
            tel = data[0]
            assert "id" in tel
            assert "generator_id" in tel
            assert "timestamp" in tel


class TestAlarms:
    """Test alarm endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get first generator
        gen_response = requests.get(f"{BASE_URL}/api/generators", headers=self.headers)
        generators = gen_response.json()
        self.test_gen_id = generators[0]["id"] if len(generators) > 0 else None
    
    def test_get_alarms(self):
        """GET /api/generators/{id}/alarms - Get active alarms"""
        if not self.test_gen_id:
            pytest.skip("No generators available")
        
        response = requests.get(f"{BASE_URL}/api/generators/{self.test_gen_id}/alarms?active_only=true", 
                               headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # Validate alarm structure if any exist
        if len(data) > 0:
            alarm = data[0]
            assert "id" in alarm
            assert "generator_id" in alarm
            assert "alarm_text" in alarm
            assert "severity" in alarm
            assert "timestamp" in alarm


class TestSimulateData:
    """Test demo data simulation endpoint"""
    
    @pytest.fixture(autouse=True)
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_simulate_data(self):
        """POST /api/generators/simulate - Create demo data (admin only)"""
        response = requests.post(f"{BASE_URL}/api/generators/simulate", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "generators" in data
        assert isinstance(data["generators"], list)


class TestAuthorizationNonAdmin:
    """Test authorization for non-admin users"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        # Login as admin first
        admin_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert admin_response.status_code == 200
        self.admin_token = admin_response.json()["token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Create a test non-admin user (kunde)
        self.test_user_email = f"test_kunde_{uuid.uuid4().hex[:8]}@test.com"
        
        create_user_response = requests.post(f"{BASE_URL}/api/users", json={
            "email": self.test_user_email,
            "password": "testpassword123",
            "name": "Test Kunde",
            "role": "kunde"
        }, headers=self.admin_headers)
        
        if create_user_response.status_code == 200:
            self.test_user_id = create_user_response.json()["id"]
            
            # Login as the test user
            user_login = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": self.test_user_email,
                "password": "testpassword123"
            })
            if user_login.status_code == 200:
                self.user_token = user_login.json()["token"]
                self.user_headers = {"Authorization": f"Bearer {self.user_token}"}
            else:
                self.user_token = None
                self.user_headers = None
        else:
            self.test_user_id = None
            self.user_token = None
            self.user_headers = None
    
    def test_kunde_cannot_create_generator(self):
        """POST /api/generators - Kunde should be forbidden to create"""
        if not self.user_headers:
            pytest.skip("Test user not available")
        
        payload = {
            "name": "Unauthorized Generator",
            "serial_number": f"UNAUTH-{uuid.uuid4().hex[:8].upper()}",
            "model": "DSE8610MK2"
        }
        
        response = requests.post(f"{BASE_URL}/api/generators", json=payload, headers=self.user_headers)
        assert response.status_code == 403
    
    def test_kunde_cannot_delete_generator(self):
        """DELETE /api/generators/{id} - Kunde should be forbidden to delete"""
        if not self.user_headers:
            pytest.skip("Test user not available")
        
        # Get a generator ID
        gen_response = requests.get(f"{BASE_URL}/api/generators", headers=self.admin_headers)
        generators = gen_response.json()
        if len(generators) == 0:
            pytest.skip("No generators to test")
        
        gen_id = generators[0]["id"]
        
        response = requests.delete(f"{BASE_URL}/api/generators/{gen_id}", headers=self.user_headers)
        assert response.status_code == 403
    
    def test_kunde_can_list_generators(self):
        """GET /api/generators - Kunde should see generators (maybe filtered)"""
        if not self.user_headers:
            pytest.skip("Test user not available")
        
        response = requests.get(f"{BASE_URL}/api/generators", headers=self.user_headers)
        # Should succeed, but may return empty list if not assigned
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Kunde should NOT see api_key
        for gen in data:
            assert "api_key" not in gen
    
    def teardown_method(self, method):
        """Cleanup test user"""
        if hasattr(self, 'test_user_id') and self.test_user_id and hasattr(self, 'admin_headers'):
            requests.delete(f"{BASE_URL}/api/users/{self.test_user_id}", headers=self.admin_headers)


# Cleanup fixture
@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
    """Cleanup created test generators after all tests"""
    def cleanup_generators():
        # Login as admin
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            token = response.json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            for gen_id in created_generators:
                requests.delete(f"{BASE_URL}/api/generators/{gen_id}", headers=headers)
    
    request.addfinalizer(cleanup_generators)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
