"""
Iteration 18 Tests - DSE Power Generator Portal
Features to test:
1. POST /api/devices/{id}/copy - returns image_gridfs_id as string (not ObjectId)
2. GET /api/devices/{id}/documents/{docId}/download - returns file content with 200
3. Service Plan filter cards functionality (Einsatzbereit, Bald fällig, Überfällig, Gesamt)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://pi-energy-hub.preview.emergentagent.com"

TEST_DEVICE_ID = "f268c2e1-3933-43b4-85d8-0595338a8287"  # DSE-HBF-001 with image + parts + document
TEST_DOCUMENT_ID = "a8f22141-b221-4974-b222-5d4a8b537b22"  # test_doc.txt


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "password"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]


class TestCopyDeviceImageGridfsId:
    """Test that copy_device returns image_gridfs_id as string"""

    def test_copy_device_returns_200(self, admin_token):
        """POST /api/devices/{id}/copy should return 200"""
        response = requests.post(
            f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/copy",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["serial_number"].startswith("KOPIE-")
        # Store for cleanup
        TestCopyDeviceImageGridfsId.copied_device_id = data["id"]

    def test_copy_device_image_gridfs_id_is_string(self, admin_token):
        """Copied device should have image_gridfs_id as string (not ObjectId)"""
        response = requests.post(
            f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/copy",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        # Key assertion: image_gridfs_id must be a string
        assert "image_gridfs_id" in data, "Response should include image_gridfs_id"
        assert isinstance(data["image_gridfs_id"], str), f"image_gridfs_id should be string, got {type(data['image_gridfs_id'])}"
        assert len(data["image_gridfs_id"]) > 0, "image_gridfs_id should not be empty"
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/devices/{data['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    def test_copy_device_copies_image_reference(self, admin_token):
        """Copied device should have same image_gridfs_id as source"""
        # Get source device
        source_response = requests.get(
            f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        source_data = source_response.json()
        source_image_id = source_data.get("image_gridfs_id")
        
        # Copy device
        copy_response = requests.post(
            f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/copy",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        copy_data = copy_response.json()
        
        # Assert same image reference
        assert copy_data.get("image_gridfs_id") == source_image_id, "Copied device should have same image_gridfs_id"
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/devices/{copy_data['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )


class TestDocumentDownloadAuth:
    """Test document download endpoint requires authentication"""

    def test_download_document_with_auth_returns_200(self, admin_token):
        """GET /api/devices/{id}/documents/{docId}/download with auth returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/documents/{TEST_DOCUMENT_ID}/download",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert len(response.content) > 0, "Response should have content"

    def test_download_document_without_auth_returns_403(self):
        """GET /api/devices/{id}/documents/{docId}/download without auth returns 403"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/documents/{TEST_DOCUMENT_ID}/download",
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"

    def test_download_document_returns_correct_content_type(self, admin_token):
        """Document download should return appropriate content type"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/documents/{TEST_DOCUMENT_ID}/download",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        # test_doc.txt should be text/plain
        content_type = response.headers.get("content-type", "")
        assert "text/plain" in content_type, f"Expected text/plain, got {content_type}"


class TestServicePlanEndpoints:
    """Test service plan endpoints for filter functionality"""

    def test_list_serviceplans_returns_200(self, admin_token):
        """GET /api/serviceplan should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/serviceplan",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_serviceplan_has_required_fields(self, admin_token):
        """Service plans should have fields needed for filtering"""
        response = requests.get(
            f"{BASE_URL}/api/serviceplan",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = response.json()
        if len(data) > 0:
            plan = data[0]
            required_fields = ["id", "device_id", "interval_hours", "interval_months"]
            for field in required_fields:
                assert field in plan, f"Service plan missing field: {field}"


class TestDevicePartsEndpoint:
    """Test device parts endpoint"""

    def test_get_device_parts(self, admin_token):
        """GET /api/devices/{id}/parts returns parts for device"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/parts",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            part = data[0]
            assert "part_type" in part
            assert "id" in part


class TestDeviceImageEndpoint:
    """Test device image endpoint (no auth required)"""

    def test_device_image_endpoint_no_auth(self):
        """GET /api/devices/{id}/image should work without auth"""
        response = requests.get(
            f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/image",
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        content_type = response.headers.get("content-type", "")
        assert "image" in content_type, f"Expected image content type, got {content_type}"
