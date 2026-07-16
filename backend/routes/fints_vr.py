"""FinTS-Endpunkte für die zweite Bank (Volksbank / VR-Bank).

Nutzt die bereits multi-bank-fähigen Funktionen aus ``fints_banking.py``.
Die Endpunkte sind bewusst parallel zu ``/kirmes/fints/*`` gehalten, damit die
UI ein separates Panel zeigen kann. State + Credentials werden per Bank-Key
"volksbank" getrennt gespeichert.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from server import db
from routes.employee import _get_user, _has_verwaltung
from fints_banking import (
    _bank_configs, _fetch_from_bank, _load_fints_state, _save_fints_state,
    DEFAULT_FINTS_PRODUCT_ID, DEFAULT_FINTS_PRODUCT_VERSION,
)

router = APIRouter(prefix="/api/fints/vr", tags=["fints-vr"])
BANK_KEY = "volksbank"
LAST_CHECK_KEY = f"fints_last_check_{BANK_KEY}"
ENABLED_KEY = f"fints_enabled_{BANK_KEY}"


def _get_vr_bank_config():
    for b in _bank_configs():
        if b["key"] == BANK_KEY:
            return b
    return None


async def _require_admin(token: str):
    caller = await _get_user(token)
    if not _has_verwaltung(caller) or caller.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Nur Admins")
    return caller


@router.post("/save-credentials")
async def save_credentials(token: str = Query(...)):
    """Status-Check der VR-Bank-Konfiguration (analog Sparkasse)."""
    await _require_admin(token)
    bank = _get_vr_bank_config()
    last_check = await db.system_settings.find_one({"key": LAST_CHECK_KEY}, {"_id": 0})
    enabled_setting = await db.system_settings.find_one({"key": ENABLED_KEY}, {"_id": 0})
    is_enabled = enabled_setting.get("value", True) if enabled_setting else True
    if bank:
        return {
            "status": "configured",
            "message": "VR-Bank-Zugangsdaten sind konfiguriert",
            "last_check": last_check.get("value") if last_check else None,
            "last_result": last_check.get("result") if last_check else None,
            "enabled": is_enabled,
            "iban": bank.get("iban"),
            "blz": bank.get("blz"),
        }
    return {
        "status": "not_configured",
        "message": "Bitte FINTS_VB_USER, FINTS_VB_PIN, FINTS_VB_URL, FINTS_VB_BLZ und FINTS_VB_IBAN in .env setzen",
        "enabled": False,
    }


class VRToggle(BaseModel):
    enabled: bool


@router.post("/toggle")
async def toggle(data: VRToggle, token: str = Query(...)):
    await _require_admin(token)
    await db.system_settings.update_one(
        {"key": ENABLED_KEY},
        {"$set": {"key": ENABLED_KEY, "value": data.enabled}},
        upsert=True,
    )
    return {"enabled": data.enabled}


@router.get("/state-info")
async def state_info(token: str = Query(...)):
    await _require_admin(token)
    key = f"fints_client_state_{BANK_KEY}"
    doc = await db.system_settings.find_one({"key": key}, {"_id": 0})
    if not doc or not doc.get("value"):
        return {"has_state": False,
                "hint": "Noch keine Bank-Anmeldung gespeichert. Beim ersten Abruf pushTAN bestätigen."}
    updated = doc.get("updated_at")
    age_days = None
    if updated:
        try:
            d = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - d).days
        except Exception:
            pass
    return {
        "has_state": True,
        "updated_at": updated,
        "age_days": age_days,
        "sca_renewal_in_days": max(0, 90 - age_days) if age_days is not None else None,
        "hint": (
            "Bank-Anmeldung gespeichert. Abrufe der nächsten 90 Tage laufen ohne pushTAN."
            if age_days is None or age_days < 90
            else "90 Tage abgelaufen – beim nächsten Abruf wird wieder eine pushTAN angefordert."
        ),
    }


@router.post("/reset-state")
async def reset_state(token: str = Query(...)):
    await _require_admin(token)
    key = f"fints_client_state_{BANK_KEY}"
    result = await db.system_settings.delete_one({"key": key})
    return {"ok": True, "deleted": result.deleted_count}


@router.post("/test-connection")
async def test_connection(token: str = Query(...)):
    """Diagnostischer Test der VR-Bank-Verbindung."""
    await _require_admin(token)
    bank = _get_vr_bank_config()
    if not bank:
        return {
            "ok": False, "stage": "config",
            "error": "VR-Bank nicht konfiguriert. Setze FINTS_VB_USER, FINTS_VB_PIN, FINTS_VB_URL, FINTS_VB_BLZ, FINTS_VB_IBAN.",
            "hint": "Nach dem Setzen der ENV-Variablen Backend neu starten.",
        }
    diag = {
        "stage": "init",
        "blz": bank["blz"],
        "url": bank["url"],
        "user_first_chars": (bank["user"][:3] + "***") if bank["user"] else "",
        "user_length": len(bank["user"]),
        "pin_length": len(bank["pin"]),
        "product_id_first_chars": (bank["product_id"][:8] + "***") if bank.get("product_id") else "(leer)",
        "product_version": bank.get("product_version") or "(leer)",
    }
    try:
        from fints.client import FinTS3PinTanClient, NeedRetryResponse
        from fints_banking import _resolve_sca_after_dialog_start, _resolve_decoupled_tan
        client = FinTS3PinTanClient(
            bank["blz"], bank["user"], bank["pin"], bank["url"],
            product_id=bank.get("product_id") or DEFAULT_FINTS_PRODUCT_ID,
            product_version=bank.get("product_version") or DEFAULT_FINTS_PRODUCT_VERSION,
        )
        diag["stage"] = "connecting"
        with client:
            diag["stage"] = "sca_init"
            try:
                sca_init = _resolve_sca_after_dialog_start(client, max_wait_seconds=120)
                diag["sca_at_dialog_start"] = sca_init
            except Exception as ex:
                diag["sca_init_error"] = str(ex)[:400]
                raise
            diag["stage"] = "tan_mechanisms"
            try:
                mechanisms = client.get_tan_mechanisms()
                diag["tan_mechanisms"] = [
                    {"id": k, "name": getattr(v, "name", None) or str(v)[:80]}
                    for k, v in (mechanisms or {}).items()
                ]
            except Exception as ex:
                diag["tan_mechanisms_error"] = str(ex)[:400]
            diag["stage"] = "get_accounts"
            accounts_resp = client.get_sepa_accounts()
            if isinstance(accounts_resp, NeedRetryResponse):
                diag["pushtan_triggered"] = True
                diag["pushtan_decoupled"] = bool(getattr(accounts_resp, "decoupled", False))
                diag["pushtan_challenge"] = str(getattr(accounts_resp, "challenge", ""))[:300]
            accounts = _resolve_decoupled_tan(client, accounts_resp, max_wait_seconds=120)
            target_iban = (bank.get("iban") or "").replace(" ", "")
            primary = next((a for a in accounts if a.iban == target_iban), None)
            diag["primary_iban"] = target_iban
            diag["primary_found"] = primary is not None
            diag["accounts_found"] = len(accounts)
            if primary:
                diag["accounts"] = [{"iban": primary.iban, "bic": getattr(primary, "bic", None)}]
            else:
                diag["accounts"] = [{"iban": a.iban, "bic": getattr(a, "bic", None)} for a in accounts]
        # State speichern damit der nächste Abruf ohne TAN läuft
        try:
            new_state = client.deconstruct(including_private=True)
            if new_state:
                await _save_fints_state(db, new_state, bank_key=BANK_KEY)
        except Exception:
            pass
        diag["stage"] = "done"
        diag["ok"] = True
        return diag
    except Exception as e:
        diag["ok"] = False
        diag["error"] = str(e)[:500]
        low = diag["error"].lower()
        if "9340" in low or "signatur" in low:
            diag["hint"] = "Ungültige Signatur – Produkt-ID/Version prüfen oder mit VR-Bank abklären."
        elif "9210" in low or "9942" in low or "pin" in low:
            diag["hint"] = "PIN wurde von der Bank abgelehnt. Prüfe FINTS_VB_PIN."
        elif "invalid user" in low or "9010" in low:
            diag["hint"] = "VR-NetKey (User) abgelehnt. Prüfe FINTS_VB_USER."
        elif "url" in low or "404" in low or "connection" in low:
            diag["hint"] = "Bank-URL oder Netzwerk-Problem. Prüfe FINTS_VB_URL."
        else:
            diag["hint"] = "Unbekannter FinTS-Fehler – siehe Log-Trace."
        return diag


@router.get("/transactions")
async def get_transactions(days: int = 14, token: str = Query(...)):
    """Kontobewegungen der VR-Bank der letzten X Tage."""
    await _require_admin(token)
    bank = _get_vr_bank_config()
    if not bank:
        raise HTTPException(status_code=400, detail="VR-Bank nicht konfiguriert")
    result = await _fetch_from_bank(db, bank, days_back=days)
    return {
        "transactions": result.get("transactions", []),
        "count": len(result.get("transactions", [])),
        "ok": result.get("ok", False),
        "state_restored": result.get("state_restored", False),
        "sca_required": result.get("sca_required", False),
        "iban": result.get("iban"),
        "error": result.get("error"),
    }


@router.post("/check-payments")
async def check_payments(token: str = Query(...)):
    """Führt einen Eingangsrechnungen-Abgleich NUR mit den VR-Bank-Transaktionen aus.
    Nutzt die bestehende Matching-Logik (analog Sparkasse) - Sammelüberweisungen
    ausgeschlossen. Gleicht ausgehende Buchungen gegen offene Eingangsrechnungen ab."""
    await _require_admin(token)
    bank = _get_vr_bank_config()
    if not bank:
        raise HTTPException(status_code=400, detail="VR-Bank nicht konfiguriert")

    result = await _fetch_from_bank(db, bank, days_back=60)
    transactions = result.get("transactions", [])
    if not transactions:
        return {"checked": 0, "matched": 0, "auto_marked": 0, "admin_tasks": 0, "ambiguous": 0,
                "ok": result.get("ok", False), "error": result.get("error")}

    # Offene Eingangsrechnungen laden + matchen (identische Regeln wie Sparkasse)
    from fints_banking import (
        _match_outgoing_to_incoming, _mark_incoming_invoice_paid,
        _create_incoming_amount_mismatch_task, _create_incoming_ambiguous_task,
    )
    docs = await db.documents.find(
        {"folder_id": {"$regex": "^rechnungseingang_"},
         "is_deleted": {"$ne": True}, "eingang_paid": {"$ne": True}},
        {"_id": 0, "id": 1, "ai_metadata": 1}
    ).to_list(5000)
    invoices = []
    for d in docs:
        meta = d.get("ai_metadata") or {}
        try:
            amount = float(meta.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount <= 0:
            continue
        invoices.append({
            "id": d["id"],
            "invoice_number": (meta.get("invoice_number") or "").strip(),
            "amount": amount,
            "sender": (meta.get("sender") or "").strip(),
        })

    matches = _match_outgoing_to_incoming(transactions, invoices)
    auto_marked = admin_tasks = ambiguous = 0
    for m in matches:
        if m["action"] == "auto_paid":
            await _mark_incoming_invoice_paid(db, m)
            auto_marked += 1
        elif m["action"] == "admin_task":
            if await _create_incoming_amount_mismatch_task(db, m):
                admin_tasks += 1
        elif m["action"] == "admin_task_ambiguous":
            if await _create_incoming_ambiguous_task(db, m):
                ambiguous += 1

    out = {
        "checked": len(transactions),
        "matched": len(matches),
        "auto_marked": auto_marked,
        "admin_tasks": admin_tasks,
        "ambiguous": ambiguous,
        "ok": True,
    }
    await db.system_settings.update_one(
        {"key": LAST_CHECK_KEY},
        {"$set": {"key": LAST_CHECK_KEY,
                  "value": datetime.now(timezone.utc).isoformat(), "result": out}},
        upsert=True,
    )
    return out
