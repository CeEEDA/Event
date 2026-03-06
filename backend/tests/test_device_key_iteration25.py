"""
Iteration 25 - Per-Device Key Management Tests
Tests for self-onboarding Messkoffer with encrypted device keys:
- POST /api/energy-monitoring/devices/{id}/generate-key - generates SHA-256 hashed key
- GET /api/energy-monitoring/devices/{id}/key-info - returns has_key, prefix, created_at
- POST /api/energy-monitoring/ingest - authenticates with per-device key
- POST /api/energy-monitoring/ingest - rejects wrong key with 401
- GET /api/energy-monitoring/ingest/sync-state - works with per-device key
- Download endpoints for sync files (emu_sync.py, emu_sync.service, emu_sync.conf)
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from previous iteration
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"
DEVICE_ID_MK001 = "1d35dfbf-c944-4127-abe6-c0f97ed3b165"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Auth headers for admin requests"""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestDeviceKeyGeneration:
    """Test device key generation endpoint"""

    def test_generate_key_returns_plain_key(self, api_client, auth_headers):
        """POST /api/energy-monitoring/devices/{id}/generate-key returns 48 char hex key"""
        response = api_client.post(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}/generate-key",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Generate key failed: {response.text}"
        
        data = response.json()
        assert "device_key" in data, "Response missing device_key"
        assert "prefix" in data, "Response missing prefix"
        assert "message" in data, "Response missing message"
        
        # Key should be 48 hex chars (24 bytes)
        device_key = data["device_key"]
        assert len(device_key) == 48, f"Key should be 48 chars, got {len(device_key)}"
        assert device_key.isalnum(), "Key should be alphanumeric"
        
        # Prefix should be first 8 chars
        assert data["prefix"] == device_key[:8], "Prefix should be first 8 chars of key"
        
        print(f"Generated key: {device_key[:8]}... (prefix shown)")
        
        # Store for next test
        TestDeviceKeyGeneration.generated_key = device_key
        
    def test_generate_key_requires_admin(self, api_client):
        """Generate key requires admin authentication"""
        response = api_client.post(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}/generate-key"
        )
        assert response.status_code in [401, 403], f"Should require auth: {response.status_code}"

    def test_generate_key_404_for_nonexistent_device(self, api_client, auth_headers):
        """Generate key returns 404 for non-existent device"""
        fake_id = str(uuid.uuid4())
        response = api_client.post(
            f"{BASE_URL}/api/energy-monitoring/devices/{fake_id}/generate-key",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Should return 404: {response.status_code}"


class TestDeviceKeyInfo:
    """Test key info endpoint"""

    def test_key_info_shows_has_key_true(self, api_client, auth_headers):
        """GET /api/energy-monitoring/devices/{id}/key-info returns has_key, prefix, created_at"""
        response = api_client.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}/key-info",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Key info failed: {response.text}"
        
        data = response.json()
        assert "has_key" in data, "Response missing has_key"
        assert "prefix" in data, "Response missing prefix"
        assert "created_at" in data, "Response missing created_at"
        
        assert data["has_key"] == True, "has_key should be True after generation"
        assert len(data["prefix"]) == 8, f"Prefix should be 8 chars, got {len(data['prefix'])}"
        assert data["created_at"] != "", "created_at should not be empty"
        
        print(f"Key info: has_key={data['has_key']}, prefix={data['prefix']}")

    def test_key_info_requires_admin(self, api_client):
        """Key info requires admin authentication"""
        response = api_client.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}/key-info"
        )
        assert response.status_code in [401, 403], f"Should require auth: {response.status_code}"


class TestIngestWithDeviceKey:
    """Test ingest endpoint with per-device key authentication"""

    def test_ingest_with_correct_device_key(self, api_client, auth_headers):
        """POST /api/energy-monitoring/ingest succeeds with correct device key"""
        # First generate a fresh key to ensure we have a valid one
        gen_response = api_client.post(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}/generate-key",
            headers=auth_headers
        )
        assert gen_response.status_code == 200, f"Key generation failed: {gen_response.text}"
        device_key = gen_response.json()["device_key"]
        
        # Get a meter_id for this device
        device_response = api_client.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}",
            headers=auth_headers
        )
        assert device_response.status_code == 200, f"Get device failed: {device_response.text}"
        meters = device_response.json().get("meters", [])
        
        if not meters:
            pytest.skip("No meters found for device - skipping ingest test")
        
        meter_id = meters[0]["id"]
        
        # Attempt ingest with device key
        payload = {
            "api_key": device_key,
            "device_id": DEVICE_ID_MK001,
            "meter_id": meter_id,
            "records": [
                {
                    "ts_utc": "2026-01-15T10:00:00+00:00",
                    "meter_ts": 1736935200,
                    "I_L1": 10.5,
                    "I_L2": 10.3,
                    "I_L3": 10.2,
                    "U_L1": 230.1,
                    "U_L2": 230.2,
                    "U_L3": 230.3,
                    "P_sum_kW": 7.2,
                    "id": 99999001
                }
            ],
            "last_sync_id": 99999001
        }
        
        response = api_client.post(f"{BASE_URL}/api/energy-monitoring/ingest", json=payload)
        assert response.status_code == 200, f"Ingest with device key failed: {response.text}"
        
        data = response.json()
        assert "inserted" in data, "Response missing inserted count"
        assert data["inserted"] >= 1, f"Should insert at least 1 record: {data}"
        
        print(f"Ingest successful: {data['inserted']} records inserted")
        
        # Store key for next tests
        TestIngestWithDeviceKey.valid_key = device_key
        TestIngestWithDeviceKey.meter_id = meter_id

    def test_ingest_rejects_wrong_key(self, api_client):
        """POST /api/energy-monitoring/ingest returns 401 with wrong key"""
        meter_id = getattr(TestIngestWithDeviceKey, 'meter_id', None)
        if not meter_id:
            pytest.skip("No meter_id available from previous test")
        
        payload = {
            "api_key": "wrongkey123456789012345678901234567890123456",  # 48 chars but invalid
            "device_id": DEVICE_ID_MK001,
            "meter_id": meter_id,
            "records": [{"ts_utc": "2026-01-15T11:00:00+00:00", "id": 99999002}],
            "last_sync_id": 99999002
        }
        
        response = api_client.post(f"{BASE_URL}/api/energy-monitoring/ingest", json=payload)
        assert response.status_code == 401, f"Should reject wrong key with 401: {response.status_code} - {response.text}"
        
        print(f"Correctly rejected wrong key with 401")


class TestSyncStateWithDeviceKey:
    """Test sync state endpoint with per-device key"""

    def test_sync_state_with_valid_key(self, api_client, auth_headers):
        """GET /api/energy-monitoring/ingest/sync-state works with device key"""
        # First ensure we have a valid key
        gen_response = api_client.post(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}/generate-key",
            headers=auth_headers
        )
        assert gen_response.status_code == 200
        device_key = gen_response.json()["device_key"]
        
        # Get meter
        device_response = api_client.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}",
            headers=auth_headers
        )
        meters = device_response.json().get("meters", [])
        if not meters:
            pytest.skip("No meters found")
        meter_id = meters[0]["id"]
        
        # Request sync state
        response = api_client.get(
            f"{BASE_URL}/api/energy-monitoring/ingest/sync-state",
            params={
                "device_id": DEVICE_ID_MK001,
                "meter_id": meter_id,
                "api_key": device_key
            }
        )
        assert response.status_code == 200, f"Sync state failed: {response.text}"
        
        data = response.json()
        assert "last_sync_id" in data, "Response missing last_sync_id"
        
        print(f"Sync state: last_sync_id={data['last_sync_id']}")

    def test_sync_state_rejects_wrong_key(self, api_client, auth_headers):
        """GET /api/energy-monitoring/ingest/sync-state returns 401 with wrong key"""
        # Get meter
        device_response = api_client.get(
            f"{BASE_URL}/api/energy-monitoring/devices/{DEVICE_ID_MK001}",
            headers=auth_headers
        )
        meters = device_response.json().get("meters", [])
        if not meters:
            pytest.skip("No meters found")
        meter_id = meters[0]["id"]
        
        response = api_client.get(
            f"{BASE_URL}/api/energy-monitoring/ingest/sync-state",
            params={
                "device_id": DEVICE_ID_MK001,
                "meter_id": meter_id,
                "api_key": "invalidkey12345678901234567890123456789012345"
            }
        )
        assert response.status_code == 401, f"Should reject wrong key: {response.status_code}"


class TestDownloadEndpoints:
    """Test download endpoints for Pi sync files"""

    def test_download_sync_script(self, api_client):
        """GET /api/download-sync-script returns Python script"""
        response = api_client.get(f"{BASE_URL}/api/download-sync-script")
        assert response.status_code == 200, f"Download script failed: {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "python" in content_type or "text/plain" in content_type or "octet-stream" in content_type, \
            f"Unexpected content type: {content_type}"
        
        # Check content contains Python code
        content = response.text
        assert "#!/usr/bin/env python3" in content or "import" in content, \
            "File should contain Python code"
        assert "emu_sync" in content.lower() or "sync" in content.lower(), \
            "File should be the sync script"
        
        print(f"Sync script downloaded: {len(content)} bytes")

    def test_download_sync_service(self, api_client):
        """GET /api/download-sync-service returns systemd service file"""
        response = api_client.get(f"{BASE_URL}/api/download-sync-service")
        assert response.status_code == 200, f"Download service failed: {response.status_code}"
        
        content = response.text
        assert "[Unit]" in content or "[Service]" in content, \
            "File should be a systemd service file"
        
        print(f"Sync service downloaded: {len(content)} bytes")

    def test_download_sync_config(self, api_client):
        """GET /api/download-sync-config returns config template"""
        response = api_client.get(f"{BASE_URL}/api/download-sync-config")
        assert response.status_code == 200, f"Download config failed: {response.status_code}"
        
        content = response.text
        assert "[emu_sync]" in content or "api_url" in content, \
            "File should be a config template"
        assert "device_key" in content or "device_id" in content, \
            "Config should have device fields"
        
        print(f"Sync config downloaded: {len(content)} bytes")


class TestKeyInfoForNewDevice:
    """Test key info returns correct state for device without key"""

    def test_key_info_for_device_before_key_generation(self, api_client, auth_headers):
        """Create a new device and check key info shows has_key=false"""
        # Create a new Messkoffer device
        create_payload = {
            "device_type": "messkoffer",
            "serial_number": f"TEST-MK-{uuid.uuid4().hex[:8].upper()}",
            "model": "Test Messkoffer",
            "power_output": "32A"
        }
        
        create_response = api_client.post(
            f"{BASE_URL}/api/devices",
            headers=auth_headers,
            json=create_payload
        )
        assert create_response.status_code in [200, 201], f"Create device failed: {create_response.text}"
        
        new_device_id = create_response.json()["id"]
        
        try:
            # Check key info shows no key
            key_response = api_client.get(
                f"{BASE_URL}/api/energy-monitoring/devices/{new_device_id}/key-info",
                headers=auth_headers
            )
            assert key_response.status_code == 200
            
            data = key_response.json()
            assert data["has_key"] == False, "New device should have no key"
            assert data["prefix"] == "", "New device should have empty prefix"
            
            print(f"New device {new_device_id} correctly shows has_key=false")
            
        finally:
            # Cleanup: delete test device
            api_client.delete(f"{BASE_URL}/api/devices/{new_device_id}", headers=auth_headers)
