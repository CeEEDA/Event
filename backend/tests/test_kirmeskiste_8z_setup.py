"""Test: Kirmeskiste 8Z setup endpoint creates 8 meters with hat_channel,
kwh-offset endpoint stores offsets, OTA registers the new device_type."""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, "/app/backend")

import httpx
from motor.motor_asyncio import AsyncIOMotorClient


async def _run():
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")

    backend_url = "http://localhost:8001"
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    async with httpx.AsyncClient(base_url=backend_url, timeout=30) as http:
        # Login as admin
        r = await http.post("/api/auth/login",
                            json={"email": "admin@test.com", "password": "password"})
        assert r.status_code == 200
        token = r.json()["token"]
        H = {"Authorization": f"Bearer {token}"}

        # Create a Kirmeskiste 8Z device
        sn = f"TEST-KK8Z-{uuid.uuid4().hex[:6].upper()}"
        r1 = await http.post("/api/devices",
                             json={"device_type": "kirmeskiste", "serial_number": sn,
                                   "kirmeskiste_variant": "8z"},
                             headers=H)
        assert r1.status_code == 200, r1.text
        device = r1.json()
        device_id = device["id"]
        print(f"[OK] Created Kirmeskiste 8Z device {sn}")

        try:
            # Trigger 8Z-setup endpoint (admin only)
            r2 = await http.post(
                f"/api/energy-monitoring/devices/{device_id}/kirmeskiste-8z-setup",
                json={"lte_apn": "internet.m2mportal.de", "enable_gps": True},
                headers=H,
            )
            assert r2.status_code == 200, f"Setup failed: {r2.status_code} {r2.text}"
            setup = r2.json()
            assert len(setup["meter_ids"]) == 8, f"Expected 8 meters, got {len(setup['meter_ids'])}"
            assert setup["device_key"], "device_key should be set"
            assert setup["download_url"]
            print(f"[OK] Setup endpoint returned 8 meters and a key {setup['device_key'][:8]}...")

            # Verify the meters in DB have hat_channel 1-8
            meters = await db.emu_meters.find(
                {"device_id": device_id}, {"_id": 0}
            ).sort("hat_channel", 1).to_list(20)
            assert len(meters) == 8
            for i, m in enumerate(meters, start=1):
                assert m["hat_channel"] == i, f"meter {i} channel mismatch: {m}"
                assert m["pulses_per_kwh"] == 1000
                assert m["kwh_offset"] == 0.0
                assert m["meter_type"] == "ABB D11/D13 (S0 Pulse)"
            print(f"[OK] 8 meters in DB, channel 1-8, default 1000 imp/kWh")

            # PUT kwh-offset (staff)
            target_meter = meters[2]  # channel 3
            r3 = await http.put(
                f"/api/energy-monitoring/devices/{device_id}/meters/{target_meter['id']}/kwh-offset",
                json={"kwh_offset": 1234.567},
                headers=H,
            )
            assert r3.status_code == 200, r3.text
            updated = await db.emu_meters.find_one({"id": target_meter["id"]}, {"_id": 0})
            assert abs(updated["kwh_offset"] - 1234.567) < 0.001
            assert updated.get("kwh_offset_updated_by")
            print(f"[OK] kWh-offset PUT works (admin)")

            # GET kwh-offset (Pi - via api_key)
            api_key = setup["device_key"]
            r4 = await http.get(
                f"/api/energy-monitoring/devices/{device_id}/meters/{target_meter['id']}/kwh-offset",
                params={"api_key": api_key},
            )
            assert r4.status_code == 200, r4.text
            assert abs(r4.json()["kwh_offset"] - 1234.567) < 0.001
            print(f"[OK] kWh-offset GET via api_key works (Pi)")

            # Quick-Info zeigt Anfangsstand wenn noch keine Telemetrie da ist
            r4b = await http.get(f"/api/devices/{device_id}/quick-info", headers=H)
            assert r4b.status_code == 200, r4b.text
            qi = r4b.json()
            tgt_reading = next(
                (rd for rd in qi.get("readings", []) if rd.get("meter_id") == target_meter["id"]),
                None,
            )
            assert tgt_reading is not None, "Reading fuer Target-Meter fehlt"
            assert "1234.57 kWh" in tgt_reading["value"], f"Anfangsstand fehlt: {tgt_reading}"
            assert "Anfangsstand" in tgt_reading["value"]
            assert tgt_reading.get("pending_offset") is True
            assert abs(tgt_reading.get("kwh_offset") - 1234.567) < 0.001
            # Andere Meter (offset=0) zeigen "Keine Daten"
            other = next(
                (rd for rd in qi.get("readings", []) if rd.get("meter_id") == meters[0]["id"]),
                None,
            )
            assert other is not None
            assert other["value"] == "Keine Daten"
            assert not other.get("pending_offset")
            # Sortierung: Reihenfolge muss hat_channel 1..8 entsprechen
            channels_order = [
                next((m["hat_channel"] for m in meters if m["id"] == rd["meter_id"]), None)
                for rd in qi["readings"]
            ]
            assert channels_order == [1, 2, 3, 4, 5, 6, 7, 8], f"Falsche Reihenfolge: {channels_order}"
            print(f"[OK] quick-info zeigt Anfangsstand als Fallback + Sortierung K1-K8")

            # Quick-Info: Telemetrie kleiner als Offset -> max(offset, telemetry) wird gezeigt
            from datetime import datetime, timezone
            await db.emu_data.insert_one({
                "device_id": device_id,
                "meter_id": target_meter["id"],
                "ts_utc": datetime.now(timezone.utc).isoformat(),
                "E_imp_kWh": 0.0,
                "P_sum_kW": 0.0,
            })
            r4c = await http.get(f"/api/devices/{device_id}/quick-info", headers=H)
            qi2 = r4c.json()
            tgt2 = next(rd for rd in qi2["readings"] if rd.get("meter_id") == target_meter["id"])
            assert "1234.57 kWh" in tgt2["value"], f"Offset wurde nicht als Fallback verwendet: {tgt2}"
            assert tgt2.get("pending_offset") is True, "pending_offset sollte True sein"
            assert tgt2.get("timestamp"), "timestamp sollte gesetzt sein"
            print(f"[OK] quick-info: max(offset, E_imp_kWh) wenn Pi 0 sendet + pending_offset Flag")

            # Telemetrie groesser als Offset -> echter Wert wird gezeigt, kein Pending mehr
            await db.emu_data.insert_one({
                "device_id": device_id,
                "meter_id": target_meter["id"],
                "ts_utc": datetime.now(timezone.utc).isoformat(),
                "E_imp_kWh": 1300.5,
                "P_sum_kW": 1.2,
            })
            r4d = await http.get(f"/api/devices/{device_id}/quick-info", headers=H)
            qi3 = r4d.json()
            tgt3 = next(rd for rd in qi3["readings"] if rd.get("meter_id") == target_meter["id"])
            assert "1300.50 kWh" in tgt3["value"], f"Echter Wert nicht gezeigt: {tgt3}"
            assert "1.20 kW" in tgt3["value"]
            assert not tgt3.get("pending_offset")
            print(f"[OK] quick-info: echter Telemetrie-Wert wenn > Offset, kein Pending-Flag")
            await db.emu_data.delete_many({"device_id": device_id})

            # Wrong api_key should be 401
            r5 = await http.get(
                f"/api/energy-monitoring/devices/{device_id}/meters/{target_meter['id']}/kwh-offset",
                params={"api_key": "wrong"},
            )
            assert r5.status_code == 401
            print(f"[OK] kWh-offset GET rejects wrong api_key")

            # Verify OTA endpoint registers new device_type
            r6 = await http.get(
                "/api/system/ota/pi/kirmeskiste_8z/check",
                params={"pi_id": str(uuid.uuid4()), "hash": "abc", "version": "0.1"},
            )
            assert r6.status_code == 200, f"OTA check failed: {r6.status_code} {r6.text}"
            data = r6.json()
            assert data["update_available"] is True, "Update should be available (hash mismatch)"
            assert data["file_hash"]
            print(f"[OK] OTA check registered for kirmeskiste_8z")

            # OTA download
            r7 = await http.get(
                "/api/system/ota/pi/kirmeskiste_8z/download",
                params={"pi_id": str(uuid.uuid4())},
            )
            assert r7.status_code == 200
            assert b"kirmeskiste8z" in r7.content.lower()
            print(f"[OK] OTA download returns sync script ({len(r7.content)} bytes)")

            # Setup download_url should serve the bash script
            r8 = await http.get(setup["download_url"])
            assert r8.status_code == 200
            txt = r8.text
            assert "Kirmeskiste 8 Zaehler" in txt
            assert "16inpind" in txt
            assert "internet.m2mportal.de" in txt
            assert device_id in txt
            assert api_key in txt
            # LTE-Spezifika
            assert "/etc/ppp/peers/m2m" in txt, "PPP-Konfig fehlt"
            assert "/etc/chatscripts/m2m-connect" in txt, "Chat-Skript fehlt"
            assert "AT+CPIN=0000" in txt, "SIM-PIN 0000 fehlt im Chat-Skript"
            assert "ATD*99#" in txt, "Dial-String fehlt"
            assert "ModemManager" in txt, "ModemManager-Disable fehlt"
            assert "AT+CGPS=1" in txt, "GPS-Aktivierung fehlt"
            assert "lte-connection.service" in txt, "LTE-Service fehlt"
            assert "lte-wait-device" in txt, "LTE-Device-Wait fehlt"
            # Default = USB-Modus (PPP & AT ueber /dev/ttyUSB2 - der Composite-AT-Port)
            assert "/dev/ttyUSB2" in txt, "Default USB-PPP-Device (ttyUSB2) fehlt"
            assert "1e0e:9001" in txt, "USB-Stack Sanity-Check (lsusb 1e0e:9001) fehlt"
            assert "noipv6" in txt, "noipv6 (gegen IPV6CP-Timeouts) fehlt"
            assert "lcp-echo-interval" in txt, "LCP-Echo-Watchdog fehlt"
            assert "16inpind $STACK" in txt, "Stack-Auto-Discovery in sequent-init fehlt"
            assert "sudo reboot" in txt, "Auto-Reboot am Ende fehlt"
            print(f"[OK] Setup bash script enthaelt PIN/APN/PPP/GPS/USB-ttyUSB2/Auto-Stack/Auto-Reboot ({len(txt)} chars)")

            # UART-Modus override
            r8b = await http.post(
                f"/api/energy-monitoring/devices/{device_id}/kirmeskiste-8z-setup",
                json={"lte_apn": "internet.m2mportal.de", "lte_pin": "1234",
                      "enable_gps": True, "enable_lte": True,
                      "lte_uart": True},
                headers=H,
            )
            assert r8b.status_code == 200
            txt_b = (await http.get(r8b.json()["download_url"])).text
            assert "AT+CPIN=1234" in txt_b
            assert "/dev/ttyAMA0" in txt_b, "UART-Device fehlt im UART-Modus"
            assert "enable_uart=1" in txt_b, "UART-config-Anpassung fehlt im UART-Modus"
            print(f"[OK] Custom SIM-PIN + UART-Modus override")
            # Note: r8b setup hat einen neuen Key generiert; alten api_key auffrischen
            api_key = r8b.json()["device_key"]

            # Pi-Health endpoint test
            health = {
                "ts_utc": "2026-05-03T11:30:00+00:00",
                "hostname": "test-pi", "pi_id": "abc-123",
                "hat_stack": 7, "lte_ip": "10.27.23.227",
                "lte_csq": 20, "lte_signal_dbm": -73,
                "lte_operator": "Telekom.de", "lte_act": "LTE",
                "gps_lat": 49.5, "gps_lon": 8.4, "gps_mode": 3,
                "script_version": "1.1.0",
                "meters": [{"meter_id": meters[0]["id"], "channel": 1, "kwh_total": 1234.567}],
            }
            r9 = await http.post("/api/energy-monitoring/pi-health",
                                 json={"api_key": api_key, "device_id": device_id, "health": health})
            assert r9.status_code == 200, f"pi-health failed: {r9.text}"
            d_after = await db.devices.find_one({"id": device_id}, {"_id": 0})
            assert d_after.get("pi_health", {}).get("lte_ip") == "10.27.23.227"
            assert d_after.get("pi_health", {}).get("hat_stack") == 7
            print(f"[OK] pi-health endpoint persists health data")

            # Wrong key rejected
            r9b = await http.post("/api/energy-monitoring/pi-health",
                                  json={"api_key": "wrong", "device_id": device_id, "health": health})
            assert r9b.status_code == 401
            print(f"[OK] pi-health rejects wrong api_key")

            # quick-info returns pi_health
            r10 = await http.get(f"/api/devices/{device_id}/quick-info", headers=H)
            assert r10.status_code == 200
            assert r10.json().get("pi_health", {}).get("lte_ip") == "10.27.23.227"
            print(f"[OK] quick-info returns pi_health")

        finally:
            # Cleanup
            await db.emu_meters.delete_many({"device_id": device_id})
            await http.delete(f"/api/devices/{device_id}", headers=H)

        print("\nPASS: Kirmeskiste 8Z full stack works end-to-end")
    client.close()


if __name__ == "__main__":
    asyncio.run(_run())
