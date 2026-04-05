import os
import uuid
import json
import logging
import asyncio
import requests
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, BackgroundTasks
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "eventenergie-docs"

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

PREDEFINED_FOLDERS = [
    # Finanzen & Buchhaltung
    {"id": "rechnungseingang", "name": "Rechnungseingang", "icon": "receipt", "color": "emerald"},
    {"id": "rechnungsausgang", "name": "Rechnungsausgang", "icon": "receipt", "color": "emerald"},
    {"id": "banken", "name": "Banken", "icon": "landmark", "color": "emerald"},
    {"id": "datev", "name": "DATEV", "icon": "receipt", "color": "emerald"},
    {"id": "finanzierungen", "name": "Finanzierungen", "icon": "receipt", "color": "emerald"},
    {"id": "gescannte_fibu_fuer_stb", "name": "gescannte Fibu für StB", "icon": "receipt", "color": "emerald"},
    {"id": "kreditkartenabrechnungen", "name": "Kreditkartenabrechnungen", "icon": "receipt", "color": "emerald"},
    {"id": "steuer_bescheide", "name": "Steuer-bescheide", "icon": "receipt", "color": "emerald"},
    {"id": "steuerberater", "name": "Steuerberater", "icon": "receipt", "color": "emerald"},
    {"id": "zahlen_bwa_und_ja", "name": "Zahlen - BWA und JA", "icon": "receipt", "color": "emerald"},
    {"id": "anlagevermoegen", "name": "Anlagevermögen", "icon": "receipt", "color": "emerald"},
    {"id": "stille_reserven", "name": "Stille Reserven", "icon": "receipt", "color": "emerald"},
    # Versicherungen
    {"id": "versicherungen", "name": "Versicherungen", "icon": "shield", "color": "blue"},
    {"id": "kfz_versicherung", "name": "KFZ Versicherung", "icon": "car", "color": "blue"},
    {"id": "betriebshaftpflicht", "name": "Betriebshaftpflicht", "icon": "shield", "color": "blue"},
    {"id": "berufsgenossenschaft_bg_etem", "name": "Berufsgenossenschaft - BG ETEM", "icon": "shield", "color": "blue"},
    {"id": "krankenkassen", "name": "Krankenkassen", "icon": "shield", "color": "blue"},
    # Verträge & Recht
    {"id": "vertraege", "name": "Verträge", "icon": "file-text", "color": "fuchsia"},
    {"id": "vertraege_auftraege_mit_dritten", "name": "Verträge, Aufträge mit Dritten", "icon": "file-text", "color": "fuchsia"},
    {"id": "rahmenvertraege", "name": "Rahmenverträge", "icon": "file-text", "color": "fuchsia"},
    {"id": "mehrjahresvertraege", "name": "Mehrjahresverträge", "icon": "file-text", "color": "fuchsia"},
    {"id": "mobilfunkvertraege", "name": "Mobilfunkverträge", "icon": "file-text", "color": "fuchsia"},
    {"id": "werksvertrag_hb_energy", "name": "Werksvertrag HB Energy", "icon": "file-text", "color": "fuchsia"},
    {"id": "recht_anwalt", "name": "Recht - Anwalt", "icon": "landmark", "color": "purple"},
    {"id": "klagen_rechtsstreit", "name": "Klagen - Rechtsstreit", "icon": "landmark", "color": "purple"},
    {"id": "marken_patent_markenamt", "name": "Marken - eingetragene Marken - Patent-Markenamt", "icon": "landmark", "color": "purple"},
    # Behörden & Institutionen
    {"id": "behoerden", "name": "Behörden", "icon": "landmark", "color": "purple"},
    {"id": "hwk_handwerkskammer", "name": "HWK - Handwerkskammer", "icon": "landmark", "color": "purple"},
    {"id": "konzessionsausweis_swn", "name": "Konzessionsausweis SWN", "icon": "landmark", "color": "purple"},
    {"id": "unbedenklichkeitsbescheinigungen", "name": "Unbedenklichkeitsbescheinigungen", "icon": "landmark", "color": "purple"},
    {"id": "zoll", "name": "Zoll", "icon": "landmark", "color": "purple"},
    {"id": "wirtschaftsbeirat_andernach", "name": "Wirtschaftsbeirat Andernach", "icon": "landmark", "color": "purple"},
    {"id": "aktionsgemeinschaft_andernach", "name": "Aktionsgemeinschaft Andernach", "icon": "landmark", "color": "purple"},
    # Lieferanten & Partner
    {"id": "lieferscheine", "name": "Lieferscheine", "icon": "truck", "color": "orange"},
    {"id": "oel_lieferanten", "name": "Öl-Lieferanten", "icon": "truck", "color": "orange"},
    {"id": "spedition_normann", "name": "Spedition Normann", "icon": "truck", "color": "orange"},
    {"id": "walther_werke", "name": "Walther Werke 10-2025", "icon": "truck", "color": "orange"},
    {"id": "teba", "name": "TEBA", "icon": "truck", "color": "orange"},
    {"id": "kreditreform", "name": "Kreditreform", "icon": "file-text", "color": "orange"},
    {"id": "freelancer", "name": "Freelancer", "icon": "file-text", "color": "orange"},
    # Personal & HR
    {"id": "mitarbeiter", "name": "Mitarbeiter", "icon": "file-text", "color": "amber"},
    {"id": "hr_unterlagen_notarunterlagen", "name": "HR-Unterlagen - Notarunterlagen", "icon": "file-text", "color": "amber"},
    {"id": "unittime_arbeitsueberlassung", "name": "uniTTime - Arbeitsüberlassung", "icon": "file-text", "color": "amber"},
    {"id": "vertriebler_holzem_thomas", "name": "Vertriebler - Holzem, Thomas", "icon": "file-text", "color": "amber"},
    # Projekte & Anfragen
    {"id": "anfragen_projekte", "name": "Anfragen - Projekte", "icon": "file-text", "color": "fuchsia"},
    {"id": "ibau_ausschreibungsplatform", "name": "ibau - Ausschreibungsplatform", "icon": "file-text", "color": "fuchsia"},
    {"id": "kirmes_nachkalkulation", "name": "Kirmes Nachkalkulation", "icon": "file-text", "color": "fuchsia"},
    # Betrieb & Technik
    {"id": "fuhrpark", "name": "Fuhrpark", "icon": "car", "color": "blue"},
    {"id": "inventur_maschinenbestand", "name": "Inventur - Maschinenbestand", "icon": "file-text", "color": "gray"},
    {"id": "it", "name": "IT", "icon": "file-text", "color": "gray"},
    {"id": "funk_betriebsfunk_frequenzen", "name": "Funk - Betriebsfunk - Frequenzen", "icon": "file-text", "color": "gray"},
    {"id": "sicherheit", "name": "Sicherheit", "icon": "shield", "color": "amber"},
    {"id": "pruefberichte", "name": "Prüfberichte", "icon": "file-text", "color": "amber"},
    # Standorte & Unternehmen
    {"id": "halle_andernach", "name": "Halle Andernach", "icon": "landmark", "color": "gray"},
    {"id": "nbr_buero", "name": "NBR - Büro", "icon": "landmark", "color": "gray"},
    {"id": "nbr_flaeche_welcherath", "name": "NBR - Fläche Welcherath", "icon": "landmark", "color": "gray"},
    {"id": "nbr_gmbh", "name": "NBR GmbH", "icon": "landmark", "color": "gray"},
    {"id": "eed_holding", "name": "EED Holding", "icon": "landmark", "color": "gray"},
    # Marketing & Unternehmensdarstellung
    {"id": "marketing_werbung", "name": "Marketing-Werbung", "icon": "file-text", "color": "fuchsia"},
    {"id": "unternehmensvorstellung", "name": "Unternehmensvorstellung", "icon": "file-text", "color": "fuchsia"},
    {"id": "vorlagen", "name": "Vorlagen", "icon": "file-text", "color": "gray"},
    # Veranstaltungen & Sonstiges
    {"id": "veranstaltungen_infos", "name": "Veranstaltungen - Info's", "icon": "file-text", "color": "orange"},
    {"id": "betriebsversammlung_meetingprotokolle", "name": "Betriebsversammlung - Meetingprotokolle", "icon": "file-text", "color": "gray"},
    {"id": "ablage_allgemein", "name": "Ablage - allgemein", "icon": "folder", "color": "gray"},
    {"id": "temporaerer_ordner", "name": "temporärer Ordner", "icon": "folder", "color": "gray"},
    {"id": "sonstiges", "name": "Sonstiges", "icon": "folder", "color": "gray"},
]

storage_key = None

def init_storage():
    global storage_key
    if storage_key:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120
    )
    resp.raise_for_status()
    return resp.json()

def get_object(path: str):
    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


AI_SYSTEM_PROMPT = """Du bist ein Dokumentenerkennungssystem für die Firma Eventenergie Deutschland GmbH & Co. KG.
Die Firma ist ein Elektrotechnik-Meisterbetrieb, spezialisiert auf temporäre Stromversorgung für Events/Kirmes, Photovoltaik-Anlagen, Erzeugungsanlagen, Speicher und Netzanschlüsse.

Analysiere das hochgeladene Dokument und extrahiere alle relevanten Informationen.

Antworte IMMER als valides JSON mit exakt dieser Struktur:
{
  "document_type": "rechnung|versicherung|vertrag|lieferschein|behoerdenschreiben|netzantrag|pruefbericht|protokoll|angebot|sonstiges",
  "suggested_folder": "ORDNER_ID (siehe Branchenregeln unten)",
  "sender": "Name des Absenders/Firma",
  "recipient": "Name des Empfängers (falls erkennbar)",
  "date": "Datum des Dokuments im Format YYYY-MM-DD (falls erkennbar)",
  "subject": "Betreff/Zusammenfassung in 1-2 Sätzen",
  "amount": null oder Betrag als Zahl (z.B. 1234.56),
  "currency": "EUR" oder andere Währung,
  "invoice_number": "Rechnungsnummer (falls vorhanden)",
  "reference": "Verwendungszweck/Referenznummer/Vertragsnummer/Policennummer/MaStR-Nummer/Zählernummer",
  "due_date": "Fälligkeitsdatum YYYY-MM-DD (falls vorhanden)",
  "tax_amount": null oder MwSt-Betrag als Zahl,
  "iban": "IBAN (falls vorhanden)",
  "keywords": ["Stichwort1", "Stichwort2", "..."],
  "full_text": "Kompletter extrahierter Text des Dokuments für die Volltextsuche"
}

=== BRANCHENREGELN (Eventenergie / Elektrotechnik / Energie) ===

PROJEKTDOKUMENTATION → anfragen_projekte:
- Netzanträge, Netzanschlussanträge, Netzverträglichkeitsprüfungen
- Inbetriebsetzungsprotokolle (z.B. Syna E.8, Westnetz, E.ON)
- Einspeisezusagen, Anschlusszusagen, Einspeiseverträge
- Dokumente von Netzbetreibern: Syna, Westnetz, Innogy, E.ON Netz, Avacon, Bayernwerk, Mittelnetz, EnBW, SWN, Stadtwerke, EWR, Pfalzwerke, RWE, Amprion, TenneT, 50Hertz, TransnetBW
- PV-Anlagen Dokumentation, Speicher-Protokolle, Wechselrichter-Datenblätter
- MaStR-Registrierungen (Marktstammdatenregister)
- EEG-Anmeldungen, EEG-Vergütungsanträge
- Technische Anschlussbedingungen (TAB)
- Zähleranträge, Zählersetzungsprotokolle

PRÜFBERICHTE → pruefberichte:
- VDE-Prüfprotokolle, DGUV V3 Prüfungen
- Elektroprüfungen, Isolationsmessungen, Schleifenimpedanzmessungen
- TÜV-Berichte, DEKRA-Prüfungen
- Sachverständigengutachten
- CE-Konformitätserklärungen

RECHNUNGEN:
- Eingangsrechnungen (von Lieferanten/Dienstleistern an Eventenergie) → rechnungseingang
- Ausgangsrechnungen (von Eventenergie an Kunden) → rechnungsausgang
- Erkennbar an: Rechnungsnummer, Nettobetrag, MwSt, Zahlungsziel, IBAN

VERSICHERUNGEN:
- KFZ-Versicherung, Fahrzeugschein, Grüne Karte → kfz_versicherung
- Betriebshaftpflicht, Berufshaftpflicht → betriebshaftpflicht
- Andere Versicherungen (Elektronik, Transport, Ertragsausfall) → versicherungen
- BG ETEM Bescheide, Beiträge → berufsgenossenschaft_bg_etem

VERTRÄGE:
- Mietverträge, Kaufverträge, Dienstleistungsverträge → vertraege
- Rahmenverträge (mit Stammlieferanten) → rahmenvertraege
- Mehrjahresverträge → mehrjahresvertraege
- Mobilfunkverträge (Vodafone, Telekom, O2) → mobilfunkvertraege

LIEFERANTEN:
- Lieferscheine → lieferscheine
- Öl/Kraftstoff-Lieferungen → oel_lieferanten
- Spedition Normann → spedition_normann
- Walther Werke → walther_werke
- TEBA → teba

FINANZEN:
- Bankbelege, Kontoauszüge → banken
- Kreditkartenabrechnungen → kreditkartenabrechnungen
- Steuer-Bescheide, Finanzamt → steuer_bescheide
- Steuerberater-Korrespondenz → steuerberater
- BWA, Jahresabschluss → zahlen_bwa_und_ja
- DATEV-Belege → datev
- Finanzierungsverträge, Darlehen → finanzierungen
- Anlagenverzeichnis → anlagevermoegen

BEHÖRDEN:
- Genehmigungen, Auflagen → behoerden
- HWK-Korrespondenz → hwk_handwerkskammer
- Zoll-Dokumente → zoll
- Unbedenklichkeitsbescheinigungen → unbedenklichkeitsbescheinigungen

PERSONAL:
- Arbeitsverträge, Zeugnisse, Lohnabrechnungen → mitarbeiter
- HR/Notar-Dokumente → hr_unterlagen_notarunterlagen

SONSTIGES:
- Marketing, Flyer, Werbematerial → marketing_werbung
- Betriebsversammlungen, Protokolle → betriebsversammlung_meetingprotokolle
- Kirmes-Nachkalkulation → kirmes_nachkalkulation
- Nicht zuordenbar → sonstiges

=== ALLGEMEINE REGELN ===
- keywords: IMMER Firmennamen, Projektnummern, MaStR-Nummern, Zählernummern, Ortsnamen, Betragswerte als Text einfügen
- full_text: Gesamten lesbaren Text extrahieren
- reference: Projektname/Nummer, Vertragsnummer, Policennummer, MaStR-Nr., oder Zählernummer
- Wenn ein Feld nicht erkennbar ist, setze null oder leeren String
- Im Zweifel lieber anfragen_projekte als sonstiges wählen bei technischen Dokumenten"""


async def analyze_document_with_ai(file_path: str, mime_type: str, custom_folders: list = None) -> dict:
    """Analyze a document using Gemini AI."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType

        # Build dynamic folder list for AI prompt
        all_folder_ids = [f["id"] for f in PREDEFINED_FOLDERS]
        extra_hint = ""
        if custom_folders:
            for cf in custom_folders:
                all_folder_ids.append(cf["id"])
            folder_names = ", ".join(f'{cf["name"]}→{cf["id"]}' for cf in custom_folders)
            extra_hint = f"\n- Zusätzliche benutzerdefinierte Ordner: {folder_names}"

        system = AI_SYSTEM_PROMPT.replace(
            "rechnungseingang|kfz_versicherung|betriebshaftpflicht|vertraege|lieferscheine|behoerden|sonstiges",
            "|".join(all_folder_ids)
        ) + extra_hint

        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"doc-analysis-{uuid.uuid4()}",
            system_message=system
        ).with_model("gemini", "gemini-2.5-flash")

        file_content = FileContentWithMimeType(
            file_path=file_path,
            mime_type=mime_type
        )

        user_message = UserMessage(
            text="Analysiere dieses Dokument und extrahiere alle Informationen als JSON.",
            file_contents=[file_content]
        )

        response = await chat.send_message(user_message)

        # Parse JSON from response
        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            response_text = "\n".join(json_lines)

        return json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"AI response not valid JSON: {e}, response: {response_text[:500]}")
        return {"document_type": "sonstiges", "suggested_folder": "sonstiges", "subject": "Nicht erkannt", "full_text": "", "keywords": []}
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        return {"document_type": "sonstiges", "suggested_folder": "sonstiges", "subject": "Analyse fehlgeschlagen", "full_text": "", "keywords": []}


MONTH_NAMES = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
    7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
}
AUTO_YEAR_MONTH_FOLDERS = ["rechnungseingang", "rechnungsausgang"]


async def _ensure_year_month_subfolder(parent_folder_id: str, doc_date_str: str) -> str:
    """Create year/month subfolders for invoices and return the target folder_id."""
    try:
        if doc_date_str:
            dt = datetime.fromisoformat(doc_date_str.replace("Z", "+00:00")) if "T" in doc_date_str else datetime.strptime(doc_date_str[:10], "%Y-%m-%d")
        else:
            dt = datetime.now(timezone.utc)
        year = dt.year
        month = dt.month
    except Exception:
        dt = datetime.now(timezone.utc)
        year = dt.year
        month = dt.month

    year_id = f"{parent_folder_id}_{year}"
    month_id = f"{year_id}_{month:02d}"

    # Ensure year subfolder
    existing_year = await db.document_folders.find_one({"id": year_id, "is_deleted": False})
    if not existing_year:
        await db.document_folders.insert_one({
            "id": year_id, "name": str(year), "icon": "folder", "color": "gray",
            "parent_id": parent_folder_id, "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # Ensure month subfolder
    existing_month = await db.document_folders.find_one({"id": month_id, "is_deleted": False})
    if not existing_month:
        await db.document_folders.insert_one({
            "id": month_id, "name": MONTH_NAMES.get(month, str(month)), "icon": "folder", "color": "gray",
            "parent_id": year_id, "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return month_id


@router.get("/folders")
async def get_folders():
    """Get all predefined + custom folders with document counts, including subfolders."""
    counts = {}
    pipeline = [
        {"$match": {"is_deleted": False}},
        {"$group": {"_id": "$folder_id", "count": {"$sum": 1}}}
    ]
    async for item in db.documents.aggregate(pipeline):
        counts[item["_id"]] = item["count"]

    total = await db.documents.count_documents({"is_deleted": False})

    # Build all folders: predefined (root) + custom/subfolders from DB
    all_folders = []
    for f in PREDEFINED_FOLDERS:
        all_folders.append({**f, "count": counts.get(f["id"], 0), "is_custom": False, "parent_id": None})

    async for cf in db.document_folders.find({"is_deleted": False}, {"_id": 0}).sort("created_at", 1):
        cf["count"] = counts.get(cf["id"], 0)
        cf["is_custom"] = True
        if "parent_id" not in cf:
            cf["parent_id"] = None
        all_folders.append(cf)

    # Calculate recursive counts for parent folders
    folder_map = {f["id"]: f for f in all_folders}
    for f in all_folders:
        if f["parent_id"] and f["parent_id"] in folder_map:
            folder_map[f["parent_id"]]["count"] = folder_map[f["parent_id"]].get("count", 0) + f["count"]
    # Second pass for grandparent (year -> root)
    for f in all_folders:
        if f["parent_id"] and f["parent_id"] in folder_map:
            parent = folder_map[f["parent_id"]]
            if parent.get("parent_id") and parent["parent_id"] in folder_map:
                folder_map[parent["parent_id"]]["count"] = folder_map[parent["parent_id"]].get("count", 0) + f["count"]

    return {"folders": all_folders, "total": total}


@router.post("/folders")
async def create_folder(body: dict):
    """Create a custom folder or subfolder."""
    name = body.get("name", "").strip()
    parent_id = body.get("parent_id", None)
    if not name:
        raise HTTPException(status_code=400, detail="Ordnername darf nicht leer sein")
    if len(name) > 60:
        raise HTTPException(status_code=400, detail="Ordnername zu lang (max. 60 Zeichen)")

    folder_id = name.lower().replace(" ", "_").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    folder_id = "".join(c for c in folder_id if c.isalnum() or c == "_")
    if parent_id:
        folder_id = f"{parent_id}_{folder_id}"

    # Check for duplicate
    existing_ids = [f["id"] for f in PREDEFINED_FOLDERS]
    if folder_id in existing_ids:
        raise HTTPException(status_code=400, detail="Ein Ordner mit diesem Namen existiert bereits")
    existing_custom = await db.document_folders.find_one({"id": folder_id, "is_deleted": False})
    if existing_custom:
        raise HTTPException(status_code=400, detail="Ein Ordner mit diesem Namen existiert bereits")

    icon = body.get("icon", "folder")
    color = body.get("color", "gray")
    folder = {
        "id": folder_id,
        "name": name,
        "icon": icon,
        "color": color,
        "parent_id": parent_id,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.document_folders.insert_one(folder)
    return {"id": folder_id, "name": name, "icon": icon, "color": color, "parent_id": parent_id, "count": 0, "is_custom": True}


@router.put("/folders/{folder_id}")
async def rename_folder(folder_id: str, body: dict):
    """Rename a custom folder."""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Ordnername darf nicht leer sein")
    result = await db.document_folders.update_one(
        {"id": folder_id, "is_deleted": False},
        {"$set": {"name": name}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ordner nicht gefunden oder ist ein Systemordner")
    return {"status": "renamed", "name": name}


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: str):
    """Delete a custom folder (moves documents to 'sonstiges')."""
    predefined_ids = [f["id"] for f in PREDEFINED_FOLDERS]
    if folder_id in predefined_ids:
        raise HTTPException(status_code=400, detail="Systemordner können nicht gelöscht werden")

    result = await db.document_folders.update_one(
        {"id": folder_id, "is_deleted": False},
        {"$set": {"is_deleted": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ordner nicht gefunden")

    # Move all documents from this folder to "sonstiges"
    await db.documents.update_many(
        {"folder_id": folder_id, "is_deleted": False},
        {"$set": {"folder_id": "sonstiges", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"status": "deleted"}


DATEV_EMAIL = "d5aa2eb6-6bae-417a-8894-664a6eb160c8@uploadmail.datev.de"
DATEV_FORWARD_FOLDERS = ["rechnungseingang"]


async def _forward_to_datev(doc_id: str, storage_path: str, original_filename: str, content_type: str, ai_metadata: dict):
    """Forward incoming invoices to DATEV Unternehmen Online via email."""
    try:
        from email_service import send_email_with_attachment

        file_data, _ = get_object(storage_path)
        sender = ai_metadata.get("sender", "Unbekannt")
        inv_nr = ai_metadata.get("invoice_number", "")
        amount = ai_metadata.get("amount")
        subject_line = ai_metadata.get("subject", original_filename)

        subject = f"Eingangsrechnung: {subject_line}"
        if inv_nr:
            subject += f" (Nr. {inv_nr})"

        html = f"""<p>Automatische Weiterleitung aus dem Eventenergie Dokumentenportal.</p>
<p><b>Datei:</b> {original_filename}<br/>
<b>Absender:</b> {sender}<br/>
{'<b>Rechnungsnummer:</b> ' + inv_nr + '<br/>' if inv_nr else ''}
{'<b>Betrag:</b> ' + f'{amount:.2f} EUR<br/>' if amount else ''}
<b>Erkannt als:</b> Eingangsrechnung</p>"""

        send_email_with_attachment(DATEV_EMAIL, subject, html, file_data, original_filename)
        await db.documents.update_one({"id": doc_id}, {"$set": {"datev_forwarded": True, "datev_forwarded_at": datetime.now(timezone.utc).isoformat()}})
        logger.info(f"Document {doc_id} forwarded to DATEV: {original_filename}")
    except Exception as e:
        logger.error(f"DATEV forwarding failed for doc {doc_id}: {e}")
        await db.documents.update_one({"id": doc_id}, {"$set": {"datev_forwarded": False, "datev_forward_error": str(e)}})


async def _run_ai_analysis(doc_id: str, temp_path: str, content_type: str, folder_id: str):
    """Background task to run AI analysis on an uploaded document."""
    try:
        custom_folders = []
        async for cf in db.document_folders.find({"is_deleted": False}, {"_id": 0}):
            custom_folders.append(cf)
        all_valid_ids = [f["id"] for f in PREDEFINED_FOLDERS] + [cf["id"] for cf in custom_folders]

        ai_result = await analyze_document_with_ai(temp_path, content_type, custom_folders)
        suggested_folder = ai_result.get("suggested_folder", folder_id)
        final_folder = folder_id
        if folder_id == "sonstiges" and suggested_folder in all_valid_ids:
            final_folder = suggested_folder

        await db.documents.update_one({"id": doc_id}, {"$set": {
            "folder_id": final_folder,
            "ai_status": "completed",
            "ai_metadata": {k: v for k, v in ai_result.items() if k not in ("full_text", "keywords")},
            "full_text": ai_result.get("full_text", ""),
            "keywords": ai_result.get("keywords", []),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})

        # Auto-create year/month subfolders for invoice folders
        if final_folder in AUTO_YEAR_MONTH_FOLDERS:
            doc_date = ai_result.get("date", "")
            subfolder_id = await _ensure_year_month_subfolder(final_folder, doc_date)
            await db.documents.update_one({"id": doc_id}, {"$set": {"folder_id": subfolder_id}})
            final_folder = subfolder_id

        logger.info(f"AI analysis completed for doc {doc_id} -> folder: {final_folder}")

        # Auto-forward incoming invoices to DATEV
        doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
        if final_folder in DATEV_FORWARD_FOLDERS and doc:
            await _forward_to_datev(doc_id, doc["storage_path"], doc["original_filename"], content_type, ai_result)
    except Exception as e:
        logger.error(f"AI analysis error for doc {doc_id}: {e}")
        await db.documents.update_one({"id": doc_id}, {"$set": {"ai_status": "failed"}})
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), folder_id: str = Form("sonstiges")):
    """Upload a document, store it, and start AI analysis in background."""
    allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/webp", "image/tiff"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Dateityp {file.content_type} nicht unterstützt. Erlaubt: PDF, JPEG, PNG, WebP, TIFF")

    file_data = await file.read()
    if len(file_data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Datei zu groß (max. 50 MB)")

    ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    storage_path = f"{APP_NAME}/uploads/{uuid.uuid4()}.{ext}"

    try:
        result = put_object(storage_path, file_data, file.content_type)
    except Exception as e:
        logger.error(f"Storage upload failed: {e}")
        raise HTTPException(status_code=500, detail="Fehler beim Speichern der Datei")

    doc_id = str(uuid.uuid4())
    doc = {
        "id": doc_id,
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": result.get("size", len(file_data)),
        "folder_id": folder_id,
        "ai_status": "pending",
        "ai_metadata": {},
        "full_text": "",
        "keywords": [],
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.documents.insert_one(doc)

    # Save temp file and start background AI analysis
    temp_path = f"/tmp/{uuid.uuid4()}.{ext}"
    with open(temp_path, "wb") as f:
        f.write(file_data)

    asyncio.create_task(_run_ai_analysis(doc_id, temp_path, file.content_type, folder_id))

    clean = {k: v for k, v in doc.items() if k != "_id"}
    return clean


@router.get("/list")
async def list_documents(folder_id: str = None, include_children: bool = True, page: int = 1, limit: int = 50):
    """List documents, optionally filtered by folder (includes subfolder docs)."""
    query = {"is_deleted": False}
    if folder_id:
        if include_children:
            # Include docs from this folder and all subfolders (prefix match)
            query["folder_id"] = {"$regex": f"^{folder_id}"}
        else:
            query["folder_id"] = folder_id

    total = await db.documents.count_documents(query)
    skip = (page - 1) * limit
    docs = []
    async for doc in db.documents.find(query, {"_id": 0, "full_text": 0}).sort("created_at", -1).skip(skip).limit(limit):
        docs.append(doc)

    return {"documents": docs, "total": total, "page": page, "limit": limit}


@router.get("/search")
async def search_documents(q: str = Query(..., min_length=1)):
    """Full-text search across all documents."""
    docs = []
    query = {
        "is_deleted": False,
        "$or": [
            {"full_text": {"$regex": q, "$options": "i"}},
            {"keywords": {"$regex": q, "$options": "i"}},
            {"original_filename": {"$regex": q, "$options": "i"}},
            {"ai_metadata.sender": {"$regex": q, "$options": "i"}},
            {"ai_metadata.subject": {"$regex": q, "$options": "i"}},
            {"ai_metadata.invoice_number": {"$regex": q, "$options": "i"}},
            {"ai_metadata.reference": {"$regex": q, "$options": "i"}},
            {"ai_metadata.iban": {"$regex": q, "$options": "i"}},
        ]
    }
    async for doc in db.documents.find(query, {"_id": 0, "full_text": 0}).sort("created_at", -1).limit(50):
        docs.append(doc)
    return {"documents": docs, "query": q}


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """Get a single document with all metadata."""
    doc = await db.documents.find_one({"id": doc_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return doc


@router.put("/{doc_id}/move")
async def move_document(doc_id: str, folder_id: str = Query(...)):
    """Move a document to a different folder."""
    valid_ids = [f["id"] for f in PREDEFINED_FOLDERS]
    # Also accept custom folders
    async for cf in db.document_folders.find({"is_deleted": False}, {"_id": 0}):
        valid_ids.append(cf["id"])
    if folder_id not in valid_ids:
        raise HTTPException(status_code=400, detail="Ungültiger Ordner")

    result = await db.documents.update_one(
        {"id": doc_id, "is_deleted": False},
        {"$set": {"folder_id": folder_id, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return {"status": "moved", "folder_id": folder_id}


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """Soft-delete a document."""
    result = await db.documents.update_one(
        {"id": doc_id, "is_deleted": False},
        {"$set": {"is_deleted": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return {"status": "deleted"}


@router.get("/{doc_id}/file")
async def download_file(doc_id: str):
    """Download the actual file."""
    doc = await db.documents.find_one({"id": doc_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    try:
        data, ct = get_object(doc["storage_path"])
        return Response(
            content=data,
            media_type=doc.get("content_type", ct),
            headers={"Content-Disposition": f'inline; filename="{doc["original_filename"]}"'}
        )
    except Exception as e:
        logger.error(f"File download failed: {e}")
        raise HTTPException(status_code=500, detail="Fehler beim Herunterladen")
