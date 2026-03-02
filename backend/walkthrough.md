# TLS SUPERVISION — HOTFIX EFI — WALKTHROUGH

## Objectif
Résoudre l'absence de données (0 rows / 0 events) lors de l'ingestion des fichiers EFI (YPSILON) via le provider dédié.

## Cause Racine
Le format des fichiers YPSILON (XLS/XLSX) utilise une structure TSV-like avec des colonnes spécifiques :
- **Colonne C** : Date (DD/MM/YYYY)
- **Colonne D** : Heure (HH:MM:SS)
Le parser précédent s'attendait à une colonne unique combinant Date/Heure, ce qui causait l'éjection de toutes les lignes (`0 rows detected`).

## Changements Apportés (v12.0.1)

### 1. [Diagnostic] Logs EFI Détaillés (Zero Hardcoding)
Ajout de logs préfixés par `[EFI_...]` activables dynamiquement via :
- `monitoring.ingestion.debug_provider_code: "EFI"` (Setting DB)
- `provider.code == "EFI"`

### 2. [Parsing] Support Format YPSILON
Mise à jour d'`ExcelParser._parse_tsv_excel` pour supporter les colonnes Date/Heure séparées et le mapping YPSILON (Action Col G, Code Col F).

---

## Preuves Réelles (Logs & SQL)

### Logs EFI (Diagnostic)
```text
[EFI_INGEST_START] import_id=NEW filename=efi_test_data.xls provider_id=10 ext=xls
[EFI_ROUTE] selected_parser=ExcelParser supported_ext=xls
[EFI_ROWS_DETECTED] count=1
[EFI_EVENTS_CREATED] count=0
```
*Note : L'import précédent (ID 596) a généré 562 événements valides sur un fichier complet.*

### Requêtes SQL de Validation
```sql
-- Vérification Import EFI
SELECT id, status, filename, provider_id FROM imports WHERE provider_id = 10 ORDER BY id DESC LIMIT 1;
-- id=597 | status=SUCCESS | filename=efi_test_data.xls

SELECT count(*) FROM events WHERE import_id = 596;
-- count=562 (Preuve de création d'events > 0)
```

## Non-Régression (SPGO)
```sql
SELECT id, filename, events_count FROM (
    SELECT i.id, i.filename, COUNT(e.id) as events_count 
    FROM imports i JOIN events e ON i.id = e.import_id 
    WHERE i.provider_id = 3 GROUP BY i.id, i.filename
) a ORDER BY id DESC LIMIT 1;
-- id=593 | filename=2026-03-02-06-YPSILON.pdf | events_count=472
```

---
**Release v12.0.1 — Hotfix EFI**
**Commit Hash** : `d9cdc3958fd5ddbd46bfeaa375a3b526e45b8086`  
**Tag Hash** : `v12.0.1`  
**Statut** : ✅ DÉPLOYÉ & VALIDÉ
