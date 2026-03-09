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

### Admin Zahlungs-Dashboard (2026-03-08)
- Neue Seite: /kirmes/zahlungen
- KPI-Karten: Kautionen/Rechnungen bezahlt/offen (Anzahl + EUR-Betraege)
- Gesamteinnahmen, Veranstaltungs-Uebersicht mit Zahlungsstand
- Transaktionsliste mit "Link senden" Button (erstellt Stripe-Link, sendet per Mail)
- Filter nach Veranstaltung
- Payment-Summary-Card auf Event-Detailseite
- "Zahlungen" Button im KirmesPage Header (nur Admin)
- Backend: GET /api/payments/dashboard, /dashboard/events, POST /send-payment-link
- GiroCode (EPC QR Code) in Rechnungs-PDFs: COMPANY_IBAN und COMPANY_BIC in .env setzen
- Mobile-responsive (390px iPhone)

### Stripe Payment Integration (2026-03-08)
- Kaution nach Anmeldung per Stripe Checkout (abhaengig vom Anschlusstyp)
- Standard-Kautionsbetraege: Schuko=50€, 16A=100€, 32A=200€, 63A=400€, 125A=800€
- Admin kann Kautionsbetraege konfigurieren (GET/PUT /api/payments/deposits/config)
- Rechnungszahlung per Stripe Checkout (POST /api/payments/checkout/invoice)
- Status-Polling nach Stripe-Rueckkehr (GET /api/payments/checkout/status/{session_id})
- Webhook-Handler (POST /api/payments/webhook/stripe)
- Transaktionsuebersicht fuer Admin (GET /api/payments/transactions)
- Frontend: Payment-Step nach Signup, "Jetzt bezahlen" + "Spaeter bezahlen"
- Backend: /app/backend/routes/payments.py
- Uses emergentintegrations Stripe checkout library

### P0 Fix: Zahlungslogik korrigiert (2026-03-09)
- Buchungen werden bei Kartenzahlung/PayPal mit Status 'pending_payment' erstellt
- Bestaetigung + E-Mail erst nach erfolgreicher Stripe-Zahlung (Webhook/Polling)
- 'Kauf auf Rechnung' wird sofort bestaetigt (Status 'ausstehend')
- Frontend: Korrekte Step-Weiterleitung basierend auf payment_status
- Sicherheitsfix: password_hash aus Signup-Response entfernt
- Bug behoben: payments.py nutzte falsche Collection 'schausteller' statt 'kirmes_schausteller'

### E-Mail-Konfiguration in Admin-Einstellungen (2026-03-09)
- SMTP-Zugangsdaten (Host, Port, User, Passwort, Absendername) editierbar
- Sofortige Uebernahme ohne Neustart (os.environ + MongoDB Persistenz)
- Verbindungstest-Button zum Pruefen der SMTP-Verbindung
- Automatisches Laden der DB-Konfiguration beim Serverstart
- Min. 8 Zeichen, 1 Ziffer, 1 Grossbuchstabe, 1 Kleinbuchstabe, 1 Sonderzeichen
- Backend: _validate_password() in kirmes.py (public + staff endpoints)
- Frontend: Live-Feedback mit Haekchen im Passwort-Formular
- Passwort fuer christian.ecker@eventenergie-deutschland.de zurueckgesetzt


### Zaehlerdaten-Detailseite (2026-03-08)
- Neue Seite: /kirmes/{eventId}/zaehler/{signupId}
- Live-Metriken: Leistung, Strom, Spannung, Energie, Frequenz
- Charts: Leistungsverlauf, Stromverlauf, Energieverbrauch (Recharts)
- CSV-Export im Veranstaltungszeitraum
- Datums-Filter (Von/Bis) aus Event-Daten vorbelegt
- Auto-Refresh alle 30 Sekunden
- Button auf Event-Detailseite: "Zaehlerdaten & Export"

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
- (keine offenen P0 Items)

### P1
- MQTT Broker URL -> .env Refactoring (hardcoded in mqtt_service.py)
- PayPal-Integration als alternative Zahlungsmethode
- Direkter QR-Label-Druck (Print-Button statt PDF)
- Self-hosted MQTT Broker (Mosquitto)
- SMTP-Anbieter Upgrade (mail.de Tageslimit)

### P2
- Admin File Size Limits

## Test Credentials
- Admin: admin@test.com / password
- Mitarbeiter: ma1@test.com / password
