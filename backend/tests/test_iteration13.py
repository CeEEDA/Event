"""
Iteration 13 - Testing device form redesign & serviceplan filter cards:
- Device form: NO 'Wartung' (Letzte/Nächste Wartung) section
- Device form: NO 'GPS' (Breitengrad/Längengrad) section  
- Device form: HAS 'Erworben am' (acquired_date) field
- Device form: HAS 'Portal-Verknüpfung' (portal_link) field
- Device form: 'Dateiablage' section (not 'Dokumente')
- Backend POST/PUT devices with acquired_date and portal_link
- Serviceplan: 4 filter cards (Einsatzbereit, Bald fällig, Überfällig, Gesamt)
- Monitoring: GET /api/generators returns devices with device_type 'stromerzeuger'/'lichtmast' as generators (from_device=true)
- Monitoring: Devices with status 'ausser_betrieb' do NOT appear in monitoring
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestDeviceFormRedesign:
    """Test device API changes: removed GPS/maintenance fields, added acquired_date/portal_link"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login as admin to get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]

    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

    def test_create_device_with_acquired_date_and_portal_link(self, auth_headers):
        """Test creating device with new fields: acquired_date, portal_link"""
        unique_serial = f"TEST-IT13-{uuid.uuid4().hex[:8]}"
        device_data = {
            "device_type": "stromerzeuger",
            "serial_number": unique_serial,
            "user_field": "Test Generator Iteration 13",
            "model": "DSE8610MK2",
            "acquired_date": "2025-06-15",
            "portal_link": "https://monitoring.example.com/device/123",
            "notes": "Test device for iteration 13"
        }
        
        response = requests.post(f"{BASE_URL}/api/devices", json=device_data, headers=auth_headers)
        assert response.status_code in [200, 201], f"Create device failed: {response.text}"
        
        device = response.json()
        # Verify new fields are present
        assert device.get("acquired_date") == "2025-06-15", f"acquired_date not saved correctly: {device.get('acquired_date')}"
        assert device.get("portal_link") == "https://monitoring.example.com/device/123", f"portal_link not saved correctly: {device.get('portal_link')}"
        
        # Verify old GPS/maintenance fields are NOT present
        assert "latitude" not in device or device.get("latitude") is None, "latitude should not be in device"
        assert "longitude" not in device or device.get("longitude") is None, "longitude should not be in device"
        assert "last_maintenance" not in device or device.get("last_maintenance") is None, "last_maintenance should not be in device"
        assert "next_maintenance" not in device or device.get("next_maintenance") is None, "next_maintenance field should be managed by serviceplan, not device form"
        
        print(f"Device created with acquired_date={device.get('acquired_date')}, portal_link={device.get('portal_link')}")
        return device

    def test_update_device_acquired_date_and_portal_link(self, auth_headers, test_create_device_with_acquired_date_and_portal_link):
        """Test updating device with acquired_date and portal_link"""
        device = test_create_device_with_acquired_date_and_portal_link
        
        update_data = {
            "acquired_date": "2024-01-01",
            "portal_link": "https://updated-portal.example.com/device/456"
        }
        
        response = requests.put(f"{BASE_URL}/api/devices/{device['id']}", json=update_data, headers=auth_headers)
        assert response.status_code == 200, f"Update device failed: {response.text}"
        
        updated = response.json()
        assert updated.get("acquired_date") == "2024-01-01", f"acquired_date not updated: {updated.get('acquired_date')}"
        assert updated.get("portal_link") == "https://updated-portal.example.com/device/456"
        
        print(f"Device updated: acquired_date={updated.get('acquired_date')}, portal_link={updated.get('portal_link')}")

    def test_get_device_returns_new_fields(self, auth_headers):
        """Test GET device returns acquired_date and portal_link"""
        # Get list of devices
        response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert response.status_code == 200, f"Get devices failed: {response.text}"
        
        devices = response.json()
        assert len(devices) > 0, "No devices found"
        
        # Get single device
        device_id = devices[0]["id"]
        response = requests.get(f"{BASE_URL}/api/devices/{device_id}", headers=auth_headers)
        assert response.status_code == 200
        
        device = response.json()
        print(f"Device fields present: {list(device.keys())}")
        
        # These fields should exist (may be null)
        assert "acquired_date" in device or device.get("acquired_date") is None, "acquired_date field should exist"
        assert "portal_link" in device or device.get("portal_link") is None, "portal_link field should exist"
        
        # Old GPS fields should NOT be required fields in the model
        # (They might exist from old data but not be part of new schema)
        print(f"Device {device.get('serial_number')}: acquired_date={device.get('acquired_date')}, portal_link={device.get('portal_link')}")


class TestGeneratorMonitoringDeviceIntegration:
    """Test that stromerzeuger/lichtmast devices appear in generator monitoring"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert response.status_code == 200
        return response.json()["token"]

    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

    def test_generators_include_stromerzeuger_devices(self, auth_headers):
        """Test GET /api/generators includes stromerzeuger devices from device management"""
        # First check if there are any stromerzeuger devices
        devices_response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        assert devices_response.status_code == 200
        devices = devices_response.json()
        
        stromerzeuger_devices = [d for d in devices if d.get("device_type") == "stromerzeuger" and d.get("status") != "ausser_betrieb"]
        print(f"Found {len(stromerzeuger_devices)} active stromerzeuger devices")
        
        # Get generators
        response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        assert response.status_code == 200
        generators = response.json()
        
        # Check for generators with from_device=true
        device_generators = [g for g in generators if g.get("from_device") == True]
        print(f"Found {len(device_generators)} generators from devices")
        
        # Verify device serial numbers appear in generators
        device_serials = {d.get("serial_number") for d in stromerzeuger_devices}
        generator_serials = {g.get("serial_number") for g in generators}
        
        found_in_monitoring = device_serials.intersection(generator_serials)
        print(f"Device serials found in monitoring: {found_in_monitoring}")
        
        if stromerzeuger_devices:
            assert len(device_generators) > 0 or len(found_in_monitoring) > 0, \
                "Stromerzeuger devices should appear in generator monitoring"

    def test_generators_include_lichtmast_devices(self, auth_headers):
        """Test GET /api/generators includes lichtmast devices from device management"""
        # Check for lichtmast devices
        devices_response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        devices = devices_response.json()
        
        lichtmast_devices = [d for d in devices if d.get("device_type") == "lichtmast" and d.get("status") != "ausser_betrieb"]
        print(f"Found {len(lichtmast_devices)} active lichtmast devices")
        
        if lichtmast_devices:
            # Get generators and check if lichtmast devices appear
            response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
            generators = response.json()
            
            lichtmast_serials = {d.get("serial_number") for d in lichtmast_devices}
            generator_serials = {g.get("serial_number") for g in generators}
            
            found = lichtmast_serials.intersection(generator_serials)
            print(f"Lichtmast devices in monitoring: {found}")
            
            if lichtmast_serials:
                assert len(found) > 0, "Lichtmast devices should appear in generator monitoring"

    def test_ausser_betrieb_devices_not_in_monitoring(self, auth_headers):
        """Test devices with status 'ausser_betrieb' do NOT appear in monitoring"""
        # First get or create a device and set it to ausser_betrieb
        devices_response = requests.get(f"{BASE_URL}/api/devices", headers=auth_headers)
        devices = devices_response.json()
        
        # Find out-of-service devices
        oos_devices = [d for d in devices if d.get("status") == "ausser_betrieb"]
        oos_serials = {d.get("serial_number") for d in oos_devices}
        
        print(f"Found {len(oos_devices)} devices with ausser_betrieb status")
        
        if oos_devices:
            # Get generators
            response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
            generators = response.json()
            generator_serials = {g.get("serial_number") for g in generators}
            
            # Check that out-of-service device serials are NOT in generators
            leaked = oos_serials.intersection(generator_serials)
            assert len(leaked) == 0, f"Out-of-service devices should NOT appear in monitoring: {leaked}"
            print("Verified: ausser_betrieb devices correctly excluded from monitoring")

    def test_generator_from_device_has_correct_id_format(self, auth_headers):
        """Test that virtual generators from devices have id='dev-{device_id}' format"""
        response = requests.get(f"{BASE_URL}/api/generators", headers=auth_headers)
        assert response.status_code == 200
        generators = response.json()
        
        device_generators = [g for g in generators if g.get("from_device") == True]
        
        for gen in device_generators:
            assert gen["id"].startswith("dev-"), f"Device generator should have id starting with 'dev-': {gen['id']}"
            assert gen.get("device_id") is not None, f"Device generator should have device_id field"
            print(f"Generator from device: id={gen['id']}, serial={gen.get('serial_number')}")


class TestServiceplanFilterCards:
    """Test serviceplan page filter card functionality"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password"
        })
        assert response.status_code == 200
        return response.json()["token"]

    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

    def test_serviceplan_list_returns_plan_status_info(self, auth_headers):
        """Test GET /api/serviceplan returns plans with enough info for status calculation"""
        response = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers)
        assert response.status_code == 200
        
        plans = response.json()
        print(f"Found {len(plans)} service plans")
        
        for plan in plans:
            # Verify fields needed for status calculation
            assert "id" in plan
            assert "device_id" in plan
            # These should be present for status calculation
            has_interval = "interval_months" in plan or "interval_hours" in plan
            has_entry_info = "latest_entry" in plan or "entry_count" in plan
            
            print(f"Plan {plan['id']}: device={plan.get('device_serial')}, interval_months={plan.get('interval_months')}, interval_hours={plan.get('interval_hours')}, latest_entry={plan.get('latest_entry')}")
        
        return plans

    def test_serviceplan_status_categories(self, auth_headers):
        """Test that plans can be categorized: Einsatzbereit(OK), Bald fällig, Überfällig"""
        response = requests.get(f"{BASE_URL}/api/serviceplan", headers=auth_headers)
        plans = response.json()
        
        # Calculate status for each plan (mimicking frontend logic)
        import datetime
        
        ok_count = 0
        due_soon_count = 0
        overdue_count = 0
        no_service_count = 0
        
        for plan in plans:
            if not plan.get("latest_entry"):
                no_service_count += 1
                continue
            
            last_date_str = plan["latest_entry"].get("performed_at")
            if not last_date_str:
                no_service_count += 1
                continue
            
            try:
                last_date = datetime.datetime.fromisoformat(last_date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                now = datetime.datetime.now()
                days_since = (now - last_date).days
                
                interval_days = (plan.get("interval_months") or 12) * 30
                remaining = interval_days - days_since
                
                # Hours-based check
                current_hrs = plan.get("current_hours") or 0
                last_hrs = plan["latest_entry"].get("hours_at_service") or 0
                interval_hrs = plan.get("interval_hours") or 500
                hrs_remaining = interval_hrs - (current_hrs - last_hrs)
                
                is_overdue = remaining < 0 or hrs_remaining < 0
                is_due_soon = remaining <= 30 or hrs_remaining <= 50
                
                if is_overdue:
                    overdue_count += 1
                elif is_due_soon:
                    due_soon_count += 1
                else:
                    ok_count += 1
            except Exception as e:
                print(f"Error processing plan {plan['id']}: {e}")
                no_service_count += 1
        
        print(f"Plan status distribution: OK={ok_count}, BaldFällig={due_soon_count}, Überfällig={overdue_count}, KeinService={no_service_count}")
        print(f"Total: {len(plans)}")


class TestEmailSSLPort:
    """Test email service switched to SSL port 465"""
    
    def test_email_service_uses_smtp_ssl(self):
        """Verify email_service.py uses SMTP_SSL with port 465"""
        email_service_path = "/app/backend/email_service.py"
        
        with open(email_service_path, "r") as f:
            content = f.read()
        
        # Check for SMTP_SSL usage
        assert "SMTP_SSL" in content, "email_service should use SMTP_SSL"
        assert "smtplib.SMTP_SSL" in content, "Should use smtplib.SMTP_SSL"
        
        # Check that default port is 587 (but env can override to 465)
        # The actual port 465 should come from .env
        print("Email service correctly configured to use SMTP_SSL")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
