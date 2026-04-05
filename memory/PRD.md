# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung, Dokumentenverwaltung, Team Chat und Aufgabenverwaltung.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe, MQTT, OpenStreetMap, Gemini 2.5 Flash (KI)
- **Object Storage:** Emergent Object Storage
- **DATEV:** Automatische Weiterleitung an uploadmail.datev.de

## What's Been Implemented

### Team Chat & Aufgabenverwaltung - FERTIG (2026-04-05)
- Direktnachrichten zwischen allen Benutzern
- Gruppenchats (nur Admin kann erstellen)
- Echtzeit-Polling (4 Sekunden)
- Datei-/Bildanhänge im Chat (Object Storage)
- Ungelesene-Nachrichten-Zähler (Badge)
- Aufgaben mit Prioritäten (Hoch/Mittel/Niedrig)
- Fälligkeitsdaten mit Überfällig-Anzeige
- Aufgaben anderen Benutzern zuweisen
- Filter: Meine / Erstellt / Alle (Admin)
- Aufgaben erledigen / wiederherstellen / löschen
- Hub-Seite kompakt redesigned (Icon-Grid + Aufgaben-Panel)
- 17/17 Backend + 100% Frontend Tests bestanden

### Dokumentenverwaltung mit KI - FERTIG (2026-04-04/05)
- 66+ Masterordner, hierarchische Unterordner-Struktur
- KI-Erkennung via Gemini 2.5 Flash (asynchron)
- Automatische DATEV-Weiterleitung
- Drag & Drop Upload, Volltextsuche
- PDF-Vorschau inline per iframe
- Detail-Sidebar als Overlay-Panel
- KI-Training im Admin (custom Anweisungen)

### Auto-Speicherung Portal-Rechnungen - FERTIG (2026-04-05)
### Mitarbeiter-Berechtigungen (Finance + Dokumentenverwaltung) - FERTIG
### SchaustellerAnmeldungPage Refactoring - FERTIG (14 Subkomponenten)
### Multi-Anschluss Buchung, Kaution, Sammelrechnung - FERTIG
### Lastdiagramm Feature - FERTIG

## Key API Endpoints
### Chat & Tasks
- GET /api/chat/conversations?token=...
- POST /api/chat/conversations?token=...
- GET /api/chat/conversations/{id}/messages?token=...
- POST /api/chat/conversations/{id}/messages?token=... (FormData)
- GET /api/chat/conversations/{id}/file/{att_id}?token=...
- GET /api/chat/users?token=...
- GET /api/chat/tasks?token=...&filter=mine|created|all
- POST /api/chat/tasks?token=...
- PUT /api/chat/tasks/{id}?token=...
- DELETE /api/chat/tasks/{id}?token=...

### Documents
- POST /api/documents/upload
- GET /api/documents/folders
- GET/PUT /api/documents/ai-settings

## DB Collections
- chat_conversations: {id, type, name, members[], last_message, created_by, ...}
- chat_messages: {id, conversation_id, sender_id, sender_name, text, attachment, read_by[], ...}
- tasks: {id, title, description, priority, priority_order, due_date, completed, created_by, assigned_to, ...}

## Prioritized Backlog
### P1
- Microsoft 365 Postfach-Anbindung
- PayPal/Kreditkarten Integration

### P2
- Chromium Kiosk, Windows Installer, GPS-Support
- Admin Dateigroessen-Limits
- DSE890 Gateway GSM (SIM-Karten)
