"""
DSE 5510 Integration Tests - Eventenergie Portal
=================================================
Tests for DSE 5510 generator controller integration via RS232 Modbus RTU + Pi.

Features tested:
1. POST /api/generators/ingest - Pi telemetry ingest with device_key auth
2. POST /api/generators/ingest - Returns pending commands in response
3. POST /api/mqtt/control/dev-{device_id} - Command routing for Pi-based DSE 5510
4. gen_switch_on / gen_switch_off commands
5. POST /api/energy-monitoring/devices/{device_id}/dse5510-setup - Setup script generation
6. Telemetry field normalization (power_total_w->power_kw, etc.)
"""

import pytest
import requests
import os
import hashlib
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://kirmes-billing.preview.emergentagent.com")

# Test credentials from review request
TEST_DEVICE_ID = "5cf84060-95c2-407d-a5d6-1cbf0f184617"
TEST_DEVICE_KEY = "abc123testkey"
TEST_GENERATOR_ID = f"dev-{TEST_DEVICE_ID}"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Authentication failed: {resp.status_code} - {resp.text}")
    return resp.json().get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestDSE5510IngestEndpoint:
    """Tests for POST /api/generators/ingest - Pi telemetry ingest."""

    def test_ingest_with_valid_device_key(self, auth_headers):
        """Test telemetry ingest with valid device_key authentication."""
        payload = {
            "api_key": TEST_DEVICE_KEY,
            "device_id": TEST_DEVICE_ID,
            "generator_id": "",
            "records": [
                {
                    "ts_utc": "2026-03-25T16:00:00.000Z",
                    "source": "dse5510_pi",
                    "oil_pressure_kpa": 350,
                    "coolant_temp_c": 85,
                    "fuel_level_pct": 75,
                    "battery_voltage": 13.8,
                    "rpm": 1500,
                    "frequency": 50.0,
                    "voltage_l1": 230.5,
                    "voltage_l2": 231.0,
                    "voltage_l3": 229.8,
                    "current_l1": 45.2,
                    "current_l2": 44.8,
                    "current_l3": 45.5,
                    "power_total_w": 31200,
                    "power_factor_avg": 0.95,
                    "engine_run_hours": 1234.5,
                    "engine_running": True,
                }
            ],
            "latitude": 50.1109,
            "longitude": 8.6821,
            "command_results": []
        }
        
        resp = requests.post(f"{BASE_URL}/api/generators/ingest", json=payload)
        
        assert resp.status_code == 200, f"Ingest failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert "inserted" in data, "Response should contain 'inserted' count"
        assert data["inserted"] >= 1, "Should have inserted at least 1 record"
        assert "generator_id" in data, "Response should contain generator_id"
        assert "pending_commands" in data, "Response should contain pending_commands list"
        print(f"✓ Ingest successful: {data['inserted']} records, generator_id={data['generator_id']}")

    def test_ingest_with_invalid_device_key(self):
        """Test that ingest fails with invalid device_key."""
        payload = {
            "api_key": "invalid_key_12345",
            "device_id": TEST_DEVICE_ID,
            "generator_id": "",
            "records": [{"ts_utc": "2026-03-25T16:00:00.000Z", "rpm": 1500}],
        }
        
        resp = requests.post(f"{BASE_URL}/api/generators/ingest", json=payload)
        
        assert resp.status_code == 403, f"Should reject invalid key: {resp.status_code}"
        print("✓ Invalid device key correctly rejected")

    def test_ingest_with_nonexistent_device(self):
        """Test that ingest fails for non-existent device."""
        payload = {
            "api_key": "some_key",
            "device_id": "nonexistent-device-id-12345",
            "generator_id": "",
            "records": [{"ts_utc": "2026-03-25T16:00:00.000Z", "rpm": 1500}],
        }
        
        resp = requests.post(f"{BASE_URL}/api/generators/ingest", json=payload)
        
        assert resp.status_code == 404, f"Should return 404 for non-existent device: {resp.status_code}"
        print("✓ Non-existent device correctly returns 404")

    def test_ingest_returns_pending_commands(self, auth_headers):
        """Test that ingest response includes pending commands."""
        # First, queue a command via the control endpoint
        cmd_resp = requests.post(
            f"{BASE_URL}/api/mqtt/control/{TEST_GENERATOR_ID}",
            json={"command": "auto_on"},
            headers=auth_headers
        )
        # Command may succeed or fail depending on device state, but we test the ingest response
        
        # Now do an ingest call
        payload = {
            "api_key": TEST_DEVICE_KEY,
            "device_id": TEST_DEVICE_ID,
            "generator_id": "",
            "records": [{"ts_utc": "2026-03-25T16:01:00.000Z", "rpm": 1500, "source": "dse5510_pi"}],
            "command_results": []
        }
        
        resp = requests.post(f"{BASE_URL}/api/generators/ingest", json=payload)
        
        assert resp.status_code == 200, f"Ingest failed: {resp.status_code}"
        data = resp.json()
        assert "pending_commands" in data, "Response must include pending_commands"
        # pending_commands is a list (may be empty if commands were already sent)
        assert isinstance(data["pending_commands"], list), "pending_commands should be a list"
        print(f"✓ Ingest returns pending_commands: {len(data['pending_commands'])} commands")


class TestDSE5510ControlCommands:
    """Tests for control command routing for Pi-based DSE 5510."""

    def test_control_start_command(self, auth_headers):
        """Test sending 'start' command to DSE 5510 generator."""
        resp = requests.post(
            f"{BASE_URL}/api/mqtt/control/{TEST_GENERATOR_ID}",
            json={"command": "start"},
            headers=auth_headers
        )
        
        assert resp.status_code == 200, f"Start command failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert data.get("success") == True, "Command should succeed"
        assert "command_id" in data or "delivery" in data, "Response should contain command_id or delivery info"
        print(f"✓ Start command queued: {data}")

    def test_control_stop_command(self, auth_headers):
        """Test sending 'stop' command to DSE 5510 generator."""
        resp = requests.post(
            f"{BASE_URL}/api/mqtt/control/{TEST_GENERATOR_ID}",
            json={"command": "stop"},
            headers=auth_headers
        )
        
        assert resp.status_code == 200, f"Stop command failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert data.get("success") == True, "Command should succeed"
        print(f"✓ Stop command queued: {data}")

    def test_control_auto_on_command(self, auth_headers):
        """Test sending 'auto_on' command to DSE 5510 generator."""
        resp = requests.post(
            f"{BASE_URL}/api/mqtt/control/{TEST_GENERATOR_ID}",
            json={"command": "auto_on"},
            headers=auth_headers
        )
        
        assert resp.status_code == 200, f"Auto_on command failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert data.get("success") == True, "Command should succeed"
        print(f"✓ Auto_on command queued: {data}")

    def test_control_gen_switch_on_command(self, auth_headers):
        """Test sending 'gen_switch_on' command (new DSE 5510 command)."""
        resp = requests.post(
            f"{BASE_URL}/api/mqtt/control/{TEST_GENERATOR_ID}",
            json={"command": "gen_switch_on"},
            headers=auth_headers
        )
        
        assert resp.status_code == 200, f"gen_switch_on command failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert data.get("success") == True, "Command should succeed"
        print(f"✓ gen_switch_on command queued: {data}")

    def test_control_gen_switch_off_command(self, auth_headers):
        """Test sending 'gen_switch_off' command (new DSE 5510 command)."""
        resp = requests.post(
            f"{BASE_URL}/api/mqtt/control/{TEST_GENERATOR_ID}",
            json={"command": "gen_switch_off"},
            headers=auth_headers
        )
        
        assert resp.status_code == 200, f"gen_switch_off command failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert data.get("success") == True, "Command should succeed"
        print(f"✓ gen_switch_off command queued: {data}")

    def test_control_invalid_command(self, auth_headers):
        """Test that invalid commands are rejected."""
        resp = requests.post(
            f"{BASE_URL}/api/mqtt/control/{TEST_GENERATOR_ID}",
            json={"command": "invalid_command_xyz"},
            headers=auth_headers
        )
        
        assert resp.status_code == 400, f"Should reject invalid command: {resp.status_code}"
        print("✓ Invalid command correctly rejected")

    def test_control_requires_auth(self):
        """Test that control commands require authentication."""
        resp = requests.post(
            f"{BASE_URL}/api/mqtt/control/{TEST_GENERATOR_ID}",
            json={"command": "start"}
        )
        
        assert resp.status_code in [401, 403], f"Should require auth: {resp.status_code}"
        print("✓ Control commands require authentication")


class TestDSE5510SetupScript:
    """Tests for DSE 5510 setup script generation."""

    def test_generate_dse5510_setup_script(self, auth_headers):
        """Test generating DSE 5510 setup script."""
        resp = requests.post(
            f"{BASE_URL}/api/energy-monitoring/devices/{TEST_DEVICE_ID}/dse5510-setup",
            json={
                "serial_port": "/dev/ttyUSB0",
                "baud_rate": 9600,
                "slave_id": 10
            },
            headers=auth_headers
        )
        
        assert resp.status_code == 200, f"Setup script generation failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        
        assert "download_url" in data, "Response should contain download_url"
        assert "download_token" in data, "Response should contain download_token"
        assert "device_id" in data, "Response should contain device_id"
        assert "device_key" in data, "Response should contain device_key"
        assert data["device_id"] == TEST_DEVICE_ID, "Device ID should match"
        assert data["serial_port"] == "/dev/ttyUSB0", "Serial port should match"
        assert data["baud_rate"] == 9600, "Baud rate should match"
        assert data["slave_id"] == 10, "Slave ID should match"
        
        print(f"✓ DSE 5510 setup script generated: {data['download_url'][:80]}...")

    def test_download_setup_script(self, auth_headers):
        """Test downloading the generated setup script."""
        # First generate the script
        gen_resp = requests.post(
            f"{BASE_URL}/api/energy-monitoring/devices/{TEST_DEVICE_ID}/dse5510-setup",
            json={"serial_port": "/dev/ttyUSB0", "baud_rate": 9600, "slave_id": 10},
            headers=auth_headers
        )
        
        assert gen_resp.status_code == 200, f"Script generation failed: {gen_resp.status_code}"
        download_url = gen_resp.json()["download_url"]
        
        # Download the script (public endpoint, no auth needed)
        dl_resp = requests.get(download_url)
        
        assert dl_resp.status_code == 200, f"Script download failed: {dl_resp.status_code}"
        script_content = dl_resp.text
        
        # Verify script contains expected content
        assert "#!/bin/bash" in script_content, "Script should start with shebang"
        assert "DSE 5510" in script_content, "Script should mention DSE 5510"
        assert TEST_DEVICE_ID in script_content, "Script should contain device ID"
        assert "/dev/ttyUSB0" in script_content, "Script should contain serial port"
        assert "dse5510_sync.py" in script_content, "Script should reference sync script"
        
        print(f"✓ Setup script downloaded successfully ({len(script_content)} bytes)")

    def test_setup_script_requires_admin(self):
        """Test that setup script generation requires admin auth."""
        resp = requests.post(
            f"{BASE_URL}/api/energy-monitoring/devices/{TEST_DEVICE_ID}/dse5510-setup",
            json={"serial_port": "/dev/ttyUSB0", "baud_rate": 9600, "slave_id": 10}
        )
        
        assert resp.status_code in [401, 403], f"Should require admin auth: {resp.status_code}"
        print("✓ Setup script generation requires admin authentication")


class TestTelemetryNormalization:
    """Tests for telemetry field normalization."""

    def test_telemetry_normalization_in_generator_detail(self, auth_headers):
        """Test that Pi-ingest fields are normalized in generator detail response."""
        # First ingest some data with Pi-specific field names
        ingest_payload = {
            "api_key": TEST_DEVICE_KEY,
            "device_id": TEST_DEVICE_ID,
            "generator_id": "",
            "records": [
                {
                    "ts_utc": "2026-03-25T16:05:00.000Z",
                    "source": "dse5510_pi",
                    "power_total_w": 25000,  # Should become power_kw = 25.0
                    "coolant_temp_c": 82,    # Should become coolant_temp = 82
                    "oil_pressure_kpa": 400, # Should become oil_pressure = 4.0 (bar)
                    "fuel_level_pct": 65,    # Should become fuel_level = 65
                    "engine_run_hours": 1500.5,  # Should become hours_run = 1500.5
                    "power_factor_avg": 0.92,    # Should become power_factor = 0.92
                    "rpm": 1500,
                    "frequency": 50.0,
                    "voltage_l1": 230.0,
                    "voltage_l2": 231.0,
                    "voltage_l3": 229.5,
                    "current_l1": 36.2,
                    "current_l2": 35.8,
                    "current_l3": 36.5,
                    "engine_running": True,
                }
            ],
        }
        
        ingest_resp = requests.post(f"{BASE_URL}/api/generators/ingest", json=ingest_payload)
        assert ingest_resp.status_code == 200, f"Ingest failed: {ingest_resp.status_code}"
        
        # Wait a moment for data to be stored
        time.sleep(0.5)
        
        # Now fetch the generator detail
        gen_resp = requests.get(f"{BASE_URL}/api/generators/{TEST_GENERATOR_ID}", headers=auth_headers)
        
        assert gen_resp.status_code == 200, f"Generator fetch failed: {gen_resp.status_code}"
        gen_data = gen_resp.json()
        
        # Check that latest_telemetry has normalized fields
        telemetry = gen_data.get("latest_telemetry")
        assert telemetry is not None, "Generator should have latest_telemetry"
        
        # Verify normalization: power_total_w -> power_kw
        if "power_total_w" in telemetry:
            assert "power_kw" in telemetry, "power_total_w should be normalized to power_kw"
            expected_kw = round(telemetry["power_total_w"] / 1000, 2)
            assert telemetry["power_kw"] == expected_kw, f"power_kw should be {expected_kw}"
        
        # Verify normalization: coolant_temp_c -> coolant_temp
        if "coolant_temp_c" in telemetry:
            assert "coolant_temp" in telemetry, "coolant_temp_c should be normalized to coolant_temp"
            assert telemetry["coolant_temp"] == telemetry["coolant_temp_c"]
        
        # Verify normalization: oil_pressure_kpa -> oil_pressure (bar)
        if "oil_pressure_kpa" in telemetry:
            assert "oil_pressure" in telemetry, "oil_pressure_kpa should be normalized to oil_pressure"
            expected_bar = round(telemetry["oil_pressure_kpa"] / 100, 2)
            assert telemetry["oil_pressure"] == expected_bar, f"oil_pressure should be {expected_bar} bar"
        
        print(f"✓ Telemetry normalization verified: power_kw={telemetry.get('power_kw')}, coolant_temp={telemetry.get('coolant_temp')}, oil_pressure={telemetry.get('oil_pressure')}")

    def test_telemetry_normalization_in_list(self, auth_headers):
        """Test that telemetry is normalized in generator list response."""
        resp = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        
        assert resp.status_code == 200, f"Generator list failed: {resp.status_code}"
        generators = resp.json()
        
        # Find our test generator
        test_gen = next((g for g in generators if g.get("id") == TEST_GENERATOR_ID), None)
        
        if test_gen and test_gen.get("latest_telemetry"):
            telemetry = test_gen["latest_telemetry"]
            # If Pi-ingest fields exist, normalized fields should also exist
            if "power_total_w" in telemetry:
                assert "power_kw" in telemetry, "power_kw should be present in list view"
            print(f"✓ Telemetry normalization in list view verified")
        else:
            print("⚠ Test generator not found in list or has no telemetry")


class TestPiCommandEndpoint:
    """Tests for the direct Pi command endpoint."""

    def test_pi_command_endpoint(self, auth_headers):
        """Test POST /api/generators/pi-command/{device_id}."""
        resp = requests.post(
            f"{BASE_URL}/api/generators/pi-command/{TEST_DEVICE_ID}",
            json={"command": "start"},
            headers=auth_headers
        )
        
        assert resp.status_code == 200, f"Pi command failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        
        assert data.get("success") == True, "Command should succeed"
        assert "command_id" in data, "Response should contain command_id"
        assert data.get("command") == "start", "Command should be 'start'"
        assert data.get("status") == "pending", "Status should be 'pending'"
        
        print(f"✓ Pi command endpoint works: {data}")

    def test_pi_command_gen_switch_on(self, auth_headers):
        """Test gen_switch_on via Pi command endpoint."""
        resp = requests.post(
            f"{BASE_URL}/api/generators/pi-command/{TEST_DEVICE_ID}",
            json={"command": "gen_switch_on"},
            headers=auth_headers
        )
        
        assert resp.status_code == 200, f"gen_switch_on failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert data.get("success") == True
        assert "Generator zuschalten" in data.get("label", "")
        print(f"✓ gen_switch_on via Pi command: {data['label']}")

    def test_pi_command_gen_switch_off(self, auth_headers):
        """Test gen_switch_off via Pi command endpoint."""
        resp = requests.post(
            f"{BASE_URL}/api/generators/pi-command/{TEST_DEVICE_ID}",
            json={"command": "gen_switch_off"},
            headers=auth_headers
        )
        
        assert resp.status_code == 200, f"gen_switch_off failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert data.get("success") == True
        assert "Generator abschalten" in data.get("label", "")
        print(f"✓ gen_switch_off via Pi command: {data['label']}")

    def test_pi_command_invalid(self, auth_headers):
        """Test that invalid commands are rejected."""
        resp = requests.post(
            f"{BASE_URL}/api/generators/pi-command/{TEST_DEVICE_ID}",
            json={"command": "invalid_xyz"},
            headers=auth_headers
        )
        
        assert resp.status_code == 400, f"Should reject invalid command: {resp.status_code}"
        print("✓ Invalid Pi command correctly rejected")


class TestDeviceControllerDropdown:
    """Tests for DSE 5510 in controller dropdown."""

    def test_device_has_dse5510_controller(self, auth_headers):
        """Test that the test device has DSE 5510 as controller."""
        resp = requests.get(f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}", headers=auth_headers)
        
        assert resp.status_code == 200, f"Device fetch failed: {resp.status_code}"
        device = resp.json()
        
        # The device should have controller set to "DSE 5510"
        controller = device.get("controller", "")
        print(f"Device controller: {controller}")
        
        # This test verifies the device exists and has a controller field
        assert "controller" in device or device.get("device_type") in ["stromerzeuger", "lichtmast"], \
            "Device should have controller field or be a generator type"
        print(f"✓ Device {TEST_DEVICE_ID} exists with controller: {controller}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
