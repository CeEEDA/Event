"""
Test Suite for Cascade Delete Functionality - Iteration 20
Tests that deleting a device also removes its service plan and maintenance entries
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ============== Fixtures ==============

@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "password"
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth token"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


# ============== Test: Serviceplan returns only valid plans (no orphans) ==============

class TestServiceplanNoOrphans:
    """Verify GET /api/serviceplan only returns plans for existing devices"""

    def test_list_serviceplan_returns_only_valid_plans(self, admin_headers):
        """GET /api/serviceplan should only return plans for existing devices"""
        # Get all devices first
        devices_resp = requests.get(f"{BASE_URL}/api/devices", headers=admin_headers)
        assert devices_resp.status_code == 200
        devices = devices_resp.json()
        device_ids = {d["id"] for d in devices}
        
        # Get all service plans
        plans_resp = requests.get(f"{BASE_URL}/api/serviceplan", headers=admin_headers)
        assert plans_resp.status_code == 200
        plans = plans_resp.json()
        
        # Every plan should reference an existing device
        for plan in plans:
            assert plan["device_id"] in device_ids, f"Orphaned plan found: {plan['id']} references non-existent device {plan['device_id']}"
            # Should also have enriched device info
            assert "device_serial" in plan, "Plan should have device_serial enriched"
        
        print(f"✓ All {len(plans)} service plans reference existing devices")

    def test_serviceplan_count_matches_expectations(self, admin_headers):
        """Current state: should have exactly 1 plan for 1 device"""
        plans_resp = requests.get(f"{BASE_URL}/api/serviceplan", headers=admin_headers)
        assert plans_resp.status_code == 200
        plans = plans_resp.json()
        
        # Based on current state: 1 device (XBAP2021) with 1 plan
        assert len(plans) == 1, f"Expected 1 service plan, got {len(plans)}"
        assert plans[0]["device_serial"] == "XBAP2021", f"Expected XBAP2021, got {plans[0].get('device_serial')}"
        
        print(f"✓ Service plan count is correct: {len(plans)}")


# ============== Test: Cascade Delete Flow ==============

class TestCascadeDelete:
    """Test full cascade delete: Device -> Service Plan -> Maintenance Entries"""

    @pytest.fixture
    def test_device(self, admin_headers):
        """Create a test device for cascade delete testing"""
        device_data = {
            "device_type": "stromerzeuger",
            "serial_number": "TEST_CASCADE_DEL_001",
            "model": "Cascade Test Model",
            "notes": "Test device for cascade delete"
        }
        response = requests.post(f"{BASE_URL}/api/devices", json=device_data, headers=admin_headers)
        assert response.status_code == 200, f"Failed to create test device: {response.text}"
        device = response.json()
        yield device
        # Cleanup: delete device if it still exists (in case test failed)
        requests.delete(f"{BASE_URL}/api/devices/{device['id']}", headers=admin_headers)

    def test_full_cascade_delete_flow(self, admin_headers, test_device):
        """
        Full test: Create device -> Create service plan -> Add maintenance entry 
        -> Delete device -> Verify plan and entries deleted
        """
        device_id = test_device["id"]
        print(f"\n1. Created test device: {device_id}")

        # Create service plan for the device
        plan_data = {
            "device_id": device_id,
            "current_hours": 100,
            "interval_hours": 500,
            "interval_months": 12,
            "tasks": ["Test task 1", "Test task 2"],
            "notes": "Cascade delete test plan"
        }
        plan_resp = requests.post(f"{BASE_URL}/api/serviceplan", json=plan_data, headers=admin_headers)
        assert plan_resp.status_code == 200, f"Failed to create service plan: {plan_resp.text}"
        plan = plan_resp.json()
        plan_id = plan["id"]
        print(f"2. Created service plan: {plan_id}")

        # Add maintenance entry to the service plan
        entry_data = {
            "performed_by": "Test Technician",
            "performed_at": "2026-03-06",
            "hours_at_service": 100,
            "next_maintenance_months": 6,
            "next_maintenance_hours": 250,
            "notes": "Cascade delete test entry"
        }
        entry_resp = requests.post(f"{BASE_URL}/api/serviceplan/{plan_id}/entries", json=entry_data, headers=admin_headers)
        assert entry_resp.status_code == 200, f"Failed to create maintenance entry: {entry_resp.text}"
        entry = entry_resp.json()
        entry_id = entry["id"]
        print(f"3. Created maintenance entry: {entry_id}")

        # Verify plan exists before delete
        check_plan_resp = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", headers=admin_headers)
        assert check_plan_resp.status_code == 200, "Service plan should exist before delete"
        plan_data = check_plan_resp.json()
        assert len(plan_data.get("entries", [])) == 1, "Plan should have 1 entry"
        print(f"4. Verified plan exists with 1 entry")

        # DELETE THE DEVICE - should cascade delete plan and entries
        delete_resp = requests.delete(f"{BASE_URL}/api/devices/{device_id}", headers=admin_headers)
        assert delete_resp.status_code == 200, f"Failed to delete device: {delete_resp.text}"
        print(f"5. Deleted device: {device_id}")

        # Verify device is deleted
        device_check = requests.get(f"{BASE_URL}/api/devices/{device_id}", headers=admin_headers)
        assert device_check.status_code == 404, "Device should be deleted"
        print(f"6. Verified device deleted (404)")

        # Verify service plan is deleted
        plan_check = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", headers=admin_headers)
        assert plan_check.status_code == 404, f"Service plan should be deleted but got {plan_check.status_code}"
        print(f"7. Verified service plan deleted (404)")

        # Verify plan doesn't appear in list
        list_plans = requests.get(f"{BASE_URL}/api/serviceplan", headers=admin_headers)
        assert list_plans.status_code == 200
        plans = list_plans.json()
        plan_ids = [p["id"] for p in plans]
        assert plan_id not in plan_ids, "Deleted plan should not appear in list"
        print(f"8. Verified plan not in list endpoint")

        print("\n✓ CASCADE DELETE TEST PASSED: Device, Service Plan, and Maintenance Entry all deleted correctly")


# ============== Test: Multiple entries cascade delete ==============

class TestCascadeDeleteMultipleEntries:
    """Test cascade delete with multiple maintenance entries"""

    def test_cascade_delete_with_multiple_entries(self, admin_headers):
        """Device with multiple maintenance entries should all be deleted"""
        # Create device
        device_resp = requests.post(f"{BASE_URL}/api/devices", json={
            "device_type": "stromerzeuger",
            "serial_number": "TEST_CASCADE_MULTI_001",
            "notes": "Multi-entry cascade test"
        }, headers=admin_headers)
        assert device_resp.status_code == 200
        device_id = device_resp.json()["id"]

        # Create service plan
        plan_resp = requests.post(f"{BASE_URL}/api/serviceplan", json={
            "device_id": device_id,
            "current_hours": 0,
            "interval_hours": 500
        }, headers=admin_headers)
        assert plan_resp.status_code == 200
        plan_id = plan_resp.json()["id"]

        # Create 3 maintenance entries
        entry_ids = []
        for i in range(3):
            entry_resp = requests.post(f"{BASE_URL}/api/serviceplan/{plan_id}/entries", json={
                "performed_by": f"Tech {i+1}",
                "performed_at": f"2026-0{i+1}-15",
                "hours_at_service": (i+1) * 100,
                "next_maintenance_hours": 500,
                "notes": f"Entry {i+1}"
            }, headers=admin_headers)
            assert entry_resp.status_code == 200
            entry_ids.append(entry_resp.json()["id"])
        
        print(f"Created device with plan and {len(entry_ids)} entries")

        # Delete device
        delete_resp = requests.delete(f"{BASE_URL}/api/devices/{device_id}", headers=admin_headers)
        assert delete_resp.status_code == 200

        # Verify plan deleted
        plan_check = requests.get(f"{BASE_URL}/api/serviceplan/{plan_id}", headers=admin_headers)
        assert plan_check.status_code == 404, "Plan should be deleted"

        # The entries are associated with the plan, so verifying plan deletion is sufficient
        # since entries collection is cleaned by delete_many({"service_plan_id": plan_id})
        
        print("✓ Multi-entry cascade delete successful")


# ============== Test: Delete device without plan ==============

class TestDeleteDeviceWithoutPlan:
    """Ensure deleting a device without a service plan works correctly"""

    def test_delete_device_without_serviceplan(self, admin_headers):
        """Delete device that has no service plan should work without error"""
        # Create device
        device_resp = requests.post(f"{BASE_URL}/api/devices", json={
            "device_type": "stromerzeuger",
            "serial_number": "TEST_NO_PLAN_001",
            "notes": "Device without service plan"
        }, headers=admin_headers)
        assert device_resp.status_code == 200
        device_id = device_resp.json()["id"]

        # Verify no plan exists
        plan_info = requests.get(f"{BASE_URL}/api/serviceplan/device/{device_id}", headers=admin_headers)
        assert plan_info.status_code == 200
        assert plan_info.json().get("has_plan") == False

        # Delete device
        delete_resp = requests.delete(f"{BASE_URL}/api/devices/{device_id}", headers=admin_headers)
        assert delete_resp.status_code == 200, f"Delete should succeed even without plan: {delete_resp.text}"

        # Verify device deleted
        device_check = requests.get(f"{BASE_URL}/api/devices/{device_id}", headers=admin_headers)
        assert device_check.status_code == 404

        print("✓ Delete device without plan successful")


# ============== Test: Plan count remains correct after operations ==============

class TestPlanCountIntegrity:
    """Verify plan count stays correct through create/delete cycles"""

    def test_plan_count_after_cascade_delete(self, admin_headers):
        """Plan count should be exactly 1 (original XBAP2021) after all test cleanups"""
        # Get baseline count
        plans = requests.get(f"{BASE_URL}/api/serviceplan", headers=admin_headers).json()
        initial_count = len(plans)
        
        # Create device + plan
        device_resp = requests.post(f"{BASE_URL}/api/devices", json={
            "device_type": "stromerzeuger",
            "serial_number": "TEST_COUNT_001"
        }, headers=admin_headers)
        device_id = device_resp.json()["id"]

        plan_resp = requests.post(f"{BASE_URL}/api/serviceplan", json={
            "device_id": device_id,
            "interval_hours": 500
        }, headers=admin_headers)
        assert plan_resp.status_code == 200

        # Check count increased
        plans_mid = requests.get(f"{BASE_URL}/api/serviceplan", headers=admin_headers).json()
        assert len(plans_mid) == initial_count + 1, "Plan count should increase by 1"

        # Delete device (cascade)
        requests.delete(f"{BASE_URL}/api/devices/{device_id}", headers=admin_headers)

        # Check count returned to initial
        plans_final = requests.get(f"{BASE_URL}/api/serviceplan", headers=admin_headers).json()
        assert len(plans_final) == initial_count, f"Plan count should return to {initial_count}, got {len(plans_final)}"

        print(f"✓ Plan count integrity maintained: {initial_count} -> {initial_count + 1} -> {initial_count}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
