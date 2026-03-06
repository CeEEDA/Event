"""
Iteration 19 - Backend Tests for QR Code System and Device Copy Enhancements

Tests for:
1. GET /api/serviceplan/{planId} - entries sorted by performed_at descending (newest first)
2. POST /api/devices/{id}/copy - copies image_gridfs_id, device_code, and parts
3. GET /api/devices - lists all devices with device_code field
4. GET /api/devices/{id}/qrcode - returns PNG image
5. GET /api/devices/search/by-code/{CODE} - finds device by code
6. POST /api/devices with copy_from_device_id - copies image, parts, docs from source
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def api_session():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def auth_token(api_session):
    """Get authentication token for admin user"""
    response = api_session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "password"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


# ============== Device Code Tests ==============

class TestDeviceCodeGeneration:
    """Tests for device_code field in devices"""

    def test_list_devices_returns_device_code(self, api_session, auth_headers):
        """GET /api/devices returns device_code for each device"""
        response = api_session.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        devices = response.json()
        assert isinstance(devices, list), "Response should be a list"
        if len(devices) > 0:
            device = devices[0]
            assert "device_code" in device, "Device should have device_code field"
            assert device["device_code"] is not None, "device_code should not be None"
            assert len(device["device_code"]) == 8, f"device_code should be 8 chars, got {len(device['device_code'])}"
            # Check format: uppercase alphanumeric
            assert device["device_code"].isalnum(), "device_code should be alphanumeric"
            assert device["device_code"].isupper(), "device_code should be uppercase"
        print(f"PASS: GET /api/devices returns {len(devices)} devices with device_code field")

    def test_all_devices_have_device_code(self, api_session, auth_headers):
        """All devices should have unique device_code"""
        response = api_session.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert response.status_code == 200
        devices = response.json()
        codes = set()
        for d in devices:
            code = d.get("device_code")
            assert code is not None, f"Device {d['serial_number']} missing device_code"
            assert code not in codes, f"Duplicate device_code: {code}"
            codes.add(code)
        print(f"PASS: All {len(devices)} devices have unique device_codes")


# ============== QR Code Endpoint Tests ==============

class TestQRCodeEndpoint:
    """Tests for GET /api/devices/{id}/qrcode endpoint"""

    def test_qrcode_endpoint_returns_png(self, api_session, auth_headers):
        """GET /api/devices/{id}/qrcode returns PNG image"""
        # First get a device ID
        devices_resp = api_session.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert devices_resp.status_code == 200
        devices = devices_resp.json()
        if len(devices) == 0:
            pytest.skip("No devices available for QR code test")
        
        device_id = devices[0]["id"]
        response = api_session.get(f"{BASE_URL}/api/devices/{device_id}/qrcode")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("content-type") == "image/png", \
            f"Expected image/png, got {response.headers.get('content-type')}"
        assert len(response.content) > 100, "PNG should have substantial content"
        # Check PNG magic bytes
        assert response.content[:8] == b'\x89PNG\r\n\x1a\n', "Response should be valid PNG"
        print(f"PASS: GET /api/devices/{device_id}/qrcode returns PNG image ({len(response.content)} bytes)")

    def test_qrcode_endpoint_returns_404_for_invalid_device(self, api_session):
        """GET /api/devices/{invalid_id}/qrcode returns 404"""
        response = api_session.get(f"{BASE_URL}/api/devices/invalid-uuid/qrcode")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: GET /api/devices/invalid-uuid/qrcode returns 404")


# ============== Search by Code Tests ==============

class TestSearchByCode:
    """Tests for GET /api/devices/search/by-code/{code} endpoint"""

    def test_search_by_code_finds_device(self, api_session, auth_headers):
        """GET /api/devices/search/by-code/{code} finds device"""
        # Get a device with its code
        devices_resp = api_session.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert devices_resp.status_code == 200
        devices = devices_resp.json()
        if len(devices) == 0:
            pytest.skip("No devices available")
        
        device = devices[0]
        device_code = device.get("device_code")
        assert device_code, "Device must have device_code"
        
        response = api_session.get(f"{BASE_URL}/api/devices/search/by-code/{device_code}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        found_device = response.json()
        assert found_device["id"] == device["id"], "Should find the same device"
        assert found_device["device_code"] == device_code, "device_code should match"
        print(f"PASS: Search by code {device_code} found device {found_device['serial_number']}")

    def test_search_by_code_case_insensitive(self, api_session, auth_headers):
        """Search by code should be case-insensitive"""
        devices_resp = api_session.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        devices = devices_resp.json()
        if len(devices) == 0:
            pytest.skip("No devices available")
        
        device_code = devices[0].get("device_code")
        # Search with lowercase
        response = api_session.get(f"{BASE_URL}/api/devices/search/by-code/{device_code.lower()}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"PASS: Search by code is case-insensitive (searched with {device_code.lower()})")

    def test_search_by_code_returns_404_for_invalid(self, api_session, auth_headers):
        """Search by invalid code returns 404"""
        response = api_session.get(f"{BASE_URL}/api/devices/search/by-code/INVALID1", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Search by invalid code returns 404")


# ============== Device Copy Tests ==============

class TestDeviceCopy:
    """Tests for POST /api/devices/{id}/copy endpoint"""

    def test_copy_device_generates_new_device_code(self, api_session, auth_headers):
        """POST /api/devices/{id}/copy generates a new unique device_code"""
        # Get a device to copy
        devices_resp = api_session.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert devices_resp.status_code == 200
        devices = devices_resp.json()
        if len(devices) == 0:
            pytest.skip("No devices available")
        
        source_device = devices[0]
        source_code = source_device.get("device_code")
        
        # Copy the device
        response = api_session.post(f"{BASE_URL}/api/devices/{source_device['id']}/copy", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        copied_device = response.json()
        assert "device_code" in copied_device, "Copied device should have device_code"
        assert copied_device["device_code"] != source_code, \
            f"Copied device should have different device_code (both have {copied_device['device_code']})"
        assert len(copied_device["device_code"]) == 8, "device_code should be 8 chars"
        
        # Clean up - delete the copied device
        api_session.delete(f"{BASE_URL}/api/devices/{copied_device['id']}", headers=auth_headers)
        
        print(f"PASS: Copy device generates new device_code: {source_code} -> {copied_device['device_code']}")

    def test_copy_device_copies_image_gridfs_id(self, api_session, auth_headers):
        """POST /api/devices/{id}/copy copies image_gridfs_id from source"""
        # Find a device with an image
        devices_resp = api_session.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        devices = devices_resp.json()
        device_with_image = next((d for d in devices if d.get("image_gridfs_id")), None)
        
        if not device_with_image:
            pytest.skip("No device with image available")
        
        source_image_id = device_with_image.get("image_gridfs_id")
        
        # Copy the device
        response = api_session.post(f"{BASE_URL}/api/devices/{device_with_image['id']}/copy", headers=auth_headers)
        assert response.status_code == 200
        
        copied_device = response.json()
        assert copied_device.get("image_gridfs_id") == source_image_id, \
            f"Copied device should have same image_gridfs_id: {copied_device.get('image_gridfs_id')} != {source_image_id}"
        
        # Clean up
        api_session.delete(f"{BASE_URL}/api/devices/{copied_device['id']}", headers=auth_headers)
        
        print(f"PASS: Copy device copies image_gridfs_id: {source_image_id}")

    def test_copy_device_copies_parts(self, api_session, auth_headers):
        """POST /api/devices/{id}/copy copies parts to new device"""
        # Find a device with parts
        devices_resp = api_session.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        devices = devices_resp.json()
        
        device_with_parts = None
        source_parts = []
        for d in devices:
            parts_resp = api_session.get(f"{BASE_URL}/api/devices/{d['id']}/parts", headers=auth_headers)
            if parts_resp.status_code == 200:
                parts = parts_resp.json()
                if len(parts) > 0:
                    device_with_parts = d
                    source_parts = parts
                    break
        
        if not device_with_parts:
            pytest.skip("No device with parts available")
        
        # Copy the device
        response = api_session.post(f"{BASE_URL}/api/devices/{device_with_parts['id']}/copy", headers=auth_headers)
        assert response.status_code == 200
        copied_device = response.json()
        
        # Check copied device has parts
        copied_parts_resp = api_session.get(f"{BASE_URL}/api/devices/{copied_device['id']}/parts", headers=auth_headers)
        assert copied_parts_resp.status_code == 200
        copied_parts = copied_parts_resp.json()
        
        assert len(copied_parts) == len(source_parts), \
            f"Copied device should have same number of parts: {len(copied_parts)} != {len(source_parts)}"
        
        # Verify part types match
        source_types = set(p["part_type"] for p in source_parts)
        copied_types = set(p["part_type"] for p in copied_parts)
        assert source_types == copied_types, f"Part types should match: {source_types} != {copied_types}"
        
        # Clean up
        api_session.delete(f"{BASE_URL}/api/devices/{copied_device['id']}", headers=auth_headers)
        
        print(f"PASS: Copy device copies {len(source_parts)} parts")


# ============== Create Device with copy_from_device_id Tests ==============

class TestCreateDeviceWithCopyFrom:
    """Tests for POST /api/devices with copy_from_device_id"""

    def test_create_device_with_copy_from_copies_image(self, api_session, auth_headers):
        """POST /api/devices with copy_from_device_id copies image"""
        # Find source device with image
        devices_resp = api_session.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        devices = devices_resp.json()
        device_with_image = next((d for d in devices if d.get("image_gridfs_id")), None)
        
        if not device_with_image:
            pytest.skip("No device with image available")
        
        # Create new device with copy_from_device_id
        unique_serial = f"TEST_COPY_{datetime.now().strftime('%H%M%S')}"
        response = api_session.post(f"{BASE_URL}/api/devices", headers=auth_headers, json={
            "device_type": "stromerzeuger",
            "serial_number": unique_serial,
            "copy_from_device_id": device_with_image["id"]
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        new_device = response.json()
        
        # Verify image was copied
        device_detail = api_session.get(f"{BASE_URL}/api/devices/{new_device['id']}", headers=auth_headers).json()
        assert device_detail.get("image_gridfs_id") == device_with_image.get("image_gridfs_id"), \
            "Image should be copied from source device"
        
        # Clean up
        api_session.delete(f"{BASE_URL}/api/devices/{new_device['id']}", headers=auth_headers)
        
        print(f"PASS: Create device with copy_from_device_id copies image")

    def test_create_device_with_copy_from_copies_parts(self, api_session, auth_headers):
        """POST /api/devices with copy_from_device_id copies parts"""
        # Find source device with parts
        devices_resp = api_session.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        devices = devices_resp.json()
        
        device_with_parts = None
        source_parts = []
        for d in devices:
            parts_resp = api_session.get(f"{BASE_URL}/api/devices/{d['id']}/parts", headers=auth_headers)
            if parts_resp.status_code == 200:
                parts = parts_resp.json()
                if len(parts) > 0:
                    device_with_parts = d
                    source_parts = parts
                    break
        
        if not device_with_parts:
            pytest.skip("No device with parts available")
        
        # Create new device with copy_from_device_id
        unique_serial = f"TEST_PARTS_{datetime.now().strftime('%H%M%S')}"
        response = api_session.post(f"{BASE_URL}/api/devices", headers=auth_headers, json={
            "device_type": "stromerzeuger",
            "serial_number": unique_serial,
            "copy_from_device_id": device_with_parts["id"]
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        new_device = response.json()
        
        # Verify parts were copied
        new_parts_resp = api_session.get(f"{BASE_URL}/api/devices/{new_device['id']}/parts", headers=auth_headers)
        new_parts = new_parts_resp.json()
        
        assert len(new_parts) == len(source_parts), \
            f"Parts should be copied: {len(new_parts)} != {len(source_parts)}"
        
        # Clean up
        api_session.delete(f"{BASE_URL}/api/devices/{new_device['id']}", headers=auth_headers)
        
        print(f"PASS: Create device with copy_from_device_id copies {len(source_parts)} parts")

    def test_create_device_with_copy_from_copies_documents(self, api_session, auth_headers):
        """POST /api/devices with copy_from_device_id copies documents"""
        # Find source device with documents
        devices_resp = api_session.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        devices = devices_resp.json()
        
        device_with_docs = None
        source_docs = []
        for d in devices:
            docs_resp = api_session.get(f"{BASE_URL}/api/devices/{d['id']}/documents", headers=auth_headers)
            if docs_resp.status_code == 200:
                docs = docs_resp.json()
                if len(docs) > 0:
                    device_with_docs = d
                    source_docs = docs
                    break
        
        if not device_with_docs:
            pytest.skip("No device with documents available")
        
        # Create new device with copy_from_device_id
        unique_serial = f"TEST_DOCS_{datetime.now().strftime('%H%M%S')}"
        response = api_session.post(f"{BASE_URL}/api/devices", headers=auth_headers, json={
            "device_type": "stromerzeuger",
            "serial_number": unique_serial,
            "copy_from_device_id": device_with_docs["id"]
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        new_device = response.json()
        
        # Verify documents were copied
        new_docs_resp = api_session.get(f"{BASE_URL}/api/devices/{new_device['id']}/documents", headers=auth_headers)
        new_docs = new_docs_resp.json()
        
        assert len(new_docs) == len(source_docs), \
            f"Documents should be copied: {len(new_docs)} != {len(source_docs)}"
        
        # Clean up
        api_session.delete(f"{BASE_URL}/api/devices/{new_device['id']}", headers=auth_headers)
        
        print(f"PASS: Create device with copy_from_device_id copies {len(source_docs)} documents")


# ============== Service Plan Entry Sorting Tests ==============

class TestServicePlanEntrySorting:
    """Tests for GET /api/serviceplan/{planId} entry sorting"""

    def test_serviceplan_entries_sorted_newest_first(self, api_session, auth_headers):
        """GET /api/serviceplan/{planId} returns entries sorted by performed_at descending"""
        # Get service plans
        plans_resp = api_session.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers)
        assert plans_resp.status_code == 200
        plans = plans_resp.json()
        
        # Find a plan with multiple entries
        plan_with_entries = None
        for p in plans:
            if p.get("entry_count", 0) >= 2:
                plan_with_entries = p
                break
        
        if not plan_with_entries:
            # Try to find any plan with entries
            for p in plans:
                plan_detail_resp = api_session.get(f"{BASE_URL}/api/serviceplan/{p['id']}", headers=auth_headers)
                if plan_detail_resp.status_code == 200:
                    detail = plan_detail_resp.json()
                    if len(detail.get("entries", [])) >= 2:
                        plan_with_entries = p
                        break
        
        if not plan_with_entries:
            pytest.skip("No service plan with multiple entries available")
        
        # Get plan detail
        plan_detail_resp = api_session.get(f"{BASE_URL}/api/serviceplan/{plan_with_entries['id']}", headers=auth_headers)
        assert plan_detail_resp.status_code == 200
        plan_detail = plan_detail_resp.json()
        entries = plan_detail.get("entries", [])
        
        if len(entries) < 2:
            pytest.skip("Plan doesn't have enough entries to test sorting")
        
        # Verify entries are sorted by performed_at descending
        dates = [e.get("performed_at") for e in entries]
        sorted_dates = sorted(dates, reverse=True)
        assert dates == sorted_dates, f"Entries should be sorted newest first: {dates} != {sorted_dates}"
        
        print(f"PASS: Service plan entries sorted newest first: {dates[:3]}...")

    def test_serviceplan_entries_order_consistent(self, api_session, auth_headers):
        """Service plan entries maintain consistent order on multiple requests"""
        plans_resp = api_session.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers)
        plans = plans_resp.json()
        
        plan_with_entries = next((p for p in plans if p.get("entry_count", 0) > 0), None)
        if not plan_with_entries:
            pytest.skip("No service plan with entries available")
        
        # Make two requests and verify same order
        resp1 = api_session.get(f"{BASE_URL}/api/serviceplan/{plan_with_entries['id']}", headers=auth_headers)
        resp2 = api_session.get(f"{BASE_URL}/api/serviceplan/{plan_with_entries['id']}", headers=auth_headers)
        
        entries1 = resp1.json().get("entries", [])
        entries2 = resp2.json().get("entries", [])
        
        ids1 = [e["id"] for e in entries1]
        ids2 = [e["id"] for e in entries2]
        
        assert ids1 == ids2, "Entry order should be consistent across requests"
        print(f"PASS: Service plan entries order consistent across requests ({len(ids1)} entries)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
