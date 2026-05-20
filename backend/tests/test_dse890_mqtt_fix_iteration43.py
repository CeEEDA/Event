"""Iteration 43 - Erweiterte Regression fuer den DSE 890 MQTT-Subtopic-Split-Fix.

Verifiziert:
  1. Throttle (5 Min) fuer Stromerzeuger - kein doppelter Insert innerhalb 5 Min
  2. latest_snapshot wird auch ohne Insert aktualisiert
  3. is_running-Fallback via persistiertem mqtt_status="running" (auch wenn
     aktuelles Topic kein rpm/engine_running enthaelt)
  4. is_running-Fallback via latest_snapshot.engine_running (DB-Snapshot)
  5. Snapshot-Merge fuellt alle Telemetry-Felder
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient


def test_throttle_blocks_double_insert_within_5min():
    asyncio.run(_throttle())


def test_running_fallback_via_mqtt_status():
    asyncio.run(_mqtt_status_fallback())


def test_running_fallback_via_snapshot_engine_running():
    asyncio.run(_snapshot_fallback())


def test_snapshot_updated_when_no_insert():
    asyncio.run(_snapshot_update_no_insert())


async def _setup(controller="DSE 8610 MK2", mqtt_status="online", snapshot=None):
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    dev_id = "test_dse890_it43_" + uuid.uuid4().hex[:8]
    gen_id = f"dev-{dev_id}"

    dev_doc = {
        "id": dev_id, "device_type": "stromerzeuger",
        "controller": controller, "serial_number": "TEST_IT43",
        "mqtt_status": mqtt_status,
    }
    if snapshot:
        dev_doc["latest_snapshot"] = snapshot
    await db.devices.insert_one(dev_doc)
    await db.generators.insert_one({
        "id": gen_id, "name": "TEST_IT43", "controller": controller,
        "status": "online",
    })

    import mqtt_service
    mqtt_service._db = db
    mqtt_service._devices_cache = await db.devices.find({}, {"_id": 0}).to_list(None)
    mqtt_service._telemetry_insert_cache.pop(gen_id, None)
    return db, dev_id, gen_id, mqtt_service


async def _cleanup(db, dev_id, gen_id):
    await db.devices.delete_one({"id": dev_id})
    await db.generators.delete_one({"id": gen_id})
    await db.generator_telemetry.delete_many({"generator_id": gen_id})


async def _throttle():
    db, dev_id, gen_id, mq = await _setup()
    try:
        ts1 = datetime.now(timezone.utc).isoformat()
        engine_payload = {"AAAA1": {"P004": {"R001": 80, "R005": 280, "R006": 1400},
                                    "P003": {"R022": 0}}}
        await mq._ingest_telemetry_device(
            dev_id, "eventenergie/DSE8610/AAAA1/engine", "{}", engine_payload, ts1)

        # Sofortiges 2. Engine-Topic -> Throttle (5 Min) muss greifen
        ts2 = datetime.now(timezone.utc).isoformat()
        await mq._ingest_telemetry_device(
            dev_id, "eventenergie/DSE8610/AAAA1/engine", "{}", engine_payload, ts2)

        rows = await db.generator_telemetry.find(
            {"generator_id": gen_id}, {"_id": 0}).to_list(10)
        assert len(rows) == 1, f"Throttle: erwartet 1 Insert (5min Sperre), bekommen {len(rows)}"
    finally:
        await _cleanup(db, dev_id, gen_id)


async def _mqtt_status_fallback():
    """/generator-Topic OHNE rpm/engine_running, aber Device mqtt_status='running'
       -> Fallback muss is_running=True liefern und Insert ausloesen."""
    db, dev_id, gen_id, mq = await _setup(mqtt_status="running")
    try:
        ts = datetime.now(timezone.utc).isoformat()
        gen_payload = {"BBBB1": {
            "P004": {"R007": 500, "R008": 2300, "R010": 2295, "R012": 2305,
                     "R020": 150, "R022": 145, "R024": 152},
            "P007": {"R004": 999}}}
        await mq._ingest_telemetry_device(
            dev_id, "eventenergie/DSE8610/BBBB1/generator", "{}", gen_payload, ts)

        rows = await db.generator_telemetry.find(
            {"generator_id": gen_id}, {"_id": 0}).to_list(10)
        assert len(rows) == 1, f"mqtt_status-Fallback: erwartet 1 Insert, bekommen {len(rows)}"
        assert rows[0]["voltage_l1"] == 230.0
        assert rows[0]["energy_kwh"] == 999
        assert rows[0]["frequency"] == 50.0
    finally:
        await _cleanup(db, dev_id, gen_id)


async def _snapshot_fallback():
    """Snapshot in DB hat engine_running=True (z.B. vom letzten /engine-Topic
       vor Service-Restart). Aktuelles /generator-Topic ohne rpm -> Fallback."""
    db, dev_id, gen_id, mq = await _setup(
        mqtt_status="online",
        snapshot={"engine_running": True, "rpm": 1500, "coolant_temp": 82})
    try:
        ts = datetime.now(timezone.utc).isoformat()
        gen_payload = {"CCCC1": {
            "P004": {"R007": 500, "R008": 2300, "R010": 2300, "R012": 2300,
                     "R020": 150, "R022": 150, "R024": 150}}}
        await mq._ingest_telemetry_device(
            dev_id, "eventenergie/DSE8610/CCCC1/generator", "{}", gen_payload, ts)

        rows = await db.generator_telemetry.find(
            {"generator_id": gen_id}, {"_id": 0}).to_list(10)
        assert len(rows) == 1, f"snapshot-Fallback: erwartet 1 Insert, bekommen {len(rows)}"
        # Snapshot-Merge: rpm/coolant_temp aus DB-Snapshot
        assert rows[0]["rpm"] == 1500
        assert rows[0]["coolant_temp"] == 82
        assert rows[0]["voltage_l1"] == 230.0
    finally:
        await _cleanup(db, dev_id, gen_id)


async def _snapshot_update_no_insert():
    """Generator offline / nicht laufend -> kein Insert, aber latest_snapshot
       muss trotzdem aktualisiert werden."""
    db, dev_id, gen_id, mq = await _setup(mqtt_status="offline")
    try:
        ts = datetime.now(timezone.utc).isoformat()
        gen_payload = {"DDDD1": {
            "P004": {"R008": 2350, "R010": 2350, "R012": 2350}}}
        await mq._ingest_telemetry_device(
            dev_id, "eventenergie/DSE8610/DDDD1/generator", "{}", gen_payload, ts)

        rows = await db.generator_telemetry.find(
            {"generator_id": gen_id}).to_list(10)
        assert len(rows) == 0, f"Offline: erwartet 0 Inserts, bekommen {len(rows)}"

        # Snapshot/Status muss aktualisiert sein
        dev = await db.devices.find_one({"id": dev_id}, {"_id": 0})
        snap = (dev or {}).get("latest_snapshot") or {}
        assert snap.get("voltage_l1") == 235.0, \
            f"Snapshot nicht aktualisiert. Snapshot: {snap}"
    finally:
        await _cleanup(db, dev_id, gen_id)
