# ============================================================================
#  Eventenergie Portal - Datenbank Migration (Windows)
#
#  EXPORT (alter Server):  .\db-migrate-win.ps1 export
#  IMPORT (neuer Server):  .\db-migrate-win.ps1 import C:\pfad\backup.gz
#  PRUEFEN:                .\db-migrate-win.ps1 verify
# ============================================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("export", "import", "verify", "help")]
    [string]$Action = "help",
    
    [Parameter(Position=1)]
    [string]$BackupFile = ""
)

$ErrorActionPreference = "Stop"
$OLD_DB = "test_database"
$NEW_DB = "eventenergie"
$DEFAULT_BACKUP = "eventenergie-backup.gz"
$APP_DIR = "C:\eventenergie"
$DATA_DIR = "$APP_DIR\data"

function Show-Help {
    Write-Host ""
    Write-Host "Verwendung:" -ForegroundColor Cyan
    Write-Host "  .\db-migrate-win.ps1 export              Datenbank exportieren (alter Server)" -ForegroundColor Gray
    Write-Host "  .\db-migrate-win.ps1 import [datei.gz]   Datenbank importieren (neuer Server)" -ForegroundColor Gray
    Write-Host "  .\db-migrate-win.ps1 verify              Import pruefen" -ForegroundColor Gray
    Write-Host ""
}

function Do-Export {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host "  Datenbank-Export" -ForegroundColor Cyan
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host ""

    # Check mongodump
    $mongodumpExists = $null
    try { $mongodumpExists = Get-Command mongodump -ErrorAction SilentlyContinue } catch {}
    if (-not $mongodumpExists) {
        Write-Host "mongodump nicht gefunden. Bitte MongoDB Database Tools installieren:" -ForegroundColor Red
        Write-Host "  choco install mongodb-database-tools" -ForegroundColor Yellow
        exit 1
    }

    $outFile = Join-Path (Get-Location) $DEFAULT_BACKUP
    Write-Host "[..] Exportiere Datenbank '$OLD_DB'..." -ForegroundColor Yellow

    & mongodump --db="$OLD_DB" --gzip --archive="$outFile"

    $fileSize = (Get-Item $outFile).Length
    $fileSizeMB = [math]::Round($fileSize / 1MB, 1)
    Write-Host ""
    Write-Host "[OK] Export: $outFile ($fileSizeMB MB)" -ForegroundColor Green

    # Dokumentenablage sichern
    $docDir = "$DATA_DIR\Dokumentenablage"
    if (Test-Path $docDir) {
        $docBackup = Join-Path (Get-Location) "dokumentenablage-backup.zip"
        Write-Host "[..] Dokumentenablage wird gesichert..." -ForegroundColor Yellow
        Compress-Archive -Path "$docDir\*" -DestinationPath $docBackup -Force
        $docSize = [math]::Round((Get-Item $docBackup).Length / 1MB, 1)
        Write-Host "[OK] Dokumente: $docBackup ($docSize MB)" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "  Naechste Schritte:" -ForegroundColor White
    Write-Host "    1. Dateien auf neuen Server kopieren (USB/Netzwerk/RDP)" -ForegroundColor Gray
    Write-Host "    2. Auf neuem Server: .\db-migrate-win.ps1 import $DEFAULT_BACKUP" -ForegroundColor Gray
    Write-Host ""
}

function Do-Import {
    $file = if ($BackupFile) { $BackupFile } else { $DEFAULT_BACKUP }

    Write-Host ""
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host "  Datenbank-Import" -ForegroundColor Cyan
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host ""

    if (-not (Test-Path $file)) {
        Write-Host "Datei nicht gefunden: $file" -ForegroundColor Red
        exit 1
    }

    # Check mongorestore
    $mongorestoreExists = $null
    try { $mongorestoreExists = Get-Command mongorestore -ErrorAction SilentlyContinue } catch {}
    if (-not $mongorestoreExists) {
        Write-Host "mongorestore nicht gefunden. Bitte installieren:" -ForegroundColor Red
        Write-Host "  choco install mongodb-database-tools" -ForegroundColor Yellow
        exit 1
    }

    $fileSize = [math]::Round((Get-Item $file).Length / 1MB, 1)
    Write-Host "[..] Importiere $file ($fileSize MB)..." -ForegroundColor Yellow
    Write-Host "     Alte DB: $OLD_DB -> Neue DB: $NEW_DB" -ForegroundColor Gray

    & mongorestore --gzip --archive="$file" --nsFrom="${OLD_DB}.*" --nsTo="${NEW_DB}.*" --drop

    Write-Host ""
    Write-Host "[OK] Datenbank importiert als '$NEW_DB'" -ForegroundColor Green

    # Dokumentenablage wiederherstellen
    $docBackup = ""
    foreach ($f in @("dokumentenablage-backup.zip", ".\dokumentenablage-backup.zip")) {
        if (Test-Path $f) { $docBackup = $f; break }
    }
    if ($docBackup) {
        $destDir = "$DATA_DIR\Dokumentenablage"
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        Write-Host "[..] Dokumentenablage wird wiederhergestellt..." -ForegroundColor Yellow
        Expand-Archive -Path $docBackup -DestinationPath $destDir -Force
        Write-Host "[OK] Dokumentenablage wiederhergestellt" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "  Pruefen: .\db-migrate-win.ps1 verify" -ForegroundColor Gray
    Write-Host ""
}

function Do-Verify {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host "  Datenbank-Pruefung" -ForegroundColor Cyan
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host ""

    & mongosh --quiet --eval @"
        var db = db.getSiblingDB('$NEW_DB');
        var colls = db.getCollectionNames();
        print('Datenbank: $NEW_DB');
        print('Collections: ' + colls.length);
        print('');
        var total = 0;
        colls.forEach(function(c) {
            var count = db.getCollection(c).countDocuments({});
            total += count;
            if (count > 0) print('  ' + c + ': ' + count + ' Dokumente');
        });
        print('');
        print('Gesamt: ' + total + ' Dokumente');
        print('');
        print('--- Wichtige Daten ---');
        print('Benutzer: ' + db.users.countDocuments({}));
        print('Auftraege: ' + db.orders_cache.countDocuments({}));
        print('Zeiteintraege: ' + db.time_entries.countDocuments({}));
        print('Dokumente: ' + db.documents.countDocuments({}));
        print('Geraete: ' + db.devices.countDocuments({}));
"@
    Write-Host ""
}

# Main
switch ($Action) {
    "export"  { Do-Export }
    "import"  { Do-Import }
    "verify"  { Do-Verify }
    default   { Show-Help }
}
