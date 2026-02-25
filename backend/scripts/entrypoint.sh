#!/bin/sh
set -e

# S'assurer que les répertoires critiques existent
mkdir -p /app/data/email_ingress
mkdir -p /app/data/ingress
mkdir -p /app/data/archive
mkdir -p /app/data/uploads

# Si on tourne en tant que root, on ajuste les permissions et on drop les privilèges
if [ "$(id -u)" = '0' ]; then
    echo "Correction des permissions pour les répertoires de données..."
    # On cible uniquement les dossiers nécessaires à l'ingestion
    chown -R appuser:appuser /app/data/email_ingress
    chown -R appuser:appuser /app/data/ingress
    chown -R appuser:appuser /app/data/archive
    chown -R appuser:appuser /app/data/uploads
    
    echo "Exécution de la commande en tant qu'appuser..."
    exec gosu appuser "$@"
fi

# Sinon on exécute normalement
exec "$@"
