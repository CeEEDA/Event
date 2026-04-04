# Eventenergie Portal - PRD

## Original Problem Statement
Umfassendes "Kirmes" (Jahrmarkt) Abrechnungssystem mit Tankbeleg-Digitalisierung, Auftragsverwaltung, Energiemonitoring, Zahlungsabwicklung und mehr.

## Core Architecture
- **Frontend:** React (CRA) + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI (Python) + MongoDB + GridFS
- **Desktop:** Electron Wrapper
- **External APIs:** EpiRent (ERP), Stripe (Payments), MQTT, OpenStreetMap

## What's Been Implemented

### Multi-Anschluss Buchung - FERTIG (2026-04-04)
- Hauptanschluss + beliebig viele Zusatzanschluesse + Wohnwagen in einem Formular
- "Weiteren Anschluss anmelden" hat gleiche Maske wie Hauptformular (Platznummer, Fahrgeschaeft, Stromanschluss-Karten)
- Wohnwagen-Formular: nur Platznummer + Anschluss (kein Nutzungs-Feld)
- Buttons untereinander (nicht nebeneinander)
- Kein grauer Hintergrund bei Zusatzformularen
- Placeholder "Imbiss" statt "Imbissbude"

### Zahlungsmittel & Kaution - FERTIG (2026-04-04)
- EIN Zahlungsmittel-Dropdown UEBER der Buchungsuebersicht (nicht pro Anschluss)
- Kreditkarte/PayPal: Kautionen werden in Gesamtsumme eingerechnet
- Auf Rechnung: Nur Anschlussgebuehren, keine Kautionen
- Buchungsuebersicht zeigt alle Anschluesse mit korrekten Preisen + Gesamtsumme

### Wohnwagen-Preise korrekt - FERTIG (2026-04-04)
- Backend unterscheidet regulaere und Wohnwagen-Preislisten (gleicher connection_type, andere Preise)
- Frontend Buchungsuebersicht nutzt korrekte Preisliste je nach isWohnwagen Flag

### Kombinierte Rechnung - FERTIG (2026-04-04)
- EINE Rechnung pro Schausteller pro Event (nicht pro Anschluss)
- Alle Anschluesse als separate Positionen in einer Rechnung
- Admin "Rechnung" Button bei beliebigem Anschluss erstellt Gesamtrechnung
- Sammelabrechnung gruppiert automatisch nach Schausteller
- PDF-Export mit allen Positionen korrekt
- Kundenportal zeigt Rechnung korrekt an

### Bestaetigungsseite - FERTIG (2026-04-04)
- Zeigt komplette Zusammenfassung aller gebuchten Anschluesse
- Einzelpreise, Kautionen (bei Kreditkarte), Gesamtsumme, Zahlungsmittel

### Lastdiagramm Feature - FERTIG (2026-04-03)
- Dashboard-Sektion zeigt verfuegbare und gekaufte Diagramme
- Kaufprozess: 125 EUR netto + 19% MwSt = 148,75 EUR brutto
- PDF-Generierung: Deckblatt + taegliche Lastdiagramme
- Voraussetzung: EMU-Zaehler muss mit Anschluss verknuepft sein

### Vorherige Features
- Datenschutz-Modal, AGB/Impressum mit korrekten Umlauten
- Admin Lastdiagramm Download, Schausteller-Detailseite
- Projektbericht, Abrechnung Export, Expanded Row Redesign

## Key API Endpoints
- POST /api/kirmes/public/signup (Multi-Anschluss, korrekte Preisberechnung)
- POST /api/kirmes/signups/{signup_id}/invoice (Kombinierte Rechnung fuer alle Anschluesse des Schaustellers)
- POST /api/kirmes/events/{event_id}/generate-invoices (Sammelabrechnung, gruppiert nach Schausteller)
- GET /api/kirmes/public/my-bookings?schausteller_id=... (Buchungen + Rechnungen)
- GET/POST /api/kirmes/public/lastdiagramm/*

## Prioritized Backlog

### P1 - Kommend
- PayPal/Kreditkarten Integration

### P2 - Backlog
- Chromium Translate Popup auf Raspberry Pi
- Admin File Size Limits fuer Uploads
- Windows Installer fuer Electron Desktop App
- GPS-Support fuer Kirmeskiste

### Blocked
- DSE890 Gateway GSM (wartet auf neue SIM-Karten)
- Lastdiagramm Live-Test (braucht verknuepfte EMU-Zaehler mit Messdaten)

### Refactoring
- SchaustellerAnmeldungPage.jsx aufteilen (aktuell >1300 Zeilen)
