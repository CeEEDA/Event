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
- Auth, Auftragsverwaltung, Energiemonitoring, Zahlungen, QR, Rechnungen, Admin, Desktop

### Phase 1b - Tankbeleg Portal UI (abgeschlossen)
- CRUD, PDF, Auto-Nummerierung, GPS-Karte, Admin-Funktionen

### Phase 1c - EpiRent API Optimierung (abgeschlossen)
- Background-Sync, Cache, Manueller Sync, Adress-Ueberschreibung

### Phase 2 - Tankbeleg Pi Script (abgeschlossen)
- ESC/POS Parser, Serial, GPS, SQLite, Auto-Sync, 48 Tests

### Self-Hosted MQTT Broker (abgeschlossen)
- Mosquitto + Let's Encrypt TLS, 3 Listener

### Serviceplan Anpassungen (abgeschlossen)
- Messkoffer/Kirmeskiste: Reduzierter Plan
- PDF + Bilder Upload (max 25 MB)

### Artikel positionieren - Status & Detail (abgeschlossen - 2026-03-19)
- **Zeilen-Farbe**: Magenta-Hintergrund wenn Artikel gestellt, normal wenn abgebaut
- **"Abgebaut"-Button**: Toggle-Button in jeder Zeile (gestellt <-> abgebaut)
- **Detail-Modal**: Klick auf Zeile oeffnet Modal mit:
  - OpenStreetMap-Karte mit genauem Standort
  - Gestellt von (Name) und Gestellt am (Datum/Uhrzeit)
  - Koordinaten + Plus Code
  - Aktueller Status (gestellt/abgebaut)
  - Link "In Google Maps oeffnen"
- **Backend**: PATCH /api/orders/epirent/{pk}/assets/{id}/status Toggle-Endpoint
- **Status-Zaehler**: "X gestellt · Y abgebaut" in der Sektions-Kopfzeile
- Leaflet Marker-Icon Fix fuer Karte

## Key API Endpoints
- `/api/orders/epirent/{pk}/assets` - GET/POST Assets
- `/api/orders/epirent/{pk}/assets/{id}/status` - PATCH Toggle Status
- `/api/fuel-receipts/sync` - Pi-Sync
- `/api/download/tankbeleg-pi-bundle` - Pi-Script ZIP
- `/api/download/mosquitto-bundle` - Mosquitto ZIP

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
