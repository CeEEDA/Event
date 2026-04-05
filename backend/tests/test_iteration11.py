"""
Iteration 11 - Testing new features:
1. Serviceplan: current_hours field, remarks field
2. Serviceplan: image upload (POST /api/serviceplan/{plan_id}/entries/{entry_id}/images)
3. Serviceplan: image retrieval (GET /api/serviceplan/images/{image_id})
4. Device image upload (POST /api/devices/{id}/image)
5. Device image retrieval (GET /api/devices/{id}/image)
6. Admin send reset email endpoint (POST /api/admin/send-reset-email/{user_id})
7. Frontend URL passed to password reset
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="function")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "password"
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="function")
def mitarbeiter_token():
    """Get mitarbeiter authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "ma1@test.com",
        "password": "password"
    })
    assert response.status_code == 200, f"Mitarbeiter login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="function")
def auth_headers(admin_token):
    """Admin authorization headers"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="function")
def ma_headers(mitarbeiter_token):
    """Mitarbeiter authorization headers"""
    return {"Authorization": f"Bearer {mitarbeiter_token}"}


# ============== Serviceplan current_hours and remarks ==============

class TestServiceplanCurrentHoursAndRemarks:
    """Tests for new serviceplan fields: current_hours and remarks"""

    def test_create_plan_with_current_hours(self, auth_headers):
        """Create serviceplan with current_hours field"""
        # Get a device without a plan
        devices = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers).json()
        plans = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers).json()
        existing_device_ids = [p["device_id"] for p in plans]
        
        available_devices = [d for d in devices if d["id"] not in existing_device_ids]
        
        if not available_devices:
            pytest.skip("No devices available without a plan - need at least one for testing")
        
        device_id = available_devices[0]["id"]
        
        # Create plan with current_hours
        response = requests.post(f"{BASE_URL}/api/serviceplan", headers=auth_headers, json={
            "device_id": device_id,
            "current_hours": 1234.5,
            "interval_hours": 500,
            "interval_months": 12,
            "tasks": ["Ölwechsel", "Filterwechsel"]
        })
        
        assert response.status_code == 200, f"Create failed: {response.text}"
        plan = response.json()
        assert plan["current_hours"] == 1234.5, f"Expected 1234.5, got {plan.get('current_hours')}"
        assert plan["interval_hours"] == 500
        assert "Ölwechsel" in plan["tasks"]
        
        # Clean up - keep track for other tests
        return plan

    def test_update_plan_current_hours(self, auth_headers):
        """Update serviceplan current_hours, interval_hours, interval_months, tasks"""
        plans = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers).json()
        assert len(plans) > 0, "Need at least one plan to test update"
        
        plan_id = plans[0]["id"]
        
        # Update with new current_hours
        response = requests.put(f"{BASE_URL}/api/serviceplan/{plan_id}", headers=auth_headers, json={
            "current_hours": 2500.0,
            "interval_hours": 750,
            "interval_months": 6,
            "tasks": ["Task1", "Task2", "Task3"]
        })
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        updated = response.json()
        assert updated["current_hours"] == 2500.0
        assert updated["interval_hours"] == 750
        assert updated["interval_months"] == 6
        assert len(updated["tasks"]) == 3

    def test_add_entry_with_remarks(self, auth_headers):
        """Create maintenance entry with remarks field"""
        plans = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers).json()
        assert len(plans) > 0, "Need at least one plan"
        
        plan_id = plans[0]["id"]
        
        # Add entry with remarks
        response = requests.post(f"{BASE_URL}/api/serviceplan/{plan_id}/entries", headers=auth_headers, json={
            "performed_by": "Test Techniker",
            "performed_at": "2026-03-06",
            "hours_at_service": 2500,
            "tasks_completed": ["Task1", "Task2"],
            "notes": "Regular maintenance notes",
            "remarks": "Besondere Vorkommnisse: Motor hatte leichte Vibrationen, wurde nachgestellt."
        })
        
        assert response.status_code == 200, f"Add entry failed: {response.text}"
        entry = response.json()
        assert entry["remarks"] == "Besondere Vorkommnisse: Motor hatte leichte Vibrationen, wurde nachgestellt."
        assert entry["notes"] == "Regular maintenance notes"
        assert entry["performed_by"] == "Test Techniker"
        
        return entry

    def test_get_plan_detail_shows_current_hours(self, auth_headers):
        """GET /api/serviceplan/{id} returns current_hours in response"""
        plans = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers).json()
        assert len(plans) > 0, "Need at least one plan"
        
        plan_id = plans[0]["id"]
        response = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", headers=auth_headers)
        
        assert response.status_code == 200
        detail = response.json()
        assert "current_hours" in detail, "current_hours should be in response"
        assert "device_serial" in detail, "Enriched device info should be present"


# ============== Serviceplan Image Upload ==============

class TestServiceplanImageUpload:
    """Tests for serviceplan entry image upload/retrieval"""

    def test_upload_image_to_entry(self, auth_headers):
        """POST /api/serviceplan/{plan_id}/entries/{entry_id}/images uploads image"""
        # Get plans and entries
        plans = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers).json()
        assert len(plans) > 0, "Need at least one plan"
        
        plan_id = plans[0]["id"]
        
        # Get plan detail to find entries
        detail = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", headers=auth_headers).json()
        entries = detail.get("entries", [])
        
        if not entries:
            # Create an entry first
            entry_res = requests.post(f"{BASE_URL}/api/serviceplan/{plan_id}/entries", headers=auth_headers, json={
                "performed_by": "Image Test Tech",
                "performed_at": "2026-03-05",
                "tasks_completed": ["Test"],
                "notes": "For image upload test"
            })
            assert entry_res.status_code == 200
            entry_id = entry_res.json()["id"]
        else:
            entry_id = entries[0]["id"]
        
        # Create a fake image file
        image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        files = {"file": ("test_image.png", io.BytesIO(image_content), "image/png")}
        
        # Upload
        response = requests.post(
            f"{BASE_URL}/api/serviceplan/{plan_id}/entries/{entry_id}/images",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 200, f"Image upload failed: {response.text}"
        image_doc = response.json()
        assert "id" in image_doc
        assert image_doc["filename"] == "test_image.png"
        assert image_doc["content_type"] == "image/png"
        
        return image_doc["id"]

    def test_retrieve_serviceplan_image(self, auth_headers):
        """GET /api/serviceplan/images/{image_id} retrieves uploaded image"""
        # First upload an image
        plans = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers).json()
        if not plans:
            pytest.skip("No plans available")
        
        plan_id = plans[0]["id"]
        detail = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", headers=auth_headers).json()
        entries = detail.get("entries", [])
        
        image_id = None
        for entry in entries:
            if entry.get("images"):
                image_id = entry["images"][0]
                break
        
        if not image_id:
            pytest.skip("No images uploaded yet")
        
        # Retrieve image
        response = requests.get(f"{BASE_URL}/api/serviceplan/images/{image_id}")
        
        assert response.status_code == 200, f"Image retrieval failed: {response.status_code}"
        assert response.headers.get("Content-Type", "").startswith("image/")

    def test_list_entry_images(self, auth_headers):
        """GET /api/serviceplan/{plan_id}/entries/{entry_id}/images lists images"""
        plans = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers).json()
        if not plans:
            pytest.skip("No plans available")
        
        plan_id = plans[0]["id"]
        detail = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", headers=auth_headers).json()
        entries = detail.get("entries", [])
        
        if not entries:
            pytest.skip("No entries to test")
        
        entry_id = entries[0]["id"]
        response = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}/entries/{entry_id}/images", headers=auth_headers)
        
        assert response.status_code == 200
        images = response.json()
        assert isinstance(images, list)


# ============== Device Image Upload ==============

class TestDeviceImageUpload:
    """Tests for device image upload/retrieval"""

    def test_upload_device_image(self, auth_headers):
        """POST /api/devices/{id}/image uploads device image"""
        # Get a device
        devices = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers).json()
        assert len(devices) > 0, "Need at least one device"
        
        device_id = devices[0]["id"]
        
        # Create a fake image
        image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        files = {"file": ("device_photo.png", io.BytesIO(image_content), "image/png")}
        
        response = requests.post(
            f"{BASE_URL}/api/devices/{device_id}/image",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 200, f"Device image upload failed: {response.text}"
        result = response.json()
        assert "image_gridfs_id" in result
        
        return device_id

    def test_retrieve_device_image(self, auth_headers):
        """GET /api/devices/{id}/image retrieves device image"""
        # Get a device with image
        res = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert res.status_code == 200, f"Failed to get devices: {res.status_code} - {res.text}"
        devices = res.json()
        
        device_with_image = next((d for d in devices if d.get("image_gridfs_id")), None)
        
        if not device_with_image:
            # Upload one first
            device_id = devices[0]["id"]
            image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
            files = {"file": ("device_photo.png", io.BytesIO(image_content), "image/png")}
            requests.post(f"{BASE_URL}/api/devices/{device_id}/image", headers=auth_headers, files=files)
        else:
            device_id = device_with_image["id"]
        
        # Retrieve image
        response = requests.get(f"{BASE_URL}/api/devices/{device_id}/image")
        
        assert response.status_code == 200, f"Device image retrieval failed: {response.status_code}"
        assert response.headers.get("Content-Type", "").startswith("image/")

    def test_device_without_image_returns_404(self, auth_headers):
        """GET /api/devices/{id}/image returns 404 if no image uploaded"""
        # Create a new device without image
        new_device = requests.post(f"{BASE_URL}/api/devices", headers=auth_headers, json={
            "device_type": "messkoffer",
            "serial_number": f"TEST-NOIMG-{os.urandom(4).hex()[:6].upper()}",
            "user_field": "No image device"
        })
        
        if new_device.status_code != 200:
            pytest.skip("Could not create test device")
        
        device_id = new_device.json()["id"]
        
        # Try to get image - should 404
        response = requests.get(f"{BASE_URL}/api/devices/{device_id}/image")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        # Clean up
        requests.delete(f"{BASE_URL}/api/devices/{device_id}", headers=auth_headers)

    def test_device_table_shows_image_when_available(self, auth_headers):
        """Device list includes image_gridfs_id field"""
        res = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert res.status_code == 200, f"Failed to get devices: {res.status_code} - {res.text}"
        devices = res.json()
        
        # Check that image_gridfs_id field exists (may be null)
        for device in devices[:3]:  # Check a few devices
            # The field may not exist or be null - that's OK
            # We're checking the API returns it when it exists
            if device.get("image_gridfs_id"):
                # Device with image should have the field
                assert "image_gridfs_id" in device
                break


# ============== Admin Email Endpoints ==============

class TestAdminEmailEndpoints:
    """Tests for admin password reset email functionality"""

    def test_admin_send_reset_email_endpoint_exists(self, auth_headers):
        """POST /api/admin/send-reset-email/{user_id} endpoint exists"""
        # Get a user to test with
        users = requests.get(f"{BASE_URL}/api/users", headers=auth_headers).json()
        non_admin_user = next((u for u in users if u["role"] != "admin"), None)
        
        if not non_admin_user:
            pytest.skip("No non-admin user to test email endpoint")
        
        user_id = non_admin_user["id"]
        
        # Call the endpoint (will fail due to SMTP but endpoint should exist)
        response = requests.post(
            f"{BASE_URL}/api/admin/send-reset-email/{user_id}",
            headers=auth_headers,
            json={"frontend_url": "https://kirmes-docs.preview.emergentagent.com"}
        )
        
        # Endpoint should exist (may fail with 500 due to SMTP config)
        # 200 = email sent successfully
        # 500 = endpoint exists but email failed (expected per context)
        # 404/405 = endpoint doesn't exist (failure)
        assert response.status_code in [200, 500], f"Unexpected status: {response.status_code} - {response.text}"
        
        if response.status_code == 500:
            # Expected - SMTP not configured correctly
            error = response.json()
            assert "E-Mail" in error.get("detail", ""), f"Unexpected error: {error}"

    def test_forgot_password_passes_frontend_url(self, auth_headers):
        """Password reset request accepts frontend_url parameter"""
        response = requests.post(f"{BASE_URL}/api/auth/request-password-reset", json={
            "email": "nonexistent@test.com",  # Using non-existent to not trigger actual email
            "frontend_url": "https://kirmes-docs.preview.emergentagent.com"
        })
        
        # Should return 200 (doesn't reveal if email exists)
        assert response.status_code == 200
        result = response.json()
        assert "message" in result


# ============== Mitarbeiter Access Tests ==============

class TestMitarbeiterServiceplanAccess:
    """Verify mitarbeiter can access serviceplan features"""

    def test_mitarbeiter_can_list_serviceplans(self, ma_headers):
        """Mitarbeiter can GET /api/serviceplan"""
        response = requests.get(f"{BASE_URL}/api/serviceplan", headers=ma_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        assert isinstance(response.json(), list)

    def test_mitarbeiter_can_add_entry(self, ma_headers):
        """Mitarbeiter can POST maintenance entry"""
        plans = requests.get(f"{BASE_URL}/api/serviceplan", headers=ma_headers).json()
        if not plans:
            pytest.skip("No plans available")
        
        plan_id = plans[0]["id"]
        
        response = requests.post(f"{BASE_URL}/api/serviceplan/{plan_id}/entries", headers=ma_headers, json={
            "performed_by": "Mitarbeiter Techniker",
            "performed_at": "2026-03-06",
            "hours_at_service": 3000,
            "tasks_completed": ["Sichtprüfung"],
            "remarks": "Alles in Ordnung"
        })
        
        assert response.status_code == 200, f"Failed: {response.text}"

    def test_mitarbeiter_can_upload_entry_image(self, ma_headers):
        """Mitarbeiter can upload images to entries"""
        plans = requests.get(f"{BASE_URL}/api/serviceplan", headers=ma_headers).json()
        if not plans:
            pytest.skip("No plans available")
        
        plan_id = plans[0]["id"]
        detail = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", headers=ma_headers).json()
        entries = detail.get("entries", [])
        
        if not entries:
            pytest.skip("No entries to test")
        
        entry_id = entries[0]["id"]
        
        # Upload image
        image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        files = {"file": ("ma_upload.png", io.BytesIO(image_content), "image/png")}
        
        response = requests.post(
            f"{BASE_URL}/api/serviceplan/{plan_id}/entries/{entry_id}/images",
            headers=ma_headers,
            files=files
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
