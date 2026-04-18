# Test Credentials (Preview + Live)

## Admin Accounts
- **Live (Production)**: christian.ecker@eventenergie-deutschland.de / qivbeb-Wodha1-sewram
- **Preview (Testing)**: admin@test.com / password

## Schausteller Portal (Public)
Registrierung über `/kirmes/anmeldung` (E-Mail-Verifikation per 6-stelligem Code)

## Stripe
- LIVE KEYS bereits in `.env` konfiguriert (STRIPE_API_KEY + STRIPE_WEBHOOK_SECRET)
- Preview-Umgebung hat Test-Key-Platzhalter → Refund-Tests schlagen dort fehl, in Live funktionieren sie
