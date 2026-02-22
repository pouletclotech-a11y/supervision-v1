# --- Configuration ---
$BackupRoot = ".\backups"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $BackupRoot $Timestamp
$LatestDir = Join-Path $BackupRoot "latest"

$DbContainer = "supervision_db"
$DbUser = "admin"
$DbName = "supervision"

# --- Pré-requis ---
if (-not (Test-Path $BackupRoot)) {
    New-Item -ItemType Directory -Path $BackupRoot | Out-Null
}
New-Item -ItemType Directory -Path $BackupDir | Out-Null

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "   TLS-Y SUPERVISION - BACKUP LOCAL (PowerShell)    " -ForegroundColor Cyan
Write-Host "   Timestamp: $Timestamp" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# 1. Vérification Docker
if (-not (docker info 2>$null)) {
    Write-Host "ERREUR : Docker n'est pas lancé ou n'est pas accessible." -ForegroundColor Red
    exit 1
}

# 2. Sauvegarde Base de Données
Write-Host "[1/3] Sauvegarde PostgreSQL (via Docker)..." -ForegroundColor Yellow
$DumpPath = Join-Path $BackupDir "db_dump.sql"
try {
    # Utilisation de docker exec pour le dump vers un fichier sur l'hôte
    docker exec $DbContainer pg_dump -U $DbUser $DbName > $DumpPath
    if ((Get-Item $DumpPath).Length -gt 0) {
        Write-Host "  > OK : Base de données sauvegardée." -ForegroundColor Green
    } else {
        throw "Le dump est vide."
    }
} catch {
    Write-Host "  > ERREUR : Échec du dump DB. Vérifiez que le conteneur '$DbContainer' est lancé." -ForegroundColor Red
    exit 1
}

# 3. Sauvegarde fichiers d'ingestion (Host side)
Write-Host "[2/3] Sauvegarde des fichiers physiques..." -ForegroundColor Yellow

function Sync-Folder($Src, $Dest) {
    if (Test-Path $Src) {
        Copy-Item -Path $Src -Destination $Dest -Recurse -Force
        Write-Host "  > OK : dossier '$Src' sauvegardé." -ForegroundColor Green
    } else {
        Write-Host "  > INFO : dossier '$Src' absent, ignoré." -ForegroundColor Gray
    }
}

Sync-Folder ".\dropbox_in" (Join-Path $BackupDir "dropbox_in")
Sync-Folder ".\archive" (Join-Path $BackupDir "archive")

# 4. Mise à jour de 'latest' (Copie simple sous Windows pour éviter les problèmes de liens symboliques/permissions)
Write-Host "[3/3] Mise à jour du dossier 'latest'..." -ForegroundColor Yellow
if (Test-Path $LatestDir) {
    Remove-Item -Path $LatestDir -Recurse -Force
}
Copy-Item -Path $BackupDir -Destination $LatestDir -Recurse -Force
Write-Host "  > OK : dossier 'latest' mis à jour." -ForegroundColor Green

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " SAUVEGARDE TERMINÉE AVEC SUCCÈS : $BackupDir" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
