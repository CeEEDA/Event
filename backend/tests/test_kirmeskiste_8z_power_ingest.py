"""Test: Stellt sicher dass die Kirmeskiste 8Z-Variante echte kW-Werte
aus dem Pi-Sync NICHT durch 1000 teilt (Bug: Backend wandelte fuer alle
Kirmeskisten Watt->kW um, was fuer 8Z-Pulse-Berechnung falsch ist)."""
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
        r = await http.post("/api/auth/login",
                            json={"email": "admin@test.com", "password": "password"})
        assert r.status_code == 200
        token = r.json()["token"]
        H = {"Authorization": f"Bearer {token}"}

        # 8Z-Kirmeskiste anlegen
        sn8z = f"TEST-PWR-8Z-{uuid.uuid4().hex[:6].upper()}"
        r1 = await http.post("/api/devices",
                             json={"device_type": "kirmeskiste", "serial_number": sn8z,
                                   "kirmeskiste_variant": "8z"}, headers=H)
        assert r1.status_code == 200
        dev8z = r1.json()
        d8z_id = dev8z["id"]

        # Standard-Kirmeskiste anlegen (Legacy 4-Meter)
        sn_std = f"TEST-PWR-STD-{uuid.uuid4().hex[:6].upper()}"
        r2 = await http.post("/api/devices",
                             json={"device_type": "kirmeskiste", "serial_number": sn_std},
                             headers=H)
        assert r2.status_code == 200
        d_std = r2.json()
        d_std_id = d_std["id"]

        try:
            # 8Z Setup -> erzeugt Meter + device_key
            r3 = await http.post(
                f"/api/energy-monitoring/devices/{d8z_id}/kirmeskiste-8z-setup",
                json={"lte_apn": "internet.m2mportal.de"}, headers=H,
            )
            assert r3.status_code == 200
            setup_8z = r3.json()
            key_8z = setup_8z["device_key"]
            meter_8z = setup_8z["meter_ids"][0]

            # Standard-Kirmeskiste: API-Key generieren + Meter anlegen
            r4 = await http.post(f"/api/energy-monitoring/ingest/generate-key",
                                 json={"device_id": d_std_id}, headers=H)
            assert r4.status_code == 200
            key_std = r4.json()["api_key"]
            meter_std_id = str(uuid.uuid4())
            await db.emu_meters.insert_one({
                "id": meter_std_id, "device_id": d_std_id,
                "meter_name": "Legacy", "meter_type": "EMU", "meter_ip": "192.168.1.10",
            })

            # 8Z Pi sendet 1.2 kW (echter Wert in kW)
            r5 = await http.post("/api/energy-monitoring/ingest", json={
                "api_key": key_8z, "device_id": d8z_id, "meter_id": meter_8z,
                "records": [{
                    "ts_utc": "2026-05-03T13:00:00+00:00",
                    "E_imp_kWh": 170.5, "P_sum_kW": 1.2,
                }],
            })
            assert r5.status_code == 200, r5.text
            saved_8z = await db.emu_data.find_one({"device_id": d8z_id, "meter_id": meter_8z}, {"_id": 0})
            assert saved_8z is not None
            assert abs(saved_8z["P_sum_kW"] - 1.2) < 0.001, \
                f"8Z P_sum_kW falsch konvertiert: erwartet 1.2 kW, bekommen {saved_8z['P_sum_kW']}"
            assert abs(saved_8z["E_imp_kWh"] - 170.5) < 0.001
            print(f"[OK] 8Z behaelt P_sum_kW=1.2 (keine Watt->kW Konvertierung)")

            # Standard-Kirmeskiste sendet 1200 (Watt aus EMU Modbus)
            r6 = await http.post("/api/energy-monitoring/ingest", json={
                "api_key": key_std, "device_id": d_std_id, "meter_id": meter_std_id,
                "records": [{
                    "ts_utc": "2026-05-03T13:00:00+00:00",
                    "E_imp_kWh": 50.0, "P_sum_kW": 1200,
                }],
            })
            assert r6.status_code == 200, r6.text
            saved_std = await db.emu_data.find_one({"device_id": d_std_id, "meter_id": meter_std_id}, {"_id": 0})
            assert saved_std is not None
            assert abs(saved_std["P_sum_kW"] - 1.2) < 0.001, \
                f"Standard-Kirmeskiste sollte 1200W -> 1.2 kW konvertieren, bekommen {saved_std['P_sum_kW']}"
            print(f"[OK] Standard-Kirmeskiste konvertiert 1200W -> 1.2kW (Legacy-Logik)")

            # Quick-Info zeigt P_sum_kW korrekt
            r7 = await http.get(f"/api/devices/{d8z_id}/quick-info", headers=H)
            qi = r7.json()
            reading = next(rd for rd in qi["readings"] if rd["meter_id"] == meter_8z)
            assert "1.20 kW" in reading["value"], f"Quick-Info kW falsch: {reading}"
            print(f"[OK] Quick-Info zeigt 1.20 kW fuer 8Z-Reading")

        finally:
            await db.emu_data.delete_many({"device_id": {"$in": [d8z_id, d_std_id]}})
            await db.emu_meters.delete_many({"device_id": {"$in": [d8z_id, d_std_id]}})
            await http.delete(f"/api/devices/{d8z_id}", headers=H)
            await http.delete(f"/api/devices/{d_std_id}", headers=H)

        print("\nPASS: Kirmeskiste 8Z echte kW-Werte werden korrekt gespeichert")
    client.close()


if __name__ == "__main__":
    asyncio.run(_run())
