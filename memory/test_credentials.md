# Test Credentials (Preview + Live)

## Admin Accounts
- **Live (Production)**: christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- **Preview (Testing)**: admin@test.com / password

## Mitarbeiter Accounts (Preview)
- **Anna Weber (Mitarbeiter, Verwaltung+Abrechnung aktiv, M-Box: mbox_lesen=true / mbox_bedienen=false)**: ma1@test.com / Anna2026!  (Passwort am 2026-06 im Preview neu gesetzt)

## M-Box Test-Gerät (Preview)
- Geräteverwaltung: `MBOX-TEST-1` („Lichtmast Test 1"), Typ M-Box, Endpoint opc.tcp://192.168.0.100:4840, Port 8101 – keine echte SPS im Preview → immer „Zeitüberschreitung: Verbinden"
- Pi-Simulation: Pi-Setup wurde generiert (Key-Prefix im Gerät `mbox_pi_key_prefix`); Pi-GPS 50.43/7.47 per `/api/mbox/pi/<id>/sync` eingespielt

## M-Box Testkunde + Testauftrag (Preview)
- **Test Meier (Kunde, customer_no TM-4711)**: kunde.meier@test.com / Meier2026!
- Testauftrag in `orders_cache`: primary_key 999901 „Testfest Neuwied (M-Box)", customer_no TM-4711, dispo 2026-01-01..2027-12-31, Koordinaten 50.4335/7.4720 (`order_settings`) → MBOX-TEST-1 liegt 0,41 km entfernt (auto zugewiesen). Kein EpiRent-Auftrag → `/api/orders/epirent/999901` liefert seit 2026-06 Grunddaten aus dem Cache (Admin-Auftragsdetail nutzbar).
- Zweiter Testauftrag 999902 „Kommendes Fest (M-Box)", customer_no TM-4711, dispo 2027-03-01..2027-03-05 → in `/durchsagen` als „ab 01.03.2027 bedienbar" (Upload ja, Play 403).
- Echter Pi im Preview: Gerät `M-Box_001` (Serial, id bcd7198b…) meldet echte GPS-Position; Auftrag 128 (ohne Dispo-Zeitraum) hat ihn manuell zugewiesen und Kunden kunde@test.com / kunde1@test.com freigegeben (Passwörter unbekannt).

## Freelancer Accounts (Preview)
- **Test 12 (Freelancer, Aufträge: 33, 21, 163)**: test12@test.de / Freelance2026!

## Schausteller Portal (Public)
Registrierung über `/kirmes/anmeldung` (E-Mail-Verifikation per 6-stelligem Code)

## Stripe
- LIVE KEYS bereits in `.env` konfiguriert (STRIPE_API_KEY + STRIPE_WEBHOOK_SECRET)
- Preview-Umgebung hat Test-Key-Platzhalter → Refund-Tests schlagen dort fehl, in Live funktionieren sie
