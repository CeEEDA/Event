# DSE Power Generator Portal – PRD

## Original Problem Statement
Comprehensive monitoring and management portal for DSE power generators with EpiRent ERP integration, energy monitoring, fleet management, and Kirmes billing system.

## Tech Stack
- **Backend**: FastAPI, Python, MongoDB (Motor), GridFS, paho-mqtt, httpx, bcrypt, reportlab, pdfrw, factur-x, qrcode
- **Frontend**: React, Tailwind CSS, Shadcn/UI, Recharts, Leaflet/OpenStreetMap, open-location-code, jspdf, jspdf-autotable
- **Pi Skripte**: pymodbus (Modbus TCP), requests, sqlite3

## What's Been Implemented

### Kirmeskiste Anbindung (2026-03-08)
- **kirmeskiste_sync.py**: Pi-Skript liest 4x EMU Professional II 3/5 via Modbus TCP
  - Modbus Register: Leistung (9000-9006), Strom (9100-9106), Spannung (9200-9204), Power Factor (9300-9304), Frequenz (9310), Energie (7000/7020), Stromausfaelle (11000)
  - Lokale SQLite-Zwischenspeicherung mit Batch-Sync zum Portal
  - Automatische Wiederverbindung bei Netzwerkausfaellen
- **setup_kirmeskiste.sh**: Vollautomatisches Pi-Setup (systemd, venv, Konfiguration)
- **QR-Code System**: Generiert druckbare QR-Labels (A6 PDF) fuer jeden Zaehler
  - QR verlinkt zu /kirmes/meter-zuordnung/{meterId} im Portal
  - Admin scannt QR -> waehlt Anmeldung -> Zaehler wird zugewiesen
- **Meter-Zuordnungsseite**: Zeigt Zaehler-Info, aktuelle Zuweisung, offene Anmeldungen

### Dokumentenablage pro Veranstaltung (2026-03-08)
- Upload per Drag & Drop (PDF, JPG, PNG, WebP, GIF, max 20MB)
- Bildvorschau-Galerie mit Zoom-Modal
- PDF-Liste mit Vorschau, Download, Loeschen
- Neue Seite: /kirmes/{id}/dokumente
- Card auf Event-Detailseite mit Dokumentenzaehler
- Backend: CRUD auf /api/kirmes/events/{id}/documents
- Dateispeicher: /app/storage/event_documents/{event_id}/

### Kamera-basierter QR-Scanner (2026-03-08)
- Dropdown fuer Zaehler-Zuweisung ersetzt durch Kamera-QR-Scanner (html5-qrcode)
- Primaer: "QR-Code scannen" Button oeffnet Kamera, scannt Label am Stromverteiler
- Fallback: Manuelles Dropdown bleibt als Alternative
- Extrahiert meter_id aus URL und ruft POST /api/kirmes/meters/{id}/assign-signup auf
- QrScanner-Komponente: frontend/src/components/QrScanner.jsx

### ZUGFeRD E-Rechnungen (2026-03-08)
- PDF-Rechnungen mit eingebetteter factur-x.xml (Basic Profil, XSD-validiert)

### Kirmes: EMU Meter Data Integration (2026-03-08)
- Link/unlink EMU meters to signups, live data display, power chart

### Kirmes: Abrechnungsmodul (2026-03-08)
- Invoice generation with letterhead, batch billing, email sending

## Key New API Endpoints

### Kirmeskiste QR System
- `GET /api/kirmes/meters/{id}/qr-code` - QR-Code als PNG
- `GET /api/kirmes/meters/{id}/qr-label` - Druckbares QR-Label als PDF (A6)
- `GET /api/kirmes/meters/{id}/info` - Zaehler-Info mit Zuweisungen
- `POST /api/kirmes/meters/{id}/assign-signup` - Zaehler einer Anmeldung zuweisen

## Pi-Skripte (zum Download unter /static/)
- `kirmeskiste_sync.py` - Sync-Skript fuer Kirmeskiste
- `setup_kirmeskiste.sh` - Auto-Setup fuer Raspberry Pi
- `emu_sync.py` - Sync-Skript fuer Messkoffer (Shelly Pro 4EM)

## Backlog

### P0 (Next)
- MQTT Broker URL -> .env Refactoring (hardcoded in mqtt_service.py)
- Stripe Integration fuer Kaution-Zahlung

### P1
- SMTP-Anbieter Upgrade (mail.de Tageslimit)
- Self-hosted MQTT Broker (Mosquitto)
- Direkter QR-Label-Druck (Print-Button statt PDF)

### P2
- Admin File Size Limits

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
