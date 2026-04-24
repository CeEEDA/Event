"""
Test suite for Backup System API endpoints.
Tests: GET/POST settings, list backups, trigger backups, delete backup, download backup.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://kirmeskiste-sync.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"


class TestBackupSystemAPI:
    """Backup System API tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Auth headers for requests"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    # ───────────── GET /api/backup/settings ─────────────
    def test_get_backup_settings(self, auth_headers):
        """GET /api/backup/settings - should return backup settings"""
        response = requests.get(f"{BASE_URL}/api/backup/settings", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify settings structure
        assert "db_backup_enabled" in data, "Missing db_backup_enabled field"
        assert "db_backup_interval_hours" in data, "Missing db_backup_interval_hours field"
        assert "files_backup_enabled" in data, "Missing files_backup_enabled field"
        assert "files_backup_interval_hours" in data, "Missing files_backup_interval_hours field"
        assert "retention_days" in data, "Missing retention_days field"
        
        # Verify data types
        assert isinstance(data["db_backup_enabled"], bool)
        assert isinstance(data["db_backup_interval_hours"], int)
        assert isinstance(data["files_backup_enabled"], bool)
        assert isinstance(data["files_backup_interval_hours"], int)
        assert isinstance(data["retention_days"], int)
        
        print(f"✓ GET /api/backup/settings: {data}")
    
    # ───────────── POST /api/backup/settings ─────────────
    def test_post_backup_settings(self, auth_headers):
        """POST /api/backup/settings - should save new backup settings"""
        new_settings = {
            "db_backup_enabled": True,
            "db_backup_interval_hours": 24,
            "files_backup_enabled": True,
            "files_backup_interval_hours": 48,
            "retention_days": 14
        }
        
        response = requests.post(f"{BASE_URL}/api/backup/settings", 
                                 json=new_settings, 
                                 headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify settings were saved
        assert data["db_backup_enabled"] == True
        assert data["db_backup_interval_hours"] == 24
        assert data["files_backup_enabled"] == True
        assert data["files_backup_interval_hours"] == 48
        assert data["retention_days"] == 14
        assert "message" in data
        
        print(f"✓ POST /api/backup/settings: Settings saved successfully")
        
        # Verify persistence by GET
        get_response = requests.get(f"{BASE_URL}/api/backup/settings", headers=auth_headers)
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["db_backup_interval_hours"] == 24
        assert get_data["files_backup_interval_hours"] == 48
        assert get_data["retention_days"] == 14
        
        print(f"✓ Settings persisted correctly")
    
    # ───────────── GET /api/backup/list ─────────────
    def test_list_backups(self, auth_headers):
        """GET /api/backup/list - should return list of existing backups"""
        response = requests.get(f"{BASE_URL}/api/backup/list", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of backups"
        
        if len(data) > 0:
            backup = data[0]
            # Verify backup structure
            assert "id" in backup, "Missing id field"
            assert "type" in backup, "Missing type field"
            assert "file_path" in backup, "Missing file_path field"
            assert "file_name" in backup, "Missing file_name field"
            assert "file_size" in backup, "Missing file_size field"
            assert "status" in backup, "Missing status field"
            assert "trigger" in backup, "Missing trigger field"
            assert "created_at" in backup, "Missing created_at field"
            assert "file_exists" in backup, "Missing file_exists field"
            
            # Verify type values
            assert backup["type"] in ["database", "files"], f"Invalid type: {backup['type']}"
            assert backup["trigger"] in ["manual", "auto"], f"Invalid trigger: {backup['trigger']}"
            
            print(f"✓ GET /api/backup/list: Found {len(data)} backup(s)")
            for b in data[:3]:  # Print first 3
                print(f"  - {b['type']}: {b['file_name']} ({b['file_size']} bytes, trigger={b['trigger']})")
        else:
            print(f"✓ GET /api/backup/list: No backups yet (empty list)")
    
    # ───────────── POST /api/backup/trigger/db ─────────────
    def test_trigger_db_backup(self, auth_headers):
        """POST /api/backup/trigger/db - should create a MongoDB backup"""
        response = requests.post(f"{BASE_URL}/api/backup/trigger/db", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Backup should succeed: {data}"
        assert "backup" in data, "Missing backup field in response"
        
        backup = data["backup"]
        assert backup["type"] == "database"
        assert backup["status"] == "success"
        assert backup["trigger"] == "manual"
        assert backup["file_size"] > 0, "Backup file should have size > 0"
        assert ".gz" in backup["file_name"], "DB backup should be gzipped"
        
        print(f"✓ POST /api/backup/trigger/db: Created {backup['file_name']} ({backup['file_size']} bytes)")
        
        return backup["id"]
    
    # ───────────── POST /api/backup/trigger/files ─────────────
    def test_trigger_files_backup(self, auth_headers):
        """POST /api/backup/trigger/files - should create a source code ZIP"""
        response = requests.post(f"{BASE_URL}/api/backup/trigger/files", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Backup should succeed: {data}"
        assert "backup" in data, "Missing backup field in response"
        
        backup = data["backup"]
        assert backup["type"] == "files"
        assert backup["status"] == "success"
        assert backup["trigger"] == "manual"
        assert backup["file_size"] > 0, "Backup file should have size > 0"
        assert ".zip" in backup["file_name"], "Files backup should be a ZIP"
        
        print(f"✓ POST /api/backup/trigger/files: Created {backup['file_name']} ({backup['file_size']} bytes)")
        
        return backup["id"]
    
    # ───────────── GET /api/backup/{backup_id}/download ─────────────
    def test_download_backup(self, auth_headers):
        """GET /api/backup/{backup_id}/download - should download a backup file"""
        # First get a backup id
        list_response = requests.get(f"{BASE_URL}/api/backup/list", headers=auth_headers)
        assert list_response.status_code == 200
        
        backups = list_response.json()
        if not backups:
            pytest.skip("No backups available for download test")
        
        # Find one that exists on disk
        backup = None
        for b in backups:
            if b.get("file_exists"):
                backup = b
                break
        
        if not backup:
            pytest.skip("No backup files exist on disk")
        
        backup_id = backup["id"]
        
        # Try to download
        response = requests.get(f"{BASE_URL}/api/backup/{backup_id}/download", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify content-disposition header
        content_disp = response.headers.get("content-disposition", "")
        assert "filename" in content_disp, "Should have filename in content-disposition"
        
        # Verify content type
        content_type = response.headers.get("content-type", "")
        assert content_type in ["application/zip", "application/gzip", "application/octet-stream"], \
            f"Unexpected content type: {content_type}"
        
        # Verify we got some content
        assert len(response.content) > 0, "Downloaded file should have content"
        
        print(f"✓ GET /api/backup/{backup_id}/download: Downloaded {len(response.content)} bytes")
    
    # ───────────── DELETE /api/backup/{backup_id} ─────────────
    def test_delete_backup(self, auth_headers):
        """DELETE /api/backup/{backup_id} - should delete a backup from DB and disk"""
        # First create a backup specifically for deletion
        create_response = requests.post(f"{BASE_URL}/api/backup/trigger/db", headers=auth_headers)
        assert create_response.status_code == 200
        
        backup_id = create_response.json()["backup"]["id"]
        
        # Now delete it
        response = requests.delete(f"{BASE_URL}/api/backup/{backup_id}", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Should have message field"
        
        print(f"✓ DELETE /api/backup/{backup_id}: {data['message']}")
        
        # Verify it's gone from the list
        list_response = requests.get(f"{BASE_URL}/api/backup/list", headers=auth_headers)
        assert list_response.status_code == 200
        
        backup_ids = [b["id"] for b in list_response.json()]
        assert backup_id not in backup_ids, "Deleted backup should not appear in list"
        
        print(f"✓ Verified backup {backup_id} no longer in list")
    
    # ───────────── DELETE non-existent backup ─────────────
    def test_delete_nonexistent_backup(self, auth_headers):
        """DELETE /api/backup/nonexistent - should return 404"""
        response = requests.delete(f"{BASE_URL}/api/backup/nonexistent-id-12345", headers=auth_headers)
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ DELETE non-existent backup returns 404")
    
    # ───────────── Reset settings to defaults ─────────────
    def test_reset_settings_to_defaults(self, auth_headers):
        """Reset settings to reasonable defaults after testing"""
        default_settings = {
            "db_backup_enabled": True,
            "db_backup_interval_hours": 12,
            "files_backup_enabled": True,
            "files_backup_interval_hours": 72,
            "retention_days": 7
        }
        
        response = requests.post(f"{BASE_URL}/api/backup/settings", 
                                 json=default_settings, 
                                 headers=auth_headers)
        
        assert response.status_code == 200
        print(f"✓ Reset backup settings to defaults")


# Run tests standalone
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
