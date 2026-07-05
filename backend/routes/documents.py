import os
import re
import uuid
import json
import logging
import asyncio
import tempfile
import requests
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, BackgroundTasks
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "eventenergie-docs"

# SSL-Konfiguration fuer Object-Storage Requests.
# Auf Windows-Servern ohne System-CA-Bundle schlaegt die Verifikation gegen
# integrations.emergentagent.com oft mit "unable to get local issuer certificate"
# fehl. Drei Abstufungen:
#  1) STORAGE_SSL_CA_BUNDLE=/pfad/zu/bundle.pem  -> explizites Bundle nutzen
#  2) STORAGE_SSL_VERIFY=false                   -> Verify komplett aus (Notfall)
#  3) Standard: versuche `truststore` (Windows-Zertifikatsstore), sonst certifi
_STORAGE_CA_BUNDLE = os.environ.get("STORAGE_SSL_CA_BUNDLE", "").strip()
_STORAGE_SSL_VERIFY = os.environ.get("STORAGE_SSL_VERIFY", "true").strip().lower() not in ("false", "0", "no")

def _ssl_verify_param():
    """Liefert das passende `verify`-Argument fuer requests.* Calls."""
    if not _STORAGE_SSL_VERIFY:
        return False
    if _STORAGE_CA_BUNDLE and os.path.exists(_STORAGE_CA_BUNDLE):
        return _STORAGE_CA_BUNDLE
    return True

# Optional: truststore aktiviert den OS-Zertifikatsstore (Windows, macOS)
# damit Corporate-CAs & System-Roots automatisch gefunden werden.
try:
    import truststore  # type: ignore
    truststore.inject_into_ssl()
    logger.info("[documents] truststore aktiviert (OS-Zertifikatsstore wird verwendet)")
except Exception:
    pass

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
    {"id": "gescannte_fibu_fuer_stb", "name": "gescannte Fibu fuer StB", "icon": "receipt", "color": "emerald"},
    {"id": "kreditkartenabrechnungen", "name": "Kreditkartenabrechnungen", "icon": "receipt", "color": "emerald"},
    {"id": "steuer_bescheide", "name": "Steuer-bescheide", "icon": "receipt", "color": "emerald"},
    {"id": "steuerberater", "name": "Steuerberater", "icon": "receipt", "color": "emerald"},
    {"id": "zahlen_bwa_und_ja", "name": "Zahlen - BWA und JA", "icon": "receipt", "color": "emerald"},
    {"id": "anlagevermoegen", "name": "Anlagevermoegen", "icon": "receipt", "color": "emerald"},
    {"id": "stille_reserven", "name": "Stille Reserven", "icon": "receipt", "color": "emerald"},
    {"id": "lohnabrechnung", "name": "Lohnabrechnung", "icon": "receipt", "color": "emerald"},
    # Versicherungen
    {"id": "versicherungen", "name": "Versicherungen", "icon": "shield", "color": "blue"},
    {"id": "kfz_versicherung", "name": "KFZ Versicherung", "icon": "car", "color": "blue"},
    {"id": "betriebshaftpflicht", "name": "Betriebshaftpflicht", "icon": "shield", "color": "blue"},
    {"id": "berufsgenossenschaft_bg_etem", "name": "Berufsgenossenschaft - BG ETEM", "icon": "shield", "color": "blue"},
    {"id": "krankenkassen", "name": "Krankenkassen", "icon": "shield", "color": "blue"},
    # Verträge & Recht
    {"id": "vertraege", "name": "Vertraege", "icon": "file-text", "color": "fuchsia"},
    {"id": "vertraege_auftraege_mit_dritten", "name": "Vertraege, Auftraege mit Dritten", "icon": "file-text", "color": "fuchsia"},
    {"id": "rahmenvertraege", "name": "Rahmenvertraege", "icon": "file-text", "color": "fuchsia"},
    {"id": "mehrjahresvertraege", "name": "Mehrjahresvertraege", "icon": "file-text", "color": "fuchsia"},
    {"id": "mobilfunkvertraege", "name": "Mobilfunkvertraege", "icon": "file-text", "color": "fuchsia"},
    {"id": "werksvertrag_hb_energy", "name": "Werksvertrag HB Energy", "icon": "file-text", "color": "fuchsia"},
    {"id": "recht_anwalt", "name": "Recht - Anwalt", "icon": "landmark", "color": "purple"},
    {"id": "klagen_rechtsstreit", "name": "Klagen - Rechtsstreit", "icon": "landmark", "color": "purple"},
    {"id": "marken_patent_markenamt", "name": "Marken - eingetragene Marken - Patent-Markenamt", "icon": "landmark", "color": "purple"},
    # Behörden & Institutionen
    {"id": "behoerden", "name": "Behoerden", "icon": "landmark", "color": "purple"},
    {"id": "hwk_handwerkskammer", "name": "HWK - Handwerkskammer", "icon": "landmark", "color": "purple"},
    {"id": "konzessionsausweis_swn", "name": "Konzessionsausweis SWN", "icon": "landmark", "color": "purple"},
    {"id": "unbedenklichkeitsbescheinigungen", "name": "Unbedenklichkeitsbescheinigungen", "icon": "landmark", "color": "purple"},
    {"id": "zoll", "name": "Zoll", "icon": "landmark", "color": "purple"},
    {"id": "wirtschaftsbeirat_andernach", "name": "Wirtschaftsbeirat Andernach", "icon": "landmark", "color": "purple"},
    {"id": "aktionsgemeinschaft_andernach", "name": "Aktionsgemeinschaft Andernach", "icon": "landmark", "color": "purple"},
    # Lieferanten & Partner
    {"id": "lieferscheine_eingehend", "name": "Lieferscheine eingehend", "icon": "truck", "color": "orange"},
    {"id": "lieferscheine_ausgehend", "name": "Lieferscheine ausgehend", "icon": "truck", "color": "orange"},
    {"id": "oel_lieferanten", "name": "Oel-Lieferanten", "icon": "truck", "color": "orange"},
    {"id": "spedition_normann", "name": "Spedition Normann", "icon": "truck", "color": "orange"},
    {"id": "walther_werke", "name": "Walther Werke 10-2025", "icon": "truck", "color": "orange"},
    {"id": "teba", "name": "TEBA", "icon": "truck", "color": "orange"},
    {"id": "kreditreform", "name": "Kreditreform", "icon": "file-text", "color": "orange"},
    {"id": "freelancer", "name": "Freelancer", "icon": "file-text", "color": "orange"},
    # Personal & HR
    {"id": "mitarbeiter", "name": "Mitarbeiter", "icon": "file-text", "color": "amber"},
    {"id": "hr_unterlagen_notarunterlagen", "name": "HR-Unterlagen - Notarunterlagen", "icon": "file-text", "color": "amber"},
    {"id": "unittime_arbeitsueberlassung", "name": "uniTTime - Arbeitsueberlassung", "icon": "file-text", "color": "amber"},
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
    {"id": "pruefberichte", "name": "Pruefberichte", "icon": "file-text", "color": "amber"},
    # Standorte & Unternehmen
    {"id": "halle_andernach", "name": "Halle Andernach", "icon": "landmark", "color": "gray"},
    {"id": "nbr_buero", "name": "NBR - Buero", "icon": "landmark", "color": "gray"},
    {"id": "nbr_flaeche_welcherath", "name": "NBR - Flaeche Welcherath", "icon": "landmark", "color": "gray"},
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
    {"id": "temporaerer_ordner", "name": "temporaerer Ordner", "icon": "folder", "color": "gray"},
    {"id": "sonstiges", "name": "Sonstiges", "icon": "folder", "color": "gray"},
]

storage_key = None

# LOCAL_ONLY_STORAGE: Wenn True, werden ALLE Cloud-Calls uebersprungen und
# Dateien ausschliesslich lokal gespeichert. Standard: True (lokal-first),
# kann per Env-Variable STORAGE_CLOUD_ENABLED=true wieder aktiviert werden.
LOCAL_ONLY_STORAGE = os.environ.get("STORAGE_CLOUD_ENABLED", "false").strip().lower() not in ("true", "1", "yes")

# Wurzelverzeichnis fuer alle lokalen Uploads. Unter dieser Wurzel wird der
# gleiche Pfad erzeugt, den die Cloud-API erwartet. So kann Download sowohl
# lokal als auch aus der Cloud identisch ueber den storage_path zugreifen.
LOCAL_STORAGE_ROOT = os.environ.get(
    "LOCAL_STORAGE_PATH",
    r"C:\eventenergie\Dokumentenablage" if os.name == "nt" else "/app/storage",
)


def _local_path_for(storage_path: str) -> str:
    """Ermittelt den lokalen Dateipfad fuer einen logischen storage_path."""
    rel = storage_path.replace("/", os.sep).lstrip(os.sep)
    return os.path.join(LOCAL_STORAGE_ROOT, rel)


def init_storage():
    global storage_key
    if LOCAL_ONLY_STORAGE:
        return None
    if storage_key:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30, verify=_ssl_verify_param())
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key

def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Speichert eine Datei. Im LOCAL_ONLY-Modus nur lokal, sonst Cloud.

    Aufrufer koennen das Ergebnis ignorieren - wichtig ist nur, dass keine
    Exception fliegt. Der `storage_path` bleibt identisch (logischer Pfad)."""
    if LOCAL_ONLY_STORAGE:
        local_file = _local_path_for(path)
        os.makedirs(os.path.dirname(local_file), exist_ok=True)
        with open(local_file, "wb") as f:
            f.write(data)
        return {"ok": True, "path": path, "local": True}
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120, verify=_ssl_verify_param()
    )
    resp.raise_for_status()
    return resp.json()

def get_object(path: str):
    """Laedt eine Datei. Im LOCAL_ONLY-Modus nur lokal, sonst Cloud (mit lokalem Cache)."""
    if LOCAL_ONLY_STORAGE:
        local_file = _local_path_for(path)
        if not os.path.exists(local_file):
            raise FileNotFoundError(f"Datei nicht lokal vorhanden: {local_file}")
        with open(local_file, "rb") as f:
            data = f.read()
        # Content-Type anhand Dateiendung raten
        ext = os.path.splitext(local_file)[1].lower()
        ct_map = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                  ".png": "image/png", ".webp": "image/webp", ".heic": "image/heic"}
        return data, ct_map.get(ext, "application/octet-stream")
    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60, verify=_ssl_verify_param()
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

RECHNUNGEN (auch international):
- Eingangsrechnungen (von Lieferanten/Dienstleistern an uns) → rechnungseingang_eventenergie_deutschland ODER rechnungseingang_es_besitz_verwaltung (siehe FIRMEN-ZUORDNUNG unten)
- Ausgangsrechnungen (von uns an Kunden) → rechnungsausgang_eventenergie_deutschland ODER rechnungsausgang_es_besitz_verwaltung
- Erkennbar an: Rechnungsnummer, Nettobetrag, MwSt, Zahlungsziel, IBAN
- WICHTIG: Folgende Begriffe bedeuten ebenfalls RECHNUNG (egal in welcher Sprache) und sind IMMER als document_type="rechnung" zu behandeln:
  * Englisch: "Invoice", "Proforma Invoice", "Pro Forma Invoice", "Bill", "Tax Invoice", "Commercial Invoice"
  * Franzoesisch: "Facture", "Facture Pro Forma"
  * Italienisch: "Fattura"
  * Spanisch: "Factura"
  * Niederlaendisch: "Factuur"
- Auch eine PROFORMA-RECHNUNG (Vorab-Rechnung, meist fuer Anzahlungen/Vorauszahlungen) ist eine Rechnung und gehoert in denselben Rechnungseingang-Ordner. Erkennungsmerkmale: Rechnungsnummer, Betrag, IBAN/Bankverbindung, Zahlungshinweis - auch ohne MwSt-Ausweis (typisch bei Auslands-Proforma).
- Bei auslaendischen Absendern (UK, Frankreich, etc.) ist der Empfaenger dennoch typischerweise "Eventenergie Deutschland" oder eine der beiden Firmen - pruefe die Empfaenger-Anschrift sorgfaeltig.

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
3. Wenn der Name "Eventenergie Deutschland", "Eventenergie", "EED" enthaelt (mit oder ohne Rechtsform-Zusatz wie GmbH, GmbH & Co. KG) -> IMMER EED
4. Wenn der Name "ES Besitz", "Besitz und Verwaltung", "ESBV", oder aehnliche Variante enthaelt -> IMMER ES Besitz
5. WICHTIG: Der Rechtsform-Zusatz (GmbH & Co. KG, GmbH etc.) ist NICHT erforderlich fuer die Zuordnung - der Firmenname allein reicht aus.
6. Beide Firmen haben die GLEICHE Adresse (Andernach). Die Adresse ist KEIN Unterscheidungsmerkmal - schau dir ausschliesslich den Firmennamen im Empfaenger/Absender-Feld an.
7. Nur wenn WIRKLICH kein Empfaenger erkennbar ist ODER der Empfaenger eine voellig andere Firma ist: suggested_folder = "unbekannt"
8. Proforma-Rechnungen aus dem Ausland (UK, Frankreich, etc.) an "Eventenergie Deutschland" sind IMMER Eingangsrechnungen der EED - auch wenn keine deutsche USt-IdNr. aufgefuehrt ist.

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
    """Analysiert ein Dokument mit lokalem Ollama (Text-first, Vision-Fallback).

    - PDFs mit extrahierbarem Text -> Gemma 2:2b (reiner Text, ~5-10s)
    - Reine Bilder/Scans -> Gemma 3:1b/4b Vision (~30-180s)
    Gibt ein dict mit suggested_folder, document_type, metadata, full_text, keywords zurueck."""
    from services.ollama_client import analyze_document_smart, parse_json_response

    response_text = ""
    try:
        # Build dynamic folder list for AI prompt
        all_folder_ids = [f["id"] for f in PREDEFINED_FOLDERS]
        extra_hint = ""
        if custom_folders:
            for cf in custom_folders:
                all_folder_ids.append(cf["id"])
            folder_names = ", ".join(f'{cf["name"]}->{cf["id"]}' for cf in custom_folders)
            extra_hint = f"\n- Zusaetzliche benutzerdefinierte Ordner: {folder_names}"

        system = AI_SYSTEM_PROMPT.replace(
            "rechnungseingang|kfz_versicherung|betriebshaftpflicht|vertraege|lieferscheine|behoerden|sonstiges",
            "|".join(all_folder_ids)
        ) + extra_hint

        # Inject custom admin instructions
        custom_instructions = await _get_custom_ai_instructions()
        if custom_instructions:
            system += f"\n\n=== ZUSAETZLICHE ADMIN-ANWEISUNGEN ===\n{custom_instructions}"

        response_text, mode = await analyze_document_smart(
            system_prompt=system,
            file_path=file_path,
            mime_type=mime_type,
            want_json=True,
        )

        logger.info(f"[AI-DEBUG] Mode={mode} Raw response ({len(response_text)} chars): {response_text[:800]}")
        result = parse_json_response(response_text)
        logger.info(f"[AI-DEBUG] Parsed suggested_folder={result.get('suggested_folder')!r}, document_type={result.get('document_type')!r}")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"AI response not valid JSON: {e}, response: {response_text[:500]}", exc_info=True)
        return {"document_type": "sonstiges", "suggested_folder": "sonstiges", "full_text": "", "keywords": []}
    except Exception as e:
        # OllamaUnavailable (Timeout/ConnectError) durchpropagieren, damit der
        # Outer-Handler in _run_ai_analysis das Dokument als 'failed' markiert
        # statt mit leeren Default-Metadaten 'completed' zu faken.
        from services.ollama_client import OllamaUnavailable
        if isinstance(e, OllamaUnavailable):
            raise
        logger.error(f"AI analysis failed: {type(e).__name__}: {e}", exc_info=True)
        return {"document_type": "sonstiges", "suggested_folder": "sonstiges", "full_text": "", "keywords": []}


MONTH_NAMES = {
    1: "Januar", 2: "Februar", 3: "Maerz", 4: "April", 5: "Mai", 6: "Juni",
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

    # Idempotente Anlage via upsert - verhindert Duplikate bei parallelen Uploads
    await db.document_folders.update_one(
        {"id": year_id},
        {
            "$setOnInsert": {
                "id": year_id, "name": str(year), "icon": "folder", "color": "gray",
                "parent_id": parent_folder_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "$set": {"is_deleted": False},
        },
        upsert=True,
    )
    await db.document_folders.update_one(
        {"id": month_id},
        {
            "$setOnInsert": {
                "id": month_id, "name": MONTH_NAMES.get(month, str(month)), "icon": "folder", "color": "gray",
                "parent_id": year_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "$set": {"is_deleted": False},
        },
        upsert=True,
    )

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
        from services.ollama_client import ollama_chat_vision, parse_json_response

        # Get all users from DB
        users = []
        async for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1, "email": 1}):
            users.append(u)
        user_list = ", ".join(f'{u["name"]} (ID: {u["id"]})' for u in users)

        system = f"""Du bist ein Spezialist fuer die Erkennung von Lohnabrechnungen.
Extrahiere aus dem Dokument:
1. Den vollstaendigen Namen des Mitarbeiters
2. Die Personalnummer
3. Den Abrechnungsmonat (YYYY-MM Format)
4. Den Netto-Auszahlungsbetrag

Hier sind die bekannten Mitarbeiter im System:
{user_list}

Ordne den erkannten Namen dem passenden Mitarbeiter zu. Beachte: Kleine Abweichungen (Vorname/Nachname vertauscht, Umlaute) sind moeglich.

Antworte NUR mit JSON:
{{"employee_name": "...", "personnel_number": "...", "month": "YYYY-MM", "net_amount": 0.00, "matched_user_id": "..." oder null falls kein Match, "matched_user_name": "..."}}"""

        user_text = "Analysiere diese Lohnabrechnung und ordne sie einem Mitarbeiter zu."
        file_arg = temp_path if os.path.exists(temp_path) else None
        if file_arg is None:
            # Fallback auf Text aus erster Analyse
            full_text = ai_result.get("full_text", "")
            user_text = f"Analysiere diese Lohnabrechnung und ordne sie einem Mitarbeiter zu:\n\n{full_text}"

        response_text = await ollama_chat_vision(
            system_prompt=system,
            user_text=user_text,
            file_path=file_arg,
            mime_type=content_type if file_arg else None,
            want_json=True,
        )
        payroll_info = parse_json_response(response_text)
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
        logger.error(f"Payroll assignment failed for doc {doc_id}: {type(e).__name__}: {e}", exc_info=True)
        await db.documents.update_one({"id": doc_id}, {"$set": {"payroll_info": {"error": str(e)}}})


async def _run_ai_analysis(doc_id: str, temp_path: str, content_type: str, folder_id: str):
    """Background task to run AI analysis on an uploaded document."""
    try:
        # Warmup-Ping (max OLLAMA_WARMUP_TIMEOUT) - failed schnell wenn Ollama
        # ueberhaupt nicht antwortet. Verhindert dass wir 10min auf einen toten
        # Server warten und das Dokument stillschweigend "completed-mit-leer" wird.
        from services.ollama_client import ollama_warmup_ping, OllamaUnavailable
        ok, msg, elapsed = await ollama_warmup_ping()
        if not ok:
            logger.error(f"[ollama] Warmup-Ping fehlgeschlagen ({elapsed:.1f}s): {msg}")
            raise OllamaUnavailable(f"Warmup-Ping fehlgeschlagen: {msg}")
        if elapsed > 8:
            logger.warning(f"[ollama] Warmup-Ping langsam ({elapsed:.1f}s) - Modell war evtl. evictet, ist jetzt aber wieder warm")

        custom_folders = []
        async for cf in db.document_folders.find({"is_deleted": False}, {"_id": 0}):
            custom_folders.append(cf)
        all_valid_ids = [f["id"] for f in PREDEFINED_FOLDERS] + [cf["id"] for cf in custom_folders]

        ai_result = await analyze_document_with_ai(temp_path, content_type, custom_folders)
        suggested_folder = ai_result.get("suggested_folder", folder_id)

        # ─── ZUGFeRD / Factur-X XML PRIORITAET ─────────────────────────────
        # Wenn das PDF eine eingebettete ZUGFeRD-XML enthaelt, sind diese
        # strukturierten Rechnungsdaten authoritativ. Ollama kann optisch
        # verwirrende Layouts falsch lesen (siehe "von/nach Transport" Bug
        # bei Speditions-Rechnungen). Die XML enthaelt eindeutige Felder.
        if (content_type or "").lower() == "application/pdf":
            try:
                from services.zugferd_parser import try_zugferd_parse, merge_zugferd_into_ai_result
                zugferd_data = await asyncio.to_thread(try_zugferd_parse, temp_path)
                if zugferd_data:
                    logger.info(f"[zugferd] Erkannt - Absender aus XML: {zugferd_data.get('sender')!r}")
                    ai_result = merge_zugferd_into_ai_result(ai_result, zugferd_data)
            except Exception as e:
                logger.warning(f"[zugferd] Parser-Fehler (ueberspringt XML-Merge): {e}")

        # ─── REGEX-FALLBACK fuer Datum und IBAN ────────────────────────────
        # Das LLM ist bei diesen beiden Feldern nicht deterministisch (Sampling)
        # und uebersieht IBANs im Absender-Header wenn Zahlung per PayPal
        # gemacht wurde. Wenn Ollama diese Felder null laesst, versuchen wir
        # eine regex-basierte Extraktion aus dem full_text.
        _full_text = ai_result.get("full_text") or ""
        if _full_text:
            import re as _re
            # -- Datum-Fallback ------------------------------------------------
            _current_date = ai_result.get("date") or ai_result.get("document_date")
            if not _current_date:
                # Bevorzugt Datum in Naehe eines Rechnungs-Keywords
                candidates = []
                for m in _re.finditer(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})", _full_text):
                    day, month, year = m.groups()
                    y = int(year)
                    if y < 100:
                        y = 2000 + y
                    if 1 <= int(day) <= 31 and 1 <= int(month) <= 12 and 2000 <= y <= 2099:
                        # Score: naeher am Wort "Rechnung"/"Datum" ist besser
                        start = max(0, m.start() - 40)
                        context = _full_text[start:m.start()].lower()
                        score = 0
                        if "rechnungs" in context or "datum" in context:
                            score += 10
                        if "lieferdatum" in context:
                            score += 5
                        if "bestellung vom" in context:
                            score += 3
                        candidates.append((score, m.start(), f"{y:04d}-{int(month):02d}-{int(day):02d}"))
                if candidates:
                    candidates.sort(key=lambda x: (-x[0], x[1]))
                    ai_result["date"] = candidates[0][2]
                    ai_result["document_date"] = candidates[0][2]
                    logger.info(f"[regex-fallback] Datum={ai_result['date']} extrahiert (score={candidates[0][0]})")
            # -- IBAN-Fallback -------------------------------------------------
            _current_iban = ai_result.get("iban")
            if not _current_iban:
                # DE-IBAN: DE gefolgt von 20 Ziffern, ggf. mit Leerzeichen zerlegt
                iban_matches = _re.findall(r"DE\s?(?:\d\s?){20}", _full_text)
                if iban_matches:
                    first = iban_matches[0].replace(" ", "")
                    # Zurueck ins DIN-Format mit Leerzeichen alle 4 Zeichen (Standard)
                    formatted = " ".join(first[i:i+4] for i in range(0, len(first), 4))
                    ai_result["iban"] = formatted
                    logger.info(f"[regex-fallback] IBAN={formatted} extrahiert (aus {len(iban_matches)} Kandidaten)")

        # ─── DETERMINISTISCHER FIRMEN-OVERRIDE ──────────────────────────────
        # Bei JEDER Rechnungs-Klassifizierung schauen wir nochmal explizit auf
        # Empfaenger (Eingang) bzw. Absender (Ausgang). Wenn dort eine der
        # beiden Firmen eindeutig identifizierbar ist, ueberschreiben wir die
        # AI-Empfehlung. Das ist robuster als der AI-System-Prompt, weil das
        # Sprachmodell sich gerne mit dem "Hauptkunden" verwirrt.
        doctype = (ai_result.get("document_type") or "").lower()
        recipient_text = " ".join([
            str(ai_result.get("recipient") or ""),
            str(ai_result.get("empfaenger") or ""),
        ]).lower()
        sender_text = " ".join([
            str(ai_result.get("sender") or ""),
            str(ai_result.get("absender") or ""),
        ]).lower()

        def _detect_company(haystack: str) -> str:
            if any(k in haystack for k in ["es besitz", "esbv", "es-besitz", "besitz und verwalt", "besitz- und verwalt"]):
                return "es_besitz_verwaltung"
            if any(k in haystack for k in ["eventenergie deutschland", "eventenergie gmbh", "eed gmbh", " eed ", "eed,"]):
                return "eventenergie_deutschland"
            if "eventenergie" in haystack:
                return "eventenergie_deutschland"
            return ""

        if doctype == "rechnung" and (
            (suggested_folder or "").startswith("rechnungseingang")
            or (suggested_folder or "").startswith("rechnungsausgang")
        ):
            # Eingangsrechnung: Firmen-Hinweis im EMPFAENGER, Ausgang im ABSENDER
            is_eingang = (suggested_folder or "").startswith("rechnungseingang")
            primary = recipient_text if is_eingang else sender_text
            fallback = sender_text if is_eingang else recipient_text
            company = _detect_company(primary) or _detect_company(fallback)
            if company:
                direction = "rechnungseingang" if is_eingang else "rechnungsausgang"
                new_folder = f"{direction}_{company}"
                if new_folder != suggested_folder:
                    logger.info(
                        f"Firmen-Override: {suggested_folder} -> {new_folder} "
                        f"(recipient='{recipient_text[:60]}', sender='{sender_text[:60]}')"
                    )
                    suggested_folder = new_folder

        # Safety: Wenn KI den Rechnungs-Root ohne Firma zurueckgibt, versuchen wir
        # die Firma anhand des AI-Metadaten-Empfaengers/Senders zu ermitteln
        RECHNUNGS_ROOTS_WITHOUT_COMPANY = {"rechnungseingang", "rechnungsausgang"}
        if suggested_folder in RECHNUNGS_ROOTS_WITHOUT_COMPANY:
            direction = "rechnungseingang" if suggested_folder == "rechnungseingang" else "rechnungsausgang"
            # ai_result ist FLACH (kein nested 'metadata'-key) - Felder direkt lesen
            candidate_text = " ".join([
                str(ai_result.get("recipient") or ""),
                str(ai_result.get("empfaenger") or ""),
                str(ai_result.get("sender") or ""),
                str(ai_result.get("absender") or ""),
                str(ai_result.get("firma") or ""),
            ]).lower()
            company = _detect_company(candidate_text)
            if company:
                suggested_folder = f"{direction}_{company}"
                logger.info(f"KI gab {direction} zurueck, Metadaten deuten auf {company} -> {suggested_folder}")
            else:
                logger.info(f"KI gab {direction} ohne erkennbare Firma zurueck -> 'unbekannt'")
                suggested_folder = "unbekannt"

        # Bestimme finale Ablage: Wenn KI sicher ist -> vorgeschlagener Ordner, sonst 'unbekannt'
        final_folder = folder_id
        uncertain = suggested_folder in (None, "", "sonstiges", "unbekannt") or suggested_folder not in all_valid_ids

        # Hat der Firmen-Override oben eingegriffen UND ist die Upload-Ablage
        # eine ANDERE Firma als die jetzt erkannte? Dann das Dokument umziehen,
        # auch wenn der User es manuell in eine bestimmte Firma gelegt hatte
        # (Rechnungen muessen zwingend in der richtigen Firma landen, da DATEV-
        # Versand davon abhaengt). Greift auch wenn der User in den bare-Root
        # 'rechnungseingang' / 'rechnungsausgang' (ohne Firma) hochlaedt.
        if (
            suggested_folder
            and suggested_folder in all_valid_ids
            and (suggested_folder.startswith("rechnungseingang_") or suggested_folder.startswith("rechnungsausgang_"))
            and (
                (folder_id or "") in ("rechnungseingang", "rechnungsausgang")
                or (folder_id or "").startswith(("rechnungseingang_", "rechnungsausgang_"))
            )
        ):
            # Vergleiche Base-Ordner (ohne Jahr/Monat-Suffix)
            def _strip_year_month(fid: str) -> str:
                # rechnungseingang_eventenergie_deutschland_2026_04 -> rechnungseingang_eventenergie_deutschland
                parts = fid.split("_")
                # entferne hinten anhaengende _YYYY[_MM] Suffixe
                while parts and len(parts[-1]) <= 4 and parts[-1].isdigit():
                    parts.pop()
                return "_".join(parts)
            current_base = _strip_year_month(folder_id or "")
            suggested_base = suggested_folder
            if current_base and suggested_base and current_base != suggested_base:
                logger.info(
                    f"Move: Upload-Ordner '{folder_id}' (base={current_base}) ≠ "
                    f"erkannte Firma '{suggested_base}' - Dokument wird verschoben"
                )
                folder_id = suggested_folder        # damit untenstehender Year/Month-Block korrekt arbeitet
                final_folder = suggested_folder

        if folder_id in ("sonstiges", "unbekannt", "rechnungseingang", "rechnungsausgang"):
            if uncertain:
                # AI war unsicher ODER hat year/month-Suffix drangehaengt - versuche Base-Folder
                # zu extrahieren. WICHTIG: sortiere nach Laenge DESC, damit
                # "rechnungseingang_eventenergie_deutschland" vor "rechnungseingang" gewinnt.
                matched_base = None
                for base_folder in sorted(all_valid_ids, key=len, reverse=True):
                    if suggested_folder and suggested_folder.startswith(base_folder + "_"):
                        matched_base = base_folder
                        break
                # Falls der matched_base ein "Root ohne Firma" ist -> unbekannt (Firma nicht erkannt)
                if matched_base in RECHNUNGS_ROOTS_WITHOUT_COMPANY:
                    logger.info(f"KI-Praefix {matched_base} ohne Firmen-Zuordnung -> 'unbekannt'")
                    matched_base = None
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
        # Wichtig: Wenn final_folder bereits ein Year/Month-Subfolder ist und das
        # AI-erkannte Rechnungsdatum NICHT zu diesem Monat passt, korrigieren wir
        # auf den richtigen Monat (Rechnungsdatum hat Vorrang vor Upload-Ordner).
        already_in_subfolder = False
        existing_folder = await db.document_folders.find_one(
            {"id": final_folder, "parent_id": {"$exists": True, "$ne": None}},
            {"_id": 0, "parent_id": 1, "name": 1},
        )
        if existing_folder:
            already_in_subfolder = True

        if already_in_subfolder and final_folder not in SKIP_YEAR_MONTH_FOLDERS:
            # Berechne Base-Folder (z.B. rechnungseingang_eventenergie_deutschland)
            ai_date = (ai_result.get("date") or "").strip()
            if ai_date and len(ai_date) >= 7:
                ai_year = ai_date[:4]
                ai_month = ai_date[5:7]
                # Aktueller Subfolder-Suffix: rechnungseingang_eventenergie_deutschland_2026_04
                #                              -> base = rechnungseingang_eventenergie_deutschland
                def _strip_year_month_2(fid: str) -> str:
                    parts = fid.split("_")
                    while parts and len(parts[-1]) <= 4 and parts[-1].isdigit():
                        parts.pop()
                    return "_".join(parts)
                base = _strip_year_month_2(final_folder)
                expected_subfolder = f"{base}_{ai_year}_{ai_month}"
                if expected_subfolder != final_folder:
                    logger.info(
                        f"Year/Month-Override: AI-Datum {ai_date} passt nicht zu Ordner {final_folder} "
                        f"-> verschiebe nach {expected_subfolder}"
                    )
                    final_folder = base
                    already_in_subfolder = False

        if final_folder not in SKIP_YEAR_MONTH_FOLDERS and not already_in_subfolder:
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
        # BATCH-MODE: Dokument wird jetzt nur als "datev_pending" markiert.
        # Der taegliche Scheduler (services/datev_scheduler.py) verschickt alle
        # pending Rechnungen gesammelt um DATEV_SEND_TIME (Standard: 20:00 Uhr Europe/Berlin).
        if not doc:
            doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
        if doc and _resolve_datev_target(final_folder):
            await db.documents.update_one({"id": doc_id}, {"$set": {
                "datev_pending": True,
                "datev_pending_since": datetime.now(timezone.utc).isoformat(),
            }})
            logger.info(f"Dokument {doc_id} als datev_pending markiert - Versand beim naechsten 20:00-Batch")

        # Auto-assign payroll documents to employees
        if final_folder.startswith("lohnabrechnung"):
            await _assign_payroll_to_employee(doc_id, ai_result, temp_path, content_type)
    except Exception as e:
        import traceback
        from services.ollama_client import OllamaUnavailable
        tb = traceback.format_exc()
        logger.error(f"AI analysis error for doc {doc_id}: {e}\n{tb}")
        # Kategorisierter Fehler im UI: bei Ollama-Unreachable klare Meldung,
        # damit der User weiss dass er einfach "Erneut analysieren" klicken kann
        # sobald Ollama wieder antwortet (Modell-Reload, Netz-Glitch, etc).
        if isinstance(e, OllamaUnavailable):
            error_msg = f"KI-Server nicht erreichbar: {str(e)[:300]}. Bitte spaeter erneut analysieren."
        else:
            error_msg = str(e)[:500]
        await db.documents.update_one({"id": doc_id}, {"$set": {
            "ai_status": "failed",
            "ai_error": error_msg,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})
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

    return await create_document_from_bytes(file_data, file.filename, file.content_type, folder_id)


async def create_document_from_bytes(file_data: bytes, filename: str, content_type: str, folder_id: str = "unbekannt", source: str = "upload"):
    """Internal helper: persist a document from raw bytes and kick off AI analysis.
    Used by the REST upload endpoint AND the Mailbridge service for IMAP attachments."""
    ext = filename.split(".")[-1] if "." in filename else "bin"
    storage_path = f"{APP_NAME}/uploads/{uuid.uuid4()}.{ext}"

    cloud_storage_path = None
    try:
        result = put_object(storage_path, file_data, content_type)
        cloud_storage_path = result["path"]
    except Exception as e:
        logger.warning(f"Cloud storage upload failed (using local fallback): {e}")

    final_storage_path = cloud_storage_path or f"local://{storage_path}"

    doc_id = str(uuid.uuid4())
    doc = {
        "id": doc_id,
        "storage_path": final_storage_path,
        "original_filename": filename,
        "content_type": content_type,
        "size": len(file_data),
        "folder_id": folder_id,
        "ai_status": "pending",
        "ai_metadata": {},
        "full_text": "",
        "keywords": [],
        "is_deleted": False,
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.documents.insert_one(doc)

    # Always save locally as well
    await _save_to_local_storage(file_data, filename, folder_id)

    # Save temp file and start background AI analysis
    temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.{ext}")
    with open(temp_path, "wb") as f:
        f.write(file_data)

    asyncio.create_task(_run_ai_analysis(doc_id, temp_path, content_type, folder_id))

    clean = {k: v for k, v in doc.items() if k != "_id"}
    return clean


@router.post("/{doc_id}/reanalyze")
async def reanalyze_document(doc_id: str):
    """Triggert die KI-Kategorisierung fuer ein bereits hochgeladenes Dokument
    erneut. Laedt die Datei aus Cloud-Storage oder lokaler Ablage und startet
    die Analyse im Hintergrund."""
    doc = await db.documents.find_one({"id": doc_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    storage_path = doc.get("storage_path") or ""
    content_type = doc.get("content_type") or "application/octet-stream"
    ext = (doc.get("original_filename") or "file.bin").split(".")[-1]

    # Datei beschaffen: zuerst lokal, dann Cloud
    file_data = None
    if storage_path.startswith("local://"):
        try:
            local_rel = storage_path.replace("local://", "", 1)
            with open(local_rel, "rb") as f:
                file_data = f.read()
        except Exception:
            file_data = None
    if file_data is None:
        try:
            cloud_path = storage_path.replace("local://", "", 1) if storage_path.startswith("local://") else storage_path
            file_data, _ = get_object(cloud_path)
        except Exception as e:
            logger.warning(f"Reanalyze: Cloud-Download fehlgeschlagen {storage_path}: {e}")

    if not file_data:
        raise HTTPException(status_code=404, detail="Datei nicht auffindbar - Neuanalyse nicht moeglich")

    # In temp speichern und Analyse starten
    temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.{ext}")
    with open(temp_path, "wb") as f:
        f.write(file_data)

    # Status zuruecksetzen, damit UI "Analysiere..." anzeigt
    await db.documents.update_one(
        {"id": doc_id},
        {"$set": {"ai_status": "pending", "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    asyncio.create_task(_run_ai_analysis(doc_id, temp_path, content_type, doc.get("folder_id", "unbekannt")))
    return {"ok": True, "status": "analysis_started"}


@router.post("/cleanup-nested-year-month")
async def cleanup_nested_year_month():
    """Bereinigt fehlerhaft mehrfach verschachtelte Jahr/Monat-Ordner, die durch
    den Reanalyze-Bug entstanden sind (z.B. ...eed_2026_04_2026_04).
    Verschiebt alle Dokumente in die korrekte einfache Year/Month-Struktur und
    loescht die ueberzaehligen Ordner.

    Ausserdem: Dedupliziert doppelte folder-Eintraege (gleiche id, mehrfach in
    der Collection) und legt einen Unique-Index auf der id an."""
    import re

    # 1) Duplikate mit gleichem id bereinigen (behalte den "lebenden" Eintrag)
    dedup_removed = 0
    pipeline = [
        {"$group": {"_id": "$id", "docs": {"$push": "$$ROOT"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
    ]
    async for group in db.document_folders.aggregate(pipeline):
        docs = group["docs"]
        # Behalte einen mit is_deleted=False, loesche die anderen
        alive = [d for d in docs if not d.get("is_deleted")]
        keep = alive[0] if alive else docs[0]
        for d in docs:
            if d.get("_id") == keep.get("_id"):
                continue
            await db.document_folders.delete_one({"_id": d["_id"]})
            dedup_removed += 1

    # 2) Unique-Index auf id anlegen
    try:
        await db.document_folders.create_index("id", unique=True)
    except Exception as e:
        logger.warning(f"Unique-Index auf document_folders.id nicht moeglich: {e}")

    # 3) Verschachtelte Year/Month-Ordner bereinigen (mehrere Passes bis stabil)
    pattern = re.compile(r"^(.+?)_(\d{4})_(\d{2})(?:_\d{4}_\d{2})+$")
    fixed_docs = 0
    deleted_folders = 0
    for _ in range(5):  # max 5 Passes, um tief verschachtelte Ebenen aufzuloesen
        found_any = False
        async for folder in db.document_folders.find({"is_deleted": False}, {"_id": 0}):
            fid = folder.get("id", "")
            m = pattern.match(fid)
            if not m:
                continue
            found_any = True
            base, year, month = m.group(1), m.group(2), m.group(3)
            # base selbst koennte noch verschachtelt sein -> auf ersten nicht-year/month stripen
            while True:
                mb = re.match(r"^(.+?)_(\d{4})_(\d{2})$", base)
                if not mb:
                    break
                base = mb.group(1)
            canonical = f"{base}_{year}_{month}"
            # Sicherstellen, dass der korrekte Ordner existiert
            canonical_folder = await db.document_folders.find_one({"id": canonical, "is_deleted": False})
            if not canonical_folder:
                year_id = f"{base}_{year}"
                await db.document_folders.update_one(
                    {"id": year_id},
                    {"$setOnInsert": {
                        "id": year_id, "name": str(year), "icon": "folder", "color": "gray",
                        "parent_id": base,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }, "$set": {"is_deleted": False}},
                    upsert=True,
                )
                await db.document_folders.update_one(
                    {"id": canonical},
                    {"$setOnInsert": {
                        "id": canonical, "name": MONTH_NAMES.get(int(month), str(int(month))),
                        "icon": "folder", "color": "gray", "parent_id": year_id,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }, "$set": {"is_deleted": False}},
                    upsert=True,
                )
            # Dokumente umziehen
            res = await db.documents.update_many(
                {"folder_id": fid, "is_deleted": False},
                {"$set": {"folder_id": canonical, "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            fixed_docs += res.modified_count
            # Alle Instanzen des kaputten Ordners als geloescht markieren
            res_del = await db.document_folders.update_many(
                {"id": fid}, {"$set": {"is_deleted": True}},
            )
            deleted_folders += res_del.modified_count
        if not found_any:
            break

    # 4) Leere Zwischenordner (reine Jahr/Monat-Struktur) aufraeumen
    year_month_pat = re.compile(r"^.+_\d{4}(_\d{2})?$")
    async for folder in db.document_folders.find({"is_deleted": False}, {"_id": 0}):
        fid = folder.get("id", "")
        if not year_month_pat.match(fid):
            continue
        has_docs = await db.documents.count_documents({"folder_id": fid, "is_deleted": False})
        has_children = await db.document_folders.count_documents({"parent_id": fid, "is_deleted": False})
        if has_docs == 0 and has_children == 0:
            await db.document_folders.update_many({"id": fid}, {"$set": {"is_deleted": True}})
            deleted_folders += 1

    return {"ok": True, "fixed_docs": fixed_docs, "deleted_folders": deleted_folders, "duplicates_removed": dedup_removed}


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


@router.get("/spam-blacklist")
async def get_spam_blacklist():
    """Liste aller gelernten Spam-Absender / Domains fuer die Admin-UI."""
    items = []
    async for e in db.spam_blacklist.find({}, {"_id": 0}).sort("learned_at", -1):
        items.append(e)
    return {"items": items, "count": len(items)}


@router.delete("/spam-blacklist/{entry_id}")
async def delete_spam_blacklist_entry(entry_id: str):
    """Entfernt einen Absender von der Blacklist (falls False-Positive)."""
    r = await db.spam_blacklist.delete_one({"$or": [
        {"sender_email": entry_id},
        {"sender_domain": entry_id},
    ]})
    return {"deleted": r.deleted_count}


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


@router.post("/{doc_id}/mark-as-spam")
async def mark_document_as_spam(doc_id: str):
    """Markiert das Dokument als Spam:
    1. Extrahiert Absender-Email / Domain aus den KI-Metadaten oder dem
       original_filename und speichert diese in der 'spam_blacklist' Collection.
       Kuenftige Mails von dieser Adresse/Domain werden von der Mailbridge automatisch verworfen.
    2. Loescht das Dokument endgueltig (hard delete).
    Effekt: Die KI 'lernt' dazu, indem der Absender geblockt wird.
    """
    doc = await db.documents.find_one({"id": doc_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    # Absenderinfo extrahieren
    meta = doc.get("ai_metadata") or {}
    sender_email = ""
    for key in ("sender_email", "email", "from_email"):
        v = meta.get(key)
        if v and isinstance(v, str) and "@" in v:
            sender_email = v.strip().lower()
            break
    # Fallback: nach E-Mail im full_text suchen
    if not sender_email:
        text = (doc.get("full_text") or "")
        m = re.search(r"[\w\.\-\+]+@[\w\-]+\.[\w\.\-]+", text)
        if m:
            sender_email = m.group(0).lower()

    sender_domain = sender_email.split("@")[-1] if "@" in sender_email else ""
    sender_name = (meta.get("sender_name") or meta.get("sender") or "").strip()

    # Blacklist-Eintrag (idempotent - upsert nach sender_email ODER sender_domain)
    if sender_email or sender_domain:
        entry = {
            "sender_email": sender_email,
            "sender_domain": sender_domain,
            "sender_name": sender_name,
            "learned_from_doc_id": doc_id,
            "learned_at": datetime.now(timezone.utc).isoformat(),
            "hits": 0,
        }
        # Nach Email deduplizieren (wenn vorhanden), sonst nach Domain
        query = {"sender_email": sender_email} if sender_email else {"sender_domain": sender_domain}
        await db.spam_blacklist.update_one(query, {"$setOnInsert": entry}, upsert=True)

    # Dokument endgueltig loeschen (kein soft-delete - Spam braucht keine Historie)
    await db.documents.delete_one({"id": doc_id})

    # Datei aus lokaler Ablage / Cloud entfernen (best-effort)
    try:
        storage_path = doc.get("storage_path", "")
        if storage_path.startswith("local://"):
            local = storage_path.replace("local://", "", 1)
            if os.path.exists(local):
                os.remove(local)
    except Exception as e:
        logger.debug(f"[mark-as-spam] local file cleanup failed: {e}")

    logger.info(
        f"[mark-as-spam] doc {doc_id} als Spam markiert - "
        f"Blacklist: email={sender_email or '-'} domain={sender_domain or '-'}"
    )
    return {
        "status": "spam_marked",
        "sender_email": sender_email,
        "sender_domain": sender_domain,
        "blacklisted": bool(sender_email or sender_domain),
    }


class DocumentMetadataUpdate(BaseModel):
    """Payload fuer PATCH /{doc_id}/metadata - erlaubt manuelle Korrektur
    einzelner AI-erkannter Felder."""
    sender: Optional[str] = None
    recipient: Optional[str] = None
    date: Optional[str] = None
    document_date: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    invoice_number: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None
    subject: Optional[str] = None
    reference: Optional[str] = None
    due_date: Optional[str] = None
    tax_amount: Optional[float] = None
    document_type: Optional[str] = None
    sender_address: Optional[str] = None
    sender_vat: Optional[str] = None


@router.patch("/{doc_id}/metadata")
async def update_document_metadata(doc_id: str, payload: DocumentMetadataUpdate):
    """Manuelles Korrigieren einzelner AI-Metadaten (z.B. Bezeichnung, Sender,
    Betrag). Nur die tatsaechlich gesetzten Felder werden ueberschrieben; andere
    bleiben unveraendert. Setzt zusaetzlich manually_edited=True als Marker."""
    doc = await db.documents.find_one({"id": doc_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return {"status": "no_changes", "ai_metadata": doc.get("ai_metadata", {})}

    # date und document_date synchron halten
    if "date" in updates and "document_date" not in updates:
        updates["document_date"] = updates["date"]
    elif "document_date" in updates and "date" not in updates:
        updates["date"] = updates["document_date"]

    ai_metadata = dict(doc.get("ai_metadata") or {})
    for key, value in updates.items():
        # Leere Strings/None -> Feld entfernen, damit UI klaren Zustand hat
        if value in (None, ""):
            ai_metadata.pop(key, None)
        else:
            ai_metadata[key] = value

    ai_metadata["manually_edited"] = True

    await db.documents.update_one(
        {"id": doc_id, "is_deleted": False},
        {"$set": {
            "ai_metadata": ai_metadata,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"status": "updated", "ai_metadata": ai_metadata, "changed_fields": list(updates.keys())}


@router.get("/{doc_id}/file")
async def download_file(doc_id: str):
    """Download the actual file. Tries cloud storage, then folder-based local path,
    then the flat storage_path cache - and caches cloud successes locally."""
    doc = await db.documents.find_one({"id": doc_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    sp = doc.get("storage_path", "")
    filename = doc["original_filename"]
    content_type = doc.get("content_type", "application/octet-stream")
    data = None

    # Flat cache path (uuid-based, cannot collide, always reachable even if folder changed)
    flat_cache = os.path.join(LOCAL_STORAGE_ROOT, "_cache", sp.replace("local://", "").replace("/", os.sep))

    # 1) Flat cache (fastest)
    if os.path.exists(flat_cache):
        try:
            with open(flat_cache, "rb") as f:
                data = f.read()
        except Exception as e:
            logger.debug(f"Doc {doc_id}: flat cache read failed: {e}")

    # 2) Folder-based local (how the user sees it in Explorer)
    if not data:
        try:
            all_folders = []
            async for cf in db.document_folders.find({"is_deleted": False}, {"_id": 0}):
                all_folders.append(cf)
            for pf in PREDEFINED_FOLDERS:
                all_folders.append({"id": pf["id"], "name": pf["name"], "parent_id": None})
            folder_path = _build_folder_path(doc.get("folder_id", "sonstiges"), all_folders)
            local_file = os.path.join(LOCAL_STORAGE_ROOT, folder_path, filename)
            if os.path.exists(local_file):
                with open(local_file, "rb") as f:
                    data = f.read()
        except Exception as e:
            logger.debug(f"Doc {doc_id}: folder-based local read failed: {e}")

    # 3) Cloud storage (+ opportunistic cache)
    if not data and not sp.startswith("local://"):
        try:
            fetched, ct = get_object(sp)
            data = fetched
            if not content_type or content_type == "application/octet-stream":
                content_type = ct
            try:
                os.makedirs(os.path.dirname(flat_cache), exist_ok=True)
                with open(flat_cache, "wb") as f:
                    f.write(data)
                logger.info(f"Doc {doc_id}: cached cloud file to {flat_cache}")
            except Exception as e:
                logger.debug(f"Doc {doc_id}: local cache write failed: {e}")
        except Exception as e:
            logger.warning(f"Doc {doc_id}: cloud storage fetch failed: {e}")

    if not data:
        logger.error(f"Doc {doc_id}: could not be fetched (all fallbacks failed); storage_path={sp}")
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            # IMPORTANT: do NOT set Cache-Control no-store here - Chrome's PDF viewer
            # needs to be able to cache the response internally, otherwise the iframe
            # preview fails silently (ERR_ABORTED). Keep private to avoid CDN caching.
            "Cache-Control": "private, max-age=60",
        },
    )


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


@router.post("/{doc_id}/save-as-training-sample")
async def save_doc_as_training_sample(doc_id: str, error_description: str = Form("")):
    """Erzeugt aus einem bereits manuell korrigierten Dokument ein
    Trainings-Sample. Die aktuellen (korrigierten) ai_metadata werden als
    'correction' hinterlegt, das Original-File wird beigelegt, damit
    kuenftig Prompt-Tuning bzw. Few-Shot-Beispiele damit gefuettert werden
    koennen."""
    import base64
    doc = await db.documents.find_one({"id": doc_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    ai_metadata = doc.get("ai_metadata") or {}
    if not ai_metadata.get("manually_edited"):
        raise HTTPException(status_code=400, detail="Dokument wurde nicht manuell korrigiert - kein Trainings-Sample noetig")

    # File-Content aus lokalem Storage lesen (Cloud-Storage optional laden)
    file_bytes = b""
    local_path = _local_path_for(doc.get("storage_path", ""))
    if local_path and os.path.exists(local_path):
        try:
            with open(local_path, "rb") as fh:
                file_bytes = fh.read()
        except Exception as e:
            logger.warning(f"[training-sample] local read failed: {e}")
    # Falls kein lokaler Bytes gefunden, Cloud-Storage versuchen
    if not file_bytes and doc.get("storage_path"):
        try:
            file_bytes, _ct = await asyncio.to_thread(get_object, doc["storage_path"])
        except Exception as e:
            logger.warning(f"[training-sample] cloud read failed: {e}")

    if not file_bytes:
        raise HTTPException(status_code=500, detail="Datei konnte nicht geladen werden")

    corrections = {k: v for k, v in ai_metadata.items() if k != "manually_edited"}
    error_desc = error_description.strip() or (
        f"Manuelle Korrektur: {doc.get('original_filename','')} - "
        f"Zielordner {doc.get('folder_id','')}"
    )

    sample_id = str(uuid.uuid4())
    sample = {
        "id": sample_id,
        "filename": doc.get("original_filename", "document.pdf"),
        "content_type": doc.get("content_type", "application/pdf"),
        "file_data": base64.b64encode(file_bytes).decode("utf-8"),
        "file_size": len(file_bytes),
        "error_description": error_desc,
        "correction": json.dumps(corrections, ensure_ascii=False, indent=2),
        "source_doc_id": doc_id,
        "target_folder_id": doc.get("folder_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_training_samples.insert_one(sample)
    return {"id": sample_id, "filename": sample["filename"], "status": "created"}
