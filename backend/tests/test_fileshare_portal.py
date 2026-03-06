"""
FileShare Portal Backend Tests
Tests for: Authentication, Password Reset, User Management, Files, Folders, Shares
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://mqtt-monitor-hub.preview.emergentagent.com')


class TestHealthCheck:
    """Health check endpoint test"""
    
    def test_health_check(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("Health check passed")


class TestAuthentication:
    """Authentication flow tests"""
    
    def test_login_with_admin_credentials(self):
        """Test login with admin@test.com / password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == "admin@test.com"
        assert data["user"]["role"] == "admin"
        print(f"Admin login successful, user: {data['user']['name']}")
    
    def test_login_with_kunde_credentials(self):
        """Test login with kunde@test.com / password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "kunde@test.com",
            "password": "password"
        })
        assert response.status_code == 200, f"Kunde login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "kunde@test.com"
        print(f"Kunde login successful, user: {data['user']['name']}")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@test.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("Invalid login correctly rejected")
    
    def test_get_current_user(self):
        """Test /api/auth/me endpoint"""
        # First login
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert login_res.status_code == 200
        token = login_res.json()["token"]
        
        # Get current user
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@test.com"
        print(f"Current user endpoint working, user: {data['name']}")


class TestPasswordReset:
    """Password reset flow tests - MOCKED EMAIL SENDING"""
    
    def test_request_password_reset(self):
        """Test requesting password reset returns token (mocked)"""
        response = requests.post(f"{BASE_URL}/api/auth/request-password-reset", json={
            "email": "admin@test.com"
        })
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        # MOCKED: Token is returned in response for demo purposes
        assert "reset_token" in data
        print(f"Password reset requested, got token: {data['reset_token'][:10]}...")
    
    def test_verify_reset_token(self):
        """Test verifying a reset token"""
        # First request reset
        reset_res = requests.post(f"{BASE_URL}/api/auth/request-password-reset", json={
            "email": "admin@test.com"
        })
        assert reset_res.status_code == 200
        token = reset_res.json().get("reset_token")
        
        if token:
            # Verify token
            response = requests.get(f"{BASE_URL}/api/auth/verify-reset-token/{token}")
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] == True
            print("Reset token verified successfully")
    
    def test_verify_invalid_reset_token(self):
        """Test verifying invalid token returns 400"""
        response = requests.get(f"{BASE_URL}/api/auth/verify-reset-token/invalidtoken123")
        assert response.status_code == 400
        print("Invalid reset token correctly rejected")


class TestUserManagement:
    """Admin user management tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if login_res.status_code != 200:
            pytest.skip("Admin login failed")
        return login_res.json()["token"]
    
    def test_list_users(self, admin_token):
        """Test listing all users"""
        response = requests.get(f"{BASE_URL}/api/users", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} users")
    
    def test_create_and_delete_user(self, admin_token):
        """Test user creation and deletion"""
        test_email = f"TEST_user_{uuid.uuid4().hex[:8]}@test.com"
        
        # Create user
        create_res = requests.post(f"{BASE_URL}/api/users", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": test_email,
                "password": "testpass123",
                "name": "Test User",
                "role": "kunde"
            }
        )
        assert create_res.status_code == 200, f"Create failed: {create_res.text}"
        user_id = create_res.json()["id"]
        print(f"Created user: {test_email}")
        
        # Delete user
        delete_res = requests.delete(f"{BASE_URL}/api/users/{user_id}", 
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert delete_res.status_code == 200
        print(f"Deleted user: {test_email}")
    
    def test_update_user(self, admin_token):
        """Test user update including app permissions"""
        # Create test user
        test_email = f"TEST_update_{uuid.uuid4().hex[:8]}@test.com"
        create_res = requests.post(f"{BASE_URL}/api/users", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": test_email,
                "password": "testpass123",
                "name": "Original Name",
                "role": "kunde"
            }
        )
        assert create_res.status_code == 200
        user_id = create_res.json()["id"]
        
        # Update user with filesharing permissions
        update_res = requests.put(f"{BASE_URL}/api/users/{user_id}", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Updated Name",
                "apps": {
                    "filesharing": {
                        "enabled": True,
                        "max_upload_size_mb": 200,
                        "can_write": True,
                        "can_delete": False
                    }
                }
            }
        )
        assert update_res.status_code == 200
        data = update_res.json()
        assert data["name"] == "Updated Name"
        assert data["apps"]["filesharing"]["enabled"] == True
        print(f"Updated user with filesharing permissions")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/users/{user_id}", 
            headers={"Authorization": f"Bearer {admin_token}"})


class TestAdminPasswordManagement:
    """Admin password management tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if login_res.status_code != 200:
            pytest.skip("Admin login failed")
        return login_res.json()["token"]
    
    def test_admin_set_password(self, admin_token):
        """Test admin setting password for a user"""
        # First create a test user
        test_email = f"TEST_pw_{uuid.uuid4().hex[:8]}@test.com"
        create_res = requests.post(f"{BASE_URL}/api/users", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": test_email,
                "password": "initialpass",
                "name": "Password Test User",
                "role": "kunde"
            }
        )
        assert create_res.status_code == 200
        user_id = create_res.json()["id"]
        
        # Set new password
        response = requests.post(f"{BASE_URL}/api/admin/set-password", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "user_id": user_id,
                "new_password": "newpassword123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["password"] == "newpassword123"
        print("Admin set password successfully")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/users/{user_id}", 
            headers={"Authorization": f"Bearer {admin_token}"})
    
    def test_admin_generate_reset_link(self, admin_token):
        """Test admin generating reset link for a user"""
        # Get list of users first
        users_res = requests.get(f"{BASE_URL}/api/users", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert users_res.status_code == 200
        users = users_res.json()
        
        if len(users) > 0:
            user_id = users[0]["id"]
            response = requests.post(f"{BASE_URL}/api/admin/generate-reset-link/{user_id}", 
                headers={"Authorization": f"Bearer {admin_token}"})
            assert response.status_code == 200
            data = response.json()
            assert "reset_token" in data
            assert "expires_at" in data
            print(f"Generated reset link, token: {data['reset_token'][:10]}...")


class TestFolderOperations:
    """Folder CRUD operations tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if login_res.status_code != 200:
            pytest.skip("Admin login failed")
        return login_res.json()["token"]
    
    def test_create_folder_personal(self, admin_token):
        """Test creating folder in personal storage"""
        folder_name = f"TEST_folder_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(f"{BASE_URL}/api/folders", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": folder_name,
                "parent_path": "/",
                "storage_area": "personal"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == folder_name
        assert data["storage_area"] == "personal"
        print(f"Created personal folder: {folder_name}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/folders/{data['id']}", 
            headers={"Authorization": f"Bearer {admin_token}"})
    
    def test_create_folder_shared(self, admin_token):
        """Test creating folder in shared storage"""
        folder_name = f"TEST_shared_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(f"{BASE_URL}/api/folders", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": folder_name,
                "parent_path": "/",
                "storage_area": "shared"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == folder_name
        assert data["storage_area"] == "shared"
        print(f"Created shared folder: {folder_name}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/folders/{data['id']}", 
            headers={"Authorization": f"Bearer {admin_token}"})
    
    def test_list_folders(self, admin_token):
        """Test listing folders"""
        response = requests.get(f"{BASE_URL}/api/folders", 
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"path": "/", "storage_area": "personal"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"Listed {len(response.json())} folders")


class TestFileOperations:
    """File CRUD operations tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if login_res.status_code != 200:
            pytest.skip("Admin login failed")
        return login_res.json()["token"]
    
    def test_list_files(self, admin_token):
        """Test listing files"""
        response = requests.get(f"{BASE_URL}/api/files", 
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"folder_path": "/", "storage_area": "personal"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"Listed {len(response.json())} files")
    
    def test_upload_file(self, admin_token):
        """Test file upload"""
        files = {"file": ("TEST_testfile.txt", b"Test file content", "text/plain")}
        data = {"folder_path": "/", "storage_area": "personal"}
        
        response = requests.post(f"{BASE_URL}/api/files/upload", 
            headers={"Authorization": f"Bearer {admin_token}"},
            files=files,
            data=data
        )
        assert response.status_code == 200
        file_data = response.json()
        assert file_data["original_filename"] == "TEST_testfile.txt"
        print(f"Uploaded file: {file_data['original_filename']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/files/{file_data['id']}", 
            headers={"Authorization": f"Bearer {admin_token}"})


class TestShareOperations:
    """Share link operations tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if login_res.status_code != 200:
            pytest.skip("Admin login failed")
        return login_res.json()["token"]
    
    def test_list_shares(self, admin_token):
        """Test listing shares"""
        response = requests.get(f"{BASE_URL}/api/shares", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"Listed {len(response.json())} shares")
    
    def test_create_share_for_file(self, admin_token):
        """Test creating share link for a file"""
        # First upload a file
        files = {"file": ("TEST_sharefile.txt", b"Share test content", "text/plain")}
        data = {"folder_path": "/", "storage_area": "personal"}
        
        upload_res = requests.post(f"{BASE_URL}/api/files/upload", 
            headers={"Authorization": f"Bearer {admin_token}"},
            files=files,
            data=data
        )
        assert upload_res.status_code == 200
        file_id = upload_res.json()["id"]
        
        # Create share
        share_res = requests.post(f"{BASE_URL}/api/shares", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "file_id": file_id,
                "share_type": "file",
                "expires_in_days": 7,
                "allow_download": True,
                "allow_upload": False,
                "allow_edit": False
            }
        )
        assert share_res.status_code == 200
        share_data = share_res.json()
        assert "token" in share_data
        print(f"Created share link with token: {share_data['token']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/shares/{share_data['id']}", 
            headers={"Authorization": f"Bearer {admin_token}"})
        requests.delete(f"{BASE_URL}/api/files/{file_id}", 
            headers={"Authorization": f"Bearer {admin_token}"})


class TestStatistics:
    """Admin statistics tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if login_res.status_code != 200:
            pytest.skip("Admin login failed")
        return login_res.json()["token"]
    
    def test_get_stats(self, admin_token):
        """Test admin statistics endpoint"""
        response = requests.get(f"{BASE_URL}/api/stats", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "files" in data
        assert "shares" in data
        print(f"Stats: {data['users']} users, {data['files']} files, {data['shares']} shares")
    
    def test_get_users_with_files(self, admin_token):
        """Test admin users with files endpoint"""
        response = requests.get(f"{BASE_URL}/api/admin/users-with-files", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} users with file info")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
