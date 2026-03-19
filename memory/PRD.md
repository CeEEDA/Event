# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB
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

### Serviceplan Anpassung (abgeschlossen - 2026-03-19)
- Messkoffer und Kirmeskiste: Reduzierter Serviceplan
  - Nur Elektrische Pruefung + Diagnose + Bemerkungen/Fotos/Notizen
  - Sektionen 1 (Mechanisch), 3 (Messwerte), 4 (Lasttest), 5 (ATS) ausgeblendet
- Stromerzeuger und Lichtmast: Weiterhin alle 6 Sektionen
- Dynamische Nummerierung (1, 2 statt 2, 6)
- Betrifft Formular und Anzeige gespeicherter Eintraege

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
