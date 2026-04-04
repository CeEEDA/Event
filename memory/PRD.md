# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung, Dokumentenverwaltung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap, Gemini 2.5 Flash (KI-Dokumentenerkennung)
- **Object Storage:** Emergent Object Storage (fuer Dokumentenablage)

## What's Been Implemented

### Dokumentenverwaltung mit KI-Erkennung - FERTIG (2026-04-04)
- Neuer Bereich unter Verwaltung -> Dokumentenverwaltung
- 7 vordefinierte Ordner: Rechnungseingang, KFZ Versicherung, Betriebshaftpflicht, Vertraege, Lieferscheine, Behoerden, Sonstiges
- Upload von PDF, JPEG, PNG, WebP, TIFF (max 50 MB)
- **KI-Erkennung via Gemini 2.5 Flash:**
  - Automatische Dokumententyp-Erkennung
  - Metadaten-Extraktion: Absender, Empfaenger, Datum, Betrag, MwSt, Rechnungsnummer, Referenz, IBAN, Faelligkeitsdatum
  - Automatische Ordnerzuordnung (z.B. Versicherungsschreiben -> KFZ Versicherung)
  - Volltext-Extraktion fuer Suchindex
  - Stichwort-Generierung
- **Volltextsuche:** Suche ueber Verwendungszweck, Firmenname, IBAN, Rechnungsnummer, Referenz
- Dokumente verschieben zwischen Ordnern
- Detail-Sidebar mit allen KI-Metadaten, Bild-Vorschau, extrahiertem Text
- Drag & Drop Upload-Unterstuetzung
- Backend: /api/documents/* (CRUD, Upload, Suche, KI-Analyse)
- Frontend: /verwaltung/dokumente
- 100% Tests bestanden (iteration_57: Backend 21/21, Frontend alle Features verifiziert)

### SchaustellerAnmeldungPage Refactoring - FERTIG (2026-04-04)
- Datei von 1400+ Zeilen in 14 Subkomponenten aufgeteilt
- Ordner: /app/frontend/src/pages/schausteller/
- 100% Frontend-Tests bestanden (iteration_56)

### Multi-Anschluss Buchung - FERTIG
### Zahlungsmittel & Kaution - FERTIG
### Wohnwagen-Preise korrekt - FERTIG
### Kombinierte Rechnung (Sammelrechnung) - FERTIG
### Bestaetigungsseite - FERTIG
### Lastdiagramm Feature - FERTIG

## Key API Endpoints
- POST /api/documents/upload (Upload + KI-Analyse)
- GET /api/documents/folders (Ordner mit Dokumentanzahl)
- GET /api/documents/list?folder_id=... (Dokumentenliste)
- GET /api/documents/search?q=... (Volltextsuche)
- GET /api/documents/{id} (Dokumentdetails mit Volltext)
- PUT /api/documents/{id}/move?folder_id=... (Verschieben)
- DELETE /api/documents/{id} (Soft-Delete)
- GET /api/documents/{id}/file (Datei-Download)
- POST /api/kirmes/public/signup
- GET /api/kirmes/public/my-bookings
- POST /api/kirmes/admin/invoices/generate/event/{event_id}

## Prioritized Backlog

### P1 - Kommend
- Microsoft 365 Postfach-Anbindung (IMAP/Graph API) fuer automatischen Dokumenteneingang
- DATEV Unternehmen Online Export fuer erkannte Rechnungen
- PayPal/Kreditkarten Integration
- Lastdiagramm Live-Test mit verknuepften EMU-Zaehlern

### P2 - Backlog
- Chromium Translate Popup auf Raspberry Pi
- Admin File Size Limits fuer Uploads
- Windows Installer fuer Electron Desktop App
- GPS-Support fuer Kirmeskiste

### Blocked
- DSE890 Gateway GSM (wartet auf neue SIM-Karten)
- Lastdiagramm Live-Test (braucht verknuepfte EMU-Zaehler mit Messdaten)
