"""
Test der MQTT Auto-Learn Logik fuer DSE890 GPS-Routing.

Verifiziert die 3 Match-Pfade in mqtt_service._process_message:
  1) _mappings_cache (gateway_mapping prefix)
  2) _generators_cache (dse_mqtt_topic_prefix)
  3) _devices_cache (dse_module_uid match im topic)

Plus: Verifiziert dass _process_gateway_gps GPS-Pakete via gelerntem
dse_gateway_uid an Devices/Generators routet (DSE890-Spezialfall:
GPS-Payload-Key = Gateway-UID, nicht Module-UID).

Kein dotenv, keine echte MongoDB, keine echte FastAPI-App. Reine
Unit-Tests gegen ein In-Memory-Fake der Motor-Collections.
"""
import asyncio
import re
from datetime import datetime, timezone
import sys
import types


# --- Stub paho.mqtt.client damit Import von mqtt_service kein paho braucht ---
if "paho" not in sys.modules:
    paho_pkg = types.ModuleType("paho")
    paho_mqtt = types.ModuleType("paho.mqtt")
    paho_client = types.ModuleType("paho.mqtt.client")

    class _DummyClient:
        def __init__(self, *a, **kw):
            pass

        def subscribe(self, *a, **kw):
            pass

    paho_client.Client = _DummyClient
    paho_pkg.mqtt = paho_mqtt
    paho_mqtt.client = paho_client
    sys.modules["paho"] = paho_pkg
    sys.modules["paho.mqtt"] = paho_mqtt
    sys.modules["paho.mqtt.client"] = paho_client


# --- Fake Motor Collection / DB --------------------------------------------
class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length):
        return self._docs[:length] if length else self._docs


class FakeCollection:
    def __init__(self):
        self.docs = []
        self.updates = []  # list of (filter, update)

    def _match_one(self, doc, filt):
        if not filt:
            return True
        if "$or" in filt:
            return any(self._match_one(doc, sub) for sub in filt["$or"])
        for k, v in filt.items():
            if isinstance(v, dict):
                if "$regex" in v:
                    pat = v["$regex"]
                    flags = re.IGNORECASE if "i" in v.get("$options", "") else 0
                    if not re.match(pat, str(doc.get(k, "")), flags):
                        return False
                elif "$exists" in v:
                    exists = k in doc and doc.get(k) not in (None, "")
                    if exists != v["$exists"]:
                        return False
                    if "$ne" in v and doc.get(k) == v["$ne"]:
                        return False
                elif "$ne" in v:
                    if doc.get(k) == v["$ne"]:
                        return False
                else:
                    continue
            else:
                if doc.get(k) != v:
                    return False
        return True

    def find(self, filt=None, projection=None):
        return FakeCursor([d for d in self.docs if self._match_one(d, filt)])

    async def find_one(self, filt=None, projection=None):
        return self.docs[0] if self.docs else None

    async def update_one(self, filt, update, upsert=False):
        # Apply $set in-memory damit nachfolgende Reads den neuen Wert sehen
        self.updates.append((filt, update))
        target_id = filt.get("id")
        matched = 0
        if target_id and "$set" in update:
            for d in self.docs:
                if d.get("id") == target_id:
                    d.update(update["$set"])
                    matched = 1
                    break
        else:
            # Generischer Match via _match_one
            for d in self.docs:
                if self._match_one(d, filt):
                    if "$set" in update:
                        d.update(update["$set"])
                    matched = 1
                    break
        if matched == 0 and upsert:
            new_doc = {}
            for k, v in filt.items():
                if not isinstance(v, dict):
                    new_doc[k] = v
            if "$set" in update:
                new_doc.update(update["$set"])
            if "$setOnInsert" in update:
                new_doc.update(update["$setOnInsert"])
            self.docs.append(new_doc)
            return types.SimpleNamespace(matched_count=0, modified_count=0, upserted_id=new_doc.get("id"))
        return types.SimpleNamespace(matched_count=matched, modified_count=matched)

    async def insert_one(self, doc):
        self.docs.append(doc)
        return types.SimpleNamespace(inserted_id=doc.get("id"))

    async def count_documents(self, filt):
        return len(self.docs)

    async def delete_many(self, filt):
        return types.SimpleNamespace(deleted_count=0)


class FakeDB:
    def __init__(self):
        self._collections = {}
        # Vorab-bekannte Collections
        for name in ("devices", "generators", "mqtt_gateway_mappings",
                     "mqtt_gps_log", "mqtt_config", "mqtt_raw_messages",
                     "generator_telemetry", "device_telemetry"):
            self._collections[name] = FakeCollection()

    def __getattr__(self, name):
        # Auto-create unknown collections (z.B. generator_telemetry)
        if name.startswith("_"):
            raise AttributeError(name)
        coll = self.__dict__.setdefault("_collections", {}).setdefault(name, FakeCollection())
        return coll

    def __getitem__(self, name):
        return getattr(self, name)

    # explizite Properties damit Zugriff via attr nicht ueber __getattr__
    # geht und damit IDEs nicht meckern
    @property
    def devices(self):
        return self._collections["devices"]

    @property
    def generators(self):
        return self._collections["generators"]

    @property
    def mqtt_gateway_mappings(self):
        return self._collections["mqtt_gateway_mappings"]

    @property
    def mqtt_gps_log(self):
        return self._collections["mqtt_gps_log"]

    @property
    def mqtt_config(self):
        return self._collections["mqtt_config"]

    @property
    def mqtt_raw_messages(self):
        return self._collections["mqtt_raw_messages"]


# --- Fake MQTT message -----------------------------------------------------
class FakeMsg:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload.encode() if isinstance(payload, str) else payload


# --- Import mqtt_service NACH dem paho-Stub --------------------------------
sys.path.insert(0, "/app/backend")
import mqtt_service  # noqa: E402


def _reset_state(db):
    """Reset caches damit jeder Test isoliert ist."""
    mqtt_service._db = db
    mqtt_service._mappings_cache = None
    mqtt_service._mappings_cache_ts = 0
    mqtt_service._generators_cache = None
    mqtt_service._generators_cache_ts = 0
    mqtt_service._devices_cache = None
    mqtt_service._devices_cache_ts = 0


# ===========================================================================
# TESTS
# ===========================================================================

def test_path1_mapping_prefix_auto_learns_gateway_uid():
    """Pfad 1: Topic matched ueber mqtt_gateway_mappings (topic_prefix).
    Auto-Learn muss die Gateway-UID auf den verlinkten Generator schreiben."""
    db = FakeDB()
    db.mqtt_gateway_mappings.docs.append({
        "topic_prefix": "eventenergie/35072/",
        "generator_id": "gen-001",
    })
    db.generators.docs.append({"id": "gen-001"})
    _reset_state(db)

    msg = FakeMsg(
        "eventenergie/35072/1912C4E76883D4B/6D2B5CD695/status",
        '{"foo": "bar"}',
    )
    asyncio.run(mqtt_service._process_message(msg))

    # Verifiziere: dse_gateway_uid wurde auf gen-001 gelernt
    gen = next(g for g in db.generators.docs if g["id"] == "gen-001")
    assert gen.get("dse_gateway_uid") == "1912C4E76883D4B", \
        f"Gateway-UID nicht gelernt: {gen}"


def test_path2_generator_prefix_auto_learns_gateway_uid():
    """Pfad 2: Topic matched ueber generators.dse_mqtt_topic_prefix."""
    db = FakeDB()
    db.generators.docs.append({
        "id": "gen-002",
        "dse_mqtt_topic_prefix": "eventenergie/35073/",
    })
    _reset_state(db)

    msg = FakeMsg(
        "eventenergie/35073/AABBCCDDEEFF1122/6D2B5CD777/telemetry",
        '{"x": 1}',
    )
    asyncio.run(mqtt_service._process_message(msg))

    gen = next(g for g in db.generators.docs if g["id"] == "gen-002")
    assert gen.get("dse_gateway_uid") == "AABBCCDDEEFF1122", \
        f"Gateway-UID nicht gelernt: {gen}"


def test_path3_device_module_uid_auto_learns_gateway_uid_segment_before():
    """Pfad 3: Topic matched via Module-UID. Das Segment direkt VOR der
    Module-UID muss als Gateway-UID auf das Device gespeichert werden."""
    db = FakeDB()
    db.devices.docs.append({
        "id": "dev-aaa",
        "dse_module_uid": "6D2B5CD695",
    })
    _reset_state(db)

    msg = FakeMsg(
        "eventenergie/35074/1912C4E76883D4B/6D2B5CD695/telemetry",
        '{"k": "v"}',
    )
    asyncio.run(mqtt_service._process_message(msg))

    dev = next(d for d in db.devices.docs if d["id"] == "dev-aaa")
    assert dev.get("dse_gateway_uid") == "1912C4E76883D4B", \
        f"Gateway-UID nicht gelernt: {dev}"


def test_gateway_gps_routes_via_learned_gateway_uid_to_device():
    """Kern-Fix: DSE890 schickt GPS mit {GATEWAY_UID: {LAT, LON}}.
    Nach Auto-Learn muss dieses Paket korrekt auf das Device geroutet werden,
    auch wenn die Module-UID NICHT im Payload steht."""
    db = FakeDB()
    db.devices.docs.append({
        "id": "dev-bbb",
        "dse_module_uid": "6D2B5CD695",
        "dse_gateway_uid": "1912C4E76883D4B",  # vorher gelernt
    })
    _reset_state(db)

    # Cache initialisieren via beliebige Message
    mqtt_service._devices_cache = db.devices.docs
    mqtt_service._devices_cache_ts = 1e12  # nicht refreshen
    mqtt_service._generators_cache = []
    mqtt_service._generators_cache_ts = 1e12
    mqtt_service._mappings_cache = []
    mqtt_service._mappings_cache_ts = 1e12

    topic = "eventenergie/35074/1912C4E76883D4B/gps"
    parsed = {"1912C4E76883D4B": {"LAT": 52.5, "LON": 13.4}}
    asyncio.run(mqtt_service._process_gateway_gps(
        topic, '{"1912C4E76883D4B":{"LAT":52.5,"LON":13.4}}',
        parsed, datetime.now(timezone.utc).isoformat()
    ))

    # Device sollte ge-updated worden sein
    dev = next(d for d in db.devices.docs if d["id"] == "dev-bbb")
    assert dev.get("latitude") == 52.5, f"GPS nicht gesetzt: {dev}"
    assert dev.get("longitude") == 13.4, f"GPS nicht gesetzt: {dev}"


def test_gateway_gps_routes_via_module_uid_payload_key():
    """Klassischer Fall: Payload-Key = Module-UID. Muss weiterhin matchen."""
    db = FakeDB()
    db.devices.docs.append({
        "id": "dev-ccc",
        "dse_module_uid": "6D2B5CD695",
    })
    _reset_state(db)

    mqtt_service._devices_cache = db.devices.docs
    mqtt_service._devices_cache_ts = 1e12
    mqtt_service._generators_cache = []
    mqtt_service._generators_cache_ts = 1e12
    mqtt_service._mappings_cache = []
    mqtt_service._mappings_cache_ts = 1e12

    topic = "eventenergie/35074/1912C4E76883D4B/gps"
    parsed = {"6D2B5CD695": {"LAT": 48.1, "LON": 11.5}}
    asyncio.run(mqtt_service._process_gateway_gps(
        topic, '{"6D2B5CD695":{"LAT":48.1,"LON":11.5}}',
        parsed, datetime.now(timezone.utc).isoformat()
    ))

    dev = next(d for d in db.devices.docs if d["id"] == "dev-ccc")
    assert dev.get("latitude") == 48.1, f"GPS Module-UID Match fehlgeschlagen: {dev}"


def test_gateway_gps_tertiary_match_via_topic_hex_uid():
    """Fallback: Flat-Payload ohne UID-Wrapper. Match muss via erstes
    Hex-Segment im Topic + gelerntem dse_gateway_uid funktionieren."""
    db = FakeDB()
    db.devices.docs.append({
        "id": "dev-ddd",
        "dse_module_uid": "6D2B5CD999",
        "dse_gateway_uid": "BBCCDDEEFF001122",
    })
    _reset_state(db)

    mqtt_service._devices_cache = db.devices.docs
    mqtt_service._devices_cache_ts = 1e12
    mqtt_service._generators_cache = []
    mqtt_service._generators_cache_ts = 1e12
    mqtt_service._mappings_cache = []
    mqtt_service._mappings_cache_ts = 1e12

    topic = "eventenergie/35074/BBCCDDEEFF001122/gps"
    parsed = {"LAT": 50.0, "LON": 8.0}  # flach, kein UID-Wrapper
    asyncio.run(mqtt_service._process_gateway_gps(
        topic, '{"LAT":50.0,"LON":8.0}',
        parsed, datetime.now(timezone.utc).isoformat()
    ))

    dev = next(d for d in db.devices.docs if d["id"] == "dev-ddd")
    assert dev.get("latitude") == 50.0, f"Tertiary-Match fehlgeschlagen: {dev}"


def test_dse890_5segment_bridge_persists_pairing():
    """Echte DSE890 Bridge: Telemetrie-Topic mit 5 Segmenten
       eventenergie/<anlage>/<gateway_uid>/<module_uid>/<sub>
    persistiert das Gateway-UID <-> Module-UID Pairing sofort.
    GPS-Topic mit gleicher Gateway-UID matcht dann via Pairing-Tabelle
    auf das richtige Device, OHNE Cache oder Anlage-Index zu brauchen.
    """
    db = FakeDB()
    db.devices.docs.append({
        "id": "dev-dse890-1",
        "dse_module_uid": "6D2B5CDE5F",
    })
    _reset_state(db)
    mqtt_service._anlage_index.clear()
    mqtt_service._anlage_pair_persist.clear()

    # SCHRITT 1: DSE890 Telemetrie-Topic (5 Segmente) kommt rein.
    # Bridge wird sofort persistiert.
    tele_msg = FakeMsg(
        "eventenergie/35072/1912C50541E3D25/6D2B5CDE5F/engine",
        '{"6D2B5CDE5F":{"P004":{"R000":1}}}',
    )
    asyncio.run(mqtt_service._process_message(tele_msg))

    pair = next(iter(db._collections["mqtt_anlage_pairing"].docs), None)
    assert pair is not None, "Pairing nicht persistiert!"
    assert pair["gateway_uid"] == "1912C50541E3D25"
    assert pair["module_uid"] == "6D2B5CDE5F"

    # SCHRITT 2: GPS kommt mit dieser Gateway-UID.
    # Tertiaer-B Match via Pairing-Tabelle -> Device wird gefunden.
    gps_msg = FakeMsg(
        "eventenergie/35072/1912C50541E3D25/gps",
        '{"1912C50541E3D25":{"lat":50.372563,"lon":6.930362}}',
    )
    asyncio.run(mqtt_service._process_message(gps_msg))

    dev = next(d for d in db.devices.docs if d["id"] == "dev-dse890-1")
    assert dev.get("latitude") == 50.372563, f"GPS nicht via Bridge angewendet: {dev}"
    assert dev.get("dse_gateway_uid") == "1912C50541E3D25", f"dse_gateway_uid nicht gespeichert: {dev}"


def test_anlage_pairing_dse890_bridge():
    """Kern-Fix: DSE890 Bruecke ueber Anlage-ID.
    Szenario: 
      - Device im Portal hat dse_module_uid='6D2B5CDE5F' (Bediendisplay).
      - Telemetrie kommt unter 'eventenergie/35072/6D2B5CDE5F/engine'.
      - GPS kommt unter 'eventenergie/35072/1922A5D409E1601/gps' mit
        payload {"1922A5D409E1601":{"lat":...}}.
    Erwartung: Anlage-Pairing erkennt dass beide UIDs zur Anlage 35072
    gehoeren -> Gateway-UID wird auf Device gespeichert UND GPS angewendet.
    """
    db = FakeDB()
    db.devices.docs.append({
        "id": "dev-pair-1",
        "dse_module_uid": "6D2B5CDE5F",
        # dse_gateway_uid NICHT gesetzt -> muss erlernt werden
    })
    _reset_state(db)
    # Index reset
    mqtt_service._anlage_index.clear()
    mqtt_service._anlage_pair_persist.clear()

    # SCHRITT 1: Telemetrie-Topic -> lernt mod-UID in Anlage 35072
    tele_msg = FakeMsg(
        "eventenergie/35072/6D2B5CDE5F/engine",
        '{"6D2B5CDE5F":{"P004":{"R000":1}}}',
    )
    asyncio.run(mqtt_service._process_message(tele_msg))

    # SCHRITT 2: GPS-Topic mit Gateway-UID kommt rein
    gps_msg = FakeMsg(
        "eventenergie/35072/1922A5D409E1601/gps",
        '{"1922A5D409E1601":{"lat":50.456767,"lon":7.425265}}',
    )
    asyncio.run(mqtt_service._process_message(gps_msg))

    # Verifiziere: Device hat jetzt sowohl GPS als auch gelernte Gateway-UID
    dev = next(d for d in db.devices.docs if d["id"] == "dev-pair-1")
    assert dev.get("dse_gateway_uid") == "1922A5D409E1601", \
        f"Gateway-UID nicht ueber Anlage-Pairing gelernt: {dev}"
    assert dev.get("latitude") == 50.456767, \
        f"GPS nicht angewendet trotz Pairing: {dev}"
    assert dev.get("longitude") == 7.425265, \
        f"GPS nicht angewendet trotz Pairing: {dev}"

    # Verifiziere: Pairing wurde persistiert
    pairings = db._collections.get("mqtt_anlage_pairing", FakeCollection()).docs
    assert len(pairings) == 1, f"Pairing nicht persistiert: {pairings}"
    p = pairings[0]
    assert p["anlage_id"] == "35072"
    assert p["gateway_uid"] == "1922A5D409E1601"
    assert p["module_uid"] == "6D2B5CDE5F"


def test_anlage_pairing_second_gps_uses_persisted_link():
    """Zweites GPS-Telegramm an dasselbe Setup sollte ohne erneutes
    Pairing (= via tertiary match auf dse_gateway_uid) routen."""
    db = FakeDB()
    db.devices.docs.append({
        "id": "dev-pair-2",
        "dse_module_uid": "AABBCCDDEE",
        "dse_gateway_uid": "1234567890ABCDE",  # bereits gepaart
    })
    _reset_state(db)
    mqtt_service._anlage_index.clear()
    mqtt_service._anlage_pair_persist.clear()

    # Direkt GPS-Topic (ohne vorherige Telemetrie)
    gps_msg = FakeMsg(
        "eventenergie/99999/1234567890ABCDE/gps",
        '{"1234567890ABCDE":{"LAT":48.1,"LON":11.5}}',
    )
    asyncio.run(mqtt_service._process_message(gps_msg))

    dev = next(d for d in db.devices.docs if d["id"] == "dev-pair-2")
    assert dev.get("latitude") == 48.1, f"GPS nicht via gelernter Gateway-UID: {dev}"


def test_no_match_logs_rejected():
    """Unbekannte Module-UID darf KEIN Device updaten und muss als rejected loggen."""
    db = FakeDB()
    db.devices.docs.append({
        "id": "dev-eee",
        "dse_module_uid": "AAAAAAAAAA",
    })
    _reset_state(db)

    mqtt_service._devices_cache = db.devices.docs
    mqtt_service._devices_cache_ts = 1e12
    mqtt_service._generators_cache = []
    mqtt_service._generators_cache_ts = 1e12
    mqtt_service._mappings_cache = []
    mqtt_service._mappings_cache_ts = 1e12

    topic = "eventenergie/35074/UNKNOWN_GW/gps"
    parsed = {"FFFFFFFFFFFF": {"LAT": 51.0, "LON": 9.0}}
    asyncio.run(mqtt_service._process_gateway_gps(
        topic, '{"FFFFFFFFFFFF":{"LAT":51.0,"LON":9.0}}',
        parsed, datetime.now(timezone.utc).isoformat()
    ))

    dev = next(d for d in db.devices.docs if d["id"] == "dev-eee")
    assert dev.get("latitude") is None, f"Device duerfte NICHT geupdated werden: {dev}"
    # Log muss rejected_no_module_match enthalten
    routes = [d["route"] for d in db.mqtt_gps_log.docs]
    assert any("rejected" in r for r in routes), f"Kein reject-Log: {routes}"


if __name__ == "__main__":
    # Ohne pytest aufrufen: alle Tests laufen lassen
    import traceback
    tests = [
        test_path1_mapping_prefix_auto_learns_gateway_uid,
        test_path2_generator_prefix_auto_learns_gateway_uid,
        test_path3_device_module_uid_auto_learns_gateway_uid_segment_before,
        test_gateway_gps_routes_via_learned_gateway_uid_to_device,
        test_gateway_gps_routes_via_module_uid_payload_key,
        test_gateway_gps_tertiary_match_via_topic_hex_uid,
        test_dse890_5segment_bridge_persists_pairing,
        test_anlage_pairing_dse890_bridge,
        test_anlage_pairing_second_gps_uses_persisted_link,
        test_no_match_logs_rejected,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL: {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
