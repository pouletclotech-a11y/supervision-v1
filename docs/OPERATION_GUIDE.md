# OPERATION GUIDE — TRIAGE DATA VALIDATION

Ce document décrit la procédure pour diagnostiquer et résoudre les régressions d'affichage dans la page "Data Validation".

## 1. Procédure de Triage Rapide

Si la page "Data Validation" semble vide ou incohérente :

### Étape 1 : Vérification DB (Source de Vérité)
Vérifiez si les données existent réellement en base de données pour l'import concerné.
```sql
SELECT 
    import_id, 
    COUNT(*) AS total, 
    SUM(CASE WHEN time IS NULL THEN 1 ELSE 0 END) AS time_null,
    SUM(CASE WHEN site_code IS NULL OR site_code='' THEN 1 ELSE 0 END) AS site_null
FROM events 
WHERE import_id = <ID>
GROUP BY import_id;
```
*   **Si total > 0 et null-rate = 0** : Le problème est dans l'API ou l'UI.
*   **Si total = 0** : Le problème est dans l'ingestion (Parser).

### Étape 2 : Vérification API (Shape & Auth)
Testez l'endpoint d'événements sans passer par l'UI.
```bash
curl -s "http://localhost:8000/api/v1/imports/<ID>/events?limit=5"
```
*   **Vérifiez le champ date** : Il doit s'appeler `time` (pas `timestamp`).
*   **Vérifiez la structure** : Doit être `{ "events": [...], "total": N }`.

### Étape 3 : Nettoyage UI
Si la DB et l'API sont OK, le problème vient probablement des filtres persistés ou de la pagination.
*   Utilisez le bouton **Reset Filters** (icône X) dans la barre d'outils des événements.
*   Changez d'import pour forcer le reset du `pageIndex`.

## 2. Guide d'Ingestion (Phase 4 Standards)

### Archivage Déterministe
Depuis la Phase 4, chaque import possède deux colonnes d'archivage :
- `archive_path` : Le fichier source (XLS/XLSX/TSV).
- `archive_path_pdf` : Le compagnon PDF (si disponible).
### Supervision de la Qualité (Phase 5.5)
Le système calcule désormais des indicateurs de qualité par import :
- **Created Ratio** : Pourcentage de lignes ayant pu être transformées en événements (nécessite un horodatage valide).
- **Action Ratio** : Pourcentage d'événements ayant une action métier identifiée (APPARITION/DISPARITION/etc.).
- **Code Ratio** : Pourcentage d'événements ayant un code détecté (format `$CODE` ou regex).

L'extraction des codes conserve les symboles `$`, `-`, `_`, `/`, `.` mais s'arrête sur les délimiteurs forts (espace, parenthèse, virgule).

#### Endpoints de Qualité
- `GET /api/v1/imports` : Résumé des ratios dans `quality_summary`.
- `GET /api/v1/imports/{id}/quality-report` : Détails techniques des erreurs de parsing.
L'API privilégie `archive_path_pdf` pour les téléchargements de type `pdf`.

### Regroupement Logique (Phase 6 V1.3)
Depuis la Phase 6 V1.3, les pièces jointes d'un même email sont regroupées en un seul lot logique :
- **Clé de regroupement** : `Message-ID` de l'email source (stocké dans `source_message_id`).
- **Comportement** : Le premier fichier traité (Excel ou PDF) crée l'`ImportLog`. Le second fichier est rattaché au même ID, mettant à jour les métadonnées et les chemins d'archivage (`archive_path_pdf`).
- **Sécurité** : La sélection du profil PDF est pilotée par des `filename_regex` strictes pour éviter les collisions entre SPGO et CORS.

### Profils Stricts
Le `ProfileMatcher` utilise les regex suivantes pour les PDF :
- SPGO : `YPSILON\.pdf`
- CORS : `_HISTO\.pdf`
Une priorité plus élevée (20) est donnée à CORS pour garantir que `_HISTO.pdf` est détecté avant le pattern générique SPGO.

### Notes d'opérateurs (SPGO)
Les lignes contenant uniquement une heure (ex: `14:25`) sans date sont classées en `OPERATOR_NOTE`. L'horodatage est automatiquement reconstruit à partir de la date du dernier événement de sécurité rencontré dans le même bloc client.

## 3. Ingestions de Test (Admin)

L'application intègre un outil d'upload manuel pour valider les paires Excel + PDF sans passer par le script local.

### Procédure Admin Test Upload
1. Accédez à la page **Admin > Test Ingest**.
2. Sélectionnez le **Provider** (ex: SPGO).
3. Uploadez le fichier **Excel/TSV** (obligatoire).
4. Uploadez le fichier **PDF compagnon** (optionnel).
5. (Optionnel) Cochez **Strict Baseline** pour forcer la vérification des compteurs 157/162.
6. Cliquez sur **Lancer Test**.
7. Une fois terminé, un résumé s'affiche. Cliquez sur **Ouvrir dans Data Validation** pour inspecter les événements.

### Avantages
- Statut `MANUAL_VALIDATION` pour isoler les tests de la production.
- Matching PDF automatique si les deux fichiers sont fournis.
- Redirection directe vers les résultats pour analyse rapide.

## 4. Triage ResponseValidationError (Schema Hardening)

Si l'API renvoie une Erreur 500 avec `fastapi.exceptions.ResponseValidationError` dans les logs du backend :

### Causes fréquentes
- **Mismatch Type JSONB** : La base de données contient une liste `[]` alors que le schéma attend un dictionnaire `{}` (ou inversement).
- **Valeurs Nulles** : Une colonne obligatoire en Pydantic est `NULL` en base de données sans valeur par défaut.

### Résolution
1. **Identifier les rows coupables** via SQL `jsonb_typeof()`.
2. **Lancer le script de correction** :
   ```bash
   docker compose exec backend sh -c "export PYTHONPATH=/app && python /app/scripts/fix_profile_data.py --apply"
   ```
3. **Vérification des validateurs Pydantic** : Utiliser `@validator(..., pre=True)` pour coerrcer les types (ex: `[] -> {}`) avant la validation finale.
