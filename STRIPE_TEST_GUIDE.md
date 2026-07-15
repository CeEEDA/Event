# 🧪 Stripe-Rechnungs-Test in der Testumgebung

**Ziel:** Kompletten Rechnungs-Flow (Anzahlung → Rechnung → Refund/Restzahlung → E-Mail-Link) testen, **ohne echtes Geld zu bewegen und ohne echte Rechnungen zu versenden**.

## Voraussetzungen

- Preview-URL: `https://fuel-truck-deploy.preview.emergentagent.com`
- Admin-Login: `admin@test.com` / `password`
- Stripe-Key: `sk_test_...` (**Testmodus**, kein Live-Zugriff)

## Stripe-Test-Karten (kein echtes Geld!)

| Karte | Zweck |
|---|---|
| `4242 4242 4242 4242` | Zahlung geht IMMER durch (Erfolgsfall) |
| `4000 0000 0000 9995` | Zahlung wird abgelehnt (insufficient funds) |
| `4000 0025 0000 3155` | Erfordert 3D-Secure-Bestätigung |
| CVC | Beliebig 3-stellig (z.B. `123`) |
| Ablauf | Beliebig in der Zukunft (z.B. `12/30`) |

## Ablauf

### 1. Test-Kirmes anlegen
1. Login als Admin
2. `Kirmes → Neue Veranstaltung`
3. Name z.B. **"TEST-Herbstkirmes 2026"**, Ende-Datum in 2 Wochen
4. **Netzanschluss anlegen**: z.B. `16A → 100€ Anschluss + 200€ Kaution`

### 2. Test-Schausteller-Anmeldung
1. Neuer Tab (Inkognito): `/kirmes/anmeldung`
2. Test-E-Mail: `test-schausteller@example.com` (Verifikations-Code steht in der Backend-Console)
3. Signup für TEST-Herbstkirmes → 16A Anschluss auswählen
4. **Stripe Checkout** öffnet sich → Test-Karte `4242 4242 4242 4242` eingeben
5. Nach Erfolg → Signup ist bezahlt (100€ Anschluss + 200€ Kaution = 300€ auf Karte)

### 3. Rechnung generieren (mit Anzahlung)
Als Admin:
1. Zurück zur TEST-Kirmes → Signup öffnen
2. Meter-Verbrauch simulieren:
   - **Szenario A (Rest zu zahlen)**: Verbrauch so eintragen dass Rechnung > 300€ → Restzahlung offen
   - **Szenario B (Refund)**: Verbrauch niedrig lassen → Rechnung z.B. 220€ → 80€ Refund
   - **Szenario C (exakt)**: Verbrauch trifft genau die Kaution
3. `Rechnung erstellen` klicken

**Erwartetes Verhalten:**

| Szenario | Anzahlung | Rechnung | Refund | Restzahlung | Rechnungs-PDF zeigt |
|---|---|---|---|---|---|
| A | 300€ | 500€ | 0€ | 200€ | Stripe-Zahlungslink „Jetzt bezahlen" |
| B | 300€ | 220€ | 80€ automatisch auf Karte | 0€ | „Überzahlung 80€ auf Ihre Karte zurückerstattet" |
| C | 300€ | 300€ | 0€ | 0€ | „Vollständig durch Anzahlung beglichen" |

### 4. Rechnung per Mail verschicken
1. Admin → Rechnung → `Rechnung schicken`
2. **Empfänger auf dich selbst umlenken:** In der Signup-Maske vor dem Klick die `rechnungs_email` auf **deine Test-Adresse** ändern
   → damit landet die Test-Rechnung bei dir, nicht beim echten Kunden
3. Mail bekommen → PDF prüfen → "Jetzt online bezahlen"-Link testen

### 5. Restzahlung testen (Szenario A)
1. Klick auf **"Jetzt online bezahlen"** in der Mail
2. Stripe-Checkout öffnet sich mit dem exakten Restbetrag
3. Test-Karte `4242 4242 4242 4242`
4. Rückleitung auf `/rechnung/bezahlt` → Erfolgs-Anzeige
5. Backend: Webhook wird ausgelöst → Rechnung automatisch auf `bezahlt` gesetzt

### 6. Refund verifizieren (Szenario B)
Sofort nach `Rechnung erstellen`:
- Backend-Log prüfen: `logger.info("Stripe Refund created ...")`
- DB-Check: `db.kirmes_invoices.findOne({_id: <id>})` → `deposit_refunded > 0`
- Stripe-Dashboard (Testmodus): siehst du den Refund unter Payments

---

## Was zu prüfen ist

- [ ] Anzahlung + Kaution werden als **eine Summe** im Rechnungs-PDF angezeigt (nicht getrennt)
- [ ] Bei Szenario B: **Refund-Zeile** ist im PDF sichtbar
- [ ] Bei Szenario A/B: **GiroCode QR** enthält den **Restzahlbetrag**, nicht den Bruttobetrag
- [ ] Bei Szenario C: **Kein GiroCode**, Text „Keine weitere Zahlung erforderlich"
- [ ] Stripe-Zahlungslink funktioniert (nur bei Restzahlung > 0,50€ vorhanden)
- [ ] Nach Zahlung: Rechnung wechselt von `offen` → `bezahlt` (Webhook)
- [ ] E-Mail geht durch (SMTP funktioniert, kein SSL-Fehler)

## Falls etwas fehlschlägt

- **SSL-Fehler beim Mail-Versand:** `certifi`-Fix ist drin → sollte weg sein
- **Refund schlägt fehl:** Stripe-Log prüfen, evtl. Payment-Intent noch nicht `succeeded`
- **Keine E-Mail:** SMTP-Config in Preview ist leer → benutze für Test-Umgebung `IONOS-Creds temporär` oder skippe Mail-Versand
- **Falscher Betrag im QR:** `deposit_open_balance` in der DB prüfen

## Sicherheit für Live

- Deine Live-Rechnungen sind **nicht betroffen** — Testumgebung nutzt eigenen Stripe-Test-Key + eigene MongoDB
- **Kunden bekommen KEINE Mails** solange du die E-Mail-Adresse auf deine eigene umlenkst
- Falls du versehentlich eine Rechnung mit echter E-Mail-Adresse erstellst → einfach nicht auf „Schicken" klicken; sie bleibt in der DB, wird aber nicht versendet
