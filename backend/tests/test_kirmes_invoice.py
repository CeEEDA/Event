"""
Kirmes Invoice Module - Backend API Tests (Iteration 31)
Tests for Invoice CRUD operations, PDF generation, search, and auto-incrementing invoice numbers.

Invoice Number Format: R{YY}-K-{NNNN} (e.g., R26-K-0001)
Line Items: Anschlussgebühr, Stromverbrauch (kWh), Handlingaufschlag
All amounts include 19% MwSt.
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_PREFIX = "TEST_INV_"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "password"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed - skipping authenticated tests")


@pytest.fixture
def admin_client(api_client, admin_token):
    """Session with admin auth header"""
    api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return api_client


# ===================== Invoice List & Search Tests =====================

class TestInvoiceList:
    """Test invoice list and search endpoints"""
    
    def test_list_invoices_requires_auth(self, api_client):
        """Invoices list requires staff auth"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/kirmes/invoices")
        assert response.status_code in [401, 403], "Expected auth error without token"
    
    def test_list_invoices(self, admin_client):
        """Staff can list all invoices"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # If there are invoices, verify structure
        if len(data) > 0:
            invoice = data[0]
            assert "id" in invoice
            assert "invoice_number" in invoice
            assert "event_name" in invoice
            assert "schausteller_firma" in invoice
            assert "netto" in invoice
            assert "brutto" in invoice
            assert "status" in invoice
            assert "invoice_date" in invoice
    
    def test_search_invoices_by_number(self, admin_client):
        """Search invoices by invoice number (R26 prefix)"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices?search=R26")
        assert response.status_code == 200
        
        data = response.json()
        # All results should contain R26 in invoice number or related fields
        for inv in data:
            invoice_num = inv.get("invoice_number", "")
            assert "R26" in invoice_num or "R26" in inv.get("event_name", ""), \
                f"Invoice {invoice_num} should match R26 search"
    
    def test_search_invoices_by_company_name(self, admin_client):
        """Search invoices by company name (Müller)"""
        # URL encode Müller properly
        response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices?search=M%C3%BCller")
        assert response.status_code == 200
        
        data = response.json()
        for inv in data:
            # Should match firma, name, or invoice number
            firma = inv.get("schausteller_firma", "").lower()
            name = inv.get("schausteller_name", "").lower()
            assert "müller" in firma or "müller" in name, \
                f"Invoice should match Müller search, got firma={firma}, name={name}"
    
    def test_search_invoices_by_event_name(self, admin_client):
        """Search invoices by event name"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices?search=Rhein")
        assert response.status_code == 200
        
        data = response.json()
        for inv in data:
            event_name = inv.get("event_name", "").lower()
            assert "rhein" in event_name, f"Invoice event should contain 'Rhein', got {event_name}"


# ===================== Invoice Detail Tests =====================

class TestInvoiceDetail:
    """Test getting full invoice details"""
    
    def test_get_invoice_by_id(self, admin_client):
        """Get full invoice details by ID"""
        # First list invoices to get an ID
        list_response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices")
        if list_response.status_code != 200 or len(list_response.json()) == 0:
            pytest.skip("No invoices available to test")
        
        invoice_id = list_response.json()[0]["id"]
        
        response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices/{invoice_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == invoice_id
        assert "invoice_number" in data
        assert "signup_id" in data
        assert "event_id" in data
        assert "line_items" in data
        assert isinstance(data["line_items"], list)
        assert "netto" in data
        assert "mwst_rate" in data
        assert "mwst_amount" in data
        assert "brutto" in data
        assert "schausteller" in data  # Full schausteller data
        assert "event" in data  # Full event data
    
    def test_get_invoice_by_id_not_found(self, admin_client):
        """Get invoice with non-existent ID returns 404"""
        fake_id = f"nonexistent-{uuid.uuid4().hex}"
        response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices/{fake_id}")
        assert response.status_code == 404
        assert "nicht gefunden" in response.json().get("detail", "").lower()
    
    def test_invoice_line_items_structure(self, admin_client):
        """Verify invoice line items structure"""
        list_response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices")
        if list_response.status_code != 200 or len(list_response.json()) == 0:
            pytest.skip("No invoices available")
        
        invoice_id = list_response.json()[0]["id"]
        response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices/{invoice_id}")
        assert response.status_code == 200
        
        line_items = response.json()["line_items"]
        for item in line_items:
            assert "pos" in item
            assert "description" in item
            assert "quantity" in item
            assert "unit" in item
            assert "unit_price" in item
            assert "total" in item


# ===================== Invoice Number Auto-Increment Tests =====================

class TestInvoiceNumberAutoIncrement:
    """Test invoice number auto-incrementing R{YY}-K-{NNNN} format"""
    
    def test_invoice_number_format(self, admin_client):
        """Verify invoice numbers follow R{YY}-K-{NNNN} format"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices")
        if response.status_code != 200 or len(response.json()) == 0:
            pytest.skip("No invoices available")
        
        import re
        pattern = r'^R\d{2}-K-\d{4}$'  # R26-K-0001 format
        
        for invoice in response.json():
            invoice_number = invoice["invoice_number"]
            assert re.match(pattern, invoice_number), \
                f"Invoice number {invoice_number} doesn't match R{{YY}}-K-{{NNNN}} format"
    
    def test_invoice_numbers_are_unique(self, admin_client):
        """Verify all invoice numbers are unique"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices")
        if response.status_code != 200:
            pytest.skip("Cannot fetch invoices")
        
        invoices = response.json()
        invoice_numbers = [inv["invoice_number"] for inv in invoices]
        
        # All numbers should be unique
        assert len(invoice_numbers) == len(set(invoice_numbers)), \
            "Invoice numbers should be unique"


# ===================== PDF Download Tests =====================

class TestInvoicePDF:
    """Test invoice PDF download"""
    
    def test_download_invoice_pdf(self, admin_client):
        """Download invoice as PDF"""
        # Get an invoice ID
        list_response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices")
        if list_response.status_code != 200 or len(list_response.json()) == 0:
            pytest.skip("No invoices available")
        
        invoice_id = list_response.json()[0]["id"]
        
        response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices/{invoice_id}/pdf")
        assert response.status_code == 200
        assert response.headers.get("Content-Type") == "application/pdf"
        
        # Verify PDF header bytes
        pdf_bytes = response.content
        assert len(pdf_bytes) > 0, "PDF should not be empty"
        assert pdf_bytes[:4] == b'%PDF', "Response should be a valid PDF file"
    
    def test_download_invoice_pdf_not_found(self, admin_client):
        """Download PDF for non-existent invoice returns 404"""
        fake_id = f"nonexistent-{uuid.uuid4().hex}"
        response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices/{fake_id}/pdf")
        assert response.status_code == 404


# ===================== Invoice Generation (Single Signup) Tests =====================

class TestGenerateSingleInvoice:
    """Test generating invoice for single signup - POST /api/kirmes/signups/{id}/invoice"""
    
    def test_generate_invoice_requires_auth(self, api_client):
        """Generate invoice requires staff auth"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/kirmes/signups/fake-id/invoice")
        assert response.status_code in [401, 403, 422]
    
    def test_generate_invoice_signup_not_found(self, admin_client):
        """Generate invoice for non-existent signup returns 404"""
        fake_id = f"nonexistent-{uuid.uuid4().hex}"
        response = admin_client.post(f"{BASE_URL}/api/kirmes/signups/{fake_id}/invoice")
        assert response.status_code == 404
    
    def test_generate_invoice_duplicate_prevention(self, admin_client, api_client):
        """Cannot generate invoice twice for same signup"""
        # Find a signup that already has an invoice
        invoices_response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices")
        if invoices_response.status_code != 200 or len(invoices_response.json()) == 0:
            pytest.skip("No invoices available to test duplicate prevention")
        
        # Get signup_id from existing invoice
        invoice_id = invoices_response.json()[0]["id"]
        detail_response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices/{invoice_id}")
        signup_id = detail_response.json()["signup_id"]
        
        # Try to generate another invoice for this signup
        response = admin_client.post(f"{BASE_URL}/api/kirmes/signups/{signup_id}/invoice")
        assert response.status_code == 400, "Should fail - invoice already exists"
        assert "existiert" in response.json().get("detail", "").lower()


# ===================== Batch Invoice Generation Tests =====================

class TestBatchInvoiceGeneration:
    """Test batch invoice generation - POST /api/kirmes/events/{id}/generate-invoices"""
    
    def test_batch_generate_requires_auth(self, api_client):
        """Batch generate invoices requires staff auth"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/kirmes/events/fake-id/generate-invoices")
        assert response.status_code in [401, 403, 422]
    
    def test_batch_generate_event_not_found(self, admin_client):
        """Batch generate for non-existent event returns 404"""
        fake_id = f"nonexistent-{uuid.uuid4().hex}"
        response = admin_client.post(f"{BASE_URL}/api/kirmes/events/{fake_id}/generate-invoices")
        assert response.status_code == 404
    
    def test_batch_generate_skips_existing_invoices(self, admin_client):
        """Batch generate skips signups that already have invoices"""
        # Find an event that already has invoiced signups
        events_response = admin_client.get(f"{BASE_URL}/api/kirmes/events?status=abgerechnet")
        if events_response.status_code != 200 or len(events_response.json()) == 0:
            pytest.skip("No abgerechnet events available")
        
        event_id = events_response.json()[0]["id"]
        
        # Run batch again - should skip all
        response = admin_client.post(f"{BASE_URL}/api/kirmes/events/{event_id}/generate-invoices")
        assert response.status_code == 200
        
        data = response.json()
        # Should have skipped entries (already invoiced)
        assert "skipped" in data
        assert "generated" in data


# ===================== Invoice Calculation Tests =====================

class TestInvoiceCalculation:
    """Test netto/brutto calculation with 19% MwSt"""
    
    def test_invoice_mwst_calculation(self, admin_client):
        """Verify MwSt calculation is correct (19%)"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices")
        if response.status_code != 200 or len(response.json()) == 0:
            pytest.skip("No invoices available")
        
        # Get full invoice details
        invoice_id = response.json()[0]["id"]
        detail_response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices/{invoice_id}")
        assert detail_response.status_code == 200
        
        invoice = detail_response.json()
        netto = invoice["netto"]
        mwst_rate = invoice["mwst_rate"]
        mwst_amount = invoice["mwst_amount"]
        brutto = invoice["brutto"]
        
        # Verify MwSt is 19%
        assert mwst_rate == 19, f"MwSt rate should be 19%, got {mwst_rate}%"
        
        # Verify calculation
        expected_mwst = round(netto * 19 / 100, 2)
        expected_brutto = round(netto + expected_mwst, 2)
        
        assert mwst_amount == expected_mwst, f"MwSt amount {mwst_amount} != expected {expected_mwst}"
        assert brutto == expected_brutto, f"Brutto {brutto} != expected {expected_brutto}"


# ===================== Invoice Send Email Tests =====================

class TestInvoiceSendEmail:
    """Test invoice send email endpoint - POST /api/kirmes/invoices/{id}/send"""
    
    def test_send_invoice_requires_auth(self, api_client):
        """Send invoice email requires staff auth"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/kirmes/invoices/fake-id/send")
        assert response.status_code in [401, 403, 422]
    
    def test_send_invoice_not_found(self, admin_client):
        """Send email for non-existent invoice returns 404"""
        fake_id = f"nonexistent-{uuid.uuid4().hex}"
        response = admin_client.post(f"{BASE_URL}/api/kirmes/invoices/{fake_id}/send")
        assert response.status_code == 404


# ===================== Integration Test - Full Invoice Flow =====================

class TestInvoiceFullFlow:
    """Integration test: Create event -> Add signup -> Generate invoice -> Verify"""
    
    def test_full_invoice_flow(self, admin_client, api_client):
        """Test complete invoice generation flow"""
        # 1. Create a new event with custom prices for testing
        event_payload = {
            "name": f"{TEST_PREFIX}InvoiceFlowTest_{uuid.uuid4().hex[:6]}",
            "location": "Invoice Test Stadt",
            "start_date": "2027-03-01",
            "end_date": "2027-03-10",
            "use_standard_prices": False,
            "custom_prices": [
                {"connection_type": "Schuko", "price": 30.0, "avg_kwh": 0.0},
                {"connection_type": "16A", "price": 50.0, "avg_kwh": 0.0},
                {"connection_type": "32A", "price": 100.0, "avg_kwh": 0.0},
                {"connection_type": "63A", "price": 200.0, "avg_kwh": 0.0},
                {"connection_type": "125A", "price": 350.0, "avg_kwh": 0.0},
                {"connection_type": "Festanschluss", "price": 500.0, "avg_kwh": 0.0},
            ]
        }
        
        create_response = admin_client.post(f"{BASE_URL}/api/kirmes/events", json=event_payload)
        assert create_response.status_code == 200
        event_id = create_response.json()["id"]
        
        # 2. Release the event
        release_response = admin_client.post(f"{BASE_URL}/api/kirmes/events/{event_id}/release")
        assert release_response.status_code == 200
        
        # 3. Register a schausteller and sign up
        unique_email = f"invflow_{uuid.uuid4().hex[:8]}@test.de"
        sch_payload = {
            "firma": f"{TEST_PREFIX}InvoiceFlowFirma",
            "name": "Invoice Flow Test",
            "strasse": "Teststr 1",
            "plz": "12345",
            "ort": "Teststadt",
            "steuernummer": "DE999888777",
            "email": unique_email,
            "password": "testpass123",
            "telefon": "555-0000",
            "rechnungs_email": unique_email
        }
        reg_response = api_client.post(f"{BASE_URL}/api/kirmes/public/register", json=sch_payload)
        assert reg_response.status_code == 200
        schausteller_id = reg_response.json()["id"]
        
        # 4. Sign up for the event with 32A (100 EUR)
        signup_payload = {
            "event_id": event_id,
            "schausteller_id": schausteller_id,
            "platznummer": f"INVTEST{uuid.uuid4().hex[:4]}",
            "fahrgeschaeft": "Test Fahrgeschaeft",
            "connection_type": "32A",
            "payment_method": "kreditkarte"
        }
        signup_response = api_client.post(f"{BASE_URL}/api/kirmes/public/signup", json=signup_payload)
        assert signup_response.status_code == 200
        signup_id = signup_response.json()["id"]
        
        # 5. Generate invoice
        invoice_response = admin_client.post(f"{BASE_URL}/api/kirmes/signups/{signup_id}/invoice")
        assert invoice_response.status_code == 200
        
        invoice = invoice_response.json()
        assert invoice["signup_id"] == signup_id
        assert "R" in invoice["invoice_number"]
        assert "-K-" in invoice["invoice_number"]
        
        # Verify netto is 100 EUR (32A price)
        assert invoice["netto"] == 100.0, f"Expected netto 100.0, got {invoice['netto']}"
        
        # Verify MwSt (19% of 100 = 19)
        assert invoice["mwst_amount"] == 19.0, f"Expected mwst 19.0, got {invoice['mwst_amount']}"
        
        # Verify brutto (100 + 19 = 119)
        assert invoice["brutto"] == 119.0, f"Expected brutto 119.0, got {invoice['brutto']}"
        
        # 6. Verify invoice appears in list
        list_response = admin_client.get(f"{BASE_URL}/api/kirmes/invoices?event_id={event_id}")
        assert list_response.status_code == 200
        invoices = list_response.json()
        assert len(invoices) == 1
        assert invoices[0]["invoice_number"] == invoice["invoice_number"]
        
        # 7. Cleanup - set event to entwurf and delete
        admin_client.put(f"{BASE_URL}/api/kirmes/events/{event_id}", json={"status": "entwurf"})
        admin_client.delete(f"{BASE_URL}/api/kirmes/events/{event_id}")


# ===================== Cleanup =====================

class TestCleanup:
    """Clean up test data after all tests"""
    
    def test_cleanup_test_events(self, admin_client):
        """Delete test events created during testing"""
        response = admin_client.get(f"{BASE_URL}/api/kirmes/events")
        if response.status_code != 200:
            return
        
        events = response.json()
        deleted_count = 0
        
        for event in events:
            if event["name"].startswith(TEST_PREFIX):
                # Set to entwurf first to allow deletion
                admin_client.put(f"{BASE_URL}/api/kirmes/events/{event['id']}", json={"status": "entwurf"})
                delete_response = admin_client.delete(f"{BASE_URL}/api/kirmes/events/{event['id']}")
                if delete_response.status_code == 200:
                    deleted_count += 1
        
        print(f"Cleaned up {deleted_count} test events")
