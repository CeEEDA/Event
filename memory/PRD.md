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

### Admin Mitarbeiter-Zeitdetail Monatsansicht - FERTIG (2026-04-06)
- AdminZeitDetailPage (`/verwaltung/zeiterfassung/:userId`) komplett redesigned
- Aufklappbare Monatsansicht (Accordion) identisch zur Mitarbeiter-Seite (`/arbeitszeit`)
- Summary Badges pro Monat: Stunden, Urlaub, Krank
- HR-Stammdaten (Überstunden, Urlaubstage) bearbeitbar
- Genehmigte Urlaube eintragen/löschen mit Kalender-Berechnung
- Jahres-Summary-Karten: Stundenkonto, Genehmigt, Resturlaub, Krankheit
- GPS-Pins für Ein-/Ausstempeln sichtbar (nur Admin)

### Antrags-Tasks Genehmigt/Abgelehnt Buttons - FERTIG (2026-04-06)
- Antrags-Tasks zeigen "Genehmigt" und "Abgelehnt" Buttons statt Häkchen
- Mülleimer-Button bei Antrags-Tasks entfernt
- "von undefined" Bug behoben (created_by_name fehlte bei Task-Erstellung)
- Genehmigte/Abgelehnte Antrags-Tasks werden korrekt als erledigt markiert (completed=true)
- Betrifft: HubPage.js (Frontend), employee.py (Backend Task-Erstellung + Resolve)

### Überstundenabbau-Verrechnung Bugfix - FERTIG (2026-04-06)
- Bug: Genehmigte Überstundenabbau-Anträge wurden nicht vom Stundenkonto abgezogen
- Fix: Bei Genehmigung (direkt + via Task) werden automatisch 8h pro Arbeitstag abgezogen
- Betrifft: employee.py (resolve_time_off_request) + chat.py (update_task auto-approve)

### Arbeitsfreie-Zeit-Anträge - FERTIG (2026-04-06)
- Mitarbeiter können über Hub-Kachel "Freie Zeit" Anträge stellen (Krank, Urlaub, Überstundenabbau)
- Dialog mit Dropdown, Datumsauswahl, Ganztägig-Toggle, optionale Uhrzeiten
- Anträge erscheinen als Aufgabe bei allen Admins
- Admin kann Anträge genehmigen/ablehnen
- Bei Genehmigung von Urlaub werden Tage automatisch in Urlaubskonto verrechnet
- Mitarbeiter sieht Status (In Bearbeitung/Genehmigt/Abgelehnt) in der Arbeitszeitseite
- DB-Collections: `time_off_requests`, Tasks-Integration

### HR-Daten (Überstunden / Urlaub) - FERTIG (2026-04-06)
- Admin kann pro Mitarbeiter Überstunden (Std.), Urlaubstage (Gesamt/Jahr) und Genehmigten Urlaub eintragen
- Berechnete Anzeige: Stundenkonto, Genehmigter Urlaub, Resturlaub
- Daten im Hub für Mitarbeiter sichtbar (nur lesen)
- DB-Collection: `hr_data` (user_id, year, overtime_hours, vacation_days_total, vacation_days_used)

### GPS-Zeiterfassung (Stempeln) - FERTIG (2026-04-05)
- SwipeClock-Slider im Hub zum Ein-/Ausstempeln (verhindert versehentliches Stempeln)
- GPS-Koordinaten werden bei jedem Stempelvorgang erfasst
- Backend: clock-in, clock-out, status, report Endpunkte
- Eigene Arbeitszeitseite (`/arbeitszeit`) mit Monatsübersicht und Stundenauswertung
- Admin-Arbeitszeit-Tab in Auswertungsseite (`/verwaltung/auswertung`)
- Hub-Dashboard: Heutige Einstempel-Zeit, letzte Stempelungen, Resturlaub (Platzhalter), Überstundenkonto (Platzhalter)
- DB-Collection: `time_entries` (user_id, clock_in/out, GPS lat/lng, duration_minutes)

### Auswertung Dokumenten-Ablauf - FERTIG (2026-06-04)
- Auswertungsseite unter Verwaltung > Auswertung
- Dashboard: Abgelaufen / Kritisch / Warnung / Gültig Zähler (klickbar)
- Gruppierung nach Status oder Mitarbeiter
- Suche nach Mitarbeiter oder Dokumenttyp
- Zeigt: Mitarbeitername, Dokumenttyp, Ablaufdatum, Tage verbleibend/überfällig
- KI-Dokumenterkennung Fix (LlmChat Import korrigiert)

### Profilbild-Integration & Admin-Mitarbeiterverwaltung - FERTIG (2026-06-04)
- Profilbild wird im Hub-Header, Chat-Nachrichten und Konversationsliste angezeigt
- Mitarbeiter-Profil + Dokumente direkt in Benutzerverwaltung eingebettet
- Aufklappbare Zeile zeigt: Kontaktdaten, 9 Dokument-Karten (Ampel), Login-Aktivität
- Keine separate Seite/Kachel nötig

### Mitarbeiter-Profil & Dokumentenverwaltung - FERTIG (2026-06-04)
- Profilseite: Name, Profilbild, Anschrift, Telefon, Passwort ändern
- Profilbild-Upload mit Kamera-Button
- Profil-Link im Hub-Header (klickbar)
- 9 Dokumenten-Kategorien mit Drag & Drop PDF-Upload
- KI-Ablaufdatum-Erkennung via Gemini 2.5 Flash
- Manuell korrigierbares Ablaufdatum
- Versionierung: Neues Dokument markiert altes als "alt"
- Ampel-Status: Grün (gültig), Gelb (bald ablaufend), Rot (abgelaufen)
- Admin kann alle Mitarbeiter-Profile einsehen

### Chat Gruppenbild & Namensänderung - FERTIG (2026-06-04)
- Gruppenbilder hochladen (Kamera-Button im Detail-Panel)
- Avatar wird in Chat-Liste, Header und Detail-Panel angezeigt
- Gruppenname per Stift-Icon änderbar
- Nur für Admins bei Gruppenchats

### Chat Detail-Panel - FERTIG (2026-06-04)
- Klick auf Chat-Name öffnet Detail-Panel (Slide-over)
- Tabs: Mitglieder, Dateien, Fotos
- Mitglieder hinzufügen/entfernen (Admin, nur Gruppen)
- Alle geteilten Dateien und Fotos durchsuchbar

### Aufgaben-Filter Redesign - FERTIG (2026-06-04)
- Tabs geändert: "Aktuell / Erledigt / Alle" statt "Meine / Erstellt / Alle"
- Erledigte Aufgaben werden im Aktuell-Tab ausgeblendet
- Suchmaske zum Filtern von Aufgaben hinzugefügt

### Team Chat & Aufgabenverwaltung - FERTIG (2026-04-05)
- Direktnachrichten zwischen allen Benutzern
- Gruppenchats (nur Admin kann erstellen)
- Echtzeit-Polling (4 Sekunden)
- Datei-/Bildanhaenge im Chat (Object Storage)
- Ungelesene-Nachrichten-Zaehler (Badge)
- Aufgaben mit Prioritaeten (Hoch/Mittel/Niedrig)
- Faelligkeitsdaten mit Ueberfaellig-Anzeige
- Aufgaben anderen Benutzern zuweisen
- Filter: Meine / Erstellt / Alle (Admin)
- Aufgaben erledigen / wiederherstellen / loeschen
- Hub-Seite kompakt redesigned (Icon-Grid + Aufgaben-Panel)
- Chat/Task Datei-Downloads (Tuple-Unpacking Fix) - BEHOBEN (2026-06-04)

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
- GET /api/chat/tasks/{id}/file?token=...
- POST /api/chat/tasks/{id}/comments?token=...
- GET /api/chat/tasks/{id}/comments/{comment_id}/file?token=...

### Documents
- POST /api/documents/upload
- GET /api/documents/folders
- GET/PUT /api/documents/ai-settings

## DB Collections
- chat_conversations: {id, type, name, members[], last_message, created_by, ...}
- chat_messages: {id, conversation_id, sender_id, sender_name, text, attachment, read_by[], ...}
- tasks: {id, title, description, priority, priority_order, due_date, completed, created_by, assigned_to, ...}
- task_comments: {id, task_id, user_id, user_name, text, attachment, created_at}

## Prioritized Backlog
### P1
- Microsoft 365 Postfach-Anbindung
- PayPal/Kreditkarten Integration

### P2
- Chromium Kiosk, Windows Installer, GPS-Support
- Admin Dateigroessen-Limits
- DSE890 Gateway GSM (SIM-Karten)
