from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging
import asyncio
import secrets
import os
import hashlib
import base64
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mqtt", tags=["mqtt"])
security = HTTPBearer()

db = None
decode_jwt_token = None


def init_mqtt_routes(_db, _decode_jwt_token):
    global db, decode_jwt_token
    db = _db
    decode_jwt_token = _decode_jwt_token


# ============== Models ==============

class MqttConfigUpdate(BaseModel):
    enabled: bool = False
    broker_url: str = ""
    broker_port: int = 1883
    username: str = ""
    password: str = ""
    use_tls: bool = False
    subscribe_topics: List[str] = ["dse/#"]


class GatewayMappingCreate(BaseModel):
    gateway_name: str
    topic_prefix: str
    generator_id: str
    notes: str = ""


class GatewayMappingUpdate(BaseModel):
    gateway_name: Optional[str] = None
    topic_prefix: Optional[str] = None
    generator_id: Optional[str] = None
    notes: Optional[str] = None


# ============== Helpers ==============

async def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_jwt_token(credentials.credentials)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin-Berechtigung erforderlich")
    return user


async def require_operator(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Require admin or Mitarbeiter role."""
    payload = decode_jwt_token(credentials.credentials)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user or user["role"] not in ("admin", "mitarbeiter"):
        raise HTTPException(status_code=403, detail="Keine Berechtigung (Admin oder Mitarbeiter erforderlich)")
    return user


# ============== MQTT Config ==============

@router.get("/config")
async def get_mqtt_config(admin: dict = Depends(require_admin)):
    config = await db.mqtt_config.find_one({}, {"_id": 0})
    if not config:
        config = {
            "enabled": False,
            "broker_url": "",
            "broker_port": 1883,
            "username": "",
            "password": "",
            "use_tls": False,
            "subscribe_topics": ["dse/#"],
            "connection_status": "disconnected",
            "connection_message": "",
        }
    # Mask password
    if config.get("password"):
        config["password_set"] = True
        config["password"] = "********"
    else:
        config["password_set"] = False
    return config


@router.put("/config")
async def update_mqtt_config(data: MqttConfigUpdate, admin: dict = Depends(require_admin)):
    existing = await db.mqtt_config.find_one({}, {"_id": 0})

    update_doc = {
        "enabled": data.enabled,
        "broker_url": data.broker_url.strip(),
        "broker_port": data.broker_port,
        "username": data.username.strip(),
        "use_tls": data.use_tls,
        "subscribe_topics": data.subscribe_topics,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Only update password if it's not the masked value
    if data.password and data.password != "********":
        update_doc["password"] = data.password

    if existing:
        await db.mqtt_config.update_one({}, {"$set": update_doc})
    else:
        update_doc["connection_status"] = "disconnected"
        update_doc["connection_message"] = ""
        if "password" not in update_doc:
            update_doc["password"] = ""
        await db.mqtt_config.insert_one(update_doc)

    # Restart MQTT client with new config
    from mqtt_service import restart_mqtt_client
    loop = asyncio.get_event_loop()
    await restart_mqtt_client(db, loop)

    result = await db.mqtt_config.find_one({}, {"_id": 0})
    if result and result.get("password"):
        result["password"] = "********"
        result["password_set"] = True
    return result


@router.post("/test-connection")
async def test_mqtt_connection(admin: dict = Depends(require_admin)):
    """Test MQTT broker connection without saving config."""
    config = await db.mqtt_config.find_one({}, {"_id": 0})
    if not config:
        raise HTTPException(status_code=400, detail="Keine MQTT-Konfiguration vorhanden")

    import paho.mqtt.client as mqtt
    result = {"success": False, "message": ""}

    try:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"test-{uuid.uuid4().hex[:8]}",
            protocol=mqtt.MQTTv311
        )
        if config.get("username") and config.get("password"):
            client.username_pw_set(config["username"], config["password"])
        if config.get("use_tls"):
            client.tls_set()

        client.connect(config["broker_url"], config.get("broker_port", 1883), keepalive=10)
        client.loop_start()

        import time
        time.sleep(3)

        if client.is_connected():
            result = {"success": True, "message": "Verbindung erfolgreich!"}
        else:
            result = {"success": False, "message": "Verbindung fehlgeschlagen - Broker nicht erreichbar"}

        client.loop_stop()
        client.disconnect()
    except Exception as e:
        result = {"success": False, "message": f"Fehler: {str(e)}"}

    return result


@router.get("/status")
async def get_mqtt_status(admin: dict = Depends(require_admin)):
    from mqtt_service import is_connected
    config = await db.mqtt_config.find_one({}, {"_id": 0})

    return {
        "enabled": config.get("enabled", False) if config else False,
        "connected": is_connected(),
        "connection_status": config.get("connection_status", "disconnected") if config else "disconnected",
        "connection_message": config.get("connection_message", "") if config else "",
        "last_status_update": config.get("last_status_update", "") if config else "",
    }


# ============== Gateway Mappings ==============

@router.get("/mappings")
async def list_gateway_mappings(admin: dict = Depends(require_admin)):
    mappings = await db.mqtt_gateway_mappings.find({}, {"_id": 0}).to_list(100)
    # Enrich with generator info
    for m in mappings:
        gen = await db.generators.find_one({"id": m.get("generator_id")}, {"_id": 0, "name": 1, "serial_number": 1})
        if gen:
            m["generator_name"] = gen.get("name", "")
            m["generator_serial"] = gen.get("serial_number", "")
    return mappings


@router.post("/mappings")
async def create_gateway_mapping(data: GatewayMappingCreate, admin: dict = Depends(require_admin)):
    gen = await db.generators.find_one({"id": data.generator_id}, {"_id": 0})
    if not gen and data.generator_id.startswith("dev-"):
        device_id = data.generator_id[4:]
        device = await db.devices.find_one({"id": device_id}, {"_id": 0})
        if device:
            gen = device
    if not gen:
        raise HTTPException(status_code=404, detail="Generator nicht gefunden")

    mapping_doc = {
        "id": str(uuid.uuid4()),
        "gateway_name": data.gateway_name,
        "topic_prefix": data.topic_prefix,
        "generator_id": data.generator_id,
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.mqtt_gateway_mappings.insert_one(mapping_doc)
    result = {k: v for k, v in mapping_doc.items() if k != "_id"}
    return result


@router.put("/mappings/{mapping_id}")
async def update_gateway_mapping(mapping_id: str, data: GatewayMappingUpdate, admin: dict = Depends(require_admin)):
    existing = await db.mqtt_gateway_mappings.find_one({"id": mapping_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Mapping nicht gefunden")

    update_data = {}
    if data.gateway_name is not None:
        update_data["gateway_name"] = data.gateway_name
    if data.topic_prefix is not None:
        update_data["topic_prefix"] = data.topic_prefix
    if data.generator_id is not None:
        gen = await db.generators.find_one({"id": data.generator_id}, {"_id": 0})
        if not gen and data.generator_id.startswith("dev-"):
            device_id = data.generator_id[4:]
            device = await db.devices.find_one({"id": device_id}, {"_id": 0})
            if device:
                gen = device
        if not gen:
            raise HTTPException(status_code=404, detail="Generator nicht gefunden")
        update_data["generator_id"] = data.generator_id
    if data.notes is not None:
        update_data["notes"] = data.notes

    if update_data:
        await db.mqtt_gateway_mappings.update_one({"id": mapping_id}, {"$set": update_data})

    updated = await db.mqtt_gateway_mappings.find_one({"id": mapping_id}, {"_id": 0})
    return updated


@router.delete("/mappings/{mapping_id}")
async def delete_gateway_mapping(mapping_id: str, admin: dict = Depends(require_admin)):
    result = await db.mqtt_gateway_mappings.delete_one({"id": mapping_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Mapping nicht gefunden")
    return {"message": "Mapping gelöscht"}


# ============== Raw Messages (Debug) ==============

@router.get("/raw-messages")
async def get_raw_messages(limit: int = 50, admin: dict = Depends(require_admin)):
    messages = await db.mqtt_raw_messages.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return messages


@router.delete("/raw-messages")
async def clear_raw_messages(admin: dict = Depends(require_admin)):
    await db.mqtt_raw_messages.delete_many({})
    return {"message": "Alle Roh-Nachrichten gelöscht"}


# ============== Generator Control ==============

# DSE Gencomm System Control Keys (Page 16, Offset 8+9)
# Register 4104 = Control Key, Register 4105 = Complement (65535 - Key)
# Both must be written simultaneously (Modbus Function Code 16)
# DSE System Control Keys – Function 3: Gateway berechnet Complement automatisch
# Payload: {"key": VALUE} – NICHT das volle GenComm JSON!
DSE_COMMANDS = {
    "stop":                {"key": 35700, "label": "Stop-Modus"},
    "auto_on":             {"key": 35701, "label": "Automatikmodus"},
    "manual":              {"key": 35702, "label": "Manueller Modus"},
    "test_on_load":        {"key": 35703, "label": "Testlauf unter Last"},
    "auto_manual_restore": {"key": 35704, "label": "Auto mit manueller Rueckkehr"},
    "start":               {"key": 35705, "label": "Motor starten (Manuell/Test)"},
    "mute":                {"key": 35706, "label": "Alarm stumm"},
    "reset":               {"key": 35707, "label": "Alarme zuruecksetzen"},
    "gen_switch_on":       {"key": 35708, "label": "Generator zuschalten"},
    "gen_switch_off":      {"key": 35709, "label": "Generator abschalten"},
    "reset_mains":         {"key": 35710, "label": "Netzausfall zuruecksetzen"},
}


class GeneratorCommand(BaseModel):
    command: str  # start, stop, auto_on, auto_off


@router.post("/control/{generator_id}")
async def send_generator_command(generator_id: str, cmd: GeneratorCommand, user: dict = Depends(require_operator)):
    """Send a control command to a generator via MQTT."""
    from mqtt_service import publish_command

    if cmd.command not in DSE_COMMANDS:
        raise HTTPException(status_code=400, detail=f"Unbekannter Befehl: {cmd.command}. Erlaubt: {list(DSE_COMMANDS.keys())}")

    # Find the generator AND device (for dev- generators, always lookup both)
    gen = await db.generators.find_one({"id": generator_id}, {"_id": 0})
    device = None
    if generator_id.startswith("dev-"):
        device_id = generator_id[4:]
        device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not gen and not device:
        raise HTTPException(status_code=404, detail="Generator nicht gefunden")

    # Check if this is a Pi-based generator (DSE 5510) -> queue command instead of MQTT
    pi_device = device
    if pi_device and pi_device.get("controller") == "DSE 5510":
        dse_cmd = DSE_COMMANDS[cmd.command]
        cmd_doc = {
            "id": str(uuid.uuid4()),
            "device_id": pi_device["id"],
            "generator_id": generator_id,
            "command": cmd.command,
            "label": dse_cmd["label"],
            "status": "pending",
            "user_id": user.get("id", ""),
            "user_name": user.get("name", user.get("email", "")),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.generator_pending_commands.insert_one(cmd_doc)
        await db.generator_control_log.insert_one({
            "id": str(uuid.uuid4()),
            "generator_id": generator_id,
            "generator_name": pi_device.get("serial_number", ""),
            "command": cmd.command,
            "command_label": dse_cmd["label"],
            "topic": "pi-http",
            "payload": f"Queued for Pi: {cmd.command}",
            "user_id": user.get("id", ""),
            "user_name": user.get("name", user.get("email", "")),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "success": True,
            "message": f"{dse_cmd['label']} - wird beim naechsten Pi-Sync ausgefuehrt",
            "command_id": cmd_doc["id"],
            "delivery": "pi-queue",
        }

    # For devices with dse_module_uid, build control topic directly
    module_uid = device.get("dse_module_uid", "") if device else ""

    # Also check generator's own UID (set directly or auto-detected from MQTT)
    if not module_uid and gen:
        module_uid = gen.get("dse_module_uid", "") or gen.get("last_mqtt_module_uid", "")

    # Get the full topic prefix (group/type/uid) from auto-detection
    topic_prefix = ""
    if gen:
        topic_prefix = gen.get("last_mqtt_topic_prefix", "")
    if not topic_prefix and device:
        topic_prefix = device.get("last_mqtt_topic_prefix", "")

    # Fallback: find prefix from another device on same gateway (shared gateway PIN)
    if not topic_prefix and module_uid:
        other = await db.devices.find_one(
            {"last_mqtt_topic_prefix": {"$exists": True, "$ne": ""}},
            {"_id": 0, "last_mqtt_topic_prefix": 1}
        )
        if other:
            # Extract gateway PIN from other device's prefix: eventenergie/32788/OTHER_UID
            parts = other["last_mqtt_topic_prefix"].split("/")
            if len(parts) >= 3:
                # Replace the UID with our module_uid
                parts[-1] = module_uid
                topic_prefix = "/".join(parts)

    if module_uid:
        # Build control topic: use stored prefix if available (includes TYPE segment)
        if topic_prefix:
            control_topic = f"{topic_prefix}/control"
        else:
            control_topic = f"eventenergie/{module_uid}/control"

        dse_cmd = DSE_COMMANDS[cmd.command]
        # Function 3: {"UID": {"K": control_key}} – Gateway berechnet Complement automatisch
        payload = json.dumps({module_uid: {"K": dse_cmd["key"]}})

        try:
            success = publish_command(control_topic, payload)
            log_entry = {
                "id": str(uuid.uuid4()),
                "generator_id": generator_id,
                "command": cmd.command,
                "topic": control_topic,
                "payload": payload,
                "success": success,
                "user": user.get("email", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await db.generator_control_log.insert_one(log_entry)

            # Store commanded mode on device + generator for instant UI feedback
            dev_id = generator_id[4:] if generator_id.startswith("dev-") else None
            mode_map = {"stop": "stop", "auto_on": "auto", "manual": "manual", "start": "manual"}
            commanded_mode = mode_map.get(cmd.command, "")
            if commanded_mode:
                mode_update = {"last_dse_mode": commanded_mode}
                await db.generators.update_one({"id": generator_id}, {"$set": mode_update})
                if dev_id:
                    await db.devices.update_one({"id": dev_id}, {"$set": mode_update})

            # Force immediate status refresh: invalidate status cache
            from mqtt_service import _status_cache, _uid_store_cache
            if dev_id and dev_id in _status_cache:
                del _status_cache[dev_id]
            if generator_id in _uid_store_cache:
                del _uid_store_cache[generator_id]

            return {
                "success": success,
                "message": dse_cmd["label"],
                "topic": control_topic,
                "command_sent": cmd.command,
            }
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=f"Fehler: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")

    # Legacy: Find the gateway mapping for this generator
    mapping = await db.mqtt_gateway_mappings.find_one({"generator_id": generator_id}, {"_id": 0})
    if not mapping:
        raise HTTPException(status_code=404, detail="Kein MQTT-Gateway für diesen Generator konfiguriert")

    # Build the control topic from the mapping's topic_prefix
    # Topic prefix is like "/32788/" and the UID is in the notes or we derive from existing topics
    prefix = mapping.get("topic_prefix", "").rstrip("/")

    # Get the module UID from the latest raw message for this prefix
    escaped_prefix = prefix.replace("/", "\\/")
    latest_msg = await db.mqtt_raw_messages.find_one(
        {"topic": {"$regex": f"^{escaped_prefix}"}},
        {"_id": 0, "topic": 1}
    )
    if latest_msg:
        # Extract full prefix from topic like eventenergie/DSE8610/6D2B5CDE5F/engine
        # The control topic is: everything-before-last-segment/control
        parts = latest_msg["topic"].strip("/").split("/")
        if len(parts) >= 4:
            # Standard: group/type/uid/subtopic → control = group/type/uid/control
            uid = parts[-2]  # UID is second-to-last
            control_topic = "/".join(parts[:-1]) + "/control"
        elif len(parts) >= 2:
            uid = parts[1] if len(parts) >= 2 else ""
            control_topic = f"{prefix}/{uid}/control"
        else:
            raise HTTPException(status_code=400, detail="Topic-Format nicht erkannt")
    else:
        raise HTTPException(status_code=400, detail="Kein aktives Gerät gefunden. Gateway muss zuerst Daten senden.")

    dse_cmd = DSE_COMMANDS[cmd.command]
    # Function 3: {"UID": {"K": control_key}} – Gateway berechnet Complement automatisch
    payload = json.dumps({uid: {"K": dse_cmd["key"]}})

    try:
        publish_command(control_topic, payload)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Log the control action
    entity = gen or device or {}
    entity_name = entity.get("name", entity.get("serial_number", ""))
    log_entry = {
        "id": str(uuid.uuid4()),
        "generator_id": generator_id,
        "generator_name": entity_name,
        "command": cmd.command,
        "command_label": dse_cmd["label"],
        "topic": control_topic,
        "payload": payload,
        "user_id": user["id"],
        "user_name": user.get("name", user.get("email", "")),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.generator_control_log.insert_one(log_entry)

    return {
        "success": True,
        "command": cmd.command,
        "label": dse_cmd["label"],
        "topic": control_topic,
        "generator": entity_name,
    }


@router.get("/control/{generator_id}/log")
async def get_control_log(generator_id: str, user: dict = Depends(require_operator)):
    """Get the control command history for a generator."""
    logs = await db.generator_control_log.find(
        {"generator_id": generator_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(50)
    return logs


# ============== Gateway MQTT Credentials ==============

MOSQUITTO_PASSWD_FILE = r"C:\eventenergie\mosquitto_passwd"
MOSQUITTO_EXE = r"C:\Program Files\Mosquitto\mosquitto.exe"
MOSQUITTO_CONF = r"C:\Program Files\Mosquitto\mosquitto.conf"


def _mosquitto_hash(password: str, iterations: int = 101) -> str:
    """Generate Mosquitto-compatible PBKDF2-SHA512 password hash ($7$ format)."""
    salt = os.urandom(12)
    dk = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), salt, iterations, dklen=64)
    salt_b64 = base64.b64encode(salt).decode('ascii')
    dk_b64 = base64.b64encode(dk).decode('ascii')
    return f"$7${iterations}${salt_b64}${dk_b64}"


async def _regenerate_passwd_file():
    """Update the Mosquitto passwd file: keep existing entries, add/update from DB."""
    passwd_path = MOSQUITTO_PASSWD_FILE
    if not passwd_path:
        logger.info("MOSQUITTO_PASSWD_FILE nicht konfiguriert")
        return False

    # Read existing entries first (preserve manually added ones)
    existing = {}
    try:
        with open(passwd_path, 'r') as f:
            for line in f:
                line = line.strip()
                if ':' in line:
                    user, pw = line.split(':', 1)
                    existing[user] = pw
    except FileNotFoundError:
        pass

    # Add/update from DB (generators)
    generators = await db.generators.find(
        {"mqtt_username": {"$exists": True, "$ne": ""}},
        {"_id": 0, "mqtt_username": 1, "mqtt_password_hash": 1}
    ).to_list(1000)
    for gen in generators:
        username = gen.get("mqtt_username", "")
        pw_hash = gen.get("mqtt_password_hash", "")
        if username and pw_hash:
            existing[username] = pw_hash

    # Add/update from DB (devices)
    devices = await db.devices.find(
        {"mqtt_username": {"$exists": True, "$ne": ""}},
        {"_id": 0, "mqtt_username": 1, "mqtt_password_hash": 1}
    ).to_list(1000)
    for dev in devices:
        username = dev.get("mqtt_username", "")
        pw_hash = dev.get("mqtt_password_hash", "")
        if username and pw_hash:
            existing[username] = pw_hash

    lines = [f"{user}:{pw}" for user, pw in existing.items()]

    try:
        with open(passwd_path, 'w', newline='\n') as f:
            f.write('\n'.join(lines) + '\n' if lines else '')
        logger.info(f"Mosquitto passwd aktualisiert: {len(lines)} User in {passwd_path}")

        # Signal Mosquitto to reload password file (without restart)
        import subprocess
        try:
            # mosquitto_passwd --reload or kill -HUP on Linux
            # On Windows: restart mosquitto gracefully
            import platform
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/f", "/im", "mosquitto.exe"],
                               capture_output=True, timeout=5)
                import time
                time.sleep(1)
                subprocess.Popen([MOSQUITTO_EXE, "-c", MOSQUITTO_CONF],
                                 creationflags=0x00000008)  # DETACHED_PROCESS
                logger.info("Mosquitto neugestartet nach Passwort-Aenderung")
            else:
                # Linux: send SIGHUP to reload config
                result = subprocess.run(["pkill", "-HUP", "mosquitto"],
                                        capture_output=True, timeout=5)
                if result.returncode == 0:
                    logger.info("Mosquitto SIGHUP gesendet (passwd reload)")
        except Exception as e:
            logger.warning(f"Mosquitto Reload fehlgeschlagen: {e} – bitte manuell neustarten")

        return True
    except Exception as e:
        logger.error(f"passwd-Datei schreiben fehlgeschlagen: {e}")
        return False


@router.get("/credentials")
async def list_mqtt_credentials(user: dict = Depends(require_operator)):
    """List all generators with their MQTT credential status."""
    generators = await db.generators.find(
        {},
        {"_id": 0, "id": 1, "name": 1, "serial_number": 1,
         "mqtt_username": 1, "mqtt_created_at": 1}
    ).to_list(1000)

    return [{
        "generator_id": g["id"],
        "name": g.get("name", ""),
        "serial_number": g.get("serial_number", ""),
        "has_credentials": bool(g.get("mqtt_username")),
        "mqtt_username": g.get("mqtt_username", ""),
        "created_at": g.get("mqtt_created_at", ""),
    } for g in generators]


@router.post("/credentials/{generator_id}/generate")
async def generate_mqtt_credentials(generator_id: str, user: dict = Depends(require_operator)):
    """Generate unique MQTT username + password for a gateway. Password is shown only once."""
    gen = await db.generators.find_one({"id": generator_id}, {"_id": 0})
    if not gen:
        raise HTTPException(status_code=404, detail="Generator nicht gefunden")

    serial = gen.get("serial_number", generator_id[:12])
    username = "gw_" + serial.lower().replace(" ", "_").replace("-", "_")
    password = secrets.token_urlsafe(16)
    pw_hash = _mosquitto_hash(password)

    await db.generators.update_one(
        {"id": generator_id},
        {"$set": {
            "mqtt_username": username,
            "mqtt_password_hash": pw_hash,
            "mqtt_created_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    passwd_ok = await _regenerate_passwd_file()

    return {
        "username": username,
        "password": password,
        "generator_name": gen.get("name", ""),
        "serial_number": gen.get("serial_number", ""),
        "passwd_file_updated": passwd_ok,
        "message": "Zugangsdaten generiert. Passwort wird nur einmal angezeigt!",
    }


@router.delete("/credentials/{generator_id}")
async def revoke_mqtt_credentials(generator_id: str, user: dict = Depends(require_operator)):
    """Revoke MQTT credentials for a gateway."""
    gen = await db.generators.find_one({"id": generator_id}, {"_id": 0})
    if not gen:
        raise HTTPException(status_code=404, detail="Generator nicht gefunden")

    await db.generators.update_one(
        {"id": generator_id},
        {"$unset": {"mqtt_username": "", "mqtt_password_hash": "", "mqtt_created_at": ""}}
    )

    await _regenerate_passwd_file()
    return {"message": "MQTT-Zugangsdaten widerrufen"}


# ============== Device MQTT Credentials (Stromerzeuger/Lichtmast) ==============

@router.post("/device-credentials/{device_id}/generate")
async def generate_device_mqtt_credentials(device_id: str, user: dict = Depends(require_operator)):
    """Generate unique MQTT credentials for a device (Stromerzeuger/Lichtmast). Password shown only once."""
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Geraet nicht gefunden")

    serial = device.get("serial_number", device_id[:12])
    username = "gw_" + serial.lower().replace(" ", "_").replace("-", "_")
    password = secrets.token_urlsafe(16)
    pw_hash = _mosquitto_hash(password)

    await db.devices.update_one(
        {"id": device_id},
        {"$set": {
            "mqtt_username": username,
            "mqtt_password_hash": pw_hash,
            "mqtt_created_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    await _regenerate_passwd_file()

    return {
        "username": username,
        "password": password,
        "device_name": device.get("serial_number", ""),
        "message": "Zugangsdaten generiert. Passwort wird nur einmal angezeigt!",
    }


@router.get("/device-credentials/{device_id}")
async def get_device_mqtt_credentials(device_id: str, user: dict = Depends(require_operator)):
    """Get MQTT credential info for a device (without password)."""
    device = await db.devices.find_one(
        {"id": device_id},
        {"_id": 0, "mqtt_username": 1, "mqtt_created_at": 1}
    )
    if not device:
        raise HTTPException(status_code=404, detail="Geraet nicht gefunden")

    return {
        "has_credentials": bool(device.get("mqtt_username")),
        "mqtt_username": device.get("mqtt_username", ""),
        "created_at": device.get("mqtt_created_at", ""),
    }


@router.delete("/device-credentials/{device_id}")
async def revoke_device_mqtt_credentials(device_id: str, user: dict = Depends(require_operator)):
    """Revoke MQTT credentials for a device."""
    await db.devices.update_one(
        {"id": device_id},
        {"$unset": {"mqtt_username": "", "mqtt_password_hash": "", "mqtt_created_at": ""}}
    )
    await _regenerate_passwd_file()
    return {"message": "MQTT-Zugangsdaten widerrufen"}