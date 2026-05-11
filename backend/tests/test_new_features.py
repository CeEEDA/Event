"""
FileShare Portal - New Features Tests
Tests for: File Download, File Delete, File Move, Folder ZIP Download, File Preview, All Folders API
Focus: The NEW features added to fix user-reported issues
"""
import pytest
import requests
import os
import uuid
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://trupps-dashboard.preview.emergentagent.com')


class TestNewFeatures:
    """Tests for newly implemented features"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if login_res.status_code != 200:
            pytest.skip("Admin login failed")
        return login_res.json()["token"]

    @pytest.fixture
    def test_file(self, admin_token):
        """Create a test file for testing"""
        files = {"file": ("TEST_download_test.txt", b"Test content for download", "text/plain")}
        data = {"folder_path": "/", "storage_area": "personal"}
        
        response = requests.post(f"{BASE_URL}/api/files/upload", 
            headers={"Authorization": f"Bearer {admin_token}"},
            files=files,
            data=data
        )
        assert response.status_code == 200
        file_data = response.json()
        
        yield file_data
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/files/{file_data['id']}", 
            headers={"Authorization": f"Bearer {admin_token}"})

    @pytest.fixture
    def test_image_file(self, admin_token):
        """Create a test image file for preview testing"""
        # Simple PNG file (1x1 red pixel)
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01\x00\x05\xfe\xd4\x00\x00\x00\x00IEND\xaeB`\x82'
        files = {"file": ("TEST_image.png", png_data, "image/png")}
        data = {"folder_path": "/", "storage_area": "personal"}
        
        response = requests.post(f"{BASE_URL}/api/files/upload", 
            headers={"Authorization": f"Bearer {admin_token}"},
            files=files,
            data=data
        )
        assert response.status_code == 200
        file_data = response.json()
        
        yield file_data
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/files/{file_data['id']}", 
            headers={"Authorization": f"Bearer {admin_token}"})

    @pytest.fixture
    def test_folder_with_file(self, admin_token):
        """Create a test folder with a file inside for ZIP download testing"""
        folder_name = f"TEST_zip_folder_{uuid.uuid4().hex[:8]}"
        
        # Create folder
        folder_res = requests.post(f"{BASE_URL}/api/folders", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": folder_name,
                "parent_path": "/",
                "storage_area": "personal"
            }
        )
        assert folder_res.status_code == 200
        folder_data = folder_res.json()
        
        # Upload file inside folder
        files = {"file": ("TEST_inside_folder.txt", b"Content inside folder", "text/plain")}
        data = {"folder_path": folder_data["path"], "storage_area": "personal"}
        
        file_res = requests.post(f"{BASE_URL}/api/files/upload", 
            headers={"Authorization": f"Bearer {admin_token}"},
            files=files,
            data=data
        )
        assert file_res.status_code == 200
        file_data = file_res.json()
        
        yield {"folder": folder_data, "file": file_data}
        
        # Cleanup - delete folder (which also deletes files inside)
        requests.delete(f"{BASE_URL}/api/folders/{folder_data['id']}", 
            headers={"Authorization": f"Bearer {admin_token}"})


    # ========== FILE DOWNLOAD TESTS ==========
    
    def test_file_download_success(self, admin_token, test_file):
        """Test that file download endpoint works correctly"""
        response = requests.get(f"{BASE_URL}/api/files/{test_file['id']}/download", 
            headers={"Authorization": f"Bearer {admin_token}"})
        
        assert response.status_code == 200, f"Download failed: {response.text}"
        assert len(response.content) > 0, "Downloaded file is empty"
        assert "Content-Disposition" in response.headers
        assert "attachment" in response.headers.get("Content-Disposition", "")
        print(f"✓ File download works, received {len(response.content)} bytes")

    def test_file_download_nonexistent(self, admin_token):
        """Test download of non-existent file returns 404"""
        response = requests.get(f"{BASE_URL}/api/files/nonexistent-id/download", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 404
        print("✓ Non-existent file download correctly returns 404")


    # ========== FILE DELETE TESTS ==========
    
    def test_file_delete_success(self, admin_token):
        """Test that file delete endpoint works correctly"""
        # First upload a file to delete
        files = {"file": ("TEST_delete_me.txt", b"Delete this content", "text/plain")}
        data = {"folder_path": "/", "storage_area": "personal"}
        
        upload_res = requests.post(f"{BASE_URL}/api/files/upload", 
            headers={"Authorization": f"Bearer {admin_token}"},
            files=files,
            data=data
        )
        assert upload_res.status_code == 200
        file_id = upload_res.json()["id"]
        
        # Now delete it
        delete_res = requests.delete(f"{BASE_URL}/api/files/{file_id}", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert delete_res.status_code == 200, f"Delete failed: {delete_res.text}"
        
        # Verify it's gone
        get_res = requests.get(f"{BASE_URL}/api/files/{file_id}/download", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert get_res.status_code == 404, "File still exists after deletion"
        print("✓ File delete works correctly")

    def test_file_delete_nonexistent(self, admin_token):
        """Test delete of non-existent file returns 404"""
        response = requests.delete(f"{BASE_URL}/api/files/nonexistent-id", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 404
        print("✓ Non-existent file delete correctly returns 404")


    # ========== FOLDER DELETE TESTS ==========
    
    def test_folder_delete_success(self, admin_token):
        """Test that folder delete endpoint works correctly"""
        folder_name = f"TEST_delete_folder_{uuid.uuid4().hex[:8]}"
        
        # Create folder
        create_res = requests.post(f"{BASE_URL}/api/folders", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": folder_name,
                "parent_path": "/",
                "storage_area": "personal"
            }
        )
        assert create_res.status_code == 200
        folder_id = create_res.json()["id"]
        
        # Delete folder
        delete_res = requests.delete(f"{BASE_URL}/api/folders/{folder_id}", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert delete_res.status_code == 200, f"Folder delete failed: {delete_res.text}"
        print("✓ Folder delete works correctly")


    # ========== FILE MOVE TESTS ==========
    
    def test_file_move_success(self, admin_token):
        """Test PUT /api/files/{file_id}/move endpoint"""
        # Create source folder
        source_folder_name = f"TEST_source_{uuid.uuid4().hex[:8]}"
        source_res = requests.post(f"{BASE_URL}/api/folders", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": source_folder_name, "parent_path": "/", "storage_area": "personal"}
        )
        assert source_res.status_code == 200
        source_folder = source_res.json()
        
        # Create target folder
        target_folder_name = f"TEST_target_{uuid.uuid4().hex[:8]}"
        target_res = requests.post(f"{BASE_URL}/api/folders", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": target_folder_name, "parent_path": "/", "storage_area": "personal"}
        )
        assert target_res.status_code == 200
        target_folder = target_res.json()
        
        # Upload file to source folder
        files = {"file": ("TEST_move_file.txt", b"Move me content", "text/plain")}
        data = {"folder_path": source_folder["path"], "storage_area": "personal"}
        upload_res = requests.post(f"{BASE_URL}/api/files/upload", 
            headers={"Authorization": f"Bearer {admin_token}"},
            files=files,
            data=data
        )
        assert upload_res.status_code == 200
        file_data = upload_res.json()
        assert file_data["folder_path"] == source_folder["path"]
        
        # Move file to target folder
        move_res = requests.put(f"{BASE_URL}/api/files/{file_data['id']}/move", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"target_folder_path": target_folder["path"]}
        )
        assert move_res.status_code == 200, f"Move failed: {move_res.text}"
        moved_file = move_res.json()
        assert moved_file["folder_path"] == target_folder["path"], "File not moved to target folder"
        print(f"✓ File move works: moved from {source_folder['path']} to {target_folder['path']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/files/{file_data['id']}", 
            headers={"Authorization": f"Bearer {admin_token}"})
        requests.delete(f"{BASE_URL}/api/folders/{source_folder['id']}", 
            headers={"Authorization": f"Bearer {admin_token}"})
        requests.delete(f"{BASE_URL}/api/folders/{target_folder['id']}", 
            headers={"Authorization": f"Bearer {admin_token}"})

    def test_file_move_to_root(self, admin_token):
        """Test moving file to root folder"""
        # Create folder and file inside
        folder_name = f"TEST_moveroot_{uuid.uuid4().hex[:8]}"
        folder_res = requests.post(f"{BASE_URL}/api/folders", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": folder_name, "parent_path": "/", "storage_area": "personal"}
        )
        assert folder_res.status_code == 200
        folder = folder_res.json()
        
        # Upload file to folder
        files = {"file": ("TEST_movetoroot.txt", b"Move to root", "text/plain")}
        data = {"folder_path": folder["path"], "storage_area": "personal"}
        upload_res = requests.post(f"{BASE_URL}/api/files/upload", 
            headers={"Authorization": f"Bearer {admin_token}"},
            files=files,
            data=data
        )
        assert upload_res.status_code == 200
        file_data = upload_res.json()
        
        # Move to root
        move_res = requests.put(f"{BASE_URL}/api/files/{file_data['id']}/move", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"target_folder_path": "/"}
        )
        assert move_res.status_code == 200
        moved_file = move_res.json()
        assert moved_file["folder_path"] == "/"
        print("✓ File move to root works")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/files/{file_data['id']}", 
            headers={"Authorization": f"Bearer {admin_token}"})
        requests.delete(f"{BASE_URL}/api/folders/{folder['id']}", 
            headers={"Authorization": f"Bearer {admin_token}"})


    # ========== FOLDER ZIP DOWNLOAD TESTS ==========
    
    def test_folder_zip_download(self, admin_token, test_folder_with_file):
        """Test GET /api/folders/{folder_id}/download returns ZIP"""
        folder = test_folder_with_file["folder"]
        
        response = requests.get(f"{BASE_URL}/api/folders/{folder['id']}/download", 
            headers={"Authorization": f"Bearer {admin_token}"})
        
        assert response.status_code == 200, f"ZIP download failed: {response.text}"
        assert "application/zip" in response.headers.get("Content-Type", "")
        assert len(response.content) > 0, "ZIP file is empty"
        assert "Content-Disposition" in response.headers
        print(f"✓ Folder ZIP download works, received {len(response.content)} bytes")

    def test_folder_zip_download_empty_folder(self, admin_token):
        """Test ZIP download of empty folder returns 404"""
        # Create empty folder
        folder_name = f"TEST_empty_{uuid.uuid4().hex[:8]}"
        folder_res = requests.post(f"{BASE_URL}/api/folders", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": folder_name, "parent_path": "/", "storage_area": "personal"}
        )
        assert folder_res.status_code == 200
        folder = folder_res.json()
        
        # Try to download empty folder
        response = requests.get(f"{BASE_URL}/api/folders/{folder['id']}/download", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 404, "Empty folder should return 404"
        print("✓ Empty folder ZIP download correctly returns 404")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/folders/{folder['id']}", 
            headers={"Authorization": f"Bearer {admin_token}"})


    # ========== FILE PREVIEW TESTS ==========
    
    def test_file_preview_image(self, admin_token, test_image_file):
        """Test GET /api/files/{file_id}/preview for images"""
        response = requests.get(f"{BASE_URL}/api/files/{test_image_file['id']}/preview", 
            headers={"Authorization": f"Bearer {admin_token}"})
        
        assert response.status_code == 200, f"Preview failed: {response.text}"
        assert "image/" in response.headers.get("Content-Type", "")
        assert len(response.content) > 0
        print(f"✓ Image preview works, received {len(response.content)} bytes")

    def test_file_preview_non_previewable(self, admin_token, test_file):
        """Test preview of non-previewable file returns 400"""
        response = requests.get(f"{BASE_URL}/api/files/{test_file['id']}/preview", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 400, "Non-previewable file should return 400"
        print("✓ Non-previewable file preview correctly returns 400")


    # ========== GET ALL FOLDERS API TEST ==========
    
    def test_get_all_folders(self, admin_token):
        """Test GET /api/folders/all endpoint for move dialog"""
        response = requests.get(f"{BASE_URL}/api/folders/all", 
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"storage_area": "personal"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get all folders works, found {len(data)} folders")


class TestEdgeCases:
    """Edge case tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if login_res.status_code != 200:
            pytest.skip("Admin login failed")
        return login_res.json()["token"]

    def test_move_nonexistent_file(self, admin_token):
        """Test moving non-existent file returns 404"""
        response = requests.put(f"{BASE_URL}/api/files/nonexistent-id/move", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"target_folder_path": "/"}
        )
        assert response.status_code == 404
        print("✓ Move non-existent file correctly returns 404")

    def test_download_nonexistent_folder(self, admin_token):
        """Test ZIP download of non-existent folder returns 404"""
        response = requests.get(f"{BASE_URL}/api/folders/nonexistent-id/download", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 404
        print("✓ Download non-existent folder correctly returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
