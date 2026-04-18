# Eventenergie Portal - PRD

## Original Problem Statement
Comprehensive "Kirmes" (Fairground) billing and HR management system with:
- Desktop Apps (Mac/Windows) via Electron
- Mobile Apps (Android/iOS) via Capacitor
- Server Infrastructure on Windows Server 2019
- DSE 890 Gateway MQTT Integration for remote generator monitoring and control

## Architecture
- **Frontend**: React (CRA + craco)
- **Backend**: FastAPI + MongoDB (motor)
- **MQTT**: Mosquitto broker on Windows Server
- **DSE Gateways**: DSE 890 MK1 with L401 and 8610 controllers

## What's Been Implemented (2026-04-18)

### DSE 890 Gateway – COMPLETE
- [x] Sentinel value filtering (valid() function + _sanitize_telemetry)
- [x] Control buttons working: Stop/Auto/Start via MQTT Function 3, {"K": key} payload
- [x] 4-segment topic format (group/type/uid/subtopic)
- [x] Auto module UID + topic prefix detection from MQTT messages
- [x] GPS from gateway applied to all connected devices
- [x] Alarm integration: P3R6 Status Bits + GenComm Page 8 Named Alarm Conditions (52+ Alarme)
- [x] L401 single-phase view (no L2/L3, no Öldruck, no cos φ)
- [x] 8610 full 3-phase view (all registers)
- [x] Betriebsstunden via Page 7 Register 6 (hours topic, 20 min interval)
- [x] Button blink animation after command (green pulse for 2 min)
- [x] Mode feedback stored on device after command
- [x] Mosquitto password auto-management

### Alarm System (2026-04-18 overhaul)
- [x] GenComm Page 8 register reading via Function 1 (13 registers = 52 named alarms)
- [x] Correct alarm condition codes: only 2/3/4/5/10 = active alarm (was: >0)
- [x] Alarm name map aligned to official GenComm Page 8 documentation
- [x] Severity from condition code: 3/4=shutdown, 2/5/10=warning
- [x] Dual format support: A-code format (Function 4) + GenComm P008 register format
- [x] Updated universal topic file includes Page 8 R1-R13

### Topic Files
- [x] Universal: All DSE controllers use same GenComm Topic File
- [x] Contains: Engine params, generator params, status bits, hours, starts, Page 8 alarms, control
- [x] Register mapping based on official DSE GenComm documentation

### Performance Optimizations
- [x] MQTT deduplication, DB lookup caching (30s TTL)
- [x] Telemetry insert throttling (Lichtmast 60s, Stromerzeuger 5min)
- [x] Snapshot-based telemetry (no N×10 queries)

### Telemetry Parsing Fixes (2026-04-18)
- [x] Hours parsing: accepts 0 seconds (never-run devices), handles string values
- [x] Fuel level clamped to max 100% (was showing 107%)
- [x] Diagnostic logging for /hours topic (MQTT hours OK / MQTT hours FEHLEND)
- [x] Diagnostic endpoint: GET /api/generators/diagnose-hours

### DSE USB-Treiber für Raspberry Pi (2026-04-18 NEW)
- [x] Custom Linux USB driver for DSE controllers (VID 1b90:0001) via pyusb BULK
- [x] Modbus RTU over USB BULK (Function 3 Read + Function 16 Write)
- [x] GenComm register reading: Pages 3,4,6,7,8 (Status, Engine, Power, Hours, Alarms)
- [x] 3-phase support: L1/L2/L3 voltage, current, watts (for 8610/7310)
- [x] Control commands via KEY+COMPLEMENT (Page 16 Register 8) - verified on real L401
- [x] GPS integration via gpsd
- [x] Alarm processing: Pi alarms → generator_alarms → Dashboard alarm banner
- [x] Pi-command endpoint for remote control from portal
- [x] udev rule for persistent USB binding after reboot
- [x] Connection type selection in UI: "DSE 890 Gateway (MQTT)" vs "Pi + USB direkt" vs "Pi + DSE USB/LAN Adapter"
- [x] LTE setup completely rebuilt based on user-tested working script
- [x] Uses PPP with defaultroute+replacedefaultroute+ifmetric (was: nodefaultroute)
- [x] NetworkManager metrics instead of dhcpcd (Pi 5 Bookworm compatible)
- [x] ModemManager disabled (was blocking ttyUSB ports)
- [x] GPS: gpsd + sim7600-gps-enable systemd service
- [x] Fixed port schema: ttyUSB2=GPS, ttyUSB3=AT+PPP
- [x] Status tools: lte-status, gps-status
- [x] Routing: eth0 (100) → wlan0 (600) → ppp0 (700)
- [x] Generalized for ALL DSE controllers (5510, 8610, 8610 MKII, 7310, L401)
- [x] Controller type passed to generated script (header + config)
- [x] 3-phase indicator (L1/L2/L3) shown for 8610/7310 controllers
- [x] Both DSE 890 Gateway AND Pi Setup available for 8610/7310/L401

### Finance
- [x] Invoice Payment Status (Bezahlt/Offen) & Filter UI
- [x] 2-Stage Dunning Workflow (Mahnwesen) with Admin Task integration
- [x] FinTS/HBCI Bank integration code (disabled pending bank registration)
- [x] Fuel Management (Tankbelege) UI

### Störmeldungs- & Reparatur-System (2026-04-18 NEW)
- [x] Störmeldung anlegen: Erfasser (auto), Auftrag (aus Liste), Maschine (Suche), Beschreibung, "Gerät sperren"
- [x] Reparatur-Tab: Offene Störmeldungen mit Status (Offen → In Arbeit → Erledigt)
- [x] Reparatur eintragen: Was wurde gemacht, Gerät entsperren
- [x] Status-Farben: Rot=Offen, Amber=In Arbeit, Grün=Erledigt
- [x] Service-Log: Störmeldung + Reparatur werden in maintenance_entries geloggt
- [x] Maschinen-Auswertung: Eigene Seite unter /verwaltung/maschinen-auswertung
- [x] Zeitraum-Filter (Von/Bis), Übersichtskarten, Tabelle pro Maschine, aufklappbar mit Details
- [ ] Einsatzplanung: Gesperrte Geräte rot markiert (noch zu implementieren)

## 2026-02-XX – DSE USB Fast-Command-Polling Bugfix
- [x] Kritischer Bug in `dse_usb_sync.py`: Poll-URL zeigte auf nicht existenten Endpoint `/generators/remote-update/{id}/poll` (gab lautlos 404 wegen `except: pass`). Dadurch wurden Befehle nur im 30s-Sync-Zyklus abgeholt → ~20s Latenz.
- [x] Fix: Korrekte Lightweight-URL `/generators/poll-commands/{id}?key=<device_key>` (wie in `dse5510_sync.py`), Logging für Poll-Antworten aktiviert.
- [ ] User-Verifikation am physischen DSE L401 ausstehend.

## 2026-02-18 – Stripe Checkout Return Flow Fix (P0)
- [x] **Root-Cause**: Stripe success_url zeigte auf `/schausteller-anmeldung` statt auf React-Route `/kirmes/anmeldung` → User landete auf White Page
- [x] Alle Stripe URLs in `payments.py` auf `/kirmes/anmeldung` umgestellt (success + cancel)
- [x] `_confirm_deposit_and_send_email` setzt `signup.payment_status="bezahlt"` (vorher: "ausstehend") → in Kirmesverwaltung grün sichtbar
- [x] Frontend `api`-Wrapper (`constants.js`) liefert jetzt `response.status` im Error → saubere 404-Erkennung
- [x] Neue `PaymentSuccessStep` Komponente für Fresh-Load nach Stripe-Return (ohne Schausteller-Login)
- [x] `PaymentCheckStep` mit Timeout- und Error-State + "Erneut prüfen" / "Zum Portal"-Buttons
- [x] URL wird nach Auswertung automatisch bereinigt (kein stuck session_id)
- [x] Backend-Logging aller Status-Polls und Webhook-Events

## 2026-02-18 – Auto-Refund auf Kreditkarte bei Rechnungsstellung (P0)
- [x] Pre-Auth verworfen (7-Tage-Limit zu kurz für typische 3+ Wochen Event-Laufzeit)
- [x] Stattdessen: volle Kaution (Anschluss + kWh-Puffer + MwSt) wird eingezogen, Differenz nach Rechnung automatisch per Stripe Refund API zurück auf Kreditkarte
- [x] Neue Funktion `refund_deposit_difference()` in `payments.py` – automatisch aufgerufen in `/signups/{id}/invoice` und `/events/{id}/generate-invoices`
- [x] Speichert `payment_intent_id` + `charge_id` beim Bezahlvorgang via `_fetch_and_store_payment_intent()`
- [x] Admin-Endpoints: `POST /api/payments/refund/manual`, `GET /api/payments/refund/status/{signup_id}`, `POST /api/payments/refund/sync-payment-intent/{session_id}` (Legacy-Support)
- [x] Rechnungs-Dokument erhält `deposit_applied`, `deposit_refunded`, `deposit_open_balance`, `refunds[]`
- [x] UI: Kaution-Badge und Refund-Badge in KirmesEventDetailPage (Mobile + Desktop)
- [x] Proportionale Refund-Verteilung bei Sammelrechnungen (mehrere Signups eines Schaustellers → Refund pro PaymentIntent anteilig)

## Upcoming Tasks (P1)
- [ ] Microsoft 365 Postfach-Anbindung (IMAP "Mailbridge" Windows Service)
- [ ] DSE 890 Gateway CSV-Upload (User-Task)
- [ ] Test Tankwagen-Pi setup script on real hardware
- [ ] FinTS/HBCI activation when bank registers Product ID

## Future Tasks (P2)
- [ ] Eingangsrechnungen überwachen
- [ ] Lastdiagramm Live-Test
- [ ] Chromium "Translate" Popup on RPi Kiosk
- [ ] GPS Support for Kirmeskiste

## Test Credentials
- Admin Live: christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- Admin Preview: admin@test.com / password
