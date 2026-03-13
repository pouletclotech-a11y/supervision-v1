# Walkthrough — Correction Parser Excel CORS

Ce document présente les changements effectués pour corriger le mapping Excel du provider CORS et la procédure de validation effectuée.

## Changements Appliqués

### [Backend]
- **`worker.py`** : Transmission du `provider_code` au parser lors du traitement.
- **`excel_parser.py`** :
    - Implémentation du mapping spécifique CORS quand `provider_code == "CORS"`.
    - Mapping : A=Site, G=DateTime, H=State, I=AlarmCode, J=Details.
    - Détection de `OPERATOR_ACTION` en colonne N.
    - Règles de nettoyage strictes (respect des tirets et suffixes dans `alarm_code`).

### [Documentation]
- **`INGESTION_SPECS.md`** : Ajout des spécifications CORS.
- **`PROJECT_EFFORT.md`** : Enregistrement de l'intervention.

## Plan de Validation

### 1. Rebuild des Services
```bash
docker compose down
docker compose up -d --build
```

### 2. Test d'Ingestion
Rejouer le fichier en erreur :
```bash
# Copier le fichier vers dropbox_in pour déclencher l'ingestion
cp "archive\error\2026\03\13\2026-03-13-06-YPSILON_HISTO.xlsx" "dropbox_in\2026-03-13-06-YPSILON_HISTO.xlsx"
```

### 3. Vérification SQL
```sql
SELECT site_code, alarm_code, details, state
FROM events
WHERE source_file LIKE '%2026-03-13-06-YPSILON_HISTO.xlsx%'
ORDER BY created_at DESC
LIMIT 20;
```

### 4. Logs Worker
```bash
docker compose logs -f worker
```
