"""
Test suite for Project Reports (Projektberichte) feature
Tests CRUD operations for project reports API endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "password"
TEST_ORDER_PK = "18"  # Known order from EpiRent API


class TestProjectReportsAPI:
    """Test Project Reports CRUD endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Get auth token and cleanup test data"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("token")
        assert token, "No token received"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Store created report IDs for cleanup
        self.created_report_ids = []
        
        yield
        
        # Cleanup: Delete test reports
        for report_id in self.created_report_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/project-reports/{report_id}")
            except:
                pass
    
    def test_create_project_report_minimal(self):
        """Test creating a project report with minimal data"""
        payload = {
            "order_pk": TEST_ORDER_PK,
            "order_name": "TEST_Order",
            "kunde_name": "TEST_Minimal Customer"
        }
        
        response = self.session.post(f"{BASE_URL}/api/project-reports", json=payload)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should contain id"
        assert data["order_pk"] == TEST_ORDER_PK
        assert data["kunde_name"] == "TEST_Minimal Customer"
        
        self.created_report_ids.append(data["id"])
        print(f"Created report with ID: {data['id']}")
    
    def test_create_project_report_full(self):
        """Test creating a project report with all fields"""
        payload = {
            "order_pk": TEST_ORDER_PK,
            "order_name": "TEST_Full Order",
            "anrede": "Firma",
            "kunde_name": "TEST_Full Customer GmbH",
            "kunde_anschrift": "Teststraße 123",
            "kunde_plz": "12345",
            "kunde_ort": "Teststadt",
            "kunde_telefon": "+49 123 456789",
            "kunde_ansprechpartner": "Herr Test",
            "projektnummer": "PROJ-2026-001",
            "projekt_datum": "2026-01-15",
            "kunde_nicht_anwesend": False,
            "mitarbeiter": [
                {"name": "Max Mustermann", "rolle": "PL"},
                {"name": "Hans Techniker", "rolle": "T"}
            ],
            "work_log": [
                {
                    "datum": "2026-01-15",
                    "beschreibung": "Installation der Anlage",
                    "stunden": {"0": {"N": 4, "E": 0, "NO": 0}, "1": {"N": 4, "E": 0, "NO": 0}}
                }
            ],
            "material": [
                {"pos": 1, "material": "Kabel 10m", "vorbereitung": "5", "verarbeitet": "5", "bestellung": ""}
            ],
            "fahrzeuge": [
                {"typ": "LKW", "km": 150, "stunden": 2}
            ],
            "bemerkungen": "Alles gut verlaufen",
            "uebernachtung_zeitraum": "15.01. - 16.01.",
            "uebernachtung_naechte": 1
        }
        
        response = self.session.post(f"{BASE_URL}/api/project-reports", json=payload)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        data = response.json()
        assert data["id"], "Should have ID"
        assert data["kunde_name"] == "TEST_Full Customer GmbH"
        assert data["kunde_plz"] == "12345"
        assert len(data["mitarbeiter"]) == 2
        assert data["mitarbeiter"][0]["name"] == "Max Mustermann"
        assert data["mitarbeiter"][0]["rolle"] == "PL"
        assert len(data["work_log"]) == 1
        assert data["work_log"][0]["beschreibung"] == "Installation der Anlage"
        assert len(data["material"]) == 1
        assert len(data["fahrzeuge"]) == 1
        assert data["fahrzeuge"][0]["km"] == 150
        assert data["bemerkungen"] == "Alles gut verlaufen"
        assert data["uebernachtung_naechte"] == 1
        
        self.created_report_ids.append(data["id"])
        print(f"Created full report with ID: {data['id']}")
    
    def test_get_reports_by_order(self):
        """Test fetching reports by order_pk"""
        # First create a report
        create_payload = {
            "order_pk": TEST_ORDER_PK,
            "order_name": "TEST_GetByOrder",
            "kunde_name": "TEST_GetByOrder Customer"
        }
        create_response = self.session.post(f"{BASE_URL}/api/project-reports", json=create_payload)
        assert create_response.status_code == 200
        created_id = create_response.json()["id"]
        self.created_report_ids.append(created_id)
        
        # Now fetch by order
        response = self.session.get(f"{BASE_URL}/api/project-reports/by-order/{TEST_ORDER_PK}")
        assert response.status_code == 200, f"Get by order failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        
        # Find our created report
        found = any(r["id"] == created_id for r in data)
        assert found, f"Created report {created_id} should be in the list"
        print(f"Found {len(data)} reports for order {TEST_ORDER_PK}")
    
    def test_get_single_report(self):
        """Test fetching a single report by ID"""
        # First create a report
        create_payload = {
            "order_pk": TEST_ORDER_PK,
            "order_name": "TEST_GetSingle",
            "kunde_name": "TEST_GetSingle Customer",
            "kunde_ort": "Berlin"
        }
        create_response = self.session.post(f"{BASE_URL}/api/project-reports", json=create_payload)
        assert create_response.status_code == 200
        created_id = create_response.json()["id"]
        self.created_report_ids.append(created_id)
        
        # Fetch single report
        response = self.session.get(f"{BASE_URL}/api/project-reports/{created_id}")
        assert response.status_code == 200, f"Get single failed: {response.text}"
        
        data = response.json()
        assert data["id"] == created_id
        assert data["kunde_name"] == "TEST_GetSingle Customer"
        assert data["kunde_ort"] == "Berlin"
        print(f"Successfully fetched report {created_id}")
    
    def test_get_nonexistent_report(self):
        """Test fetching a report that doesn't exist"""
        fake_id = str(uuid.uuid4())
        response = self.session.get(f"{BASE_URL}/api/project-reports/{fake_id}")
        assert response.status_code == 404, f"Should return 404, got {response.status_code}"
        print("Correctly returned 404 for nonexistent report")
    
    def test_update_report(self):
        """Test updating a project report"""
        # First create a report
        create_payload = {
            "order_pk": TEST_ORDER_PK,
            "order_name": "TEST_Update",
            "kunde_name": "TEST_Original Name",
            "kunde_ort": "Original City"
        }
        create_response = self.session.post(f"{BASE_URL}/api/project-reports", json=create_payload)
        assert create_response.status_code == 200
        created_id = create_response.json()["id"]
        self.created_report_ids.append(created_id)
        
        # Update the report
        update_payload = {
            "kunde_name": "TEST_Updated Name",
            "kunde_ort": "Updated City",
            "bemerkungen": "Updated remarks"
        }
        update_response = self.session.put(f"{BASE_URL}/api/project-reports/{created_id}", json=update_payload)
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        updated_data = update_response.json()
        assert updated_data["kunde_name"] == "TEST_Updated Name"
        assert updated_data["kunde_ort"] == "Updated City"
        assert updated_data["bemerkungen"] == "Updated remarks"
        
        # Verify with GET
        get_response = self.session.get(f"{BASE_URL}/api/project-reports/{created_id}")
        assert get_response.status_code == 200
        fetched_data = get_response.json()
        assert fetched_data["kunde_name"] == "TEST_Updated Name"
        assert fetched_data["kunde_ort"] == "Updated City"
        print(f"Successfully updated report {created_id}")
    
    def test_update_report_arrays(self):
        """Test updating array fields (mitarbeiter, work_log, etc.)"""
        # Create report with initial data
        create_payload = {
            "order_pk": TEST_ORDER_PK,
            "order_name": "TEST_UpdateArrays",
            "kunde_name": "TEST_Arrays Customer",
            "mitarbeiter": [{"name": "Initial Worker", "rolle": "T"}]
        }
        create_response = self.session.post(f"{BASE_URL}/api/project-reports", json=create_payload)
        assert create_response.status_code == 200
        created_id = create_response.json()["id"]
        self.created_report_ids.append(created_id)
        
        # Update with new array data
        update_payload = {
            "mitarbeiter": [
                {"name": "Worker 1", "rolle": "PL"},
                {"name": "Worker 2", "rolle": "ME"},
                {"name": "Worker 3", "rolle": "T"}
            ],
            "fahrzeuge": [
                {"typ": "PKW", "km": 100, "stunden": 1},
                {"typ": "LKW", "km": 200, "stunden": 3}
            ]
        }
        update_response = self.session.put(f"{BASE_URL}/api/project-reports/{created_id}", json=update_payload)
        assert update_response.status_code == 200
        
        updated_data = update_response.json()
        assert len(updated_data["mitarbeiter"]) == 3
        assert updated_data["mitarbeiter"][0]["name"] == "Worker 1"
        assert len(updated_data["fahrzeuge"]) == 2
        print(f"Successfully updated arrays in report {created_id}")
    
    def test_update_nonexistent_report(self):
        """Test updating a report that doesn't exist"""
        fake_id = str(uuid.uuid4())
        update_payload = {"kunde_name": "Should Fail"}
        response = self.session.put(f"{BASE_URL}/api/project-reports/{fake_id}", json=update_payload)
        assert response.status_code == 404, f"Should return 404, got {response.status_code}"
        print("Correctly returned 404 for updating nonexistent report")
    
    def test_delete_report(self):
        """Test deleting a project report"""
        # First create a report
        create_payload = {
            "order_pk": TEST_ORDER_PK,
            "order_name": "TEST_Delete",
            "kunde_name": "TEST_ToBeDeleted"
        }
        create_response = self.session.post(f"{BASE_URL}/api/project-reports", json=create_payload)
        assert create_response.status_code == 200
        created_id = create_response.json()["id"]
        
        # Delete the report
        delete_response = self.session.delete(f"{BASE_URL}/api/project-reports/{created_id}")
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        
        # Verify deletion with GET
        get_response = self.session.get(f"{BASE_URL}/api/project-reports/{created_id}")
        assert get_response.status_code == 404, "Deleted report should return 404"
        print(f"Successfully deleted report {created_id}")
    
    def test_delete_nonexistent_report(self):
        """Test deleting a report that doesn't exist"""
        fake_id = str(uuid.uuid4())
        response = self.session.delete(f"{BASE_URL}/api/project-reports/{fake_id}")
        assert response.status_code == 404, f"Should return 404, got {response.status_code}"
        print("Correctly returned 404 for deleting nonexistent report")
    
    def test_unauthorized_access(self):
        """Test that endpoints require authentication"""
        # Create a new session without auth
        unauth_session = requests.Session()
        unauth_session.headers.update({"Content-Type": "application/json"})
        
        # Try to access endpoints without token
        response = unauth_session.get(f"{BASE_URL}/api/project-reports/by-order/{TEST_ORDER_PK}")
        assert response.status_code in [401, 403], f"Should be unauthorized, got {response.status_code}"
        
        response = unauth_session.post(f"{BASE_URL}/api/project-reports", json={"order_pk": TEST_ORDER_PK})
        assert response.status_code in [401, 403], f"Should be unauthorized, got {response.status_code}"
        
        print("Correctly rejected unauthorized requests")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
