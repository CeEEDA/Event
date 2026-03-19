# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap

## What's Been Implemented

### Phase 1 - Portal Grundfunktionen (abgeschlossen)
- Benutzerauthentifizierung (JWT)
- Auftragsverwaltung (EpiRent-Integration)
- Energiemonitoring (MQTT)
- Zahlungsabwicklung (Stripe)
- QR-Code-System fuer Kirmeskisten
- Rechnungserstellung (PDF)
- Admin-Einstellungen
- Desktop App (Electron)

### Phase 1b - Tankbeleg Portal UI (abgeschlossen)
- Tankbeleg-Verwaltung in OrderDetailPage.js
- CRUD, PDF, Auto-Nummerierung, GPS-Karte, Admin-Funktionen

### Phase 1c - EpiRent API Optimierung (abgeschlossen)
- Background-Sync, Cache, Manueller Sync, Adress-Ueberschreibung

### Phase 2 - Tankbeleg Pi Script (abgeschlossen)
- tankbeleg_pi.py + tankbeleg_simulator.py (48 Tests)
- ESC/POS Parser, Serial, GPS, SQLite, Auto-Sync

### Self-Hosted MQTT Broker (abgeschlossen)
- setup_mosquitto.sh + mosquitto_eventenergie.conf
- Let's Encrypt TLS, 3 Listener (8883, 9883, 1883)

### Serviceplan Anpassungen (abgeschlossen - 2026-03-19)
- Messkoffer/Kirmeskiste: Reduzierter Plan (nur Elektrisch + Diagnose)
- PDF + Bilder Upload in Wartungseintraegen (max 25 MB)
  - Sektion umbenannt: "Anhänge (Fotos & Dokumente)"
  - Backend: attachments Array mit Metadaten (id, filename, content_type, size)
  - Frontend: PDFs als Download-Link mit Icon, Bilder als Thumbnails
  - Drag & Drop fuer PDFs und Bilder
  - Größenvalidierung (25 MB) mit Fehlermeldung

## Prioritized Backlog

### P1 - Kommend
- PayPal Integration
- Direkter QR-Label-Druck an Drucker
- Windows Installer (.exe) fuer Electron Desktop App

### P2 - Backlog
- Admin File Size Limits fuer Uploads

## Credentials
- **Admin (lokal):** admin@test.com / password
- **Admin (Server):** christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
