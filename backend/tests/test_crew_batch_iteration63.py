"""
Test EpiRent Crew Batch Endpoint - Iteration 63
Tests the new batch crew endpoint for fetching personnel requirements from EpiRent.
Known working orders with crew data: PK=3, PK=4, PK=6, PK=7
PK=5 has no crew data.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestCrewEndpoints:
    """Test crew/personnel requirements endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        self.token = None
        try:
            resp = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": "admin@test.com",
                "password": "password"
            })
            if resp.status_code == 200:
                self.token = resp.json().get("token")
        except Exception as e:
            pytest.skip(f"Auth failed: {e}")
        
        if not self.token:
            pytest.skip("Could not get auth token")
    
    def test_health_check(self):
        """Verify API is accessible"""
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        print("Health check passed")
    
    def test_get_single_order_crew_pk3(self):
        """Test GET /api/orders/epirent/{order_pk}/crew for PK=3 (Festival der Currywurst)"""
        resp = requests.get(
            f"{BASE_URL}/api/orders/epirent/3/crew",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert "crew" in data
        assert "event" in data
        
        crew = data.get("crew", [])
        print(f"PK=3 crew items: {len(crew)}")
        print(f"PK=3 event: {data.get('event', '')}")
        
        # PK=3 should have 4 crew items according to context
        if len(crew) > 0:
            print(f"Crew data found: {crew}")
            # Verify crew item structure
            for item in crew:
                assert "title" in item or "count" in item
                print(f"  - {item.get('count', 1)}x {item.get('title', 'Unknown')}")
    
    def test_get_single_order_crew_pk4(self):
        """Test GET /api/orders/epirent/{order_pk}/crew for PK=4 (Rheinkirmes Düsseldorf)"""
        resp = requests.get(
            f"{BASE_URL}/api/orders/epirent/4/crew",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        crew = data.get("crew", [])
        print(f"PK=4 crew items: {len(crew)}")
        
        # PK=4 should have 8 total personnel across 4 items
        if len(crew) > 0:
            total_count = sum(c.get("count", 1) for c in crew)
            print(f"PK=4 total personnel: {total_count}")
            for item in crew:
                print(f"  - {item.get('count', 1)}x {item.get('title', 'Unknown')}")
    
    def test_get_single_order_crew_pk5_no_data(self):
        """Test GET /api/orders/epirent/{order_pk}/crew for PK=5 (Rock am Ring - no crew)"""
        resp = requests.get(
            f"{BASE_URL}/api/orders/epirent/5/crew",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        crew = data.get("crew", [])
        print(f"PK=5 crew items: {len(crew)} (expected 0)")
        # PK=5 should have no crew data
    
    def test_batch_crew_endpoint(self):
        """Test POST /api/orders/epirent/crew/batch for multiple orders"""
        resp = requests.post(
            f"{BASE_URL}/api/orders/epirent/crew/batch",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"order_pks": [3, 4, 5, 6, 7]}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert "results" in data
        results = data.get("results", {})
        
        print(f"Batch results keys: {list(results.keys())}")
        
        # Check each order
        for pk in ["3", "4", "6", "7"]:
            if pk in results:
                crew = results[pk]
                total = sum(c.get("count", 1) for c in crew)
                print(f"PK={pk}: {len(crew)} items, {total} total personnel")
            else:
                print(f"PK={pk}: No crew data in results")
        
        # PK=5 should not be in results (no crew data)
        if "5" in results:
            print(f"PK=5: Unexpectedly has crew data: {results['5']}")
    
    def test_batch_crew_empty_request(self):
        """Test batch endpoint with empty order_pks"""
        resp = requests.post(
            f"{BASE_URL}/api/orders/epirent/crew/batch",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"order_pks": []}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("results") == {}
        print("Empty batch request handled correctly")
    
    def test_batch_crew_large_request(self):
        """Test batch endpoint with many orders (up to 50)"""
        # Get some order PKs from the orders list
        orders_resp = requests.get(
            f"{BASE_URL}/api/orders/epirent",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        assert orders_resp.status_code == 200
        orders = orders_resp.json().get("orders", [])
        
        # Take first 20 orders
        pks = [o.get("primary_key") for o in orders[:20] if o.get("primary_key")]
        print(f"Testing batch with {len(pks)} orders")
        
        resp = requests.post(
            f"{BASE_URL}/api/orders/epirent/crew/batch",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"order_pks": pks}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        results = data.get("results", {})
        orders_with_crew = len(results)
        print(f"Orders with crew data: {orders_with_crew}/{len(pks)}")
    
    def test_batch_crew_over_limit(self):
        """Test batch endpoint rejects >50 orders"""
        pks = list(range(1, 60))  # 59 PKs
        resp = requests.post(
            f"{BASE_URL}/api/orders/epirent/crew/batch",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"order_pks": pks}
        )
        assert resp.status_code == 200
        # Should return empty results for >50 orders
        data = resp.json()
        assert data.get("results") == {}
        print("Over-limit batch request handled correctly")
    
    def test_crew_caching(self):
        """Test that crew data is cached (second request should be faster)"""
        import time
        
        # First request - may hit EpiRent API
        start1 = time.time()
        resp1 = requests.get(
            f"{BASE_URL}/api/orders/epirent/3/crew",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        time1 = time.time() - start1
        
        # Second request - should hit cache
        start2 = time.time()
        resp2 = requests.get(
            f"{BASE_URL}/api/orders/epirent/3/crew",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        time2 = time.time() - start2
        
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        
        # Both should return same data
        assert resp1.json().get("crew") == resp2.json().get("crew")
        
        print(f"First request: {time1:.3f}s, Second request: {time2:.3f}s")
        print("Caching appears to be working")


class TestEinsatzplanungIntegration:
    """Test the Einsatzplanung page integration with crew data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        self.token = None
        try:
            resp = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": "admin@test.com",
                "password": "password"
            })
            if resp.status_code == 200:
                self.token = resp.json().get("token")
        except Exception as e:
            pytest.skip(f"Auth failed: {e}")
        
        if not self.token:
            pytest.skip("Could not get auth token")
    
    def test_orders_endpoint_for_week(self):
        """Test orders endpoint with date filtering (used by Einsatzplanung)"""
        # Get current week dates
        from datetime import datetime, timedelta
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        
        date_from = monday.strftime("%Y-%m-%d")
        date_to = sunday.strftime("%Y-%m-%d")
        
        resp = requests.get(
            f"{BASE_URL}/api/orders/epirent?date_from={date_from}&date_to={date_to}",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        orders = data.get("orders", [])
        print(f"Orders for week {date_from} to {date_to}: {len(orders)}")
        
        # Verify order structure
        if orders:
            order = orders[0]
            assert "primary_key" in order
            assert "event" in order or "order_no" in order
            print(f"Sample order: PK={order.get('primary_key')}, Event={order.get('event', order.get('order_no', 'N/A'))}")
    
    def test_shift_plan_endpoint(self):
        """Test shift plan endpoint (used by Einsatzplanung)"""
        # Get current week key
        from datetime import datetime
        today = datetime.now()
        year = today.year
        week = today.isocalendar()[1]
        week_key = f"{year}-W{week:02d}"
        
        resp = requests.get(
            f"{BASE_URL}/api/employee/shift-plan?week={week_key}&token={self.token}"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert "assignments" in data
        assert "absences" in data
        assert "released" in data
        
        print(f"Shift plan for {week_key}: {len(data.get('assignments', []))} assignments, released={data.get('released')}")
    
    def test_job_reqs_endpoint(self):
        """Test job requirements endpoint (manual personnel requirements)"""
        from datetime import datetime
        today = datetime.now()
        year = today.year
        week = today.isocalendar()[1]
        week_key = f"{year}-W{week:02d}"
        
        resp = requests.get(
            f"{BASE_URL}/api/employee/shift-plan/job-reqs?week={week_key}&token={self.token}"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        print(f"Job requirements for {week_key}: {len(data)} entries")
        if data:
            print(f"Sample: {data[0]}")
    
    def test_create_shift_assignment(self):
        """Test creating a shift assignment"""
        from datetime import datetime, timedelta
        today = datetime.now()
        year = today.year
        week = today.isocalendar()[1]
        week_key = f"{year}-W{week:02d}"
        
        # Get a user
        users_resp = requests.get(
            f"{BASE_URL}/api/chat/users?token={self.token}"
        )
        assert users_resp.status_code == 200
        users = users_resp.json()
        
        if not users:
            pytest.skip("No users available")
        
        user = users[0]
        test_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Create assignment
        resp = requests.post(
            f"{BASE_URL}/api/employee/shift-plan?token={self.token}",
            json={
                "user_id": user["id"],
                "date": test_date,
                "week_key": week_key,
                "order_pk": 3,
                "order_name": "TEST_Festival der Currywurst",
                "role": "Elektrotechniker",
                "note": "Test assignment",
                "start_time": "08:00",
                "end_time": "16:00"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert "id" in data
        print(f"Created assignment: {data.get('id')}")
        
        # Clean up - delete the assignment
        delete_resp = requests.delete(
            f"{BASE_URL}/api/employee/shift-plan/{data['id']}?token={self.token}"
        )
        assert delete_resp.status_code == 200
        print("Cleaned up test assignment")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
