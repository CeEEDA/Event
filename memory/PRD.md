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
- Firmenlogo auf PDF-Belegen

### Phase 1c - EpiRent API Optimierung (abgeschlossen)
- Background-Sync mit konfigurierbarem Intervall
- Lokaler Cache (orders_cache Collection)
- Manueller Sync-Button
- Manuelle Adress-Ueberschreibung (Workaround fuer EpiRent API)

### Phase 2 - Tankbeleg Pi (abgeschlossen - 2026-03-19)
- **tankbeleg_pi.py:** Raspberry Pi Script
  - ESC/POS Druckdaten-Parser fuer Epson TM-U295 / Sening MultiFlow
  - Serielle Schnittstelle (USB-zu-RS232) mit reconnect
  - GPS-Erfassung via gpsd
  - SQLite Offline-Pufferung
  - Auto-Sync mit Portal (/api/fuel-receipts/sync)
  - Konfiguration via /etc/tankbeleg_pi.conf und Env-Variablen
- **tankbeleg_simulator.py:** Test-Suite + Drucker-Simulator
  - ESC/POS Receipt Generator (nachbildet Sening MultiFlow Output)
  - 48 Unit-Tests (Parser, Storage, Sync, Virtual Serial, Live API)
  - Virtuelle serielle Ports via socat
  - Live-API-Sync-Test gegen Portal
- **tankbeleg_pi.conf / .service / setup.sh:** Config, Systemd, Installer
- Download-Bereich in Admin-Einstellungen (ZIP-Bundle mit Simulator)
- Messgeraet: Sening MultiFlow (SFF09003GE), RS232 zum Epson TM-U295

### Refactoring (2026-03-19)
- FuelReceiptsPage.js geloescht (Funktionalitaet in OrderDetailPage)
- Route /fuel-receipts aus App.js entfernt
- MQTT-Issue bestaetigt: Kein hardcoded URL im Produktionscode

## Key DB Schema
- **fuel_receipts:** `{id, order_pk, beleg_nr, zaehler_nr, fuel_type, quantity_liters, original_quantity_liters, adjustment_percent, location, fahrer, receipt_date, gps_lat, gps_lon, pi_local_id, source, ...}`
- **orders_cache:** `{...epirent_order_data, address, address_source}`
- **manual_address_overrides:** `{order_pk, address}`

## Key API Endpoints
- `/api/fuel-receipts/by-order/{pk}` - Belege pro Auftrag
- `/api/fuel-receipts/sync` - Pi-Sync (ohne Auth)
- `/api/fuel-receipts/pdf/all/{pk}` - Sammel-PDF
- `/api/fuel-receipts/adjust/{pk}` - Mengenanpassung
- `/api/orders/sync/trigger` - EpiRent Sync manuell
- `/api/orders/{pk}/address-override` - Adress-Ueberschreibung
- `/api/download/tankbeleg-pi-bundle` - Pi-Script ZIP-Download

## Prioritized Backlog

### P1 - Kommend
- PayPal Integration
- Direkter QR-Label-Druck an Drucker
- Windows Installer (.exe) fuer Electron Desktop App

### P1 - Spaeter
- Self-Hosted MQTT Broker (Mosquitto)

### P2 - Backlog
- Admin File Size Limits fuer Uploads

## Credentials
- **Admin (lokal):** admin@test.com / password
- **Admin (Server):** christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
