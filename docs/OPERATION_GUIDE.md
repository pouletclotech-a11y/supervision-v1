# Operation Guide

## 1. Deployment & Lifecycle

### Start Stack
```bash
docker compose up -d --build
```
*Wait for TimescaleDB to initialize (approx 20s on first run).*

### Stop Stack
```bash
docker compose down
```

### Restart Helper
To restart only the backend logic (code reload):
```bash
docker compose restart backend worker
```

## 2. Database Management

### Database Access
```bash
docker compose exec db psql -U admin -d supervision
```

### Backup
A script `backup_before_migration.sql` is available.
Manually:
```bash
docker compose exec db pg_dump -U admin supervision > backup_$(date +%F).sql
```

### Migrations
Les migrations sont gérées automatiquement au démarrage, mais peuvent être rejouées manuellement :
```bash
docker exec -i supervision_db psql -U admin -d supervision < backend/migrations/15_sliding_window_sequences.sql
docker exec -i supervision_db psql -U admin -d supervision < backend/migrations/12_rule_conditions.sql
```

### Seed & Données de Test (Alerting V3)
Pour valider le moteur d'alerte avec des scénarios réels (Séquences, AST) :
```bash
docker exec -i supervision_db psql -U admin -d supervision < backend/migrations/16_seed_test_rules.sql
```
*Cela injecte 4 types de règles (Simple, OpenOnly, Sequence, AST) pour la vérification.*

## 3. User Management (V2)

### Create First Admin
```bash
docker compose exec backend python create_admin.py admin@example.com MySecr3t
```

### Reset Password
Simply run the `create_admin.py` script again with the same email and new password. The script handles updates idempotently.

## 4. Monitoring & Debugging

### View Logs
```bash
docker logs -f supervision_worker    # Ingestion logs
docker logs -f supervision_backend   # API logs
```

### Navigation & Audit (Import Log)
L'interface de validation des données permet de naviguer dans l'historique complet des imports :
- **Pagination** : La liste des imports est paginée (serveur) pour garantir la fluidité.
- **Filtres** : Recherche par statut (SUCCESS/ERROR) et plage de dates.
- **Colonnes (Visibilité / Ordre)** : Personnalisez votre vue en masquant/réordonnant les colonnes via le menu DataGrid. Ces réglages persistent localement dans votre navigateur.
- **Colonnes (Largeur)** : Les largeurs ont été optimisées manuellement pour offrir une lecture confortable sans troncature excessive. Le défilement horizontal s'active automatiquement pour les contenus longs (ex: messages techniques). *Note : Le redimensionnement interactif à la souris n'est pas disponible dans la version Community actuelle.*
- **Audit** : Le compteur total permet de suivre le volume d'activité.

### Détails d'un Import (Événements)
Lorsque vous cliquez sur un import, la liste des événements s'affiche avec des informations enrichies pour l'analyse métier :
- **Action** : Affiche le type d'événement (`APPARITION` en rouge, `DISPARITION` en vert). Cela permet de repérer immédiatement les cycles d'alertes.
- **Code** : Affiche le code d'alarme ou de transmission brut (ex: `MVS`, `130`, `SMAIL`) issu directement du fichier source.
- **Filtres Rapides** : Utilisez les champs "Filtre Action" et "Filtre Code" en haut du tableau pour isoler instantanément des événements sur la page chargée.
- **Persistance** : Comme pour la table principale, la visibilité et l'ordre des colonnes sont mémorisés dans votre navigateur.

## 5. Storage & Uploads (V2.5)

### Locations
- **Photos de profil** : Stockées dans `/app/data/uploads` sur le serveur.
- **Accès** : Servies via http://localhost:8000/uploads/

### Persistence (Docker)
Pour ne pas perdre les photos au redémarrage, assurez-vous que le volume suivant est présent dans `docker-compose.yml` :
```yaml
services:
  backend:
    volumes:
      - ./data/uploads:/app/data/uploads
```

### Procedures
- **Backup** : Copiez le dossier `./data/uploads` lors de vos sauvegardes régulières.
- **Vider le cache** : Les fichiers sont renommés avec un timestamp (`user_{id}_{timestamp}.png`), ce qui évite les problèmes de cache navigateur.

## 6. Data Architecture & Persistence

### Code vs. Runtime Data
The repository follows a strict separation between application code and runtime data/backups:
- **Git Tracked**: Code, migrations, configuration templates, and `docker/seed.sql`.
- **Git Ignored**: `docker/data/` (Postgres/Redis volumes), `backups/`, `archive/`, `dropbox_in/`.

> [!WARNING]
> Never force-add `docker/data/` to Git. This folder contains a live Postgres instance and is platform-dependent.

### Docker Volumes
On a VPS or Production environment, data persistence is handled via Docker volumes mapped to host folders:
- `./docker/data/db` -> Postgres storage.
- `./archive` -> Permanent storage for ingested files.
- `./backups` -> Local dump storage (should be symlinked to a large external drive if possible).

## 7. Backup & Restore Strategy (Production)

### Strategy
1. **Database**: Daily logical dumps using `pg_dump`.
2. **Files**: Incremental rsync of the `archive/` folder to an offsite location (e.g., S3, OVH Cloud Archive).

### Restore to a fresh VPS
1. Clone the repo.
2. Initialize the DB structure using the seed:
   ```bash
   docker compose up -d db
   docker compose exec -T db psql -U admin -d supervision < docker/seed.sql
   ```
3. Restore the latest data dump:
   ```bash
   docker compose exec -T db psql -U admin -d supervision < latest_dump.sql
   ```
4. Restore the `archive/` folder from backup.

## 8. KNOWN ISSUES & TROUBLESHOOTING

| Symptom | Cause | Solution | Lesson |
| :--- | :--- | :--- | :--- |
| **Worker Crash with "ImportError"** | Circular dependency in `config.py` vs `config_loader.py`. | Moved imports to top-level or inside functions to break the cycle. | Keep configuration loading simple and acyclic. |
| **Docker: `02_normalization.sql` not found** | Windows file system vs Linux Docker volume mounting. | Embedded the SQL script directly into the Python migration runner. | Avoid relying on complex volume binds for initialization scripts on Windows. |
| **API 500 Error on GET** | Pydantic V2 strictness on ORM objects. | Added `model_config = ConfigDict(from_attributes=True)` to schemas. | Pydantic V2 requires explicit opt-in for ORM mode. |
| **100% Events Marked Duplicate** | Deduplication used `time.time()` (Processing Time) vs `event.timestamp`. | Changed Dedupe key to use Event Timestamp Bucket. | Idempotence must rely on deterministic data, not processing time. |
| **UI: Zebra Striping Broken** | Default MUI CSS specificity was higher than custom class. | Used `sx` prop or `!important` utility classes correctly. | Ensure custom theme classes have sufficient specificity. |
| **Site Code contains "C-"** | Raw data often has prefixes (e.g., `C-69000`). | added Regex `\D` replacement in Normalizer. | Always sanitize identifiers (Digits Only) before storage. |
