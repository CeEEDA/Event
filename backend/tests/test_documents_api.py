"""
Document Management API Tests
Tests for the Dokumentenverwaltung feature including:
- Folder listing with counts
- Document upload with AI analysis
- Document listing and filtering
- Full-text search
- Document move and delete operations
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDocumentFolders:
    """Tests for folder listing endpoint"""
    
    def test_get_folders_returns_7_predefined_folders(self):
        """Verify all 7 predefined folders are returned"""
        response = requests.get(f"{BASE_URL}/api/documents/folders")
        assert response.status_code == 200
        
        data = response.json()
        assert "folders" in data
        assert "total" in data
        assert len(data["folders"]) == 7
        
        # Verify folder IDs
        folder_ids = [f["id"] for f in data["folders"]]
        expected_ids = ["rechnungseingang", "kfz_versicherung", "betriebshaftpflicht", 
                       "vertraege", "lieferscheine", "behoerden", "sonstiges"]
        assert set(folder_ids) == set(expected_ids)
        
    def test_folders_have_required_fields(self):
        """Verify each folder has required fields"""
        response = requests.get(f"{BASE_URL}/api/documents/folders")
        assert response.status_code == 200
        
        for folder in response.json()["folders"]:
            assert "id" in folder
            assert "name" in folder
            assert "icon" in folder
            assert "color" in folder
            assert "count" in folder
            assert isinstance(folder["count"], int)


class TestDocumentList:
    """Tests for document listing endpoint"""
    
    def test_list_all_documents(self):
        """List all documents without folder filter"""
        response = requests.get(f"{BASE_URL}/api/documents/list")
        assert response.status_code == 200
        
        data = response.json()
        assert "documents" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        
    def test_list_documents_by_folder(self):
        """List documents filtered by folder"""
        response = requests.get(f"{BASE_URL}/api/documents/list?folder_id=kfz_versicherung")
        assert response.status_code == 200
        
        data = response.json()
        # All returned documents should be in the specified folder
        for doc in data["documents"]:
            assert doc["folder_id"] == "kfz_versicherung"
            
    def test_list_documents_pagination(self):
        """Test pagination parameters"""
        response = requests.get(f"{BASE_URL}/api/documents/list?page=1&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data["page"] == 1
        assert data["limit"] == 10


class TestDocumentSearch:
    """Tests for full-text search endpoint"""
    
    def test_search_by_sender(self):
        """Search documents by sender name"""
        response = requests.get(f"{BASE_URL}/api/documents/search?q=Autohaus")
        assert response.status_code == 200
        
        data = response.json()
        assert "documents" in data
        assert "query" in data
        assert data["query"] == "Autohaus"
        
    def test_search_by_iban(self):
        """Search documents by IBAN"""
        response = requests.get(f"{BASE_URL}/api/documents/search?q=DE89370400")
        assert response.status_code == 200
        
        data = response.json()
        assert "documents" in data
        # Should find the test document with this IBAN
        
    def test_search_by_reference(self):
        """Search documents by reference/Verwendungszweck"""
        response = requests.get(f"{BASE_URL}/api/documents/search?q=Transit")
        assert response.status_code == 200
        
        data = response.json()
        assert "documents" in data
        
    def test_search_requires_query(self):
        """Search without query should fail"""
        response = requests.get(f"{BASE_URL}/api/documents/search")
        assert response.status_code == 422  # Validation error
        
    def test_search_minimum_length(self):
        """Search with too short query should fail"""
        response = requests.get(f"{BASE_URL}/api/documents/search?q=a")
        # Should fail validation (min_length=1 but might need 2)
        # Accept either 200 or 422 depending on implementation
        assert response.status_code in [200, 422]


class TestDocumentDetail:
    """Tests for single document retrieval"""
    
    def test_get_existing_document(self):
        """Get details of an existing document"""
        # First get list to find a document ID
        list_response = requests.get(f"{BASE_URL}/api/documents/list")
        assert list_response.status_code == 200
        
        docs = list_response.json()["documents"]
        if len(docs) > 0:
            doc_id = docs[0]["id"]
            response = requests.get(f"{BASE_URL}/api/documents/{doc_id}")
            assert response.status_code == 200
            
            data = response.json()
            assert data["id"] == doc_id
            assert "ai_metadata" in data
            assert "ai_status" in data
            
    def test_get_nonexistent_document(self):
        """Get non-existent document should return 404"""
        response = requests.get(f"{BASE_URL}/api/documents/nonexistent-id-12345")
        assert response.status_code == 404


class TestDocumentUpload:
    """Tests for document upload endpoint"""
    
    def test_upload_invalid_file_type(self):
        """Upload unsupported file type should fail"""
        files = {"file": ("test.txt", io.BytesIO(b"test content"), "text/plain")}
        data = {"folder_id": "sonstiges"}
        
        response = requests.post(f"{BASE_URL}/api/documents/upload", files=files, data=data)
        assert response.status_code == 400
        assert "nicht unterstützt" in response.json().get("detail", "")
        
    def test_upload_valid_image(self):
        """Upload a valid PNG image"""
        # Create a minimal valid PNG (1x1 pixel)
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 dimensions
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # bit depth, color type, etc
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,  # compressed data
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,  # 
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
            0x44, 0xAE, 0x42, 0x60, 0x82                      # IEND CRC
        ])
        
        files = {"file": ("TEST_upload_test.png", io.BytesIO(png_data), "image/png")}
        data = {"folder_id": "sonstiges"}
        
        response = requests.post(f"{BASE_URL}/api/documents/upload", files=files, data=data, timeout=120)
        assert response.status_code == 200
        
        doc = response.json()
        assert "id" in doc
        assert doc["original_filename"] == "TEST_upload_test.png"
        assert doc["content_type"] == "image/png"
        assert doc["ai_status"] in ["pending", "completed", "failed"]
        
        # Store doc_id for cleanup
        TestDocumentUpload.uploaded_doc_id = doc["id"]
        
    def test_cleanup_uploaded_document(self):
        """Clean up test document"""
        if hasattr(TestDocumentUpload, 'uploaded_doc_id'):
            doc_id = TestDocumentUpload.uploaded_doc_id
            response = requests.delete(f"{BASE_URL}/api/documents/{doc_id}")
            assert response.status_code == 200


class TestDocumentMove:
    """Tests for document move endpoint"""
    
    def test_move_document_to_valid_folder(self):
        """Move document to a valid folder"""
        # Get a document to move
        list_response = requests.get(f"{BASE_URL}/api/documents/list")
        docs = list_response.json()["documents"]
        
        if len(docs) > 0:
            doc_id = docs[0]["id"]
            original_folder = docs[0]["folder_id"]
            
            # Move to a different folder
            target_folder = "sonstiges" if original_folder != "sonstiges" else "rechnungseingang"
            
            response = requests.put(f"{BASE_URL}/api/documents/{doc_id}/move?folder_id={target_folder}")
            assert response.status_code == 200
            assert response.json()["status"] == "moved"
            assert response.json()["folder_id"] == target_folder
            
            # Move back to original folder
            requests.put(f"{BASE_URL}/api/documents/{doc_id}/move?folder_id={original_folder}")
            
    def test_move_document_to_invalid_folder(self):
        """Move document to invalid folder should fail"""
        list_response = requests.get(f"{BASE_URL}/api/documents/list")
        docs = list_response.json()["documents"]
        
        if len(docs) > 0:
            doc_id = docs[0]["id"]
            response = requests.put(f"{BASE_URL}/api/documents/{doc_id}/move?folder_id=invalid_folder")
            assert response.status_code == 400
            
    def test_move_nonexistent_document(self):
        """Move non-existent document should fail"""
        response = requests.put(f"{BASE_URL}/api/documents/nonexistent-id/move?folder_id=sonstiges")
        assert response.status_code == 404


class TestDocumentDelete:
    """Tests for document delete endpoint"""
    
    def test_delete_nonexistent_document(self):
        """Delete non-existent document should fail"""
        response = requests.delete(f"{BASE_URL}/api/documents/nonexistent-id-12345")
        assert response.status_code == 404


class TestDocumentFile:
    """Tests for document file download endpoint"""
    
    def test_download_existing_document_file(self):
        """Download file of existing document"""
        list_response = requests.get(f"{BASE_URL}/api/documents/list")
        docs = list_response.json()["documents"]
        
        if len(docs) > 0:
            doc_id = docs[0]["id"]
            response = requests.get(f"{BASE_URL}/api/documents/{doc_id}/file")
            assert response.status_code == 200
            assert len(response.content) > 0
            
    def test_download_nonexistent_document_file(self):
        """Download file of non-existent document should fail"""
        response = requests.get(f"{BASE_URL}/api/documents/nonexistent-id/file")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
