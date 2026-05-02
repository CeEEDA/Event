"""
Notfall-Skript: Admin-Passwort zuruecksetzen direkt in MongoDB.
Nutzung auf dem Windows Server:
    cd C:\\eventenergie
    venv\\Scripts\\activate.bat
    python reset_admin.py
"""
import os
import sys
import asyncio
from pathlib import Path

# .env laden
from dotenv import load_dotenv
env_path = Path(__file__).parent / "backend" / ".env"
if not env_path.exists():
    print(f"FEHLER: {env_path} nicht gefunden")
    sys.exit(1)
load_dotenv(env_path)

import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
if not MONGO_URL or not DB_NAME:
    print("FEHLER: MONGO_URL oder DB_NAME nicht gesetzt in backend/.env")
    sys.exit(1)


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    ADMIN_EMAIL = "christian.ecker@eventenergie-deutschland.de"
    NEW_PASSWORD = "Notfall2026!Neu"  # <-- bei Bedarf hier aendern

    user = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
    if not user:
        print(f"Kein User mit email={ADMIN_EMAIL}")
        print("\nAlle Admin-Accounts in der DB:")
        admins = await db.users.find({"role": "admin"}, {"_id": 0, "email": 1, "name": 1, "is_active": 1}).to_list(50)
        for a in admins:
            print(f"  {a.get('email')} | name={a.get('name')} | aktiv={a.get('is_active')}")
        return

    print(f"\nUser gefunden:")
    print(f"  Name:    {user.get('name')}")
    print(f"  Email:   {user.get('email')}")
    print(f"  Rolle:   {user.get('role')}")
    print(f"  Aktiv:   {user.get('is_active')}")
    print(f"  Hash:    {user.get('password_hash', '')[:30]}...")

    new_hash = bcrypt.hashpw(NEW_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    result = await db.users.update_one(
        {"email": ADMIN_EMAIL},
        {"$set": {
            "password_hash": new_hash,
            "is_active": True,
            "role": "admin",
        }}
    )
    print(f"\nUpdate: matched={result.matched_count}, modified={result.modified_count}")
    print(f"\nNeues Passwort: {NEW_PASSWORD}")
    print("Bitte aendere es nach dem Login sofort in der UI.")


if __name__ == "__main__":
    asyncio.run(main())
