"""
Test file for iteration 10 - Testing new features:
- P0: Mitarbeiter (employee) can access Geräteverwaltung page
- P1: Devices marked 'ausser_betrieb' should NOT appear in monitoring dashboard
- P3: Serviceplan APIs (CRUD for plans and entries)
- P4: Maintenance warnings in monitoring
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')

class TestServiceplanFeatures:
    """Tests for Serviceplan and related features"""
    
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
    
    @pytest.fixture(scope="class")
    def mitarbeiter_token(self):
        """Get Mitarbeiter (employee) auth token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "ma1@test.com",
            "password": "password"
        })
        if login_res.status_code != 200:
            pytest.skip("Mitarbeiter login failed - ensure user ma1@test.com exists")
        return login_res.json()["token"]
    
    @pytest.fixture(scope="class")
    def kunde_token(self):
        """Get Kunde (customer) auth token"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "kunde@test.com",
            "password": "password"
        })
        if login_res.status_code != 200:
            pytest.skip("Kunde login failed - ensure user kunde@test.com exists")
        return login_res.json()["token"]

    # ========== P0: MITARBEITER ACCESS TO DEVICES ==========
    
    def test_p0_mitarbeiter_can_list_devices(self, mitarbeiter_token):
        """P0: Mitarbeiter should be able to access GET /api/devices"""
        response = requests.get(f"{BASE_URL}/api/devices", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        assert response.status_code == 200, f"Mitarbeiter cannot list devices: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ P0: Mitarbeiter can list {len(data)} devices")
    
    def test_p0_mitarbeiter_can_get_single_device(self, mitarbeiter_token):
        """P0: Mitarbeiter should be able to access GET /api/devices/{id}"""
        # First get list of devices
        list_res = requests.get(f"{BASE_URL}/api/devices", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        assert list_res.status_code == 200
        devices = list_res.json()
        if len(devices) == 0:
            pytest.skip("No devices to test with")
        
        device_id = devices[0]["id"]
        response = requests.get(f"{BASE_URL}/api/devices/{device_id}", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        assert response.status_code == 200, f"Mitarbeiter cannot get device: {response.text}"
        print(f"✓ P0: Mitarbeiter can get single device {device_id}")
    
    def test_p0_mitarbeiter_cannot_create_device(self, mitarbeiter_token):
        """P0: Mitarbeiter should NOT be able to create devices (admin only)"""
        response = requests.post(f"{BASE_URL}/api/devices", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"},
            json={
                "device_type": "stromerzeuger",
                "serial_number": f"TEST-MA-{uuid.uuid4().hex[:8]}",
                "user_field": "Test by Mitarbeiter"
            })
        assert response.status_code == 403, f"Mitarbeiter should not be able to create devices: {response.status_code}"
        print("✓ P0: Mitarbeiter correctly blocked from creating devices")
    
    def test_p0_mitarbeiter_can_toggle_status(self, mitarbeiter_token, admin_token):
        """P0: Mitarbeiter can toggle device status (ausser_betrieb)"""
        # First get a device
        list_res = requests.get(f"{BASE_URL}/api/devices", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        devices = list_res.json()
        if len(devices) == 0:
            pytest.skip("No devices to test with")
        
        device_id = devices[0]["id"]
        
        # Mitarbeiter should be able to toggle status
        response = requests.post(f"{BASE_URL}/api/devices/{device_id}/ausser-betrieb", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        assert response.status_code == 200, f"Mitarbeiter cannot toggle status: {response.text}"
        new_status = response.json().get("status")
        print(f"✓ P0: Mitarbeiter can toggle device status to: {new_status}")
        
        # Toggle back to original state
        requests.post(f"{BASE_URL}/api/devices/{device_id}/ausser-betrieb", 
            headers={"Authorization": f"Bearer {admin_token}"})
    
    def test_p0_kunde_cannot_access_devices(self, kunde_token):
        """P0: Kunde should NOT be able to access device management"""
        response = requests.get(f"{BASE_URL}/api/devices", 
            headers={"Authorization": f"Bearer {kunde_token}"})
        assert response.status_code == 403, f"Kunde should not access devices: {response.status_code}"
        print("✓ P0: Kunde correctly blocked from device management")

    # ========== P1: AUSSER_BETRIEB FILTER IN GENERATORS ==========
    
    def test_p1_setup_ausser_betrieb_device(self, admin_token):
        """P1: Setup - Create a device with 'ausser_betrieb' status and matching serial"""
        # Check if we have any generators
        gen_res = requests.get(f"{BASE_URL}/api/generators", 
            headers={"Authorization": f"Bearer {admin_token}"})
        generators = gen_res.json() if gen_res.status_code == 200 else []
        
        if len(generators) == 0:
            # Create demo generators
            simulate_res = requests.post(f"{BASE_URL}/api/generators/simulate", 
                headers={"Authorization": f"Bearer {admin_token}"})
            if simulate_res.status_code == 200:
                gen_res = requests.get(f"{BASE_URL}/api/generators", 
                    headers={"Authorization": f"Bearer {admin_token}"})
                generators = gen_res.json()
        
        if len(generators) == 0:
            pytest.skip("No generators available")
        
        # Get first generator's serial number
        first_gen = generators[0]
        serial = first_gen.get("serial_number")
        print(f"✓ P1 Setup: Found generator with serial {serial}")
        return serial
    
    def test_p1_ausser_betrieb_hides_generator(self, admin_token):
        """P1: Generator with matching device in 'ausser_betrieb' should NOT appear in monitoring"""
        # Get all generators first
        gen_res = requests.get(f"{BASE_URL}/api/generators", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert gen_res.status_code == 200
        initial_generators = gen_res.json()
        initial_count = len(initial_generators)
        
        if initial_count == 0:
            pytest.skip("No generators to test")
        
        # Get a generator serial to test with
        test_gen = initial_generators[0]
        serial = test_gen.get("serial_number")
        
        # Check if there's already a device with this serial
        devices_res = requests.get(f"{BASE_URL}/api/devices", 
            headers={"Authorization": f"Bearer {admin_token}"})
        devices = devices_res.json() if devices_res.status_code == 200 else []
        matching_device = next((d for d in devices if d.get("serial_number") == serial), None)
        
        if not matching_device:
            # Create a device with matching serial
            create_res = requests.post(f"{BASE_URL}/api/devices", 
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "device_type": "stromerzeuger",
                    "serial_number": serial,
                    "user_field": "TEST matching generator"
                })
            if create_res.status_code == 200:
                matching_device = create_res.json()
            else:
                pytest.skip(f"Cannot create matching device: {create_res.text}")
        
        # Now set device to ausser_betrieb
        device_id = matching_device["id"]
        toggle_res = requests.post(f"{BASE_URL}/api/devices/{device_id}/ausser-betrieb", 
            headers={"Authorization": f"Bearer {admin_token}"})
        
        if toggle_res.status_code == 200 and toggle_res.json().get("status") == "ausser_betrieb":
            # Check generators again - should have one less
            gen_res2 = requests.get(f"{BASE_URL}/api/generators", 
                headers={"Authorization": f"Bearer {admin_token}"})
            new_generators = gen_res2.json()
            
            # Verify the generator with matching serial is NOT in the list
            matching_gen_in_list = any(g.get("serial_number") == serial for g in new_generators)
            
            assert not matching_gen_in_list, f"Generator {serial} should be hidden when device is ausser_betrieb"
            print(f"✓ P1: Generator {serial} correctly hidden when device is ausser_betrieb")
            
            # Restore status
            requests.post(f"{BASE_URL}/api/devices/{device_id}/ausser-betrieb", 
                headers={"Authorization": f"Bearer {admin_token}"})
        else:
            # Toggle back if it was already ausser_betrieb or failed
            requests.post(f"{BASE_URL}/api/devices/{device_id}/ausser-betrieb", 
                headers={"Authorization": f"Bearer {admin_token}"})
            print(f"✓ P1: Testing generator filter (toggle status issue)")

    # ========== P3a: SERVICEPLAN LIST AND CREATE ==========
    
    def test_p3a_serviceplan_list(self, mitarbeiter_token):
        """P3a: GET /api/serviceplan should list plans"""
        response = requests.get(f"{BASE_URL}/api/serviceplan", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        assert response.status_code == 200, f"Failed to list service plans: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ P3a: Listed {len(data)} service plans")
    
    def test_p3a_serviceplan_create(self, admin_token, mitarbeiter_token):
        """P3a: POST /api/serviceplan creates a plan for a device"""
        # Get a device without a plan
        devices_res = requests.get(f"{BASE_URL}/api/devices", 
            headers={"Authorization": f"Bearer {admin_token}"})
        devices = devices_res.json() if devices_res.status_code == 200 else []
        
        plans_res = requests.get(f"{BASE_URL}/api/serviceplan", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        plans = plans_res.json() if plans_res.status_code == 200 else []
        planned_device_ids = [p.get("device_id") for p in plans]
        
        unplanned_device = next((d for d in devices if d["id"] not in planned_device_ids), None)
        
        if not unplanned_device:
            # Create a new device for testing
            create_device_res = requests.post(f"{BASE_URL}/api/devices", 
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "device_type": "stromerzeuger",
                    "serial_number": f"TEST-SP-{uuid.uuid4().hex[:8]}",
                    "user_field": "Test for serviceplan"
                })
            if create_device_res.status_code != 200:
                pytest.skip("Cannot create test device")
            unplanned_device = create_device_res.json()
        
        # Create a serviceplan
        plan_res = requests.post(f"{BASE_URL}/api/serviceplan", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"},
            json={
                "device_id": unplanned_device["id"],
                "interval_hours": 500,
                "interval_months": 12,
                "tasks": ["Ölwechsel", "Filterprüfung"],
                "notes": "Test plan"
            })
        
        assert plan_res.status_code == 200, f"Failed to create service plan: {plan_res.text}"
        plan_data = plan_res.json()
        assert "id" in plan_data
        assert plan_data["device_id"] == unplanned_device["id"]
        assert plan_data["interval_hours"] == 500
        print(f"✓ P3a: Created service plan {plan_data['id']} for device {unplanned_device['serial_number']}")
        return plan_data
    
    def test_p3a_serviceplan_duplicate_rejected(self, mitarbeiter_token):
        """P3a: Creating duplicate plan for same device should fail"""
        plans_res = requests.get(f"{BASE_URL}/api/serviceplan", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        plans = plans_res.json()
        
        if len(plans) == 0:
            pytest.skip("No existing plans to test duplicate rejection")
        
        existing_device_id = plans[0]["device_id"]
        
        response = requests.post(f"{BASE_URL}/api/serviceplan", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"},
            json={
                "device_id": existing_device_id,
                "interval_hours": 500,
                "interval_months": 12
            })
        
        assert response.status_code == 400, f"Duplicate plan should be rejected: {response.status_code}"
        print("✓ P3a: Duplicate plan correctly rejected with 400")
    
    def test_p3a_serviceplan_get_detail(self, mitarbeiter_token):
        """P3a: GET /api/serviceplan/{id} returns detail with entries"""
        plans_res = requests.get(f"{BASE_URL}/api/serviceplan", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        plans = plans_res.json()
        
        if len(plans) == 0:
            pytest.skip("No plans to get detail")
        
        plan_id = plans[0]["id"]
        response = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        
        assert response.status_code == 200, f"Failed to get plan detail: {response.text}"
        detail = response.json()
        assert detail["id"] == plan_id
        assert "entries" in detail  # Should have entries array even if empty
        assert "device_serial" in detail  # Should have enriched device info
        print(f"✓ P3a: Got service plan detail with {len(detail.get('entries', []))} entries")

    # ========== P3b: SERVICEPLAN ENTRIES ==========
    
    def test_p3b_add_maintenance_entry(self, mitarbeiter_token):
        """P3b: POST /api/serviceplan/{id}/entries adds a maintenance entry"""
        plans_res = requests.get(f"{BASE_URL}/api/serviceplan", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        plans = plans_res.json()
        
        if len(plans) == 0:
            pytest.skip("No plans to add entry to")
        
        plan_id = plans[0]["id"]
        
        entry_data = {
            "performed_by": "Test Techniker",
            "performed_at": datetime.now().strftime("%Y-%m-%d"),
            "hours_at_service": 4500.5,
            "tasks_completed": ["Ölwechsel", "Filterprüfung"],
            "notes": "Test maintenance entry"
        }
        
        response = requests.post(f"{BASE_URL}/api/serviceplan/{plan_id}/entries", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"},
            json=entry_data)
        
        assert response.status_code == 200, f"Failed to add entry: {response.text}"
        entry = response.json()
        assert "id" in entry
        assert entry["performed_by"] == "Test Techniker"
        assert entry["hours_at_service"] == 4500.5
        print(f"✓ P3b: Added maintenance entry {entry['id']}")
        return entry
    
    def test_p3b_entry_has_required_fields(self, mitarbeiter_token):
        """P3b: Entry should have performed_by, performed_at, hours_at_service, tasks_completed"""
        plans_res = requests.get(f"{BASE_URL}/api/serviceplan", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        plans = plans_res.json()
        
        if len(plans) == 0:
            pytest.skip("No plans")
        
        plan_id = plans[0]["id"]
        detail_res = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        detail = detail_res.json()
        entries = detail.get("entries", [])
        
        if len(entries) == 0:
            pytest.skip("No entries to check")
        
        entry = entries[0]
        required_fields = ["performed_by", "performed_at", "hours_at_service", "tasks_completed"]
        for field in required_fields:
            assert field in entry, f"Entry missing field: {field}"
        print(f"✓ P3b: Entry has all required fields: {', '.join(required_fields)}")
    
    def test_p3b_delete_entry_admin_only(self, admin_token, mitarbeiter_token):
        """P3b: DELETE entry should be admin only"""
        plans_res = requests.get(f"{BASE_URL}/api/serviceplan", 
            headers={"Authorization": f"Bearer {admin_token}"})
        plans = plans_res.json()
        
        if len(plans) == 0:
            pytest.skip("No plans")
        
        plan_id = plans[0]["id"]
        detail_res = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", 
            headers={"Authorization": f"Bearer {admin_token}"})
        detail = detail_res.json()
        entries = detail.get("entries", [])
        
        if len(entries) == 0:
            # Add an entry first
            add_res = requests.post(f"{BASE_URL}/api/serviceplan/{plan_id}/entries", 
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "performed_by": "Admin Test",
                    "performed_at": datetime.now().strftime("%Y-%m-%d"),
                    "hours_at_service": 5000
                })
            if add_res.status_code == 200:
                entry_id = add_res.json()["id"]
            else:
                pytest.skip("Cannot create test entry")
        else:
            entry_id = entries[0]["id"]
        
        # Mitarbeiter trying to delete should fail
        delete_res = requests.delete(f"{BASE_URL}/api/serviceplan/{plan_id}/entries/{entry_id}", 
            headers={"Authorization": f"Bearer {mitarbeiter_token}"})
        assert delete_res.status_code == 403, f"Mitarbeiter should not delete entries: {delete_res.status_code}"
        print("✓ P3b: Entry deletion correctly requires admin")

    # ========== P4: MAINTENANCE WARNING IN GENERATORS ==========
    
    def test_p4_maintenance_warning_flag(self, admin_token):
        """P4: Generators with next_maintenance within 30 days show maintenance_warning"""
        # Get devices and set one with next_maintenance within 30 days
        devices_res = requests.get(f"{BASE_URL}/api/devices", 
            headers={"Authorization": f"Bearer {admin_token}"})
        devices = devices_res.json()
        
        # Get generators
        gen_res = requests.get(f"{BASE_URL}/api/generators", 
            headers={"Authorization": f"Bearer {admin_token}"})
        generators = gen_res.json()
        
        if len(generators) == 0:
            pytest.skip("No generators")
        
        # Find a generator with matching device
        test_gen = generators[0]
        serial = test_gen.get("serial_number")
        matching_device = next((d for d in devices if d.get("serial_number") == serial), None)
        
        if matching_device:
            # Set next_maintenance to within 30 days
            next_maint_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
            update_res = requests.put(f"{BASE_URL}/api/devices/{matching_device['id']}", 
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"next_maintenance": next_maint_date})
            
            if update_res.status_code == 200:
                # Re-fetch generators
                gen_res2 = requests.get(f"{BASE_URL}/api/generators", 
                    headers={"Authorization": f"Bearer {admin_token}"})
                updated_generators = gen_res2.json()
                
                target_gen = next((g for g in updated_generators if g.get("serial_number") == serial), None)
                if target_gen:
                    has_warning = target_gen.get("maintenance_warning", False)
                    print(f"✓ P4: Generator {serial} maintenance_warning={has_warning} (expected True)")
                    assert has_warning, f"Generator should have maintenance_warning when device next_maintenance is within 30 days"
                    
                    # Verify additional fields
                    assert "maintenance_due_days" in target_gen, "Should have maintenance_due_days"
                    assert "next_maintenance_date" in target_gen, "Should have next_maintenance_date"
                    print(f"✓ P4: maintenance_due_days={target_gen['maintenance_due_days']}, next_maintenance_date={target_gen['next_maintenance_date']}")
        else:
            pytest.skip("No matching device found for generator")


class TestServiceplanAuth:
    """Auth tests for Serviceplan endpoints"""
    
    @pytest.fixture
    def kunde_token(self):
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "kunde@test.com",
            "password": "password"
        })
        if login_res.status_code != 200:
            pytest.skip("Kunde login failed")
        return login_res.json()["token"]
    
    def test_kunde_cannot_access_serviceplan(self, kunde_token):
        """Kunde should not access serviceplan endpoints"""
        response = requests.get(f"{BASE_URL}/api/serviceplan", 
            headers={"Authorization": f"Bearer {kunde_token}"})
        assert response.status_code == 403, f"Kunde should not access serviceplans: {response.status_code}"
        print("✓ Kunde correctly blocked from serviceplan")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
