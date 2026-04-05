# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung, Dokumentenverwaltung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap, Gemini 2.5 Flash (KI-Dokumentenerkennung)
- **Object Storage:** Emergent Object Storage (fuer Dokumentenablage)
- **DATEV:** Automatische Weiterleitung an uploadmail.datev.de

## What's Been Implemented

### Dokumentenverwaltung mit KI - FERTIG (2026-04-04/05)
- 66+ Masterordner (branchenspezifisch fuer Eventenergie)
- Hierarchische Unterordner-Struktur (aufklappbarer Baum)
- Automatische Jahr/Monat-Unterordner bei Rechnungsein-/ausgang
- Manuelle Unterordner-Erstellung per + Button
- Unterordner umbenennen/loeschen (custom), Systemordner geschuetzt
- KI-Erkennung via Gemini 2.5 Flash (asynchron, branchenspezifisch)
- Automatische DATEV-Weiterleitung bei Eingangsrechnungen
- Ausgangsrechnungen (Portal) BCC an DATEV statt Accounting
- Drag & Drop Upload-Zone
- Volltextsuche ueber alle Metadaten
- Detail-Sidebar mit KI-Metadaten, DATEV-Status

### Auto-Speicherung Portal-Rechnungen - FERTIG (2026-04-05)
- Einzelrechnung (generate_invoice_for_signup) speichert PDF automatisch in Rechnungsausgang/Jahr/Monat
- Batch-Rechnung (generate_all_invoices) speichert PDF automatisch in Rechnungsausgang/Jahr/Monat
- Lokale Kopie + Object Storage + MongoDB documents Collection
- Bug-Fix: tax_amount Feld korrigiert (mwst -> mwst_amount)

### Mitarbeiter-Berechtigungen (Finance + Dokumentenverwaltung) - FERTIG (2026-04-05)
- Finance Toggle in AdminPage Benutzerbearbeitung
- Dokumentenverwaltung Toggle in AdminPage Benutzerbearbeitung
- ProtectedRoute erweitert mit requiredApp-Prop
- VerwaltungPage filtert Navigation basierend auf Benutzerberechtigungen
- Leere-Seite-Hinweis wenn keine Berechtigungen vorhanden
- 12/12 Backend-Tests + alle Frontend-Tests bestanden

### SchaustellerAnmeldungPage Refactoring - FERTIG (2026-04-04)
- 14 Subkomponenten in /pages/schausteller/

### Multi-Anschluss Buchung, Kaution, Sammelrechnung - FERTIG
### Lastdiagramm Feature - FERTIG

## Key API Endpoints
- POST /api/documents/upload (Async Upload + Background KI)
- GET /api/documents/folders (Hierarchischer Baum mit Counts)
- POST /api/documents/folders (Ordner/Unterordner erstellen)
- PUT /api/documents/folders/{id} (Umbenennen)
- DELETE /api/documents/folders/{id} (Loeschen)
- GET /api/documents/list?folder_id=...&include_children=true
- GET /api/documents/search?q=...
- GET /api/documents/{id} (Detail mit Volltext)
- GET /api/documents/{id}/file (Download)
- PUT /api/documents/{id}/move?folder_id=...
- PUT /api/users/{id} (User-Update mit apps.finance, apps.dokumentenverwaltung)

## Prioritized Backlog
### P0 (Erledigt)
- Auto-Speicherung Portal-Rechnungen in Dokumentenverwaltung
- Finance + Dokumentenverwaltung Berechtigungen

### P1
- Microsoft 365 Postfach-Anbindung (IMAP/Graph API)
- PayPal/Kreditkarten Integration
- Lastdiagramm Live-Test

### P2
- Chromium Kiosk, Windows Installer, GPS-Support
- Admin Dateigroessen-Limits fuer Uploads
- Blocked: DSE890 Gateway GSM (SIM-Karten)
