"""
Test Employee Profile and Document Management APIs
Tests for: GET/PUT /api/employee/profile, PUT /api/employee/profile/password,
GET /api/employee/document-types, POST/GET/PUT /api/employee/documents
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "password"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")

@pytest.fixture(scope="module")
def mitarbeiter_token():
    """Get mitarbeiter authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "ma1@test.com",
        "password": "password"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Mitarbeiter authentication failed")


class TestEmployeeProfile:
    """Test employee profile endpoints"""
    
    def test_get_profile_returns_data(self, admin_token):
        """GET /api/employee/profile returns profile data"""
        response = requests.get(f"{BASE_URL}/api/employee/profile?token={admin_token}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify required fields exist
        assert "user_id" in data, "Missing user_id in profile"
        assert "name" in data, "Missing name in profile"
        assert "email" in data, "Missing email in profile"
        assert "role" in data, "Missing role in profile"
        assert "phone" in data, "Missing phone in profile"
        assert "street" in data, "Missing street in profile"
        assert "zip_code" in data, "Missing zip_code in profile"
        assert "city" in data, "Missing city in profile"
        print(f"Profile data: user_id={data['user_id']}, name={data['name']}, email={data['email']}")
    
    def test_update_profile_name_phone_address(self, admin_token):
        """PUT /api/employee/profile updates name, phone, address"""
        # First get current profile
        get_response = requests.get(f"{BASE_URL}/api/employee/profile?token={admin_token}")
        original = get_response.json()
        
        # Update profile with test data
        update_data = {
            "name": "TEST_Updated Admin Name",
            "phone": "+49 170 1234567",
            "street": "Teststraße 123",
            "zip_code": "12345",
            "city": "Teststadt"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/employee/profile?token={admin_token}",
            data=update_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["name"] == update_data["name"], f"Name not updated: {data['name']}"
        assert data["phone"] == update_data["phone"], f"Phone not updated: {data['phone']}"
        assert data["street"] == update_data["street"], f"Street not updated: {data['street']}"
        assert data["zip_code"] == update_data["zip_code"], f"Zip code not updated: {data['zip_code']}"
        assert data["city"] == update_data["city"], f"City not updated: {data['city']}"
        
        # Verify persistence with GET
        verify_response = requests.get(f"{BASE_URL}/api/employee/profile?token={admin_token}")
        verify_data = verify_response.json()
        assert verify_data["phone"] == update_data["phone"], "Phone not persisted"
        assert verify_data["city"] == update_data["city"], "City not persisted"
        
        # Restore original name
        restore_data = {
            "name": original.get("name", "Admin"),
            "phone": original.get("phone", ""),
            "street": original.get("street", ""),
            "zip_code": original.get("zip_code", ""),
            "city": original.get("city", "")
        }
        requests.put(
            f"{BASE_URL}/api/employee/profile?token={admin_token}",
            data=restore_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        print("Profile update test passed - name, phone, address updated and verified")
    
    def test_get_profile_without_token_fails(self):
        """GET /api/employee/profile without token returns 422"""
        response = requests.get(f"{BASE_URL}/api/employee/profile")
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("Profile without token correctly returns 422")


class TestPasswordChange:
    """Test password change endpoint"""
    
    def test_change_password_with_correct_old_password(self, mitarbeiter_token):
        """PUT /api/employee/profile/password changes password with correct old password"""
        # Change password
        response = requests.put(
            f"{BASE_URL}/api/employee/profile/password?token={mitarbeiter_token}",
            json={
                "old_password": "password",
                "new_password": "newpassword123"
            }
        )
        # If user has no password stored, we get 400 with specific message
        if response.status_code == 400:
            data = response.json()
            if "Kein Passwort gesetzt" in data.get("detail", ""):
                print("User has no password stored in DB - this is expected for some test users")
                pytest.skip("User has no password stored - cannot test password change")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok", f"Expected status ok, got {data}"
        
        # Verify new password works
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "ma1@test.com",
            "password": "newpassword123"
        })
        assert login_response.status_code == 200, "Login with new password failed"
        
        # Restore original password
        new_token = login_response.json().get("token")
        restore_response = requests.put(
            f"{BASE_URL}/api/employee/profile/password?token={new_token}",
            json={
                "old_password": "newpassword123",
                "new_password": "password"
            }
        )
        assert restore_response.status_code == 200, "Failed to restore original password"
        print("Password change test passed - changed and restored successfully")
    
    def test_change_password_with_wrong_old_password(self, admin_token):
        """PUT /api/employee/profile/password rejects wrong old password"""
        response = requests.put(
            f"{BASE_URL}/api/employee/profile/password?token={admin_token}",
            json={
                "old_password": "wrongpassword",
                "new_password": "newpassword123"
            }
        )
        # If user has no password stored, we get 400 with specific message
        if response.status_code == 400:
            data = response.json()
            if "Kein Passwort gesetzt" in data.get("detail", ""):
                print("User has no password stored in DB - this is expected for some test users")
                pytest.skip("User has no password stored - cannot test wrong password rejection")
            # Otherwise it should be the "wrong password" error
            assert "falsch" in data["detail"].lower() or "wrong" in data["detail"].lower(), f"Unexpected error: {data['detail']}"
            print(f"Wrong password correctly rejected: {data['detail']}")
            return
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "detail" in data, "Missing error detail"
        assert "falsch" in data["detail"].lower() or "wrong" in data["detail"].lower(), f"Unexpected error: {data['detail']}"
        print(f"Wrong password correctly rejected: {data['detail']}")
    
    def test_change_password_missing_fields(self, admin_token):
        """PUT /api/employee/profile/password requires both old and new password"""
        response = requests.put(
            f"{BASE_URL}/api/employee/profile/password?token={admin_token}",
            json={"old_password": "password"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("Missing new_password correctly rejected")


class TestDocumentTypes:
    """Test document types endpoint"""
    
    def test_get_document_types_returns_9_types(self, admin_token):
        """GET /api/employee/document-types returns 9 document types"""
        response = requests.get(f"{BASE_URL}/api/employee/document-types?token={admin_token}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of document types"
        assert len(data) == 9, f"Expected 9 document types, got {len(data)}"
        
        # Verify expected types
        expected_keys = [
            "personalausweis", "fuehrerschein", "fahrerkarte", "erste_hilfe",
            "sicherheitsunterweisung", "staplerschein", "hubarbeitsbuehne",
            "teleskoplader", "baumaschine"
        ]
        actual_keys = [d["key"] for d in data]
        for key in expected_keys:
            assert key in actual_keys, f"Missing document type: {key}"
        
        # Verify each type has key and label
        for doc_type in data:
            assert "key" in doc_type, "Missing key in document type"
            assert "label" in doc_type, "Missing label in document type"
        
        print(f"Document types: {[d['key'] for d in data]}")


class TestDocumentUpload:
    """Test document upload and management"""
    
    def test_upload_pdf_creates_document_record(self, admin_token):
        """POST /api/employee/documents uploads a PDF and creates document record"""
        # Create a simple PDF-like content (minimal valid PDF)
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        
        files = {
            "file": ("test_document.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        data = {
            "doc_type": "personalausweis"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/employee/documents?token={admin_token}",
            files=files,
            data=data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        doc = response.json()
        assert "id" in doc, "Missing document id"
        assert doc["doc_type"] == "personalausweis", f"Wrong doc_type: {doc['doc_type']}"
        assert doc["filename"] == "test_document.pdf", f"Wrong filename: {doc['filename']}"
        assert doc["status"] == "active", f"Wrong status: {doc['status']}"
        assert "storage_path" in doc, "Missing storage_path"
        assert "uploaded_at" in doc, "Missing uploaded_at"
        
        print(f"Document uploaded: id={doc['id']}, type={doc['doc_type']}, status={doc['status']}")
        return doc["id"]
    
    def test_get_documents_returns_list(self, admin_token):
        """GET /api/employee/documents returns list of documents"""
        response = requests.get(f"{BASE_URL}/api/employee/documents?token={admin_token}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of documents"
        
        if len(data) > 0:
            doc = data[0]
            assert "id" in doc, "Missing id in document"
            assert "doc_type" in doc, "Missing doc_type in document"
            assert "filename" in doc, "Missing filename in document"
            assert "status" in doc, "Missing status in document"
            print(f"Found {len(data)} documents, first: {doc['doc_type']} - {doc['filename']}")
        else:
            print("No documents found (empty list)")
    
    def test_update_document_expiry_date(self, admin_token):
        """PUT /api/employee/documents/{id} updates expiry date"""
        # First upload a document
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        files = {"file": ("test_expiry.pdf", io.BytesIO(pdf_content), "application/pdf")}
        data = {"doc_type": "fuehrerschein"}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/employee/documents?token={admin_token}",
            files=files,
            data=data
        )
        assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
        doc_id = upload_response.json()["id"]
        
        # Update expiry date
        new_expiry = "2027-12-31"
        update_response = requests.put(
            f"{BASE_URL}/api/employee/documents/{doc_id}?token={admin_token}",
            json={"expiry_date": new_expiry}
        )
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        
        updated_doc = update_response.json()
        assert updated_doc["expiry_date"] == new_expiry, f"Expiry not updated: {updated_doc['expiry_date']}"
        
        # Verify persistence
        docs_response = requests.get(f"{BASE_URL}/api/employee/documents?token={admin_token}")
        docs = docs_response.json()
        found_doc = next((d for d in docs if d["id"] == doc_id), None)
        assert found_doc is not None, "Document not found after update"
        assert found_doc["expiry_date"] == new_expiry, "Expiry date not persisted"
        
        print(f"Document expiry updated: {doc_id} -> {new_expiry}")
    
    def test_download_document_file(self, admin_token):
        """GET /api/employee/documents/{id}/file downloads the document"""
        # First upload a document
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        files = {"file": ("test_download.pdf", io.BytesIO(pdf_content), "application/pdf")}
        data = {"doc_type": "fahrerkarte"}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/employee/documents?token={admin_token}",
            files=files,
            data=data
        )
        assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
        doc_id = upload_response.json()["id"]
        
        # Download the file
        download_response = requests.get(
            f"{BASE_URL}/api/employee/documents/{doc_id}/file?token={admin_token}"
        )
        assert download_response.status_code == 200, f"Expected 200, got {download_response.status_code}: {download_response.text}"
        assert download_response.headers.get("content-type") == "application/pdf", f"Wrong content type: {download_response.headers.get('content-type')}"
        assert len(download_response.content) > 0, "Empty file content"
        
        print(f"Document downloaded: {doc_id}, size={len(download_response.content)} bytes")
    
    def test_upload_same_type_marks_old_as_alt(self, admin_token):
        """POST /api/employee/documents for same type marks old as 'alt'"""
        doc_type = "staplerschein"
        
        # Upload first document
        pdf_content1 = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        files1 = {"file": ("first_staplerschein.pdf", io.BytesIO(pdf_content1), "application/pdf")}
        
        response1 = requests.post(
            f"{BASE_URL}/api/employee/documents?token={admin_token}",
            files=files1,
            data={"doc_type": doc_type}
        )
        assert response1.status_code == 200, f"First upload failed: {response1.text}"
        first_doc_id = response1.json()["id"]
        assert response1.json()["status"] == "active", "First doc should be active"
        
        # Upload second document of same type
        pdf_content2 = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        files2 = {"file": ("second_staplerschein.pdf", io.BytesIO(pdf_content2), "application/pdf")}
        
        response2 = requests.post(
            f"{BASE_URL}/api/employee/documents?token={admin_token}",
            files=files2,
            data={"doc_type": doc_type}
        )
        assert response2.status_code == 200, f"Second upload failed: {response2.text}"
        second_doc_id = response2.json()["id"]
        assert response2.json()["status"] == "active", "Second doc should be active"
        
        # Verify first document is now marked as 'alt'
        docs_response = requests.get(f"{BASE_URL}/api/employee/documents?token={admin_token}")
        docs = docs_response.json()
        
        first_doc = next((d for d in docs if d["id"] == first_doc_id), None)
        second_doc = next((d for d in docs if d["id"] == second_doc_id), None)
        
        assert first_doc is not None, "First document not found"
        assert second_doc is not None, "Second document not found"
        assert first_doc["status"] == "alt", f"First doc should be 'alt', got: {first_doc['status']}"
        assert second_doc["status"] == "active", f"Second doc should be 'active', got: {second_doc['status']}"
        
        print(f"Old document marked as 'alt': {first_doc_id} (status={first_doc['status']})")
        print(f"New document is active: {second_doc_id} (status={second_doc['status']})")
    
    def test_upload_invalid_doc_type_fails(self, admin_token):
        """POST /api/employee/documents with invalid doc_type returns 400"""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
        
        response = requests.post(
            f"{BASE_URL}/api/employee/documents?token={admin_token}",
            files=files,
            data={"doc_type": "invalid_type"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("Invalid doc_type correctly rejected")


class TestDocumentPermissions:
    """Test document access permissions"""
    
    def test_cannot_access_other_user_document(self, admin_token, mitarbeiter_token):
        """Non-admin cannot access other user's documents"""
        # Upload document as admin
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        files = {"file": ("admin_doc.pdf", io.BytesIO(pdf_content), "application/pdf")}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/employee/documents?token={admin_token}",
            files=files,
            data={"doc_type": "baumaschine"}
        )
        assert upload_response.status_code == 200
        doc_id = upload_response.json()["id"]
        
        # Try to download as mitarbeiter (should fail with 403)
        download_response = requests.get(
            f"{BASE_URL}/api/employee/documents/{doc_id}/file?token={mitarbeiter_token}"
        )
        # Should be 403 Forbidden since mitarbeiter is not admin and not owner
        assert download_response.status_code == 403, f"Expected 403, got {download_response.status_code}"
        print("Document access correctly restricted to owner/admin")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
