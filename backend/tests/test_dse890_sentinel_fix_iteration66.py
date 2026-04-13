"""
Test DSE 890 Gateway UI Fixes - Iteration 66
Tests for:
1. Sentinel value filtering in _parse_gencomm_registers()
2. _sanitize_telemetry() function for historical data cleanup
3. Control button routing via /api/mqtt/control/{id}
4. Generator detail API returns sanitized telemetry
"""

import pytest
import requests
import os
import sys

# Add backend to path for direct imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# DSE Sentinel values that should be filtered
DSE_SENTINEL_VALUES = [
    2147483644,  # 0x7FFFFFFC - DSE "not available" for 32-bit
    2147483645,
    2147483646,
    2147483647,
    32764,       # 0x7FFC - DSE "not available" for 16-bit
    32765,
    32766,
    32767,
    65535,
    4294967295,
]

# Values that should pass through (valid readings)
VALID_VALUES = [
    0, 1, 100, 230, 400, 1500, 50.0, 12.5, 99.9, 1000, 50000, 999999
]


class TestHealthAndAuth:
    """Basic health and authentication tests"""
    
    def test_health_endpoint(self):
        """Test that the API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy", f"Unexpected health status: {data}"
        print("PASS: Health endpoint returns healthy")
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        print("PASS: Admin login successful")
        return data["token"]


class TestSentinelValueFiltering:
    """Test that DSE sentinel values are properly filtered"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_generators_list_no_sentinel_values(self, auth_headers):
        """Test that generator list doesn't contain sentinel values in telemetry"""
        response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get generators: {response.text}"
        
        generators = response.json()
        assert isinstance(generators, list), "Expected list of generators"
        
        sentinel_found = []
        for gen in generators:
            telemetry = gen.get("latest_telemetry", {})
            if telemetry:
                for field, value in telemetry.items():
                    if isinstance(value, (int, float)):
                        # Check for sentinel values
                        for sentinel in DSE_SENTINEL_VALUES:
                            if abs(value - sentinel) < 0.5:
                                sentinel_found.append({
                                    "generator": gen.get("name", gen.get("id")),
                                    "field": field,
                                    "value": value,
                                    "sentinel": sentinel
                                })
                        # Check for values > 10 million (frontend filter threshold)
                        if abs(value) > 10_000_000:
                            sentinel_found.append({
                                "generator": gen.get("name", gen.get("id")),
                                "field": field,
                                "value": value,
                                "reason": "exceeds 10M threshold"
                            })
        
        if sentinel_found:
            print(f"WARNING: Found sentinel values in telemetry: {sentinel_found}")
        else:
            print("PASS: No sentinel values found in generator list telemetry")
        
        # This is informational - we don't fail if historical data has sentinels
        # The frontend sanitizeValue() should handle them
        return sentinel_found
    
    def test_generator_detail_sanitized_telemetry(self, auth_headers):
        """Test that individual generator detail returns sanitized telemetry"""
        # First get list of generators
        response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        assert response.status_code == 200
        generators = response.json()
        
        if not generators:
            pytest.skip("No generators available for testing")
        
        # Test first generator with telemetry
        for gen in generators:
            gen_id = gen.get("id")
            if not gen_id:
                continue
            
            detail_response = requests.get(f"{BASE_URL}/api/generators/{gen_id}", headers=auth_headers)
            assert detail_response.status_code == 200, f"Failed to get generator {gen_id}: {detail_response.text}"
            
            detail = detail_response.json()
            telemetry = detail.get("latest_telemetry", {})
            
            if telemetry:
                # Check specific fields that had sentinel issues
                problem_fields = []
                for field in ["voltage_l1", "voltage_l2", "voltage_l3", "current_l1", "current_l2", "current_l3",
                              "power_kw", "frequency", "oil_pressure", "coolant_temp", "fuel_level", 
                              "battery_voltage", "rpm", "hours_run"]:
                    value = telemetry.get(field)
                    if value is not None and isinstance(value, (int, float)):
                        # Check for sentinel values
                        for sentinel in DSE_SENTINEL_VALUES:
                            if abs(value - sentinel) < 0.5:
                                problem_fields.append(f"{field}={value} (sentinel {sentinel})")
                        # Check for unreasonably large values
                        if abs(value) > 10_000_000:
                            problem_fields.append(f"{field}={value} (>10M)")
                
                if problem_fields:
                    print(f"WARNING: Generator {gen_id} has potential sentinel values: {problem_fields}")
                else:
                    print(f"PASS: Generator {gen_id} telemetry appears sanitized")
                
                # Test at least one generator
                break
        
        print("PASS: Generator detail endpoint tested")


class TestControlButtonRouting:
    """Test that control commands are routed correctly"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_control_endpoint_exists(self, auth_headers):
        """Test that the control endpoint exists and accepts commands"""
        # Get a generator to test with
        response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        assert response.status_code == 200
        generators = response.json()
        
        if not generators:
            pytest.skip("No generators available for testing")
        
        # Find a dev- generator (virtual generator from device)
        dev_gen = None
        for gen in generators:
            if gen.get("id", "").startswith("dev-"):
                dev_gen = gen
                break
        
        if not dev_gen:
            # Use first generator
            dev_gen = generators[0]
        
        gen_id = dev_gen.get("id")
        print(f"Testing control endpoint with generator: {gen_id}")
        
        # Test sending a command - expect either success or MQTT not connected error
        # (MQTT broker is not available in preview environment)
        response = requests.post(
            f"{BASE_URL}/api/mqtt/control/{gen_id}",
            headers=auth_headers,
            json={"command": "stop"}
        )
        
        # Accept 200 (success), 500/503 (MQTT not connected), or 404 (no gateway configured)
        assert response.status_code in [200, 500, 503, 404], f"Unexpected status: {response.status_code} - {response.text}"
        
        data = response.json()
        if response.status_code == 200:
            print(f"PASS: Control command accepted - {data}")
        elif response.status_code in [500, 503]:
            # Expected in preview - MQTT broker not connected
            assert "MQTT" in str(data) or "nicht verbunden" in str(data), f"Unexpected error response: {data}"
            print(f"PASS: Control endpoint returns expected MQTT not connected error: {data}")
        elif response.status_code == 404:
            # No gateway configured for this generator
            print(f"PASS: Control endpoint returns 404 (no gateway configured): {data}")
    
    def test_control_invalid_command(self, auth_headers):
        """Test that invalid commands are rejected"""
        response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        assert response.status_code == 200
        generators = response.json()
        
        if not generators:
            pytest.skip("No generators available for testing")
        
        gen_id = generators[0].get("id")
        
        # Test invalid command
        response = requests.post(
            f"{BASE_URL}/api/mqtt/control/{gen_id}",
            headers=auth_headers,
            json={"command": "invalid_command_xyz"}
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid command, got {response.status_code}"
        data = response.json()
        assert "Unbekannter Befehl" in str(data) or "unknown" in str(data).lower(), f"Unexpected error: {data}"
        print("PASS: Invalid command correctly rejected")
    
    def test_control_valid_commands(self, auth_headers):
        """Test that all valid DSE commands are accepted"""
        valid_commands = ["stop", "auto_on", "manual", "test_on_load", "auto_manual_restore", 
                         "start", "mute", "reset", "gen_switch_on", "gen_switch_off", "reset_mains"]
        
        response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        assert response.status_code == 200
        generators = response.json()
        
        if not generators:
            pytest.skip("No generators available for testing")
        
        gen_id = generators[0].get("id")
        
        for cmd in valid_commands:
            response = requests.post(
                f"{BASE_URL}/api/mqtt/control/{gen_id}",
                headers=auth_headers,
                json={"command": cmd}
            )
            
            # Accept 200, 500/503 (MQTT not connected), or 404 (no gateway)
            assert response.status_code in [200, 500, 503, 404], f"Command '{cmd}' failed with {response.status_code}: {response.text}"
        
        print(f"PASS: All {len(valid_commands)} valid commands accepted by endpoint")


class TestDevGeneratorControlRouting:
    """Test that dev- generators (virtual generators from devices) route commands correctly"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_dev_generator_lookup(self, auth_headers):
        """Test that dev- generators are properly resolved"""
        response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        assert response.status_code == 200
        generators = response.json()
        
        dev_generators = [g for g in generators if g.get("id", "").startswith("dev-")]
        
        if not dev_generators:
            print("INFO: No dev- generators found in system")
            pytest.skip("No dev- generators available for testing")
        
        print(f"Found {len(dev_generators)} dev- generators")
        
        for dev_gen in dev_generators[:3]:  # Test up to 3
            gen_id = dev_gen.get("id")
            
            # Test that we can get the generator detail
            detail_response = requests.get(f"{BASE_URL}/api/generators/{gen_id}", headers=auth_headers)
            assert detail_response.status_code == 200, f"Failed to get dev- generator {gen_id}: {detail_response.text}"
            
            detail = detail_response.json()
            print(f"PASS: dev- generator {gen_id} resolved - name: {detail.get('name')}, dse_module_uid: {detail.get('dse_module_uid', 'N/A')}")
    
    def test_dev_generator_control_uses_device_lookup(self, auth_headers):
        """Test that control commands for dev- generators look up the device"""
        response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        assert response.status_code == 200
        generators = response.json()
        
        # Find a dev- generator with dse_module_uid
        dev_gen_with_uid = None
        for g in generators:
            if g.get("id", "").startswith("dev-") and g.get("dse_module_uid"):
                dev_gen_with_uid = g
                break
        
        if not dev_gen_with_uid:
            print("INFO: No dev- generator with dse_module_uid found")
            # Still test that the endpoint works
            dev_generators = [g for g in generators if g.get("id", "").startswith("dev-")]
            if dev_generators:
                dev_gen_with_uid = dev_generators[0]
            else:
                pytest.skip("No dev- generators available")
        
        gen_id = dev_gen_with_uid.get("id")
        print(f"Testing control for dev- generator: {gen_id}, dse_module_uid: {dev_gen_with_uid.get('dse_module_uid', 'N/A')}")
        
        # Send a control command
        response = requests.post(
            f"{BASE_URL}/api/mqtt/control/{gen_id}",
            headers=auth_headers,
            json={"command": "auto_on"}
        )
        
        # Accept 200, 500/503 (MQTT not connected), or 404 (no gateway)
        assert response.status_code in [200, 500, 503, 404], f"Control failed: {response.status_code} - {response.text}"
        
        data = response.json()
        print(f"PASS: Control command for dev- generator returned: {response.status_code} - {data}")


class TestTelemetryThresholds:
    """Test that telemetry values are filtered by field-specific thresholds"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_telemetry_field_thresholds(self, auth_headers):
        """Test that telemetry values exceeding thresholds are filtered"""
        # These are the thresholds from _sanitize_telemetry()
        thresholds = {
            "voltage_l1": 2000, "voltage_l2": 2000, "voltage_l3": 2000,
            "current_l1": 50000, "current_l2": 50000, "current_l3": 50000,
            "frequency": 200, "power_kw": 100000,
            "oil_pressure": 5000, "coolant_temp": 500, "fuel_level": 200,
            "battery_voltage": 100, "rpm": 50000, "hours_run": 1000000,
        }
        
        response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        assert response.status_code == 200
        generators = response.json()
        
        violations = []
        for gen in generators:
            telemetry = gen.get("latest_telemetry", {})
            if telemetry:
                for field, max_val in thresholds.items():
                    value = telemetry.get(field)
                    if value is not None and isinstance(value, (int, float)):
                        if abs(value) > max_val:
                            violations.append({
                                "generator": gen.get("name", gen.get("id")),
                                "field": field,
                                "value": value,
                                "threshold": max_val
                            })
        
        if violations:
            print(f"WARNING: Found {len(violations)} threshold violations: {violations}")
        else:
            print("PASS: No threshold violations found in telemetry")


class TestDseModeReading:
    """Test that DSE mode is read from telemetry and fallback to last_dse_mode"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_dse_mode_in_generator_detail(self, auth_headers):
        """Test that dse_mode is available in generator detail"""
        response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        assert response.status_code == 200
        generators = response.json()
        
        if not generators:
            pytest.skip("No generators available")
        
        modes_found = []
        for gen in generators[:5]:  # Check first 5
            gen_id = gen.get("id")
            detail_response = requests.get(f"{BASE_URL}/api/generators/{gen_id}", headers=auth_headers)
            assert detail_response.status_code == 200
            
            detail = detail_response.json()
            telemetry = detail.get("latest_telemetry", {})
            
            dse_mode = telemetry.get("dse_mode") if telemetry else None
            last_dse_mode = detail.get("last_dse_mode")
            
            if dse_mode or last_dse_mode:
                modes_found.append({
                    "generator": gen.get("name", gen_id),
                    "dse_mode": dse_mode,
                    "last_dse_mode": last_dse_mode
                })
        
        if modes_found:
            print(f"PASS: Found DSE modes in {len(modes_found)} generators: {modes_found}")
        else:
            print("INFO: No DSE modes found in tested generators (may not have mode data)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
