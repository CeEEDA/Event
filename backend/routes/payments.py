from fastapi import APIRouter, HTTPException, Depends, Request, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime, timezone
import os
import uuid
import logging

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionRequest,
)

logger = logging.getLogger("payments")

router = APIRouter(prefix="/api/payments", tags=["payments"])
security = HTTPBearer()

_db = None
_decode_token = None


def init_payments(db, decode_jwt_token):
    global _db, _decode_token
    _db = db
    _decode_token = decode_jwt_token


STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY")

# Initialize raw stripe SDK for refunds (checkout lib doesn't expose refunds)
import stripe as _stripe_sdk
if STRIPE_API_KEY:
    _stripe_sdk.api_key = STRIPE_API_KEY


async def _create_stripe_session_with_error_handling(stripe_client, checkout_req, pm_pref: str):
    """Helper: wraps stripe.create_checkout_session with friendly error handling (e.g. PayPal not activated)."""
    try:
        return await stripe_client.create_checkout_session(checkout_req)
    except Exception as e:
        err_str = str(e)
        logger.exception(f"[payments] Stripe checkout creation failed (pm={pm_pref}): {err_str}")
        if "paypal" in err_str.lower() and pm_pref == "paypal":
            raise HTTPException(
                status_code=400,
                detail=(
                    "PayPal ist im Stripe-Dashboard noch nicht aktiviert. "
                    "Bitte im Stripe-Dashboard unter 'Zahlungsmethoden' PayPal aktivieren, "
                    "oder vorerst Kreditkarte wählen."
                ),
            )
        raise HTTPException(status_code=502, detail=f"Checkout konnte nicht erstellt werden: {err_str[:200]}")


async def _fetch_and_store_payment_intent(session_id: str):
    """After successful payment, fetch the Stripe session to get payment_intent & charge for future refunds."""
    if not STRIPE_API_KEY:
        return None, None
    try:
        sess = _stripe_sdk.checkout.Session.retrieve(session_id, expand=["payment_intent.latest_charge"])
        pi = sess.get("payment_intent") if isinstance(sess, dict) else sess.payment_intent
        pi_id = pi if isinstance(pi, str) else (pi.get("id") if pi else None)
        charge_id = None
        if pi and not isinstance(pi, str):
            latest_charge = pi.get("latest_charge")
            if latest_charge:
                charge_id = latest_charge if isinstance(latest_charge, str) else latest_charge.get("id")
        await _db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_intent_id": pi_id, "charge_id": charge_id}},
        )
        logger.info(f"[payments] Stored payment_intent={pi_id} charge={charge_id} for session={session_id}")
        return pi_id, charge_id
    except Exception as e:
        logger.exception(f"[payments] Could not fetch session details for {session_id}: {e}")
        return None, None


async def refund_deposit_difference(signup_id: str, invoice_brutto: float, invoice_id: str, invoice_number: str):
    """
    After invoice creation: refund the difference between paid deposit and actual invoice amount.
    Only refunds if deposit > invoice (positive difference).
    Returns dict with status info.
    """
    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup or not signup.get("deposit_paid"):
        return {"ok": False, "reason": "no_deposit_paid"}

    deposit_amount = float(signup.get("deposit_amount", 0.0))
    refundable = round(deposit_amount - float(invoice_brutto), 2)

    # Update signup: record that invoice was settled against deposit
    await _db.kirmes_signups.update_one(
        {"id": signup_id},
        {"$set": {
            "deposit_applied_to_invoice": invoice_id,
            "deposit_applied_amount": min(deposit_amount, float(invoice_brutto)),
        }},
    )

    if refundable <= 0.01:
        logger.info(f"[payments] No refund needed signup={signup_id} deposit={deposit_amount} invoice={invoice_brutto}")
        return {"ok": True, "refunded": False, "amount": 0.0, "reason": "no_excess", "open_balance": round(-refundable, 2)}

    # Find the deposit transaction
    tx = await _db.payment_transactions.find_one(
        {"signup_id": signup_id, "type": "deposit", "payment_status": "paid"},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not tx:
        logger.warning(f"[payments] No paid deposit tx found for signup={signup_id}")
        return {"ok": False, "reason": "no_transaction"}

    if tx.get("refund_id"):
        logger.info(f"[payments] Refund already exists for session={tx.get('session_id')} refund={tx.get('refund_id')}")
        return {"ok": True, "refunded": True, "amount": tx.get("refund_amount", 0.0), "reason": "already_refunded", "refund_id": tx.get("refund_id")}

    # Ensure we have payment_intent_id
    pi_id = tx.get("payment_intent_id")
    if not pi_id:
        pi_id, _ = await _fetch_and_store_payment_intent(tx["session_id"])
    if not pi_id:
        return {"ok": False, "reason": "no_payment_intent"}

    if not STRIPE_API_KEY:
        return {"ok": False, "reason": "no_stripe_key"}

    try:
        amount_cents = int(round(refundable * 100))
        refund = _stripe_sdk.Refund.create(
            payment_intent=pi_id,
            amount=amount_cents,
            reason="requested_by_customer",
            metadata={
                "signup_id": signup_id,
                "invoice_id": invoice_id,
                "invoice_number": invoice_number,
                "reason": "deposit_excess_refund",
            },
        )
        logger.info(f"[payments] Refund created: {refund.id} amount={refundable} signup={signup_id}")
        await _db.payment_transactions.update_one(
            {"session_id": tx["session_id"]},
            {"$set": {
                "refund_id": refund.id,
                "refund_amount": refundable,
                "refund_status": refund.status,
                "refund_created_at": datetime.now(timezone.utc).isoformat(),
                "refund_invoice_id": invoice_id,
                "refund_invoice_number": invoice_number,
            }},
        )
        await _db.kirmes_signups.update_one(
            {"id": signup_id},
            {"$set": {
                "deposit_refund_id": refund.id,
                "deposit_refund_amount": refundable,
                "deposit_refund_status": refund.status,
                "deposit_refund_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        return {"ok": True, "refunded": True, "amount": refundable, "refund_id": refund.id, "status": refund.status}
    except Exception as e:
        logger.exception(f"[payments] Refund creation failed signup={signup_id}: {e}")
        await _db.payment_transactions.update_one(
            {"session_id": tx["session_id"]},
            {"$set": {"refund_error": str(e)[:200], "refund_attempted_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {"ok": False, "reason": "stripe_error", "error": str(e)[:200]}


async def _confirm_deposit_and_send_email(signup_id, amount, session_id=None):
    """After successful deposit payment: activate booking, store payment_intent for refunds, send confirmation email."""
    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup:
        return
    await _db.kirmes_signups.update_one(
        {"id": signup_id},
        {"$set": {
            "deposit_paid": True,
            "deposit_amount": amount,
            "deposit_paid_at": datetime.now(timezone.utc).isoformat(),
            "payment_status": "bezahlt",
        }},
    )
    # Fetch payment_intent details for future refunds
    if session_id:
        try:
            await _fetch_and_store_payment_intent(session_id)
        except Exception as e:
            logger.warning(f"[payments] Could not fetch payment intent for session={session_id}: {e}")
    try:
        sch = await _db.kirmes_schausteller.find_one({"id": signup["schausteller_id"]}, {"_id": 0})
        event = await _db.kirmes_events.find_one({"id": signup["event_id"]}, {"_id": 0})
        if sch and event:
            from routes.kirmes import _send_booking_confirmation_email
            _send_booking_confirmation_email(sch, event, signup)
    except Exception:
        pass


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
    payment_method: Optional[str] = "kreditkarte"  # "kreditkarte" | "paypal"


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
    """Create a Stripe checkout session for a deposit payment after signup. Supports card and PayPal."""
    signup = await _db.kirmes_signups.find_one({"id": req.signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")

    if signup.get("deposit_paid"):
        raise HTTPException(status_code=400, detail="Kaution bereits bezahlt")

    event = await _db.kirmes_events.find_one({"id": req.event_id}, {"_id": 0, "name": 1})
    schausteller = await _db.kirmes_schausteller.find_one({"id": signup.get("schausteller_id")}, {"_id": 0})

    connection_type = signup.get("connection_type", "16A")
    amount = await _get_deposit_amount(connection_type)

    # Determine payment methods based on signup preference
    pm_pref = (signup.get("payment_method") or "kreditkarte").lower()
    if pm_pref == "paypal":
        payment_methods = ["paypal"]
    else:
        payment_methods = ["card"]

    success_url = f"{req.origin_url}/kirmes/anmeldung?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{req.origin_url}/kirmes/anmeldung?payment=cancelled"

    metadata = {
        "type": "deposit",
        "signup_id": req.signup_id,
        "event_id": req.event_id,
        "schausteller_id": signup.get("schausteller_id", ""),
        "connection_type": connection_type,
        "payment_method_pref": pm_pref,
    }

    webhook_url = f"{req.origin_url}/api/payments/webhook/stripe"
    stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    checkout_req = CheckoutSessionRequest(
        amount=amount,
        currency="eur",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        payment_methods=payment_methods,
    )
    try:
        session = await _create_stripe_session_with_error_handling(stripe, checkout_req, pm_pref)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Checkout konnte nicht erstellt werden: {str(e)[:200]}")

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
        "payment_method_pref": pm_pref,
        "metadata": metadata,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.payment_transactions.insert_one(tx)

    return {"url": session.url, "session_id": session.session_id, "amount": amount, "payment_method": pm_pref}


# ============== Invoice Checkout ==============

@router.post("/checkout/invoice")
async def create_invoice_checkout(req: InvoiceCheckoutRequest):
    """Create a Stripe checkout session for an invoice payment. Supports card and PayPal."""
    invoice = await _db.invoices.find_one({"id": req.invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    if invoice.get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="Rechnung bereits bezahlt")

    amount = float(invoice.get("total_gross", invoice.get("total_amount", 0)))
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Ungültiger Rechnungsbetrag")

    pm_pref = (req.payment_method or "kreditkarte").lower()
    payment_methods = ["paypal"] if pm_pref == "paypal" else ["card", "paypal"]

    success_url = f"{req.origin_url}/kirmes/anmeldung?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{req.origin_url}/kirmes/anmeldung?payment=cancelled"

    metadata = {
        "type": "invoice",
        "invoice_id": req.invoice_id,
        "invoice_number": invoice.get("invoice_number", ""),
        "payment_method_pref": pm_pref,
    }

    webhook_url = f"{req.origin_url}/api/payments/webhook/stripe"
    stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    checkout_req = CheckoutSessionRequest(
        amount=amount,
        currency="eur",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        payment_methods=payment_methods,
    )
    session = await _create_stripe_session_with_error_handling(stripe, checkout_req, pm_pref)

    tx = {
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "type": "invoice",
        "invoice_id": req.invoice_id,
        "invoice_number": invoice.get("invoice_number", ""),
        "amount": amount,
        "currency": "eur",
        "payment_status": "pending",
        "payment_method_pref": pm_pref,
        "metadata": metadata,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.payment_transactions.insert_one(tx)

    return {"url": session.url, "session_id": session.session_id, "amount": amount, "payment_method": pm_pref}


# ============== Payment status polling ==============

@router.get("/checkout/status/{session_id}")
async def check_payment_status(session_id: str):
    """Poll Stripe for payment status and update DB."""
    logger.info(f"[payments] check_payment_status called session_id={session_id}")
    tx = await _db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        logger.warning(f"[payments] Transaction not found for session_id={session_id}")
        raise HTTPException(status_code=404, detail="Transaktion nicht gefunden")

    # If already processed, return cached status
    if tx.get("payment_status") in ("paid", "expired"):
        logger.info(f"[payments] Cached status returned: {tx.get('payment_status')} for session_id={session_id}")
        return {
            "status": tx.get("payment_status"),
            "payment_status": tx.get("payment_status"),
            "amount": tx.get("amount"),
            "type": tx.get("type"),
        }

    # Poll Stripe
    try:
        webhook_url = "https://placeholder/api/payments/webhook/stripe"
        stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
        checkout_status = await stripe.get_checkout_status(session_id)
        logger.info(
            f"[payments] Stripe status for session={session_id}: "
            f"payment_status={checkout_status.payment_status} status={checkout_status.status}"
        )
    except Exception as e:
        logger.exception(f"[payments] Stripe get_checkout_status failed for session={session_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Stripe-Abfrage fehlgeschlagen: {str(e)[:120]}")

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
        logger.info(f"[payments] Marking session={session_id} as paid (type={tx.get('type')})")
        if tx.get("type") == "deposit":
            await _confirm_deposit_and_send_email(tx["signup_id"], tx["amount"], session_id=session_id)
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
        logger.info(f"[payments] Webhook received: session={event.session_id} payment_status={event.payment_status}")

        if event.payment_status == "paid" and event.session_id:
            tx = await _db.payment_transactions.find_one({"session_id": event.session_id}, {"_id": 0})
            if tx and tx.get("payment_status") != "paid":
                await _db.payment_transactions.update_one(
                    {"session_id": event.session_id},
                    {"$set": {"payment_status": "paid", "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                if tx.get("type") == "deposit":
                    await _confirm_deposit_and_send_email(tx["signup_id"], tx["amount"], session_id=event.session_id)
                elif tx.get("type") == "invoice":
                    await _db.invoices.update_one(
                        {"id": tx["invoice_id"]},
                        {"$set": {"payment_status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}},
                    )
    except Exception as e:
        logger.exception(f"[payments] Webhook processing failed: {e}")

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


# ============== Admin: Manual refund / refund status ==============

class ManualRefundRequest(BaseModel):
    signup_id: str
    amount: Optional[float] = None  # If None: refund full remaining deposit
    reason: Optional[str] = "manual_admin_refund"


@router.post("/refund/manual")
async def manual_refund(req: ManualRefundRequest, user: dict = Depends(_require_admin)):
    """Manually trigger a refund for a signup's paid deposit. If amount omitted, refunds full remaining deposit."""
    signup = await _db.kirmes_signups.find_one({"id": req.signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")
    if not signup.get("deposit_paid"):
        raise HTTPException(status_code=400, detail="Keine bezahlte Kaution vorhanden")

    tx = await _db.payment_transactions.find_one(
        {"signup_id": req.signup_id, "type": "deposit", "payment_status": "paid"},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Keine Zahlungstransaktion gefunden")

    pi_id = tx.get("payment_intent_id")
    if not pi_id:
        pi_id, _ = await _fetch_and_store_payment_intent(tx["session_id"])
    if not pi_id:
        raise HTTPException(status_code=400, detail="PaymentIntent nicht verfügbar – Refund nicht möglich")

    deposit_amount = float(signup.get("deposit_amount", 0.0))
    already_refunded = float(tx.get("refund_amount", 0.0) or 0.0)
    max_refundable = round(deposit_amount - already_refunded, 2)
    amount_to_refund = round(float(req.amount), 2) if req.amount is not None else max_refundable

    if amount_to_refund <= 0:
        raise HTTPException(status_code=400, detail="Betrag muss größer 0 sein")
    if amount_to_refund > max_refundable + 0.01:
        raise HTTPException(status_code=400, detail=f"Maximal {max_refundable:.2f} EUR erstattbar")

    try:
        refund = _stripe_sdk.Refund.create(
            payment_intent=pi_id,
            amount=int(round(amount_to_refund * 100)),
            reason="requested_by_customer",
            metadata={"signup_id": req.signup_id, "reason": req.reason or "manual_admin_refund", "admin": user.get("email", "")},
        )
        logger.info(f"[payments] Manual refund: {refund.id} amount={amount_to_refund} signup={req.signup_id} by={user.get('email')}")
        new_total = round(already_refunded + amount_to_refund, 2)
        await _db.payment_transactions.update_one(
            {"session_id": tx["session_id"]},
            {"$set": {
                "refund_id": refund.id,
                "refund_amount": new_total,
                "refund_status": refund.status,
                "refund_created_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        await _db.kirmes_signups.update_one(
            {"id": req.signup_id},
            {"$set": {
                "deposit_refund_id": refund.id,
                "deposit_refund_amount": new_total,
                "deposit_refund_status": refund.status,
                "deposit_refund_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        return {"ok": True, "refund_id": refund.id, "amount": amount_to_refund, "total_refunded": new_total, "status": refund.status}
    except Exception as e:
        logger.exception(f"[payments] Manual refund failed: {e}")
        raise HTTPException(status_code=502, detail=f"Stripe-Refund fehlgeschlagen: {str(e)[:160]}")


@router.get("/refund/status/{signup_id}")
async def refund_status(signup_id: str, user: dict = Depends(_require_admin)):
    """Get refund status for a signup."""
    signup = await _db.kirmes_signups.find_one(
        {"id": signup_id},
        {"_id": 0, "id": 1, "deposit_paid": 1, "deposit_amount": 1, "deposit_refund_id": 1,
         "deposit_refund_amount": 1, "deposit_refund_status": 1, "deposit_refund_at": 1,
         "deposit_applied_to_invoice": 1, "deposit_applied_amount": 1}
    )
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")
    tx = await _db.payment_transactions.find_one(
        {"signup_id": signup_id, "type": "deposit"},
        {"_id": 0, "session_id": 1, "amount": 1, "payment_status": 1, "payment_intent_id": 1,
         "refund_id": 1, "refund_amount": 1, "refund_status": 1, "refund_error": 1},
        sort=[("created_at", -1)],
    )
    return {"signup": signup, "transaction": tx}


@router.post("/refund/sync-payment-intent/{session_id}")
async def sync_payment_intent(session_id: str, user: dict = Depends(_require_admin)):
    """Fetch and store the payment_intent_id for an existing session. Useful to enable refund for legacy paid sessions."""
    pi_id, charge_id = await _fetch_and_store_payment_intent(session_id)
    if not pi_id:
        raise HTTPException(status_code=404, detail="PaymentIntent konnte nicht ermittelt werden")
    return {"ok": True, "payment_intent_id": pi_id, "charge_id": charge_id}


# ============== Public: Get deposit info for signup ==============

@router.get("/deposit-info/{event_id}")
async def get_deposit_info(event_id: str):
    """Get deposit amounts for all connection types (public endpoint for signup flow)."""
    result = {}
    for ct in DEFAULT_DEPOSITS:
        result[ct] = await _get_deposit_amount(ct)
    return result


# ============== Dashboard ==============

@router.get("/dashboard")
async def get_payment_dashboard(event_id: Optional[str] = None, user: dict = Depends(_require_admin)):
    """Aggregated payment dashboard."""
    match = {}
    if event_id:
        match["event_id"] = event_id

    txs = await _db.payment_transactions.find(match, {"_id": 0}).to_list(5000)

    deposits = [t for t in txs if t.get("type") == "deposit"]
    invoices = [t for t in txs if t.get("type") == "invoice"]

    deposits_paid = [t for t in deposits if t.get("payment_status") == "paid"]
    deposits_pending = [t for t in deposits if t.get("payment_status") == "pending"]
    invoices_paid = [t for t in invoices if t.get("payment_status") == "paid"]
    invoices_pending = [t for t in invoices if t.get("payment_status") == "pending"]

    return {
        "deposits": {
            "total": len(deposits),
            "paid": len(deposits_paid),
            "pending": len(deposits_pending),
            "total_amount": sum(t.get("amount", 0) for t in deposits),
            "paid_amount": sum(t.get("amount", 0) for t in deposits_paid),
            "pending_amount": sum(t.get("amount", 0) for t in deposits_pending),
        },
        "invoices": {
            "total": len(invoices),
            "paid": len(invoices_paid),
            "pending": len(invoices_pending),
            "total_amount": sum(t.get("amount", 0) for t in invoices),
            "paid_amount": sum(t.get("amount", 0) for t in invoices_paid),
            "pending_amount": sum(t.get("amount", 0) for t in invoices_pending),
        },
        "recent_transactions": txs[:20],
    }


@router.get("/dashboard/events")
async def get_events_with_payment_summary(user: dict = Depends(_require_admin)):
    """List all events with payment summary counts."""
    events = await _db.kirmes_events.find({}, {"_id": 0, "id": 1, "name": 1, "status": 1, "start_date": 1}).to_list(200)

    for event in events:
        txs = await _db.payment_transactions.find({"event_id": event["id"]}, {"_id": 0, "payment_status": 1, "type": 1, "amount": 1}).to_list(1000)
        deposits = [t for t in txs if t.get("type") == "deposit"]
        inv = [t for t in txs if t.get("type") == "invoice"]
        event["deposits_paid"] = sum(1 for t in deposits if t.get("payment_status") == "paid")
        event["deposits_pending"] = sum(1 for t in deposits if t.get("payment_status") == "pending")
        event["invoices_paid"] = sum(1 for t in inv if t.get("payment_status") == "paid")
        event["invoices_pending"] = sum(1 for t in inv if t.get("payment_status") == "pending")
        event["total_received"] = sum(t.get("amount", 0) for t in txs if t.get("payment_status") == "paid")

    return events


# ============== Send payment link via email ==============

class SendPaymentLinkRequest(BaseModel):
    signup_id: Optional[str] = None
    invoice_id: Optional[str] = None
    origin_url: str
    payment_method: Optional[str] = None  # "kreditkarte" | "paypal" | None (auto from signup)


@router.post("/send-payment-link")
async def send_payment_link(req: SendPaymentLinkRequest, user: dict = Depends(_require_admin)):
    """Create a Stripe checkout session and send the payment link via email."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    email_to = None
    subject = ""
    checkout_url = ""

    if req.signup_id:
        signup = await _db.kirmes_signups.find_one({"id": req.signup_id}, {"_id": 0})
        if not signup:
            raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")
        sch = await _db.kirmes_schausteller.find_one({"id": signup.get("schausteller_id")}, {"_id": 0})
        event = await _db.kirmes_events.find_one({"id": signup.get("event_id")}, {"_id": 0, "name": 1})
        if not sch:
            raise HTTPException(status_code=404, detail="Schausteller nicht gefunden")
        email_to = sch.get("rechnungs_email") or sch.get("email")
        connection_type = signup.get("connection_type", "16A")
        amount = await _get_deposit_amount(connection_type)
        subject = f"Kaution für {event.get('name', 'Veranstaltung')} - Zahlungslink"

        pm_pref = (req.payment_method or signup.get("payment_method") or "kreditkarte").lower()
        payment_methods = ["paypal"] if pm_pref == "paypal" else ["card", "paypal"]

        success_url = f"{req.origin_url}/kirmes/anmeldung?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{req.origin_url}/kirmes/anmeldung?payment=cancelled"
        metadata = {"type": "deposit", "signup_id": req.signup_id, "event_id": signup.get("event_id", ""), "schausteller_id": signup.get("schausteller_id", ""), "connection_type": connection_type, "payment_method_pref": pm_pref}

        webhook_url = f"{req.origin_url}/api/payments/webhook/stripe"
        stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
        checkout_req = CheckoutSessionRequest(amount=amount, currency="eur", success_url=success_url, cancel_url=cancel_url, metadata=metadata, payment_methods=payment_methods)
        session = await _create_stripe_session_with_error_handling(stripe, checkout_req, pm_pref)
        checkout_url = session.url

        tx = {
            "id": str(uuid.uuid4()), "session_id": session.session_id, "type": "deposit",
            "signup_id": req.signup_id, "event_id": signup.get("event_id", ""),
            "schausteller_id": signup.get("schausteller_id", ""), "schausteller_name": sch.get("name", ""),
            "connection_type": connection_type, "amount": amount, "currency": "eur",
            "payment_status": "pending", "payment_method_pref": pm_pref,
            "metadata": metadata, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await _db.payment_transactions.insert_one(tx)

    elif req.invoice_id:
        invoice = await _db.invoices.find_one({"id": req.invoice_id}, {"_id": 0})
        if not invoice:
            raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
        sch = invoice.get("schausteller", {})
        email_to = sch.get("rechnungs_email") or sch.get("email")
        amount = float(invoice.get("total_gross", invoice.get("total_amount", 0)))
        subject = f"Rechnung {invoice.get('invoice_number', '')} - Zahlungslink"

        pm_pref = (req.payment_method or "kreditkarte").lower()
        payment_methods = ["paypal"] if pm_pref == "paypal" else ["card", "paypal"]

        success_url = f"{req.origin_url}/kirmes/anmeldung?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{req.origin_url}/kirmes/anmeldung?payment=cancelled"
        metadata = {"type": "invoice", "invoice_id": req.invoice_id, "invoice_number": invoice.get("invoice_number", ""), "payment_method_pref": pm_pref}

        webhook_url = f"{req.origin_url}/api/payments/webhook/stripe"
        stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
        checkout_req = CheckoutSessionRequest(amount=amount, currency="eur", success_url=success_url, cancel_url=cancel_url, metadata=metadata, payment_methods=payment_methods)
        session = await _create_stripe_session_with_error_handling(stripe, checkout_req, pm_pref)
        checkout_url = session.url

        tx = {
            "id": str(uuid.uuid4()), "session_id": session.session_id, "type": "invoice",
            "invoice_id": req.invoice_id, "invoice_number": invoice.get("invoice_number", ""),
            "amount": amount, "currency": "eur", "payment_status": "pending", "payment_method_pref": pm_pref,
            "metadata": metadata, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await _db.payment_transactions.insert_one(tx)
    else:
        raise HTTPException(status_code=400, detail="signup_id oder invoice_id erforderlich")

    if not email_to:
        raise HTTPException(status_code=400, detail="Keine E-Mail-Adresse gefunden")

    # Send email with payment link
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")

    body = f"""Sehr geehrte Damen und Herren,

bitte verwenden Sie den folgenden Link zur Zahlung:

{checkout_url}

Der Link ist für eine begrenzte Zeit gültig.

Mit freundlichen Grüßen
Eventenergie Deutschland GmbH & Co. KG"""

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = email_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception:
        pass  # Email may fail due to SMTP limits

    return {"message": "Zahlungslink gesendet", "email": email_to, "url": checkout_url, "amount": amount if req.signup_id else amount}
