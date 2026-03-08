from fastapi import APIRouter, HTTPException, Depends, Request, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime, timezone
import os
import uuid

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionRequest,
)

router = APIRouter(prefix="/api/payments", tags=["payments"])
security = HTTPBearer()

_db = None
_decode_token = None


def init_payments(db, decode_jwt_token):
    global _db, _decode_token
    _db = db
    _decode_token = decode_jwt_token


STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY")


# ============== Auth helpers ==============

async def _auth_user(credentials: HTTPAuthorizationCredentials):
    payload = _decode_token(credentials.credentials)
    user = await _db.users.find_one({"email": payload["email"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Nicht autorisiert")
    return user


async def _require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await _auth_user(credentials)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin-Berechtigung erforderlich")
    return user


# ============== Models ==============

class DepositCheckoutRequest(BaseModel):
    signup_id: str
    event_id: str
    origin_url: str


class InvoiceCheckoutRequest(BaseModel):
    invoice_id: str
    origin_url: str


# ============== Kaution (deposit) configuration ==============

# Default deposit amounts per connection type in EUR
DEFAULT_DEPOSITS = {
    "Schuko": 50.0,
    "16A": 100.0,
    "32A": 200.0,
    "63A": 400.0,
    "125A": 800.0,
}


async def _get_deposit_amount(connection_type: str) -> float:
    """Get deposit amount for a connection type from DB or defaults."""
    cfg = await _db.kirmes_deposit_config.find_one(
        {"connection_type": connection_type}, {"_id": 0}
    )
    if cfg and cfg.get("deposit_amount") is not None:
        return float(cfg["deposit_amount"])
    return DEFAULT_DEPOSITS.get(connection_type, 100.0)


# ============== Admin: Configure deposit amounts ==============

@router.get("/deposits/config")
async def get_deposit_config(user: dict = Depends(_require_admin)):
    """Get all deposit configurations."""
    configs = await _db.kirmes_deposit_config.find({}, {"_id": 0}).to_list(100)
    config_map = {c["connection_type"]: c.get("deposit_amount", 0.0) for c in configs}
    result = []
    for ct, default_amt in DEFAULT_DEPOSITS.items():
        result.append({
            "connection_type": ct,
            "deposit_amount": config_map.get(ct, default_amt),
        })
    return result


@router.put("/deposits/config")
async def update_deposit_config(deposits: List[dict] = Body(...), user: dict = Depends(_require_admin)):
    """Update deposit amounts per connection type."""
    for d in deposits:
        ct = d.get("connection_type")
        amt = float(d.get("deposit_amount", 0))
        await _db.kirmes_deposit_config.update_one(
            {"connection_type": ct},
            {"$set": {"connection_type": ct, "deposit_amount": amt, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
    return {"message": "Kautionen aktualisiert"}


# ============== Deposit Checkout (public – after signup) ==============

@router.post("/checkout/deposit")
async def create_deposit_checkout(req: DepositCheckoutRequest):
    """Create a Stripe checkout session for a deposit payment after signup."""
    signup = await _db.kirmes_signups.find_one({"id": req.signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")

    if signup.get("deposit_paid"):
        raise HTTPException(status_code=400, detail="Kaution bereits bezahlt")

    event = await _db.kirmes_events.find_one({"id": req.event_id}, {"_id": 0, "name": 1})
    schausteller = await _db.schausteller.find_one({"id": signup.get("schausteller_id")}, {"_id": 0})

    connection_type = signup.get("connection_type", "16A")
    amount = await _get_deposit_amount(connection_type)

    success_url = f"{req.origin_url}/schausteller-anmeldung?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{req.origin_url}/schausteller-anmeldung?payment=cancelled"

    metadata = {
        "type": "deposit",
        "signup_id": req.signup_id,
        "event_id": req.event_id,
        "schausteller_id": signup.get("schausteller_id", ""),
        "connection_type": connection_type,
    }

    webhook_url = f"{req.origin_url}/api/payments/webhook/stripe"
    stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    checkout_req = CheckoutSessionRequest(
        amount=amount,
        currency="eur",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    session = await stripe.create_checkout_session(checkout_req)

    # Create payment transaction record
    tx = {
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "type": "deposit",
        "signup_id": req.signup_id,
        "event_id": req.event_id,
        "event_name": event.get("name", "") if event else "",
        "schausteller_id": signup.get("schausteller_id", ""),
        "schausteller_name": schausteller.get("name", "") if schausteller else "",
        "connection_type": connection_type,
        "amount": amount,
        "currency": "eur",
        "payment_status": "pending",
        "metadata": metadata,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.payment_transactions.insert_one(tx)

    return {"url": session.url, "session_id": session.session_id, "amount": amount}


# ============== Invoice Checkout ==============

@router.post("/checkout/invoice")
async def create_invoice_checkout(req: InvoiceCheckoutRequest):
    """Create a Stripe checkout session for an invoice payment."""
    invoice = await _db.invoices.find_one({"id": req.invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    if invoice.get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="Rechnung bereits bezahlt")

    amount = float(invoice.get("total_gross", invoice.get("total_amount", 0)))
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Ungültiger Rechnungsbetrag")

    success_url = f"{req.origin_url}/schausteller-anmeldung?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{req.origin_url}/schausteller-anmeldung?payment=cancelled"

    metadata = {
        "type": "invoice",
        "invoice_id": req.invoice_id,
        "invoice_number": invoice.get("invoice_number", ""),
    }

    webhook_url = f"{req.origin_url}/api/payments/webhook/stripe"
    stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    checkout_req = CheckoutSessionRequest(
        amount=amount,
        currency="eur",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    session = await stripe.create_checkout_session(checkout_req)

    tx = {
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "type": "invoice",
        "invoice_id": req.invoice_id,
        "invoice_number": invoice.get("invoice_number", ""),
        "amount": amount,
        "currency": "eur",
        "payment_status": "pending",
        "metadata": metadata,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.payment_transactions.insert_one(tx)

    return {"url": session.url, "session_id": session.session_id, "amount": amount}


# ============== Payment status polling ==============

@router.get("/checkout/status/{session_id}")
async def check_payment_status(session_id: str):
    """Poll Stripe for payment status and update DB."""
    tx = await _db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaktion nicht gefunden")

    # If already processed, return cached status
    if tx.get("payment_status") in ("paid", "expired"):
        return {
            "status": tx.get("payment_status"),
            "payment_status": tx.get("payment_status"),
            "amount": tx.get("amount"),
            "type": tx.get("type"),
        }

    # Poll Stripe
    webhook_url = "https://placeholder/api/payments/webhook/stripe"
    stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    checkout_status = await stripe.get_checkout_status(session_id)

    new_status = "pending"
    if checkout_status.payment_status == "paid":
        new_status = "paid"
    elif checkout_status.status in ("expired", "complete") and checkout_status.payment_status != "paid":
        new_status = "expired"

    # Update transaction
    await _db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {"payment_status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    # If paid, update related records (only once)
    if new_status == "paid" and tx.get("payment_status") != "paid":
        if tx.get("type") == "deposit":
            await _db.kirmes_signups.update_one(
                {"id": tx["signup_id"]},
                {"$set": {"deposit_paid": True, "deposit_amount": tx["amount"], "deposit_paid_at": datetime.now(timezone.utc).isoformat()}},
            )
        elif tx.get("type") == "invoice":
            await _db.invoices.update_one(
                {"id": tx["invoice_id"]},
                {"$set": {"payment_status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}},
            )

    return {
        "status": new_status,
        "payment_status": new_status,
        "amount": tx.get("amount"),
        "type": tx.get("type"),
    }


# ============== Webhook ==============

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    try:
        webhook_url = str(request.base_url) + "payments/webhook/stripe"
        stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
        event = await stripe.handle_webhook(body, signature)

        if event.payment_status == "paid" and event.session_id:
            tx = await _db.payment_transactions.find_one({"session_id": event.session_id}, {"_id": 0})
            if tx and tx.get("payment_status") != "paid":
                await _db.payment_transactions.update_one(
                    {"session_id": event.session_id},
                    {"$set": {"payment_status": "paid", "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                if tx.get("type") == "deposit":
                    await _db.kirmes_signups.update_one(
                        {"id": tx["signup_id"]},
                        {"$set": {"deposit_paid": True, "deposit_amount": tx["amount"], "deposit_paid_at": datetime.now(timezone.utc).isoformat()}},
                    )
                elif tx.get("type") == "invoice":
                    await _db.invoices.update_one(
                        {"id": tx["invoice_id"]},
                        {"$set": {"payment_status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}},
                    )
    except Exception:
        pass  # Webhook verification may fail in test mode

    return {"status": "ok"}


# ============== Admin: View payments ==============

@router.get("/transactions")
async def list_transactions(event_id: Optional[str] = None, user: dict = Depends(_require_admin)):
    """List all payment transactions, optionally filtered by event."""
    query = {}
    if event_id:
        query["event_id"] = event_id
    txs = await _db.payment_transactions.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return txs


# ============== Public: Get deposit info for signup ==============

@router.get("/deposit-info/{event_id}")
async def get_deposit_info(event_id: str):
    """Get deposit amounts for all connection types (public endpoint for signup flow)."""
    result = {}
    for ct in DEFAULT_DEPOSITS:
        result[ct] = await _get_deposit_amount(ct)
    return result
