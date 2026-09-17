"""Offday / Ausgleichstag-Konto

Jeder Mitarbeiter hat ein Offday-Saldo, das automatisch waechst wenn er an
einem Sonntag oder gesetzlichen Feiertag (Rheinland-Pfalz) einstempelt
(siehe deutsches Arbeitszeitgesetz, Anspruch auf Ersatzruhetag).
In der Einsatzplanung kann ein Admin/Verwaltungs-User einen `Offday`
zuweisen - das zieht 1 Tag vom Saldo ab.

Architektur: Doppelte Buchfuehrung via `offday_ledger` Collection.
- accrual:    +1 (z.B. Sonntagsarbeit)
- consumption: -1 (z.B. Offday in Einsatzplanung)
- manual_adjust: variable (Admin-Korrektur)

Saldo = SUM(delta) ueber alle ledger-Eintraege des Users.

Idempotenz: Per (user_id, source, ref_id) Unique - dadurch
fuehrt mehrfaches Einstempeln am gleichen Tag nicht zu Doppel-Accrual.
"""
from fastapi import APIRouter, HTTPException, Query, Body
from datetime import date as _date, datetime, timezone, timedelta
import uuid
import os
import jwt as pyjwt

router = APIRouter(prefix="/api/employee/offdays", tags=["offdays"])
db = None


def init_offday_routes(database):
    global db
    db = database


# ── Feiertage Rheinland-Pfalz ──

def _easter_sunday(year: int) -> _date:
    """Gauss-Algorithmus fuer Ostersonntag."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    L = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * L) // 451
    month = (h + L - 7 * m + 114) // 31
    day = ((h + L - 7 * m + 114) % 31) + 1
    return _date(year, month, day)


def _rlp_holidays(year: int) -> set:
    """Gesetzliche Feiertage in Rheinland-Pfalz fuer ein Jahr."""
    easter = _easter_sunday(year)
    fixed = {
        _date(year, 1, 1),    # Neujahr
        _date(year, 5, 1),    # Tag der Arbeit
        _date(year, 10, 3),   # Tag der Deutschen Einheit
        _date(year, 11, 1),   # Allerheiligen (RLP)
        _date(year, 12, 25),  # 1. Weihnachtstag
        _date(year, 12, 26),  # 2. Weihnachtstag
    }
    movable = {
        easter - timedelta(days=2),   # Karfreitag
        easter + timedelta(days=1),   # Ostermontag
        easter + timedelta(days=39),  # Christi Himmelfahrt
        easter + timedelta(days=50),  # Pfingstmontag
        easter + timedelta(days=60),  # Fronleichnam (RLP)
    }
    return fixed | movable


def is_sunday_or_rlp_holiday(date_str: str) -> tuple[bool, str]:
    """Returns (bool, reason_label). reason: 'sunday' | 'holiday' | ''.
    Eingabe: ISO-Date 'YYYY-MM-DD'."""
    try:
        d = _date.fromisoformat(date_str)
    except Exception:
        return False, ""
    if d.weekday() == 6:  # 6 = Sonntag
        return True, "sunday"
    if d in _rlp_holidays(d.year):
        return True, "holiday"
    return False, ""


# ── Auth ──

async def _get_user(token: str):
    JWT_SECRET = os.environ.get('JWT_SECRET', 'eventenergie-fileshare-secret-key-2024')
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Ungueltiger Token")
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    return user


def _has_verwaltung(caller: dict) -> bool:
    if not caller:
        return False
    if caller.get("role") == "admin":
        return True
    if caller.get("role") == "mitarbeiter":
        modules = (caller.get("apps") or {}).get("modules") or {}
        return modules.get("verwaltung") is not False
    return False


# ── Ledger-Helpers (werden auch von employee.py importiert) ──

async def grant_offday_for_work(user_id: str, user_name: str, date_str: str) -> bool:
    """Wird beim Clock-In aufgerufen. Wenn date_str ein Sonntag oder
    RLP-Feiertag ist, wird +1 Offday auf das Konto gebucht.

    Idempotent: pro (user_id, date_str) kann nur EIN accrual entstehen,
    auch wenn der MA mehrfach am selben Tag einstempelt.

    Returns True wenn neu gebucht, False wenn bereits vorhanden oder kein
    Sonntag/Feiertag.
    """
    is_special, reason = is_sunday_or_rlp_holiday(date_str)
    if not is_special:
        return False

    existing = await db.offday_ledger.find_one({
        "user_id": user_id,
        "source": "clock_in",
        "ref_date": date_str,
    })
    if existing:
        return False

    await db.offday_ledger.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "user_name": user_name,
        "delta": 1,
        "kind": "accrual",
        "source": "clock_in",
        "source_label": "Sonntagsarbeit" if reason == "sunday" else "Feiertagsarbeit",
        "reason": reason,
        "ref_date": date_str,
        "ref_id": None,
        "note": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "system",
    })
    return True


async def consume_offday_for_assignment(user_id: str, user_name: str, date_str: str,
                                        assignment_id: str, created_by: str) -> bool:
    """Wird aufgerufen wenn in der Einsatzplanung ein Offday zugewiesen wird.
    Bucht -1 Offday auf das Konto.

    Idempotent: pro assignment_id nur EIN deduction.
    """
    existing = await db.offday_ledger.find_one({
        "source": "shift_assignment",
        "ref_id": assignment_id,
    })
    if existing:
        return False

    await db.offday_ledger.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "user_name": user_name,
        "delta": -1,
        "kind": "consumption",
        "source": "shift_assignment",
        "source_label": "Offday in Einsatzplanung",
        "reason": "shift_offday",
        "ref_date": date_str,
        "ref_id": assignment_id,
        "note": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": created_by,
    })
    return True


async def release_offday_for_assignment(assignment_id: str) -> bool:
    """Wird aufgerufen wenn ein Offday-Assignment in der Einsatzplanung
    geloescht wird. Loescht den deduction-Eintrag (== gibt den Tag wieder
    auf das Konto zurueck)."""
    result = await db.offday_ledger.delete_one({
        "source": "shift_assignment",
        "ref_id": assignment_id,
    })
    return result.deleted_count > 0


async def _balance_for_user(user_id: str) -> int:
    """Saldo = Summe aller delta-Werte des Users."""
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": None, "total": {"$sum": "$delta"}}},
    ]
    res = await db.offday_ledger.aggregate(pipeline).to_list(1)
    return int(res[0]["total"]) if res else 0


# ── Endpoints ──

@router.get("/me")
async def get_my_offdays(token: str = Query(...)):
    """Eigener Saldo + Buchungs-Historie (jeder User)."""
    user = await _get_user(token)
    balance = await _balance_for_user(user["id"])
    entries = await db.offday_ledger.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort([("ref_date", -1), ("created_at", -1)]).to_list(500)
    return {"balance": balance, "entries": entries}


@router.get("")
async def list_all_offdays(token: str = Query(...)):
    """Verwaltung: Alle User mit Saldo + komplette Buchungs-Historie."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    # Saldo pro User aggregieren
    pipeline = [
        {"$group": {
            "_id": "$user_id",
            "balance": {"$sum": "$delta"},
            "user_name": {"$first": "$user_name"},
            "last_entry": {"$max": "$created_at"},
        }},
        {"$sort": {"user_name": 1}},
    ]
    balances_raw = await db.offday_ledger.aggregate(pipeline).to_list(500)

    # Auch User OHNE Buchungen einbeziehen, damit man sehen kann, wer noch
    # nichts hat (sonst muss man raten).
    all_users = await db.users.find(
        {"role": {"$in": ["admin", "mitarbeiter"]}, "is_active": {"$ne": False}},
        {"_id": 0, "id": 1, "name": 1}
    ).sort("name", 1).to_list(500)

    by_user = {b["_id"]: b for b in balances_raw}
    balances = []
    for u in all_users:
        b = by_user.get(u["id"])
        balances.append({
            "user_id": u["id"],
            "user_name": u.get("name", ""),
            "balance": int(b["balance"]) if b else 0,
            "last_entry": b.get("last_entry") if b else None,
        })

    # Letzte 200 Bewegungen ueber alle User (Activity Feed)
    recent = await db.offday_ledger.find({}, {"_id": 0}).sort(
        [("created_at", -1)]
    ).to_list(200)

    return {"balances": balances, "recent": recent}


@router.get("/user/{user_id}")
async def get_offdays_for_user(user_id: str, token: str = Query(...)):
    """Verwaltung: Saldo + komplette Historie eines bestimmten Users."""
    caller = await _get_user(token)
    if not _has_verwaltung(caller) and caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    balance = await _balance_for_user(user_id)
    entries = await db.offday_ledger.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort([("ref_date", -1), ("created_at", -1)]).to_list(1000)
    return {"user_id": user_id, "balance": balance, "entries": entries}


@router.post("/adjust")
async def manual_adjust(data: dict = Body(...), token: str = Query(...)):
    """Verwaltung: Manuelles Plus/Minus auf das Offday-Konto eines Users.

    Body: { user_id, delta (int), note, ref_date (optional, "YYYY-MM-DD"),
            affect_overtime (bool, default True) }

    Wenn `affect_overtime=True` (Default): Zusaetzlich zur Ledger-Buchung wird
    auch das Ueberstunden-Konto angepasst — bei `delta<0` (Abziehen = Offday
    konsumiert) wird das Tages-Soll aus dem Wochenplan des `ref_date` von der
    `overtime_baseline` abgebucht; bei `delta>0` (Gutschrift) analog aufgerechnet.
    Anschliessend wird der Recompute mit `force=True` ausgeloest und ein
    Audit-Log-Eintrag geschrieben.

    Wenn `affect_overtime=False`: Nur Ledger-Buchung (fuer Sonderfaelle wie
    Sonntagsarbeit-Nachtrag, wo das Ueberstundenkonto schon durch den
    Time-Entry gutgeschrieben wurde).
    """
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    user_id = data.get("user_id")
    delta = data.get("delta")
    note = (data.get("note") or "").strip()
    ref_date = (data.get("ref_date") or "").strip() or _date.today().isoformat()
    affect_overtime = data.get("affect_overtime")
    if affect_overtime is None:
        affect_overtime = True
    # Validierung ISO-Datum
    try:
        _refdt = _date.fromisoformat(ref_date)
    except Exception:
        raise HTTPException(status_code=400, detail="ref_date muss im Format YYYY-MM-DD sein")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id fehlt")
    try:
        delta = int(delta)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="delta muss eine Ganzzahl sein")
    if delta == 0:
        raise HTTPException(status_code=400, detail="delta darf nicht 0 sein")

    target = await db.users.find_one({"id": user_id}, {"_id": 0, "name": 1})
    if not target:
        raise HTTPException(status_code=404, detail="User nicht gefunden")

    await db.offday_ledger.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "user_name": target.get("name", ""),
        "delta": delta,
        "kind": "manual_adjust",
        "source": "manual",
        "source_label": "Manuelle Korrektur",
        "reason": "admin_adjust",
        "ref_date": ref_date,
        "ref_id": None,
        "note": note,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": caller.get("name") or caller.get("email") or "admin",
    })
    new_balance = await _balance_for_user(user_id)

    # ── Ueberstunden-Konto anpassen (Feb 2026 Fix) ────────────────────────
    # Semantik: NUR Abzuege (delta<0) reduzieren das Ueberstunden-Konto —
    # der MA verbraucht seine Ueberstunden fuer den freien Tag.
    # Gutschriften (delta>0) beruehren das Ueberstunden-Konto NICHT: das
    # Offday-Guthaben kommt entweder aus tatsaechlicher Sonntagsarbeit
    # (dort wurde die Zeit schon per time_entry auf's Konto gebucht) oder
    # aus einer geschenkten Zuweisung durch den Admin (die haben keinen
    # Ueberstunden-Gegenwert).
    overtime_deducted_h = 0.0
    if affect_overtime and delta < 0:
        try:
            from routes import employee as _em
            _ws = await db.work_schedules.find_one({"user_id": user_id}, {"_id": 0}) or {}
            _mins_per_day = _em._soll_minutes_from_schedule(_ws, _refdt.weekday())
            _h_per_day = _mins_per_day / 60.0
            overtime_deducted_h = round(delta * _h_per_day, 2)  # negativ
            if _h_per_day > 0:
                await db.hr_data.update_one(
                    {"user_id": user_id, "year": _refdt.year},
                    {"$inc": {"overtime_baseline": overtime_deducted_h}},
                    upsert=True,
                )
                await _em._recompute_overtime_for_year(user_id, _refdt.year, force=True)
                await _em._log_audit(
                    user_id, "offday_manual_adjust", caller,
                    after={"ref_date": ref_date, "delta": delta,
                           "overtime_delta_h": overtime_deducted_h, "note": note},
                    summary=f"Offday abgezogen {ref_date} ({delta:+d} Tag / {overtime_deducted_h:.2f}h Ueberstunden)",
                )
        except Exception as _e:
            import logging
            logging.getLogger("employee").warning(f"Offday-Manual-Adjust Overtime-Update fehlgeschlagen: {_e}")
    else:
        # Gutschrift oder affect_overtime=False -> nur Ledger + Audit ohne Overtime-Effekt
        try:
            from routes import employee as _em
            _label = "Offday gutgeschrieben" if delta > 0 else "Offday-Ledger-Korrektur"
            await _em._log_audit(
                user_id, "offday_manual_adjust", caller,
                after={"ref_date": ref_date, "delta": delta,
                       "overtime_delta_h": 0.0, "note": note},
                summary=f"{_label} {ref_date} ({delta:+d} Tag, ohne Ueberstunden-Effekt)",
            )
        except Exception as _e:
            import logging
            logging.getLogger("employee").warning(f"Offday-Manual-Adjust Audit-Log fehlgeschlagen: {_e}")

    return {"ok": True, "new_balance": new_balance, "overtime_delta_h": overtime_deducted_h}


@router.post("/recompute")
async def recompute(token: str = Query(...)):
    """Verwaltung: Neuberechnung aller automatischen Accruals aus den
    time_entries. Sinnvoll wenn ein Mitarbeiter rueckwirkend Stempelzeiten
    eingetragen hat oder das Feature nachtraeglich aktiviert wurde.

    Achtung: loescht ALLE bestehenden `source=clock_in` Eintraege und legt
    sie aus den time_entries neu an. Manuelle Adjustments und shift-
    Verbrauche bleiben erhalten.
    """
    caller = await _get_user(token)
    if not _has_verwaltung(caller):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    deleted = await db.offday_ledger.delete_many({"source": "clock_in"})

    # Distinct (user_id, date) pairs aus time_entries
    pipeline = [
        {"$match": {"date": {"$ne": None}}},
        {"$group": {
            "_id": {"user_id": "$user_id", "date": "$date"},
            "user_name": {"$first": "$user_name"},
        }},
    ]
    pairs = await db.time_entries.aggregate(pipeline).to_list(50000)
    granted = 0
    for p in pairs:
        uid = p["_id"]["user_id"]
        d_str = p["_id"]["date"]
        if not uid or not d_str:
            continue
        if await grant_offday_for_work(uid, p.get("user_name", ""), d_str):
            granted += 1

    return {"ok": True, "deleted_clock_in_entries": deleted.deleted_count, "granted": granted}
