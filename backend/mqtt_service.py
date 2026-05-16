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

# MQTT Worker-Pool: vermeidet Event-Loop-Saturation bei vielen Telegrammen
_mqtt_queue = None              # asyncio.Queue (max 500)
_mqtt_workers = []              # List[asyncio.Task]
_MQTT_WORKER_COUNT = 4          # Parallele Verarbeiter
_MQTT_QUEUE_MAX = 500           # Drop wenn voll (Backpressure)
_mqtt_dropped_counter = 0       # Zaehler verworfener Messages

# Deduplication: prevent processing same message twice (overlapping subscriptions)
_dedup_cache = {}  # topic -> (timestamp, payload_hash)
_dedup_ttl = 2.0   # seconds
_raw_msg_counter = 0  # for periodic trimming
_raw_log_counter = 0  # for periodic raw-message-log trimming

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

# DSE890 Anlagen-Pairing: Bruecke zwischen Gateway-UID und Module-UID
# Idee: Beide UIDs landen typischerweise im selben Anlagen-Topic
#   eventenergie/{ANLAGE_ID}/{GATEWAY_UID}/gps    <- Gateway sendet GPS
#   eventenergie/{ANLAGE_ID}/{MODULE_UID}/engine  <- Bediendisplay sendet Telemetrie
# Wenn beide UIDs in derselben ANLAGE_ID auftauchen, paaren wir sie automatisch.
_anlage_index = {}  # anlage_id -> {"gw": set([UIDs]), "mod": set([UIDs]), "ts": time}
_ANLAGE_INDEX_TTL = 3600  # 1h Eviction-Zeit
_anlage_pair_persist = set()  # anlage_id pairs schon persistiert (idempotent)


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
    # In Queue legen (statt direkt im Event-Loop dispatchen), damit Bursts
    # nicht den Event-Loop saturieren. Worker-Pool verarbeitet seriell mit
    # kontrollierter Parallelitaet.
    global _mqtt_dropped_counter
    if _mqtt_queue is None or _loop is None:
        return
    try:
        # call_soon_threadsafe sicher vom MQTT-Thread aus
        def _enqueue():
            try:
                _mqtt_queue.put_nowait(msg)
            except asyncio.QueueFull:
                global _mqtt_dropped_counter
                _mqtt_dropped_counter += 1
                if _mqtt_dropped_counter % 50 == 1:
                    logger.warning(
                        f"MQTT: Queue voll (max={_MQTT_QUEUE_MAX}), "
                        f"verworfen={_mqtt_dropped_counter}"
                    )
        _loop.call_soon_threadsafe(_enqueue)
    except Exception as e:
        logger.error(f"MQTT: Error queueing message: {e}")


async def _mqtt_worker(worker_id: int):
    """Worker-Task: Liest Messages aus _mqtt_queue und verarbeitet sie.
    Mehrere Worker laufen parallel, aber jeder seriell - damit ist die
    Last auf dem Event-Loop kontrollierbar.
    """
    logger.info(f"MQTT-Worker {worker_id} gestartet")
    while True:
        try:
            msg = await _mqtt_queue.get()
        except asyncio.CancelledError:
            logger.info(f"MQTT-Worker {worker_id} beendet")
            return
        try:
            await _process_message(msg)
        except Exception as e:
            logger.error(f"MQTT-Worker {worker_id} Fehler: {e}", exc_info=True)
        finally:
            try:
                _mqtt_queue.task_done()
            except ValueError:
                pass


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


def _extract_first_hex_uid(topic_parts):
    """Findet die erste Hex-UID-aehnliche Komponente im Topic-Pfad.
    Typische DSE890-Konvention: das ERSTE Hex-Segment mit >=10 Zeichen ist
    die Gateway-UID (z.B. '1922B6E660DBF6E'). Die Module-UID kommt typisch
    danach (z.B. '6E2B5CE14B').
    Returns: Hex-String oder None
    """
    import re as _re
    for p in topic_parts:
        p_clean = p.strip()
        if len(p_clean) >= 10 and _re.fullmatch(r"[A-Fa-f0-9]+", p_clean):
            return p_clean
    return None


def _learn_anlage_uids(topic: str):
    """Lerne UIDs pro Anlage aus jedem auflaufenden MQTT-Topic.

    Konvention: eventenergie/{ANLAGE_ID}/{UID_xx}/...
      - UID mit 10 Hex-Zeichen  -> Module-UID (DSE Bediendisplay)
      - UID mit 14-16 Hex-Zeichen -> Gateway-UID (DSE 890)

    Damit koennen wir spaeter beim GPS-Match die Bruecke schlagen:
    "Anlage 35072 hat Gateway-UID X und Module-UID Y" -> beide gehoeren
    zum gleichen physischen Setup.
    """
    if not topic:
        return None, set(), set()
    parts = topic.split("/")
    if len(parts) < 3 or parts[0] != "eventenergie":
        return None, set(), set()
    anlage_id = parts[1].strip()
    if not anlage_id:
        return None, set(), set()
    import re as _re
    new_gw = set()
    new_mod = set()
    for p in parts[2:]:
        p = p.strip()
        if not p:
            continue
        if _re.fullmatch(r"[A-Fa-f0-9]+", p):
            up = p.upper()
            if len(p) == 10:
                new_mod.add(up)
            elif 14 <= len(p) <= 16:
                new_gw.add(up)
    if not new_gw and not new_mod:
        return anlage_id, set(), set()
    entry = _anlage_index.setdefault(
        anlage_id, {"gw": set(), "mod": set(), "ts": time.time()}
    )
    entry["gw"].update(new_gw)
    entry["mod"].update(new_mod)
    entry["ts"] = time.time()
    return anlage_id, new_gw, new_mod


def _try_extract_dse890_pairing(topic: str):
    """Extrahiere ein Gateway-UID <-> Module-UID Pair direkt aus einem
    DSE890-konformen Telemetrie-Topic, falls beide UIDs darin enthalten sind.

    DSE890-Standard-Topic-Schema (5+ Segmente):
       eventenergie/<ANLAGE_ID>/<GATEWAY_UID>/<MODULE_UID>/<sub>

    - GATEWAY_UID: 14-16 Hex-Zeichen (USB-ID des DSE890 Gateways)
    - MODULE_UID:  10 Hex-Zeichen (USB-ID des DSE Bediendisplays)

    Returns: dict {anlage_id, gateway_uid, module_uid} oder None.
    """
    import re as _re
    if not topic:
        return None
    parts = topic.split("/")
    if len(parts) < 5 or parts[0] != "eventenergie":
        return None
    anlage = parts[1].strip()
    gw = parts[2].strip()
    mod = parts[3].strip()
    if not (_re.fullmatch(r"[A-Fa-f0-9]+", gw) and 14 <= len(gw) <= 16):
        return None
    if not (_re.fullmatch(r"[A-Fa-f0-9]+", mod) and len(mod) == 10):
        return None
    return {
        "anlage_id": anlage,
        "gateway_uid": gw.upper(),
        "module_uid": mod.upper(),
    }


async def _persist_anlage_pairing(anlage_id, gateway_uid, module_uid):
    """Speichere ein neues Anlage-Pairing in der DB (idempotent + best-effort).
    Wird genutzt fuer Audit/Reporting im Admin-GPS-Diagnose UI.
    """
    if not anlage_id or not gateway_uid or not module_uid or _db is None:
        return
    key = (anlage_id, gateway_uid.upper(), module_uid.upper())
    if key in _anlage_pair_persist:
        return
    _anlage_pair_persist.add(key)
    try:
        await _db.mqtt_anlage_pairing.update_one(
            {"anlage_id": anlage_id,
             "gateway_uid": gateway_uid.upper(),
             "module_uid": module_uid.upper()},
            {"$set": {
                "anlage_id": anlage_id,
                "gateway_uid": gateway_uid.upper(),
                "module_uid": module_uid.upper(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
            },
             "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "first_seen": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"_persist_anlage_pairing failed: {e}")


async def _auto_learn_gateway_uid(device_id=None, generator_id=None, topic=""):
    """Lerne die Gateway-UID aus dem Topic und speichere sie auf das
    matched Device (oder den verknuepften echten Generator). Nur einmal
    pro Device — wird per Cache-In-Memory-Check guarded, damit kein
    DB-Spam entsteht.
    """
    if not topic or _db is None:
        return
    topic_parts = topic.split("/")
    gw_uid = _extract_first_hex_uid(topic_parts)
    if not gw_uid:
        return
    try:
        # Auf Device speichern (primaer)
        if device_id:
            # In-Memory-Check: aktualisiere Cache
            for dev in (_devices_cache or []):
                if dev.get("id") == device_id:
                    if dev.get("dse_gateway_uid") == gw_uid:
                        return  # bereits gelernt
                    dev["dse_gateway_uid"] = gw_uid
                    break
            await _db.devices.update_one(
                {"id": device_id, "$or": [
                    {"dse_gateway_uid": {"$exists": False}},
                    {"dse_gateway_uid": {"$ne": gw_uid}},
                ]},
                {"$set": {"dse_gateway_uid": gw_uid}}
            )
            logger.info(f"MQTT: Auto-learned gateway_uid='{gw_uid}' for device {device_id}")
        # Auf Generator speichern (sekundaer, falls kein Device-Pendant)
        if generator_id and not generator_id.startswith("dev-"):
            for gen in (_generators_cache or []):
                if gen.get("id") == generator_id:
                    if gen.get("dse_gateway_uid") == gw_uid:
                        return
                    gen["dse_gateway_uid"] = gw_uid
                    break
            await _db.generators.update_one(
                {"id": generator_id, "$or": [
                    {"dse_gateway_uid": {"$exists": False}},
                    {"dse_gateway_uid": {"$ne": gw_uid}},
                ]},
                {"$set": {"dse_gateway_uid": gw_uid}}
            )
            logger.info(f"MQTT: Auto-learned gateway_uid='{gw_uid}' for generator {generator_id}")
    except Exception as e:
        logger.debug(f"Auto-learn gateway_uid failed: {e}")


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

    # --- Roh-Message-Logging (Ringpuffer, max 2000 Eintraege) ----------------
    # Damit der Diagnose-Block im Portal sehen kann WAS fuer ein konkretes
    # Geraet wirklich rein kommt (Topic + Payload). Nur die letzten 2000
    # Messages werden behalten (rotation via FIFO), sonst waechst das endlos.
    try:
        await _db.mqtt_raw_messages.insert_one({
            "topic": topic,
            "payload": payload_str[:4000],  # cap auf 4 KB
            "timestamp": timestamp,
            "received_at": timestamp,
        })
        global _raw_log_counter
        _raw_log_counter += 1
        # Periodisches Trimmen: alle 200 Inserts die aeltesten verwerfen,
        # damit max 2000 Eintraege im Ring bleiben.
        if _raw_log_counter % 200 == 0:
            n = await _db.mqtt_raw_messages.count_documents({})
            if n > 2000:
                overflow = n - 2000
                oldest = await _db.mqtt_raw_messages.find({}, {"_id": 1}).sort("timestamp", 1).limit(overflow).to_list(overflow)
                if oldest:
                    await _db.mqtt_raw_messages.delete_many({"_id": {"$in": [o["_id"] for o in oldest]}})
    except Exception as _e:
        # Logging darf NIE die Verarbeitung blockieren
        logger.debug(f"MQTT raw-log skip: {_e}")

    # Anlage-Index lernen: pro Anlage-ID, welche Gateway- und Module-UIDs
    # sehen wir? Wird spaeter genutzt um die DSE890 Bruecke zu schlagen.
    _learn_anlage_uids(topic)

    # DSE890-Bridge (USB-ID <-> Gateway-ID) aus Topic-Struktur extrahieren.
    # Wenn das Topic dem Schema eventenergie/<anlage>/<gw>/<mod>/<sub>
    # folgt -> persistiere das Pairing sofort. Damit kennt das System
    # die Bruecke OHNE Telemetrie verarbeiten zu muessen.
    dse890_pair = _try_extract_dse890_pairing(topic)
    if dse890_pair:
        await _persist_anlage_pairing(
            dse890_pair["anlage_id"],
            dse890_pair["gateway_uid"],
            dse890_pair["module_uid"],
        )

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
        # Beide Match-Felder mitladen, damit kein DB-Fallback bei jedem
        # GPS-Match noetig ist (vermeidet sonst N+1-DB-Roundtrips)
        _generators_cache = await _db.generators.find(
            {"$or": [
                {"dse_mqtt_topic_prefix": {"$exists": True, "$ne": ""}},
                {"dse_module_uid": {"$exists": True, "$ne": ""}},
                {"dse_gateway_uid": {"$exists": True, "$ne": ""}},
            ]},
            {"_id": 0, "id": 1, "dse_mqtt_topic_prefix": 1,
             "dse_module_uid": 1, "dse_gateway_uid": 1}
        ).to_list(200)
        _generators_cache_ts = now_ts

    if _devices_cache is None or now_ts - _devices_cache_ts > _CACHE_TTL:
        _devices_cache = await _db.devices.find(
            {"dse_module_uid": {"$exists": True, "$ne": ""}},
            {"_id": 0, "id": 1, "dse_module_uid": 1, "device_type": 1, "controller": 1,
             "dse_gateway_uid": 1}
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
            await _auto_learn_gateway_uid(generator_id=generator_id, topic=topic)
            if topic.endswith("/gps"):
                await _process_gps(generator_id, payload_str, parsed, timestamp, topic=topic)
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
            await _auto_learn_gateway_uid(generator_id=gen["id"], topic=topic)
            if topic.endswith("/gps"):
                await _process_gps(gen["id"], payload_str, parsed, timestamp, topic=topic)
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
    import re as _re
    for dev in _devices_cache:
        uid = dev.get("dse_module_uid", "").strip()
        if uid and uid.upper() in topic_parts_upper:
            device_id = dev["id"]
            logger.info(f"MQTT: Matched device {device_id} via module_uid {uid}")
            # AUTO-LEARN dse_gateway_uid: Das Segment direkt VOR der Module-UID
            # im Telemetrie-Topic ist die Gateway-UID. Damit kann das GPS-Topic
            # spaeter genauso einfach gematcht werden wie die Telemetrie.
            try:
                idx = topic_parts_upper.index(uid.upper())
                if idx > 0:
                    seg_before = topic_parts[idx - 1].strip()
                    # Hex-UID-Pruefung: alphanumerisch, >=10 Zeichen
                    # (verhindert falsches Lernen einer Anlagen-ID wie "35072")
                    if len(seg_before) >= 10 and _re.fullmatch(r"[A-Fa-f0-9]+", seg_before):
                        if dev.get("dse_gateway_uid") != seg_before:
                            await _db.devices.update_one(
                                {"id": device_id},
                                {"$set": {"dse_gateway_uid": seg_before}}
                            )
                            dev["dse_gateway_uid"] = seg_before
                            logger.info(
                                f"MQTT: Auto-learned gateway_uid='{seg_before}' "
                                f"for device {device_id} (module_uid={uid})"
                            )
            except (ValueError, Exception) as e:
                logger.debug(f"Auto-learn gateway_uid failed: {e}")
            if topic.endswith("/gps"):
                await _process_gps_device(device_id, payload_str, parsed, timestamp, topic=topic)
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


async def _log_gps_event(topic, lat, lng, route, applied_to, raw_payload=None, module_uid=None):
    """Schreibt jedes verarbeitete GPS-Event in mqtt_gps_log fuer Admin-Diagnose.

    route:      "per_generator" | "per_device" | "gateway_module_match" |
                "rejected_no_module_match" | "rejected"
    applied_to: Liste der Generator-IDs (oder Device-IDs als dev-<id>), die
                tatsaechlich upgedated wurden.
    module_uid: Die im JSON-Payload extrahierte Modul-UID (DSE890-Konvention:
                top-level JSON-Key). Wichtig fuer Diagnose:
                bei "rejected_no_module_match" sieht der Admin direkt, welche
                UID nicht im Portal hinterlegt ist und nachgetragen werden muss.
    """
    if _db is None:
        return
    try:
        doc = {
            "id": str(uuid.uuid4()),
            "topic": topic,
            "lat": lat,
            "lng": lng,
            "route": route,
            "applied_to": list(applied_to) if applied_to else [],
            "match_count": len(applied_to) if applied_to else 0,
            "ts": datetime.now(timezone.utc).isoformat(),
            "raw_preview": (str(raw_payload)[:400] if raw_payload else None),
            "module_uid": module_uid,
        }
        await _db.mqtt_gps_log.insert_one(doc)
        # Begrenze auf die letzten 1000 Eintraege - Auto-Pruning aber NICHT
        # synchron (blockiert sonst den Event-Loop bei MQTT-Spam). Stattdessen
        # fire-and-forget: bei jedem 500. Eintrag eine Hintergrund-Task starten.
        global _raw_msg_counter
        _raw_msg_counter += 1
        if _raw_msg_counter % 500 == 0:
            async def _prune():
                try:
                    cnt = await _db.mqtt_gps_log.count_documents({})
                    if cnt > 1000:
                        oldest = await _db.mqtt_gps_log.find(
                            {}, {"_id": 0, "id": 1}, sort=[("ts", 1)]
                        ).to_list(cnt - 1000)
                        if oldest:
                            old_ids = [o["id"] for o in oldest]
                            await _db.mqtt_gps_log.delete_many({"id": {"$in": old_ids}})
                except Exception:
                    pass
            asyncio.ensure_future(_prune())
    except Exception as e:
        logger.debug(f"_log_gps_event failed: {e}")




async def _process_gateway_gps(topic, raw_payload, parsed, timestamp):
    """Process GPS from a DSE 890 gateway and apply ONLY to the Module/Device
    whose UID is im JSON-Payload referenziert.

    DSE890 GPS-Konvention:
      Topic:   eventenergie/{ANLAGE_ID}/{GATEWAY_UID}/gps
      Payload: {"{MODULE_UID}": {"LAT": x, "LON": y}}

    Die Module-UID (z.B. "6D2B5CD695") wird im Portal als `dse_module_uid`
    gespeichert; die Gateway-UID (z.B. "1912C4E76883D4B") steht hingegen
    im Topic-Pfad. Daher MUSS die Zuordnung primaer ueber den JSON-Key
    erfolgen, NICHT ueber die Topic-Segmente.
    """
    if not isinstance(parsed, dict):
        return

    # Modul-UIDs (= Top-Level JSON Keys) sammeln + Lat/Lng extrahieren.
    # DSE890 kann mehrere Module gleichzeitig liefern:
    # {"UID_A": {"LAT": ...}, "UID_B": {"LAT": ...}}
    module_gps_pairs = []  # [(module_uid, lat, lng), ...]
    for uid_key, uid_data in parsed.items():
        if isinstance(uid_data, dict):
            mod_lat = uid_data.get("LAT") or uid_data.get("lat") or uid_data.get("latitude")
            mod_lng = uid_data.get("LON") or uid_data.get("lon") or uid_data.get("lng") or uid_data.get("longitude")
            if mod_lat is not None and mod_lng is not None:
                module_gps_pairs.append((str(uid_key).strip(), mod_lat, mod_lng))

    # Fallback: Flat-Format ohne Modul-Wrapper {"LAT": ..., "LON": ...}
    if not module_gps_pairs:
        flat_lat = parsed.get("LAT") or parsed.get("lat") or parsed.get("latitude")
        flat_lng = parsed.get("LON") or parsed.get("lon") or parsed.get("lng") or parsed.get("longitude")
        if flat_lat is not None and flat_lng is not None:
            # Ohne Modul-UID muessen wir auf den Topic-Pfad zurueckfallen
            module_gps_pairs.append((None, flat_lat, flat_lng))

    if not module_gps_pairs:
        return

    # Gateway-Topic ohne /gps (fuer Logging + Fallback-Match)
    gw_topic = topic[: -len("/gps")] if topic.endswith("/gps") else topic
    gw_topic = gw_topic.rstrip("/")

    total_matched = set()

    for module_uid, lat_raw, lng_raw in module_gps_pairs:
        try:
            lat = float(lat_raw)
            lng = float(lng_raw)
        except (TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        if lat == 0 and lng == 0:
            continue

        gps_update = {"latitude": lat, "longitude": lng, "last_gps_update": timestamp}
        matched_gen_ids = set()
        matched_device_ids = set()

        # PRIMAER: Match via Modul-UID aus dem JSON-Key (klassisches DSE-Format
        # mit Module-UID als Wrapper) ODER via dse_gateway_uid (DSE890 schickt
        # die Gateway-UID als Top-Level-Key im GPS-Payload).
        if module_uid:
            mu_upper = module_uid.upper()
            # 1a) Devices mit passender dse_module_uid (Modul-UID Match)
            for dev in (_devices_cache or []):
                dev_uid = (dev.get("dse_module_uid") or "").strip()
                if dev_uid and dev_uid.upper() == mu_upper:
                    matched_device_ids.add(dev["id"])
            # 1a-2) Devices mit passender dse_gateway_uid (Gateway-UID Match,
            #       hat Auto-Learn vorher per Telemetrie-Payload-Key gesetzt)
            for dev in (_devices_cache or []):
                dev_gw_uid = (dev.get("dse_gateway_uid") or "").strip()
                if dev_gw_uid and dev_gw_uid.upper() == mu_upper:
                    matched_device_ids.add(dev["id"])
            # 1b) Echte Generatoren mit passender dse_module_uid
            #     (manuell angelegte Generators, die kein Device-Pendant haben)
            for gen in (_generators_cache or []):
                gen_uid = (gen.get("dse_module_uid") or "").strip()
                if gen_uid and gen_uid.upper() == mu_upper:
                    matched_gen_ids.add(gen["id"])
            # 1c) DB-Fallback wenn Cache stale: BEIDE Collections + BEIDE UID-Felder
            if not matched_device_ids and not matched_gen_ids:
                import re
                try:
                    esc = re.escape(module_uid)
                    db_devs = await _db.devices.find(
                        {"$or": [
                            {"dse_module_uid": {"$regex": f"^{esc}$", "$options": "i"}},
                            {"dse_gateway_uid": {"$regex": f"^{esc}$", "$options": "i"}},
                        ]},
                        {"_id": 0, "id": 1}
                    ).to_list(10)
                    for d in db_devs:
                        matched_device_ids.add(d["id"])
                    db_gens = await _db.generators.find(
                        {"dse_module_uid": {"$regex": f"^{esc}$", "$options": "i"}},
                        {"_id": 0, "id": 1}
                    ).to_list(10)
                    for g in db_gens:
                        matched_gen_ids.add(g["id"])
                except Exception as e:
                    logger.debug(f"GPS DB-fallback (module_uid) failed: {e}")

        # SEKUNDAER: Mapping/Generator-Prefix oder Modul-UID irgendwo im Topic
        if not matched_device_ids and not matched_gen_ids:
            for mapping in _mappings_cache:
                mp = (mapping.get("topic_prefix") or "").strip().rstrip("/")
                gen_id = mapping.get("generator_id")
                if not mp or not gen_id:
                    continue
                # Match falls Modul-UID im Mapping-Prefix vorkommt
                if module_uid and module_uid.upper() in mp.upper():
                    matched_gen_ids.add(gen_id)
            for gen in _generators_cache:
                gp = (gen.get("dse_mqtt_topic_prefix") or "").strip().rstrip("/")
                if not gp:
                    continue
                if module_uid and module_uid.upper() in gp.upper():
                    matched_gen_ids.add(gen["id"])

        # TERTIAER: Match GPS-Topic-Gateway-UID (= erstes Hex-Segment im Topic)
        # gegen das gelernte dse_gateway_uid der Devices UND Generators.
        # Greift wenn Payload flach kommt ({lat,lon} ohne Wrapper) oder wenn
        # die UID im Payload-Key gleich der Gateway-UID ist (DSE890-Standard).
        if not matched_device_ids and not matched_gen_ids:
            # Kandidat = erste Hex-UID >=10 im Topic-Pfad
            gw_uid_candidate = _extract_first_hex_uid(gw_topic.split("/"))
            if gw_uid_candidate:
                gwu = gw_uid_candidate.upper()
                for dev in (_devices_cache or []):
                    dgu = (dev.get("dse_gateway_uid") or "").strip()
                    if dgu and dgu.upper() == gwu:
                        matched_device_ids.add(dev["id"])
                for gen in (_generators_cache or []):
                    ggu = (gen.get("dse_gateway_uid") or "").strip()
                    if ggu and ggu.upper() == gwu:
                        matched_gen_ids.add(gen["id"])
                # DB-Fallback wenn Cache stale
                if not matched_device_ids and not matched_gen_ids:
                    try:
                        import re as _re2
                        esc = _re2.escape(gw_uid_candidate)
                        db_devs = await _db.devices.find(
                            {"dse_gateway_uid": {"$regex": f"^{esc}$", "$options": "i"}},
                            {"_id": 0, "id": 1}
                        ).to_list(20)
                        for d in db_devs:
                            matched_device_ids.add(d["id"])
                        db_gens = await _db.generators.find(
                            {"dse_gateway_uid": {"$regex": f"^{esc}$", "$options": "i"}},
                            {"_id": 0, "id": 1}
                        ).to_list(20)
                        for g in db_gens:
                            matched_gen_ids.add(g["id"])
                    except Exception as e:
                        logger.debug(f"GPS DB-fallback (gateway_uid) failed: {e}")

        # TERTIAER-B (DSE890-Bruecke via mqtt_anlage_pairing):
        # Wir haben aus Telemetrie-Topics im DSE890-Schema
        # eventenergie/<anlage>/<gateway_uid>/<module_uid>/<sub>
        # bereits ein persistentes Pairing gespeichert. Wenn das GPS-Topic
        # die Gateway-UID enthaelt, finden wir hier direkt die zugehoerige
        # Module-UID und matchen auf das Device/Generator mit dieser UID.
        if not matched_device_ids and not matched_gen_ids and _db is not None:
            gw_uid_candidate = _extract_first_hex_uid(gw_topic.split("/"))
            if gw_uid_candidate:
                try:
                    pair = await _db.mqtt_anlage_pairing.find_one(
                        {"gateway_uid": gw_uid_candidate.upper()},
                        {"_id": 0, "module_uid": 1, "anlage_id": 1}
                    )
                    if pair:
                        mod_target = pair["module_uid"]
                        # Suche Device/Generator mit dieser Module-UID
                        # und schreibe gleichzeitig dse_gateway_uid darauf
                        # damit naechste GPS-Pakete direkt tertiaer matchen
                        for dev in (_devices_cache or []):
                            if (dev.get("dse_module_uid") or "").upper() == mod_target:
                                matched_device_ids.add(dev["id"])
                                if dev.get("dse_gateway_uid") != gw_uid_candidate:
                                    await _db.devices.update_one(
                                        {"id": dev["id"]},
                                        {"$set": {"dse_gateway_uid": gw_uid_candidate}}
                                    )
                                    dev["dse_gateway_uid"] = gw_uid_candidate
                                    logger.info(
                                        f"MQTT: DSE890-Bridge (Pairing-Tabelle): "
                                        f"Gateway-UID {gw_uid_candidate} -> "
                                        f"Module-UID {mod_target} -> "
                                        f"Device {dev['id']} verlinkt."
                                    )
                        for gen in (_generators_cache or []):
                            if (gen.get("dse_module_uid") or "").upper() == mod_target:
                                matched_gen_ids.add(gen["id"])
                                if gen.get("dse_gateway_uid") != gw_uid_candidate:
                                    await _db.generators.update_one(
                                        {"id": gen["id"]},
                                        {"$set": {"dse_gateway_uid": gw_uid_candidate}}
                                    )
                                    gen["dse_gateway_uid"] = gw_uid_candidate
                                    logger.info(
                                        f"MQTT: DSE890-Bridge (Pairing-Tabelle): "
                                        f"Gateway-UID {gw_uid_candidate} -> "
                                        f"Module-UID {mod_target} -> "
                                        f"Generator {gen['id']} verlinkt."
                                    )
                        # DB-Fallback wenn Cache stale
                        if not matched_device_ids and not matched_gen_ids:
                            db_devs = await _db.devices.find(
                                {"dse_module_uid": mod_target},
                                {"_id": 0, "id": 1}
                            ).to_list(10)
                            for d in db_devs:
                                matched_device_ids.add(d["id"])
                                await _db.devices.update_one(
                                    {"id": d["id"]},
                                    {"$set": {"dse_gateway_uid": gw_uid_candidate}}
                                )
                            db_gens = await _db.generators.find(
                                {"dse_module_uid": mod_target},
                                {"_id": 0, "id": 1}
                            ).to_list(10)
                            for g in db_gens:
                                matched_gen_ids.add(g["id"])
                                await _db.generators.update_one(
                                    {"id": g["id"]},
                                    {"$set": {"dse_gateway_uid": gw_uid_candidate}}
                                )
                except Exception as e:
                    logger.debug(f"DSE890-Bridge Pairing-Lookup failed: {e}")

        # QUARTAER (DSE890-Bruecke): Anlagen-ID-Pairing.
        # Nur EINDEUTIG: greift nur wenn unter dieser Anlage GENAU EIN
        # Gateway UND GENAU EIN Module gesehen wurden. Bei mehreren
        # DSE890-Setups in derselben Anlage waere das Pairing sonst
        # mehrdeutig und wuerde falsche Geraete miteinander verbinden.
        if not matched_device_ids and not matched_gen_ids:
            parts = topic.split("/")
            if len(parts) >= 3 and parts[0] == "eventenergie":
                anlage_id = parts[1].strip()
                entry = _anlage_index.get(anlage_id)
                if (entry and len(entry.get("mod", set())) == 1
                        and len(entry.get("gw", set())) <= 1):
                    gw_uid_for_topic = _extract_first_hex_uid(parts[2:])
                    mod_uid_upper = next(iter(entry["mod"]))
                    if gw_uid_for_topic:
                        for dev in (_devices_cache or []):
                            dev_mod = (dev.get("dse_module_uid") or "").strip().upper()
                            if dev_mod and dev_mod == mod_uid_upper:
                                if dev.get("dse_gateway_uid") != gw_uid_for_topic:
                                    await _db.devices.update_one(
                                        {"id": dev["id"]},
                                        {"$set": {"dse_gateway_uid": gw_uid_for_topic}}
                                    )
                                    dev["dse_gateway_uid"] = gw_uid_for_topic
                                    logger.info(
                                        f"MQTT: Anlage-Pairing (Anlage {anlage_id}, EINDEUTIG): "
                                        f"Device {dev['id']} mod={mod_uid_upper} <-> "
                                        f"Gateway-UID {gw_uid_for_topic} gepaart."
                                    )
                                matched_device_ids.add(dev["id"])
                                await _persist_anlage_pairing(
                                    anlage_id, gw_uid_for_topic, mod_uid_upper
                                )
                        for gen in (_generators_cache or []):
                            gen_mod = (gen.get("dse_module_uid") or "").strip().upper()
                            if gen_mod and gen_mod == mod_uid_upper:
                                if gen.get("dse_gateway_uid") != gw_uid_for_topic:
                                    await _db.generators.update_one(
                                        {"id": gen["id"]},
                                        {"$set": {"dse_gateway_uid": gw_uid_for_topic}}
                                    )
                                    gen["dse_gateway_uid"] = gw_uid_for_topic
                                    logger.info(
                                        f"MQTT: Anlage-Pairing (Anlage {anlage_id}, EINDEUTIG): "
                                        f"Generator {gen['id']} mod={mod_uid_upper} <-> "
                                        f"Gateway-UID {gw_uid_for_topic} gepaart."
                                    )
                                matched_gen_ids.add(gen["id"])
                                await _persist_anlage_pairing(
                                    anlage_id, gw_uid_for_topic, mod_uid_upper
                                )
                elif entry and (len(entry.get("mod", set())) > 1
                                or len(entry.get("gw", set())) > 1):
                    logger.warning(
                        f"MQTT: Anlage-Pairing (Anlage {anlage_id}) NICHT moeglich: "
                        f"mehrdeutig (mod={len(entry.get('mod', set()))}, "
                        f"gw={len(entry.get('gw', set()))}). Bitte dse_gateway_uid "
                        f"manuell pflegen oder eindeutigeres Topic-Schema einrichten."
                    )

        # Devices auf gen_ids erweitern (dev-<id> Schema)
        for dev_id in matched_device_ids:
            matched_gen_ids.add(f"dev-{dev_id}")

        # Apply
        for gen_id in matched_gen_ids:
            await _db.generators.update_one({"id": gen_id}, {"$set": gps_update})
            if gen_id.startswith("dev-"):
                await _db.devices.update_one(
                    {"id": gen_id[4:]}, {"$set": gps_update}
                )
            total_matched.add(gen_id)

        if matched_gen_ids:
            route_used = "gateway_module_match" if module_uid else "gateway_prefix_match"
            logger.info(
                f"MQTT: Gateway-GPS {lat},{lng} module_uid='{module_uid}' "
                f"auf {len(matched_gen_ids)} Geraet(e) angewendet ({topic}, route={route_used})"
            )
            await _log_gps_event(topic, lat, lng, route_used,
                                 matched_gen_ids, raw_payload, module_uid=module_uid)
            # Wenn dieses Gateway in mqtt_unknown_gateways stand: aufraeumen
            if module_uid:
                try:
                    await _db.mqtt_unknown_gateways.delete_one(
                        {"gateway_uid": module_uid}
                    )
                except Exception:
                    pass
        else:
            reject_route = "rejected_no_module_match" if module_uid else "rejected_no_prefix_match"
            logger.warning(
                f"MQTT: Gateway-GPS {lat},{lng} ({topic}) - kein Match. "
                f"module_uid={module_uid}, gw_topic={gw_topic}. "
                f"Hinweis: Bitte dse_gateway_uid am Device/Generator pflegen "
                f"oder im Admin-GPS-Diagnose UI verknuepfen."
            )
            await _log_gps_event(topic, lat, lng, reject_route,
                                 [], raw_payload, module_uid=module_uid)
            # Auto-Discovery: speichere unbekannte Gateway-UID als Stub, damit
            # der Admin sie im UI per 1-Klick einem Device/Generator zuordnen kann.
            await _upsert_unknown_gateway(topic, module_uid, lat, lng)


async def _upsert_unknown_gateway(topic, module_uid, lat, lng):
    """Speichere ein unbekanntes Gateway als Stub in mqtt_unknown_gateways.
    Im Admin-UI kann es spaeter zugeordnet werden. Idempotent via gateway_uid.
    """
    if _db is None or not module_uid:
        return
    parts = topic.split("/")
    anlage_id = parts[1] if len(parts) > 1 else None
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        await _db.mqtt_unknown_gateways.update_one(
            {"gateway_uid": module_uid},
            {
                "$set": {
                    "gateway_uid": module_uid,
                    "anlage_id": anlage_id,
                    "last_topic": topic,
                    "last_lat": lat,
                    "last_lng": lng,
                    "last_seen": now_iso,
                },
                "$setOnInsert": {
                    "id": str(uuid.uuid4()),
                    "first_seen": now_iso,
                },
                "$inc": {"event_count": 1},
            },
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"_upsert_unknown_gateway failed: {e}")


async def _process_gps(generator_id, raw_payload, parsed, timestamp, topic=""):
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
                await _log_gps_event(topic, lat, lng, "per_generator", [generator_id], raw_payload)
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


async def _process_gps_device(device_id, raw_payload, parsed, timestamp, topic=""):
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
                await _log_gps_event(topic, lat, lng, "per_device", [f"dev-{device_id}"], raw_payload)
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
                # CPU-intensive Parsing in ThreadPool offloaden (vermeidet
                # Event-Loop-Blockierung bei Bursts).
                _loop_eo = asyncio.get_running_loop()
                gencomm_data = await _loop_eo.run_in_executor(
                    None, _parse_gencomm_registers, parsed, topic
                )
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
    Throttled to only write DB every 5 minutes per generator.
    Schreibt zusaetzlich dse_module_uid (nur falls noch leer), damit
    GPS-Routing automatisch matcht ohne manuelles Pflegen."""
    now = time.time()
    last = _uid_store_cache.get(generator_id, 0)
    if now - last < _UID_STORE_INTERVAL:
        return  # Recently stored, skip DB write

    uid, prefix = _extract_module_uid_from_topic(topic)
    if uid and _db is not None:
        update = {"last_mqtt_module_uid": uid}
        if prefix:
            update["last_mqtt_topic_prefix"] = prefix
        # Generator: setze auch dse_module_uid (nur wenn noch leer),
        # damit Sekundaer/Pfad-3-Match automatisch greift.
        await _db.generators.update_one(
            {"id": generator_id,
             "$or": [
                 {"dse_module_uid": {"$exists": False}},
                 {"dse_module_uid": ""},
                 {"dse_module_uid": None},
             ]},
            {"$set": {**update, "dse_module_uid": uid}},
        )
        # Falls bereits eine andere dse_module_uid hinterlegt ist, nur
        # die last_* Felder aktualisieren ohne ueberschreiben.
        await _db.generators.update_one(
            {"id": generator_id,
             "dse_module_uid": {"$exists": True, "$nin": ["", None]}},
            {"$set": update}
        )
        if generator_id.startswith("dev-"):
            device_id = generator_id[4:]
            await _db.devices.update_one(
                {"id": device_id,
                 "$or": [
                     {"dse_module_uid": {"$exists": False}},
                     {"dse_module_uid": ""},
                     {"dse_module_uid": None},
                 ]},
                {"$set": {**update, "dse_module_uid": uid}},
            )
            await _db.devices.update_one(
                {"id": device_id,
                 "dse_module_uid": {"$exists": True, "$nin": ["", None]}},
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
        _loop_eo2 = asyncio.get_running_loop()
        gencomm_data = await _loop_eo2.run_in_executor(
            None, _parse_gencomm_registers, parsed, topic
        )
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
        # WICHTIG: Bit 10 ("SB_WARNING") wird BEWUSST nicht hinzugefuegt.
        # Das DSE 890 setzt das oft ohne begleitende A-Code-Condition als
        # Aggregat-Flag, was zu Dauer-Alarm im Portal fuehrt ohne dass eine
        # konkrete Ursache vorhanden ist. Echte Warnings via A-Codes laufen
        # ueber _process_alarm() und triggern dort den Alarm-Status.
        active_faults = []
        if sb & 0x2000:
            active_faults.append(("SB_CTRL_FAIL", "Steuerungsfehler (Control Unit Failure)", "shutdown"))
        if sb & 0x1000:
            active_faults.append(("SB_SHUTDOWN", "Abschaltung aktiv (Shutdown Alarm)", "shutdown"))
        if sb & 0x0800:
            active_faults.append(("SB_ELEC_TRIP", "Elektrische Ausloesung (Electrical Trip)", "shutdown"))
        # if sb & 0x0400:  # SB_WARNING - ABSICHTLICH IGNORIERT (Option A, User-Choice)
        if sb & 0x0040:
            active_faults.append(("SB_CTRL_STOP", "Kontrollierte Abschaltung (Controlled Shutdown)", "warning"))

        if active_faults:
            # Use the most severe fault as the primary display text
            result["fault_code"] = sb
            result["fault_text"] = active_faults[0][1]  # Most severe first
            result["status_alarms"] = active_faults
        else:
            # Auch wenn Bit 10 alleine gesetzt ist (sb == 0x0400) zaehlt das als
            # "kein Alarm" - genau das ist der Filter-Effekt von Option A.
            result["fault_code"] = 0

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
    global _mqtt_client, _mqtt_thread, _db, _loop, _mqtt_queue, _mqtt_workers
    _db = db_instance
    _loop = loop

    # Index fuer GPS-Log Pruning (sort auf ts)
    try:
        await _db.mqtt_gps_log.create_index([("ts", 1)])
    except Exception as e:
        logger.debug(f"GPS-Log Index existiert bereits: {e}")

    # Einmalige Migration: kopiere last_mqtt_module_uid -> dse_module_uid
    # bei Geraeten/Generatoren, die das automatisch erkannt haben, aber
    # dse_module_uid noch leer ist. Damit greift das GPS-Routing
    # rueckwirkend fuer alle alten Datensaetze.
    try:
        migr_filter = {
            "last_mqtt_module_uid": {"$exists": True, "$nin": ["", None]},
            "$or": [
                {"dse_module_uid": {"$exists": False}},
                {"dse_module_uid": ""},
                {"dse_module_uid": None},
            ],
        }
        gens_to_migrate = await _db.generators.find(
            migr_filter, {"_id": 0, "id": 1, "last_mqtt_module_uid": 1}
        ).to_list(500)
        gen_migr_count = 0
        for g in gens_to_migrate:
            await _db.generators.update_one(
                {"id": g["id"]},
                {"$set": {"dse_module_uid": g["last_mqtt_module_uid"]}}
            )
            gen_migr_count += 1
        devs_to_migrate = await _db.devices.find(
            migr_filter, {"_id": 0, "id": 1, "last_mqtt_module_uid": 1}
        ).to_list(500)
        dev_migr_count = 0
        for d in devs_to_migrate:
            await _db.devices.update_one(
                {"id": d["id"]},
                {"$set": {"dse_module_uid": d["last_mqtt_module_uid"]}}
            )
            dev_migr_count += 1
        if gen_migr_count or dev_migr_count:
            logger.info(
                f"MQTT-Migration: dse_module_uid aus last_mqtt_module_uid kopiert "
                f"(Generators={gen_migr_count}, Devices={dev_migr_count})"
            )
    except Exception as e:
        logger.warning(f"MQTT-Migration fehlgeschlagen: {e}")

    # MQTT Worker-Pool starten: vermeidet Event-Loop-Saturation bei Bursts
    _mqtt_queue = asyncio.Queue(maxsize=_MQTT_QUEUE_MAX)
    _mqtt_workers = [
        asyncio.create_task(_mqtt_worker(i), name=f"mqtt-worker-{i}")
        for i in range(_MQTT_WORKER_COUNT)
    ]
    logger.info(f"MQTT: {_MQTT_WORKER_COUNT} Worker-Tasks gestartet (Queue max={_MQTT_QUEUE_MAX})")

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