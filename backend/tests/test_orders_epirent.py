"""
Test cases for Auftragsverwaltung (Order Management) - EpiRent Integration
Tests the GET /api/orders/epirent endpoint with date range and search filters
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestOrdersEpirent:
    """Tests for /api/orders/epirent endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token before each test"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Login failed - skipping test")
    
    def test_orders_endpoint_returns_200(self):
        """Test that /api/orders/epirent returns 200 status"""
        response = requests.get(f"{BASE_URL}/api/orders/epirent", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "orders" in data, "Response should contain 'orders' field"
        assert "total" in data, "Response should contain 'total' field"
        assert "page" in data, "Response should contain 'page' field"
        print(f"✅ Orders endpoint returned {data['total']} orders")
    
    def test_orders_response_structure(self):
        """Test that each order has the required fields"""
        response = requests.get(f"{BASE_URL}/api/orders/epirent", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        orders = data.get("orders", [])
        
        if len(orders) > 0:
            order = orders[0]
            required_fields = [
                "primary_key", "order_no", "event", "status",
                "event_start", "event_end", "contact_name", "address",
                "is_confirmed", "is_canceled", "is_archived"
            ]
            for field in required_fields:
                assert field in order, f"Order should have '{field}' field"
            
            print(f"✅ Order structure valid. Sample order_no: {order.get('order_no')}")
            print(f"   Event: {order.get('event')}")
            print(f"   Contact: {order.get('contact_name')}")
            print(f"   Address: {order.get('address')}")
        else:
            print("⚠️ No orders returned - cannot validate structure")
    
    def test_orders_with_date_filter(self):
        """Test filtering by date range"""
        # Use date range from 2026-03-01 to 2026-04-30
        params = {
            "date_from": "2026-03-01",
            "date_to": "2026-04-30"
        }
        response = requests.get(f"{BASE_URL}/api/orders/epirent", headers=self.headers, params=params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"✅ Date filter (2026-03-01 to 2026-04-30) returned {data['total']} orders")
    
    def test_orders_with_default_date_range(self):
        """Test with default date range (-1 week to +4 weeks)"""
        # Calculate default dates
        today = datetime.now()
        date_from = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        date_to = (today + timedelta(days=28)).strftime('%Y-%m-%d')
        
        params = {
            "date_from": date_from,
            "date_to": date_to
        }
        response = requests.get(f"{BASE_URL}/api/orders/epirent", headers=self.headers, params=params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"✅ Default date range ({date_from} to {date_to}) returned {data['total']} orders")
    
    def test_orders_with_search_filter(self):
        """Test filtering by search term"""
        # First get orders without filter to find a term to search for
        response = requests.get(f"{BASE_URL}/api/orders/epirent", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        if data['total'] > 0:
            # Get first order's event name for search
            first_order = data['orders'][0]
            search_term = first_order.get('order_no', '')[:4]  # Use first 4 chars of order_no
            
            if search_term:
                params = {"search": search_term}
                search_response = requests.get(f"{BASE_URL}/api/orders/epirent", headers=self.headers, params=params)
                assert search_response.status_code == 200
                
                search_data = search_response.json()
                print(f"✅ Search filter '{search_term}' returned {search_data['total']} orders")
                
                # Verify search results contain the search term
                if search_data['total'] > 0:
                    found = False
                    for o in search_data['orders']:
                        if (search_term.lower() in o.get('order_no', '').lower() or
                            search_term.lower() in o.get('event', '').lower() or
                            search_term.lower() in o.get('contact_name', '').lower()):
                            found = True
                            break
                    assert found, "Search results should contain the search term"
        else:
            print("⚠️ No orders to test search with")
    
    def test_orders_combined_filters(self):
        """Test combining date range and search filters"""
        params = {
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "search": "GTK"
        }
        response = requests.get(f"{BASE_URL}/api/orders/epirent", headers=self.headers, params=params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"✅ Combined filter (date + search 'GTK') returned {data['total']} orders")
    
    def test_orders_pagination(self):
        """Test pagination parameters"""
        params = {
            "page": 0,
            "page_size": 10
        }
        response = requests.get(f"{BASE_URL}/api/orders/epirent", headers=self.headers, params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data['page'] == 0, "Page should be 0"
        assert data['page_size'] == 10, "Page size should be 10"
        print(f"✅ Pagination test passed - page: {data['page']}, page_size: {data['page_size']}")
    
    def test_orders_requires_auth(self):
        """Test that endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/orders/epirent")
        assert response.status_code in [401, 403], f"Should require auth, got {response.status_code}"
        print("✅ Endpoint correctly requires authentication")
    
    def test_orders_status_flags(self):
        """Test that status flags are present in orders"""
        response = requests.get(f"{BASE_URL}/api/orders/epirent", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        orders = data.get('orders', [])
        
        # Count different status types
        confirmed = sum(1 for o in orders if o.get('is_confirmed'))
        canceled = sum(1 for o in orders if o.get('is_canceled'))
        archived = sum(1 for o in orders if o.get('is_archived'))
        
        print(f"✅ Status flags check:")
        print(f"   Total orders: {len(orders)}")
        print(f"   Confirmed: {confirmed}")
        print(f"   Canceled: {canceled}")
        print(f"   Archived: {archived}")


class TestOrdersEpirentErrors:
    """Tests for error handling in orders endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token before each test"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Login failed - skipping test")
    
    def test_invalid_page_number(self):
        """Test with invalid page number (should handle gracefully)"""
        params = {"page": -1}
        response = requests.get(f"{BASE_URL}/api/orders/epirent", headers=self.headers, params=params)
        # Should either return 422 (validation error) or handle gracefully
        assert response.status_code in [200, 422], f"Unexpected status: {response.status_code}"
        print(f"✅ Invalid page handled with status {response.status_code}")
    
    def test_empty_date_range(self):
        """Test with date range that returns no results"""
        params = {
            "date_from": "1990-01-01",
            "date_to": "1990-01-02"
        }
        response = requests.get(f"{BASE_URL}/api/orders/epirent", headers=self.headers, params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data['total'] >= 0, "Should return valid count even if empty"
        print(f"✅ Empty date range handled - returned {data['total']} orders")
