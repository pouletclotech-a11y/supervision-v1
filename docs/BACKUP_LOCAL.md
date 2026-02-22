# Procédure de Sauvegarde Locale (BACKUP_LOCAL)

Cette procédure garantit l'intégrité des données locales avant toute modification majeure du pipeline d'ingestion.

---

## 1. Sauvegarde Automatisée

Un script est disponible pour automatiser le dump de la base de données et l'archivage des fichiers d'entrée.

### Commandes
```bash
# Exécuter le script de sauvegarde
bash scripts/backup_local.sh
```

### Ce qui est sauvegardé
- **Base de données** : Dump SQL complet de PostgreSQL (`supervision_db`).
- **Dropbox Ingress** : Copie du dossier `dropbox_in/`.
- **Dossier Archive** : Copie du dossier `archive/`.

---

## 2. Sauvegarde Manuelle (En cas d'urgence)

Si le script échoue, utilisez ces commandes Docker :

### Dump PostgreSQL
```bash
docker exec supervision_db pg_dump -U admin supervision > backups/manual_dump_$(date +%Y%m%d).sql
```

### Copie des Fichiers
```bash
cp -r dropbox_in/ backups/files_$(date +%Y%m%d)/
```

---

## 3. Emplacement des Backups
Tous les backups sont stockés dans le dossier `/backups/` à la racine du projet. 
**Attention** : Ce dossier est inclus dans `.gitignore` et ne doit jamais être poussé sur le dépôt.
