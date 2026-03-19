"""
Iteration 42 - Mosquitto MQTT Broker Setup Files Testing
Tests the download endpoints for Mosquitto setup files:
- GET /api/download/mosquitto-bundle (ZIP)
- GET /api/download/mosquitto-setup (shell script)
- GET /api/download/mosquitto-config (config file)
Also verifies ZIP contents and file formats.
"""

import pytest
import requests
import os
import io
import zipfile

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


class TestMosquittoDownloads:
    """Tests for Mosquitto MQTT Broker download endpoints"""

    def test_health_check(self):
        """Verify API is up before running other tests"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print(f"Health check passed: {data}")

    def test_mosquitto_bundle_endpoint(self):
        """GET /api/download/mosquitto-bundle returns HTTP 200 ZIP"""
        response = requests.get(f"{BASE_URL}/api/download/mosquitto-bundle")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type is ZIP
        content_type = response.headers.get('Content-Type', '')
        assert 'zip' in content_type.lower() or 'application/zip' in content_type.lower(), f"Expected ZIP content-type, got {content_type}"
        
        # Check Content-Disposition header
        content_disp = response.headers.get('Content-Disposition', '')
        assert 'mosquitto' in content_disp.lower(), f"Expected mosquitto in Content-Disposition, got {content_disp}"
        
        print(f"Mosquitto bundle: status={response.status_code}, content-type={content_type}, size={len(response.content)} bytes")

    def test_mosquitto_bundle_contains_both_files(self):
        """ZIP contains both setup_mosquitto.sh and mosquitto_eventenergie.conf"""
        response = requests.get(f"{BASE_URL}/api/download/mosquitto-bundle")
        assert response.status_code == 200
        
        # Parse ZIP content
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_names = zf.namelist()
            
            # Assert both files are present
            assert "setup_mosquitto.sh" in file_names, f"setup_mosquitto.sh not in ZIP. Files: {file_names}"
            assert "mosquitto_eventenergie.conf" in file_names, f"mosquitto_eventenergie.conf not in ZIP. Files: {file_names}"
            
            print(f"ZIP bundle contains: {file_names}")
            
            # Verify shell script content
            setup_content = zf.read("setup_mosquitto.sh").decode('utf-8')
            assert "#!/bin/bash" in setup_content, "setup_mosquitto.sh should start with shebang"
            assert "Mosquitto" in setup_content, "setup_mosquitto.sh should mention Mosquitto"
            assert "certbot" in setup_content or "Let's Encrypt" in setup_content, "setup_mosquitto.sh should mention certbot or Let's Encrypt"
            
            # Verify config content
            config_content = zf.read("mosquitto_eventenergie.conf").decode('utf-8')
            assert "listener 8883" in config_content, "Config should have MQTTS listener on 8883"
            assert "listener 9883" in config_content, "Config should have WSS listener on 9883"
            assert "listener 1883" in config_content, "Config should have local listener on 1883"
            
            print("ZIP contents verified: both files have correct content")

    def test_mosquitto_setup_endpoint(self):
        """GET /api/download/mosquitto-setup returns HTTP 200 shell script"""
        response = requests.get(f"{BASE_URL}/api/download/mosquitto-setup")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get('Content-Type', '')
        # Should be shell script or octet-stream
        assert any(t in content_type.lower() for t in ['sh', 'shell', 'octet-stream', 'x-sh']), f"Unexpected content-type: {content_type}"
        
        content = response.text
        # Verify shell script structure
        assert "#!/bin/bash" in content, "Should start with bash shebang"
        assert "Mosquitto" in content, "Should mention Mosquitto"
        assert "Let's Encrypt" in content or "certbot" in content, "Should mention Let's Encrypt/certbot"
        assert "apt-get" in content or "apt install" in content, "Should have apt commands"
        assert "8883" in content, "Should mention MQTTS port 8883"
        
        print(f"Mosquitto setup script: status={response.status_code}, size={len(content)} chars")

    def test_mosquitto_config_endpoint(self):
        """GET /api/download/mosquitto-config returns HTTP 200 config file"""
        response = requests.get(f"{BASE_URL}/api/download/mosquitto-config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content = response.text
        
        # Verify config file structure
        assert "listener 8883" in content, "Should have MQTTS listener (port 8883)"
        assert "listener 9883" in content, "Should have WebSockets listener (port 9883)"
        assert "listener 1883" in content, "Should have local listener (port 1883)"
        assert "password_file" in content, "Should reference password file"
        assert "certfile" in content or "tls" in content.lower(), "Should have TLS certificate settings"
        assert "DOMAIN" in content or "letsencrypt" in content.lower(), "Should have domain placeholder or letsencrypt path"
        
        print(f"Mosquitto config file: status={response.status_code}, size={len(content)} chars")
        print(f"Config preview:\n{content[:500]}...")


class TestTankbelegPiRegression:
    """Regression tests: Verify Tankbeleg Pi downloads still work"""

    def test_tankbeleg_pi_bundle_still_works(self):
        """Tankbeleg Pi bundle endpoint still returns valid ZIP"""
        response = requests.get(f"{BASE_URL}/api/download/tankbeleg-pi-bundle")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Parse ZIP
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_names = zf.namelist()
            assert "tankbeleg_pi.py" in file_names, "Should contain tankbeleg_pi.py"
            print(f"Tankbeleg Pi bundle still works. Files: {file_names}")

    def test_tankbeleg_pi_script_still_works(self):
        """Tankbeleg Pi script endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/download/tankbeleg-pi-script")
        assert response.status_code == 200
        assert "parse_receipt" in response.text or "ESC/POS" in response.text
        print("Tankbeleg Pi script endpoint works")


class TestExistingMqttConfig:
    """Regression tests: Existing MQTT config page API"""

    def test_mqtt_config_endpoint_exists(self):
        """MQTT config API should still exist (requires auth)"""
        # This endpoint requires auth, so we just verify it doesn't 404
        response = requests.get(f"{BASE_URL}/api/mqtt/config")
        # Should be 401 (unauthorized) or 403 (forbidden), NOT 404
        assert response.status_code in [401, 403, 422], f"Expected auth error, got {response.status_code}"
        print(f"MQTT config endpoint exists (returns {response.status_code} without auth)")


class TestAdminLoginRegression:
    """Regression test: Admin login still works"""

    def test_admin_login_works(self):
        """Admin can still login with test credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "token" in data, "Should return token"
        assert data["user"]["role"] == "admin", "Should be admin user"
        print(f"Admin login works: user={data['user']['email']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
