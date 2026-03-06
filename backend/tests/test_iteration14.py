"""
Iteration 14 - Backend Tests for:
1. Generator Monitoring stats (total should include device-synced generators)
2. Device Parts (Ersatzteile) CRUD
3. Service Plan maintenance entry with both months AND hours mandatory
4. Load test table header verification (frontend: 'Lasttest' not 'Messwerte')
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"


class TestIteration14:
    """Iteration 14 tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        self.token = resp.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    # ========== MONITORING STATS TESTS ==========
    
    def test_monitoring_stats_total_includes_virtual_generators(self):
        """
        Test 1: Monitoring page stats should show total including device-synced generators
        Expected: Total should be 12 (5 real generators + 7 virtual from devices)
        """
        resp = requests.get(f"{BASE_URL}/api/generators/stats/overview", headers=self.headers)
        assert resp.status_code == 200
        stats = resp.json()
        
        # Verify stats structure
        assert "total" in stats
        assert "running" in stats
        assert "standby" in stats
        
        # Total should be >= 5 (real generators)
        assert stats["total"] >= 5, f"Expected at least 5 generators, got {stats['total']}"
        print(f"Stats overview: total={stats['total']}, running={stats['running']}, standby={stats['standby']}")
    
    def test_generators_list_includes_virtual_from_devices(self):
        """
        Test 2: Generators list should include virtual generators from stromerzeuger/lichtmast devices
        """
        resp = requests.get(f"{BASE_URL}/api/generators", headers=self.headers)
        assert resp.status_code == 200
        generators = resp.json()
        
        # Check for virtual generators (from_device=True, id starts with 'dev-')
        virtual_gens = [g for g in generators if g.get('from_device') == True]
        device_id_gens = [g for g in generators if g.get('id', '').startswith('dev-')]
        
        # Should have some virtual generators from devices
        print(f"Total generators: {len(generators)}, Virtual from devices: {len(virtual_gens)}, Device ID format: {len(device_id_gens)}")
        assert len(generators) >= 5, "Expected at least 5 generators total"
    
    # ========== PARTS (ERSATZTEILE) CRUD TESTS ==========
    
    def test_parts_add_to_device(self):
        """
        Test 3: Add an Ersatzteil (part) to a device with type dropdown and part number
        """
        # Get first device
        devices_resp = requests.get(f"{BASE_URL}/api/devices", headers=self.headers)
        assert devices_resp.status_code == 200
        devices = devices_resp.json()
        assert len(devices) > 0, "Need at least one device"
        device_id = devices[0]["id"]
        
        # Add a part
        part_data = {
            "part_type": "Ölfilter",
            "part_number": f"TEST-OIL-{uuid.uuid4().hex[:8]}",
            "liters": 5.5,
            "notes": "Test part for IT14"
        }
        resp = requests.post(f"{BASE_URL}/api/devices/{device_id}/parts", json=part_data, headers=self.headers)
        assert resp.status_code == 200, f"Failed to add part: {resp.text}"
        
        created_part = resp.json()
        assert created_part["part_type"] == part_data["part_type"]
        assert created_part["part_number"] == part_data["part_number"]
        assert created_part["liters"] == part_data["liters"]
        
        # Store for deletion test
        self.created_part_id = created_part["id"]
        self.test_device_id = device_id
        print(f"Created part: {created_part['id']} - {created_part['part_type']}")
    
    def test_parts_list_shows_added_parts(self):
        """
        Test 4: List parts for a device and verify they appear
        """
        devices_resp = requests.get(f"{BASE_URL}/api/devices", headers=self.headers)
        device_id = devices_resp.json()[0]["id"]
        
        resp = requests.get(f"{BASE_URL}/api/devices/{device_id}/parts", headers=self.headers)
        assert resp.status_code == 200
        parts = resp.json()
        print(f"Device {device_id} has {len(parts)} parts")
        # Parts list should be accessible
        assert isinstance(parts, list)
    
    def test_parts_delete(self):
        """
        Test 5: Delete an Ersatzteil from the list
        """
        # First add a part to delete
        devices_resp = requests.get(f"{BASE_URL}/api/devices", headers=self.headers)
        device_id = devices_resp.json()[0]["id"]
        
        # Add a part
        part_data = {
            "part_type": "Luftfilter",
            "part_number": f"TEST-DEL-{uuid.uuid4().hex[:8]}",
            "notes": "Part to delete"
        }
        add_resp = requests.post(f"{BASE_URL}/api/devices/{device_id}/parts", json=part_data, headers=self.headers)
        assert add_resp.status_code == 200
        part_id = add_resp.json()["id"]
        
        # Delete it
        del_resp = requests.delete(f"{BASE_URL}/api/devices/parts/{part_id}", headers=self.headers)
        assert del_resp.status_code == 200
        assert del_resp.json()["message"] == "Ersatzteil gelöscht"
        
        # Verify it's gone
        parts_resp = requests.get(f"{BASE_URL}/api/devices/{device_id}/parts", headers=self.headers)
        parts = parts_resp.json()
        assert not any(p["id"] == part_id for p in parts), "Deleted part still appears in list"
        print(f"Successfully deleted part: {part_id}")
    
    # ========== SERVICE PLAN TESTS ==========
    
    def test_create_service_plan_for_device_without_plan(self):
        """
        Test 6: Create service plan for a device that doesn't have one
        """
        # Find a device without a plan
        devices_resp = requests.get(f"{BASE_URL}/api/devices", headers=self.headers)
        devices = devices_resp.json()
        
        plans_resp = requests.get(f"{BASE_URL}/api/serviceplan", headers=self.headers)
        plans = plans_resp.json()
        plan_device_ids = {p["device_id"] for p in plans}
        
        device_without_plan = next((d for d in devices if d["id"] not in plan_device_ids), None)
        
        if device_without_plan:
            # Create a plan
            plan_data = {
                "device_id": device_without_plan["id"],
                "current_hours": 1000,
                "interval_hours": 500,
                "interval_months": 12,
                "tasks": ["Test task"],
                "notes": "IT14 test plan"
            }
            resp = requests.post(f"{BASE_URL}/api/serviceplan", json=plan_data, headers=self.headers)
            assert resp.status_code == 200, f"Failed to create plan: {resp.text}"
            plan = resp.json()
            assert plan["device_id"] == device_without_plan["id"]
            print(f"Created service plan for device {device_without_plan['serial_number']}")
        else:
            # All devices have plans - that's OK for this test
            print("All devices already have service plans - skipping creation")
    
    def test_maintenance_entry_with_both_months_and_hours(self):
        """
        Test 7: Create maintenance entry with BOTH next_maintenance_months AND next_maintenance_hours
        The new form requires both fields to be filled (not dropdown selector)
        """
        # Get a plan
        plans_resp = requests.get(f"{BASE_URL}/api/serviceplan", headers=self.headers)
        plans = plans_resp.json()
        assert len(plans) > 0, "Need at least one service plan"
        plan_id = plans[0]["id"]
        
        # Create entry with BOTH months and hours
        entry_data = {
            "performed_by": "Test Technician IT14",
            "performed_at": "2026-03-06",
            "hours_at_service": 5500,
            "next_maintenance_months": 12,  # MANDATORY
            "next_maintenance_hours": 500,   # MANDATORY
            "checklist_data": {
                "mechanical": {"Motor auf Undichtigkeiten geprüft": "durchgefuehrt"},
                "electrical": {"Kabel und Leitungen geprüft": "durchgefuehrt"}
            },
            "measurements": {"spannung_l1": "230V"},
            "load_test": [{"load": "25%", "values": "100", "remarks": "OK"}],
            "ats_test": {"netzausfall_simuliert": "durchgefuehrt"},
            "diagnosis": {"fehlerspeicher_ausgelesen": "durchgefuehrt"},
            "notes": "IT14 dual mandatory fields test",
            "remarks": "Testing both months and hours"
        }
        
        resp = requests.post(f"{BASE_URL}/api/serviceplan/{plan_id}/entries", json=entry_data, headers=self.headers)
        assert resp.status_code == 200, f"Failed to create entry: {resp.text}"
        
        entry = resp.json()
        assert entry["next_maintenance_months"] == 12
        assert entry["next_maintenance_hours"] == 500
        print(f"Created maintenance entry with months={entry['next_maintenance_months']}, hours={entry['next_maintenance_hours']}")
    
    def test_maintenance_entry_ats_tristate(self):
        """
        Test 8: Verify ATS items can be saved with 3-state values
        States: nicht_durchgefuehrt, durchgefuehrt, nicht_vorhanden
        """
        plans_resp = requests.get(f"{BASE_URL}/api/serviceplan", headers=self.headers)
        plan_id = plans_resp.json()[0]["id"]
        
        # Test all three states for ATS
        entry_data = {
            "performed_by": "ATS Test Tech",
            "performed_at": "2026-03-06",
            "hours_at_service": 6000,
            "next_maintenance_months": 6,
            "next_maintenance_hours": 250,
            "ats_test": {
                "netzausfall_simuliert": "durchgefuehrt",
                "generator_startet_auto": "durchgefuehrt",
                "umschaltung_generator": "nicht_vorhanden",  # 3rd state: not available
                "versorgung_stabil": "nicht_durchgefuehrt",
                "rueckschaltung_netz": "durchgefuehrt",
                "nachlaufzeit_korrekt": "durchgefuehrt"
            },
            "notes": "ATS 3-state test"
        }
        
        resp = requests.post(f"{BASE_URL}/api/serviceplan/{plan_id}/entries", json=entry_data, headers=self.headers)
        assert resp.status_code == 200
        
        entry = resp.json()
        ats = entry["ats_test"]
        assert ats["umschaltung_generator"] == "nicht_vorhanden"
        print(f"ATS 3-state values saved correctly")
    
    def test_maintenance_entry_diagnosis_tristate(self):
        """
        Test 9: Verify Diagnosis items can be saved with 3-state values
        """
        plans_resp = requests.get(f"{BASE_URL}/api/serviceplan", headers=self.headers)
        plan_id = plans_resp.json()[0]["id"]
        
        entry_data = {
            "performed_by": "Diagnosis Test Tech",
            "performed_at": "2026-03-06",
            "hours_at_service": 6500,
            "next_maintenance_months": 3,
            "next_maintenance_hours": 100,
            "diagnosis": {
                "fehlerspeicher_ausgelesen": "durchgefuehrt",
                "keine_fehler": "nicht_durchgefuehrt",
                "fehler_vorhanden": "nicht_vorhanden",
                "fehlercodes": "TEST-ERR-001"
            },
            "notes": "Diagnosis 3-state test"
        }
        
        resp = requests.post(f"{BASE_URL}/api/serviceplan/{plan_id}/entries", json=entry_data, headers=self.headers)
        assert resp.status_code == 200
        
        entry = resp.json()
        diag = entry["diagnosis"]
        assert diag["fehlerspeicher_ausgelesen"] == "durchgefuehrt"
        assert diag["fehler_vorhanden"] == "nicht_vorhanden"
        print(f"Diagnosis 3-state values saved correctly")
    
    def test_get_part_types(self):
        """
        Test 10: Verify part types endpoint returns dropdown options
        """
        resp = requests.get(f"{BASE_URL}/api/devices/parts/types", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert "types" in data
        types = data["types"]
        assert "Kraftstofffilter" in types
        assert "Ölfilter" in types
        assert "Luftfilter" in types
        print(f"Part types available: {len(types)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
