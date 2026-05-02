"""Test: FinTS auto-match should close open Mahnungs-Tasks for matched invoices.

Validates the fix in /app/backend/fints_banking.py auto_match_and_mark()
that closes any open `payment_reminder` tasks linked to an invoice that
gets automatically marked as paid via FinTS.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient


async def _run():
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # 1. Setup: insert an invoice + payment_reminder task
    invoice_id = f"test-inv-{uuid.uuid4()}"
    invoice_number = f"TR{uuid.uuid4().hex[:6].upper()}"
    task_id = f"test-task-{uuid.uuid4()}"

    await db.kirmes_invoices.insert_one({
        "id": invoice_id,
        "invoice_number": invoice_number,
        "brutto": 123.45,
        "schausteller_firma": "Testfirma",
        "schausteller_kundennummer": "K9999",
        "schausteller_name": "Tester",
        "payment_status": "offen",
    })
    await db.tasks.insert_one({
        "id": task_id,
        "title": "1. Mahnung Testfirma",
        "task_type": "payment_reminder",
        "payment_reminder_invoice_id": invoice_id,
        "payment_reminder_invoice_number": invoice_number,
        "payment_reminder_stufe": 1,
        "completed": False,
        "is_deleted": False,
        "assigned_to": ["admin"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # 2. Mock fetch_transactions_persisted to return a matching transaction
    fake_tx = {
        "date": "2026-02-15",
        "amount": 123.45,
        "applicant_name": "Tester GmbH",
        "purpose": f"Rechnung {invoice_number}",
    }

    import fints_banking
    with patch.object(
        fints_banking,
        "fetch_transactions_persisted",
        new=AsyncMock(return_value={"ok": True, "transactions": [fake_tx]}),
    ):
        result = await fints_banking.auto_match_and_mark(db)

    print(f"[result] {result}")
    assert result["auto_marked"] >= 1, f"Expected auto_marked>=1, got {result}"

    # 3. Verify the task is closed
    task_after = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    print(f"[task_after] completed={task_after.get('completed')} "
          f"completed_by_name={task_after.get('completed_by_name')}")
    assert task_after["completed"] is True, "Task should be marked completed"
    assert "FinTS" in (task_after.get("completed_by_name") or ""), \
        f"Expected completed_by_name to include FinTS, got {task_after.get('completed_by_name')}"
    assert task_after.get("completed_at"), "completed_at should be set"

    # 4. Verify the invoice is paid
    inv_after = await db.kirmes_invoices.find_one({"id": invoice_id}, {"_id": 0})
    assert inv_after["payment_status"] == "bezahlt", \
        f"Invoice should be 'bezahlt', got {inv_after['payment_status']}"

    # 5. Cleanup
    await db.tasks.delete_one({"id": task_id})
    await db.kirmes_invoices.delete_one({"id": invoice_id})

    print("PASS: FinTS auto-match closes open Mahnungs-Task and marks invoice paid")

    # ============== Test 2: Sweep Cleanup ==============
    # Invoice already paid but Mahnung task still open -> sweep should close it
    invoice_id_2 = f"test-inv-{uuid.uuid4()}"
    invoice_number_2 = f"TR{uuid.uuid4().hex[:6].upper()}"
    task_id_2 = f"test-task-{uuid.uuid4()}"

    await db.kirmes_invoices.insert_one({
        "id": invoice_id_2,
        "invoice_number": invoice_number_2,
        "brutto": 99.99,
        "schausteller_firma": "AlreadyPaid GmbH",
        "schausteller_kundennummer": "K7777",
        "schausteller_name": "Tester2",
        "payment_status": "bezahlt",  # Already paid
    })
    await db.tasks.insert_one({
        "id": task_id_2,
        "title": "1. Mahnung AlreadyPaid",
        "task_type": "payment_reminder",
        "payment_reminder_invoice_id": invoice_id_2,
        "payment_reminder_invoice_number": invoice_number_2,
        "payment_reminder_stufe": 1,
        "completed": False,
        "is_deleted": False,
        "assigned_to": ["admin"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Mock with NO transactions - sweep should still run
    with patch.object(
        fints_banking,
        "fetch_transactions_persisted",
        new=AsyncMock(return_value={"ok": True, "transactions": []}),
    ):
        result2 = await fints_banking.auto_match_and_mark(db)

    print(f"[result2] {result2}")
    assert result2.get("swept_closed", 0) >= 1, f"Expected swept_closed>=1, got {result2}"

    task2_after = await db.tasks.find_one({"id": task_id_2}, {"_id": 0})
    assert task2_after["completed"] is True, "Sweep: Task should be closed"
    assert "bezahlt" in (task2_after.get("completed_by_name") or ""), \
        f"Expected sweep reason, got {task2_after.get('completed_by_name')}"

    await db.tasks.delete_one({"id": task_id_2})
    await db.kirmes_invoices.delete_one({"id": invoice_id_2})

    print("PASS: FinTS sweep closes open Mahnungs-Tasks for already-paid invoices")
    client.close()


if __name__ == "__main__":
    # Load .env so MONGO_URL/DB_NAME are available
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    asyncio.run(_run())
