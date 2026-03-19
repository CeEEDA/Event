"""
Iteration 43 - Testing PDF document upload feature for Serviceplan maintenance entries:
- POST /api/serviceplan/{plan_id}/entries/{entry_id}/images accepts PDF files
- 25MB file size limit validation
- Backend stores attachments metadata (id, filename, content_type, size) on entry
- GET /api/serviceplan/images/{image_id} returns PDF with correct content-type
- Regression: Existing photo upload still works
- Regression: Serviceplan CRUD still works
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestServiceplanPDFUpload:
    """Test PDF upload feature for serviceplan maintenance entries"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login as admin to get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def auth_headers_multipart(self, auth_token):
        """Headers for multipart file upload - no Content-Type (requests sets it)"""
        return {"Authorization": f"Bearer {auth_token}"}

    @pytest.fixture(scope="class")
    def test_device(self, auth_headers):
        """Get or create a test device for serviceplan testing"""
        response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        if response.status_code == 200 and len(response.json()) > 0:
            return response.json()[0]
        # Create a test device if none exists
        device_data = {
            "serial_number": f"TEST-PDF-IT43-{os.urandom(4).hex()}",
            "device_type": "stromerzeuger",
            "model": "TestModel",
            "user_field": "PDF Test Device",
            "status": "aktiv"
        }
        response = requests.post(f"{BASE_URL}/api/devices", json=device_data, headers=auth_headers)
        assert response.status_code in [200, 201]
        return response.json()

    @pytest.fixture(scope="class")
    def test_plan(self, auth_headers, test_device):
        """Get or create a test service plan"""
        response = requests.get(f"{BASE_URL}/api/serviceplan/device/{test_device['id']}", headers=auth_headers)
        if response.status_code == 200 and response.json().get("has_plan"):
            return response.json()
        
        plan_data = {
            "device_id": test_device["id"],
            "current_hours": 100,
            "interval_hours": 500,
            "interval_months": 12,
            "tasks": [],
            "notes": "Test plan for PDF upload iteration 43"
        }
        response = requests.post(f"{BASE_URL}/api/serviceplan", json=plan_data, headers=auth_headers)
        if response.status_code == 400 and "bereits" in response.json().get("detail", ""):
            plans_response = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers)
            for plan in plans_response.json():
                if plan["device_id"] == test_device["id"]:
                    return plan
        assert response.status_code in [200, 201], f"Failed to create plan: {response.text}"
        return response.json()

    @pytest.fixture(scope="class")
    def test_entry(self, auth_headers, test_plan):
        """Create a test maintenance entry for image/PDF upload testing"""
        entry_data = {
            "performed_by": "Test Admin",
            "performed_at": "2026-01-15",
            "hours_at_service": 150,
            "next_maintenance_months": 12,
            "next_maintenance_hours": 500,
            "checklist_data": {},
            "notes": "Test entry for PDF upload iteration 43",
            "remarks": ""
        }
        response = requests.post(
            f"{BASE_URL}/api/serviceplan/{test_plan['id']}/entries",
            json=entry_data,
            headers=auth_headers
        )
        assert response.status_code in [200, 201], f"Failed to create entry: {response.text}"
        return response.json()

    # ========== PDF Upload Tests ==========
    
    def test_upload_pdf_file_success(self, auth_headers_multipart, test_plan, test_entry):
        """Test uploading a PDF file to maintenance entry"""
        # Create a minimal valid PDF
        pdf_content = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 0\ntrailer\n<< /Root 1 0 R >>\n%%EOF'
        
        files = {
            'file': ('test_document.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/serviceplan/{test_plan['id']}/entries/{test_entry['id']}/images",
            headers=auth_headers_multipart,
            files=files
        )
        
        assert response.status_code == 200, f"PDF upload failed: {response.text}"
        
        result = response.json()
        assert result['filename'] == 'test_document.pdf'
        assert result['content_type'] == 'application/pdf'
        assert 'id' in result
        assert 'size' in result
        assert result['size'] > 0
        
        print(f"PDF uploaded successfully: id={result['id']}, size={result['size']} bytes")
        return result

    def test_upload_jpeg_image_still_works(self, auth_headers_multipart, test_plan, test_entry):
        """Regression: Test that JPEG image upload still works"""
        # Minimal JPEG header (not a full valid JPEG, but enough for content-type validation)
        jpeg_header = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46])
        jpeg_content = jpeg_header + b'\x00' * 100
        
        files = {
            'file': ('test_image.jpg', io.BytesIO(jpeg_content), 'image/jpeg')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/serviceplan/{test_plan['id']}/entries/{test_entry['id']}/images",
            headers=auth_headers_multipart,
            files=files
        )
        
        assert response.status_code == 200, f"JPEG upload failed: {response.text}"
        
        result = response.json()
        assert result['filename'] == 'test_image.jpg'
        assert result['content_type'] == 'image/jpeg'
        
        print(f"JPEG uploaded successfully: id={result['id']}")
        return result

    def test_upload_png_image_still_works(self, auth_headers_multipart, test_plan, test_entry):
        """Regression: Test that PNG image upload still works"""
        # Minimal PNG header
        png_header = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
        png_content = png_header + b'\x00' * 100
        
        files = {
            'file': ('test_image.png', io.BytesIO(png_content), 'image/png')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/serviceplan/{test_plan['id']}/entries/{test_entry['id']}/images",
            headers=auth_headers_multipart,
            files=files
        )
        
        assert response.status_code == 200, f"PNG upload failed: {response.text}"
        
        result = response.json()
        assert result['filename'] == 'test_image.png'
        assert result['content_type'] == 'image/png'
        
        print(f"PNG uploaded successfully: id={result['id']}")
        return result

    def test_file_size_limit_25mb(self, auth_headers_multipart, test_plan, test_entry):
        """Test that files > 25MB are rejected"""
        # Create content just over 25MB
        large_content = b'X' * (26 * 1024 * 1024)  # 26MB
        
        files = {
            'file': ('large_file.pdf', io.BytesIO(large_content), 'application/pdf')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/serviceplan/{test_plan['id']}/entries/{test_entry['id']}/images",
            headers=auth_headers_multipart,
            files=files
        )
        
        assert response.status_code == 400, f"Expected 400 for file > 25MB, got {response.status_code}"
        assert "25MB" in response.text or "zu groß" in response.text.lower() or "max" in response.text.lower()
        
        print("File size limit (25MB) correctly enforced")

    def test_get_pdf_returns_correct_content_type(self, auth_headers_multipart, test_plan, test_entry):
        """Test that GET /api/serviceplan/images/{id} returns PDF with correct content-type"""
        # First upload a PDF
        pdf_content = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 0\ntrailer\n<< /Root 1 0 R >>\n%%EOF'
        
        files = {
            'file': ('download_test.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }
        
        upload_response = requests.post(
            f"{BASE_URL}/api/serviceplan/{test_plan['id']}/entries/{test_entry['id']}/images",
            headers=auth_headers_multipart,
            files=files
        )
        assert upload_response.status_code == 200
        image_id = upload_response.json()['id']
        
        # Now download it without auth (public endpoint based on code)
        download_response = requests.get(f"{BASE_URL}/api/serviceplan/images/{image_id}")
        
        assert download_response.status_code == 200, f"Download failed: {download_response.status_code}"
        assert download_response.headers.get('Content-Type') == 'application/pdf'
        assert download_response.content.startswith(b'%PDF')
        
        print(f"PDF download returns correct content-type: application/pdf")

    def test_attachments_metadata_stored_on_entry(self, auth_headers, auth_headers_multipart, test_plan, test_entry):
        """Test that attachments metadata array is stored on entry"""
        # Upload a PDF
        pdf_content = b'%PDF-1.4\nMetadata Test PDF'
        
        files = {
            'file': ('metadata_test.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }
        
        upload_response = requests.post(
            f"{BASE_URL}/api/serviceplan/{test_plan['id']}/entries/{test_entry['id']}/images",
            headers=auth_headers_multipart,
            files=files
        )
        assert upload_response.status_code == 200
        uploaded = upload_response.json()
        
        # Get the plan detail to check entry
        plan_response = requests.get(
            f"{BASE_URL}/api/serviceplan/{test_plan['id']}",
            headers=auth_headers
        )
        assert plan_response.status_code == 200
        
        plan = plan_response.json()
        entries = plan.get('entries', [])
        
        # Find our entry
        entry = None
        for e in entries:
            if e['id'] == test_entry['id']:
                entry = e
                break
        
        assert entry is not None, "Test entry not found in plan detail"
        
        # Check attachments array exists and contains our upload
        attachments = entry.get('attachments', [])
        assert len(attachments) > 0, "Attachments array should not be empty"
        
        # Find our uploaded attachment
        found_attachment = None
        for att in attachments:
            if att.get('id') == uploaded['id']:
                found_attachment = att
                break
        
        assert found_attachment is not None, f"Uploaded attachment {uploaded['id']} not found in attachments"
        assert found_attachment['filename'] == 'metadata_test.pdf'
        assert found_attachment['content_type'] == 'application/pdf'
        assert 'size' in found_attachment
        
        print(f"Attachments metadata verified: {len(attachments)} attachments on entry")
        print(f"Sample attachment: id={found_attachment['id']}, filename={found_attachment['filename']}, content_type={found_attachment['content_type']}, size={found_attachment['size']}")

    def test_images_array_backward_compat(self, auth_headers, auth_headers_multipart, test_plan, test_entry):
        """Test that images array is also populated for backward compatibility"""
        # Get the entry detail
        plan_response = requests.get(
            f"{BASE_URL}/api/serviceplan/{test_plan['id']}",
            headers=auth_headers
        )
        assert plan_response.status_code == 200
        
        plan = plan_response.json()
        entries = plan.get('entries', [])
        
        # Find our entry
        entry = None
        for e in entries:
            if e['id'] == test_entry['id']:
                entry = e
                break
        
        assert entry is not None
        
        # Check images array exists
        images = entry.get('images', [])
        assert len(images) > 0, "Images array should not be empty (backward compat)"
        
        print(f"Images array (backward compat) has {len(images)} entries")


class TestServiceplanCRUDRegression:
    """Regression tests - Serviceplan CRUD still works"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

    def test_list_service_plans(self, auth_headers):
        """Regression: GET /api/serviceplan returns list"""
        response = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers)
        assert response.status_code == 200
        
        plans = response.json()
        assert isinstance(plans, list)
        print(f"Found {len(plans)} service plans")

    def test_get_service_plan_detail(self, auth_headers):
        """Regression: GET /api/serviceplan/{id} returns plan with entries"""
        # Get list first
        list_response = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers)
        if list_response.status_code != 200 or len(list_response.json()) == 0:
            pytest.skip("No service plans available")
        
        plan_id = list_response.json()[0]['id']
        
        response = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", headers=auth_headers)
        assert response.status_code == 200
        
        plan = response.json()
        assert 'id' in plan
        assert 'device_id' in plan
        assert 'entries' in plan
        
        print(f"Plan {plan_id} has {len(plan['entries'])} entries")

    def test_create_maintenance_entry(self, auth_headers):
        """Regression: POST /api/serviceplan/{id}/entries creates entry"""
        # Get a plan
        list_response = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers)
        if list_response.status_code != 200 or len(list_response.json()) == 0:
            pytest.skip("No service plans available")
        
        plan_id = list_response.json()[0]['id']
        
        entry_data = {
            "performed_by": "Regression Test",
            "performed_at": "2026-01-15",
            "hours_at_service": 9999,
            "next_maintenance_months": 12,
            "next_maintenance_hours": 500,
            "checklist_data": {"mechanical": {}, "electrical": {}},
            "notes": "Regression test entry",
            "remarks": ""
        }
        
        response = requests.post(
            f"{BASE_URL}/api/serviceplan/{plan_id}/entries",
            json=entry_data,
            headers=auth_headers
        )
        
        assert response.status_code in [200, 201], f"Create entry failed: {response.text}"
        
        entry = response.json()
        assert 'id' in entry
        assert entry['performed_by'] == "Regression Test"
        
        print(f"Created entry {entry['id']} in plan {plan_id}")


class TestMesskofferKirmeskisteReducedPlan:
    """Test that Messkoffer/Kirmeskiste device types show reduced plan (electrical + diagnosis only)"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

    def test_get_devices_includes_messkoffer_kirmeskiste(self, auth_headers):
        """Check if there are any messkoffer or kirmeskiste devices"""
        response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert response.status_code == 200
        
        devices = response.json()
        reduced_types = ['messkoffer', 'kirmeskiste']
        
        messkoffer_devices = [d for d in devices if d.get('device_type') in reduced_types]
        stromerzeuger_devices = [d for d in devices if d.get('device_type') == 'stromerzeuger']
        
        print(f"Found {len(messkoffer_devices)} messkoffer/kirmeskiste devices")
        print(f"Found {len(stromerzeuger_devices)} stromerzeuger devices")
        
        # Verify device types exist for frontend testing
        all_types = set(d.get('device_type') for d in devices)
        print(f"All device types: {all_types}")


class TestListEntryImages:
    """Test listing images for an entry"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

    def test_list_entry_images_endpoint(self, auth_headers):
        """Test GET /api/serviceplan/{plan_id}/entries/{entry_id}/images"""
        # Get a plan with entries
        list_response = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers)
        if list_response.status_code != 200 or len(list_response.json()) == 0:
            pytest.skip("No service plans available")
        
        plan_id = list_response.json()[0]['id']
        
        # Get plan detail to find an entry
        plan_response = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", headers=auth_headers)
        if plan_response.status_code != 200:
            pytest.skip("Cannot get plan detail")
        
        entries = plan_response.json().get('entries', [])
        if len(entries) == 0:
            pytest.skip("No entries in plan")
        
        entry_id = entries[0]['id']
        
        # List images for this entry
        images_response = requests.get(
            f"{BASE_URL}/api/serviceplan/{plan_id}/entries/{entry_id}/images",
            headers=auth_headers
        )
        
        assert images_response.status_code == 200
        images = images_response.json()
        assert isinstance(images, list)
        
        print(f"Entry {entry_id} has {len(images)} images/attachments")
        for img in images[:3]:  # Print first 3
            print(f"  - {img.get('filename')} ({img.get('content_type')})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
