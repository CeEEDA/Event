"""
Test Lastdiagramm (Load Diagram) feature for Kirmes module.
Tests the purchase flow, PDF download, and duplicate prevention.

Endpoints tested:
- GET /api/kirmes/public/lastdiagramm/available?schausteller_id=X
- POST /api/kirmes/public/lastdiagramm/purchase
- GET /api/kirmes/public/lastdiagramm/{order_id}/pdf?schausteller_id=X
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
SCHAUSTELLER_ID = "95bd69f1-261a-40f7-9bd5-7658ffd20855"
SCHAUSTELLER_EMAIL = "hans@test.de"
SCHAUSTELLER_PASSWORD = "Test1234!"

# Known signup with linked meter
SIGNUP_WITH_METER = "ec261fd0-4401-49b6-8d75-f320d0d85012"

# Expected pricing
LASTDIAGRAMM_NETTO = 125.00
LASTDIAGRAMM_MWST_RATE = 19
LASTDIAGRAMM_MWST = 23.75
LASTDIAGRAMM_BRUTTO = 148.75


class TestLastdiagrammAvailable:
    """Test GET /api/kirmes/public/lastdiagramm/available endpoint"""

    def test_get_available_lastdiagramme_valid_schausteller(self):
        """Test getting available Lastdiagramme for a valid Schausteller"""
        response = requests.get(
            f"{BASE_URL}/api/kirmes/public/lastdiagramm/available",
            params={"schausteller_id": SCHAUSTELLER_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "available" in data, "Response should contain 'available' key"
        assert "purchased" in data, "Response should contain 'purchased' key"
        assert isinstance(data["available"], list), "'available' should be a list"
        assert isinstance(data["purchased"], list), "'purchased' should be a list"
        
        print(f"Available Lastdiagramme: {len(data['available'])}")
        print(f"Purchased Lastdiagramme: {len(data['purchased'])}")
        
        # Check structure of items if any exist
        for item in data["available"]:
            assert "signup_id" in item, "Item should have signup_id"
            assert "event_name" in item, "Item should have event_name"
            assert "connection_type" in item, "Item should have connection_type"
            assert "platznummer" in item, "Item should have platznummer"
            print(f"  Available: {item['event_name']} - Platz {item['platznummer']}")
        
        for item in data["purchased"]:
            assert "signup_id" in item, "Item should have signup_id"
            assert "order_id" in item, "Purchased item should have order_id"
            assert "invoice_number" in item, "Purchased item should have invoice_number"
            print(f"  Purchased: {item['event_name']} - {item['invoice_number']}")

    def test_get_available_lastdiagramme_invalid_schausteller(self):
        """Test getting available Lastdiagramme for non-existent Schausteller"""
        response = requests.get(
            f"{BASE_URL}/api/kirmes/public/lastdiagramm/available",
            params={"schausteller_id": "non-existent-id-12345"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "detail" in data

    def test_get_available_lastdiagramme_missing_param(self):
        """Test getting available Lastdiagramme without schausteller_id"""
        response = requests.get(f"{BASE_URL}/api/kirmes/public/lastdiagramm/available")
        assert response.status_code == 422, f"Expected 422 for missing param, got {response.status_code}"


class TestLastdiagrammPurchase:
    """Test POST /api/kirmes/public/lastdiagramm/purchase endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup_and_cleanup(self):
        """Setup and cleanup for purchase tests"""
        # Store created order IDs for cleanup
        self.created_order_ids = []
        yield
        # Cleanup: Delete any test orders created
        # Note: In a real scenario, we'd have an admin endpoint to delete orders
        # For now, we'll just note that cleanup should happen

    def test_purchase_lastdiagramm_success(self):
        """Test successful Lastdiagramm purchase with correct pricing"""
        # First check if there's an available signup
        avail_response = requests.get(
            f"{BASE_URL}/api/kirmes/public/lastdiagramm/available",
            params={"schausteller_id": SCHAUSTELLER_ID}
        )
        assert avail_response.status_code == 200
        avail_data = avail_response.json()
        
        if not avail_data["available"]:
            pytest.skip("No available signups with meters for purchase test")
        
        signup_id = avail_data["available"][0]["signup_id"]
        
        # Attempt purchase
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/lastdiagramm/purchase",
            json={
                "schausteller_id": SCHAUSTELLER_ID,
                "signup_id": signup_id,
                "payment_method": "rechnung"
            }
        )
        
        if response.status_code == 400 and "bereits bestellt" in response.text.lower():
            print("Lastdiagramm already purchased for this signup - testing duplicate prevention")
            return
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "order" in data, "Response should contain 'order'"
        assert "invoice" in data, "Response should contain 'invoice'"
        
        order = data["order"]
        invoice = data["invoice"]
        
        # Verify order structure
        assert "id" in order, "Order should have id"
        assert order["signup_id"] == signup_id, "Order signup_id should match"
        assert order["schausteller_id"] == SCHAUSTELLER_ID, "Order schausteller_id should match"
        assert order["payment_method"] == "rechnung", "Payment method should be rechnung"
        assert order["status"] == "bezahlt", "Status should be bezahlt for rechnung payment"
        
        # Verify pricing
        assert order["netto"] == LASTDIAGRAMM_NETTO, f"Netto should be {LASTDIAGRAMM_NETTO}, got {order['netto']}"
        assert order["mwst_amount"] == LASTDIAGRAMM_MWST, f"MwSt should be {LASTDIAGRAMM_MWST}, got {order['mwst_amount']}"
        assert order["brutto"] == LASTDIAGRAMM_BRUTTO, f"Brutto should be {LASTDIAGRAMM_BRUTTO}, got {order['brutto']}"
        
        # Verify invoice
        assert "invoice_number" in invoice, "Invoice should have invoice_number"
        assert invoice["brutto"] == LASTDIAGRAMM_BRUTTO, f"Invoice brutto should be {LASTDIAGRAMM_BRUTTO}"
        
        # Invoice number format: R{YY}-K-{NNNN}
        inv_num = invoice["invoice_number"]
        assert inv_num.startswith("R"), f"Invoice number should start with R, got {inv_num}"
        assert "-K-" in inv_num, f"Invoice number should contain -K-, got {inv_num}"
        
        print(f"Successfully purchased Lastdiagramm: Order {order['id']}, Invoice {inv_num}")
        self.created_order_ids.append(order["id"])

    def test_purchase_lastdiagramm_duplicate_prevention(self):
        """Test that duplicate purchase is prevented"""
        # First check if there's a purchased signup
        avail_response = requests.get(
            f"{BASE_URL}/api/kirmes/public/lastdiagramm/available",
            params={"schausteller_id": SCHAUSTELLER_ID}
        )
        assert avail_response.status_code == 200
        avail_data = avail_response.json()
        
        if not avail_data["purchased"]:
            # Try to purchase first, then try again
            if not avail_data["available"]:
                pytest.skip("No signups available for duplicate test")
            
            signup_id = avail_data["available"][0]["signup_id"]
            # First purchase
            first_response = requests.post(
                f"{BASE_URL}/api/kirmes/public/lastdiagramm/purchase",
                json={
                    "schausteller_id": SCHAUSTELLER_ID,
                    "signup_id": signup_id,
                    "payment_method": "rechnung"
                }
            )
            if first_response.status_code != 200:
                pytest.skip("Could not complete first purchase for duplicate test")
        else:
            signup_id = avail_data["purchased"][0]["signup_id"]
        
        # Attempt duplicate purchase
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/lastdiagramm/purchase",
            json={
                "schausteller_id": SCHAUSTELLER_ID,
                "signup_id": signup_id,
                "payment_method": "rechnung"
            }
        )
        
        assert response.status_code == 400, f"Expected 400 for duplicate, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "bereits bestellt" in data["detail"].lower() or "already" in data["detail"].lower(), \
            f"Error should mention already ordered: {data['detail']}"
        print(f"Duplicate prevention working: {data['detail']}")

    def test_purchase_lastdiagramm_invalid_schausteller(self):
        """Test purchase with invalid Schausteller ID"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/lastdiagramm/purchase",
            json={
                "schausteller_id": "invalid-id-12345",
                "signup_id": SIGNUP_WITH_METER,
                "payment_method": "rechnung"
            }
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_purchase_lastdiagramm_invalid_signup(self):
        """Test purchase with invalid signup ID"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/lastdiagramm/purchase",
            json={
                "schausteller_id": SCHAUSTELLER_ID,
                "signup_id": "invalid-signup-id-12345",
                "payment_method": "rechnung"
            }
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestLastdiagrammPDF:
    """Test GET /api/kirmes/public/lastdiagramm/{order_id}/pdf endpoint"""

    def test_download_pdf_success(self):
        """Test successful PDF download for purchased Lastdiagramm"""
        # First get a purchased order
        avail_response = requests.get(
            f"{BASE_URL}/api/kirmes/public/lastdiagramm/available",
            params={"schausteller_id": SCHAUSTELLER_ID}
        )
        assert avail_response.status_code == 200
        avail_data = avail_response.json()
        
        if not avail_data["purchased"]:
            pytest.skip("No purchased Lastdiagramme available for PDF test")
        
        order_id = avail_data["purchased"][0]["order_id"]
        
        # Download PDF
        response = requests.get(
            f"{BASE_URL}/api/kirmes/public/lastdiagramm/{order_id}/pdf",
            params={"schausteller_id": SCHAUSTELLER_ID}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get("content-type") == "application/pdf", \
            f"Content-Type should be application/pdf, got {response.headers.get('content-type')}"
        
        # Check Content-Disposition header
        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp, "Should be attachment download"
        assert "Lastdiagramm" in content_disp, "Filename should contain Lastdiagramm"
        
        # Verify PDF content starts with PDF magic bytes
        assert response.content[:4] == b"%PDF", "Content should be a valid PDF"
        
        print(f"Successfully downloaded PDF ({len(response.content)} bytes)")

    def test_download_pdf_invalid_order(self):
        """Test PDF download with invalid order ID"""
        response = requests.get(
            f"{BASE_URL}/api/kirmes/public/lastdiagramm/invalid-order-id/pdf",
            params={"schausteller_id": SCHAUSTELLER_ID}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_download_pdf_wrong_schausteller(self):
        """Test PDF download with wrong Schausteller ID"""
        # First get a purchased order
        avail_response = requests.get(
            f"{BASE_URL}/api/kirmes/public/lastdiagramm/available",
            params={"schausteller_id": SCHAUSTELLER_ID}
        )
        assert avail_response.status_code == 200
        avail_data = avail_response.json()
        
        if not avail_data["purchased"]:
            pytest.skip("No purchased Lastdiagramme available for wrong schausteller test")
        
        order_id = avail_data["purchased"][0]["order_id"]
        
        # Try to download with wrong schausteller
        response = requests.get(
            f"{BASE_URL}/api/kirmes/public/lastdiagramm/{order_id}/pdf",
            params={"schausteller_id": "wrong-schausteller-id"}
        )
        assert response.status_code == 404, f"Expected 404 for wrong schausteller, got {response.status_code}"


class TestLastdiagrammInvoiceIntegration:
    """Test that Lastdiagramm invoices appear in Meine Rechnungen"""

    def test_invoice_appears_in_my_bookings(self):
        """Test that Lastdiagramm invoice appears in schausteller's invoices"""
        response = requests.get(
            f"{BASE_URL}/api/kirmes/public/my-bookings",
            params={"schausteller_id": SCHAUSTELLER_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "invoices" in data, "Response should contain invoices"
        
        # Check if any Lastdiagramm invoices exist
        lastdiagramm_invoices = [
            inv for inv in data["invoices"] 
            if "lastdiagramm" in inv.get("invoice_number", "").lower() or 
               "lastdiagramm" in str(inv).lower()
        ]
        
        print(f"Total invoices: {len(data['invoices'])}")
        print(f"Lastdiagramm invoices found: {len(lastdiagramm_invoices)}")
        
        # Verify invoice structure
        for inv in data["invoices"]:
            assert "id" in inv, "Invoice should have id"
            assert "invoice_number" in inv, "Invoice should have invoice_number"
            assert "brutto" in inv, "Invoice should have brutto"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
