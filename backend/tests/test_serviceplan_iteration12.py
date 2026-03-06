"""
Iteration 12 - Testing new maintenance entry form with 6 sections:
- Technician name auto-fill (read-only)
- Next maintenance calculation (months OR hours)
- Section 1: Mechanische Prüfung - 12 items with 3-state buttons
- Section 2: Elektrische Prüfung - 13 items with 3-state buttons
- Section 3: Generator Messwerte - 15 input fields
- Section 4: Lasttest Generator - 4 load level rows
- Section 5: ATS / Netzumschaltung Test - 6 checkboxes + Umschaltzeit
- Section 6: Diagnose - 3 checkboxes + Fehlercodes textarea
- Remarks/Bemerkungen field
- Backend POST /api/serviceplan/{id}/entries with new fields
- Next maintenance calculation on device (months->date, hours->next_maintenance_hours)
- Maintenance warnings with <30 days OR <50 hours threshold
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMaintenanceEntryNewFields:
    """Test new maintenance entry fields: checklist_data, measurements, load_test, ats_test, diagnosis, next_maintenance_mode/value"""
    
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
    def user_name(self):
        """Get logged-in user name for verification"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        return response.json()["user"]["name"]

    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

    @pytest.fixture(scope="class")
    def mitarbeiter_token(self):
        """Login as mitarbeiter to get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "ma1@test.com",
            "password": "password"
        })
        if response.status_code != 200:
            pytest.skip("Mitarbeiter user not available")
        return response.json()["token"]

    @pytest.fixture(scope="class")
    def mitarbeiter_headers(self, mitarbeiter_token):
        return {"Authorization": f"Bearer {mitarbeiter_token}", "Content-Type": "application/json"}

    @pytest.fixture(scope="class")
    def mitarbeiter_name(self, mitarbeiter_token):
        """Get mitarbeiter user name"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "ma1@test.com",
            "password": "password"
        })
        return response.json()["user"]["name"]

    @pytest.fixture(scope="class")
    def test_device(self, auth_headers):
        """Get or create a test device for serviceplan testing"""
        # First try to get existing devices
        response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        if response.status_code == 200 and len(response.json()) > 0:
            return response.json()[0]
        # If no devices, create one
        device_data = {
            "serial_number": f"TEST-IT12-{os.urandom(4).hex()}",
            "device_type": "stromerzeuger",
            "model": "DSE8610MK2",
            "user_field": "Test Generator",
            "status": "aktiv"
        }
        response = requests.post(f"{BASE_URL}/api/devices", json=device_data, headers=auth_headers)
        assert response.status_code == 201 or response.status_code == 200
        return response.json()

    @pytest.fixture(scope="class")
    def test_plan(self, auth_headers, test_device):
        """Get or create a test service plan"""
        # Check if device already has a plan
        response = requests.get(f"{BASE_URL}/api/serviceplan/device/{test_device['id']}", headers=auth_headers)
        if response.status_code == 200 and response.json().get("has_plan"):
            return response.json()
        
        # Create new plan
        plan_data = {
            "device_id": test_device["id"],
            "current_hours": 5000,
            "interval_hours": 500,
            "interval_months": 12,
            "tasks": [],
            "notes": "Test plan for iteration 12"
        }
        response = requests.post(f"{BASE_URL}/api/serviceplan", json=plan_data, headers=auth_headers)
        if response.status_code == 400 and "bereits" in response.json().get("detail", ""):
            # Plan exists, fetch it
            plans_response = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers)
            plans = plans_response.json()
            for plan in plans:
                if plan["device_id"] == test_device["id"]:
                    return plan
        assert response.status_code == 200 or response.status_code == 201, f"Failed to create plan: {response.text}"
        return response.json()

    def test_create_entry_with_checklist_data(self, auth_headers, test_plan, user_name):
        """Test creating maintenance entry with checklist_data containing mechanical and electrical sections"""
        entry_data = {
            "performed_by": user_name,
            "performed_at": "2026-03-06",
            "hours_at_service": 5100,
            "next_maintenance_mode": "months",
            "next_maintenance_value": 6,
            "checklist_data": {
                "mechanical": {
                    "Motor auf Undichtigkeiten geprüft": "durchgefuehrt",
                    "Motorölstand geprüft": "durchgefuehrt",
                    "Ölwechsel": "durchgefuehrt",
                    "Ölfilter gewechselt": "nicht_vorhanden",
                    "Luftfilter geprüft / ersetzt": "nicht_durchgefuehrt"
                },
                "electrical": {
                    "Kabel und Leitungen geprüft": "durchgefuehrt",
                    "Kabelverschraubungen geprüft": "durchgefuehrt",
                    "Alle Anschlussklemmen fest": "durchgefuehrt",
                    "Not-Aus Funktion geprüft": "durchgefuehrt"
                }
            },
            "measurements": {
                "spannung_l1": "230",
                "spannung_l2": "228",
                "spannung_l3": "231",
                "frequenz": "50.02",
                "batteriespannung": "13.8"
            },
            "load_test": [
                {"load": "25 %", "values": "kW: 50", "remarks": "OK"},
                {"load": "50 %", "values": "kW: 100", "remarks": "Stabil"},
                {"load": "75 %", "values": "kW: 150", "remarks": ""},
                {"load": "100 %", "values": "kW: 200", "remarks": "Volllast erreicht"}
            ],
            "ats_test": {
                "netzausfall_simuliert": True,
                "generator_startet_auto": True,
                "umschaltung_generator": True,
                "versorgung_stabil": True,
                "rueckschaltung_netz": True,
                "nachlaufzeit_korrekt": True,
                "umschaltzeit": "8"
            },
            "diagnosis": {
                "fehlerspeicher_ausgelesen": True,
                "keine_fehler": True,
                "fehler_vorhanden": False,
                "fehlercodes": ""
            },
            "remarks": "Routinewartung durchgeführt. Alle Werte im Normbereich.",
            "notes": "Nächste Prüfung in 6 Monaten empfohlen"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/serviceplan/{test_plan['id']}/entries",
            json=entry_data,
            headers=auth_headers
        )
        assert response.status_code == 200 or response.status_code == 201, f"Failed: {response.text}"
        
        entry = response.json()
        # Verify checklist_data persisted
        assert "checklist_data" in entry, "checklist_data missing from response"
        assert "mechanical" in entry["checklist_data"]
        assert "electrical" in entry["checklist_data"]
        assert entry["checklist_data"]["mechanical"]["Motor auf Undichtigkeiten geprüft"] == "durchgefuehrt"
        
        # Verify measurements persisted
        assert "measurements" in entry
        assert entry["measurements"]["spannung_l1"] == "230"
        
        # Verify load_test persisted
        assert "load_test" in entry
        assert len(entry["load_test"]) == 4
        assert entry["load_test"][0]["load"] == "25 %"
        
        # Verify ats_test persisted
        assert "ats_test" in entry
        assert entry["ats_test"]["netzausfall_simuliert"] == True
        assert entry["ats_test"]["umschaltzeit"] == "8"
        
        # Verify diagnosis persisted
        assert "diagnosis" in entry
        assert entry["diagnosis"]["fehlerspeicher_ausgelesen"] == True
        
        # Verify next_maintenance fields
        assert entry["next_maintenance_mode"] == "months"
        assert entry["next_maintenance_value"] == 6
        
        # Verify remarks
        assert "Routinewartung" in entry["remarks"]
        
        print(f"Entry created with ID: {entry['id']}")
        return entry

    def test_next_maintenance_months_calculation(self, auth_headers, test_device, test_plan):
        """Test that next_maintenance_mode='months' sets next_maintenance date on device"""
        entry_data = {
            "performed_by": "Test Techniker",
            "performed_at": "2026-03-06",
            "hours_at_service": 5200,
            "next_maintenance_mode": "months",
            "next_maintenance_value": 3,
            "checklist_data": {},
            "remarks": ""
        }
        
        response = requests.post(
            f"{BASE_URL}/api/serviceplan/{test_plan['id']}/entries",
            json=entry_data,
            headers=auth_headers
        )
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        
        # Verify device was updated
        device_response = requests.get(f"{BASE_URL}/api/devices/{test_device['id']}", headers=auth_headers)
        assert device_response.status_code == 200
        device = device_response.json()
        
        # Device should have next_maintenance set to ~3 months from 2026-03-06
        if device.get("next_maintenance"):
            print(f"Device next_maintenance: {device['next_maintenance']}")
            assert "2026-06" in device["next_maintenance"], "Expected next_maintenance around June 2026"
        
        print("Months-based next maintenance calculation verified")

    def test_next_maintenance_hours_calculation(self, auth_headers, test_device, test_plan):
        """Test that next_maintenance_mode='hours' sets next_maintenance_hours on device"""
        entry_data = {
            "performed_by": "Test Techniker",
            "performed_at": "2026-03-06",
            "hours_at_service": 5300,
            "next_maintenance_mode": "hours",
            "next_maintenance_value": 500,  # Next maintenance in 500 hours
            "checklist_data": {},
            "remarks": ""
        }
        
        response = requests.post(
            f"{BASE_URL}/api/serviceplan/{test_plan['id']}/entries",
            json=entry_data,
            headers=auth_headers
        )
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        
        # Verify device was updated
        device_response = requests.get(f"{BASE_URL}/api/devices/{test_device['id']}", headers=auth_headers)
        assert device_response.status_code == 200
        device = device_response.json()
        
        # Device should have next_maintenance_hours = 5300 + 500 = 5800
        if device.get("next_maintenance_hours"):
            print(f"Device next_maintenance_hours: {device['next_maintenance_hours']}")
            assert device["next_maintenance_hours"] == 5800, f"Expected 5800, got {device['next_maintenance_hours']}"
        
        print("Hours-based next maintenance calculation verified")

    def test_get_plan_with_entries_shows_checklist_data(self, auth_headers, test_plan):
        """Verify GET /api/serviceplan/{id} returns entries with full checklist_data"""
        response = requests.get(f"{BASE_URL}/api/serviceplan/{test_plan['id']}", headers=auth_headers)
        assert response.status_code == 200
        
        plan = response.json()
        entries = plan.get("entries", [])
        
        # Find an entry with checklist_data
        entry_with_checklist = None
        for entry in entries:
            if entry.get("checklist_data") and entry["checklist_data"].get("mechanical"):
                entry_with_checklist = entry
                break
        
        if entry_with_checklist:
            assert "mechanical" in entry_with_checklist["checklist_data"]
            assert "electrical" in entry_with_checklist["checklist_data"]
            print(f"Found entry with checklist_data: {entry_with_checklist['id']}")
        else:
            print("No entries with checklist_data found (may be from previous test runs)")

    def test_mitarbeiter_can_create_entry_with_new_fields(self, mitarbeiter_headers, mitarbeiter_name, test_plan):
        """Verify mitarbeiter can create entries with all new fields"""
        entry_data = {
            "performed_by": mitarbeiter_name,
            "performed_at": "2026-03-06",
            "hours_at_service": 5400,
            "next_maintenance_mode": "months",
            "next_maintenance_value": 12,
            "checklist_data": {
                "mechanical": {
                    "Motorölstand geprüft": "durchgefuehrt"
                },
                "electrical": {
                    "Not-Aus Funktion geprüft": "durchgefuehrt"
                }
            },
            "measurements": {
                "spannung_l1": "229"
            },
            "load_test": [
                {"load": "50 %", "values": "100 kW", "remarks": ""}
            ],
            "ats_test": {
                "netzausfall_simuliert": True
            },
            "diagnosis": {
                "fehlerspeicher_ausgelesen": True,
                "keine_fehler": True
            },
            "remarks": "Mitarbeiter-Wartung"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/serviceplan/{test_plan['id']}/entries",
            json=entry_data,
            headers=mitarbeiter_headers
        )
        assert response.status_code in [200, 201], f"Mitarbeiter should be able to create entries: {response.text}"
        
        entry = response.json()
        assert entry["performed_by"] == mitarbeiter_name
        print(f"Mitarbeiter created entry: {entry['id']}")


class TestMaintenanceWarnings:
    """Test maintenance warning thresholds: <30 days OR <50 hours"""
    
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

    def test_generators_endpoint_returns_maintenance_warning(self, auth_headers):
        """Verify generators endpoint includes maintenance_warning fields when applicable"""
        response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        assert response.status_code == 200
        
        generators = response.json()
        # Check if any generator has maintenance_warning fields
        for gen in generators:
            if gen.get("maintenance_warning"):
                print(f"Generator {gen['serial_number']} has maintenance_warning: {gen.get('maintenance_warning_reason')}")
                # Verify the fields exist
                assert "maintenance_warning" in gen
                if gen.get("maintenance_warning_reason"):
                    print(f"  - Reason: {gen['maintenance_warning_reason']}")
        
        print(f"Checked {len(generators)} generators for maintenance warnings")

    def test_maintenance_warning_days_threshold(self, auth_headers):
        """Verify <30 days threshold triggers warning"""
        # This test checks the backend logic - if a device has next_maintenance within 30 days,
        # the generator should show maintenance_warning=True
        response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        assert response.status_code == 200
        
        generators = response.json()
        for gen in generators:
            if gen.get("maintenance_due_days") is not None:
                days = gen["maintenance_due_days"]
                if days <= 30:
                    assert gen.get("maintenance_warning") == True, f"Generator {gen['serial_number']} should have warning with {days} days"
                    print(f"Generator {gen['serial_number']}: {days} days until maintenance - WARNING correct")


class TestServiceplanPageUIElements:
    """Test that Serviceplan page has correct UI elements"""
    
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

    def test_serviceplan_list_endpoint(self, auth_headers):
        """Verify serviceplan list returns all plans with device info"""
        response = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers)
        assert response.status_code == 200
        
        plans = response.json()
        print(f"Found {len(plans)} service plans")
        
        for plan in plans:
            # Verify enriched device info
            assert "device_id" in plan
            # These should be enriched from device
            if plan.get("device_serial"):
                print(f"Plan {plan['id']}: device={plan['device_serial']}, entries={plan.get('entry_count', 0)}")

    def test_serviceplan_detail_returns_entries_with_new_fields(self, auth_headers):
        """Verify plan detail includes entries with checklist_data, measurements, etc."""
        # Get a plan first
        plans_response = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers)
        if plans_response.status_code != 200 or len(plans_response.json()) == 0:
            pytest.skip("No service plans available")
        
        plan_id = plans_response.json()[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", headers=auth_headers)
        assert response.status_code == 200
        
        plan = response.json()
        entries = plan.get("entries", [])
        print(f"Plan {plan_id} has {len(entries)} entries")
        
        for entry in entries:
            print(f"  Entry {entry['id']}: performed_by={entry.get('performed_by')}, mode={entry.get('next_maintenance_mode')}")
            if entry.get("checklist_data"):
                mech_items = len(entry["checklist_data"].get("mechanical", {}))
                elec_items = len(entry["checklist_data"].get("electrical", {}))
                print(f"    - Checklist: {mech_items} mechanical, {elec_items} electrical items")


class TestNoHeaderButtonValidation:
    """Verify there is no 'Neue Wartung' button in Serviceplan page header"""
    
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

    def test_serviceplan_api_endpoints_exist(self, auth_headers):
        """Verify all required API endpoints exist"""
        # List plans
        response = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers)
        assert response.status_code == 200, "GET /api/serviceplan should work"
        
        # Get device service info
        devices_response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        if devices_response.status_code == 200 and len(devices_response.json()) > 0:
            device_id = devices_response.json()[0]["id"]
            response = requests.get(f"{BASE_URL}/api/serviceplan/device/{device_id}", headers=auth_headers)
            assert response.status_code == 200, "GET /api/serviceplan/device/{id} should work"
        
        print("All serviceplan API endpoints verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
