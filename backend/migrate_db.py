"""
Eventenergie Portal - Datenbank-Migration
==========================================
Fuehrt alle notwendigen Schema-Aenderungen an der
bestehenden MongoDB durch.

Aenderungen seit 2026-03-19 18:00:
  1. order_assets: Neues Feld "status" (placed/dismantled)
  2. maintenance_entries: Neues Feld "attachments" (Metadaten fuer PDFs)
  3. fuel_receipts: Sicherstellung dass alle Belege beleg_nr haben

Ausfuehren:
  python migrate_db.py

Sicher: Bestehende Daten werden nicht geloescht oder veraendert,
nur neue Felder hinzugefuegt wo sie fehlen.
"""

import os
import sys
from datetime import datetime, timezone

# .env laden
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "")
DB_NAME = os.environ.get("DB_NAME", "eventenergie_db")

if not MONGO_URL:
    print("FEHLER: MONGO_URL nicht gesetzt!")
    print("Bitte .env Datei pruefen oder Umgebungsvariable setzen.")
    sys.exit(1)


def migrate():
    print("=" * 50)
    print("  Datenbank-Migration")
    print("=" * 50)
    print(f"  DB: {DB_NAME}")
    print(f"  Zeitpunkt: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print()

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    # ====== 1. order_assets: status Feld ======
    print("[1/4] order_assets: Status-Feld hinzufuegen...")
    result = db.order_assets.update_many(
        {"status": {"$exists": False}},
        {"$set": {"status": "placed"}}
    )
    print(f"      {result.modified_count} Assets aktualisiert (status='placed')")

    # ====== 2. maintenance_entries: attachments Feld ======
    print("[2/4] maintenance_entries: Attachments-Feld hinzufuegen...")
    # Fuer bestehende Eintraege mit Bildern: attachments Array aus images erstellen
    entries_without_att = db.maintenance_entries.find({
        "attachments": {"$exists": False},
        "images": {"$exists": True, "$ne": []}
    })
    migrated_entries = 0
    for entry in entries_without_att:
        # Bestehende images sind alle Bilder (vor dem PDF-Feature)
        attachments = []
        for img_id in entry.get("images", []):
            # Metadaten aus maintenance_images holen
            img_doc = db.maintenance_images.find_one({"id": img_id})
            if img_doc:
                attachments.append({
                    "id": img_id,
                    "filename": img_doc.get("filename", "bild.jpg"),
                    "content_type": img_doc.get("content_type", "image/jpeg"),
                    "size": img_doc.get("size", 0),
                })
            else:
                # Fallback wenn kein Metadaten-Dokument gefunden
                attachments.append({
                    "id": img_id,
                    "filename": "bild.jpg",
                    "content_type": "image/jpeg",
                    "size": 0,
                })
        db.maintenance_entries.update_one(
            {"id": entry["id"]},
            {"$set": {"attachments": attachments}}
        )
        migrated_entries += 1
    print(f"      {migrated_entries} Eintraege mit Attachments aktualisiert")

    # Eintraege ohne Bilder: leeres attachments Array
    result = db.maintenance_entries.update_many(
        {"attachments": {"$exists": False}},
        {"$set": {"attachments": []}}
    )
    print(f"      {result.modified_count} Eintraege mit leerem Attachments-Array")

    # ====== 3. fuel_receipts: beleg_nr sicherstellen ======
    print("[3/4] fuel_receipts: Belegnummern pruefen...")
    missing_nr = db.fuel_receipts.count_documents({
        "$or": [
            {"beleg_nr": {"$exists": False}},
            {"beleg_nr": None},
            {"beleg_nr": ""},
        ]
    })
    if missing_nr > 0:
        # Hoechste bestehende Nummer finden
        pipeline = [
            {"$match": {"beleg_nr": {"$regex": "^X\\d+"}}},
            {"$addFields": {"nr_num": {"$toInt": {"$substr": ["$beleg_nr", 1, -1]}}}},
            {"$sort": {"nr_num": -1}},
            {"$limit": 1}
        ]
        result = list(db.fuel_receipts.aggregate(pipeline))
        next_nr = (result[0]["nr_num"] + 1) if result else 12000

        receipts_to_fix = db.fuel_receipts.find({
            "$or": [
                {"beleg_nr": {"$exists": False}},
                {"beleg_nr": None},
                {"beleg_nr": ""},
            ]
        }).sort("created_at", 1)

        fixed = 0
        for r in receipts_to_fix:
            db.fuel_receipts.update_one(
                {"id": r["id"]},
                {"$set": {"beleg_nr": f"X{next_nr}"}}
            )
            next_nr += 1
            fixed += 1
        print(f"      {fixed} Belege mit fehlender Nummer ergaenzt")
    else:
        print(f"      Alle Belege haben eine Nummer")

    # ====== 4. Indizes sicherstellen ======
    print("[4/4] Indizes aktualisieren...")
    try:
        db.order_assets.create_index([("order_pk", 1), ("status", 1)])
        db.fuel_receipts.create_index([("order_pk", 1)])
        db.fuel_receipts.create_index([("beleg_nr", 1)])
        db.orders_cache.create_index([("pk", 1)], sparse=True)
        db.maintenance_entries.create_index([("plan_id", 1)])
        print("      Indizes erstellt/aktualisiert")
    except Exception as e:
        print(f"      Index-Warnung (nicht kritisch): {e}")

    # ====== Zusammenfassung ======
    print()
    print("=" * 50)
    print("  Migration abgeschlossen!")
    print("=" * 50)
    print()

    # Statistiken
    stats = {
        "Assets": db.order_assets.count_documents({}),
        "Wartungseintraege": db.maintenance_entries.count_documents({}),
        "Tankbelege": db.fuel_receipts.count_documents({}),
        "Auftraege (Cache)": db.orders_cache.count_documents({}),
        "Serviceplaene": db.service_plans.count_documents({}),
    }
    print("  Datenbank-Statistiken:")
    for name, count in stats.items():
        print(f"    {name}: {count}")
    print()

    client.close()


if __name__ == "__main__":
    migrate()
