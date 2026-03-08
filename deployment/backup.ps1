# ============================================================
# Eventenergie - Taegliches MongoDB Backup
# Als geplante Aufgabe einrichten (Aufgabenplanung)
# ============================================================

$BackupDir = "C:\eventenergie\backups"
$Date = Get-Date -Format "yyyy-MM-dd_HHmm"
$TargetDir = "$BackupDir\$Date"

Write-Host "MongoDB Backup starten: $TargetDir"
mongodump --db eventenergie --out $TargetDir

# Backups aelter als 30 Tage loeschen
Get-ChildItem $BackupDir -Directory | Where-Object {
    $_.CreationTime -lt (Get-Date).AddDays(-30)
} | ForEach-Object {
    Write-Host "Loesche altes Backup: $($_.Name)"
    Remove-Item $_.FullName -Recurse -Force
}

Write-Host "Backup abgeschlossen: $TargetDir"
