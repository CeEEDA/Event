"""
Test Kirmes QR Scanner Integration - Iteration 33
Tests:
- POST /api/kirmes/meters/{meter_id}/assign-signup (assign meter to signup via QR scan)
- GET /api/kirmes/meters/{meter_id}/info (get meter info for QR assignment page)
- URL parsing regex validation
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestQrScannerBackend:
    """Test QR Scanner backend endpoints for meter assignment"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin before each test"""
        self.session = requests.Session()
        # Login as admin
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        token = resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    def test_get_meter_info_success(self):
        """GET /api/kirmes/meters/{meter_id}/info returns meter data"""
        # First get an available meter
        meters_resp = self.session.get(f"{BASE_URL}/api/kirmes/emu-meters")
        assert meters_resp.status_code == 200
        meters = meters_resp.json()
        
        if len(meters) == 0:
            pytest.skip("No EMU meters available for testing")
        
        meter = meters[0]
        meter_id = meter["id"]
        
        # Test GET meter info
        info_resp = self.session.get(f"{BASE_URL}/api/kirmes/meters/{meter_id}/info")
        assert info_resp.status_code == 200, f"Failed: {info_resp.text}"
        
        data = info_resp.json()
        # Validate response structure
        assert "id" in data
        assert "meter_name" in data
        assert "device_id" in data
        assert "device_name" in data
        assert "current_assignment" in data  # Can be None or object
        assert "available_signups" in data
        assert isinstance(data["available_signups"], list)
        
        print(f"PASS: GET /api/kirmes/meters/{meter_id}/info returned valid data")
        print(f"  - Meter name: {data.get('meter_name')}")
        print(f"  - Device name: {data.get('device_name')}")
        print(f"  - Current assignment: {data.get('current_assignment')}")
        print(f"  - Available signups: {len(data.get('available_signups', []))} items")
    
    def test_get_meter_info_invalid_id(self):
        """GET /api/kirmes/meters/{meter_id}/info returns 404 for invalid ID"""
        resp = self.session.get(f"{BASE_URL}/api/kirmes/meters/invalid-meter-id-12345/info")
        assert resp.status_code == 404
        print("PASS: GET /api/kirmes/meters/invalid-id/info returns 404")
    
    def test_get_meter_info_unauthenticated(self):
        """GET /api/kirmes/meters/{meter_id}/info requires auth"""
        # Use a fresh session without auth
        session = requests.Session()
        resp = session.get(f"{BASE_URL}/api/kirmes/meters/some-id/info")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("PASS: GET /api/kirmes/meters/{id}/info requires authentication")
        session.close()
    
    def test_assign_meter_to_signup_success(self):
        """POST /api/kirmes/meters/{meter_id}/assign-signup works correctly"""
        # Get an available meter
        meters_resp = self.session.get(f"{BASE_URL}/api/kirmes/emu-meters")
        assert meters_resp.status_code == 200
        meters = meters_resp.json()
        
        if len(meters) == 0:
            pytest.skip("No EMU meters available for testing")
        
        meter = meters[0]
        meter_id = meter["id"]
        
        # Get a signup without linked meter
        events_resp = self.session.get(f"{BASE_URL}/api/kirmes/events")
        assert events_resp.status_code == 200
        events = events_resp.json()
        
        # Find a signup without meter
        target_signup_id = None
        for event in events:
            event_detail = self.session.get(f"{BASE_URL}/api/kirmes/events/{event['id']}").json()
            for signup in event_detail.get("signups", []):
                if not signup.get("emu_meter_id"):
                    target_signup_id = signup["id"]
                    break
            if target_signup_id:
                break
        
        if not target_signup_id:
            pytest.skip("No signups without meters available for testing")
        
        # Test POST assign meter
        assign_resp = self.session.post(
            f"{BASE_URL}/api/kirmes/meters/{meter_id}/assign-signup",
            json={"signup_id": target_signup_id}
        )
        assert assign_resp.status_code == 200, f"Failed: {assign_resp.text}"
        
        data = assign_resp.json()
        assert "message" in data
        print(f"PASS: POST /api/kirmes/meters/{meter_id}/assign-signup succeeded")
        print(f"  - Message: {data.get('message')}")
        
        # Verify the assignment was persisted
        signup_resp = self.session.get(f"{BASE_URL}/api/kirmes/signups/{target_signup_id}")
        assert signup_resp.status_code == 200
        signup_data = signup_resp.json()
        assert signup_data.get("emu_meter_id") == meter_id, "Meter not assigned to signup"
        print(f"  - Verification: Signup now has emu_meter_id={meter_id}")
        
        # Clean up: unlink the meter
        self.session.delete(f"{BASE_URL}/api/kirmes/signups/{target_signup_id}/link-meter")
    
    def test_assign_meter_missing_signup_id(self):
        """POST /api/kirmes/meters/{meter_id}/assign-signup fails without signup_id"""
        meters_resp = self.session.get(f"{BASE_URL}/api/kirmes/emu-meters")
        assert meters_resp.status_code == 200
        meters = meters_resp.json()
        
        if len(meters) == 0:
            pytest.skip("No EMU meters available")
        
        meter_id = meters[0]["id"]
        
        resp = self.session.post(
            f"{BASE_URL}/api/kirmes/meters/{meter_id}/assign-signup",
            json={}
        )
        assert resp.status_code == 400
        print("PASS: POST assign-signup fails with 400 when signup_id missing")
    
    def test_assign_meter_invalid_meter_id(self):
        """POST /api/kirmes/meters/{meter_id}/assign-signup fails for invalid meter"""
        resp = self.session.post(
            f"{BASE_URL}/api/kirmes/meters/invalid-meter-xyz/assign-signup",
            json={"signup_id": "some-signup-id"}
        )
        assert resp.status_code == 404
        print("PASS: POST assign-signup returns 404 for invalid meter ID")
    
    def test_assign_meter_invalid_signup_id(self):
        """POST /api/kirmes/meters/{meter_id}/assign-signup fails for invalid signup"""
        meters_resp = self.session.get(f"{BASE_URL}/api/kirmes/emu-meters")
        assert meters_resp.status_code == 200
        meters = meters_resp.json()
        
        if len(meters) == 0:
            pytest.skip("No EMU meters available")
        
        meter_id = meters[0]["id"]
        
        resp = self.session.post(
            f"{BASE_URL}/api/kirmes/meters/{meter_id}/assign-signup",
            json={"signup_id": "invalid-signup-12345"}
        )
        assert resp.status_code == 404
        print("PASS: POST assign-signup returns 404 for invalid signup ID")


class TestQrCodeUrlParsing:
    """Test the URL parsing regex used in frontend handleQrScan"""
    
    def test_url_parsing_regex(self):
        """Test that the regex correctly extracts meter ID from various URL formats"""
        # The regex from KirmesEventDetailPage.jsx handleQrScan:
        # /meter-zuordnung\/([a-zA-Z0-9_-]+)/
        pattern = re.compile(r'meter-zuordnung/([a-zA-Z0-9_-]+)')
        
        # Test cases: various URL formats
        test_cases = [
            ("https://domain.com/kirmes/meter-zuordnung/82ae1943-bed4-48b8-9375-0b79a34e49a4", "82ae1943-bed4-48b8-9375-0b79a34e49a4"),
            ("/kirmes/meter-zuordnung/abc123", "abc123"),
            ("https://device-telemetry-1.preview.emergentagent.com/kirmes/meter-zuordnung/meter_001", "meter_001"),
            ("http://localhost:3000/kirmes/meter-zuordnung/test-meter-id-123", "test-meter-id-123"),
            # With trailing slash
            ("https://domain.com/kirmes/meter-zuordnung/abc123/", "abc123"),
            # With query params
            ("https://domain.com/kirmes/meter-zuordnung/xyz789?foo=bar", "xyz789"),
        ]
        
        for url, expected_id in test_cases:
            match = pattern.search(url)
            assert match is not None, f"Regex failed to match URL: {url}"
            extracted = match.group(1)
            assert extracted == expected_id, f"Expected {expected_id}, got {extracted} for URL: {url}"
            print(f"PASS: '{url}' -> '{extracted}'")
    
    def test_url_parsing_invalid(self):
        """Test that invalid URLs don't match"""
        pattern = re.compile(r'meter-zuordnung/([a-zA-Z0-9_-]+)')
        
        invalid_urls = [
            "https://domain.com/kirmes/meter-zuordnung/",  # Empty ID
            "https://domain.com/other-path/12345",  # Wrong path
            "random text without URL",
            "",
        ]
        
        for url in invalid_urls:
            match = pattern.search(url)
            # Either no match, or empty capture group
            if match:
                extracted = match.group(1)
                assert extracted == "" or extracted is None, f"Should not extract from: {url}"
            print(f"PASS: Invalid URL correctly not matched: '{url}'")


class TestAvailableSignupsInMeterInfo:
    """Test that GET /api/kirmes/meters/{id}/info returns available signups correctly"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        self.session = requests.Session()
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert resp.status_code == 200
        token = resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    def test_available_signups_structure(self):
        """Test available_signups has correct structure with schausteller and event names"""
        meters_resp = self.session.get(f"{BASE_URL}/api/kirmes/emu-meters")
        assert meters_resp.status_code == 200
        meters = meters_resp.json()
        
        if len(meters) == 0:
            pytest.skip("No meters available")
        
        meter_id = meters[0]["id"]
        info_resp = self.session.get(f"{BASE_URL}/api/kirmes/meters/{meter_id}/info")
        assert info_resp.status_code == 200
        
        data = info_resp.json()
        available = data.get("available_signups", [])
        
        print(f"Available signups count: {len(available)}")
        
        for signup in available[:3]:  # Check first 3
            assert "id" in signup
            assert "event_name" in signup
            assert "schausteller_name" in signup
            print(f"  - Signup {signup['id'][:8]}... : {signup.get('schausteller_name')} @ {signup.get('event_name')}")
        
        print("PASS: available_signups have correct structure")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
