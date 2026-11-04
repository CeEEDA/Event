"""Regressionstests Stundenkonto (Nov 2026).

1. Ueberstundenabbau kam beim naechsten Recompute zurueck (Andre/Martin/Dirk/Christine)
2. Direkt eingetragener Urlaub (vacation_entries) wurde als "kein Stempel" abgezogen
3. Offday doppelt abgezogen (Baseline-Abzug + Tagesbilanz) - Offday-Konto und Einsatzplan
4. Einsatzplan zeigt Offdays aus dem Offday-Konto nicht an
5. Aenderungsprotokoll: automatische Aenderungen eines Tages werden protokolliert

Laeuft in einer EIGENEN Test-Datenbank (nie gegen die Live-DB).
"""
import asyncio
import os
import uuid
from datetime import date, timedelta, datetime, timezone

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
TEST_DB = "eventenergie_pytest_stundenkonto"

from routes import employee as em  # noqa: E402
from routes import offdays as od  # noqa: E402

ADMIN = {"id": "admin-test", "name": "Admin Test", "role": "admin"}


def _last_weekday(before: date, weekday: int) -> date:
    d = before - timedelta(days=1)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def with_db(fn):
    """Fuehrt einen async-Test in eigener Test-DB aus (ohne pytest-asyncio)."""
    def wrapper(monkeypatch):
        async def main():
            client = AsyncIOMotorClient(MONGO_URL)
            await client.drop_database(TEST_DB)
            database = client[TEST_DB]
            monkeypatch.setattr(em, "db", database)
            monkeypatch.setattr(od, "db", database)

            async def _fake_user(token):
                return ADMIN
            monkeypatch.setattr(em, "_get_user", _fake_user)
            monkeypatch.setattr(od, "_get_user", _fake_user)
            try:
                await fn(database)
            finally:
                await client.drop_database(TEST_DB)
                client.close()
        asyncio.run(main())
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


async def _seed(db, baseline=100.0):
    """MA mit Mo-Fr 8h, Baseline am 1.1. (ganzes Jahr wird bilanziert)."""
    uid = str(uuid.uuid4())
    year = date.today().year
    await db.users.insert_one({"id": uid, "name": "Test MA", "role": "mitarbeiter"})
    await db.hr_data.insert_one({
        "user_id": uid, "year": year, "overtime_hours": baseline,
        "overtime_baseline": baseline, "overtime_baseline_v2_migrated": True,
        "overtime_baseline_reason": "test", "overtime_baseline_set_at": f"{year}-01-01T00:00:00+00:00",
    })
    await db.work_schedules.insert_one({
        "user_id": uid,
        "days": {d: {"soll_hours": "8"} for d in ["montag", "dienstag", "mittwoch", "donnerstag", "freitag"]},
    })
    # Alle Werktage dieses Jahres bis heute mit genau 8h "gestempelt" -> Tagesbilanz 0
    today = date.today()
    cur = date(year, 1, 1)
    docs = []
    while cur <= today:
        if cur.weekday() < 5 and cur.isoformat() not in em._get_holidays(year):
            docs.append({"id": str(uuid.uuid4()), "user_id": uid, "date": cur.isoformat(),
                         "duration_minutes": 480.0, "type": None,
                         "clock_in": f"{cur.isoformat()}T06:00:00+00:00",
                         "clock_out": f"{cur.isoformat()}T14:00:00+00:00"})
        cur += timedelta(days=1)
    if docs:
        await db.time_entries.insert_many(docs)
    return uid, year


async def _ot(db, uid, year):
    return float((await db.hr_data.find_one({"user_id": uid, "year": year}))["overtime_hours"])


def _skip_if_early_january():
    if date.today() < date(date.today().year, 1, 15):
        pytest.skip("Braucht vergangene Werktage im laufenden Jahr")


@with_db
async def test_ueberstundenabbau_bleibt_nach_recompute_abgezogen(db):
    _skip_if_early_january()
    uid, year = await _seed(db)
    day = _last_weekday(date.today(), 2)  # letzter Mittwoch
    await db.time_entries.delete_many({"user_id": uid, "date": day.isoformat()})
    await em.admin_create_time_off(token="x", data={
        "user_id": uid, "type": "ueberstundenabbau",
        "start_date": day.isoformat(), "end_date": day.isoformat()})
    assert await _ot(db, uid, year) == pytest.approx(92.0)
    # Weitere automatische Neuberechnungen duerfen den Abbau NICHT zurueckgeben
    await em._recompute_overtime_for_year(uid, year)
    await em._recompute_overtime_for_year(uid, year, force=True)
    assert await _ot(db, uid, year) == pytest.approx(92.0)
    # Loeschen storniert den Abbau - der Tag zaehlt dann wieder als Arbeitstag
    # ohne Stempel (-8h), netto bleibt das Konto gleich. Protokoll erklaert das.
    req = await db.time_off_requests.find_one({"user_id": uid})
    await em.admin_delete_time_off(req["id"], token="x")
    assert await _ot(db, uid, year) == pytest.approx(92.0)
    log = await db.time_audit_log.find_one({"target_user_id": uid, "action": "time_off_delete"})
    assert "storniert" in log["summary"]


@with_db
async def test_geplanter_abbau_loeschen_gibt_stunden_zurueck(db):
    uid, year = await _seed(db)
    day = date.today() + timedelta(days=7)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    if day.year != year:
        pytest.skip("Jahreswechsel")
    await em.admin_create_time_off(token="x", data={
        "user_id": uid, "type": "ueberstundenabbau",
        "start_date": day.isoformat(), "end_date": day.isoformat()})
    assert await _ot(db, uid, year) == pytest.approx(92.0)
    req = await db.time_off_requests.find_one({"user_id": uid})
    await em.admin_delete_time_off(req["id"], token="x")
    assert await _ot(db, uid, year) == pytest.approx(100.0)


@with_db
async def test_stundenweiser_abbau_zukuenftig_sofort_abgezogen(db):
    uid, year = await _seed(db)
    day = date.today() + timedelta(days=7)
    if day.year != year:
        pytest.skip("Jahreswechsel")
    await em.admin_create_time_off(token="x", data={
        "user_id": uid, "type": "ueberstundenabbau", "start_date": day.isoformat(), "hours": 4.5})
    assert await _ot(db, uid, year) == pytest.approx(95.5)


@with_db
async def test_direkt_eingetragener_urlaub_kostet_keine_stunden(db):
    _skip_if_early_january()
    uid, year = await _seed(db)
    day = _last_weekday(date.today(), 1)  # letzter Dienstag
    await db.time_entries.delete_many({"user_id": uid, "date": day.isoformat()})
    await em.add_vacation_entry(uid, token="x", data={"start_date": day.isoformat(), "end_date": day.isoformat()})
    assert await em._recompute_overtime_for_year(uid, year, force=True) == pytest.approx(100.0)


@with_db
async def test_offday_konto_abzug_nur_einmal(db):
    _skip_if_early_january()
    uid, year = await _seed(db)
    day = _last_weekday(date.today(), 3)  # letzter Donnerstag
    await db.time_entries.delete_many({"user_id": uid, "date": day.isoformat()})
    res = await od.manual_adjust(data={"user_id": uid, "delta": -1, "ref_date": day.isoformat()}, token="x")
    assert res["overtime_delta_h"] == pytest.approx(-8.0)
    # Vorher: -8 (Baseline) und nochmal -8 (Tag ohne Stempel) = 84
    assert await _ot(db, uid, year) == pytest.approx(92.0)
    assert await em._recompute_overtime_for_year(uid, year, force=True) == pytest.approx(92.0)


@with_db
async def test_offday_konto_bei_direkt_eingetragenem_urlaub_kein_abzug(db):
    _skip_if_early_january()
    uid, year = await _seed(db)
    day = _last_weekday(date.today(), 4)  # letzter Freitag
    await db.time_entries.delete_many({"user_id": uid, "date": day.isoformat()})
    await db.vacation_entries.insert_one({"id": "v1", "user_id": uid, "year": year,
                                          "start_date": day.isoformat(), "end_date": day.isoformat(), "days": 1})
    res = await od.manual_adjust(data={"user_id": uid, "delta": -1, "ref_date": day.isoformat()}, token="x")
    assert res["overtime_delta_h"] == 0
    assert await em._recompute_overtime_for_year(uid, year, force=True) == pytest.approx(100.0)


@with_db
async def test_einsatzplan_offday_einmal_und_loeschen_netto_null(db):
    _skip_if_early_january()
    uid, year = await _seed(db)
    day = _last_weekday(date.today(), 0)  # letzter Montag
    await db.time_entries.delete_many({"user_id": uid, "date": day.isoformat()})
    # Ohne Offday: Tag ohne Stempel = -8
    assert await em._recompute_overtime_for_year(uid, year, force=True) == pytest.approx(92.0)
    res = await em.upsert_shift_assignment(data={
        "user_id": uid, "date": day.isoformat(), "is_offday": True,
        "week_key": em._iso_week_key(day)}, token="x")
    # Offday kostet genau einmal 8h (vorher 16h)
    assert await _ot(db, uid, year) == pytest.approx(92.0)
    a = await db.shift_assignments.find_one({"id": res["id"]})
    assert a["overtime_deducted_h"] == pytest.approx(8.0)
    await em.delete_shift_assignment(res["id"], token="x")
    assert await _ot(db, uid, year) == pytest.approx(92.0)


@with_db
async def test_einsatzplan_offday_bei_urlaub_kein_abzug(db):
    _skip_if_early_january()
    uid, year = await _seed(db)
    day = _last_weekday(date.today(), 2)
    await db.time_entries.delete_many({"user_id": uid, "date": day.isoformat()})
    await db.time_off_requests.insert_one({"id": "r1", "user_id": uid, "type": "urlaub", "status": "approved",
                                           "start_date": day.isoformat(), "end_date": day.isoformat()})
    res = await em.upsert_shift_assignment(data={
        "user_id": uid, "date": day.isoformat(), "is_offday": True,
        "week_key": em._iso_week_key(day)}, token="x")
    assert await _ot(db, uid, year) == pytest.approx(100.0)
    a = await db.shift_assignments.find_one({"id": res["id"]})
    assert a["overtime_deducted_h"] == 0


@with_db
async def test_einsatzplan_zeigt_offday_aus_offday_konto(db):
    uid, year = await _seed(db)
    day = date.today() + timedelta(days=2)
    await od.manual_adjust(data={"user_id": uid, "delta": -1, "ref_date": day.isoformat(),
                                 "affect_overtime": False}, token="x")
    plan = await em.get_shift_plan(week=em._iso_week_key(day), token="x")
    offs = [a for a in plan["absences"] if a["type"] == "offday" and a["user_id"] == uid]
    assert len(offs) == 1 and offs[0]["start_date"] == day.isoformat()


@with_db
async def test_protokoll_zeigt_spaetere_aenderung_eines_tages(db):
    _skip_if_early_january()
    uid, year = await _seed(db)
    day = _last_weekday(date.today(), 1)
    await db.time_entries.delete_many({"user_id": uid, "date": day.isoformat()})
    await em._recompute_overtime_for_year(uid, year, force=True)  # Tag: -8h
    await db.time_off_requests.insert_one({"id": "k1", "user_id": uid, "type": "krank", "status": "approved",
                                           "start_date": day.isoformat(), "end_date": day.isoformat()})
    await em._recompute_overtime_for_year(uid, year, force=True)  # Tag: 0h -> +8h Aenderung
    logs = await db.time_audit_log.find({"target_user_id": uid, "action": "auto_balance_day",
                                         "details.date": day.isoformat()}).sort("created_at", 1).to_list(10)
    assert len(logs) == 2
    assert "GEÄNDERT" in logs[1]["summary"] and "+8.00h" in logs[1]["summary"]
    summ = await db.time_audit_log.find({"target_user_id": uid, "action": "auto_balance_recompute"}
                                        ).sort("created_at", -1).to_list(1)
    assert "Tagesbilanz +8.00h" in summ[0]["summary"]
