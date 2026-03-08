"""
Iteration 27: Test Order Detail, Deployments, and Generators in Radius
Tests the new features:
- GET /api/orders/epirent/{pk} - Full order detail with geocoding
- PUT /api/orders/epirent/{pk}/settings - Update radius settings
- GET /api/orders/epirent/{pk}/generators - Find generators in radius
- POST /api/orders/epirent/{pk}/deployments - Create deployment entry
- GET /api/orders/epirent/{pk}/deployments - Get deployments for order
- GET /api/orders/deployments/by-generator/{generator_id} - Get deployments by generator
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get auth token by logging in"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "password"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.fail(f"Auth failed: {response.status_code} - {response.text}")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with Bearer token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestOrderDetail:
    """Test GET /api/orders/epirent/{pk} endpoint"""
    
    def test_order_detail_returns_order(self, auth_headers):
        """Order PK 4 should return full detail with coordinates"""
        response = requests.get(f"{BASE_URL}/api/orders/epirent/4", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check required fields exist
        assert "primary_key" in data
        assert "order_no" in data
        assert "event" in data
        assert "address" in data
        assert "center_lat" in data
        assert "center_lng" in data
        assert "radius_km" in data
        
        print(f"Order 4: {data.get('order_no')} - {data.get('event')}")
        print(f"Address: {data.get('address')}")
        print(f"Coordinates: {data.get('center_lat')}, {data.get('center_lng')}")
        print(f"Radius: {data.get('radius_km')} km")
    
    def test_order_detail_has_address_raw(self, auth_headers):
        """Order detail should include raw address components"""
        response = requests.get(f"{BASE_URL}/api/orders/epirent/4", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "address_raw" in data
        assert isinstance(data["address_raw"], dict)
        
    def test_order_detail_not_found(self, auth_headers):
        """Non-existent order should return 404"""
        response = requests.get(f"{BASE_URL}/api/orders/epirent/999999", headers=auth_headers)
        # Should be 404 or similar error
        assert response.status_code in [404, 502], f"Expected 404/502, got {response.status_code}"
    
    def test_order_detail_requires_auth(self):
        """Order detail should require authentication"""
        response = requests.get(f"{BASE_URL}/api/orders/epirent/4")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"


class TestOrderSettings:
    """Test PUT /api/orders/epirent/{pk}/settings endpoint"""
    
    def test_update_radius(self, auth_headers):
        """Should update radius for an order"""
        # Update to 10km
        response = requests.put(
            f"{BASE_URL}/api/orders/epirent/4/settings",
            headers=auth_headers,
            json={"radius_km": 10.0}
        )
        assert response.status_code == 200
        assert response.json().get("ok") == True
        
        # Verify update
        detail = requests.get(f"{BASE_URL}/api/orders/epirent/4", headers=auth_headers)
        assert detail.status_code == 200
        assert detail.json().get("radius_km") == 10.0
        
        # Reset to default 5km
        requests.put(
            f"{BASE_URL}/api/orders/epirent/4/settings",
            headers=auth_headers,
            json={"radius_km": 5.0}
        )
    
    def test_update_requires_auth(self):
        """Settings update should require auth"""
        response = requests.put(
            f"{BASE_URL}/api/orders/epirent/4/settings",
            json={"radius_km": 15.0}
        )
        assert response.status_code in [401, 403]


class TestGeneratorsInRadius:
    """Test GET /api/orders/epirent/{pk}/generators endpoint"""
    
    def test_get_generators_in_radius(self, auth_headers):
        """Should return generators within order radius"""
        response = requests.get(
            f"{BASE_URL}/api/orders/epirent/4/generators",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "generators" in data
        assert isinstance(data["generators"], list)
        
        # Response should include metadata
        if data.get("center_lat"):
            assert "center_lng" in data
            assert "radius_km" in data
        
        print(f"Found {len(data['generators'])} generators in radius")
        for g in data["generators"][:3]:
            print(f"  - {g.get('name')}: {g.get('distance_km')} km")
    
    def test_generators_sorted_by_distance(self, auth_headers):
        """Generators should be sorted by distance (nearest first)"""
        response = requests.get(
            f"{BASE_URL}/api/orders/epirent/4/generators",
            headers=auth_headers
        )
        if response.status_code == 200:
            generators = response.json().get("generators", [])
            if len(generators) >= 2:
                distances = [g.get("distance_km", 0) for g in generators]
                assert distances == sorted(distances), "Generators should be sorted by distance"
    
    def test_generators_without_coordinates(self, auth_headers):
        """Order without geocoded address should return empty list"""
        # Try an order that might not have coordinates
        response = requests.get(
            f"{BASE_URL}/api/orders/epirent/1/generators",
            headers=auth_headers
        )
        # Should still return 200 with empty generators list if no coordinates
        assert response.status_code == 200
        data = response.json()
        assert "generators" in data


class TestDeploymentHistory:
    """Test deployment history CRUD endpoints"""
    
    @pytest.fixture
    def test_deployment_data(self):
        """Sample deployment data for testing"""
        return {
            "generator_id": "test-gen-" + str(uuid.uuid4())[:8],
            "generator_name": "Test Generator for Deployment",
            "started_at": "2026-01-15T08:00:00Z",
            "stopped_at": "2026-01-17T18:00:00Z",
            "operating_hours": 58.0,
            "kwh_start": 15000.0,
            "kwh_end": 15850.0,
            "faults": "",
            "notes": "Test deployment created by iteration 27 tests"
        }
    
    def test_create_deployment(self, auth_headers, test_deployment_data):
        """Should create a deployment entry for an order"""
        response = requests.post(
            f"{BASE_URL}/api/orders/epirent/4/deployments",
            headers=auth_headers,
            json=test_deployment_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert data.get("order_pk") == 4
        assert data.get("generator_id") == test_deployment_data["generator_id"]
        assert data.get("operating_hours") == 58.0
        
        print(f"Created deployment: {data.get('id')}")
        return data["id"]
    
    def test_get_order_deployments(self, auth_headers):
        """Should get all deployments for an order"""
        response = requests.get(
            f"{BASE_URL}/api/orders/epirent/4/deployments",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "deployments" in data
        assert isinstance(data["deployments"], list)
        
        print(f"Order 4 has {len(data['deployments'])} deployments")
    
    def test_get_generator_deployments(self, auth_headers, test_deployment_data):
        """Should get deployments by generator ID"""
        # First create a deployment
        create_resp = requests.post(
            f"{BASE_URL}/api/orders/epirent/4/deployments",
            headers=auth_headers,
            json=test_deployment_data
        )
        assert create_resp.status_code == 200
        
        gen_id = test_deployment_data["generator_id"]
        
        # Now get by generator
        response = requests.get(
            f"{BASE_URL}/api/orders/deployments/by-generator/{gen_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "deployments" in data
        assert len(data["deployments"]) >= 1
        
        # Verify it's the right generator
        assert all(d["generator_id"] == gen_id for d in data["deployments"])
        
        print(f"Generator {gen_id} has {len(data['deployments'])} deployments")
    
    def test_deployment_requires_auth(self):
        """Deployment endpoints should require auth"""
        # POST without auth
        response = requests.post(
            f"{BASE_URL}/api/orders/epirent/4/deployments",
            json={"generator_id": "test", "generator_name": "Test"}
        )
        assert response.status_code in [401, 403]
        
        # GET without auth
        response = requests.get(f"{BASE_URL}/api/orders/epirent/4/deployments")
        assert response.status_code in [401, 403]
        
        # GET by-generator without auth
        response = requests.get(f"{BASE_URL}/api/orders/deployments/by-generator/test-id")
        assert response.status_code in [401, 403]


class TestIntegration:
    """Integration tests for the complete flow"""
    
    def test_full_order_workflow(self, auth_headers):
        """Test complete order → settings → generators → deployments flow"""
        # 1. Get order detail
        order_resp = requests.get(f"{BASE_URL}/api/orders/epirent/4", headers=auth_headers)
        assert order_resp.status_code == 200
        order = order_resp.json()
        
        print(f"Order: {order.get('order_no')} - {order.get('event')}")
        
        # 2. Update radius
        settings_resp = requests.put(
            f"{BASE_URL}/api/orders/epirent/4/settings",
            headers=auth_headers,
            json={"radius_km": 15.0}
        )
        assert settings_resp.status_code == 200
        
        # 3. Get generators in new radius
        gen_resp = requests.get(f"{BASE_URL}/api/orders/epirent/4/generators", headers=auth_headers)
        assert gen_resp.status_code == 200
        generators = gen_resp.json().get("generators", [])
        print(f"Found {len(generators)} generators within 15km")
        
        # 4. Reset radius
        requests.put(
            f"{BASE_URL}/api/orders/epirent/4/settings",
            headers=auth_headers,
            json={"radius_km": 5.0}
        )
        
        # 5. Get deployments
        deploy_resp = requests.get(f"{BASE_URL}/api/orders/epirent/4/deployments", headers=auth_headers)
        assert deploy_resp.status_code == 200
        
        print("Full workflow completed successfully!")
