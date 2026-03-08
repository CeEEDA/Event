import paho.mqtt.client as mqtt
import json
import logging
import asyncio
import threading
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

# Global MQTT client instance
_mqtt_client = None
_mqtt_thread = None
_db = None
_loop = None


def _on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        logger.info("MQTT: Connected to broker")
        # Subscribe synchronously in the callback - this is the correct approach
        config_data = userdata or {}
        topics = config_data.get("subscribe_topics", ["dse/#"])
        for topic in topics:
            client.subscribe(topic, qos=1)
            logger.info(f"MQTT: Subscribed to '{topic}'")
        # Update status async
        asyncio.run_coroutine_threadsafe(
            _update_connection_status("connected", "Verbunden"),
            _loop
        )
    else:
        logger.error(f"MQTT: Connection failed with code {reason_code}")
        asyncio.run_coroutine_threadsafe(
            _update_connection_status("error", f"Verbindungsfehler: {reason_code}"),
            _loop
        )


def _on_disconnect(client, userdata, flags, reason_code, properties=None):
    logger.warning(f"MQTT: Disconnected (code={reason_code})")
    asyncio.run_coroutine_threadsafe(
        _update_connection_status("disconnected", "Verbindung getrennt"),
        _loop
    )


def _on_message(client, userdata, msg):
    logger.info(f"MQTT: Message received on topic '{msg.topic}' ({len(msg.payload)} bytes)")
    try:
        asyncio.run_coroutine_threadsafe(_process_message(msg), _loop)
    except Exception as e:
        logger.error(f"MQTT: Error dispatching message: {e}")


async def _update_connection_status(status, message=""):
    if _db is None:
        return
    await _db.mqtt_config.update_one(
        {},
        {"$set": {
            "connection_status": status,
            "connection_message": message,
            "last_status_update": datetime.now(timezone.utc).isoformat()
        }}
    )


async def _subscribe_all(client):
    config = await _db.mqtt_config.find_one({}, {"_id": 0})
    if not config:
        return

    topics = config.get("subscribe_topics", ["dse/#"])
    for topic in topics:
        client.subscribe(topic, qos=1)
        logger.info(f"MQTT: Subscribed to '{topic}'")

    await _update_connection_status("connected", "Verbunden")


async def _process_message(msg):
    """Process an incoming MQTT message and store it."""
    topic = msg.topic
    try:
        payload_str = msg.payload.decode("utf-8")
    except UnicodeDecodeError:
        payload_str = msg.payload.hex()

    timestamp = datetime.now(timezone.utc).isoformat()

    # Store raw message for debugging (keep last 500)
    raw_doc = {
        "id": str(uuid.uuid4()),
        "topic": topic,
        "payload": payload_str,
        "timestamp": timestamp,
    }
    await _db.mqtt_raw_messages.insert_one(raw_doc)

    # Trim old raw messages (keep last 500)
    count = await _db.mqtt_raw_messages.count_documents({})
    if count > 500:
        oldest = await _db.mqtt_raw_messages.find({}, {"_id": 1}).sort("timestamp", 1).limit(count - 500).to_list(count - 500)
        if oldest:
            ids = [d["_id"] for d in oldest]
            await _db.mqtt_raw_messages.delete_many({"_id": {"$in": ids}})

    # Try to parse JSON payload
    parsed = None
    try:
        parsed = json.loads(payload_str)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to match this message to a generator via topic mappings
    mappings = await _db.mqtt_gateway_mappings.find({}, {"_id": 0}).to_list(100)
    for mapping in mappings:
        topic_prefix = mapping.get("topic_prefix", "")
        client_name = mapping.get("client_name", "")
        generator_id = mapping.get("generator_id")

        if not generator_id:
            continue

        # Match by topic prefix
        if topic_prefix and topic.startswith(topic_prefix):
            # Handle GPS topic separately (DSE890 gateway GPS)
            if topic.endswith("/gps"):
                await _process_gps(generator_id, payload_str, parsed, timestamp)
                return
            # Handle status topic - only update online status, don't store as telemetry
            if topic.endswith("/status"):
                await _process_status(generator_id, payload_str, timestamp)
                return
            await _ingest_telemetry(generator_id, topic, payload_str, parsed, timestamp)
            return

    # Also check if any generator has a dse_mqtt_topic_prefix that matches
    generators = await _db.generators.find({"dse_mqtt_topic_prefix": {"$exists": True, "$ne": ""}}, {"_id": 0, "id": 1, "dse_mqtt_topic_prefix": 1}).to_list(100)
    for gen in generators:
        prefix = gen.get("dse_mqtt_topic_prefix", "")
        if prefix and topic.startswith(prefix):
            if topic.endswith("/gps"):
                await _process_gps(gen["id"], payload_str, parsed, timestamp)
                return
            if topic.endswith("/status"):
                await _process_status(gen["id"], payload_str, timestamp)
                return
            await _ingest_telemetry(gen["id"], topic, payload_str, parsed, timestamp)
            return

    # No mapping found - log for discovery
    logger.debug(f"MQTT: Unmatched message on topic '{topic}'")


async def _process_gps(generator_id, raw_payload, parsed, timestamp):
    """Process GPS data from DSE890 gateway (Function 10 format).
    DSE890 GPS JSON format: {"UID":{"LAT": 54.176182,"LON": -0.311576}}
    """
    lat = None
    lng = None

    if isinstance(parsed, dict):
        for uid_key, uid_data in parsed.items():
            if isinstance(uid_data, dict):
                # DSE890 format: {"UID": {"LAT": x, "LON": y}}
                lat = uid_data.get("LAT") or uid_data.get("lat") or uid_data.get("latitude")
                lng = uid_data.get("LON") or uid_data.get("lon") or uid_data.get("lng") or uid_data.get("longitude")
                if lat is not None:
                    break

        # Flat format fallback
        if lat is None:
            lat = parsed.get("LAT") or parsed.get("lat") or parsed.get("latitude")
            lng = parsed.get("LON") or parsed.get("lon") or parsed.get("lng") or parsed.get("longitude")

    if lat is not None and lng is not None:
        try:
            lat = float(lat)
            lng = float(lng)
            if -90 <= lat <= 90 and -180 <= lng <= 180 and (lat != 0 or lng != 0):
                await _db.generators.update_one(
                    {"id": generator_id},
                    {"$set": {"latitude": lat, "longitude": lng, "last_gps_update": timestamp}}
                )
                logger.info(f"MQTT: GPS updated for generator {generator_id}: {lat}, {lng}")
            else:
                logger.debug(f"MQTT: GPS invalid coordinates for {generator_id}: {lat}, {lng}")
        except (ValueError, TypeError):
            logger.debug(f"MQTT: GPS parse error for {generator_id}: {raw_payload[:100]}")
    else:
        logger.debug(f"MQTT: GPS no coordinates found for {generator_id}: {raw_payload[:200]}")


async def _process_status(generator_id, raw_payload, timestamp):
    """Process status messages (e.g. 'UID:Connected') - just update online status."""
    status = "online"
    if "disconnected" in raw_payload.lower():
        status = "offline"
    await _db.generators.update_one(
        {"id": generator_id},
        {"$set": {"last_seen": timestamp, "status": status}}
    )
    logger.debug(f"MQTT: Status '{raw_payload.strip()}' for generator {generator_id}")



async def _ingest_telemetry(generator_id, topic, raw_payload, parsed, timestamp):
    """Convert MQTT data to telemetry and store it."""
    # Check generators collection first, then devices for virtual generators
    gen = await _db.generators.find_one({"id": generator_id}, {"_id": 0})
    if not gen and generator_id.startswith("dev-"):
        device_id = generator_id[4:]
        device = await _db.devices.find_one({"id": device_id}, {"_id": 0})
        if device:
            gen = {"id": generator_id, "name": device.get("serial_number", "")}
    if not gen:
        logger.warning(f"MQTT: Generator {generator_id} not found for topic {topic}")
        return

    telemetry = {
        "id": str(uuid.uuid4()),
        "generator_id": generator_id,
        "timestamp": timestamp,
        "source": "mqtt",
        "raw_topic": topic,
    }

    if isinstance(parsed, dict):
        # Check if this is DSE Gencomm register format: {"UID":{"P004":{"R000":val,...}}}
        gencomm_data = _parse_gencomm_registers(parsed, topic)
        if gencomm_data:
            telemetry.update(gencomm_data)
        else:
            # Standard JSON field mapping (legacy format)
            field_map = {
                "voltage_l1": ["voltage_l1", "voltageL1", "V_L1", "volts_l1"],
                "voltage_l2": ["voltage_l2", "voltageL2", "V_L2", "volts_l2"],
                "voltage_l3": ["voltage_l3", "voltageL3", "V_L3", "volts_l3"],
                "current_l1": ["current_l1", "currentL1", "I_L1", "amps_l1"],
                "current_l2": ["current_l2", "currentL2", "I_L2", "amps_l2"],
                "current_l3": ["current_l3", "currentL3", "I_L3", "amps_l3"],
                "frequency": ["frequency", "freq", "Hz"],
                "power_kw": ["power_kw", "powerKW", "kW", "active_power", "power"],
                "power_kva": ["power_kva", "powerKVA", "kVA", "apparent_power"],
                "load_percent": ["load_percent", "load", "loadPercent"],
                "rpm": ["rpm", "RPM", "engine_speed"],
                "oil_pressure": ["oil_pressure", "oilPressure", "oil_press"],
                "coolant_temp": ["coolant_temp", "coolantTemp", "coolant_temperature", "water_temp"],
                "fuel_level": ["fuel_level", "fuelLevel", "fuel"],
                "battery_voltage": ["battery_voltage", "batteryVoltage", "battery", "batt_volts"],
                "hours_run": ["hours_run", "hoursRun", "run_hours", "engine_hours"],
                "engine_running": ["engine_running", "engineRunning", "running"],
                "mode": ["mode", "operating_mode", "genset_mode"],
                "gps_lat": ["gps_lat", "latitude", "lat"],
                "gps_lng": ["gps_lng", "longitude", "lng", "lon"],
            }

            for our_field, possible_keys in field_map.items():
                for key in possible_keys:
                    if key in parsed:
                        val = parsed[key]
                        if isinstance(val, (int, float)):
                            telemetry[our_field] = val
                        elif isinstance(val, bool):
                            telemetry[our_field] = val
                        elif isinstance(val, str):
                            try:
                                telemetry[our_field] = float(val)
                            except ValueError:
                                telemetry[our_field] = val
                        break

            mapped_keys = set()
            for possible_keys in field_map.values():
                mapped_keys.update(possible_keys)
            extra = {k: v for k, v in parsed.items() if k not in mapped_keys}
            if extra:
                telemetry["extra_data"] = extra

    await _db.generator_telemetry.insert_one(telemetry)

    # Update generator status
    status_update = {"last_seen": timestamp}
    if telemetry.get("engine_running") is True or telemetry.get("rpm", 0) > 0:
        status_update["status"] = "running"
    elif telemetry.get("engine_running") is False:
        status_update["status"] = "standby"
    else:
        status_update["status"] = "online"

    if telemetry.get("gps_lat") and telemetry.get("gps_lng"):
        status_update["latitude"] = telemetry["gps_lat"]
        status_update["longitude"] = telemetry["gps_lng"]

    await _db.generators.update_one({"id": generator_id}, {"$set": status_update})

    result = {k: v for k, v in telemetry.items() if k != "_id"}
    logger.info(f"MQTT: Telemetry stored for generator {generator_id}")


def _parse_gencomm_registers(parsed, topic):
    """Parse DSE Gencomm register format: {"UID":{"P004":{"R000":val,...}}}
    Returns mapped telemetry fields or None if not Gencomm format."""
    # Find the inner register data: drill into UID -> Page -> Registers
    registers = {}
    for uid_key, uid_data in parsed.items():
        if not isinstance(uid_data, dict):
            continue
        for page_key, page_data in uid_data.items():
            if not isinstance(page_data, dict):
                continue
            if page_key.startswith("P"):
                page_num = int(page_key[1:])
                for reg_key, val in page_data.items():
                    if reg_key.startswith("R"):
                        offset = int(reg_key[1:])
                        registers[(page_num, offset)] = val

    if not registers:
        return None

    result = {}
    INVALID_16 = 32764   # 0x7FFC - DSE "not available" for 16-bit
    INVALID_32 = 2147483644  # 0x7FFFFFFC - DSE "not available" for 32-bit

    def valid(val):
        """Check if value is a valid reading (not DSE error/unavailable marker)."""
        if val is None:
            return False
        if val in (INVALID_16, INVALID_16 + 1, INVALID_16 + 2, INVALID_16 + 3,
                   INVALID_32, INVALID_32 + 1, INVALID_32 + 2, INVALID_32 + 3,
                   32767, 2147483647, 65535, 4294967295):
            return False
        return True

    # Detect topic type for context
    topic_lower = topic.lower()

    # Page 4 register mapping (standard DSE Gencomm instrumentation)
    # Engine parameters
    if valid(registers.get((4, 0))):
        result["oil_pressure"] = registers[(4, 0)]          # kPa
    if valid(registers.get((4, 1))):
        result["coolant_temp"] = registers[(4, 1)]           # °C
    if valid(registers.get((4, 3))):
        result["fuel_level"] = registers[(4, 3)]             # %
    if valid(registers.get((4, 5))):
        result["battery_voltage"] = registers[(4, 5)] / 10.0  # 0.1V -> V
    if valid(registers.get((4, 6))):
        result["rpm"] = registers[(4, 6)]                    # RPM
        result["engine_running"] = registers[(4, 6)] > 0

    # Generator parameters
    if valid(registers.get((4, 7))):
        result["frequency"] = registers[(4, 7)] / 10.0      # 0.1Hz -> Hz

    # Voltages L-N (32-bit at offset 8,10,12)
    for offset, field in [(8, "voltage_l1"), (10, "voltage_l2"), (12, "voltage_l3")]:
        val = registers.get((4, offset))
        if val is not None and valid(val):
            result[field] = val / 10.0                       # 0.1V -> V

    # Voltages L-L (32-bit at offset 14,16,18)
    for offset, field in [(14, "voltage_l1_l2"), (16, "voltage_l2_l3"), (18, "voltage_l3_l1")]:
        val = registers.get((4, offset))
        if val is not None and valid(val):
            result[field] = val / 10.0

    # Currents (32-bit at offset 20,22,24)
    for offset, field in [(20, "current_l1"), (22, "current_l2"), (24, "current_l3")]:
        val = registers.get((4, offset))
        if val is not None and valid(val):
            result[field] = val / 10.0                       # 0.1A -> A

    # Power per phase (32-bit at offset 28,30,32) - watts
    for offset, field in [(28, "power_l1_w"), (30, "power_l2_w"), (32, "power_l3_w")]:
        val = registers.get((4, offset))
        if val is not None and valid(val):
            result[field] = val

    # Total power (32-bit at offset 34)
    if valid(registers.get((4, 34))):
        result["power_kw"] = registers[(4, 34)] / 1000.0    # W -> kW

    return result if result else None


async def start_mqtt_client(db_instance, loop):
    """Start the MQTT client as a background service."""
    global _mqtt_client, _mqtt_thread, _db, _loop
    _db = db_instance
    _loop = loop

    config = await _db.mqtt_config.find_one({}, {"_id": 0})
    if not config or not config.get("enabled"):
        logger.info("MQTT: Not enabled or not configured")
        return

    broker_url = config.get("broker_url", "")
    broker_port = config.get("broker_port", 1883)
    username = config.get("username", "")
    password = config.get("password", "")
    use_tls = config.get("use_tls", False)

    if not broker_url:
        logger.warning("MQTT: No broker URL configured")
        return

    try:
        client_id = f"eventenergie-portal-{uuid.uuid4().hex[:8]}"
        subscribe_topics = config.get("subscribe_topics", ["dse/#"])

        _mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311,
            userdata={"subscribe_topics": subscribe_topics}
        )
        _mqtt_client.on_connect = _on_connect
        _mqtt_client.on_disconnect = _on_disconnect
        _mqtt_client.on_message = _on_message

        if username and password:
            _mqtt_client.username_pw_set(username, password)

        if use_tls:
            _mqtt_client.tls_set()

        await _update_connection_status("connecting", "Verbinde...")

        _mqtt_client.connect_async(broker_url, broker_port, keepalive=60)
        _mqtt_client.loop_start()
        logger.info(f"MQTT: Client started, connecting to {broker_url}:{broker_port}")
    except Exception as e:
        logger.error(f"MQTT: Failed to start client: {e}")
        await _update_connection_status("error", str(e))


async def stop_mqtt_client():
    """Stop the MQTT client."""
    global _mqtt_client
    if _mqtt_client:
        _mqtt_client.loop_stop()
        _mqtt_client.disconnect()
        _mqtt_client = None
        logger.info("MQTT: Client stopped")


async def restart_mqtt_client(db_instance, loop):
    """Restart the MQTT client with potentially new config."""
    await stop_mqtt_client()
    await start_mqtt_client(db_instance, loop)


def is_connected():
    """Check if MQTT client is currently connected."""
    return _mqtt_client is not None and _mqtt_client.is_connected()


def publish_command(topic, payload):
    """Publish an MQTT command message."""
    if _mqtt_client is None or not _mqtt_client.is_connected():
        raise RuntimeError("MQTT client nicht verbunden")
    result = _mqtt_client.publish(topic, payload, qos=1)
    result.wait_for_publish(timeout=5)
    logger.info(f"MQTT: Published command to {topic}: {payload}")
    return True