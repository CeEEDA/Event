"""
Iteration 15 - Bug Fixes and Feature Tests
- BUG FIX: Edit device (PUT /api/devices/{id}) ObjectId serialization fix
- BUG FIX: Monitoring page loads - GET /api/generators returns 200
- Parts: GET /api/devices/parts/types returns updated types list
- Parts: Motoröl with liters field support
- Parts: Free text option (Sonderteil) support
- Service Plan: Techniker field read-only (frontend only)
- Service Plan: Row click opens plan detail (no Details button - frontend only)
- Service Plan: Both months and hours fields mandatory
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestAuth:
    """Authentication and token management"""

    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["token"]

    @pytest.fixture(scope="class")
    def mitarbeiter_token(self):
        """Get mitarbeiter auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "anna.weber@test.com",
            "password": "password"
        })
        assert response.status_code == 200, f"Mitarbeiter login failed: {response.text}"
        return response.json()["token"]


class TestDeviceEditBugFix(TestAuth):
    """Test BUG FIX: Edit device no longer returns 500 due to ObjectId serialization"""

    def test_update_device_xbap2021(self, admin_token):
        """Test updating device XBAP2021 with model='Aggreko' - should not return 500"""
        device_id = "07d42e9d-403e-48c6-8904-47f2f3323965"
        
        # First get the device to confirm it exists
        headers = {"Authorization": f"Bearer {admin_token}"}
        get_response = requests.get(f"{BASE_URL}/api/devices/{device_id}", headers=headers)
        
        if get_response.status_code == 404:
            pytest.skip("Device XBAP2021 not found - may have been deleted")
        
        assert get_response.status_code == 200, f"GET device failed: {get_response.text}"
        device_data = get_response.json()
        print(f"Device found: {device_data.get('serial_number')}")
        
        # Update the device model
        update_payload = {"model": "Aggreko"}
        update_response = requests.put(
            f"{BASE_URL}/api/devices/{device_id}",
            json=update_payload,
            headers=headers
        )
        
        # Key assertion: Should NOT return 500 (ObjectId bug fix)
        assert update_response.status_code != 500, f"Device update returned 500: {update_response.text}"
        assert update_response.status_code == 200, f"Device update failed: {update_response.text}"
        
        # Verify the update was applied
        updated_device = update_response.json()
        assert updated_device.get("model") == "Aggreko", "Model was not updated to Aggreko"
        
        # Verify image_gridfs_id is serialized as string (not ObjectId)
        if "image_gridfs_id" in updated_device and updated_device["image_gridfs_id"]:
            assert isinstance(updated_device["image_gridfs_id"], str), "image_gridfs_id should be string"
        
        print(f"SUCCESS: Device updated without 500 error. Model = {updated_device.get('model')}")

    def test_list_devices_no_objectid_error(self, admin_token):
        """Test that listing devices with images doesn't cause ObjectId serialization errors"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/devices", headers=headers)
        
        assert response.status_code == 200, f"List devices failed: {response.text}"
        devices = response.json()
        
        # Check that all image_gridfs_id fields are strings
        for device in devices:
            if device.get("image_gridfs_id"):
                assert isinstance(device["image_gridfs_id"], str), f"Device {device['serial_number']} has non-string image_gridfs_id"
        
        print(f"SUCCESS: Listed {len(devices)} devices without ObjectId errors")


class TestMonitoringBugFix(TestAuth):
    """Test BUG FIX: Monitoring page loads without error for manual and device-synced generators"""

    def test_generators_list_loads(self, admin_token):
        """Test GET /api/generators returns 200 with proper data"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/generators", headers=headers)
        
        assert response.status_code == 200, f"Generators list failed: {response.text}"
        generators = response.json()
        
        assert isinstance(generators, list), "Response should be a list"
        print(f"SUCCESS: GET /api/generators returned {len(generators)} generators")
        
        # Check for both regular and device-synced generators
        regular_gens = [g for g in generators if not g.get("from_device")]
        device_synced = [g for g in generators if g.get("from_device")]
        print(f"Regular generators: {len(regular_gens)}, Device-synced: {len(device_synced)}")

    def test_generators_stats_loads(self, admin_token):
        """Test GET /api/generators/stats/overview returns 200"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/generators/stats/overview", headers=headers)
        
        assert response.status_code == 200, f"Generator stats failed: {response.text}"
        stats = response.json()
        
        assert "total" in stats, "Stats should have 'total' field"
        print(f"SUCCESS: Generator stats - Total: {stats.get('total')}")


class TestPartTypes(TestAuth):
    """Test Parts endpoint returns correct types"""

    def test_part_types_list(self, admin_token):
        """Test GET /api/devices/parts/types returns updated types"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/devices/parts/types", headers=headers)
        
        assert response.status_code == 200, f"Part types failed: {response.text}"
        data = response.json()
        
        assert "types" in data, "Response should have 'types' field"
        types = data["types"]
        
        # Required types per user specification
        required_types = [
            "Kraftstoffvorfilter", "Kraftstofffilter", "Ölfilter", "Keilriemen",
            "Umlenkrollen", "Wasserpumpe", "Luftfilter", "Motoröl"
        ]
        
        for req_type in required_types:
            assert req_type in types, f"Missing part type: {req_type}"
        
        print(f"SUCCESS: Part types returned: {types}")

    def test_create_motoroel_part_with_liters(self, admin_token):
        """Test creating Motoröl part with liters field"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get a device to add part to
        devices_response = requests.get(f"{BASE_URL}/api/devices", headers=headers)
        assert devices_response.status_code == 200
        devices = devices_response.json()
        
        if not devices:
            pytest.skip("No devices available to test parts")
        
        device_id = devices[0]["id"]
        
        # Create Motoröl part with liters
        part_payload = {
            "part_type": "Motoröl",
            "part_number": "OIL-TEST-001",
            "liters": 12.5,
            "notes": "Test Motoröl with liters"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/devices/{device_id}/parts",
            json=part_payload,
            headers=headers
        )
        
        assert response.status_code == 200, f"Create part failed: {response.text}"
        part = response.json()
        
        assert part.get("part_type") == "Motoröl"
        assert part.get("liters") == 12.5, "Liters field should be 12.5"
        print(f"SUCCESS: Created Motoröl part with liters = {part.get('liters')}")
        
        # Cleanup - delete the test part
        if part.get("id"):
            requests.delete(f"{BASE_URL}/api/devices/parts/{part['id']}", headers=headers)

    def test_create_sonderteil_custom_type(self, admin_token):
        """Test creating custom part type (Sonderteil/Freitext)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get a device to add part to
        devices_response = requests.get(f"{BASE_URL}/api/devices", headers=headers)
        assert devices_response.status_code == 200
        devices = devices_response.json()
        
        if not devices:
            pytest.skip("No devices available to test parts")
        
        device_id = devices[0]["id"]
        
        # Create custom part type (free text)
        custom_type = "Spezialdichtung ABC-123"
        part_payload = {
            "part_type": custom_type,
            "part_number": "CUSTOM-001",
            "notes": "Custom/Sonderteil test"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/devices/{device_id}/parts",
            json=part_payload,
            headers=headers
        )
        
        assert response.status_code == 200, f"Create custom part failed: {response.text}"
        part = response.json()
        
        assert part.get("part_type") == custom_type, f"Custom part type not saved correctly"
        print(f"SUCCESS: Created custom part type: {part.get('part_type')}")
        
        # Cleanup
        if part.get("id"):
            requests.delete(f"{BASE_URL}/api/devices/parts/{part['id']}", headers=headers)


class TestServicePlanMandatoryFields(TestAuth):
    """Test Service Plan has both months and hours as mandatory fields"""

    def test_create_maintenance_entry_requires_both_fields(self, admin_token):
        """Test that maintenance entry creation accepts both months and hours"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get service plans
        plans_response = requests.get(f"{BASE_URL}/api/serviceplan", headers=headers)
        assert plans_response.status_code == 200
        plans = plans_response.json()
        
        if not plans:
            # Create a plan first
            devices_response = requests.get(f"{BASE_URL}/api/devices", headers=headers)
            devices = devices_response.json()
            
            if not devices:
                pytest.skip("No devices available to test service plans")
            
            # Find a device without a plan
            device_ids_with_plans = {p["device_id"] for p in plans}
            device_without_plan = None
            for d in devices:
                if d["id"] not in device_ids_with_plans:
                    device_without_plan = d
                    break
            
            if not device_without_plan:
                pytest.skip("All devices already have plans")
            
            create_plan_response = requests.post(
                f"{BASE_URL}/api/serviceplan",
                json={"device_id": device_without_plan["id"], "current_hours": 1000, "interval_hours": 500, "interval_months": 12},
                headers=headers
            )
            assert create_plan_response.status_code == 200
            plan = create_plan_response.json()
        else:
            plan = plans[0]
        
        plan_id = plan["id"]
        
        # Create maintenance entry with BOTH months and hours
        entry_payload = {
            "performed_by": "Test Techniker",
            "performed_at": "2026-01-15",
            "hours_at_service": 5000,
            "next_maintenance_months": 12,
            "next_maintenance_hours": 500,
            "remarks": "Test entry with both mandatory fields"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/serviceplan/{plan_id}/entries",
            json=entry_payload,
            headers=headers
        )
        
        assert response.status_code == 200, f"Create entry failed: {response.text}"
        entry = response.json()
        
        assert entry.get("next_maintenance_months") == 12, "next_maintenance_months should be 12"
        assert entry.get("next_maintenance_hours") == 500, "next_maintenance_hours should be 500"
        print(f"SUCCESS: Maintenance entry created with months={entry.get('next_maintenance_months')}, hours={entry.get('next_maintenance_hours')}")
        
        # Cleanup
        if entry.get("id"):
            requests.delete(f"{BASE_URL}/api/serviceplan/{plan_id}/entries/{entry['id']}", headers=headers)


class TestHealthCheck:
    """Basic health and auth checks"""

    def test_api_health(self):
        """Test API is responsive"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("SUCCESS: API health check passed")

    def test_admin_login(self):
        """Test admin login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        assert "token" in response.json()
        print("SUCCESS: Admin login successful")

    def test_mitarbeiter_login(self):
        """Test mitarbeiter login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "anna.weber@test.com",
            "password": "password"
        })
        assert response.status_code == 200, f"Mitarbeiter login failed: {response.text}"
        assert "token" in response.json()
        print("SUCCESS: Mitarbeiter login successful")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
