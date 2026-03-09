"""
Test Password Policy Implementation - Iteration 38
Tests for P1: Stricter password policy for exhibitor registration

Requirements:
- Min 8 chars, at least 1 digit, 1 uppercase, 1 lowercase, 1 special character
- Reset password for christian.ecker@eventenergie-deutschland.de to 'Kirmes#2026'
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestPasswordValidationPublicEndpoint:
    """Test POST /api/kirmes/public/set-password password validation rules"""

    # Test account for public password set - needs email_verified=True
    test_email = "christian.ecker@eventenergie-deutschland.de"

    def test_weak_password_too_short(self):
        """Password less than 8 chars should be rejected with 400"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/set-password",
            json={"email": self.test_email, "password": "Aa1#abc"}  # 7 chars
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "8 Zeichen" in data.get("detail", ""), f"Expected '8 Zeichen' in error, got: {data}"
        print(f"PASS: Too short password rejected with: {data.get('detail')}")

    def test_password_without_digit(self):
        """Password without digit should be rejected with 400"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/set-password",
            json={"email": self.test_email, "password": "Abcdefgh#"}  # No digit
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Ziffer" in data.get("detail", ""), f"Expected 'Ziffer' in error, got: {data}"
        print(f"PASS: No digit password rejected with: {data.get('detail')}")

    def test_password_without_uppercase(self):
        """Password without uppercase should be rejected with 400"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/set-password",
            json={"email": self.test_email, "password": "abcdefgh1#"}  # No uppercase
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Großbuchstaben" in data.get("detail", ""), f"Expected 'Großbuchstaben' in error, got: {data}"
        print(f"PASS: No uppercase password rejected with: {data.get('detail')}")

    def test_password_without_lowercase(self):
        """Password without lowercase should be rejected with 400"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/set-password",
            json={"email": self.test_email, "password": "ABCDEFGH1#"}  # No lowercase
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Kleinbuchstaben" in data.get("detail", ""), f"Expected 'Kleinbuchstaben' in error, got: {data}"
        print(f"PASS: No lowercase password rejected with: {data.get('detail')}")

    def test_password_without_special_char(self):
        """Password without special character should be rejected with 400"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/set-password",
            json={"email": self.test_email, "password": "Abcdefgh1"}  # No special char
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Sonderzeichen" in data.get("detail", ""), f"Expected 'Sonderzeichen' in error, got: {data}"
        print(f"PASS: No special char password rejected with: {data.get('detail')}")

    def test_valid_password_succeeds(self):
        """Valid password meeting all requirements should succeed"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/set-password",
            json={"email": self.test_email, "password": "Kirmes#2026"}  # All requirements met
        )
        # Should succeed (200) if email_verified=True, or 403 if not verified
        if response.status_code == 403:
            data = response.json()
            assert "nicht bestätigt" in data.get("detail", "").lower() or "nicht bestätigt" in str(data).lower()
            pytest.skip("Email not verified - cannot test successful password set via public endpoint")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
        print(f"PASS: Valid password 'Kirmes#2026' accepted")


class TestPasswordValidationStaffEndpoint:
    """Test POST /api/kirmes/schausteller/{id}/set-password password validation rules"""

    # Admin credentials for staff endpoint
    admin_email = "admin@test.com"
    admin_password = "password"
    test_schausteller_id = "044d0b7a-1f0b-422e-a4df-a5c422a513b8"

    @pytest.fixture(autouse=True)
    def setup_auth(self):
        """Get admin auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": self.admin_email, "password": self.admin_password}
        )
        if response.status_code != 200:
            pytest.skip("Admin login failed - cannot test staff endpoints")
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def test_staff_weak_password_too_short(self):
        """Staff endpoint: Password less than 8 chars should be rejected"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/schausteller/{self.test_schausteller_id}/set-password",
            json={"password": "Aa1#abc"},  # 7 chars
            headers=self.headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "8 Zeichen" in data.get("detail", ""), f"Expected '8 Zeichen' in error, got: {data}"
        print(f"PASS: Staff endpoint - Too short password rejected")

    def test_staff_password_without_digit(self):
        """Staff endpoint: Password without digit should be rejected"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/schausteller/{self.test_schausteller_id}/set-password",
            json={"password": "Abcdefgh#"},  # No digit
            headers=self.headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Ziffer" in data.get("detail", ""), f"Expected 'Ziffer' in error, got: {data}"
        print(f"PASS: Staff endpoint - No digit password rejected")

    def test_staff_password_without_uppercase(self):
        """Staff endpoint: Password without uppercase should be rejected"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/schausteller/{self.test_schausteller_id}/set-password",
            json={"password": "abcdefgh1#"},  # No uppercase
            headers=self.headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Großbuchstaben" in data.get("detail", ""), f"Expected 'Großbuchstaben' in error, got: {data}"
        print(f"PASS: Staff endpoint - No uppercase password rejected")

    def test_staff_password_without_lowercase(self):
        """Staff endpoint: Password without lowercase should be rejected"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/schausteller/{self.test_schausteller_id}/set-password",
            json={"password": "ABCDEFGH1#"},  # No lowercase
            headers=self.headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Kleinbuchstaben" in data.get("detail", ""), f"Expected 'Kleinbuchstaben' in error, got: {data}"
        print(f"PASS: Staff endpoint - No lowercase password rejected")

    def test_staff_password_without_special_char(self):
        """Staff endpoint: Password without special character should be rejected"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/schausteller/{self.test_schausteller_id}/set-password",
            json={"password": "Abcdefgh1"},  # No special char
            headers=self.headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Sonderzeichen" in data.get("detail", ""), f"Expected 'Sonderzeichen' in error, got: {data}"
        print(f"PASS: Staff endpoint - No special char password rejected")

    def test_staff_valid_password_succeeds(self):
        """Staff endpoint: Valid password should succeed and set password"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/schausteller/{self.test_schausteller_id}/set-password",
            json={"password": "Kirmes#2026"},  # All requirements met
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
        data = response.json()
        assert "Passwort wurde gesetzt" in data.get("message", ""), f"Unexpected response: {data}"
        print(f"PASS: Staff endpoint - Valid password 'Kirmes#2026' accepted for schausteller")


class TestLoginWithNewPassword:
    """Test login with the reset password for christian.ecker@eventenergie-deutschland.de"""

    def test_login_with_kirmes_2026(self):
        """Login with christian.ecker@eventenergie-deutschland.de / Kirmes#2026 should succeed"""
        response = requests.post(
            f"{BASE_URL}/api/kirmes/public/login",
            json={
                "email": "christian.ecker@eventenergie-deutschland.de",
                "password": "Kirmes#2026"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
        data = response.json()
        assert data.get("email") == "christian.ecker@eventenergie-deutschland.de", f"Unexpected email in response: {data}"
        print(f"PASS: Login succeeded for christian.ecker@eventenergie-deutschland.de with Kirmes#2026")
        print(f"User name: {data.get('name')}, firma: {data.get('firma')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
