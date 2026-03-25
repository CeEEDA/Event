"""
Einmal-Script: Kirmeskiste 009 mit alter device_id wiederherstellen.
Ausfuehren auf dem Server nach git pull:
    cd C:\eventenergie\backend
    python restore_kirmeskiste_009.py
"""
import pymongo
import os
import secrets
import hashlib
import hmac

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "eventenergie")

OLD_DEVICE_ID = "9a0c96cc-3e61-4a1a-b92a-557173d07992"

# Meter-IDs die der Pi sendet (von Kirmeskiste_001 kopiert)
METER_IDS = [
    "4b5ad9f6-e5f2-41ca-a799-d63c98037323",
    "84ba598f-bc68-449b-b6ef-8bc86378b457",
    "0e484175-d066-46ea-857d-ed8719f53dae",
]

def generate_key():
    """Generate a device key and its hash."""
    plain_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
    return plain_key, key_hash

def main():
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]

    # Prüfe ob Device schon existiert
    existing = db.devices.find_one({"id": OLD_DEVICE_ID})
    if existing:
        print(f"Device {OLD_DEVICE_ID} existiert bereits: {existing.get('serial_number')}")
        print("Nichts zu tun.")
        return

    # Neuen Key generieren
    plain_key, key_hash = generate_key()

    # Device anlegen
    from datetime import datetime, timezone
    device_doc = {
        "id": OLD_DEVICE_ID,
        "serial_number": "Kirmeskiste 009",
        "device_type": "kirmeskiste",
        "model": "Kirmeskiste",
        "controller": "",
        "user_field": "Kirmeskiste 009",
        "status": "aktiv",
        "device_key_hash": key_hash,
        "notes": "Wiederhergestellt - alte device_id vom Pi",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.devices.insert_one(device_doc)
    print(f"\n=== Kirmeskiste 009 wiederhergestellt ===")
    print(f"Device-ID: {OLD_DEVICE_ID}")
    print(f"Serial:    Kirmeskiste 009")

    # Meter zuordnen (falls sie noch bei einem anderen Device sind, umhaengen)
    for meter_id in METER_IDS:
        meter = db.emu_meters.find_one({"id": meter_id})
        if meter:
            old_dev = meter.get("device_id", "?")
            db.emu_meters.update_one(
                {"id": meter_id},
                {"$set": {"device_id": OLD_DEVICE_ID}}
            )
            print(f"Meter {meter.get('meter_name','?')} ({meter_id[:12]}...) -> umgehaengt von {old_dev[:12]}...")
        else:
            # Auto-register meter
            meter_doc = {
                "id": meter_id,
                "device_id": OLD_DEVICE_ID,
                "meter_name": f"Auto-registriert (Kirmeskiste 009)",
                "meter_ip": "",
                "description": "Wiederhergestellt",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            db.emu_meters.insert_one(meter_doc)
            print(f"Meter {meter_id[:12]}... -> neu angelegt")

    print(f"\n{'='*50}")
    print(f"NEUER DEVICE KEY (auf dem Pi eintragen!):")
    print(f"  {plain_key}")
    print(f"{'='*50}")
    print(f"\nAuf dem Pi in der config.json aendern:")
    print(f'  "device_key": "{plain_key}"')
    print(f"\nDanach Pi neustarten oder sync-service restarten.")

if __name__ == "__main__":
    main()
