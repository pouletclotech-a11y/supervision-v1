#!/bin/bash

# --- Configuration ---
BACKUP_ROOT="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"
LATEST_LINK="$BACKUP_ROOT/latest"

DB_CONTAINER="supervision_db"
DB_USER="admin"
DB_NAME="supervision"

# --- Pré-requis ---
mkdir -p "$BACKUP_DIR"

echo "===================================================="
echo "   TLS-Y SUPERVISION - BACKUP LOCAL ($TIMESTAMP)    "
echo "===================================================="

# 1. Vérification Docker
if ! docker info > /dev/null 2>&1; then
    echo "ERREUR : Docker n'est pas lancé."
    exit 1
fi

# 2. Sauvegarde Base de Données
echo "[1/3] Sauvegarde PostgreSQL (conteneur: $DB_CONTAINER)..."
if docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_DIR/db_dump.sql" 2> "$BACKUP_DIR/db_error.log"; then
    echo "  > OK : Base de données sauvegardée."
else
    echo "  > ERREUR : Échec du dump DB. Vérifiez que le conteneur '$DB_CONTAINER' est Up."
    echo "  > Log d'erreur : $BACKUP_DIR/db_error.log"
    exit 1
fi

# 3. Sauvegarde fichiers d'ingestion
echo "[2/3] Sauvegarde des fichiers physiques..."

# Dropbox
if [ -d "dropbox_in" ]; then
    cp -r dropbox_in/ "$BACKUP_DIR/dropbox_in"
    echo "  > OK : dossier 'dropbox_in' sauvegardé."
else
    echo "  > INFO : dossier 'dropbox_in' absent, ignoré."
fi

# Archive
if [ -d "archive" ]; then
    cp -r archive/ "$BACKUP_DIR/archive"
    echo "  > OK : dossier 'archive' sauvegardé."
else
    echo "  > INFO : dossier 'archive' absent, ignoré."
fi

# 4. Alias latest
echo "[3/3] Mise à jour du lien 'latest'..."
rm -f "$LATEST_LINK"
ln -s "$TIMESTAMP" "$LATEST_LINK"
echo "  > OK : lien mis à jour vers $TIMESTAMP."

echo "===================================================="
echo " SAUVEGARDE TERMINÉE AVEC SUCCÈS : $BACKUP_DIR"
echo "===================================================="
exit 0
