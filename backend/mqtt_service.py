import paho.mqtt.client as mqtt
import json
import logging
import asyncio
import threading
import uuid
import time
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

# Global MQTT client instance
_mqtt_client = None
_mqtt_thread = None
_db = None
_loop = None

# Deduplication: prevent processing same message twice (overlapping subscriptions)
_dedup_cache = {}  # topic -> (timestamp, payload_hash)
_dedup_ttl = 2.0   # seconds
_raw_msg_counter = 0  # for periodic trimming

# Cache for DB lookups (refreshed periodically)
_mappings_cache = None
_mappings_cache_ts = 0
_generators_cache = None
_generators_cache_ts = 0
_devices_cache = None
_devices_cache_ts = 0
_CACHE_TTL = 30  # seconds

# Cache for module UID storage (avoid repeated DB writes)
_uid_store_cache = {}  # generator_id -> last_store_time
_UID_STORE_INTERVAL = 300  # only update DB every 5 minutes per generator


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
    # Deduplicate: skip if same topic received within TTL (overlapping subscriptions)
    now = time.time()
    topic = msg.topic
    payload_hash = hash(msg.payload)
    key = (topic, payload_hash)
    if key in _dedup_cache and now - _dedup_cache[key] < _dedup_ttl:
        return  # Skip duplicate
    _dedup_cache[key] = now
    # Clean old dedup entries every ~50 messages
    if len(_dedup_cache) > 200:
        cutoff = now - _dedup_ttl * 2
        expired = [k for k, ts in _dedup_cache.items() if ts < cutoff]
        for k in expired:
            del _dedup_cache[k]
    logger.info(f"MQTT: Message on '{msg.topic}' ({len(msg.payload)} bytes)")
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
    global _raw_msg_counter, _mappings_cache, _mappings_cache_ts
    global _generators_cache, _generators_cache_ts, _devices_cache, _devices_cache_ts

    topic = msg.topic
    try:
        payload_str = msg.payload.decode("utf-8")
    except UnicodeDecodeError:
        payload_str = msg.payload.hex()

    timestamp = datetime.now(timezone.utc).isoformat()
    now_ts = time.time()

    # Try to parse JSON payload
    parsed = None
    try:
        parsed = json.loads(payload_str)
    except (json.JSONDecodeError, ValueError):
        pass

    # Cached DB lookups (refresh every CACHE_TTL seconds)
    if _mappings_cache is None or now_ts - _mappings_cache_ts > _CACHE_TTL:
        _mappings_cache = await _db.mqtt_gateway_mappings.find({}, {"_id": 0}).to_list(100)
        _mappings_cache_ts = now_ts

    if _generators_cache is None or now_ts - _generators_cache_ts > _CACHE_TTL:
        _generators_cache = await _db.generators.find(
            {"dse_mqtt_topic_prefix": {"$exists": True, "$ne": ""}},
            {"_id": 0, "id": 1, "dse_mqtt_topic_prefix": 1}
        ).to_list(100)
        _generators_cache_ts = now_ts

    if _devices_cache is None or now_ts - _devices_cache_ts > _CACHE_TTL:
        _devices_cache = await _db.devices.find(
            {"dse_module_uid": {"$exists": True, "$ne": ""}},
            {"_id": 0, "id": 1, "dse_module_uid": 1, "device_type": 1, "controller": 1}
        ).to_list(100)
        _devices_cache_ts = now_ts

    # Try to match this message to a generator via topic mappings
    for mapping in _mappings_cache:
        topic_prefix = mapping.get("topic_prefix", "").strip()
        generator_id = mapping.get("generator_id")

        if not generator_id:
            continue

        # Match by topic prefix
        if topic_prefix and topic.startswith(topic_prefix):
            logger.info(f"MQTT: Matched via gateway mapping (prefix='{topic_prefix}', gen={generator_id})")
            if topic.endswith("/gps"):
                await _process_gps(generator_id, payload_str, parsed, timestamp)
                return
            if topic.endswith("/status"):
                await _process_status(generator_id, payload_str, timestamp)
                return
            if topic.endswith("/alarm"):
                await _process_alarm(generator_id, payload_str, parsed, timestamp)
                return
            await _ingest_telemetry(generator_id, topic, payload_str, parsed, timestamp)
            return

    # Check generators with dse_mqtt_topic_prefix
    for gen in _generators_cache:
        prefix = gen.get("dse_mqtt_topic_prefix", "").strip()
        if prefix and topic.startswith(prefix):
            logger.info(f"MQTT: Matched via generator prefix (prefix='{prefix}', gen={gen['id']})")
            if topic.endswith("/gps"):
                await _process_gps(gen["id"], payload_str, parsed, timestamp)
                return
            if topic.endswith("/status"):
                await _process_status(gen["id"], payload_str, timestamp)
                return
            if topic.endswith("/alarm"):
                await _process_alarm(gen["id"], payload_str, parsed, timestamp)
                return
            await _ingest_telemetry(gen["id"], topic, payload_str, parsed, timestamp)
            return

    # Check devices collection for dse_module_uid match (auto-mapping)
    topic_parts = topic.split("/")
    topic_parts_upper = [p.strip().upper() for p in topic_parts]
    for dev in _devices_cache:
        uid = dev.get("dse_module_uid", "").strip()
        if uid and uid.upper() in topic_parts_upper:
            device_id = dev["id"]
            logger.info(f"MQTT: Matched device {device_id} via module_uid {uid}")
            if topic.endswith("/gps"):
                await _process_gps_device(device_id, payload_str, parsed, timestamp)
                return
            if topic.endswith("/status"):
                # JSON payload = telemetry data (e.g. run hours), text = online/offline status
                if parsed and isinstance(parsed, dict):
                    await _ingest_telemetry_device(device_id, topic, payload_str, parsed, timestamp)
                else:
                    await _process_status_device(device_id, payload_str, timestamp)
                return
            if topic.endswith("/alarm"):
                await _process_alarm(f"dev-{device_id}", payload_str, parsed, timestamp)
                return
            await _ingest_telemetry_device(device_id, topic, payload_str, parsed, timestamp)
            return

    # No mapping found - check if it's a GPS from gateway (apply to all connected devices)
    if topic.endswith("/gps") and parsed:
        await _process_gateway_gps(topic, payload_str, parsed, timestamp)
        return

    stored_uids = [d.get("dse_module_uid", "") for d in _devices_cache] if _devices_cache else []
    logger.debug(f"MQTT: Unmatched topic '{topic}' | stored_uids={stored_uids}")


async def _process_gateway_gps(topic, raw_payload, parsed, timestamp):
    """Process GPS from a DSE 890 gateway and apply ONLY to generators
    tied to the EXACT gateway (same UID/topic prefix).

    Topic-Konvention DSE890:
      Gateway-GPS: eventenergie/{ANLAGE_ID}/{GATEWAY_UID}/gps
      Module:      eventenergie/{ANLAGE_ID}/{GATEWAY_UID}/...
    Jede DSE890 hat eine eigene GPS-Antenne und eigene UID -> GPS gilt
    nur fuer Generatoren, deren Mapping/Topic-Prefix mit EXAKT diesem
    Gateway-Prefix (inkl. UID) beginnt. Nicht auf den Anlagen-Prefix
    spreizen, sonst ueberschreiben sich mehrere Gateways im selben
    Anlagen-Ordner gegenseitig.
    """
    lat = None
    lng = None
    if isinstance(parsed, dict):
        for uid_key, uid_data in parsed.items():
            if isinstance(uid_data, dict):
                lat = uid_data.get("LAT") or uid_data.get("lat")
                lng = uid_data.get("LON") or uid_data.get("lon") or uid_data.get("lng")
                if lat is not None:
                    break
        if lat is None:
            lat = parsed.get("LAT") or parsed.get("lat")
            lng = parsed.get("LON") or parsed.get("lon") or parsed.get("lng")
    if lat is None or lng is None:
        return
    try:
        lat = float(lat)
        lng = float(lng)
        if not (-90 <= lat <= 90 and -180 <= lng <= 180) or (lat == 0 and lng == 0):
            return
    except (ValueError, TypeError):
        return

    # Gateway-Topic ohne /gps und ohne trailing slash
    # z.B. "eventenergie/35072/1922A5D409E1601/gps" -> "eventenergie/35072/1922A5D409E1601"
    gw_topic = topic[: -len("/gps")] if topic.endswith("/gps") else topic
    gw_topic = gw_topic.rstrip("/")
    if not gw_topic or "/" not in gw_topic:
        return
    gw_prefix = gw_topic + "/"

    gps_update = {"latitude": lat, "longitude": lng, "last_gps_update": timestamp}
    matched_gen_ids = set()

    # 1) Mappings deren topic_prefix im gleichen Gateway liegt
    #    (mp == gw_topic ODER mp beginnt mit gw_topic + "/").
    for mapping in _mappings_cache:
        mp = (mapping.get("topic_prefix") or "").strip().rstrip("/")
        gen_id = mapping.get("generator_id")
        if not mp or not gen_id:
            continue
        if mp == gw_topic or mp.startswith(gw_prefix):
            matched_gen_ids.add(gen_id)

    # 2) Generators mit dse_mqtt_topic_prefix im gleichen Gateway
    for gen in _generators_cache:
        gp = (gen.get("dse_mqtt_topic_prefix") or "").strip().rstrip("/")
        if not gp:
            continue
        if gp == gw_topic or gp.startswith(gw_prefix):
            matched_gen_ids.add(gen["id"])

    # 3) Fallback: Devices, deren dse_module_uid im Gateway-Topic
    #    vorkommt (typischer DSE890-Aufbau: letztes Segment = UID)
    if not matched_gen_ids:
        uid_candidate = gw_topic.rsplit("/", 1)[-1].strip()
        if uid_candidate:
            for dev in (_devices_cache or []):
                dev_uid = (dev.get("dse_module_uid") or "").strip()
                if dev_uid and dev_uid == uid_candidate:
                    matched_gen_ids.add(f"dev-{dev['id']}")

    # Apply to all matching generators (real + virtual device-based)
    for gen_id in matched_gen_ids:
        await _db.generators.update_one({"id": gen_id}, {"$set": gps_update})
        if gen_id.startswith("dev-"):
            await _db.devices.update_one(
                {"id": gen_id[4:]}, {"$set": gps_update}
            )

    if matched_gen_ids:
        logger.info(
            f"MQTT: Gateway-GPS {lat},{lng} auf {len(matched_gen_ids)} "
            f"Generator(en) am Gateway '{gw_topic}' angewendet"
        )
    else:
        logger.info(
            f"MQTT: Gateway-GPS {lat},{lng} ({topic}) - kein Generator/Device "
            f"an Gateway '{gw_topic}' zugeordnet"
        )


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


async def _process_alarm(generator_id, raw_payload, parsed, timestamp):
    """Process alarm messages from DSE Function 4 or GenComm Page 8."""
    if not parsed or not isinstance(parsed, dict):
        return

    # GenComm Page 8 alarm name map (sequential position in register layout)
    # Register 1: pos 1-4, Register 2: pos 5-8, etc.
    # Each register holds 4 alarms in 4-bit nibbles (bits 13-16, 9-12, 5-8, 1-4)
    PAGE8_ALARM_NAMES = {
        1: "Notaus (Emergency Stop)",
        2: "Niedriger Oeldruck (Low Oil Pressure)",
        3: "Hohe Kuehlwassertemperatur (High Coolant Temp)",
        4: "Hohe Oeltemperatur (High Oil Temp)",
        5: "Unterdrehzahl (Under Speed)",
        6: "Ueberdrehzahl (Over Speed)",
        7: "Start fehlgeschlagen (Fail to Start)",
        8: "Stopp fehlgeschlagen (Fail to Come to Rest)",
        9: "Drehzahlsignal verloren (Loss of Speed Sensing)",
        10: "Generator Unterspannung (Gen Low Voltage)",
        11: "Generator Ueberspannung (Gen High Voltage)",
        12: "Generator Unterfrequenz (Gen Low Frequency)",
        13: "Generator Ueberfrequenz (Gen High Frequency)",
        14: "Generator Ueberstrom (Gen High Current)",
        15: "Erdschluss (Gen Earth Fault)",
        16: "Rueckleistung (Gen Reverse Power)",
        17: "Luftklappe (Air Flap)",
        18: "Oeldrucksensor Fehler (Oil Pressure Sender Fault)",
        19: "Kuehlmitteltemperatursensor Fehler (Coolant Temp Sender Fault)",
        20: "Oeltemperatursensor Fehler (Oil Temp Sender Fault)",
        21: "Kraftstoffsensor Fehler (Fuel Level Sender Fault)",
        22: "Drehzahlgeber Fehler (Magnetic Pickup Fault)",
        23: "AC Drehzahlsignal verloren (Loss of AC Speed Signal)",
        24: "Lademaschine Fehler (Charge Alternator Failure)",
        25: "Niedrige Batteriespannung (Low Battery Voltage)",
        26: "Hohe Batteriespannung (High Battery Voltage)",
        27: "Niedriger Kraftstoffstand (Low Fuel Level)",
        28: "Hoher Kraftstoffstand (High Fuel Level)",
        29: "Generator Schliessen fehlgeschlagen (Gen Failed to Close)",
        30: "Netz Schliessen fehlgeschlagen (Mains Failed to Close)",
        31: "Generator Oeffnen fehlgeschlagen (Gen Failed to Open)",
        32: "Netz Oeffnen fehlgeschlagen (Mains Failed to Open)",
        33: "Netz Unterspannung (Mains Low Voltage)",
        34: "Netz Ueberspannung (Mains High Voltage)",
        35: "Bus Schliessen fehlgeschlagen (Bus Failed to Close)",
        36: "Bus Oeffnen fehlgeschlagen (Bus Failed to Open)",
        37: "Netz Unterfrequenz (Mains Low Frequency)",
        38: "Netz Ueberfrequenz (Mains High Frequency)",
        39: "Netzausfall (Mains Failed)",
        40: "Netz Phasendrehung falsch (Mains Phase Rotation Wrong)",
        41: "Generator Phasendrehung falsch (Gen Phase Rotation Wrong)",
        42: "Wartung faellig (Maintenance Due)",
        43: "Uhr nicht gestellt (Clock Not Set)",
        44: "LCD Konfiguration verloren (LCD Config Lost)",
        45: "Telemetrie Konfiguration verloren (Telemetry Config Lost)",
        46: "Steuerung nicht kalibriert (Control Unit Not Calibrated)",
        47: "Modem Stromfehler (Modem Power Fault)",
        48: "Kurzschluss (Gen Short Circuit)",
        49: "Synchronisation fehlgeschlagen (Failure to Synchronise)",
        50: "Bus unter Spannung (Bus Live)",
        51: "Geplanter Lauf (Scheduled Run)",
        52: "Bus Phasendrehung falsch (Bus Phase Rotation Wrong)",
    }

    # Alarm condition codes (GenComm Page 8)
    # 0=disabled, 1=not active, 2=warning, 3=shutdown, 4=e-trip, 5=controlled shutdown, 10=active indication
    ACTIVE_CONDITIONS = {2, 3, 4, 5, 10}
    CONDITION_SEVERITY = {2: "warning", 3: "shutdown", 4: "shutdown", 5: "warning", 10: "warning"}

    active_alarms = []  # list of (alarm_code_str, alarm_text, severity)

    # Check for GenComm Page 8 format: {"UID": {"P008": {"R000": count, "R001": val, ...}}}
    for uid_key, uid_data in parsed.items():
        if not isinstance(uid_data, dict):
            continue

        # GenComm Page 8 register format
        page8_data = uid_data.get("P008") or uid_data.get("P154")
        if page8_data and isinstance(page8_data, dict):
            logger.info(f"MQTT Alarm: GenComm Page 8/154 empfangen fuer {generator_id}")
            alarm_pos = 0
            for reg_idx in range(1, 33):  # Registers 1-32
                reg_key = f"R{reg_idx:03d}"
                reg_val = page8_data.get(reg_key)
                if reg_val is None:
                    alarm_pos += 4
                    continue
                try:
                    reg_val = int(reg_val)
                except (TypeError, ValueError):
                    alarm_pos += 4
                    continue

                # Extract 4 alarm conditions from 16-bit register (4 bits each)
                nibbles = [
                    (reg_val >> 12) & 0xF,  # Bits 13-16 (high nibble)
                    (reg_val >> 8) & 0xF,   # Bits 9-12
                    (reg_val >> 4) & 0xF,   # Bits 5-8
                    reg_val & 0xF,           # Bits 1-4 (low nibble)
                ]
                for nibble_idx, condition in enumerate(nibbles):
                    alarm_pos += 1
                    if condition in ACTIVE_CONDITIONS:
                        alarm_code = f"A{alarm_pos:03d}"
                        alarm_name = PAGE8_ALARM_NAMES.get(alarm_pos, f"Alarm #{alarm_pos}")
                        severity = CONDITION_SEVERITY.get(condition, "warning")
                        active_alarms.append((alarm_code, alarm_name, severity))
                        logger.info(f"MQTT Alarm: {alarm_code} = {alarm_name} (condition={condition}, severity={severity})")
            # Skip A-code format check if we found GenComm data
            if active_alarms or page8_data:
                break

        # DSE 890 Function 4 A-code format: {"UID": {"A001": condition_code, ...}}
        for alarm_key, alarm_val in uid_data.items():
            if isinstance(alarm_key, str) and alarm_key.startswith("A") and len(alarm_key) >= 4:
                try:
                    condition = int(alarm_val)
                    if condition in ACTIVE_CONDITIONS:
                        alarm_num = int(alarm_key[1:])
                        alarm_name = PAGE8_ALARM_NAMES.get(alarm_num, f"DSE Alarm {alarm_key}")
                        severity = CONDITION_SEVERITY.get(condition, "warning")
                        active_alarms.append((alarm_key, alarm_name, severity))
                except (ValueError, TypeError):
                    pass

    if active_alarms:
        # Set generator status to alarm
        await _db.generators.update_one(
            {"id": generator_id},
            {"$set": {"status": "alarm", "last_seen": timestamp}}
        )
        if generator_id.startswith("dev-"):
            await _db.devices.update_one(
                {"id": generator_id[4:]},
                {"$set": {"mqtt_status": "alarm", "last_seen": timestamp}}
            )
        # Store each new alarm
        for alarm_code, alarm_text, severity in active_alarms:
            existing = await _db.generator_alarms.find_one(
                {"generator_id": generator_id, "alarm_code": alarm_code, "resolved_at": None}
            )
            if not existing:
                await _db.generator_alarms.insert_one({
                    "id": str(uuid.uuid4()),
                    "generator_id": generator_id,
                    "alarm_code": alarm_code,
                    "alarm_text": alarm_text,
                    "severity": severity,
                    "timestamp": timestamp,
                    "acknowledged": False,
                    "resolved_at": None,
                })
        # Write alarm text to snapshot (visible in dashboard)
        alarm_texts = [text for _, text, _ in active_alarms]
        fault_display = ", ".join(alarm_texts[:3])
        alarm_codes_str = ",".join([code for code, _, _ in active_alarms])
        snapshot_update = {
            "latest_snapshot.fault_text": fault_display,
            "latest_snapshot.fault_code": alarm_codes_str,
        }
        if generator_id.startswith("dev-"):
            await _db.devices.update_one(
                {"id": generator_id[4:]}, {"$set": snapshot_update})
        await _db.generators.update_one(
            {"id": generator_id}, {"$set": snapshot_update})
        logger.info(f"MQTT: {len(active_alarms)} active alarms for {generator_id}: {alarm_texts}")
    else:
        # No active alarms - resolve all open Function-4 alarms (A-codes)
        open_alarms = await _db.generator_alarms.count_documents(
            {"generator_id": generator_id, "alarm_code": {"$regex": "^A"}, "resolved_at": None}
        )
        if open_alarms > 0:
            await _db.generator_alarms.update_many(
                {"generator_id": generator_id, "alarm_code": {"$regex": "^A"}, "resolved_at": None},
                {"$set": {"resolved_at": timestamp}}
            )
            # Check if there are still status-bit alarms (SB_) active
            remaining = await _db.generator_alarms.count_documents(
                {"generator_id": generator_id, "resolved_at": None}
            )
            if remaining == 0:
                await _db.generators.update_one(
                    {"id": generator_id}, {"$set": {"status": "online"}})
            logger.info(f"MQTT: Function-4 alarms resolved for {generator_id}")


async def _process_gps_device(device_id, raw_payload, parsed, timestamp):
    """Process GPS data for a device (same logic as generators)."""
    lat, lng = None, None
    if isinstance(parsed, dict):
        for uid_key, uid_data in parsed.items():
            if isinstance(uid_data, dict):
                lat = uid_data.get("LAT") or uid_data.get("lat")
                lng = uid_data.get("LON") or uid_data.get("lon") or uid_data.get("lng")
                if lat is not None:
                    break
        if lat is None:
            lat = parsed.get("LAT") or parsed.get("lat")
            lng = parsed.get("LON") or parsed.get("lon") or parsed.get("lng")
    if lat is not None and lng is not None:
        try:
            lat, lng = float(lat), float(lng)
            if -90 <= lat <= 90 and -180 <= lng <= 180 and (lat != 0 or lng != 0):
                gps_update = {"latitude": lat, "longitude": lng, "last_gps_update": timestamp}
                await _db.devices.update_one(
                    {"id": device_id},
                    {"$set": gps_update}
                )
                # Auch den verknuepften virtuellen Generator (dev-<id>) updaten,
                # falls als echter Generator-Doc existiert. Sonst zeigt
                # list_generators alten Stand.
                await _db.generators.update_one(
                    {"$or": [
                        {"id": f"dev-{device_id}"},
                        {"generator_id": f"dev-{device_id}"},
                        {"device_id": device_id},
                    ]},
                    {"$set": gps_update}
                )
                # Falls ein echter Generator-Eintrag mit gleicher
                # serial_number existiert (Stromerzeuger/Lichtmast),
                # GPS auch dorthin spiegeln. Wichtig: NUR EINEN
                # treffen - update_one mit konkretem serial_number
                # (kein leer-Match), damit nicht mehrere Generators
                # ueberschrieben werden.
                dev_doc = await _db.devices.find_one(
                    {"id": device_id}, {"_id": 0, "serial_number": 1}
                )
                ser = (dev_doc or {}).get("serial_number")
                if ser:
                    await _db.generators.update_one(
                        {"serial_number": ser},
                        {"$set": gps_update}
                    )
                logger.info(f"MQTT: GPS updated for device {device_id}: {lat}, {lng}")
        except (ValueError, TypeError):
            pass


# Throttle for status updates (avoid DB write every 5s for unchanged status)
_status_cache = {}  # device_id -> (last_status, last_update_time)
_STATUS_UPDATE_INTERVAL = 1200  # only write status to DB every 20 minutes if unchanged


async def _process_status_device(device_id, raw_payload, timestamp):
    """Process status messages for a device."""
    status = "online" if "disconnected" not in raw_payload.lower() else "offline"

    # Throttle: only write if status changed or interval elapsed
    cached = _status_cache.get(device_id)
    now = time.time()
    if cached and cached[0] == status and now - cached[1] < _STATUS_UPDATE_INTERVAL:
        return  # Skip - status unchanged and recently written
    _status_cache[device_id] = (status, now)

    await _db.devices.update_one(
        {"id": device_id},
        {"$set": {"last_seen": timestamp, "mqtt_status": status}}
    )
    await _db.generators.update_one(
        {"id": f"dev-{device_id}"},
        {"$set": {"last_seen": timestamp, "status": status}}
    )
    logger.debug(f"MQTT: Status for device {device_id}")


# Throttle telemetry inserts (snapshot is always updated, but history only every 60s)
_telemetry_insert_cache = {}  # generator_id -> last_insert_time
_TELEMETRY_INSERT_INTERVAL = 60  # seconds - only insert history record every 60s


async def _ingest_telemetry_device(device_id, topic, raw_payload, parsed, timestamp):
    """Ingest MQTT telemetry for a device (Stromerzeuger/Lichtmast)."""
    generator_id = f"dev-{device_id}"
    try:
        # Auto-extract module UID and topic prefix for control routing (throttled)
        await _auto_store_module_uid(generator_id, topic)

        telemetry_data = {}
        if isinstance(parsed, dict):
            # Check for simple J1939 format (e.g. {"hours": 1234.5} from Function 6)
            if "hours" in parsed and len(parsed) <= 2:
                try:
                    telemetry_data["hours_run"] = float(parsed["hours"])
                except (ValueError, TypeError):
                    pass
            else:
                gencomm_data = _parse_gencomm_registers(parsed, topic)
                if gencomm_data:
                    telemetry_data = gencomm_data

        # Diagnose-Logging für /hours Topic
        raw_topic = topic.split("/")[-1] if topic else ""
        if raw_topic == "hours":
            if telemetry_data.get("hours_run") is not None:
                logger.info(f"MQTT hours OK: device={device_id}, hours_run={telemetry_data['hours_run']}, starts={telemetry_data.get('engine_starts')}")
            else:
                logger.warning(f"MQTT hours FEHLEND: device={device_id}, topic={topic}, raw_payload={raw_payload[:200] if raw_payload else 'None'}")

        # Always update snapshot on device + generator (fast, no new documents)
        snapshot_fields = {}
        _TELEMETRY_KEYS = [
            "voltage_l1", "voltage_l2", "voltage_l3",
            "voltage_l1_l2", "voltage_l2_l3", "voltage_l3_l1",
            "current_l1", "current_l2", "current_l3",
            "frequency", "power_kw", "power_kva", "power_total_w",
            "oil_pressure", "coolant_temp", "fuel_level", "battery_voltage",
            "rpm", "engine_running", "hours_run", "engine_starts", "energy_kwh",
            "load_percent", "power_factor", "power_factor_avg", "dse_mode",
            "fault_code", "fault_text", "status_bits",
        ]
        # Determine which fields this topic SHOULD contain
        engine_fields = {"oil_pressure", "coolant_temp", "fuel_level", "battery_voltage", "rpm"}
        generator_fields = {"voltage_l1", "voltage_l2", "voltage_l3", "current_l1", "current_l2", "current_l3",
                           "frequency", "power_kw", "power_total_w"}
        raw_topic = topic.split("/")[-1] if topic else ""
        clear_fields = set()
        if raw_topic == "engine":
            clear_fields = engine_fields
        elif raw_topic == "generator":
            clear_fields = generator_fields

        for key in _TELEMETRY_KEYS:
            val = telemetry_data.get(key)
            if val is not None:
                snapshot_fields[f"latest_snapshot.{key}"] = val
            elif key in clear_fields:
                snapshot_fields[f"latest_snapshot.{key}"] = None
        snapshot_fields["latest_snapshot.timestamp"] = timestamp

        # Single combined update for device
        # Status NICHT blind auf "online" setzen - erst pruefen ob Alarm aktiv
        device_update = {"last_seen": timestamp, "last_telemetry": timestamp}

        # Single combined update for virtual generator
        gen_update = {"last_seen": timestamp}
        # Enrich with device info (controller, serial_number) so frontend knows the type
        device_info = next((d for d in (_devices_cache or []) if d.get("id") == device_id), None)
        if device_info:
            gen_update["model"] = device_info.get("controller", "")
            gen_update["serial_number"] = device_info.get("serial_number", "")

        # Check for alarm conditions from P3R6 status bits (official GenComm)
        status_alarms = telemetry_data.get("status_alarms")
        fault_code = telemetry_data.get("fault_code")

        if status_alarms:
            # Active alarm(s) from status bits → ALARM hat hoechste Prioritaet
            gen_update["status"] = "alarm"
            device_update["mqtt_status"] = "alarm"
            for alarm_code, alarm_text, severity in status_alarms:
                existing = await _db.generator_alarms.find_one(
                    {"generator_id": generator_id, "alarm_code": alarm_code, "resolved_at": None}
                )
                if not existing:
                    await _db.generator_alarms.insert_one({
                        "id": str(uuid.uuid4()),
                        "generator_id": generator_id,
                        "alarm_code": alarm_code,
                        "alarm_text": alarm_text,
                        "severity": severity,
                        "timestamp": timestamp,
                        "acknowledged": False,
                        "resolved_at": None,
                    })
                    logger.info(f"MQTT: Status-Alarm for {device_id}: {alarm_text}")
        elif fault_code == 0:
            # No alarm active (status bits clear) - Alarm aufloesen
            snapshot_fields["latest_snapshot.fault_code"] = None
            snapshot_fields["latest_snapshot.fault_text"] = None
            # Status basierend auf Motor-Zustand setzen (kein Alarm mehr)
            if telemetry_data.get("engine_running") is True or telemetry_data.get("rpm", 0) > 0:
                gen_update["status"] = "running"
                device_update["mqtt_status"] = "running"
            else:
                gen_update["status"] = "online"
                device_update["mqtt_status"] = "online"
            open_count = await _db.generator_alarms.count_documents(
                {"generator_id": generator_id, "alarm_code": {"$regex": "^SB_|^F"}, "resolved_at": None}
            )
            if open_count > 0:
                await _db.generator_alarms.update_many(
                    {"generator_id": generator_id, "alarm_code": {"$regex": "^SB_|^F"}, "resolved_at": None},
                    {"$set": {"resolved_at": timestamp}}
                )
                logger.info(f"MQTT: Alarms resolved for {device_id}")
        else:
            # No status data in this message (z.B. /engine oder /generator Topic)
            # → Alarm-Status aus DB beibehalten, Motor-Status nur setzen wenn KEIN Alarm
            current_device = await _db.devices.find_one({"id": device_id}, {"_id": 0, "mqtt_status": 1})
            current_status = (current_device or {}).get("mqtt_status", "online")
            if current_status == "alarm":
                gen_update["status"] = "alarm"
                device_update["mqtt_status"] = "alarm"
            elif telemetry_data.get("engine_running") is True or telemetry_data.get("rpm", 0) > 0:
                gen_update["status"] = "running"
                device_update["mqtt_status"] = "running"
            elif telemetry_data.get("engine_running") is False:
                gen_update["status"] = "standby"
                device_update["mqtt_status"] = "standby"
            else:
                device_update["mqtt_status"] = current_status
        dse_mode = telemetry_data.get("dse_mode")
        if dse_mode and dse_mode not in ("unknown", ""):
            gen_update["last_dse_mode"] = dse_mode
        gen_update.update(snapshot_fields)

        # Jetzt beide Updates schreiben (NACH Alarm-Status-Bestimmung)
        device_update.update(snapshot_fields)
        await _db.devices.update_one({"id": device_id}, {"$set": device_update})
        await _db.generators.update_one(
            {"id": generator_id},
            {"$set": gen_update}
        )

        # Determine insert interval based on device type and status
        # Lichtmasten (L401): every 60 seconds
        # Stromerzeuger in Betrieb: every 5 minutes
        # Stromerzeuger offline/standby: skip insert
        device_info = next((d for d in (_devices_cache or []) if d.get("id") == device_id), None)
        device_type = (device_info or {}).get("device_type", "")
        controller = (device_info or {}).get("controller", "")
        is_lichtmast = device_type == "lichtmast" or "l401" in controller.lower()

        now = time.time()
        last_insert = _telemetry_insert_cache.get(generator_id, 0)
        should_insert = False

        if is_lichtmast:
            # Lichtmasten: every 60 seconds
            if now - last_insert >= 60:
                should_insert = True
        else:
            # Stromerzeuger: check if running
            is_running = (
                telemetry_data.get("engine_running") is True
                or (telemetry_data.get("rpm") or 0) > 0
                or gen_update.get("status") == "running"
            )
            if is_running and now - last_insert >= 300:
                # In Betrieb: every 5 minutes
                should_insert = True
            # Offline/Standby: no insert (snapshot is still updated)

        if should_insert:
            telemetry = {
                "id": str(uuid.uuid4()),
                "generator_id": generator_id,
                "device_id": device_id,
                "timestamp": timestamp,
                "source": "mqtt",
                "raw_topic": topic,
            }
            telemetry.update(telemetry_data)
            await _db.generator_telemetry.insert_one(telemetry)
            _telemetry_insert_cache[generator_id] = now

        logger.info(f"MQTT: Telemetry stored for device {device_id} from topic {topic}")
    except Exception as e:
        logger.error(f"MQTT: Error storing telemetry for device {device_id}: {e}")


def _extract_module_uid_from_topic(topic):
    """Extract the DSE module UID from an MQTT topic.
    Topics: eventenergie/DSE8610/6D2B5CDE5F/engine, etc.
    Returns (uid, topic_prefix) where prefix = group/type/uid."""
    parts = topic.strip("/").split("/")
    # DSE 890 topics always have: GROUP/TYPE/UID/subtopic (4+ parts)
    # The UID is typically the 3rd part (index 2)
    # The subtopic is the 4th part (engine, generator, gps, status, control, etc.)
    skip_suffixes = {"engine", "gps", "status", "control", "instrumentation",
                     "alarms", "config", "events", "mains", "generator",
                     "alarm", "topic_file"}
    if len(parts) >= 4:
        # Standard format: group/type/uid/subtopic
        subtopic = parts[-1].lower()
        if subtopic in skip_suffixes:
            # Everything before the subtopic is the prefix
            prefix_parts = parts[:-1]
            uid = prefix_parts[-1]  # Last part before subtopic is the UID
            prefix = "/".join(prefix_parts)
            return uid, prefix
    # Fallback: try to find UID-like string
    for i, part in enumerate(parts):
        lower = part.lower()
        if lower in skip_suffixes:
            continue
        if lower in {"eventenergie", "dse", "dsegateway4g"}:
            continue
        if part.isdigit():
            continue
        if len(part) >= 6 and part.replace("-", "").replace("_", "").isalnum():
            prefix = "/".join(parts[:i+1])
            return part, prefix
    return None, None


async def _auto_store_module_uid(generator_id, topic):
    """Extract module UID and full topic prefix from MQTT topic.
    Stores on both generator (if exists) and device (always exists).
    Throttled to only write DB every 5 minutes per generator."""
    now = time.time()
    last = _uid_store_cache.get(generator_id, 0)
    if now - last < _UID_STORE_INTERVAL:
        return  # Recently stored, skip DB write

    uid, prefix = _extract_module_uid_from_topic(topic)
    if uid and _db is not None:
        update = {"last_mqtt_module_uid": uid}
        if prefix:
            update["last_mqtt_topic_prefix"] = prefix
        await _db.generators.update_one(
            {"id": generator_id},
            {"$set": update}
        )
        if generator_id.startswith("dev-"):
            device_id = generator_id[4:]
            await _db.devices.update_one(
                {"id": device_id},
                {"$set": update}
            )
        _uid_store_cache[generator_id] = now


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

    # Auto-extract module UID from topic and store on generator for control routing
    # Topics look like: eventenergie/UIDHERE/engine or /32788/UIDHERE/engine
    await _auto_store_module_uid(generator_id, topic)

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

    # Build merged snapshot + status in a single update
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

    dse_mode = telemetry.get("dse_mode")
    if dse_mode and dse_mode not in ("unknown", ""):
        status_update["last_dse_mode"] = dse_mode

    # Merge telemetry fields into latest_snapshot (dot notation = partial update)
    _SNAPSHOT_KEYS = [
        "voltage_l1", "voltage_l2", "voltage_l3",
        "voltage_l1_l2", "voltage_l2_l3", "voltage_l3_l1",
        "current_l1", "current_l2", "current_l3",
        "frequency", "power_kw", "power_kva", "power_total_w",
        "oil_pressure", "coolant_temp", "fuel_level", "battery_voltage",
        "rpm", "engine_running", "hours_run", "engine_starts", "energy_kwh",
        "load_percent", "power_factor", "dse_mode",
    ]
    for key in _SNAPSHOT_KEYS:
        val = telemetry.get(key)
        if val is not None:
            status_update[f"latest_snapshot.{key}"] = val
    status_update["latest_snapshot.timestamp"] = timestamp

    await _db.generators.update_one({"id": generator_id}, {"$set": status_update})

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
        try:
            num = float(val)
        except (TypeError, ValueError):
            return False
        # Exact DSE sentinel values (int and float comparison)
        sentinel_vals = (
            INVALID_16, INVALID_16 + 1, INVALID_16 + 2, INVALID_16 + 3,
            INVALID_16 - 1, INVALID_16 - 2,  # 32763, 32762 also used as "not available"
            INVALID_32, INVALID_32 + 1, INVALID_32 + 2, INVALID_32 + 3,
            INVALID_32 - 1, INVALID_32 - 2,  # 0x7FFFFFFB, 0x7FFFFFFA
            32767, 2147483647, 65535, 4294967295,
        )
        for s in sentinel_vals:
            if abs(num - s) < 0.5:
                return False
        # Range-based safety: any raw register value above 1 million is almost certainly invalid
        if abs(num) > 1_000_000:
            return False
        return True

    # Page 3: Controller status (official GenComm mapping)
    # P3R4 = Control mode (NOT fault code - previously misidentified)
    DSE_MODE_MAP = {
        0: "stop", 1: "auto", 2: "manual", 3: "test_on_load",
        4: "auto_manual_restore", 5: "user_config", 6: "test_off_load",
        7: "off", 8: "stop",
    }
    control_mode = registers.get((3, 4))
    if control_mode is not None and valid(control_mode):
        result["dse_mode"] = DSE_MODE_MAP.get(int(control_mode), f"mode_{int(control_mode)}")

    # P3R6 = Status bits (official GenComm P3R6 bit definitions)
    #   Bit 15 (0x8000): Control unit not configured
    #   Bit 13 (0x2000): Control unit failure
    #   Bit 12 (0x1000): Shutdown alarm active
    #   Bit 11 (0x0800): Electrical trip
    #   Bit 10 (0x0400): Warning alarm active
    #   Bit 9  (0x0200): Telemetry alarm flag
    #   Bit 8  (0x0100): Satellite telemetry alarm flag
    #   Bit 7  (0x0080): No font file
    #   Bit 6  (0x0040): Controlled shutdown alarm active
    status_bits = registers.get((3, 6))
    if status_bits is not None and valid(status_bits):
        sb = int(status_bits)
        result["status_bits"] = sb

        # Detect alarm conditions from status bits
        active_faults = []
        if sb & 0x2000:
            active_faults.append(("SB_CTRL_FAIL", "Steuerungsfehler (Control Unit Failure)", "shutdown"))
        if sb & 0x1000:
            active_faults.append(("SB_SHUTDOWN", "Abschaltung aktiv (Shutdown Alarm)", "shutdown"))
        if sb & 0x0800:
            active_faults.append(("SB_ELEC_TRIP", "Elektrische Ausloesung (Electrical Trip)", "shutdown"))
        if sb & 0x0400:
            active_faults.append(("SB_WARNING", "Warnung aktiv (Warning Alarm)", "warning"))
        if sb & 0x0040:
            active_faults.append(("SB_CTRL_STOP", "Kontrollierte Abschaltung (Controlled Shutdown)", "warning"))

        if active_faults:
            # Use the most severe fault as the primary display text
            result["fault_code"] = sb
            result["fault_text"] = active_faults[0][1]  # Most severe first
            result["status_alarms"] = active_faults
        else:
            result["fault_code"] = 0  # No alarm active

    # Engine parameters
    if valid(registers.get((4, 0))):
        result["oil_pressure"] = round(registers[(4, 0)] / 100.0, 1)   # kPa -> bar
    if valid(registers.get((4, 1))):
        result["coolant_temp"] = registers[(4, 1)]           # °C
    if valid(registers.get((4, 3))):
        result["fuel_level"] = min(registers[(4, 3)], 100)   # % clamped to max 100
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

    # Page 6 Register 0-1: Generator total watts (32-bit signed)
    # NOTE: Previously we read P4R34 which is actually "Generator current lag/lead" (degrees)
    if valid(registers.get((6, 0))):
        total_w = registers[(6, 0)]
        result["power_total_w"] = total_w
        result["power_kw"] = round(total_w / 1000.0, 2)

    # Page 6 Register 21: Generator average power factor (scale 0.01)
    if valid(registers.get((6, 21))):
        result["power_factor"] = registers[(6, 21)] / 100.0
        result["power_factor_avg"] = result["power_factor"]

    # Page 7: kWh, starts (DSE 8610 etc.) - NOT hours (P7 R0 gives garbage on L401/890)
    if valid(registers.get((7, 4))):
        result["energy_kwh"] = registers[(7, 4)]             # kWh

    # Page 3: Run hours for L401 (Register 15, 32-bit, 0.1h) - DEPRECATED, use P7 R6
    if not result.get("hours_run") and valid(registers.get((3, 15))):
        result["hours_run"] = registers[(3, 15)] / 10.0

    # Page 7 Register 6: Run hours in SECONDS (via DSE 890 Gateway)
    # Note: bypass valid() check - seconds value can be > 1M (> 277h)
    raw_hours_sec = registers.get((7, 6))
    if raw_hours_sec is not None:
        # Robust: handle string values from gateway
        try:
            raw_hours_sec = float(raw_hours_sec)
        except (TypeError, ValueError):
            logger.warning(f"GenComm P7R6 hours: ungültiger Wert '{raw_hours_sec}' (type={type(raw_hours_sec).__name__})")
            raw_hours_sec = None
    if raw_hours_sec is not None:
        if 0 <= raw_hours_sec < 100000000:  # sanity: <= 27777h, 0 = never run
            result["hours_run"] = round(raw_hours_sec / 3600.0, 1)
        else:
            logger.warning(f"GenComm P7R6 hours: Wert {raw_hours_sec} ausserhalb Bereich (0..100M), topic={topic}")

    # Page 7 Register 16: Number of starts (32-bit)
    raw_starts = registers.get((7, 16))
    if raw_starts is not None:
        try:
            raw_starts = float(raw_starts)
        except (TypeError, ValueError):
            raw_starts = None
    if raw_starts is not None and valid(raw_starts):
        result["engine_starts"] = int(raw_starts)

    return result if result else None


# Timeout in seconds before a device/generator is marked offline (5 minutes)
OFFLINE_TIMEOUT_SECONDS = 300


async def _offline_checker_loop():
    """Background task: periodically mark devices/generators as offline if no data received."""
    await asyncio.sleep(30)  # Initial delay to let the system start up
    logger.info("MQTT: Offline-Checker gestartet (Intervall: 60s, Timeout: 5min)")
    while True:
        try:
            await _check_stale_devices()
        except Exception as e:
            logger.error(f"MQTT: Offline-Checker Fehler: {e}")
        await asyncio.sleep(60)


async def _check_stale_devices():
    """Check for devices/generators that haven't sent data within the timeout."""
    if _db is None:
        return

    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=OFFLINE_TIMEOUT_SECONDS)).isoformat()

    # Mark devices as offline if last_seen is older than cutoff
    device_result = await _db.devices.update_many(
        {
            "mqtt_status": {"$in": ["online", "running", "standby", "verbunden"]},
            "last_seen": {"$lt": cutoff}
        },
        {"$set": {"mqtt_status": "offline"}}
    )

    # Mark generators as offline if last_seen is older than cutoff
    gen_result = await _db.generators.update_many(
        {
            "status": {"$in": ["online", "running", "standby", "verbunden"]},
            "last_seen": {"$ne": None, "$lt": cutoff}
        },
        {"$set": {"status": "offline", "mqtt_status": "offline"}}
    )

    total = (device_result.modified_count or 0) + (gen_result.modified_count or 0)
    if total > 0:
        logger.info(f"MQTT: Offline-Checker: {device_result.modified_count} Geräte, {gen_result.modified_count} Generatoren als offline markiert")



async def start_mqtt_client(db_instance, loop):
    """Start the MQTT client as a background service."""
    global _mqtt_client, _mqtt_thread, _db, _loop
    _db = db_instance
    _loop = loop

    config = await _db.mqtt_config.find_one({}, {"_id": 0})

    # Auto-initialize MQTT config if missing or incomplete
    if not config:
        config = {
            "enabled": True,
            "broker_url": "127.0.0.1",
            "broker_port": 1883,
            "username": "",
            "password": "",
            "use_tls": False,
            "subscribe_topics": ["eventenergie/#", "dse/#", "DSEGateway4G/#"],
            "connection_status": "disconnected",
            "connection_message": "",
        }
        await _db.mqtt_config.insert_one(config)
        config.pop("_id", None)
        logger.info("MQTT: Default-Config erstellt (127.0.0.1:1883)")

    # Remove '#' wildcard from subscribe_topics if present (causes duplicate messages)
    topics = config.get("subscribe_topics", [])
    if "#" in topics:
        topics = [t for t in topics if t != "#"]
        await _db.mqtt_config.update_one({}, {"$set": {"subscribe_topics": topics}})
        config["subscribe_topics"] = topics
        logger.info("MQTT: Removed '#' wildcard from subscribe_topics (reduces duplicates)")

    # Start the offline-checker background task
    asyncio.ensure_future(_offline_checker_loop())

    # Cleanup old telemetry records (keep last 30 days)
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        result = await _db.generator_telemetry.delete_many({"timestamp": {"$lt": cutoff}})
        if result.deleted_count > 0:
            logger.info(f"MQTT: Cleaned up {result.deleted_count} old telemetry records (>30 days)")
    except Exception as e:
        logger.warning(f"MQTT: Telemetry cleanup failed: {e}")

    if not config.get("enabled"):
        logger.info("MQTT: Not enabled in config - skipping")
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