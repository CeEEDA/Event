"""Regression-Test: DSE 890 / DSE 8610 MK2 ueber MQTT-Broker splittet
GenComm-Register auf mehrere Subtopics (/engine, /generator). Frueher
landeten /generator-Daten (voltage_l*, current_l*, frequency, energy_kwh)
NIE in der generator_telemetry-History, weil die "is_running"-Erkennung
nur das aktuelle Payload betrachtete und /generator-Topics weder rpm
noch engine_running enthalten.

Dieser Test stellt sicher dass:
  1. Beide Subtopics einen Insert ausloesen wenn der Motor laeuft (auch wenn
     das aktuelle Subtopic keine Engine-Daten enthaelt).
  2. Jeder Insert eine vollstaendige Zeile produziert (Snapshot-Merge fuellt
     fehlende Felder), damit Charts keine Datenluecken haben.
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient


def test_dse890_split_topics_produce_full_history_rows():
    asyncio.run(_run())


async def _run():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    dev_id = "test-dse890-split-" + uuid.uuid4().hex[:8]
    gen_id = f"dev-{dev_id}"

    try:
        await db.devices.insert_one({
            "id": dev_id, "device_type": "stromerzeuger",
            "controller": "DSE 8610 MK2", "serial_number": "TEST_SPLIT",
            "mqtt_status": "online",
        })
        await db.generators.insert_one({
            "id": gen_id, "name": "TEST_SPLIT", "controller": "DSE 8610 MK2",
            "status": "online",
        })

        import mqtt_service
        mqtt_service._db = db
        mqtt_service._devices_cache = await db.devices.find({}, {"_id": 0}).to_list(None)
        mqtt_service._telemetry_insert_cache.clear()

        ts1 = datetime.now(timezone.utc).isoformat()
        engine_payload = {
            "ABCD1234": {
                "P004": {"R001": 85, "R003": 75, "R005": 280, "R006": 1500},
                "P003": {"R022": 0},
            }
        }
        await mqtt_service._ingest_telemetry_device(
            dev_id, "eventenergie/DSE8610/ABCD1234/engine",
            "{}", engine_payload, ts1,
        )

        # Throttle bypass
        mqtt_service._telemetry_insert_cache[gen_id] = 0

        ts2 = datetime.now(timezone.utc).isoformat()
        # /generator: KEIN rpm, KEIN engine_running -> trotzdem Insert erwartet
        generator_payload = {
            "ABCD1234": {
                "P004": {
                    "R007": 500,
                    "R008": 2300, "R010": 2295, "R012": 2305,
                    "R020": 150, "R022": 145, "R024": 152,
                },
                "P007": {"R004": 12345},
            }
        }
        await mqtt_service._ingest_telemetry_device(
            dev_id, "eventenergie/DSE8610/ABCD1234/generator",
            "{}", generator_payload, ts2,
        )

        rows = await db.generator_telemetry.find(
            {"generator_id": gen_id}, {"_id": 0}
        ).sort("timestamp", 1).to_list(10)

        # 1) Beide Subtopics muessen einen Insert produzieren
        assert len(rows) == 2, f"Erwartet 2 Inserts, bekommen {len(rows)}: {rows}"

        engine_row = next((r for r in rows if r["raw_topic"].endswith("/engine")), None)
        generator_row = next((r for r in rows if r["raw_topic"].endswith("/generator")), None)
        assert engine_row is not None
        assert generator_row is not None

        # 2) /engine-Row hat Engine-Werte (war vorher schon OK)
        assert engine_row["rpm"] == 1500
        assert engine_row["coolant_temp"] == 85
        assert engine_row["battery_voltage"] == 28.0

        # 3) /generator-Row hat voltage/current/frequency/energy_kwh
        #    (das war der Bug - vorher fehlten die in der History)
        assert generator_row["voltage_l1"] == 230.0
        assert generator_row["voltage_l2"] == 229.5
        assert generator_row["voltage_l3"] == 230.5
        assert generator_row["current_l1"] == 15.0
        assert generator_row["current_l2"] == 14.5
        assert generator_row["current_l3"] == 15.2
        assert generator_row["frequency"] == 50.0
        assert generator_row["energy_kwh"] == 12345

        # 4) /generator-Row hat AUSSERDEM die gemergten Engine-Snapshot-Werte
        #    aus dem vorigen /engine-Topic (Snapshot-Merge), damit Charts
        #    keine Luecken bekommen
        assert generator_row["rpm"] == 1500
        assert generator_row["coolant_temp"] == 85
        assert generator_row["battery_voltage"] == 28.0

    finally:
        await db.devices.delete_one({"id": dev_id})
        await db.generators.delete_one({"id": gen_id})
        await db.generator_telemetry.delete_many({"generator_id": gen_id})
