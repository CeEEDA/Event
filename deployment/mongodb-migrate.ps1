# ============================================================
# MongoDB Daten vom Emergent-Server exportieren und lokal importieren
# ============================================================

param(
    [string]$SourceUrl = "mongodb://localhost:27017",
    [string]$SourceDB = "test_database",
    [string]$TargetDB = "eventenergie",
    [string]$DumpDir = "C:\eventenergie\backups\migration"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " MongoDB Migration" -ForegroundColor Cyan
Write-Host " Quelle: $SourceDB" -ForegroundColor Cyan
Write-Host " Ziel:   $TargetDB" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Schritt 1: Daten exportieren (auf dem Quellserver ausfuehren)
Write-Host "`nHINWEIS: Die Daten muessen zuerst vom Emergent-Server exportiert werden."
Write-Host "Auf dem Emergent-Server ausfuehren:"
Write-Host "  mongodump --db test_database --out /tmp/db_export" -ForegroundColor Yellow
Write-Host "  Dann den Ordner /tmp/db_export/test_database herunterladen."
Write-Host ""

# Schritt 2: Lokal importieren
if (Test-Path "$DumpDir\$SourceDB") {
    Write-Host "Importiere Daten nach $TargetDB..."
    mongorestore --db $TargetDB "$DumpDir\$SourceDB" --drop
    Write-Host "OK: Daten importiert!" -ForegroundColor Green
} else {
    Write-Host "Dump-Verzeichnis nicht gefunden: $DumpDir\$SourceDB" -ForegroundColor Red
    Write-Host "Bitte zuerst die Daten vom Server herunterladen." -ForegroundColor Yellow
}
