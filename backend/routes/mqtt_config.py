from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging
import asyncio

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

# DSE Gencomm Page 3, Offset 0 - Control Key values
DSE_COMMANDS = {
    "start": {"value": 6, "label": "Manueller Start"},
    "stop": {"value": 1, "label": "Stop"},
    "auto_on": {"value": 2, "label": "Automatikmodus EIN"},
    "auto_off": {"value": 3, "label": "Manueller Modus (Auto AUS)"},
}


class GeneratorCommand(BaseModel):
    command: str  # start, stop, auto_on, auto_off


@router.post("/control/{generator_id}")
async def send_generator_command(generator_id: str, cmd: GeneratorCommand, user: dict = Depends(require_operator)):
    """Send a control command to a generator via MQTT."""
    from mqtt_service import publish_command

    if cmd.command not in DSE_COMMANDS:
        raise HTTPException(status_code=400, detail=f"Unbekannter Befehl: {cmd.command}. Erlaubt: {list(DSE_COMMANDS.keys())}")

    # Find the generator
    gen = await db.generators.find_one({"id": generator_id}, {"_id": 0})
    if not gen:
        raise HTTPException(status_code=404, detail="Generator nicht gefunden")

    # Find the gateway mapping for this generator
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
        # Extract UID from topic like /32788/6D2B5CDE5F/engine -> 6D2B5CDE5F
        parts = latest_msg["topic"].strip("/").split("/")
        uid = parts[1] if len(parts) >= 2 else ""
        control_topic = f"{prefix}/{uid}/control"
    else:
        raise HTTPException(status_code=400, detail="Kein aktives Gerät gefunden. Gateway muss zuerst Daten senden.")

    dse_cmd = DSE_COMMANDS[cmd.command]
    # DSE890 expects JSON with Page/Register/Value format
    import json
    payload = json.dumps({uid: {"P003": {"R000": dse_cmd["value"]}}})

    try:
        publish_command(control_topic, payload)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Log the control action
    log_entry = {
        "id": str(uuid.uuid4()),
        "generator_id": generator_id,
        "generator_name": gen.get("name", ""),
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
        "generator": gen.get("name", ""),
    }


@router.get("/control/{generator_id}/log")
async def get_control_log(generator_id: str, user: dict = Depends(require_operator)):
    """Get the control command history for a generator."""
    logs = await db.generator_control_log.find(
        {"generator_id": generator_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(50)
    return logs