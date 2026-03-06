"""
Device Management API Tests
Tests CRUD operations, copy, document upload, and admin-only access
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"
KUNDE_EMAIL = "kunde1@test.com"
KUNDE_PASSWORD = "password"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def kunde_token():
    """Get kunde (non-admin) authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": KUNDE_EMAIL,
        "password": KUNDE_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Kunde authentication failed")


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture
def kunde_headers(kunde_token):
    return {"Authorization": f"Bearer {kunde_token}", "Content-Type": "application/json"}


class TestDeviceListAndGet:
    """Test GET /api/devices and GET /api/devices/{id}"""
    
    def test_admin_can_list_devices(self, admin_headers):
        """Admin should be able to list all devices"""
        response = requests.get(f"{BASE_URL}/api/devices", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        # Should have existing test devices
        if len(data) > 0:
            device = data[0]
            assert "id" in device
            assert "device_type" in device
            assert "serial_number" in device
            assert "document_count" in device
            print(f"PASS: Admin listed {len(data)} devices")

    def test_kunde_cannot_list_devices(self, kunde_headers):
        """Non-admin users should NOT be able to access device list"""
        response = requests.get(f"{BASE_URL}/api/devices", headers=kunde_headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("PASS: Kunde correctly blocked from listing devices")

    def test_admin_can_get_single_device(self, admin_headers):
        """Admin should be able to get a single device by ID"""
        # First get the list to find an ID
        list_response = requests.get(f"{BASE_URL}/api/devices", headers=admin_headers)
        assert list_response.status_code == 200
        devices = list_response.json()
        if not devices:
            pytest.skip("No devices to test with")
        
        device_id = devices[0]["id"]
        response = requests.get(f"{BASE_URL}/api/devices/{device_id}", headers=admin_headers)
        assert response.status_code == 200
        device = response.json()
        assert device["id"] == device_id
        assert "documents" in device  # Single device should include documents array
        print(f"PASS: Admin retrieved device {device['serial_number']}")


class TestDeviceCreate:
    """Test POST /api/devices - Create new device"""
    
    def test_create_stromerzeuger(self, admin_headers):
        """Create a new Stromerzeuger device with all fields"""
        serial = f"TEST-GEN-{uuid.uuid4().hex[:6].upper()}"
        payload = {
            "device_type": "stromerzeuger",
            "serial_number": serial,
            "user_field": "Test Generator",
            "latitude": 50.1109,
            "longitude": 8.6821,
            "model": "QAS 200",
            "engine_manufacturer": "Volvo",
            "engine_type": "TAD1345VE",
            "engine_number": f"ENG-{uuid.uuid4().hex[:6]}",
            "generator_manufacturer": "Stamford",
            "generator_type": "UCI274H",
            "generator_number": f"GEN-{uuid.uuid4().hex[:6]}",
            "year_of_manufacture": 2024,
            "power_output": "200 kVA",
            "controller": "DSE8610MK2",
            "last_maintenance": "2025-01-15",
            "next_maintenance": "2026-01-15",
            "notes": "Created by automated test"
        }
        
        response = requests.post(f"{BASE_URL}/api/devices", headers=admin_headers, json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        device = response.json()
        assert device["serial_number"] == serial
        assert device["device_type"] == "stromerzeuger"
        assert device["model"] == "QAS 200"
        assert device["latitude"] == 50.1109
        assert device["longitude"] == 8.6821
        assert "id" in device
        assert "created_at" in device
        print(f"PASS: Created stromerzeuger with serial {serial}")
        
        # Cleanup - store ID for later deletion
        return device["id"]

    def test_create_lichtmast(self, admin_headers):
        """Create a new Lichtmast device"""
        serial = f"TEST-LM-{uuid.uuid4().hex[:6].upper()}"
        payload = {
            "device_type": "lichtmast",
            "serial_number": serial,
            "user_field": "Test Lichtmast",
            "model": "LED Tower 4x500W"
        }
        
        response = requests.post(f"{BASE_URL}/api/devices", headers=admin_headers, json=payload)
        assert response.status_code == 200
        device = response.json()
        assert device["device_type"] == "lichtmast"
        print(f"PASS: Created lichtmast with serial {serial}")

    def test_create_messkoffer(self, admin_headers):
        """Create a new Messkoffer device"""
        serial = f"TEST-MK-{uuid.uuid4().hex[:6].upper()}"
        payload = {
            "device_type": "messkoffer",
            "serial_number": serial,
            "user_field": "Messkoffer für Baustelle B"
        }
        
        response = requests.post(f"{BASE_URL}/api/devices", headers=admin_headers, json=payload)
        assert response.status_code == 200
        device = response.json()
        assert device["device_type"] == "messkoffer"
        print(f"PASS: Created messkoffer with serial {serial}")

    def test_create_kirmeskiste(self, admin_headers):
        """Create a new Kirmeskiste device"""
        serial = f"TEST-KK-{uuid.uuid4().hex[:6].upper()}"
        payload = {
            "device_type": "kirmeskiste",
            "serial_number": serial,
            "user_field": "Kirmeskiste Event X"
        }
        
        response = requests.post(f"{BASE_URL}/api/devices", headers=admin_headers, json=payload)
        assert response.status_code == 200
        device = response.json()
        assert device["device_type"] == "kirmeskiste"
        print(f"PASS: Created kirmeskiste with serial {serial}")

    def test_create_invalid_device_type(self, admin_headers):
        """Should reject invalid device type"""
        payload = {
            "device_type": "invalid_type",
            "serial_number": f"TEST-INV-{uuid.uuid4().hex[:6]}"
        }
        response = requests.post(f"{BASE_URL}/api/devices", headers=admin_headers, json=payload)
        assert response.status_code == 400
        print("PASS: Invalid device type correctly rejected")

    def test_create_duplicate_serial_number(self, admin_headers):
        """Should reject duplicate serial number"""
        serial = f"TEST-DUP-{uuid.uuid4().hex[:6].upper()}"
        payload = {
            "device_type": "stromerzeuger",
            "serial_number": serial,
            "user_field": "First device"
        }
        
        # Create first device
        response1 = requests.post(f"{BASE_URL}/api/devices", headers=admin_headers, json=payload)
        assert response1.status_code == 200
        
        # Try to create duplicate
        payload["user_field"] = "Duplicate device"
        response2 = requests.post(f"{BASE_URL}/api/devices", headers=admin_headers, json=payload)
        assert response2.status_code == 400
        assert "Seriennummer" in response2.json().get("detail", "")
        print("PASS: Duplicate serial number correctly rejected")

    def test_kunde_cannot_create_device(self, kunde_headers):
        """Non-admin users should NOT be able to create devices"""
        payload = {
            "device_type": "stromerzeuger",
            "serial_number": f"TEST-UNAUTH-{uuid.uuid4().hex[:6]}"
        }
        response = requests.post(f"{BASE_URL}/api/devices", headers=kunde_headers, json=payload)
        assert response.status_code == 403
        print("PASS: Kunde correctly blocked from creating device")


class TestDeviceUpdate:
    """Test PUT /api/devices/{id} - Update device"""
    
    def test_update_device(self, admin_headers):
        """Admin should be able to update a device"""
        # First create a device
        serial = f"TEST-UPD-{uuid.uuid4().hex[:6].upper()}"
        create_payload = {
            "device_type": "stromerzeuger",
            "serial_number": serial,
            "user_field": "Original user field"
        }
        create_resp = requests.post(f"{BASE_URL}/api/devices", headers=admin_headers, json=create_payload)
        assert create_resp.status_code == 200
        device_id = create_resp.json()["id"]
        
        # Update the device
        update_payload = {
            "user_field": "Updated user field",
            "model": "QAS 300",
            "power_output": "300 kVA"
        }
        update_resp = requests.put(f"{BASE_URL}/api/devices/{device_id}", headers=admin_headers, json=update_payload)
        assert update_resp.status_code == 200
        
        updated = update_resp.json()
        assert updated["user_field"] == "Updated user field"
        assert updated["model"] == "QAS 300"
        assert updated["power_output"] == "300 kVA"
        assert updated["serial_number"] == serial  # Should not change
        
        # Verify with GET
        get_resp = requests.get(f"{BASE_URL}/api/devices/{device_id}", headers=admin_headers)
        assert get_resp.status_code == 200
        verified = get_resp.json()
        assert verified["user_field"] == "Updated user field"
        print(f"PASS: Device {serial} updated and verified")

    def test_update_nonexistent_device(self, admin_headers):
        """Should return 404 for non-existent device"""
        fake_id = str(uuid.uuid4())
        update_payload = {"user_field": "Test"}
        response = requests.put(f"{BASE_URL}/api/devices/{fake_id}", headers=admin_headers, json=update_payload)
        assert response.status_code == 404
        print("PASS: Non-existent device update returns 404")


class TestDeviceCopy:
    """Test POST /api/devices/{id}/copy - Copy device"""
    
    def test_copy_device(self, admin_headers):
        """Copy should create duplicate with KOPIE- prefix and clear specific fields"""
        # First create a device to copy
        serial = f"TEST-COPY-{uuid.uuid4().hex[:6].upper()}"
        create_payload = {
            "device_type": "stromerzeuger",
            "serial_number": serial,
            "user_field": "Device to copy",
            "model": "QAS 150",
            "engine_number": "ENG-12345",
            "generator_number": "GEN-67890"
        }
        create_resp = requests.post(f"{BASE_URL}/api/devices", headers=admin_headers, json=create_payload)
        assert create_resp.status_code == 200
        source_id = create_resp.json()["id"]
        
        # Copy the device
        copy_resp = requests.post(f"{BASE_URL}/api/devices/{source_id}/copy", headers=admin_headers)
        assert copy_resp.status_code == 200
        
        copied = copy_resp.json()
        # Check KOPIE- prefix added to serial
        assert copied["serial_number"] == f"KOPIE-{serial}"
        # Check fields cleared
        assert copied["engine_number"] == ""
        assert copied["generator_number"] == ""
        # Check other fields preserved
        assert copied["device_type"] == "stromerzeuger"
        assert copied["model"] == "QAS 150"
        assert copied["user_field"] == "Device to copy"
        # New ID should be different
        assert copied["id"] != source_id
        print(f"PASS: Device copied with serial KOPIE-{serial}, engine/generator numbers cleared")

    def test_copy_nonexistent_device(self, admin_headers):
        """Should return 404 when copying non-existent device"""
        fake_id = str(uuid.uuid4())
        response = requests.post(f"{BASE_URL}/api/devices/{fake_id}/copy", headers=admin_headers)
        assert response.status_code == 404
        print("PASS: Copy non-existent device returns 404")


class TestDeviceDelete:
    """Test DELETE /api/devices/{id} - Delete device"""
    
    def test_delete_device(self, admin_headers):
        """Admin should be able to delete a device"""
        # First create a device
        serial = f"TEST-DEL-{uuid.uuid4().hex[:6].upper()}"
        create_payload = {
            "device_type": "stromerzeuger",
            "serial_number": serial
        }
        create_resp = requests.post(f"{BASE_URL}/api/devices", headers=admin_headers, json=create_payload)
        assert create_resp.status_code == 200
        device_id = create_resp.json()["id"]
        
        # Delete the device
        delete_resp = requests.delete(f"{BASE_URL}/api/devices/{device_id}", headers=admin_headers)
        assert delete_resp.status_code == 200
        
        # Verify deleted - should return 404
        get_resp = requests.get(f"{BASE_URL}/api/devices/{device_id}", headers=admin_headers)
        assert get_resp.status_code == 404
        print(f"PASS: Device {serial} deleted and verified gone")

    def test_delete_nonexistent_device(self, admin_headers):
        """Should return 404 for non-existent device"""
        fake_id = str(uuid.uuid4())
        response = requests.delete(f"{BASE_URL}/api/devices/{fake_id}", headers=admin_headers)
        assert response.status_code == 404
        print("PASS: Delete non-existent device returns 404")


class TestDeviceDocuments:
    """Test document upload/list/delete for devices"""
    
    def test_upload_and_list_documents(self, admin_token):
        """Admin should be able to upload and list documents for a device"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First create a device
        serial = f"TEST-DOC-{uuid.uuid4().hex[:6].upper()}"
        create_payload = {
            "device_type": "stromerzeuger",
            "serial_number": serial
        }
        create_resp = requests.post(f"{BASE_URL}/api/devices", headers={**headers, "Content-Type": "application/json"}, json=create_payload)
        assert create_resp.status_code == 200
        device_id = create_resp.json()["id"]
        
        # Upload a test document
        files = {"file": ("test_document.txt", b"Test file content for device", "text/plain")}
        upload_resp = requests.post(f"{BASE_URL}/api/devices/{device_id}/documents", headers=headers, files=files)
        assert upload_resp.status_code == 200
        doc = upload_resp.json()
        assert doc["filename"] == "test_document.txt"
        assert "id" in doc
        assert "gridfs_id" in doc
        doc_id = doc["id"]
        print(f"PASS: Uploaded document {doc['filename']} to device")
        
        # List documents
        list_resp = requests.get(f"{BASE_URL}/api/devices/{device_id}/documents", headers=headers)
        assert list_resp.status_code == 200
        docs = list_resp.json()
        assert len(docs) >= 1
        assert any(d["filename"] == "test_document.txt" for d in docs)
        print(f"PASS: Listed {len(docs)} documents for device")
        
        # Verify device detail includes document_count
        detail_resp = requests.get(f"{BASE_URL}/api/devices/{device_id}", headers={**headers, "Content-Type": "application/json"})
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert "documents" in detail
        assert len(detail["documents"]) >= 1
        
        # Delete document
        delete_resp = requests.delete(f"{BASE_URL}/api/devices/{device_id}/documents/{doc_id}", headers=headers)
        assert delete_resp.status_code == 200
        print("PASS: Document deleted successfully")
        
        # Verify document gone
        list_after_resp = requests.get(f"{BASE_URL}/api/devices/{device_id}/documents", headers=headers)
        docs_after = list_after_resp.json()
        assert not any(d["id"] == doc_id for d in docs_after)
        print("PASS: Document deletion verified")


class TestDeviceStats:
    """Test GET /api/devices/stats/overview"""
    
    def test_device_stats(self, admin_headers):
        """Admin should be able to get device stats"""
        response = requests.get(f"{BASE_URL}/api/devices/stats/overview", headers=admin_headers)
        assert response.status_code == 200
        stats = response.json()
        assert "total" in stats
        assert "by_type" in stats
        assert "stromerzeuger" in stats["by_type"]
        assert "lichtmast" in stats["by_type"]
        assert "messkoffer" in stats["by_type"]
        assert "kirmeskiste" in stats["by_type"]
        print(f"PASS: Device stats retrieved - Total: {stats['total']}, By type: {stats['by_type']}")


class TestCleanupTestDevices:
    """Cleanup test-created devices"""
    
    def test_cleanup(self, admin_headers):
        """Delete all TEST- prefixed devices created during tests"""
        response = requests.get(f"{BASE_URL}/api/devices", headers=admin_headers)
        if response.status_code != 200:
            pytest.skip("Cannot list devices for cleanup")
        
        devices = response.json()
        deleted_count = 0
        for device in devices:
            if device["serial_number"].startswith("TEST-") or device["serial_number"].startswith("KOPIE-TEST-"):
                del_resp = requests.delete(f"{BASE_URL}/api/devices/{device['id']}", headers=admin_headers)
                if del_resp.status_code == 200:
                    deleted_count += 1
        
        print(f"PASS: Cleaned up {deleted_count} test devices")
