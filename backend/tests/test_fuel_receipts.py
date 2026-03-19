"""
Test Fuel Receipts (Tankbelege) API Endpoints - Iteration 39
Tests all CRUD operations, filtering, confirm/reject workflow, PDF export, and bulk sync
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFuelReceiptsAPI:
    """Test Fuel Receipts CRUD and workflow endpoints"""
    
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
    def auth_headers(self, admin_token):
        """Auth headers for authenticated requests"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    @pytest.fixture(scope="class")
    def test_receipt_id(self, auth_headers):
        """Create a test receipt and return its ID"""
        data = {
            "fuel_type": "diesel",
            "quantity_liters": 150.5,
            "date": "2026-01-15",
            "time": "10:30",
            "location": "TEST_Teststandort",
            "notes": "TEST_pytest receipt"
        }
        response = requests.post(f"{BASE_URL}/api/fuel-receipts", json=data, headers=auth_headers)
        assert response.status_code == 200, f"Create receipt failed: {response.text}"
        receipt = response.json()
        yield receipt["id"]
        # Cleanup
        requests.delete(f"{BASE_URL}/api/fuel-receipts/{receipt['id']}", headers=auth_headers)
    
    # ============== Health and Auth Tests ==============
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        print("PASS: Health endpoint returns healthy status")
    
    def test_login_admin(self, admin_token):
        """Test admin login works"""
        assert admin_token is not None
        print("PASS: Admin login successful, token received")
    
    # ============== GET /api/fuel-receipts (List) ==============
    
    def test_list_fuel_receipts_unauthenticated(self):
        """Test listing receipts without auth returns 401/403"""
        response = requests.get(f"{BASE_URL}/api/fuel-receipts")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: List receipts without auth rejected")
    
    def test_list_fuel_receipts_authenticated(self, auth_headers):
        """Test listing receipts with auth returns 200 and array"""
        response = requests.get(f"{BASE_URL}/api/fuel-receipts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Expected list of receipts"
        print(f"PASS: List receipts returns {len(data)} receipts")
    
    def test_list_fuel_receipts_filter_by_status(self, auth_headers):
        """Test filtering receipts by status"""
        response = requests.get(f"{BASE_URL}/api/fuel-receipts?status=pending", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All returned receipts should have pending status
        for r in data:
            assert r.get("status") == "pending", f"Expected status=pending, got {r.get('status')}"
        print(f"PASS: Filter by status=pending returns {len(data)} receipts")
    
    def test_list_fuel_receipts_filter_by_fuel_type(self, auth_headers):
        """Test filtering receipts by fuel type"""
        response = requests.get(f"{BASE_URL}/api/fuel-receipts?fuel_type=diesel", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        for r in data:
            assert r.get("fuel_type") == "diesel", f"Expected fuel_type=diesel, got {r.get('fuel_type')}"
        print(f"PASS: Filter by fuel_type=diesel returns {len(data)} receipts")
    
    # ============== GET /api/fuel-receipts/stats ==============
    
    def test_get_fuel_receipt_stats_unauthenticated(self):
        """Test stats endpoint without auth returns 401/403"""
        response = requests.get(f"{BASE_URL}/api/fuel-receipts/stats")
        assert response.status_code in [401, 403]
        print("PASS: Stats endpoint without auth rejected")
    
    def test_get_fuel_receipt_stats_authenticated(self, auth_headers):
        """Test stats endpoint returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/fuel-receipts/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data, "Missing 'total' in stats"
        assert "pending" in data, "Missing 'pending' in stats"
        assert "confirmed" in data, "Missing 'confirmed' in stats"
        assert "by_fuel_type" in data, "Missing 'by_fuel_type' in stats"
        assert isinstance(data["total"], int)
        assert isinstance(data["pending"], int)
        assert isinstance(data["confirmed"], int)
        print(f"PASS: Stats endpoint - total: {data['total']}, pending: {data['pending']}, confirmed: {data['confirmed']}")
    
    # ============== POST /api/fuel-receipts (Create) ==============
    
    def test_create_fuel_receipt_unauthenticated(self):
        """Test creating receipt without auth returns 401/403"""
        data = {"fuel_type": "diesel", "quantity_liters": 100, "date": "2026-01-15", "time": "10:00"}
        response = requests.post(f"{BASE_URL}/api/fuel-receipts", json=data)
        assert response.status_code in [401, 403]
        print("PASS: Create receipt without auth rejected")
    
    def test_create_fuel_receipt_valid_diesel(self, auth_headers):
        """Test creating a valid diesel receipt"""
        data = {
            "fuel_type": "diesel",
            "quantity_liters": 200.0,
            "date": "2026-01-15",
            "time": "14:00",
            "location": "TEST_Create Test",
            "notes": "TEST_pytest create test"
        }
        response = requests.post(f"{BASE_URL}/api/fuel-receipts", json=data, headers=auth_headers)
        assert response.status_code == 200, f"Create failed: {response.text}"
        receipt = response.json()
        assert receipt.get("id") is not None, "Missing receipt ID"
        assert receipt.get("fuel_type") == "diesel"
        assert receipt.get("fuel_type_label") == "Diesel"
        assert receipt.get("quantity_liters") == 200.0
        assert receipt.get("status") == "pending"
        print(f"PASS: Created diesel receipt with ID {receipt['id'][:8]}")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/fuel-receipts/{receipt['id']}", headers=auth_headers)
    
    def test_create_fuel_receipt_valid_hvo(self, auth_headers):
        """Test creating a valid HVO receipt"""
        data = {
            "fuel_type": "hvo",
            "quantity_liters": 300.5,
            "date": "2026-01-16",
            "time": "09:15"
        }
        response = requests.post(f"{BASE_URL}/api/fuel-receipts", json=data, headers=auth_headers)
        assert response.status_code == 200
        receipt = response.json()
        assert receipt.get("fuel_type") == "hvo"
        assert receipt.get("fuel_type_label") == "HVO"
        print(f"PASS: Created HVO receipt with ID {receipt['id'][:8]}")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/fuel-receipts/{receipt['id']}", headers=auth_headers)
    
    def test_create_fuel_receipt_valid_heizoel(self, auth_headers):
        """Test creating a valid Heizöl Leicht receipt"""
        data = {
            "fuel_type": "heizoel_leicht",
            "quantity_liters": 500,
            "date": "2026-01-17",
            "time": "16:45"
        }
        response = requests.post(f"{BASE_URL}/api/fuel-receipts", json=data, headers=auth_headers)
        assert response.status_code == 200
        receipt = response.json()
        assert receipt.get("fuel_type") == "heizoel_leicht"
        assert receipt.get("fuel_type_label") == "Heizöl Leicht"
        print(f"PASS: Created Heizöl Leicht receipt with ID {receipt['id'][:8]}")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/fuel-receipts/{receipt['id']}", headers=auth_headers)
    
    def test_create_fuel_receipt_invalid_fuel_type(self, auth_headers):
        """Test creating receipt with invalid fuel type returns 400"""
        data = {
            "fuel_type": "invalid_fuel",
            "quantity_liters": 100,
            "date": "2026-01-15",
            "time": "10:00"
        }
        response = requests.post(f"{BASE_URL}/api/fuel-receipts", json=data, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("PASS: Invalid fuel type rejected with 400")
    
    # ============== GET /api/fuel-receipts/{id} (Read Single) ==============
    
    def test_get_single_receipt(self, auth_headers, test_receipt_id):
        """Test getting a single receipt by ID"""
        response = requests.get(f"{BASE_URL}/api/fuel-receipts/{test_receipt_id}", headers=auth_headers)
        assert response.status_code == 200
        receipt = response.json()
        assert receipt.get("id") == test_receipt_id
        print(f"PASS: Get single receipt {test_receipt_id[:8]} successful")
    
    def test_get_single_receipt_not_found(self, auth_headers):
        """Test getting non-existent receipt returns 404"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/fuel-receipts/{fake_id}", headers=auth_headers)
        assert response.status_code == 404
        print("PASS: Non-existent receipt returns 404")
    
    # ============== PUT /api/fuel-receipts/{id} (Update) ==============
    
    def test_update_fuel_receipt(self, auth_headers, test_receipt_id):
        """Test updating a receipt"""
        update_data = {
            "quantity_liters": 175.5,
            "notes": "Updated by pytest"
        }
        response = requests.put(f"{BASE_URL}/api/fuel-receipts/{test_receipt_id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200, f"Update failed: {response.text}"
        updated = response.json()
        assert updated.get("quantity_liters") == 175.5
        assert updated.get("notes") == "Updated by pytest"
        # Verify with GET
        get_response = requests.get(f"{BASE_URL}/api/fuel-receipts/{test_receipt_id}", headers=auth_headers)
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched.get("quantity_liters") == 175.5
        print(f"PASS: Updated receipt {test_receipt_id[:8]} and verified persistence")
    
    def test_update_fuel_receipt_change_fuel_type(self, auth_headers, test_receipt_id):
        """Test updating fuel type updates the label too"""
        update_data = {"fuel_type": "hvo"}
        response = requests.put(f"{BASE_URL}/api/fuel-receipts/{test_receipt_id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        updated = response.json()
        assert updated.get("fuel_type") == "hvo"
        assert updated.get("fuel_type_label") == "HVO"
        # Revert
        requests.put(f"{BASE_URL}/api/fuel-receipts/{test_receipt_id}", json={"fuel_type": "diesel"}, headers=auth_headers)
        print("PASS: Updating fuel_type also updates fuel_type_label")
    
    def test_update_fuel_receipt_not_found(self, auth_headers):
        """Test updating non-existent receipt returns 404"""
        fake_id = str(uuid.uuid4())
        response = requests.put(f"{BASE_URL}/api/fuel-receipts/{fake_id}", json={"notes": "test"}, headers=auth_headers)
        assert response.status_code == 404
        print("PASS: Update non-existent receipt returns 404")
    
    # ============== POST /api/fuel-receipts/{id}/confirm ==============
    
    def test_confirm_fuel_receipt(self, auth_headers):
        """Test confirming a pending receipt"""
        # Create fresh receipt to confirm
        create_data = {
            "fuel_type": "diesel",
            "quantity_liters": 100,
            "date": "2026-01-18",
            "time": "08:00"
        }
        create_response = requests.post(f"{BASE_URL}/api/fuel-receipts", json=create_data, headers=auth_headers)
        receipt_id = create_response.json()["id"]
        
        # Confirm it
        confirm_response = requests.post(f"{BASE_URL}/api/fuel-receipts/{receipt_id}/confirm", headers=auth_headers)
        assert confirm_response.status_code == 200, f"Confirm failed: {confirm_response.text}"
        
        # Verify status changed
        get_response = requests.get(f"{BASE_URL}/api/fuel-receipts/{receipt_id}", headers=auth_headers)
        receipt = get_response.json()
        assert receipt.get("status") == "confirmed"
        assert receipt.get("confirmed_by") is not None
        assert receipt.get("confirmed_at") is not None
        print(f"PASS: Confirmed receipt {receipt_id[:8]}, status=confirmed, confirmed_by={receipt.get('confirmed_by')}")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/fuel-receipts/{receipt_id}", headers=auth_headers)
    
    def test_confirm_nonexistent_receipt(self, auth_headers):
        """Test confirming non-existent receipt returns 404"""
        fake_id = str(uuid.uuid4())
        response = requests.post(f"{BASE_URL}/api/fuel-receipts/{fake_id}/confirm", headers=auth_headers)
        assert response.status_code == 404
        print("PASS: Confirm non-existent receipt returns 404")
    
    # ============== POST /api/fuel-receipts/{id}/reject ==============
    
    def test_reject_fuel_receipt(self, auth_headers):
        """Test rejecting a pending receipt"""
        # Create fresh receipt to reject
        create_data = {
            "fuel_type": "hvo",
            "quantity_liters": 50,
            "date": "2026-01-19",
            "time": "11:00"
        }
        create_response = requests.post(f"{BASE_URL}/api/fuel-receipts", json=create_data, headers=auth_headers)
        receipt_id = create_response.json()["id"]
        
        # Reject it
        reject_response = requests.post(f"{BASE_URL}/api/fuel-receipts/{receipt_id}/reject", headers=auth_headers)
        assert reject_response.status_code == 200, f"Reject failed: {reject_response.text}"
        
        # Verify status changed
        get_response = requests.get(f"{BASE_URL}/api/fuel-receipts/{receipt_id}", headers=auth_headers)
        receipt = get_response.json()
        assert receipt.get("status") == "rejected"
        print(f"PASS: Rejected receipt {receipt_id[:8]}, status=rejected")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/fuel-receipts/{receipt_id}", headers=auth_headers)
    
    # ============== DELETE /api/fuel-receipts/{id} ==============
    
    def test_delete_fuel_receipt(self, auth_headers):
        """Test deleting a receipt"""
        # Create receipt to delete
        create_data = {
            "fuel_type": "diesel",
            "quantity_liters": 75,
            "date": "2026-01-20",
            "time": "12:00"
        }
        create_response = requests.post(f"{BASE_URL}/api/fuel-receipts", json=create_data, headers=auth_headers)
        receipt_id = create_response.json()["id"]
        
        # Delete it
        delete_response = requests.delete(f"{BASE_URL}/api/fuel-receipts/{receipt_id}", headers=auth_headers)
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        
        # Verify it's gone
        get_response = requests.get(f"{BASE_URL}/api/fuel-receipts/{receipt_id}", headers=auth_headers)
        assert get_response.status_code == 404
        print(f"PASS: Deleted receipt {receipt_id[:8]} and verified removal (404)")
    
    def test_delete_nonexistent_receipt(self, auth_headers):
        """Test deleting non-existent receipt returns 404"""
        fake_id = str(uuid.uuid4())
        response = requests.delete(f"{BASE_URL}/api/fuel-receipts/{fake_id}", headers=auth_headers)
        assert response.status_code == 404
        print("PASS: Delete non-existent receipt returns 404")
    
    # ============== GET /api/fuel-receipts/{id}/pdf ==============
    
    def test_pdf_export_with_token_query_param(self, auth_headers, admin_token, test_receipt_id):
        """Test PDF export using token query parameter"""
        response = requests.get(f"{BASE_URL}/api/fuel-receipts/{test_receipt_id}/pdf?token={admin_token}")
        assert response.status_code == 200, f"PDF export failed: {response.text}"
        assert response.headers.get("content-type") == "application/pdf"
        assert "Content-Disposition" in response.headers
        assert "Tankbeleg_" in response.headers.get("Content-Disposition", "")
        print(f"PASS: PDF export with query token successful, size={len(response.content)} bytes")
    
    def test_pdf_export_with_bearer_header(self, auth_headers, test_receipt_id):
        """Test PDF export using Bearer header"""
        response = requests.get(f"{BASE_URL}/api/fuel-receipts/{test_receipt_id}/pdf", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        print("PASS: PDF export with Bearer header successful")
    
    def test_pdf_export_unauthorized(self, test_receipt_id):
        """Test PDF export without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/fuel-receipts/{test_receipt_id}/pdf")
        assert response.status_code == 401
        print("PASS: PDF export without auth rejected (401)")
    
    def test_pdf_export_nonexistent_receipt(self, admin_token):
        """Test PDF export for non-existent receipt returns 404"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/fuel-receipts/{fake_id}/pdf?token={admin_token}")
        assert response.status_code == 404
        print("PASS: PDF export for non-existent receipt returns 404")
    
    # ============== POST /api/fuel-receipts/sync (Pi Bulk Sync) ==============
    
    def test_sync_endpoint_no_auth_required(self):
        """Test sync endpoint works without auth (for Raspberry Pi)"""
        unique_id = f"pi_test_{uuid.uuid4().hex[:8]}"
        receipts = [{
            "pi_local_id": unique_id,
            "fuel_type": "diesel",
            "quantity_liters": 125.0,
            "date": "2026-01-21",
            "time": "07:30",
            "location": "Pi Test Location"
        }]
        response = requests.post(f"{BASE_URL}/api/fuel-receipts/sync", json=receipts)
        assert response.status_code == 200, f"Sync failed: {response.text}"
        data = response.json()
        assert "created" in data
        assert "skipped" in data
        assert data["created"] == 1
        print(f"PASS: Sync endpoint works without auth, created={data['created']}, skipped={data['skipped']}")
        # Cleanup - need auth for delete
        admin_response = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@test.com", "password": "password"})
        auth_headers = {"Authorization": f"Bearer {admin_response.json()['token']}"}
        # Find and delete the synced receipt
        list_response = requests.get(f"{BASE_URL}/api/fuel-receipts", headers=auth_headers)
        for r in list_response.json():
            if r.get("pi_local_id") == unique_id:
                requests.delete(f"{BASE_URL}/api/fuel-receipts/{r['id']}", headers=auth_headers)
    
    def test_sync_endpoint_dedup(self):
        """Test sync endpoint deduplicates by pi_local_id"""
        unique_id = f"pi_dedup_{uuid.uuid4().hex[:8]}"
        receipts = [{
            "pi_local_id": unique_id,
            "fuel_type": "hvo",
            "quantity_liters": 200,
            "date": "2026-01-22",
            "time": "15:00"
        }]
        # First sync
        response1 = requests.post(f"{BASE_URL}/api/fuel-receipts/sync", json=receipts)
        assert response1.json()["created"] == 1
        
        # Second sync with same pi_local_id
        response2 = requests.post(f"{BASE_URL}/api/fuel-receipts/sync", json=receipts)
        assert response2.json()["created"] == 0
        assert response2.json()["skipped"] == 1
        print("PASS: Sync endpoint correctly deduplicates by pi_local_id")
        # Cleanup
        admin_response = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@test.com", "password": "password"})
        auth_headers = {"Authorization": f"Bearer {admin_response.json()['token']}"}
        list_response = requests.get(f"{BASE_URL}/api/fuel-receipts", headers=auth_headers)
        for r in list_response.json():
            if r.get("pi_local_id") == unique_id:
                requests.delete(f"{BASE_URL}/api/fuel-receipts/{r['id']}", headers=auth_headers)


class TestOrdersForReceiptDropdown:
    """Test /api/orders endpoint used for receipt form dropdown"""
    
    def test_orders_endpoint_exists(self):
        """Test orders endpoint is accessible with auth"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@test.com", "password": "password"})
        token = login_response.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/orders", headers=headers)
        assert response.status_code == 200, f"Orders endpoint failed: {response.status_code} {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Orders endpoint returns {len(data)} orders for dropdown")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
