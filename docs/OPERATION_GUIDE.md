# Operation Guide

> [!NOTE]
> **Dernière mise à jour** : 2026-02-22 — Phase 2.A terminée. Backend opérationnel.

---

## 0. Commandes Essentielles (État Système)

```bash
# État des containers
docker compose ps

# Logs worker (ingestion en cours)
docker logs -n 50 supervision_worker

# Logs backend (API)
docker logs -n 50 supervision_backend

# Compter les événements en DB
docker compose exec db psql -U admin -d supervision -c "SELECT COUNT(*) FROM events;"

# Compter les raccordements par provider
docker compose exec db psql -U admin -d supervision -c \
  "SELECT p.code, COUNT(s.id) AS sites FROM monitoring_providers p LEFT JOIN site_connections s ON p.id = s.provider_id GROUP BY p.code;"

# État des imports
docker compose exec db psql -U admin -d supervision -c \
  "SELECT status, COUNT(*) FROM imports GROUP BY status;"
```

---

## 0.B Procédure d'Ingestion Manuelle

> [!IMPORTANT]
> Suivre ces étapes dans l'ordre pour valider une ingestion end-to-end.

1. **Déposer le fichier** dans le répertoire d'ingress :
   - Via Dropbox : copier le `.xls` dans `./dropbox_in/`
   - Via IMAP : envoyer l'email avec pièce jointe à l'adresse configurée

2. **Vérifier que l'import est traité** :
   ```bash
   docker logs -f supervision_worker 2>&1 | grep -E "SUCCESS|ERROR|import_"
   ```
   Attendre le message : `event=import_complete status=SUCCESS`

3. **Contrôler les événements insérés** :
   ```bash
   docker compose exec db psql -U admin -d supervision -c "SELECT COUNT(*) FROM events;"
   ```
   Résultat attendu : `> 0`

4. **Vérifier l'incrémentation des raccordements** :
   ```bash
   docker compose exec db psql -U admin -d supervision -c \
     "SELECT code_site, total_events, last_seen_at FROM site_connections ORDER BY last_seen_at DESC LIMIT 10;"
   ```

5. **Valider la classification du provider** :
   ```bash
   docker compose exec db psql -U admin -d supervision -c \
     "SELECT p.code, i.id, i.status FROM imports i JOIN monitoring_providers p ON i.provider_id = p.id ORDER BY i.created_at DESC LIMIT 5;"
   ```

---

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

### Create First Admin (Deterministic Seed)
```bash
docker compose exec backend python create_admin.py --email admin@supervision.local --password SuperSecurePassword123
```
Cette commande est idempotente : elle crée l'utilisateur s'il n'existe pas, ou met à jour son mot de passe s'il existe déjà.

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

---

## Roadmap 2.A — Business Metrics Layer

### Aperçu
La Phase 2.A ajoute le comptage automatique des raccordements (codes site distincts) par télésurveilleur, avec classification SMTP dynamique.

### Migrations SQL (ordre d'exécution)

```powershell
# 1. Enrichissement de site_connections (last_seen_at, total_events)
Get-Content backend/migrations/17_business_counter_updates.sql | docker exec -i supervision_db psql -U admin -d supervision

# 2. Seed des providers génériques
Get-Content backend/migrations/18_seed_providers.sql | docker exec -i supervision_db psql -U admin -d supervision
```

> [!IMPORTANT]
> Ces migrations sont **strictement non-destructives** (`ADD COLUMN IF NOT EXISTS`, `ON CONFLICT DO NOTHING/UPDATE`). Elles peuvent être rejouées sans risque.

### Commandes de maintenance

```bash
# Lister les providers actifs
docker exec supervision_db psql -U admin -d supervision -c "SELECT code, label FROM monitoring_providers WHERE is_active = true;"

# Voir les règles SMTP actives (par priorité)
docker exec supervision_db psql -U admin -d supervision -c "SELECT p.code, r.match_type, r.match_value, r.priority FROM smtp_provider_rules r JOIN monitoring_providers p ON r.provider_id = p.id WHERE r.is_active = true ORDER BY r.priority;"

# Contrôle des compteurs de raccordements
docker exec supervision_db psql -U admin -d supervision -c "SELECT p.code, count(s.id) AS sites, sum(s.total_events) AS events FROM monitoring_providers p LEFT JOIN site_connections s ON p.id = s.provider_id GROUP BY p.code;"
```

### Ajouter une règle de classification SMTP

```bash
# Exemple : tous les emails du domaine @example.org → PROVIDER_ALPHA
docker exec supervision_db psql -U admin -d supervision -c "
INSERT INTO smtp_provider_rules (provider_id, match_type, match_value, priority, is_active)
SELECT id, 'DOMAIN', 'example.org', 15, true
FROM monitoring_providers WHERE code = 'PROVIDER_ALPHA'
ON CONFLICT DO NOTHING;"
```

### API Endpoints Business

| Méthode | URL | Description |
|---|---|---|
| `GET` | `/api/v1/admin/business/summary` | Totaux par provider |
| `GET` | `/api/v1/admin/business/timeseries?granularity=month` | Nouveaux raccordements par mois |
| `GET` | `/api/v1/admin/business/sites?page=1&size=50` | Drilldown paginé |
| `GET` | `/api/v1/admin/business/smtp-rules` | Liste des règles SMTP |

### Tester la suite business

```bash
# Tests unitaires (classification SMTP avec mocks)
docker compose exec -w /app backend python -m pytest tests/test_business_counter.py -v -k "not integration"
```

### UI Admin

Accessible dans l'interface admin : **Admin → Métriques Business**
- Route : `/admin/business-metrics`
- Contenu : 4 widgets de synthèse, graphique d'évolution, table drilldown paginée

### Fallback obligatoire

Si aucune règle SMTP ne matche l'expéditeur, l'import est automatiquement attribué au provider `PROVIDER_UNCLASSIFIED`. Ce provider **doit toujours exister** en base (inclus dans `18_seed_providers.sql`).
