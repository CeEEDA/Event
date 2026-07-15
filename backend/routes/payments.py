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
                "deposit_refund_failed": False,
                "deposit_refund_error": None,
            }},
        )
        return {"ok": True, "refunded": True, "amount": refundable, "refund_id": refund.id, "status": refund.status}
    except Exception as e:
        logger.exception(f"[payments] Refund creation failed signup={signup_id}: {e}")
        err_str = str(e)[:200]
        await _db.payment_transactions.update_one(
            {"session_id": tx["session_id"]},
            {"$set": {"refund_error": err_str, "refund_attempted_at": datetime.now(timezone.utc).isoformat()}},
        )
        # Signup mit Fehler-Flag markieren, damit UI einen Warnhinweis + Retry-Button zeigen kann.
        await _db.kirmes_signups.update_one(
            {"id": signup_id},
            {"$set": {
                "deposit_refund_failed": True,
                "deposit_refund_error": err_str,
                "deposit_refund_attempted_at": datetime.now(timezone.utc).isoformat(),
                "deposit_refund_requested_amount": refundable,
                "deposit_refund_invoice_id": invoice_id,
                "deposit_refund_invoice_number": invoice_number,
            }},
        )
        return {"ok": False, "reason": "stripe_error", "error": err_str, "requested_amount": refundable}


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

    # Payment-Methoden: Wir bieten immer beides an (Karte + PayPal), damit der
    # Kunde in der Stripe-Checkout-Oberflaeche waehlen kann. Die im Anmelde-
    # formular gewaehlte Praeferenz wird nur fuer Statistik/Reporting erhalten.
    pm_pref = (signup.get("payment_method") or "kreditkarte").lower()
    payment_methods = ["card", "paypal"]

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
    payment_methods = ["card", "paypal"]

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
            await _mark_kirmes_invoice_paid(tx.get("invoice_id"), tx.get("amount"), source="Stripe-Status-Polling")

    return {
        "status": new_status,
        "payment_status": new_status,
        "amount": tx.get("amount"),
        "type": tx.get("type"),
    }


async def _mark_kirmes_invoice_paid(invoice_id: str, paid_amount: float = None, source: str = "stripe"):
    """Marks a Kirmes invoice as paid (German status 'bezahlt'), sets paid_at,
    and closes any open Mahnungs-Tasks linked to it.
    Same semantics as PUT /kirmes/invoices/{id}/payment-status with status='bezahlt'
    and the FinTS auto-match flow.
    """
    if not invoice_id:
        return
    inv = await _db.kirmes_invoices.find_one({"id": invoice_id}, {"_id": 0, "id": 1, "brutto": 1, "payment_status": 1})
    if not inv:
        logger.warning(f"[payments] Kirmes invoice {invoice_id} not found - cannot mark paid")
        return
    if inv.get("payment_status") == "bezahlt":
        return  # idempotent
    now_iso = datetime.now(timezone.utc).isoformat()
    await _db.kirmes_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "payment_status": "bezahlt",
            "paid_at": now_iso,
            "paid_amount": paid_amount if paid_amount is not None else inv.get("brutto", 0),
            "payment_updated_at": now_iso,
            "payment_updated_by": f"Auto ({source})",
        }},
    )
    # Mahnungs-Tasks dieser Rechnung schliessen
    closed = await _db.tasks.update_many(
        {"payment_reminder_invoice_id": invoice_id, "completed": False, "is_deleted": {"$ne": True}},
        {"$set": {
            "completed": True,
            "completed_at": now_iso,
            "completed_by_name": f"Auto ({source}) - Rechnung bezahlt",
        }},
    )
    logger.info(f"[payments] Kirmes invoice {invoice_id} -> bezahlt via {source}, closed {closed.modified_count} mahnung tasks")


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
                    await _mark_kirmes_invoice_paid(tx.get("invoice_id"), tx.get("amount"), source="Stripe-Webhook")
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


@router.post("/repair-stripe-paid-invoices")
async def repair_stripe_paid_invoices(user: dict = Depends(_require_admin)):
    """Einmaliger Sweep: Findet Stripe-bezahlte Rechnungen, deren Status in
    `kirmes_invoices` noch nicht 'bezahlt' ist, und korrigiert sie.

    Behebt zwei Faelle:
    1. payment_transactions ist bereits 'paid', aber kirmes_invoices ist 'offen' → einfach markieren
    2. payment_transactions ist 'pending', Stripe-Session ist aber 'paid' → bei Stripe nachfragen, updaten, markieren
       (Ursache: Webhook hat nie gefeuert, weil Webhook-URL nicht in Stripe registriert war,
       und der User kam nicht zurück auf die Erfolgsseite, sodass das Polling auch nie lief.)
    """
    txs = await _db.payment_transactions.find(
        {"type": "invoice", "payment_status": {"$in": ["paid", "pending", "initiated"]}},
        {"_id": 0},
    ).to_list(2000)
    repaired = []
    pulled_from_stripe = []
    skipped = []

    # Stripe SDK fuer Session-Lookups
    stripe_client = None
    if STRIPE_API_KEY:
        webhook_url = "https://placeholder/api/payments/webhook/stripe"
        stripe_client = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    for tx in txs:
        inv_id = tx.get("invoice_id")
        sess_id = tx.get("session_id")
        if not inv_id:
            skipped.append({"session_id": sess_id, "reason": "no invoice_id"})
            continue
        inv = await _db.kirmes_invoices.find_one({"id": inv_id}, {"_id": 0, "id": 1, "invoice_number": 1, "payment_status": 1})
        if not inv:
            skipped.append({"invoice_id": inv_id, "reason": "invoice not found"})
            continue
        if inv.get("payment_status") == "bezahlt":
            continue  # already correct

        tx_status = tx.get("payment_status")

        # Fall 1: tx schon auf 'paid', nur Invoice noch nicht synchronisiert
        if tx_status == "paid":
            await _mark_kirmes_invoice_paid(inv_id, tx.get("amount"), source="Repair-Sweep (tx=paid)")
            repaired.append({"invoice_id": inv_id, "invoice_number": inv.get("invoice_number"), "amount": tx.get("amount"), "via": "tx-already-paid"})
            continue

        # Fall 2: tx pending → Stripe direkt fragen
        if not sess_id or not stripe_client:
            skipped.append({"invoice_id": inv_id, "session_id": sess_id, "reason": "no stripe session_id or stripe client"})
            continue
        try:
            checkout_status = await stripe_client.get_checkout_status(sess_id)
            stripe_paid = checkout_status.payment_status == "paid"
        except Exception as e:
            skipped.append({"invoice_id": inv_id, "session_id": sess_id, "reason": f"stripe lookup failed: {str(e)[:100]}"})
            continue

        if stripe_paid:
            now_iso = datetime.now(timezone.utc).isoformat()
            await _db.payment_transactions.update_one(
                {"session_id": sess_id},
                {"$set": {"payment_status": "paid", "updated_at": now_iso, "repaired_at": now_iso}},
            )
            await _mark_kirmes_invoice_paid(inv_id, tx.get("amount"), source="Repair-Sweep (Stripe-confirmed)")
            pulled_from_stripe.append({"invoice_id": inv_id, "invoice_number": inv.get("invoice_number"), "amount": tx.get("amount"), "via": "stripe-confirmed"})
        else:
            skipped.append({
                "invoice_id": inv_id, "session_id": sess_id,
                "reason": f"stripe payment_status={checkout_status.payment_status} (not paid)",
            })

    return {
        "repaired": repaired,
        "pulled_from_stripe": pulled_from_stripe,
        "repaired_count": len(repaired) + len(pulled_from_stripe),
        "skipped": skipped,
    }


@router.get("/finance-summary")
async def finance_summary(user: dict = Depends(_require_admin)):
    """Finanz-Uebersicht: Was ist bei Stripe eingegangen und was ist an
    offenen Rechnungssummen noch draussen?

    Response:
    - stripe_income_gross: Summe aller erfolgreichen Stripe-Zahlungen (Kautionen + Rechnungen)
    - stripe_refunds_total: Summe aller erfolgten Rueckerstattungen
    - stripe_income_net: gross - refunds
    - by_type: {deposit: {count, amount}, invoice: {count, amount}}
    - open_invoices_amount: Summe brutto aller offenen/faelligen/ueberfaelligen Rechnungen
    - open_invoices_count: Anzahl
    - overdue_amount / overdue_count: Rechnungen mit Status ueberfaellig
    - failed_refunds_amount / failed_refunds_count: Rueckerstattungen, die bei Stripe abgelehnt wurden
    - by_month: Liste der letzten 12 Monate mit Stripe-Eingang + neuen Rechnungen
    """
    from collections import defaultdict

    # 1) Stripe-Eingaenge (payment_transactions mit payment_status=paid)
    paid_cur = _db.payment_transactions.find(
        {"payment_status": "paid"},
        {"_id": 0, "type": 1, "amount": 1, "refund_amount": 1, "refund_status": 1, "created_at": 1, "updated_at": 1},
    )
    gross = 0.0
    refunds = 0.0
    by_type_amount = defaultdict(float)
    by_type_count = defaultdict(int)
    by_month = defaultdict(lambda: {"income": 0.0, "refunds": 0.0, "count": 0})

    async for tx in paid_cur:
        amt = float(tx.get("amount") or 0)
        typ = (tx.get("type") or "unknown").lower()
        gross += amt
        by_type_amount[typ] += amt
        by_type_count[typ] += 1
        # Refunds nur mitzaehlen wenn Status positiv (succeeded/pending)
        r_amt = float(tx.get("refund_amount") or 0)
        r_stat = (tx.get("refund_status") or "").lower()
        if r_amt > 0 and r_stat in ("succeeded", "pending"):
            refunds += r_amt
        # Nach Monat gruppieren (updated_at wenn vorhanden, sonst created_at)
        ts = tx.get("updated_at") or tx.get("created_at") or ""
        month_key = ts[:7] if len(ts) >= 7 else "unknown"
        by_month[month_key]["income"] += amt
        by_month[month_key]["count"] += 1
        if r_amt > 0 and r_stat in ("succeeded", "pending"):
            by_month[month_key]["refunds"] += r_amt

    # 2) Offene Rechnungen (nur aus kirmes_invoices - Portal-Ausgangsrechnungen)
    # Achtung: payment_status wird dynamisch aus invoice_date abgeleitet (siehe
    # /invoices Endpoint) und ist bei alten Docs oft gar nicht persistent. Wir
    # muessen die gleiche Logik hier anwenden.
    open_amount = 0.0
    open_count = 0
    overdue_amount = 0.0
    overdue_count = 0
    open_net_of_deposit = 0.0
    now_dt = datetime.now(timezone.utc)
    all_cur = _db.kirmes_invoices.find(
        {},
        {"_id": 0, "brutto": 1, "payment_status": 1, "invoice_date": 1, "deposit_applied": 1, "sent_at": 1},
    )
    async for inv in all_cur:
        ps = inv.get("payment_status") or "erstellt"
        if ps == "bezahlt":
            continue
        # Ableitung wie in GET /invoices
        derived = ps
        if inv.get("sent_at"):
            try:
                inv_date = datetime.strptime(inv.get("invoice_date", ""), "%d.%m.%Y").replace(tzinfo=timezone.utc)
                days_since = (now_dt - inv_date).days
                if days_since > 17:
                    derived = "ueberfaellig"
                elif days_since > 14:
                    derived = "faellig"
                elif derived not in ("offen", "faellig", "ueberfaellig"):
                    derived = "offen"
            except (ValueError, TypeError):
                if derived == "erstellt":
                    derived = "offen"
        # Zaehle alle nicht-bezahlten als offen
        br = float(inv.get("brutto") or 0)
        dep = float(inv.get("deposit_applied") or 0)
        open_amount += br
        open_count += 1
        open_net_of_deposit += max(0.0, br - dep)
        if derived == "ueberfaellig":
            overdue_amount += br
            overdue_count += 1

    # 3) Fehlgeschlagene Refunds (Handlungsbedarf)
    failed_cur = _db.kirmes_signups.find(
        {"deposit_refund_failed": True},
        {"_id": 0, "deposit_refund_requested_amount": 1},
    )
    failed_amount = 0.0
    failed_count = 0
    async for s in failed_cur:
        failed_amount += float(s.get("deposit_refund_requested_amount") or 0)
        failed_count += 1

    # By-month sortiert (letzte 12 Monate)
    months_sorted = sorted(by_month.keys(), reverse=True)[:12]
    by_month_list = [
        {
            "month": m,
            "income": round(by_month[m]["income"], 2),
            "refunds": round(by_month[m]["refunds"], 2),
            "net": round(by_month[m]["income"] - by_month[m]["refunds"], 2),
            "count": by_month[m]["count"],
        }
        for m in months_sorted
    ]

    return {
        "stripe_income_gross": round(gross, 2),
        "stripe_refunds_total": round(refunds, 2),
        "stripe_income_net": round(gross - refunds, 2),
        "by_type": {
            t: {"count": by_type_count[t], "amount": round(by_type_amount[t], 2)}
            for t in by_type_amount
        },
        "open_invoices_amount": round(open_amount, 2),
        "open_invoices_count": open_count,
        "open_after_deposit": round(open_net_of_deposit, 2),
        "overdue_amount": round(overdue_amount, 2),
        "overdue_count": overdue_count,
        "failed_refunds_amount": round(failed_amount, 2),
        "failed_refunds_count": failed_count,
        "by_month": by_month_list,
    }


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


@router.post("/refund/retry/{signup_id}")
async def refund_retry(signup_id: str, user: dict = Depends(_require_admin)):
    """Wiederholt einen zuvor fehlgeschlagenen Auto-Refund fuer die Kaution einer
    bereits abgerechneten Anmeldung. Verwendet die im Signup gespeicherten Werte
    (invoice_id, requested_amount) und ruft die zentrale Refund-Funktion neu auf."""
    signup = await _db.kirmes_signups.find_one({"id": signup_id}, {"_id": 0})
    if not signup:
        raise HTTPException(status_code=404, detail="Anmeldung nicht gefunden")
    if not signup.get("deposit_paid"):
        raise HTTPException(status_code=400, detail="Keine bezahlte Kaution vorhanden")
    if signup.get("deposit_refund_id"):
        return {"ok": True, "already_refunded": True, "refund_id": signup["deposit_refund_id"], "amount": signup.get("deposit_refund_amount", 0)}

    inv_id = signup.get("deposit_refund_invoice_id") or signup.get("deposit_applied_to_invoice") or signup.get("invoice_id")
    inv_number = signup.get("deposit_refund_invoice_number") or signup.get("invoice_number") or ""
    if not inv_id:
        raise HTTPException(status_code=400, detail="Keine zugeordnete Rechnung gefunden")

    # Ermittle Share (Anteil der Rechnung, den diese Anmeldung tragen soll)
    inv = await _db.kirmes_invoices.find_one({"id": inv_id}, {"_id": 0, "brutto": 1, "signup_ids": 1, "signup_id": 1})
    if not inv:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    total_invoice = float(inv.get("brutto", 0) or 0)
    sig_ids = inv.get("signup_ids") or [inv.get("signup_id")]
    paid_signups = await _db.kirmes_signups.find(
        {"id": {"$in": sig_ids}, "deposit_paid": True},
        {"_id": 0, "id": 1, "deposit_amount": 1},
    ).to_list(100)
    total_deposits = sum(float(s.get("deposit_amount", 0) or 0) for s in paid_signups)
    dep = float(signup.get("deposit_amount", 0) or 0)
    share = (dep / total_deposits) * total_invoice if total_deposits > 0 else 0.0

    res = await refund_deposit_difference(signup_id, share, inv_id, inv_number)
    if not res.get("refunded"):
        # 400 (nicht 502), damit Cloudflare den JSON-Body nicht mit einer HTML-Error-Seite ersetzt
        raise HTTPException(status_code=400, detail=res.get("error") or res.get("reason") or "Refund fehlgeschlagen")

    # Invoice-Aggregate aktualisieren
    all_signups = await _db.kirmes_signups.find(
        {"id": {"$in": sig_ids}},
        {"_id": 0, "deposit_refund_amount": 1, "deposit_amount": 1}
    ).to_list(100)
    total_refunded = sum(float(s.get("deposit_refund_amount", 0) or 0) for s in all_signups)
    total_deposits_all = sum(float(s.get("deposit_amount", 0) or 0) for s in all_signups)
    open_balance = round(max(0.0, total_invoice - total_deposits_all), 2)
    await _db.kirmes_invoices.update_one(
        {"id": inv_id},
        {"$set": {
            "deposit_refunded": round(total_refunded, 2),
            "deposit_open_balance": open_balance,
        }},
    )
    return {"ok": True, "refunded": True, "refund_id": res.get("refund_id"), "amount": res.get("amount"), "status": res.get("status")}


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
        payment_methods = ["card", "paypal"]

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
        payment_methods = ["card", "paypal"]

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
