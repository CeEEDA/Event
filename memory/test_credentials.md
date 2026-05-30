# Test Credentials (Preview + Live)

## Admin Accounts
- **Live (Production)**: christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- **Preview (Testing)**: admin@test.com / password

## Mitarbeiter Accounts (Preview)
- **Anna Weber (Mitarbeiter, Verwaltung+Abrechnung aktiv)**: ma1@test.com / Anna2026!

## Freelancer Accounts (Preview)
- **Test 12 (Freelancer, Aufträge: 33, 21, 163)**: test12@test.de / Freelance2026!

## Schausteller Portal (Public)
Registrierung über `/kirmes/anmeldung` (E-Mail-Verifikation per 6-stelligem Code)

## Stripe
- LIVE KEYS bereits in `.env` konfiguriert (STRIPE_API_KEY + STRIPE_WEBHOOK_SECRET)
- Preview-Umgebung hat Test-Key-Platzhalter → Refund-Tests schlagen dort fehl, in Live funktionieren sie
