# Kirmes/Eventenergie – Full-Stack Business System – PRD

## Original Problem Statement
Comprehensive "Kirmes" (Fairground) billing, dispatch and HR management system with telemetry ingestion, order management, disruption logging, team/HR management, kiosk interfaces, deep hardware integration (DSE 5510, DSE 890, Sening MultiFlow) and AI-driven document management (ZUGFeRD, DATEV routing, spam filtering) plus Delivery Notes (Lieferscheine) and Inventory.

Language: **German** (agent must reply in German only).

## Current Status
Mature React/FastAPI/MongoDB app with EpiRent sync, order tracking, AI Document Management (Ollama + ZUGFeRD + PyMuPDF), FinTS banking, DATEV email routing, IMAP Mailbridge, Kiosk apps, generator telemetry, Tankbeleg ingestion (Sening), full Inventar module with WebRTC camera + XLSX/PDF exports.

## Completed – 2026-02-06 (this session)
- ✅ Inventar: 4. Kachel "Marktwert gesamt" (grün) in der Stat-Row ergänzt
- ✅ Inventar: Marktschätzwert wird jetzt zusätzlich in jeder Position-Zeile angezeigt (`Bilanz X € · Markt Y €`)
- ✅ Grid von grid-cols-3 → grid-cols-2 sm:grid-cols-4 (iOS-freundlich)

## Backlog

### P1 (Upcoming)
- OTA-Update-Mechanik für Tankbeleg Pi (`tankbeleg_pi.py` Self-Update inkl. Hash-Verify + systemd restart)
- EpiRent Lieferscheine (PDF-Generierung, Layout noch offen)

### P2 (Future)
- Disk-Watchdog Live-Server: `start-all.bat` prüft C:/E: >10GB frei vor MongoDB-Start
- Bulk-Move für Fuel Receipts
- Admin Audit-Page für Asset-Type-Änderungen
- "Alarm vor Ort geprüft – Sammel-Warning quittieren" auf Generator Diagnose (DSE-Reset Key 35707)
- USB-Resilience / Hardware Health Dashboard pro Pi
- GPS Support für Kirmeskiste (4-m-Variante)
- Lastdiagramm Live-Test
- Camera-Foto Upload mit EXIF GPS in Dokumentenablage
- Tank-Alarm-Threshold Notifications für Generatoren
- Offday-Verfallsregel §11 Abs. 3 ArbZG (8-Wochen-Frist)
- Mail/SMS Notification bei Shift-Plan-Freigabe

## Refactoring
- `/app/backend/routes/documents.py` (>2200 LOC) → in `document_processors.py` (ZIP upload, spam routing, TEBA merge) auslagern

## 3rd Party Integrations
- Stripe (User-Key), EpiRent (User-Key), Ollama, IONOS IMAP, DATEV Email, FinTS, Open-Meteo, Nominatim

## Test Credentials
- Admin: `admin@test.com` / `password`
- Mitarbeiter: `ma1@test.com` / `password`
