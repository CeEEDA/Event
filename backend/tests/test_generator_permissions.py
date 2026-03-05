"""
Test Generator Monitoring Permissions
Tests the permission-based filtering for generator access:
- User with monitoring enabled + access_all=true sees all generators
- User with monitoring enabled + specific generator_ids sees only assigned generators
- User without monitoring enabled sees no generators (unless via assigned_customer_id)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestGeneratorPermissions:
    """Test generator_monitoring permissions system"""
    
    admin_token = None
    kunde_token = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and kunde to get tokens"""
        # Login as admin
        admin_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert admin_resp.status_code == 200, f"Admin login failed: {admin_resp.text}"
        self.admin_token = admin_resp.json()["token"]
        
        # Login as kunde
        kunde_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "kunde@test.com",
            "password": "password"
        })
        assert kunde_resp.status_code == 200, f"Kunde login failed: {kunde_resp.text}"
        self.kunde_token = kunde_resp.json()["token"]
    
    def test_admin_sees_all_generators(self):
        """Admin should see all generators"""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/generators", headers=headers)
        
        assert resp.status_code == 200
        generators = resp.json()
        print(f"Admin sees {len(generators)} generators")
        assert len(generators) >= 5, f"Expected at least 5 generators, got {len(generators)}"
    
    def test_admin_stats_shows_all(self):
        """Admin stats should show all generators"""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/generators/stats/overview", headers=headers)
        
        assert resp.status_code == 200
        stats = resp.json()
        print(f"Admin stats: total={stats.get('total')}")
        assert stats["total"] >= 5, f"Expected total >= 5, got {stats['total']}"
    
    def test_kunde_with_specific_generators_sees_limited(self):
        """
        Kunde with monitoring enabled and specific generator_ids 
        should only see assigned generators (not all 5)
        """
        headers = {"Authorization": f"Bearer {self.kunde_token}"}
        resp = requests.get(f"{BASE_URL}/api/generators", headers=headers)
        
        assert resp.status_code == 200
        generators = resp.json()
        print(f"Kunde sees {len(generators)} generators")
        
        # Kunde should see fewer than 5 (total) generators if permissions work
        print(f"Generator names: {[g['name'] for g in generators]}")
        
        # Verify that kunde sees a subset of generators (not all 5)
        assert len(generators) < 5, f"Kunde should see fewer than 5 generators, got {len(generators)}"
        assert len(generators) > 0, "Kunde should see at least some assigned generators"
    
    def test_kunde_stats_shows_limited(self):
        """Kunde stats should only count their assigned generators (not all 5)"""
        headers = {"Authorization": f"Bearer {self.kunde_token}"}
        resp = requests.get(f"{BASE_URL}/api/generators/stats/overview", headers=headers)
        
        assert resp.status_code == 200
        stats = resp.json()
        print(f"Kunde stats: total={stats.get('total')}")
        # Kunde should see fewer than 5 (total) in stats if permissions work
        assert stats["total"] < 5, f"Expected total<5 for kunde, got {stats['total']}"
    
    def test_kunde_can_access_assigned_generator_detail(self):
        """Kunde should be able to view details of assigned generators"""
        headers = {"Authorization": f"Bearer {self.kunde_token}"}
        
        # First get the list to find an assigned generator ID
        list_resp = requests.get(f"{BASE_URL}/api/generators", headers=headers)
        assert list_resp.status_code == 200
        generators = list_resp.json()
        
        if len(generators) > 0:
            gen_id = generators[0]["id"]
            detail_resp = requests.get(f"{BASE_URL}/api/generators/{gen_id}", headers=headers)
            assert detail_resp.status_code == 200, f"Failed to get generator detail: {detail_resp.text}"
            detail = detail_resp.json()
            assert detail["id"] == gen_id
            print(f"Kunde can access generator: {detail['name']}")
        else:
            pytest.skip("No generators assigned to kunde")
    
    def test_kunde_cannot_access_unassigned_generator(self):
        """Kunde should not be able to view generators not assigned to them"""
        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        kunde_headers = {"Authorization": f"Bearer {self.kunde_token}"}
        
        # Get all generators as admin
        admin_resp = requests.get(f"{BASE_URL}/api/generators", headers=admin_headers)
        all_generators = admin_resp.json()
        
        # Get kunde's assigned generators
        kunde_resp = requests.get(f"{BASE_URL}/api/generators", headers=kunde_headers)
        kunde_generators = kunde_resp.json()
        kunde_gen_ids = [g["id"] for g in kunde_generators]
        
        # Find a generator not assigned to kunde
        unassigned = [g for g in all_generators if g["id"] not in kunde_gen_ids]
        
        if len(unassigned) > 0:
            unassigned_id = unassigned[0]["id"]
            detail_resp = requests.get(f"{BASE_URL}/api/generators/{unassigned_id}", headers=kunde_headers)
            assert detail_resp.status_code == 403, f"Expected 403 for unassigned generator, got {detail_resp.status_code}"
            print(f"Kunde correctly denied access to unassigned generator")
        else:
            pytest.skip("No unassigned generators to test")


class TestUserPermissionsUpdate:
    """Test updating user permissions via admin API"""
    
    admin_token = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        admin_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert admin_resp.status_code == 200
        self.admin_token = admin_resp.json()["token"]
    
    def test_get_users_shows_generator_monitoring_permissions(self):
        """Users list should include generator_monitoring permissions"""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/users", headers=headers)
        
        assert resp.status_code == 200
        users = resp.json()
        
        # Find kunde user
        kunde_user = next((u for u in users if u["email"] == "kunde@test.com"), None)
        assert kunde_user is not None, "kunde@test.com not found in users list"
        
        # Check apps structure
        apps = kunde_user.get("apps", {})
        gm = apps.get("generator_monitoring", {})
        
        print(f"Kunde generator_monitoring settings: {gm}")
        assert "enabled" in gm or gm == {}, "generator_monitoring should have enabled field or be empty"
    
    def test_update_user_generator_monitoring_permissions(self):
        """Admin should be able to update user's generator_monitoring permissions"""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Get all users to find kunde's ID
        users_resp = requests.get(f"{BASE_URL}/api/users", headers=headers)
        users = users_resp.json()
        kunde_user = next((u for u in users if u["email"] == "kunde@test.com"), None)
        
        if kunde_user:
            user_id = kunde_user["id"]
            
            # Get all generators to get IDs
            gens_resp = requests.get(f"{BASE_URL}/api/generators", headers=headers)
            generators = gens_resp.json()
            gen_ids = [g["id"] for g in generators[:3]]  # Take first 3 generators
            
            # Update user with new permissions
            update_data = {
                "name": kunde_user["name"],
                "role": kunde_user["role"],
                "is_active": True,
                "apps": {
                    "filesharing": kunde_user.get("apps", {}).get("filesharing", {"enabled": False}),
                    "generator_monitoring": {
                        "enabled": True,
                        "access_all": False,
                        "generator_ids": gen_ids
                    }
                }
            }
            
            update_resp = requests.put(f"{BASE_URL}/api/users/{user_id}", headers=headers, json=update_data)
            assert update_resp.status_code == 200, f"Failed to update user: {update_resp.text}"
            
            # Verify the update
            verify_resp = requests.get(f"{BASE_URL}/api/users", headers=headers)
            updated_users = verify_resp.json()
            updated_kunde = next((u for u in updated_users if u["email"] == "kunde@test.com"), None)
            
            gm = updated_kunde.get("apps", {}).get("generator_monitoring", {})
            assert gm.get("enabled") == True
            assert gm.get("access_all") == False
            assert len(gm.get("generator_ids", [])) == 3
            print(f"Successfully updated kunde with {len(gen_ids)} generator permissions")


class TestUIColorTheme:
    """Verify backend returns correct data for UI theme verification"""
    
    admin_token = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        admin_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert admin_resp.status_code == 200
        self.admin_token = admin_resp.json()["token"]
    
    def test_generators_list_returns_data_for_dashboard(self):
        """Generator list should return all required fields for dashboard"""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/generators", headers=headers)
        
        assert resp.status_code == 200
        generators = resp.json()
        assert len(generators) > 0
        
        gen = generators[0]
        # Verify required fields for dashboard cards
        required_fields = ["id", "name", "serial_number", "model", "status", "location_name"]
        for field in required_fields:
            assert field in gen, f"Missing field: {field}"
        
        print(f"Generator {gen['name']} has all required fields")
    
    def test_generator_detail_returns_data_for_detail_page(self):
        """Generator detail should return all required fields for detail page"""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Get list first
        list_resp = requests.get(f"{BASE_URL}/api/generators", headers=headers)
        generators = list_resp.json()
        
        if len(generators) > 0:
            gen_id = generators[0]["id"]
            detail_resp = requests.get(f"{BASE_URL}/api/generators/{gen_id}", headers=headers)
            
            assert detail_resp.status_code == 200
            detail = detail_resp.json()
            
            # Verify required fields for detail page
            required_fields = ["id", "name", "serial_number", "model", "status", 
                            "location_name", "latest_telemetry", "api_key"]
            for field in required_fields:
                assert field in detail, f"Missing field: {field}"
            
            print(f"Generator detail for {detail['name']} has all required fields")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
