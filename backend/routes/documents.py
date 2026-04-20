import os
import uuid
import json
import logging
import asyncio
import tempfile
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

# Lokale Dateiablage auf dem Produktionsserver
# Auf Windows: C:\eventenergie\Dokumentenablage
# Auf Linux/Dev: /app/data/Dokumentenablage (Fallback)
LOCAL_STORAGE_ROOT = os.environ.get("LOCAL_STORAGE_PATH", r"C:\eventenergie\Dokumentenablage")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

PREDEFINED_FOLDERS = [
    # Unbekannt - fuer noch nicht zugeordnete Dokumente (immer ganz oben)
    {"id": "unbekannt", "name": "Unbekannt", "icon": "help-circle", "color": "amber"},
    # Finanzen & Buchhaltung
    {"id": "rechnungseingang", "name": "Rechnungseingang", "icon": "receipt", "color": "emerald"},
    # Rechnungseingang pro Firma (Unterordner, Jahr/Monat wird automatisch darunter angelegt)
    {"id": "rechnungseingang_eventenergie_deutschland", "name": "Eventenergie Deutschland GmbH & Co. KG", "icon": "receipt", "color": "emerald", "parent_id": "rechnungseingang"},
    {"id": "rechnungseingang_es_besitz_verwaltung", "name": "ES Besitz und Verwaltungs GmbH & Co. KG", "icon": "receipt", "color": "emerald", "parent_id": "rechnungseingang"},
    {"id": "rechnungsausgang", "name": "Rechnungsausgang", "icon": "receipt", "color": "emerald"},
    # Rechnungsausgang pro Firma
    {"id": "rechnungsausgang_eventenergie_deutschland", "name": "Eventenergie Deutschland GmbH & Co. KG", "icon": "receipt", "color": "emerald", "parent_id": "rechnungsausgang"},
    {"id": "rechnungsausgang_es_besitz_verwaltung", "name": "ES Besitz und Verwaltungs GmbH & Co. KG", "icon": "receipt", "color": "emerald", "parent_id": "rechnungsausgang"},
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
    {"id": "lohnabrechnung", "name": "Lohnabrechnung", "icon": "receipt", "color": "emerald"},
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
    {"id": "lieferscheine_eingehend", "name": "Lieferscheine eingehend", "icon": "truck", "color": "orange"},
    {"id": "lieferscheine_ausgehend", "name": "Lieferscheine ausgehend", "icon": "truck", "color": "orange"},
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


async def _get_file_data_fallback(storage_path: str, filename: str, folder_id: str):
    """Try cloud storage first, then local filesystem as fallback."""
    # Try cloud storage
    if not storage_path.startswith("local://"):
        try:
            data, ct = get_object(storage_path)
            return data, ct
        except Exception:
            pass

    # Fallback: read from local filesystem
    all_folders = []
    async for cf in db.document_folders.find({"is_deleted": False}, {"_id": 0}):
        all_folders.append(cf)
    for pf in PREDEFINED_FOLDERS:
        all_folders.append({"id": pf["id"], "name": pf["name"], "parent_id": None})

    folder_path = _build_folder_path(folder_id, all_folders)
    local_file = os.path.join(LOCAL_STORAGE_ROOT, folder_path, filename)
    if os.path.exists(local_file):
        with open(local_file, "rb") as f:
            return f.read(), "application/octet-stream"

    raise FileNotFoundError(f"File not found in cloud or local storage: {filename}")


def _build_folder_path(folder_id: str, all_folders: list) -> str:
    """Build the full folder path from folder_id using folder hierarchy."""
    folder_map = {f["id"]: f for f in all_folders}
    parts = []
    current_id = folder_id
    while current_id:
        f = folder_map.get(current_id)
        if f:
            parts.insert(0, f["name"])
            current_id = f.get("parent_id")
        else:
            # Might be a predefined folder
            pf = next((p for p in PREDEFINED_FOLDERS if p["id"] == current_id), None)
            if pf:
                parts.insert(0, pf["name"])
            break
    return os.path.join(*parts) if parts else "Sonstiges"


async def _save_to_local_storage(file_data: bytes, filename: str, folder_id: str):
    """Save the original file to the local filesystem on the production server."""
    try:
        # Build folder hierarchy from DB
        all_folders = []
        async for cf in db.document_folders.find({"is_deleted": False}, {"_id": 0}):
            all_folders.append(cf)
        for pf in PREDEFINED_FOLDERS:
            all_folders.append({"id": pf["id"], "name": pf["name"], "parent_id": None})

        folder_path = _build_folder_path(folder_id, all_folders)
        full_dir = os.path.join(LOCAL_STORAGE_ROOT, folder_path)
        os.makedirs(full_dir, exist_ok=True)

        # Avoid overwriting: add suffix if file exists
        target_path = os.path.join(full_dir, filename)
        if os.path.exists(target_path):
            name, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(target_path):
                target_path = os.path.join(full_dir, f"{name}_{counter}{ext}")
                counter += 1

        with open(target_path, "wb") as f:
            f.write(file_data)

        logger.info(f"Local file saved: {target_path}")
        return target_path
    except Exception as e:
        logger.warning(f"Local storage save failed (non-critical): {e}")
        return None



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
- Eingangsrechnungen (von Lieferanten/Dienstleistern an uns) → rechnungseingang_eventenergie_deutschland ODER rechnungseingang_es_besitz_verwaltung (siehe FIRMEN-ZUORDNUNG unten)
- Ausgangsrechnungen (von uns an Kunden) → rechnungsausgang_eventenergie_deutschland ODER rechnungsausgang_es_besitz_verwaltung
- Erkennbar an: Rechnungsnummer, Nettobetrag, MwSt, Zahlungsziel, IBAN

=== FIRMEN-ZUORDNUNG (WICHTIG fuer Rechnungen!) ===
Wir haben ZWEI Firmen mit unterschiedlicher Buchhaltung:

1. "Eventenergie Deutschland GmbH & Co. KG" (kurz: EED)
   - Kerngeschaeft: Elektrotechnik, temporaere Stromversorgung, PV-Anlagen, Netzanschluesse
   - Bei Eingangsrechnungen: Empfaenger ist Eventenergie Deutschland GmbH, Eventenergie Deutschland GmbH & Co. KG, EED, oder eine dieser Schreibweisen
   - Bei Ausgangsrechnungen: Absender ist Eventenergie Deutschland
   - USt-IdNr./Steuernummer der EED erkennst Du am Briefkopf
   - Suggested_folder: "rechnungseingang_eventenergie_deutschland" bzw. "rechnungsausgang_eventenergie_deutschland"

2. "ES Besitz und Verwaltungs GmbH & Co. KG" (kurz: ES Besitz oder ESBV)
   - Zweck: Besitz- und Verwaltungsgesellschaft (Immobilien, Fuhrpark, Geraetevermoegen)
   - Bei Eingangsrechnungen: Empfaenger ist "ES Besitz und Verwaltungs GmbH & Co. KG", "ES Besitz GmbH", "ESBV" oder Varianten davon
   - Bei Ausgangsrechnungen: Absender ist ES Besitz und Verwaltungs GmbH
   - Typische Inhalte: KFZ-Leasing, Mieten, Kauf von Maschinen, Immobilien-bezogene Rechnungen
   - Suggested_folder: "rechnungseingang_es_besitz_verwaltung" bzw. "rechnungsausgang_es_besitz_verwaltung"

ENTSCHEIDUNGSREGEL fuer die Firmen-Zuordnung:
1. Schau dir IMMER zuerst den "Empfaenger" der Rechnung an (bei Eingang) bzw. den "Absender" (bei Ausgang)
2. Die Firma ist meistens im Briefkopf oder in der Adresszeile mit "An: ..." zu finden
3. Wenn eindeutig "Eventenergie Deutschland" -> EED
4. Wenn eindeutig "ES Besitz" / "ESBV" -> ES Besitz
5. Wenn du UNSICHER bist (z.B. nur "Eventenergie" ohne Zusatz, oder kein Empfaenger erkennbar): suggested_folder = "unbekannt" - NICHT raten!

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
- Eingehende Lieferscheine (von Lieferanten an Eventenergie) → lieferscheine_eingehend
- Ausgehende Lieferscheine (von Eventenergie an Kunden) → lieferscheine_ausgehend
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
- Arbeitsverträge, Zeugnisse → mitarbeiter
- HR/Notar-Dokumente → hr_unterlagen_notarunterlagen

LOHNABRECHNUNG:
- Lohnabrechnungen, Gehaltsabrechnungen, Entgeltabrechnungen, Lohnzettel → lohnabrechnung
- DATEV-Lohnabrechnungen, Brutto/Netto-Abrechnungen → lohnabrechnung
- Erkennbar an: Personal-Nr., Steuerklasse, Sozialversicherung, Bruttolohn, Nettolohn, Lohnsteuer

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


@router.get("/ai-settings")
async def get_ai_settings():
    """Get custom AI prompt instructions."""
    settings = await db.ai_settings.find_one({"key": "document_analysis"}, {"_id": 0})
    return settings or {"key": "document_analysis", "custom_instructions": "", "updated_at": None}


@router.put("/ai-settings")
async def update_ai_settings(body: dict):
    """Update custom AI prompt instructions (admin only)."""
    custom_instructions = body.get("custom_instructions", "").strip()
    if len(custom_instructions) > 5000:
        raise HTTPException(status_code=400, detail="Anweisungen zu lang (max. 5000 Zeichen)")
    
    doc = {
        "key": "document_analysis",
        "custom_instructions": custom_instructions,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_settings.update_one(
        {"key": "document_analysis"}, {"$set": doc}, upsert=True
    )
    logger.info(f"AI settings updated: {len(custom_instructions)} chars")
    return doc


async def _get_custom_ai_instructions() -> str:
    """Load custom AI instructions and training samples from DB."""
    parts = []
    settings = await db.ai_settings.find_one({"key": "document_analysis"}, {"_id": 0})
    if settings and settings.get("custom_instructions"):
        parts.append(settings["custom_instructions"])

    # Include training samples as correction examples
    samples = []
    async for s in db.ai_training_samples.find({}, {"_id": 0, "file_data": 0}).sort("created_at", -1).limit(20):
        samples.append(s)
    if samples:
        parts.append("\n--- Bekannte Fehler und Korrekturen ---")
        for s in samples:
            parts.append(f"Datei '{s.get('filename', '?')}': Fehler: {s.get('error_description', '')} | Korrektur: {s.get('correction', '')}")

    return "\n".join(parts)


async def analyze_document_with_ai(file_path: str, mime_type: str, custom_folders: list = None) -> dict:
    """Analyze a document using Gemini AI."""
    try:
        if not EMERGENT_KEY:
            raise RuntimeError("EMERGENT_LLM_KEY nicht gesetzt – bitte in backend/.env ergänzen (sk-emergent-...)")
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

        # Inject custom admin instructions
        custom_instructions = await _get_custom_ai_instructions()
        if custom_instructions:
            system += f"\n\n=== ZUSÄTZLICHE ADMIN-ANWEISUNGEN ===\n{custom_instructions}"

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
AUTO_YEAR_MONTH_FOLDERS = "*"  # "*" = alle Kategorien bekommen Jahr/Monat-Unterordner (ausser 'unbekannt')
SKIP_YEAR_MONTH_FOLDERS = {"unbekannt", "sonstiges", "temporaerer_ordner", "vorlagen"}


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
        all_folders.append({**f, "count": counts.get(f["id"], 0), "is_custom": False, "parent_id": f.get("parent_id")})

    async for cf in db.document_folders.find({"is_deleted": False}, {"_id": 0}).sort("created_at", 1):
        cf["count"] = counts.get(cf["id"], 0)
        cf["is_custom"] = True
        if "parent_id" not in cf:
            cf["parent_id"] = None
        all_folders.append(cf)

    # Recursive Bottom-Up Rollup: Jeder Parent zeigt Summe seiner eigenen Docs + aller Nachkommen
    folder_map = {f["id"]: f for f in all_folders}
    children_map = {}
    for f in all_folders:
        children_map.setdefault(f.get("parent_id"), []).append(f["id"])

    direct_counts = {fid: f["count"] for fid, f in folder_map.items()}

    def compute_total(fid):
        total_c = direct_counts.get(fid, 0)
        for child_id in children_map.get(fid, []):
            total_c += compute_total(child_id)
        return total_c

    for f in all_folders:
        f["count"] = compute_total(f["id"])

    return {"folders": all_folders, "total": total}


@router.post("/migrate/rechnungen-firma-struktur")
async def migrate_rechnungen_firma_struktur(dry_run: bool = Query(False)):
    """
    Einmalige Migration: verschiebt Dokumente aus den alten 'rechnungsausgang'-Wurzeln
    (ohne Firmen-Unterteilung) in die neue Struktur 'rechnungsausgang_eventenergie_deutschland'.
    Alte leere Jahres-/Monats-Ordner werden soft-geloescht.

    Nur Rechnungsausgang wird migriert (Kirmes-Rechnungen = immer EED). Rechnungseingang
    bleibt unangetastet und muss manuell per Drag&Drop einer Firma zugeordnet werden,
    damit die KI aus den Entscheidungen lernt.

    Mit dry_run=true werden nur die geplanten Aenderungen zurueckgegeben, ohne zu schreiben.
    """
    # 1. Alle Dokumente direkt in rechnungsausgang-Root oder in alten Jahr/Monat-Subs (ohne Firma)
    old_root_ids = ["rechnungsausgang"]
    old_subs = await db.document_folders.find(
        {"parent_id": "rechnungsausgang", "is_deleted": False}, {"_id": 0, "id": 1}
    ).to_list(100)
    old_root_ids += [f["id"] for f in old_subs]

    month_subs = await db.document_folders.find(
        {"parent_id": {"$in": [f["id"] for f in old_subs]}, "is_deleted": False},
        {"_id": 0, "id": 1}
    ).to_list(200)
    old_root_ids += [f["id"] for f in month_subs]

    # Firmen-Unterordner ausschliessen
    old_root_ids = [fid for fid in old_root_ids
                    if fid in ("rechnungsausgang",)
                    or (fid.startswith("rechnungsausgang_") and "eventenergie_deutschland" not in fid and "es_besitz_verwaltung" not in fid)]

    docs_to_move = await db.documents.find(
        {"folder_id": {"$in": old_root_ids}, "is_deleted": False},
        {"_id": 0, "id": 1, "original_filename": 1, "folder_id": 1, "ai_metadata": 1, "created_at": 1}
    ).to_list(5000)

    planned_moves = []
    for d in docs_to_move:
        date = (d.get("ai_metadata") or {}).get("date") or d.get("created_at", "")
        planned_moves.append({
            "doc_id": d["id"],
            "filename": d.get("original_filename", ""),
            "from_folder": d.get("folder_id"),
            "to_parent": "rechnungsausgang_eventenergie_deutschland",
            "date_hint": date[:10],
        })

    if dry_run:
        return {
            "dry_run": True,
            "docs_to_move": len(planned_moves),
            "old_folders_to_cleanup": [f for f in old_root_ids if f != "rechnungsausgang"],
            "moves": planned_moves[:50],  # erste 50 zeigen
        }

    # Tatsaechlich verschieben
    from datetime import datetime, timezone as _tz
    moved = 0
    for d in docs_to_move:
        date = (d.get("ai_metadata") or {}).get("date") or d.get("created_at", "")
        new_sub = await _ensure_year_month_subfolder("rechnungsausgang_eventenergie_deutschland", date)
        await db.documents.update_one(
            {"id": d["id"]},
            {"$set": {
                "folder_id": new_sub,
                "ai_metadata.suggested_folder": "rechnungsausgang_eventenergie_deutschland",
                "updated_at": datetime.now(_tz.utc).isoformat(),
            }}
        )
        moved += 1

    # Alte leere Ordner aufraeumen
    cleaned = 0
    for fid in old_root_ids:
        if fid == "rechnungsausgang":
            continue  # Root nicht loeschen
        remaining = await db.documents.count_documents({"folder_id": fid, "is_deleted": False})
        if remaining == 0:
            r = await db.document_folders.update_one(
                {"id": fid, "is_deleted": False},
                {"$set": {"is_deleted": True, "deleted_at": datetime.now(_tz.utc).isoformat()}}
            )
            if r.matched_count:
                cleaned += 1

    return {"dry_run": False, "docs_moved": moved, "folders_cleaned": cleaned}



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


# DATEV Upload-E-Mails (aus .env, pro Firma + Richtung)
# Falls nicht gesetzt, wird Weiterleitung fuer diese Kombination uebersprungen.
DATEV_EMAIL_RECH_EIN_EED = os.environ.get("DATEV_EMAIL_RECHNUNGSEINGANG_EED", "").strip()
DATEV_EMAIL_RECH_AUS_EED = os.environ.get("DATEV_EMAIL_RECHNUNGSAUSGANG_EED", "").strip()
DATEV_EMAIL_RECH_EIN_ESBV = os.environ.get("DATEV_EMAIL_RECHNUNGSEINGANG_ESBV", "").strip()
DATEV_EMAIL_RECH_AUS_ESBV = os.environ.get("DATEV_EMAIL_RECHNUNGSAUSGANG_ESBV", "").strip()

# Mapping Folder-Prefix -> (DATEV-E-Mail, Richtungs-Label, Firmen-Label)
DATEV_ROUTING = {
    "rechnungseingang_eventenergie_deutschland": (DATEV_EMAIL_RECH_EIN_EED, "Eingangsrechnung", "Eventenergie Deutschland"),
    "rechnungsausgang_eventenergie_deutschland": (DATEV_EMAIL_RECH_AUS_EED, "Ausgangsrechnung", "Eventenergie Deutschland"),
    "rechnungseingang_es_besitz_verwaltung": (DATEV_EMAIL_RECH_EIN_ESBV, "Eingangsrechnung", "ES Besitz und Verwaltung"),
    "rechnungsausgang_es_besitz_verwaltung": (DATEV_EMAIL_RECH_AUS_ESBV, "Ausgangsrechnung", "ES Besitz und Verwaltung"),
}


def _resolve_datev_target(folder_id: str):
    """Liefert (email, richtung, firma) fuer einen folder_id oder None wenn nicht weiterleitbar."""
    for prefix, (email, richtung, firma) in DATEV_ROUTING.items():
        if folder_id == prefix or folder_id.startswith(prefix + "_"):
            if email:
                return email, richtung, firma
            logger.warning(f"Fuer Ordner {folder_id} ist keine DATEV-E-Mail in .env konfiguriert")
            return None
    return None


async def _forward_to_datev(doc_id: str, storage_path: str, original_filename: str, content_type: str, ai_metadata: dict, folder_id: str):
    """Forward invoices to the correct DATEV mailbox based on company + direction (folder_id)."""
    try:
        target = _resolve_datev_target(folder_id)
        if not target:
            await db.documents.update_one({"id": doc_id}, {"$set": {"datev_forwarded": False, "datev_skip_reason": "Keine DATEV-E-Mail fuer diesen Ordner konfiguriert"}})
            return
        datev_email, richtung, firma = target

        from email_service import send_email_with_attachment

        file_data, _ = await _get_file_data_fallback(storage_path, original_filename, folder_id)
        sender = ai_metadata.get("sender", "Unbekannt")
        inv_nr = ai_metadata.get("invoice_number", "")
        amount = ai_metadata.get("amount")
        subject_line = ai_metadata.get("subject", original_filename)

        subject = f"{richtung} {firma}: {subject_line}"
        if inv_nr:
            subject += f" (Nr. {inv_nr})"

        html = f"""<p>Automatische Weiterleitung aus dem Eventenergie Dokumentenportal.</p>
<p><b>Firma:</b> {firma}<br/>
<b>Typ:</b> {richtung}<br/>
<b>Datei:</b> {original_filename}<br/>
<b>{('Absender' if richtung == 'Eingangsrechnung' else 'Empfaenger')}:</b> {sender}<br/>
{'<b>Rechnungsnummer:</b> ' + inv_nr + '<br/>' if inv_nr else ''}
{'<b>Betrag:</b> ' + f'{amount:.2f} EUR<br/>' if amount else ''}
</p>"""

        send_email_with_attachment(datev_email, subject, html, file_data, original_filename)
        await db.documents.update_one({"id": doc_id}, {"$set": {
            "datev_forwarded": True,
            "datev_forwarded_at": datetime.now(timezone.utc).isoformat(),
            "datev_target_email": datev_email,
            "datev_company": firma,
            "datev_direction": richtung,
        }})
        logger.info(f"Dokument {doc_id} ({richtung} {firma}) an DATEV weitergeleitet: {datev_email}")
    except Exception as e:
        logger.error(f"DATEV-Weiterleitung fehlgeschlagen fuer {doc_id}: {e}")
        await db.documents.update_one({"id": doc_id}, {"$set": {"datev_forwarded": False, "datev_forward_error": str(e)}})


async def _assign_payroll_to_employee(doc_id: str, ai_result: dict, temp_path: str, content_type: str):
    """Use AI to extract employee name from payroll PDF and assign it to the matching user."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType

        # Get all users from DB
        users = []
        async for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1, "email": 1}):
            users.append(u)
        user_list = ", ".join(f'{u["name"]} (ID: {u["id"]})' for u in users)

        system = f"""Du bist ein Spezialist für die Erkennung von Lohnabrechnungen.
Extrahiere aus dem Dokument:
1. Den vollständigen Namen des Mitarbeiters
2. Die Personalnummer
3. Den Abrechnungsmonat (YYYY-MM Format)
4. Den Netto-Auszahlungsbetrag

Hier sind die bekannten Mitarbeiter im System:
{user_list}

Ordne den erkannten Namen dem passenden Mitarbeiter zu. Beachte: Kleine Abweichungen (Vorname/Nachname vertauscht, Umlaute) sind möglich.

Antworte NUR mit JSON:
{{"employee_name": "...", "personnel_number": "...", "month": "YYYY-MM", "net_amount": 0.00, "matched_user_id": "..." oder null falls kein Match, "matched_user_name": "..."}}"""

        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"payroll-assign-{uuid.uuid4()}",
            system_message=system
        ).with_model("gemini", "gemini-2.5-flash")

        # Re-read the file if temp_path still exists
        if os.path.exists(temp_path):
            file_content = FileContentWithMimeType(file_path=temp_path, mime_type=content_type)
            msg = UserMessage(text="Analysiere diese Lohnabrechnung und ordne sie einem Mitarbeiter zu.", file_contents=[file_content])
        else:
            # Fall back to text from first AI analysis
            full_text = ai_result.get("full_text", "")
            msg = UserMessage(text=f"Analysiere diese Lohnabrechnung und ordne sie einem Mitarbeiter zu:\n\n{full_text}")

        response = await chat.send_message(msg)
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

        payroll_info = json.loads(response_text)
        matched_user_id = payroll_info.get("matched_user_id")

        update = {
            "payroll_info": payroll_info,
            "assigned_user_id": matched_user_id,
            "payroll_month": payroll_info.get("month"),
            "payroll_net_amount": payroll_info.get("net_amount"),
        }
        await db.documents.update_one({"id": doc_id}, {"$set": update})
        if matched_user_id:
            logger.info(f"Payroll doc {doc_id} assigned to user {matched_user_id} ({payroll_info.get('matched_user_name')})")
        else:
            logger.warning(f"Payroll doc {doc_id}: No matching user found for '{payroll_info.get('employee_name')}'")
    except Exception as e:
        logger.error(f"Payroll assignment failed for doc {doc_id}: {e}")
        await db.documents.update_one({"id": doc_id}, {"$set": {"payroll_info": {"error": str(e)}}})


async def _run_ai_analysis(doc_id: str, temp_path: str, content_type: str, folder_id: str):
    """Background task to run AI analysis on an uploaded document."""
    try:
        custom_folders = []
        async for cf in db.document_folders.find({"is_deleted": False}, {"_id": 0}):
            custom_folders.append(cf)
        all_valid_ids = [f["id"] for f in PREDEFINED_FOLDERS] + [cf["id"] for cf in custom_folders]

        ai_result = await analyze_document_with_ai(temp_path, content_type, custom_folders)
        suggested_folder = ai_result.get("suggested_folder", folder_id)

        # Safety: Rechnungs-Root-Folder (ohne Firma) zaehlen als "unsicher" -> 'unbekannt'
        RECHNUNGS_ROOTS_WITHOUT_COMPANY = {"rechnungseingang", "rechnungsausgang"}
        if suggested_folder in RECHNUNGS_ROOTS_WITHOUT_COMPANY:
            logger.info(f"KI gab {suggested_folder} ohne Firmen-Zuordnung zurueck -> 'unbekannt'")
            suggested_folder = "unbekannt"

        # Bestimme finale Ablage: Wenn KI sicher ist -> vorgeschlagener Ordner, sonst 'unbekannt'
        final_folder = folder_id
        uncertain = suggested_folder in (None, "", "sonstiges", "unbekannt") or suggested_folder not in all_valid_ids
        if folder_id in ("sonstiges", "unbekannt"):
            if uncertain:
                # AI war unsicher - versuche Base-Folder aus year/month-ID zu extrahieren
                matched_base = None
                for base_folder in all_valid_ids:
                    if suggested_folder and suggested_folder.startswith(base_folder + "_"):
                        matched_base = base_folder
                        break
                final_folder = matched_base or "unbekannt"
            else:
                final_folder = suggested_folder

        await db.documents.update_one({"id": doc_id}, {"$set": {
            "folder_id": final_folder,
            "ai_status": "completed",
            "ai_metadata": {k: v for k, v in ai_result.items() if k not in ("full_text", "keywords")},
            "full_text": ai_result.get("full_text", ""),
            "keywords": ai_result.get("keywords", []),
            "ai_suggested_folder": suggested_folder,  # fuer spaeteres Training behalten
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})

        # Jahr/Monat-Unterordner fuer ALLE Kategorien (ausser 'unbekannt' & Co.)
        if final_folder not in SKIP_YEAR_MONTH_FOLDERS:
            doc_date = ai_result.get("date", "")
            subfolder_id = await _ensure_year_month_subfolder(final_folder, doc_date)
            await db.documents.update_one({"id": doc_id}, {"$set": {"folder_id": subfolder_id}})
            final_folder = subfolder_id

        logger.info(f"AI analysis completed for doc {doc_id} -> folder: {final_folder}")

        # Save to local filesystem (C:\eventenergie\Dokumentenablage\...)
        doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
        if doc:
            try:
                file_data, _ = await _get_file_data_fallback(doc["storage_path"], doc["original_filename"], final_folder)
                local_path = await _save_to_local_storage(file_data, doc["original_filename"], final_folder)
                if local_path:
                    await db.documents.update_one({"id": doc_id}, {"$set": {"local_path": local_path}})
            except Exception as e:
                logger.warning(f"Local storage save failed for doc {doc_id}: {e}")

        # Auto-forward: Rechnungseingang UND Rechnungsausgang an DATEV (Ziel-Mail je nach Firma)
        if not doc:
            doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
        if doc and _resolve_datev_target(final_folder):
            await _forward_to_datev(doc_id, doc["storage_path"], doc["original_filename"], content_type, ai_result, final_folder)

        # Auto-assign payroll documents to employees
        if final_folder.startswith("lohnabrechnung"):
            await _assign_payroll_to_employee(doc_id, ai_result, temp_path, content_type)
    except Exception as e:
        logger.error(f"AI analysis error for doc {doc_id}: {e}")
        await db.documents.update_one({"id": doc_id}, {"$set": {"ai_status": "failed"}})
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), folder_id: str = Form("unbekannt")):
    """Upload a document, store it, and start AI analysis in background. Default landet in 'unbekannt' bis KI zuordnen konnte."""
    allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/webp", "image/tiff"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Dateityp {file.content_type} nicht unterstützt. Erlaubt: PDF, JPEG, PNG, WebP, TIFF")

    file_data = await file.read()
    if len(file_data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Datei zu groß (max. 50 MB)")

    ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    storage_path = f"{APP_NAME}/uploads/{uuid.uuid4()}.{ext}"

    cloud_storage_path = None
    try:
        result = put_object(storage_path, file_data, file.content_type)
        cloud_storage_path = result["path"]
    except Exception as e:
        logger.warning(f"Cloud storage upload failed (using local fallback): {e}")

    # If cloud storage failed, use local path as storage_path
    final_storage_path = cloud_storage_path or f"local://{storage_path}"

    doc_id = str(uuid.uuid4())
    doc = {
        "id": doc_id,
        "storage_path": final_storage_path,
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": len(file_data),
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

    # Always save locally as well
    await _save_to_local_storage(file_data, file.filename, folder_id)

    # Save temp file and start background AI analysis
    temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.{ext}")
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
    """Move a document to a different folder. Wird das Dokument aus 'unbekannt' verschoben, wird ein KI-Trainingsbeispiel gespeichert, damit die KI beim naechsten Mal besser zuordnet."""
    valid_ids = [f["id"] for f in PREDEFINED_FOLDERS]
    async for cf in db.document_folders.find({"is_deleted": False}, {"_id": 0}):
        valid_ids.append(cf["id"])
    if folder_id not in valid_ids:
        raise HTTPException(status_code=400, detail="Ungueltiger Ordner")

    doc = await db.documents.find_one({"id": doc_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    current_folder = doc.get("folder_id", "")
    target_folder_id = folder_id

    # Jahr/Monat-Unterordner automatisch anlegen (ausser fuer Skip-Liste)
    base_target = folder_id
    # Wenn Ziel selbst schon ein Jahr- oder Monats-Unterordner ist, nutze es direkt
    is_sub = await db.document_folders.find_one({"id": folder_id, "parent_id": {"$exists": True, "$ne": None}})
    if not is_sub and folder_id not in SKIP_YEAR_MONTH_FOLDERS:
        doc_date = (doc.get("ai_metadata") or {}).get("date", "") or doc.get("created_at", "")
        target_folder_id = await _ensure_year_month_subfolder(folder_id, doc_date)
        base_target = folder_id

    await db.documents.update_one(
        {"id": doc_id, "is_deleted": False},
        {"$set": {"folder_id": target_folder_id, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    # KI-Training: Dokument wurde manuell korrigiert (z.B. aus 'unbekannt' in richtigen Ordner)
    came_from_unknown = current_folder == "unbekannt" or current_folder.startswith("unbekannt_")
    ai_suggested = doc.get("ai_suggested_folder", "")
    ai_was_wrong = ai_suggested and ai_suggested != base_target and not ai_suggested.startswith(base_target + "_")

    if came_from_unknown or ai_was_wrong:
        sample = {
            "id": str(uuid.uuid4()),
            "filename": doc.get("original_filename", ""),
            "doc_id": doc_id,
            "ai_suggested": ai_suggested or "unbekannt",
            "correct_folder": base_target,
            "error_description": f"KI ordnete '{ai_suggested or 'unbekannt'}' zu, richtig ist '{base_target}'",
            "correction": f"Dokumente wie dieses ('{doc.get('original_filename', '')}', Typ: {(doc.get('ai_metadata') or {}).get('document_type', '?')}, Absender: {(doc.get('ai_metadata') or {}).get('sender', '?')}) gehoeren in den Ordner '{base_target}'.",
            "keywords": doc.get("keywords", []),
            "metadata_snapshot": doc.get("ai_metadata", {}),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "user_move",
        }
        await db.ai_training_samples.insert_one(sample)
        logger.info(f"KI-Training-Sample gespeichert: {doc.get('original_filename')} -> {base_target}")

    return {"status": "moved", "folder_id": target_folder_id, "trained": came_from_unknown or ai_was_wrong}


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

    sp = doc.get("storage_path", "")

    # Try cloud storage first, then local fallback
    try:
        if sp.startswith("local://"):
            raise Exception("Local-only document")
        data, ct = get_object(sp)
        return Response(
            content=data,
            media_type=doc.get("content_type", ct),
            headers={"Content-Disposition": f'inline; filename="{doc["original_filename"]}"'}
        )
    except Exception:
        pass

    # Fallback: try to read from local storage
    try:
        all_folders = []
        async for cf in db.document_folders.find({"is_deleted": False}, {"_id": 0}):
            all_folders.append(cf)
        for pf in PREDEFINED_FOLDERS:
            all_folders.append({"id": pf["id"], "name": pf["name"], "parent_id": None})

        folder_path = _build_folder_path(doc.get("folder_id", "sonstiges"), all_folders)
        local_file = os.path.join(LOCAL_STORAGE_ROOT, folder_path, doc["original_filename"])

        if os.path.exists(local_file):
            with open(local_file, "rb") as f:
                data = f.read()
            return Response(
                content=data,
                media_type=doc.get("content_type", "application/octet-stream"),
                headers={"Content-Disposition": f'inline; filename="{doc["original_filename"]}"'}
            )
    except Exception as e:
        logger.error(f"Local file read failed: {e}")

    raise HTTPException(status_code=500, detail="Fehler beim Herunterladen")


# ─── AI Training Samples ───

@router.get("/ai-training-samples")
async def get_training_samples():
    samples = []
    async for s in db.ai_training_samples.find({}, {"_id": 0}).sort("created_at", -1).limit(50):
        samples.append(s)
    return {"samples": samples}


@router.post("/ai-training-samples")
async def upload_training_sample(
    file: UploadFile = File(...),
    error_description: str = Form(...),
    correction: str = Form(""),
):
    import base64
    content = await file.read()
    sample_id = str(uuid.uuid4())
    doc = {
        "id": sample_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "file_data": base64.b64encode(content).decode("utf-8"),
        "file_size": len(content),
        "error_description": error_description,
        "correction": correction,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_training_samples.insert_one(doc)
    return {"id": sample_id, "filename": file.filename}


@router.delete("/ai-training-samples/{sample_id}")
async def delete_training_sample(sample_id: str):
    result = await db.ai_training_samples.delete_one({"id": sample_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Trainingsbeispiel nicht gefunden")
    return {"deleted": True}
