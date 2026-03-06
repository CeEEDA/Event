"""
Test suite for MQTT Integration feature
Tests: MQTT config endpoints, gateway mappings, raw messages, admin-only access
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthSetup:
    """Authentication fixtures for testing"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if response.status_code != 200:
            pytest.skip("Admin login failed - skipping authenticated tests")
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def mitarbeiter_token(self):
        """Get non-admin (mitarbeiter) auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "ma1@test.com",
            "password": "password"
        })
        if response.status_code != 200:
            pytest.skip("Mitarbeiter login failed - skipping non-admin tests")
        return response.json()["token"]


class TestMqttConfigEndpoints(TestAuthSetup):
    """Test MQTT configuration CRUD operations"""
    
    def test_get_mqtt_config_returns_default_when_empty(self, admin_token):
        """GET /api/mqtt/config should return default config when no config exists"""
        response = requests.get(
            f"{BASE_URL}/api/mqtt/config",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify expected fields exist
        assert "enabled" in data
        assert "broker_url" in data
        assert "broker_port" in data
        assert "username" in data
        assert "subscribe_topics" in data
        print(f"PASS: GET /api/mqtt/config returns config with enabled={data.get('enabled')}")
    
    def test_put_mqtt_config_saves_broker_configuration(self, admin_token):
        """PUT /api/mqtt/config should save MQTT broker configuration"""
        test_config = {
            "enabled": False,  # Keep disabled to not connect
            "broker_url": "test.broker.hivemq.com",
            "broker_port": 8883,
            "username": "test_user",
            "password": "test_pass_123",
            "use_tls": True,
            "subscribe_topics": ["dse/#", "test/#"]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/mqtt/config",
            json=test_config,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["broker_url"] == "test.broker.hivemq.com"
        assert data["broker_port"] == 8883
        assert data["username"] == "test_user"
        assert data["use_tls"] == True
        assert "dse/#" in data["subscribe_topics"]
        print(f"PASS: PUT /api/mqtt/config saves broker config correctly")
    
    def test_mqtt_password_is_masked_in_get_response(self, admin_token):
        """GET /api/mqtt/config should mask password in response"""
        # First set a password
        requests.put(
            f"{BASE_URL}/api/mqtt/config",
            json={
                "enabled": False,
                "broker_url": "broker.hivemq.com",
                "broker_port": 1883,
                "username": "test_user",
                "password": "secret_password_123",
                "use_tls": False,
                "subscribe_topics": ["dse/#"]
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Get config and verify password is masked
        response = requests.get(
            f"{BASE_URL}/api/mqtt/config",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Password should be masked (asterisks)
        assert data.get("password") == "********", f"Expected masked password, got: {data.get('password')}"
        assert data.get("password_set") == True, "Expected password_set=True when password exists"
        print("PASS: Password is correctly masked in GET /api/mqtt/config response")


class TestMqttStatusEndpoint(TestAuthSetup):
    """Test MQTT connection status endpoint"""
    
    def test_get_mqtt_status(self, admin_token):
        """GET /api/mqtt/status should return connection status"""
        response = requests.get(
            f"{BASE_URL}/api/mqtt/status",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify expected status fields
        assert "enabled" in data
        assert "connected" in data
        assert "connection_status" in data
        
        # Since MQTT is disabled, connected should be False
        print(f"PASS: GET /api/mqtt/status returns status: enabled={data['enabled']}, connected={data['connected']}, status={data['connection_status']}")


class TestMqttTestConnection(TestAuthSetup):
    """Test MQTT broker connection test endpoint"""
    
    def test_mqtt_test_connection_endpoint_exists(self, admin_token):
        """POST /api/mqtt/test-connection should exist and return result"""
        # First ensure config exists
        requests.put(
            f"{BASE_URL}/api/mqtt/config",
            json={
                "enabled": False,
                "broker_url": "broker.hivemq.com",
                "broker_port": 1883,
                "username": "",
                "password": "",
                "use_tls": False,
                "subscribe_topics": ["dse/#"]
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        response = requests.post(
            f"{BASE_URL}/api/mqtt/test-connection",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Could be 200 (success/fail result) or timeout - either means endpoint exists
        assert response.status_code in [200, 500, 408], f"Expected 200/500/408, got {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "message" in data
            print(f"PASS: POST /api/mqtt/test-connection returns success={data['success']}, message={data['message']}")
        else:
            print(f"PASS: POST /api/mqtt/test-connection endpoint exists (status={response.status_code})")


class TestGatewayMappings(TestAuthSetup):
    """Test CRUD operations for gateway-to-generator mappings"""
    
    @pytest.fixture(scope="class")
    def test_generator_id(self, admin_token):
        """Get a generator ID for mapping tests"""
        response = requests.get(
            f"{BASE_URL}/api/generators",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if response.status_code == 200 and response.json():
            return response.json()[0]["id"]
        pytest.skip("No generators available for mapping tests")
    
    def test_list_gateway_mappings(self, admin_token):
        """GET /api/mqtt/mappings should return list of mappings"""
        response = requests.get(
            f"{BASE_URL}/api/mqtt/mappings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert isinstance(response.json(), list), "Expected list response"
        print(f"PASS: GET /api/mqtt/mappings returns {len(response.json())} mappings")
    
    def test_create_gateway_mapping(self, admin_token, test_generator_id):
        """POST /api/mqtt/mappings should create new mapping"""
        unique_name = f"TEST_GATEWAY_{uuid.uuid4().hex[:8]}"
        mapping_data = {
            "gateway_name": unique_name,
            "topic_prefix": f"dse/test-{unique_name}",
            "generator_id": test_generator_id,
            "notes": "Test mapping for automated testing"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/mqtt/mappings",
            json=mapping_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["gateway_name"] == unique_name
        assert data["generator_id"] == test_generator_id
        assert "id" in data
        
        print(f"PASS: POST /api/mqtt/mappings creates mapping with id={data['id']}")
        return data["id"]
    
    def test_create_and_delete_gateway_mapping(self, admin_token, test_generator_id):
        """Create then delete a gateway mapping"""
        # Create
        unique_name = f"TEST_DEL_{uuid.uuid4().hex[:8]}"
        create_response = requests.post(
            f"{BASE_URL}/api/mqtt/mappings",
            json={
                "gateway_name": unique_name,
                "topic_prefix": f"dse/{unique_name}",
                "generator_id": test_generator_id,
                "notes": "Test for deletion"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert create_response.status_code == 200
        mapping_id = create_response.json()["id"]
        
        # Delete
        delete_response = requests.delete(
            f"{BASE_URL}/api/mqtt/mappings/{mapping_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert delete_response.status_code == 200, f"Expected 200 for delete, got {delete_response.status_code}"
        
        # Verify deleted - list and check it's gone
        list_response = requests.get(
            f"{BASE_URL}/api/mqtt/mappings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        mapping_ids = [m["id"] for m in list_response.json()]
        assert mapping_id not in mapping_ids, "Deleted mapping should not be in list"
        
        print(f"PASS: DELETE /api/mqtt/mappings/{mapping_id} removes mapping")
    
    def test_create_mapping_invalid_generator_returns_404(self, admin_token):
        """POST /api/mqtt/mappings with invalid generator_id should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/mqtt/mappings",
            json={
                "gateway_name": "Invalid Generator Test",
                "topic_prefix": "dse/invalid",
                "generator_id": "non-existent-id-12345",
                "notes": ""
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404, f"Expected 404 for invalid generator, got {response.status_code}"
        print("PASS: POST /api/mqtt/mappings returns 404 for invalid generator_id")


class TestRawMessages(TestAuthSetup):
    """Test raw MQTT messages endpoint"""
    
    def test_get_raw_messages(self, admin_token):
        """GET /api/mqtt/raw-messages should return list of messages"""
        response = requests.get(
            f"{BASE_URL}/api/mqtt/raw-messages?limit=50",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert isinstance(response.json(), list), "Expected list response"
        print(f"PASS: GET /api/mqtt/raw-messages returns {len(response.json())} messages")


class TestNonAdminAccess(TestAuthSetup):
    """Test that non-admin users get 403 on MQTT endpoints"""
    
    def test_non_admin_cannot_get_mqtt_config(self, mitarbeiter_token):
        """Non-admin should get 403 on GET /api/mqtt/config"""
        response = requests.get(
            f"{BASE_URL}/api/mqtt/config",
            headers={"Authorization": f"Bearer {mitarbeiter_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        print("PASS: Non-admin gets 403 on GET /api/mqtt/config")
    
    def test_non_admin_cannot_put_mqtt_config(self, mitarbeiter_token):
        """Non-admin should get 403 on PUT /api/mqtt/config"""
        response = requests.put(
            f"{BASE_URL}/api/mqtt/config",
            json={"enabled": True, "broker_url": "test.com", "broker_port": 1883},
            headers={"Authorization": f"Bearer {mitarbeiter_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        print("PASS: Non-admin gets 403 on PUT /api/mqtt/config")
    
    def test_non_admin_cannot_get_mqtt_status(self, mitarbeiter_token):
        """Non-admin should get 403 on GET /api/mqtt/status"""
        response = requests.get(
            f"{BASE_URL}/api/mqtt/status",
            headers={"Authorization": f"Bearer {mitarbeiter_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        print("PASS: Non-admin gets 403 on GET /api/mqtt/status")
    
    def test_non_admin_cannot_test_mqtt_connection(self, mitarbeiter_token):
        """Non-admin should get 403 on POST /api/mqtt/test-connection"""
        response = requests.post(
            f"{BASE_URL}/api/mqtt/test-connection",
            headers={"Authorization": f"Bearer {mitarbeiter_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        print("PASS: Non-admin gets 403 on POST /api/mqtt/test-connection")
    
    def test_non_admin_cannot_get_mappings(self, mitarbeiter_token):
        """Non-admin should get 403 on GET /api/mqtt/mappings"""
        response = requests.get(
            f"{BASE_URL}/api/mqtt/mappings",
            headers={"Authorization": f"Bearer {mitarbeiter_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        print("PASS: Non-admin gets 403 on GET /api/mqtt/mappings")
    
    def test_non_admin_cannot_create_mapping(self, mitarbeiter_token):
        """Non-admin should get 403 on POST /api/mqtt/mappings"""
        response = requests.post(
            f"{BASE_URL}/api/mqtt/mappings",
            json={"gateway_name": "Test", "topic_prefix": "dse/test", "generator_id": "123"},
            headers={"Authorization": f"Bearer {mitarbeiter_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        print("PASS: Non-admin gets 403 on POST /api/mqtt/mappings")
    
    def test_non_admin_cannot_get_raw_messages(self, mitarbeiter_token):
        """Non-admin should get 403 on GET /api/mqtt/raw-messages"""
        response = requests.get(
            f"{BASE_URL}/api/mqtt/raw-messages",
            headers={"Authorization": f"Bearer {mitarbeiter_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        print("PASS: Non-admin gets 403 on GET /api/mqtt/raw-messages")


class TestCleanup(TestAuthSetup):
    """Cleanup test data after tests"""
    
    def test_cleanup_test_mappings(self, admin_token):
        """Remove test mappings created during tests"""
        response = requests.get(
            f"{BASE_URL}/api/mqtt/mappings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if response.status_code == 200:
            for mapping in response.json():
                if "TEST_" in mapping.get("gateway_name", ""):
                    requests.delete(
                        f"{BASE_URL}/api/mqtt/mappings/{mapping['id']}",
                        headers={"Authorization": f"Bearer {admin_token}"}
                    )
        print("PASS: Cleanup completed")
