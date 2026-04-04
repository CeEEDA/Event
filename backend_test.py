import requests
import sys
import json
import io
from datetime import datetime

class FileShareAPITester:
    def __init__(self, base_url="https://vendor-portal-dev-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.admin_token = None
        self.user_token = None
        self.created_user_id = None
        self.created_user_email = None
        self.created_file_id = None
        self.created_share_id = None
        self.tests_run = 0
        self.tests_passed = 0

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
    def run_api_test(self, name, method, endpoint, expected_status, data=None, files=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        default_headers = {'Content-Type': 'application/json'}
        
        if headers:
            default_headers.update(headers)
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=default_headers)
            elif method == 'POST':
                if files:
                    # Remove Content-Type for multipart/form-data
                    del default_headers['Content-Type']
                    response = requests.post(url, files=files, data=data, headers=default_headers)
                else:
                    response = requests.post(url, json=data, headers=default_headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=default_headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=default_headers)

            success = response.status_code == expected_status
            
            if success:
                try:
                    response_data = response.json()
                    self.log_test(name, True)
                    return True, response_data
                except:
                    self.log_test(name, True)
                    return True, {}
            else:
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', f'Status: {response.status_code}')
                except:
                    error_detail = f'Status: {response.status_code}'
                    
                self.log_test(name, False, error_detail)
                return False, {}

        except Exception as e:
            self.log_test(name, False, str(e))
            return False, {}

    def test_health_check(self):
        """Test health endpoint"""
        return self.run_api_test("Health Check", "GET", "health", 200)

    def test_admin_login(self):
        """Login as admin user"""
        success, response = self.run_api_test(
            "Admin Login",
            "POST", 
            "auth/login",
            200,
            data={"email": "admin@eventenergie.de", "password": "admin123"}
        )
        
        if success and 'token' in response:
            self.admin_token = response['token']
            print(f"   Admin token received")
            return True
        return False

    def test_user_registration(self):
        """Test user registration"""
        timestamp = datetime.now().strftime('%H%M%S')
        success, response = self.run_api_test(
            "User Registration",
            "POST",
            "auth/register", 
            200,
            data={
                "email": f"test{timestamp}@eventenergie.de",
                "password": "test123456",
                "name": "Test Benutzer",
                "role": "kunde"
            }
        )
        
        if success and 'token' in response:
            self.user_token = response['token']
            print(f"   User token received")
            return True
        return False

    def test_protected_me_endpoint(self):
        """Test /auth/me endpoint with token"""
        if not self.user_token:
            self.log_test("Auth Me Endpoint", False, "No user token available")
            return False
            
        headers = {'Authorization': f'Bearer {self.user_token}'}
        return self.run_api_test("Auth Me Endpoint", "GET", "auth/me", 200, headers=headers)[0]

    def test_admin_user_list(self):
        """Test admin user list"""
        if not self.admin_token:
            self.log_test("Admin User List", False, "No admin token available")
            return False
            
        headers = {'Authorization': f'Bearer {self.admin_token}'}
        return self.run_api_test("Admin User List", "GET", "users", 200, headers=headers)[0]

    def test_admin_create_user(self):
        """Test admin creating new user"""
        if not self.admin_token:
            self.log_test("Admin Create User", False, "No admin token available")
            return False
            
        timestamp = datetime.now().strftime('%H%M%S')
        self.created_user_email = f"newuser{timestamp}@eventenergie.de"
        headers = {'Authorization': f'Bearer {self.admin_token}'}
        success, response = self.run_api_test(
            "Admin Create User",
            "POST",
            "users",
            200,
            data={
                "email": self.created_user_email,
                "password": "newuser123",
                "name": "Neuer Benutzer",
                "role": "mitarbeiter"
            },
            headers=headers
        )
        
        if success and 'id' in response:
            self.created_user_id = response['id']
            return True
        return False
    
    def test_admin_enable_fileshare(self):
        """Test admin enabling FileShare for user"""
        if not self.admin_token or not self.created_user_id:
            self.log_test("Enable FileShare", False, "No admin token or user ID available")
            return False
            
        headers = {'Authorization': f'Bearer {self.admin_token}'}
        success, response = self.run_api_test(
            "Enable FileShare",
            "PUT",
            f"users/{self.created_user_id}",
            200,
            data={
                "apps": {
                    "filesharing": {
                        "enabled": True,
                        "max_upload_size_mb": 100,
                        "can_write": True,
                        "can_delete": True
                    }
                }
            },
            headers=headers
        )
        
        if success:
            print(f"   FileShare enabled for user {self.created_user_id}")
            return True
        return False
    
    def test_user_with_fileshare_login(self):
        """Login as user with FileShare enabled"""
        if not self.created_user_email:
            self.log_test("User with FileShare Login", False, "No created user email available")
            return False
            
        success, response = self.run_api_test(
            "User with FileShare Login",
            "POST", 
            "auth/login",
            200,
            data={"email": self.created_user_email, "password": "newuser123"}
        )
        
        if success and 'token' in response:
            self.user_token = response['token']  # Update token to user with FileShare
            print(f"   FileShare user token received")
            return True
        return False

    def test_file_upload(self):
        """Test file upload"""
        if not self.user_token:
            self.log_test("File Upload", False, "No user token available")
            return False
            
        # Create a test file
        test_content = b"This is a test file for FileShare application"
        test_file = io.BytesIO(test_content)
        
        headers = {'Authorization': f'Bearer {self.user_token}'}
        files = {'file': ('test.txt', test_file, 'text/plain')}
        data = {'folder_path': '/'}
        
        success, response = self.run_api_test(
            "File Upload",
            "POST",
            "files/upload",
            200,
            data=data,
            files=files,
            headers=headers
        )
        
        if success and 'id' in response:
            self.created_file_id = response['id']
            return True
        return False

    def test_file_list(self):
        """Test file listing"""
        if not self.user_token:
            self.log_test("File List", False, "No user token available")
            return False
            
        headers = {'Authorization': f'Bearer {self.user_token}'}
        return self.run_api_test("File List", "GET", "files?folder_path=/", 200, headers=headers)[0]

    def test_create_share_link(self):
        """Test creating share link with permissions"""
        if not self.user_token or not self.created_file_id:
            self.log_test("Create Share Link", False, "No user token or file ID available")
            return False
            
        headers = {'Authorization': f'Bearer {self.user_token}'}
        success, response = self.run_api_test(
            "Create Share Link",
            "POST",
            "shares",
            200,
            data={
                "file_id": self.created_file_id,
                "expires_in_days": 7,
                "allow_download": True,
                "allow_upload": False,  # File share doesn't allow upload
                "allow_edit": False     # Test edit permission
            },
            headers=headers
        )
        
        if success and 'token' in response:
            self.created_share_id = response['id']
            self.share_token = response['token']
            print(f"   Share token: {self.share_token}")
            return True
        return False
    
    def test_folder_share_permissions(self):
        """Test folder sharing with Upload and Edit permissions"""
        if not self.user_token:
            self.log_test("Folder Share Permissions", False, "No user token available")
            return False
            
        headers = {'Authorization': f'Bearer {self.user_token}'}
        
        # First create a folder
        folder_success, folder_response = self.run_api_test(
            "Create Test Folder for Share",
            "POST",
            "folders",
            200,
            data={"name": "ShareTestFolder", "parent_path": "/"},
            headers=headers
        )
        
        if not folder_success or 'id' not in folder_response:
            return False
            
        folder_id = folder_response['id']
        
        # Create folder share with all permissions
        success, response = self.run_api_test(
            "Folder Share Permissions",
            "POST",
            "shares",
            200,
            data={
                "folder_id": folder_id,
                "share_type": "folder",
                "expires_in_days": 7,
                "allow_download": True,
                "allow_upload": True,   # Test upload permission
                "allow_edit": True      # Test edit permission
            },
            headers=headers
        )
        
        if success and 'token' in response:
            print(f"   Folder share token: {response['token']}")
            return True
        return False

    def test_share_list(self):
        """Test listing shares"""
        if not self.user_token:
            self.log_test("Share List", False, "No user token available")
            return False
            
        headers = {'Authorization': f'Bearer {self.user_token}'}
        return self.run_api_test("Share List", "GET", "shares", 200, headers=headers)[0]

    def test_public_share_info(self):
        """Test public share info (no auth required)"""
        if not hasattr(self, 'share_token'):
            self.log_test("Public Share Info", False, "No share token available")
            return False
            
        return self.run_api_test("Public Share Info", "GET", f"public/share/{self.share_token}", 200)[0]

    def test_admin_stats(self):
        """Test admin statistics"""
        if not self.admin_token:
            self.log_test("Admin Stats", False, "No admin token available")
            return False
            
        headers = {'Authorization': f'Bearer {self.admin_token}'}
        return self.run_api_test("Admin Stats", "GET", "stats", 200, headers=headers)[0]

    def test_folder_operations(self):
        """Test folder creation and listing"""
        if not self.user_token:
            self.log_test("Folder Operations", False, "No user token available")
            return False
            
        headers = {'Authorization': f'Bearer {self.user_token}'}
        
        # Create folder
        success, response = self.run_api_test(
            "Create Folder",
            "POST",
            "folders",
            200,
            data={"name": "TestFolder", "parent_path": "/"},
            headers=headers
        )
        
        if not success:
            return False
            
        # List folders  
        return self.run_api_test("List Folders", "GET", "folders?path=/", 200, headers=headers)[0]

def main():
    print("🚀 Starting FileShare API Tests...")
    print("=" * 50)
    
    tester = FileShareAPITester()
    
    # Run tests in order
    tests = [
        ("Health Check", tester.test_health_check),
        ("Admin Login", tester.test_admin_login),
        ("User Registration", tester.test_user_registration), 
        ("Auth Me Endpoint", tester.test_protected_me_endpoint),
        ("Admin User List", tester.test_admin_user_list),
        ("Admin Create User", tester.test_admin_create_user),
        ("Enable FileShare", tester.test_admin_enable_fileshare),
        ("User with FileShare Login", tester.test_user_with_fileshare_login),
        ("File Upload", tester.test_file_upload),
        ("File List", tester.test_file_list),
        ("Folder Operations", tester.test_folder_operations),
        ("Create Share Link", tester.test_create_share_link),
        ("Folder Share Permissions", tester.test_folder_share_permissions),
        ("Share List", tester.test_share_list),
        ("Public Share Info", tester.test_public_share_info),
        ("Admin Stats", tester.test_admin_stats),
    ]
    
    print(f"\nRunning {len(tests)} API tests...\n")
    
    for test_name, test_func in tests:
        test_func()
        
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All backend API tests passed!")
        return 0
    else:
        failed_count = tester.tests_run - tester.tests_passed
        print(f"❌ {failed_count} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())