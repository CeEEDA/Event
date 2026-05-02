"""Test: Marking an invoice as 'bezahlt' via PUT /invoices/{id}/payment-status
should close any open Mahnungs-Tasks for that invoice."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")

import httpx
from motor.motor_asyncio import AsyncIOMotorClient


async def _run():
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")

    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    backend_url = "http://localhost:8001"

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Login as admin to get token
    admin_email = "admin@test.com"
    admin_password = "password"

    async with httpx.AsyncClient(base_url=backend_url, timeout=15) as http:
        r = await http.post("/api/auth/login", json={"email": admin_email, "password": admin_password})
        if r.status_code != 200:
            print(f"FAIL login: {r.status_code} {r.text}")
            return
        token = r.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Setup: invoice + open mahnung task
        invoice_id = f"test-inv-{uuid.uuid4()}"
        invoice_number = f"TR{uuid.uuid4().hex[:6].upper()}"
        task_id = f"test-task-{uuid.uuid4()}"

        await db.kirmes_invoices.insert_one({
            "id": invoice_id,
            "invoice_number": invoice_number,
            "brutto": 250.00,
            "schausteller_firma": "ManualTest GmbH",
            "schausteller_name": "Manual Tester",
            "payment_status": "offen",
        })
        await db.tasks.insert_one({
            "id": task_id,
            "title": "1. Mahnung Manual Test",
            "task_type": "payment_reminder",
            "payment_reminder_invoice_id": invoice_id,
            "payment_reminder_invoice_number": invoice_number,
            "payment_reminder_stufe": 1,
            "completed": False,
            "is_deleted": False,
            "assigned_to": ["admin"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Trigger PUT /invoices/{id}/payment-status -> bezahlt
        r2 = await http.put(
            f"/api/kirmes/invoices/{invoice_id}/payment-status",
            json={"payment_status": "bezahlt", "paid_amount": 250.00},
            headers=headers,
        )
        print(f"[update] {r2.status_code} {r2.text[:200]}")
        assert r2.status_code == 200, f"Expected 200, got {r2.status_code}: {r2.text}"

        task_after = await db.tasks.find_one({"id": task_id}, {"_id": 0})
        print(f"[task_after] completed={task_after.get('completed')} "
              f"completed_by_name={task_after.get('completed_by_name')}")
        assert task_after["completed"] is True
        assert "bezahlt" in (task_after.get("completed_by_name") or "")

        # Cleanup
        await db.tasks.delete_one({"id": task_id})
        await db.kirmes_invoices.delete_one({"id": invoice_id})

        print("PASS: Manual mark-as-paid closes Mahnungs-Task")
    client.close()


if __name__ == "__main__":
    asyncio.run(_run())
