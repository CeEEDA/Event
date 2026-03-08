"""
Test suite for Kirmes Event Documents (Dokumentenablage) feature.
Tests document upload, listing, download/preview, delete for event documents.

Endpoints:
- POST /api/kirmes/events/{event_id}/documents - Upload PDF/image
- GET /api/kirmes/events/{event_id}/documents - List documents
- GET /api/kirmes/events/{event_id}/documents/{doc_id}/file - Download/preview
- DELETE /api/kirmes/events/{event_id}/documents/{doc_id} - Delete document
"""

import pytest
import requests
import os
import io

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TEST_EVENT_ID = "4b4f740b-16be-496b-aabf-e0b2667f8316"  # Test event with status 'freigegeben'


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "password"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping tests")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}"}


# ============== Test Upload Document ==============

class TestDocumentUpload:
    """Test POST /api/kirmes/events/{event_id}/documents"""

    def test_upload_pdf_document(self, auth_headers):
        """Upload a PDF document successfully."""
        # Create a minimal PDF file
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        files = {"file": ("test_document.pdf", io.BytesIO(pdf_content), "application/pdf")}
        
        response = requests.post(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["original_name"] == "test_document.pdf"
        assert data["message"] == "Dokument hochgeladen"
        
        # Store doc_id for cleanup
        TestDocumentUpload.uploaded_pdf_id = data["id"]
        print(f"✅ PDF upload successful: {data['id']}")

    def test_upload_jpg_image(self, auth_headers):
        """Upload a JPG image successfully."""
        # Create a minimal valid JPEG (smallest valid JPEG)
        jpg_content = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
            0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
            0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
            0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
            0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
            0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
            0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
            0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
            0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
            0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
            0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
            0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
            0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
            0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
            0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
            0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
            0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
            0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
            0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
            0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
            0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
            0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
            0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
            0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
            0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xFF, 0xD9
        ])
        
        files = {"file": ("test_image.jpg", io.BytesIO(jpg_content), "image/jpeg")}
        
        response = requests.post(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["original_name"] == "test_image.jpg"
        
        # Store for cleanup
        TestDocumentUpload.uploaded_jpg_id = data["id"]
        print(f"✅ JPG upload successful: {data['id']}")

    def test_upload_png_image(self, auth_headers):
        """Upload a PNG image successfully."""
        # Minimal valid PNG (1x1 white pixel)
        png_content = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D,
            0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53, 0xDE, 0x00, 0x00, 0x00,
            0x0C, 0x49, 0x44, 0x41, 0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59, 0xE7, 0x00, 0x00, 0x00,
            0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        
        files = {"file": ("test_image.png", io.BytesIO(png_content), "image/png")}
        
        response = requests.post(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data
        
        TestDocumentUpload.uploaded_png_id = data["id"]
        print(f"✅ PNG upload successful: {data['id']}")

    def test_reject_unsupported_file_type(self, auth_headers):
        """Reject unsupported file types like .txt."""
        txt_content = b"This is a text file which should be rejected"
        files = {"file": ("test.txt", io.BytesIO(txt_content), "text/plain")}
        
        response = requests.post(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Nur PDF und Bilder" in data.get("detail", "")
        print(f"✅ Unsupported file type correctly rejected: {data['detail']}")

    def test_reject_executable_file(self, auth_headers):
        """Reject executable files."""
        exe_content = b"MZ\x90\x00"  # Minimal PE header
        files = {"file": ("malware.exe", io.BytesIO(exe_content), "application/x-msdownload")}
        
        response = requests.post(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ Executable file correctly rejected")

    def test_upload_to_nonexistent_event(self, auth_headers):
        """Uploading to non-existent event returns 404."""
        pdf_content = b"%PDF-1.4\ntest"
        files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
        
        response = requests.post(
            f"{BASE_URL}/api/kirmes/events/nonexistent-event-id-12345/documents",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ Upload to non-existent event correctly returns 404")


# ============== Test List Documents ==============

class TestListDocuments:
    """Test GET /api/kirmes/events/{event_id}/documents"""

    def test_list_documents_success(self, auth_headers):
        """List documents returns uploaded documents."""
        response = requests.get(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list)
        
        # Should have at least the docs we uploaded
        print(f"✅ List documents returned {len(data)} documents")
        
        # Verify document structure
        if len(data) > 0:
            doc = data[0]
            assert "id" in doc
            assert "event_id" in doc
            assert "original_name" in doc
            assert "content_type" in doc
            assert "size" in doc
            assert "uploaded_at" in doc
            assert "uploaded_by" in doc
            print(f"✅ Document structure verified: {list(doc.keys())}")

    def test_list_documents_unauthorized(self):
        """List documents without auth returns 401/403."""
        response = requests.get(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents"
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✅ Unauthorized access correctly rejected")


# ============== Test Download/Preview Document ==============

class TestDownloadDocument:
    """Test GET /api/kirmes/events/{event_id}/documents/{doc_id}/file"""

    def test_download_pdf_document(self, auth_headers, auth_token):
        """Download PDF document file."""
        # First get a document ID
        list_response = requests.get(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents",
            headers=auth_headers
        )
        docs = list_response.json()
        pdf_docs = [d for d in docs if d["content_type"] == "application/pdf"]
        
        if not pdf_docs:
            pytest.skip("No PDF documents available to download")
        
        doc = pdf_docs[0]
        
        # Download with token query param (as used by frontend for inline display)
        response = requests.get(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents/{doc['id']}/file",
            params={"token": auth_token},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("content-type") == "application/pdf"
        assert "inline" in response.headers.get("content-disposition", "")
        print(f"✅ PDF download successful: {len(response.content)} bytes")

    def test_download_image_document(self, auth_headers, auth_token):
        """Download image document file."""
        list_response = requests.get(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents",
            headers=auth_headers
        )
        docs = list_response.json()
        image_docs = [d for d in docs if d["content_type"].startswith("image/")]
        
        if not image_docs:
            pytest.skip("No image documents available to download")
        
        doc = image_docs[0]
        
        response = requests.get(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents/{doc['id']}/file",
            params={"token": auth_token},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("content-type").startswith("image/")
        print(f"✅ Image download successful: {len(response.content)} bytes")

    def test_download_nonexistent_document(self, auth_headers, auth_token):
        """Download non-existent document returns 404."""
        response = requests.get(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents/nonexistent-doc-id/file",
            params={"token": auth_token},
            headers=auth_headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ Non-existent document correctly returns 404")


# ============== Test Delete Document ==============

class TestDeleteDocument:
    """Test DELETE /api/kirmes/events/{event_id}/documents/{doc_id}"""

    def test_delete_document_success(self, auth_headers):
        """Delete a document successfully."""
        # First upload a document to delete
        pdf_content = b"%PDF-1.4\ndelete_test"
        files = {"file": ("delete_test.pdf", io.BytesIO(pdf_content), "application/pdf")}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents",
            files=files,
            headers=auth_headers
        )
        
        if upload_response.status_code != 200:
            pytest.skip("Could not upload test document")
        
        doc_id = upload_response.json()["id"]
        
        # Delete the document
        delete_response = requests.delete(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents/{doc_id}",
            headers=auth_headers
        )
        
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        data = delete_response.json()
        assert "gelöscht" in data.get("message", "").lower() or "Dokument" in data.get("message", "")
        print(f"✅ Document deleted successfully: {data['message']}")
        
        # Verify it's gone - list should not contain the document
        list_response = requests.get(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents",
            headers=auth_headers
        )
        docs = list_response.json()
        deleted_doc = [d for d in docs if d["id"] == doc_id]
        assert len(deleted_doc) == 0, "Deleted document should not appear in list"
        print("✅ Verified document no longer in list")

    def test_delete_nonexistent_document(self, auth_headers):
        """Delete non-existent document returns 404."""
        response = requests.delete(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents/nonexistent-doc-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ Delete non-existent document correctly returns 404")

    def test_delete_unauthorized(self):
        """Delete without auth returns 401/403."""
        response = requests.delete(
            f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents/some-doc-id"
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✅ Unauthorized delete correctly rejected")


# ============== Cleanup ==============

class TestCleanup:
    """Cleanup test documents."""

    def test_cleanup_uploaded_documents(self, auth_headers):
        """Clean up test documents."""
        ids_to_delete = []
        
        # Collect IDs from TestDocumentUpload if they exist
        if hasattr(TestDocumentUpload, "uploaded_pdf_id"):
            ids_to_delete.append(TestDocumentUpload.uploaded_pdf_id)
        if hasattr(TestDocumentUpload, "uploaded_jpg_id"):
            ids_to_delete.append(TestDocumentUpload.uploaded_jpg_id)
        if hasattr(TestDocumentUpload, "uploaded_png_id"):
            ids_to_delete.append(TestDocumentUpload.uploaded_png_id)
        
        deleted = 0
        for doc_id in ids_to_delete:
            response = requests.delete(
                f"{BASE_URL}/api/kirmes/events/{TEST_EVENT_ID}/documents/{doc_id}",
                headers=auth_headers
            )
            if response.status_code == 200:
                deleted += 1
        
        print(f"✅ Cleanup: Deleted {deleted}/{len(ids_to_delete)} test documents")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
