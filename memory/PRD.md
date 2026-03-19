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
- Tankbeleg-Verwaltung direkt in OrderDetailPage.js integriert
- CRUD fuer Tankbelege (erstellen, bearbeiten, loeschen)
- PDF-Generierung (Einzelbeleg + Sammel-PDF pro Auftrag)
- Automatische Belegnummerierung (X12000, X12001, ...)
- GPS-Karten-Modal fuer Belegstandorte
- Admin-Funktionen: Liter-Zusammenfassung, %-Mengenanpassung

### Phase 1c - EpiRent API Optimierung (abgeschlossen)
- Background-Sync mit konfigurierbarem Intervall
- Lokaler Cache (orders_cache Collection)
- Manueller Sync-Button
- Manuelle Adress-Ueberschreibung

### Phase 2 - Tankbeleg Pi Script (abgeschlossen - 2026-03-19)
- tankbeleg_pi.py: ESC/POS Parser, Serial, GPS, SQLite, Auto-Sync
- tankbeleg_simulator.py: 48 Unit-Tests + Drucker-Simulator
- Config, Systemd, Setup-Script, Download im Admin-Bereich

### Self-Hosted MQTT Broker (abgeschlossen - 2026-03-19)
- setup_mosquitto.sh: Interaktives Installations-Script
  - Mosquitto + Certbot (Let's Encrypt) Installation
  - TLS-Zertifikate automatisch anfordern und erneuern
  - Benutzer-Authentifizierung (Gateway + Portal User)
  - Firewall-Konfiguration (UFW)
  - Verbindungstest nach Installation
- mosquitto_eventenergie.conf: 3 Listener
  - Port 8883: MQTTS (TLS) - oeffentlich fuer DSE Webnet Gateways
  - Port 9883: WebSockets (TLS) - fuer Web-Dashboard
  - Port 1883: Lokal ohne TLS - fuer Portal-Backend
- Download-Bereich in Admin-Einstellungen (ZIP-Bundle)
- Let's Encrypt Auto-Renewal mit Mosquitto-Restart-Hook

## Key DB Schema
- **fuel_receipts:** `{id, order_pk, beleg_nr, zaehler_nr, fuel_type, quantity_liters, ...}`
- **orders_cache:** `{...epirent_order_data, address, address_source}`
- **mqtt_config:** `{enabled, broker_url, broker_port, username, password, use_tls, ...}`

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
