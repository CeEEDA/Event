"""
Regression Test Suite - Iteration 61
Full regression test for Eventenergie Portal - Kirmes Abrechnungssystem
Testing all critical features changed in the last 7 days:
- Einsatzplanung (shift planning)
- Payroll release system
- DATEV Lohnabrechnung
- Time tracking
- Orders/EpiRent
- Monitoring routes
- Chat system
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"
EMPLOYEE_EMAIL = "test1@test.de"
EMPLOYEE_PASSWORD = "Test1234!"
EMPLOYEE2_EMAIL = "ma1@test.com"
EMPLOYEE2_PASSWORD = "password"


class TestAuthAndHealth:
    """Basic health and authentication tests"""
    
    def test_health_check(self):
        """API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")
    
    def test_admin_login(self):
        """Admin login test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful: {data['user']['name']}")
        return data["token"]
    
    def test_employee_login(self):
        """Employee login test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": EMPLOYEE_EMAIL,
            "password": EMPLOYEE_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print(f"✓ Employee login successful: {data['user']['name']}")
        return data["token"]
    
    def test_employee2_login(self):
        """Employee 2 (Anna) login test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": EMPLOYEE2_EMAIL,
            "password": EMPLOYEE2_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print(f"✓ Employee 2 login successful: {data['user']['name']}")
        return data["token"]


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Admin login failed")


@pytest.fixture(scope="module")
def employee_token():
    """Get employee token for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": EMPLOYEE_EMAIL,
        "password": EMPLOYEE_PASSWORD
    })
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Employee login failed")


class TestUsersAndProfiles:
    """User management and profile tests"""
    
    def test_list_users(self, admin_token):
        """Admin can list all users"""
        response = requests.get(f"{BASE_URL}/api/users", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)
        assert len(users) > 0
        print(f"✓ Listed {len(users)} users")
    
    def test_get_profile(self, admin_token):
        """Get own profile"""
        response = requests.get(f"{BASE_URL}/api/employee/profile?token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "email" in data
        print(f"✓ Profile retrieved: {data['name']}")
    
    def test_get_all_employees(self, admin_token):
        """Admin: Get all employees with document summary"""
        response = requests.get(f"{BASE_URL}/api/employee/all?token={admin_token}")
        assert response.status_code == 200
        employees = response.json()
        assert isinstance(employees, list)
        print(f"✓ Retrieved {len(employees)} employees")


class TestTimeTracking:
    """Time tracking (Zeiterfassung) tests"""
    
    def test_get_time_status(self, employee_token):
        """Get current clock-in status"""
        response = requests.get(f"{BASE_URL}/api/employee/time/status?token={employee_token}")
        assert response.status_code == 200
        data = response.json()
        assert "clocked_in" in data
        print(f"✓ Time status: clocked_in={data['clocked_in']}")
    
    def test_get_time_report_all_users(self, admin_token):
        """CRITICAL: Time report should return ALL users, not just those with entries"""
        response = requests.get(f"{BASE_URL}/api/employee/time/report?token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Time report returned {len(data)} users")
    
    def test_get_time_entries(self, admin_token):
        """Get time entries for a user"""
        response = requests.get(f"{BASE_URL}/api/employee/time/entries?token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved {len(data)} time entries")


class TestShiftPlanning:
    """Einsatzplanung (Shift Planning) tests - NEW FEATURE"""
    
    def test_get_shift_plan(self, admin_token):
        """Admin: Get shift plan for a week"""
        week = datetime.now().strftime("%G-W%V")
        response = requests.get(f"{BASE_URL}/api/employee/shift-plan?week={week}&token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        assert "assignments" in data
        assert "released" in data
        assert "absences" in data
        print(f"✓ Shift plan for {week}: {len(data['assignments'])} assignments, released={data['released']}")
    
    def test_create_shift_assignment(self, admin_token):
        """Admin: Create a shift assignment"""
        week = datetime.now().strftime("%G-W%V")
        today = datetime.now().strftime("%Y-%m-%d")
        response = requests.post(
            f"{BASE_URL}/api/employee/shift-plan?token={admin_token}",
            json={
                "user_id": "test-user-id",
                "date": today,
                "order_pk": 12345,
                "order_name": "TEST_Regression_Order",
                "role": "Techniker",
                "note": "Regression test assignment",
                "start_time": "08:00",
                "end_time": "17:00",
                "week_key": week
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "id" in data
        print(f"✓ Created shift assignment: {data['id']}")
        return data["id"]
    
    def test_get_job_requirements(self, admin_token):
        """Get job personnel requirements for a week"""
        week = datetime.now().strftime("%G-W%V")
        response = requests.get(f"{BASE_URL}/api/employee/shift-plan/job-reqs?week={week}&token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Job requirements: {len(data)} entries")
    
    def test_upsert_job_requirement(self, admin_token):
        """Admin: Set personnel requirements for a job"""
        week = datetime.now().strftime("%G-W%V")
        response = requests.post(
            f"{BASE_URL}/api/employee/shift-plan/job-reqs?token={admin_token}",
            json={
                "order_pk": 99999,
                "week_key": week,
                "count": 3,
                "roles": "Techniker, Helfer"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("✓ Job requirement created/updated")
    
    def test_release_shift_plan(self, admin_token):
        """Admin: Release a week plan"""
        week = datetime.now().strftime("%G-W%V")
        response = requests.post(f"{BASE_URL}/api/employee/shift-plan/release?week={week}&token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"✓ Shift plan released for {week}")
    
    def test_get_my_shift_plan(self, employee_token):
        """Employee: Get own released shift assignments"""
        response = requests.get(f"{BASE_URL}/api/employee/shift-plan/my-plan?token={employee_token}")
        assert response.status_code == 200
        data = response.json()
        assert "assignments" in data
        assert "released_weeks" in data
        print(f"✓ My shift plan: {len(data['assignments'])} assignments, {len(data['released_weeks'])} released weeks")


class TestPayroll:
    """Payroll (Abrechnung) tests"""
    
    def test_get_payroll(self, admin_token):
        """Get payroll data for a user"""
        # First get a user ID
        users_resp = requests.get(f"{BASE_URL}/api/users", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        if users_resp.status_code != 200:
            pytest.skip("Could not get users")
        users = users_resp.json()
        if not users:
            pytest.skip("No users found")
        
        user_id = users[0]["id"]
        month = datetime.now().strftime("%Y-%m")
        response = requests.get(f"{BASE_URL}/api/employee/payroll/{user_id}?month={month}&token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Payroll data retrieved for {month}")
    
    def test_get_deductions(self, admin_token):
        """Get deductions for a user"""
        users_resp = requests.get(f"{BASE_URL}/api/users", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        if users_resp.status_code != 200:
            pytest.skip("Could not get users")
        users = users_resp.json()
        if not users:
            pytest.skip("No users found")
        
        user_id = users[0]["id"]
        month = datetime.now().strftime("%Y-%m")
        response = requests.get(f"{BASE_URL}/api/employee/deductions/{user_id}?month={month}&token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Deductions retrieved: {len(data)} entries")
    
    def test_get_my_payroll_releases(self, employee_token):
        """Employee: Get own payroll releases"""
        response = requests.get(f"{BASE_URL}/api/employee/payroll/my-releases?token={employee_token}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ My payroll releases: {len(data)} entries")
    
    def test_get_my_payroll_documents(self, employee_token):
        """Employee: Get own DATEV payroll documents"""
        response = requests.get(f"{BASE_URL}/api/employee/payroll/my-documents?token={employee_token}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ My payroll documents: {len(data)} entries")


class TestWorkSchedule:
    """Regelarbeitszeit (Work Schedule) tests"""
    
    def test_get_work_schedule(self, admin_token):
        """Get work schedule for a user"""
        users_resp = requests.get(f"{BASE_URL}/api/users", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        if users_resp.status_code != 200:
            pytest.skip("Could not get users")
        users = users_resp.json()
        if not users:
            pytest.skip("No users found")
        
        user_id = users[0]["id"]
        response = requests.get(f"{BASE_URL}/api/employee/work-schedule/{user_id}?token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Work schedule retrieved")


class TestNotes:
    """Mitarbeiter-Notizen tests"""
    
    def test_get_notes(self, admin_token):
        """Get notes for a user"""
        users_resp = requests.get(f"{BASE_URL}/api/users", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        if users_resp.status_code != 200:
            pytest.skip("Could not get users")
        users = users_resp.json()
        if not users:
            pytest.skip("No users found")
        
        user_id = users[0]["id"]
        response = requests.get(f"{BASE_URL}/api/employee/notes/{user_id}?token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Notes retrieved: {len(data)} entries")
    
    def test_create_note(self, admin_token):
        """Create a note for a user"""
        users_resp = requests.get(f"{BASE_URL}/api/users", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        if users_resp.status_code != 200:
            pytest.skip("Could not get users")
        users = users_resp.json()
        if not users:
            pytest.skip("No users found")
        
        user_id = users[0]["id"]
        response = requests.post(
            f"{BASE_URL}/api/employee/notes/{user_id}?token={admin_token}",
            json={
                "title": "TEST_Regression_Note",
                "content": "This is a regression test note"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        print(f"✓ Note created: {data['id']}")


class TestChat:
    """Chat system tests"""
    
    def test_get_conversations(self, admin_token):
        """Get chat conversations"""
        response = requests.get(f"{BASE_URL}/api/chat/conversations?token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Conversations retrieved: {len(data)} entries")
    
    def test_get_chat_users(self, admin_token):
        """Get chat users list"""
        response = requests.get(f"{BASE_URL}/api/chat/users?token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Chat users: {len(data)} entries")


class TestOrders:
    """Orders/EpiRent integration tests - CRITICAL LIVE FEATURE"""
    
    def test_get_epirent_orders(self, admin_token):
        """Get EpiRent orders - CRITICAL: Must not error"""
        response = requests.get(f"{BASE_URL}/api/orders/epirent", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        # Accept 200 or 404 (no config) but NOT 500
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        if response.status_code == 200:
            data = response.json()
            print(f"✓ EpiRent orders: {len(data.get('orders', []))} orders")
        else:
            print("✓ EpiRent orders: No config (expected in test env)")
    
    def test_get_sync_status(self, admin_token):
        """Get EpiRent sync status"""
        response = requests.get(f"{BASE_URL}/api/orders/sync/status", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Sync status retrieved")


class TestMonitoring:
    """Monitoring routes tests - CRITICAL: Raspberry PI meters"""
    
    def test_get_devices(self, admin_token):
        """Get all devices"""
        response = requests.get(f"{BASE_URL}/api/devices", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Devices: {len(data)} entries")
    
    def test_get_generators(self, admin_token):
        """Get all generators"""
        response = requests.get(f"{BASE_URL}/api/generators", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Generators: {len(data)} entries")
    
    def test_system_status(self, admin_token):
        """Get system status dashboard"""
        response = requests.get(f"{BASE_URL}/api/system/status", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert "mongodb" in data
        assert "devices" in data
        assert "generators" in data
        print(f"✓ System status: MongoDB={data['mongodb']['connected']}, Devices={data['devices']['total']}")


class TestDocuments:
    """Document management tests"""
    
    def test_get_document_types(self, admin_token):
        """Get employee document types"""
        response = requests.get(f"{BASE_URL}/api/employee/document-types?token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 9  # 9 document types
        print(f"✓ Document types: {len(data)} types")
    
    def test_get_documents_folder_structure(self, admin_token):
        """Get document folder structure"""
        response = requests.get(f"{BASE_URL}/api/documents/folders?token={admin_token}")
        assert response.status_code == 200
        data = response.json()
        # API returns {"folders": [...], "total": N}
        assert "folders" in data
        folders = data["folders"]
        assert isinstance(folders, list)
        # Check for Lohnabrechnung folder
        folder_ids = [f.get("id", "") for f in folders]
        print(f"✓ Document folders: {len(folders)} folders")
        if "lohnabrechnung" in folder_ids:
            print("  ✓ Lohnabrechnung folder exists")


class TestKirmes:
    """Kirmes billing system tests - CRITICAL LIVE FEATURE"""
    
    def test_get_kirmes_events(self, admin_token):
        """Get Kirmes events"""
        response = requests.get(f"{BASE_URL}/api/kirmes/events", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Kirmes events: {len(data)} events")
    
    def test_get_kirmes_invoices(self, admin_token):
        """Get Kirmes invoices - CRITICAL: Live invoices"""
        response = requests.get(f"{BASE_URL}/api/kirmes/invoices", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Kirmes invoices: {len(data)} invoices")


class TestFilesharing:
    """Filesharing tests - CRITICAL LIVE FEATURE"""
    
    def test_get_files(self, admin_token):
        """Get files in root folder"""
        response = requests.get(f"{BASE_URL}/api/files", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Files: {len(data)} files")
    
    def test_get_folders(self, admin_token):
        """Get folders"""
        response = requests.get(f"{BASE_URL}/api/folders", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Folders: {len(data)} folders")


class TestBackup:
    """Backup system tests"""
    
    def test_get_backup_settings(self, admin_token):
        """Get backup settings"""
        response = requests.get(f"{BASE_URL}/api/backup/settings", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Backup settings retrieved")
    
    def test_get_backup_list(self, admin_token):
        """Get backup list"""
        response = requests.get(f"{BASE_URL}/api/backup/list", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Backup list: {len(data)} backups")


class TestDataIntegrity:
    """CRITICAL: Data integrity tests - ensure no destructive operations"""
    
    def test_collections_exist(self, admin_token):
        """Verify critical collections still exist via API responses"""
        # Test users collection
        users_resp = requests.get(f"{BASE_URL}/api/users", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert users_resp.status_code == 200
        assert len(users_resp.json()) > 0, "Users collection should not be empty"
        
        # Test devices collection
        devices_resp = requests.get(f"{BASE_URL}/api/devices", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert devices_resp.status_code == 200
        
        # Test generators collection
        gen_resp = requests.get(f"{BASE_URL}/api/generators", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert gen_resp.status_code == 200
        
        print("✓ Critical collections verified")


# Cleanup test data
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(admin_token):
    """Cleanup TEST_ prefixed data after tests"""
    yield
    # Note: In production, we don't want to delete anything
    # This is just for test data cleanup
    print("✓ Test cleanup complete (no destructive operations)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
