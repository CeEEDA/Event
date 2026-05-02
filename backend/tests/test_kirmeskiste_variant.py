"""Test: kirmeskiste_variant field is correctly saved on device create
and persists on get/update. Existing 'standard' Kirmeskisten remain untouched
because variant is only set when device_type=='kirmeskiste'."""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, "/app/backend")

import httpx


async def _run():
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")

    backend_url = "http://localhost:8001"

    async with httpx.AsyncClient(base_url=backend_url, timeout=15) as http:
        r = await http.post("/api/auth/login",
                            json={"email": "admin@test.com", "password": "password"})
        assert r.status_code == 200, f"Login failed: {r.text}"
        token = r.json()["token"]
        H = {"Authorization": f"Bearer {token}"}

        created_ids = []

        # 1. Create a STANDARD Kirmeskiste (existing live behaviour)
        sn1 = f"TEST-KK-STD-{uuid.uuid4().hex[:6].upper()}"
        r1 = await http.post("/api/devices",
                             json={"device_type": "kirmeskiste", "serial_number": sn1},
                             headers=H)
        assert r1.status_code == 200, f"Create standard failed: {r1.text}"
        d1 = r1.json()
        created_ids.append(d1["id"])
        assert d1.get("kirmeskiste_variant") == "standard", \
            f"Expected variant 'standard', got {d1.get('kirmeskiste_variant')}"
        print(f"[OK] Standard Kirmeskiste created: variant={d1.get('kirmeskiste_variant')}")

        # 2. Create a 8Z Kirmeskiste (new variant)
        sn2 = f"TEST-KK-8Z-{uuid.uuid4().hex[:6].upper()}"
        r2 = await http.post("/api/devices",
                             json={"device_type": "kirmeskiste", "serial_number": sn2,
                                   "kirmeskiste_variant": "8z"},
                             headers=H)
        assert r2.status_code == 200, f"Create 8z failed: {r2.text}"
        d2 = r2.json()
        created_ids.append(d2["id"])
        assert d2.get("kirmeskiste_variant") == "8z", \
            f"Expected variant '8z', got {d2.get('kirmeskiste_variant')}"
        print(f"[OK] 8Z Kirmeskiste created: variant={d2.get('kirmeskiste_variant')}")

        # 3. Non-kirmeskiste device should NOT get a variant
        sn3 = f"TEST-SE-{uuid.uuid4().hex[:6].upper()}"
        r3 = await http.post("/api/devices",
                             json={"device_type": "stromerzeuger", "serial_number": sn3,
                                   "kirmeskiste_variant": "8z"},  # ignored
                             headers=H)
        assert r3.status_code == 200
        d3 = r3.json()
        created_ids.append(d3["id"])
        assert d3.get("kirmeskiste_variant") is None, \
            f"Stromerzeuger should not have variant, got {d3.get('kirmeskiste_variant')}"
        print(f"[OK] Stromerzeuger has no variant (as expected)")

        # 4. Update the standard one to 8z
        r4 = await http.put(f"/api/devices/{d1['id']}",
                            json={"kirmeskiste_variant": "8z"},
                            headers=H)
        assert r4.status_code == 200, f"Update failed: {r4.text}"
        d1u = r4.json()
        assert d1u.get("kirmeskiste_variant") == "8z", \
            f"Expected updated variant '8z', got {d1u.get('kirmeskiste_variant')}"
        print(f"[OK] Update standard -> 8z works")

        # 5. List endpoint returns variant
        r5 = await http.get("/api/devices", headers=H)
        assert r5.status_code == 200
        devices = r5.json()
        for d in devices:
            if d["id"] == d2["id"]:
                assert d.get("kirmeskiste_variant") == "8z"
                break
        else:
            raise AssertionError("Created 8z device not found in list")
        print(f"[OK] List returns variant correctly")

        # Cleanup
        for did in created_ids:
            await http.delete(f"/api/devices/{did}", headers=H)
        print("\nPASS: kirmeskiste_variant create/update/list works; existing devices unaffected")


if __name__ == "__main__":
    asyncio.run(_run())
