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

### Gestion des Providers (Phase 2.A & 2.B)

Les providers (télésurveilleurs) peuvent être configurés via l'interface Admin ou directement via l'API.

#### Paramétrage du Monitoring (Phase 2.B)
Pour chaque provider, vous pouvez définir :
- **Seuil de silence** : Délai max (en minutes) sans réception avant alerte.
- **Volume attendu** : Nombre d'imports prévus par 24h.
- **Email de secours** : Contact pour les notifications de santé du flux.

#### Ajout d'une règle SMTP
Pour affecter automatiquement un mail entrant à un provider :
1. Aller dans **Admin > SMTP Rules**.
2. Ajouter une règle (ex: Type `DOMAIN`, Valeur `beta-telecom.fr`).
3. Définir la priorité (plus c'est haut, plus c'est testé tôt).

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

## 3. Gestion de l'Accès Admin (Sécurité)

### Seed Automatique au Démarrage
Le système vérifie au boot s'il existe au moins un utilisateur avec le rôle `ADMIN`.
- **En Développement** (`ENVIRONMENT=development`) : Si absent, un admin est créé avec `admin@supervision.local / SuperSecurePassword123`. Les tables sont créées automatiquement (`create_all`).
- **En Production** (`ENVIRONMENT=production`) :
  - L'auto-seed ne s'exécute **que si la table `users` existe** (migrations complétées).
  - Le mot de passe **doit** être défini via la variable d'environnement `DEFAULT_ADMIN_PASSWORD`.
  - La création de table automatique est **désactivée`.

### Variables d'Environnement Clés
| Variable | Valeur par défaut | Description |
|---|---|---|
| `ENVIRONMENT` | `production` | `production` ou `development`. |
| `DEFAULT_ADMIN_EMAIL` | `admin@supervision.local` | Email de l'admin par défaut. |
| `DEFAULT_ADMIN_PASSWORD` | *(Aucune en prod)* | **Obligatoire en production** pour le seed initial. |
| `AUTO_SEED_ADMIN` | `True` | Désactiver pour empêcher tout auto-seed. |

### Monitoring des Providers (Phase 2.B)

Les colonnes de monitoring dans `monitoring_providers` sont configurées avec des valeurs par défaut strictes pour éviter les erreurs d'insertion :
- `expected_emails_per_day` : 0
- `expected_frequency_type` : 'daily'
- `silence_threshold_minutes` : 1440 (24h)
- `monitoring_enabled` : false
- `is_active` : true

#### Vérification de la structure et des defaults
Pour vérifier que la base de données est correctement configurée :

```powershell
docker compose exec db psql -U admin -d supervision -c "SELECT column_name, is_nullable, column_default FROM information_schema.columns WHERE table_name='monitoring_providers' AND column_name IN ('expected_emails_per_day','expected_frequency_type','silence_threshold_minutes','monitoring_enabled','is_active');"
```

#### Vérification des données
Pour lister les 5 derniers providers et leurs paramètres de monitoring :

```powershell
docker compose exec db psql -U admin -d supervision -c "SELECT code, expected_emails_per_day, expected_frequency_type, silence_threshold_minutes, monitoring_enabled, is_active FROM monitoring_providers ORDER BY id DESC LIMIT 5;"
```

### Maintenance Roadmap 9 (Cleanup)

#### Déduplication Logique
Les doublons historiques ont été marqués avec `dup_count = 1`. Pour tout nouveau calcul de métriques ou dashboard, il est recommandé d'utiliser la vue dédupliquée :
```sql
SELECT COUNT(*) FROM view_events_deduplicated;
```

#### Normalisation "C-"
Le préfixe `C-` (ex: `C-69000`) est automatiquement retiré lors de l'ingestion si le reste du code est numérique. Les anciens codes restent en base pour préserver l'historique, mais les rejeux et futurs imports seront harmonisés.
### Procédure de Secours (Dépannage Admin)
Si l'accès Admin est perdu ou si le password doit être forcé depuis le serveur :
```bash
docker compose exec backend python create_admin.py --email "votre@email.com" --password "NouveauPasswordSecurise"
```
*Cette commande est prioritaire sur l'auto-seed et mettra à jour l'utilisateur s'il existe déjà.*

---

## 4. Maintenance Database (Protections)

### Synchronisation des Tables (`sync_db.py`)
Le script `sync_db.py` (qui exécute `create_all`) est **verrouillé en production** pour éviter tout reset accidentel.

Pour outrepasser cette sécurité (usage exceptionnel) :
```bash
docker compose exec -e ALLOW_SYNC_DB=1 -e I_UNDERSTAND_DATA_LOSS=YES backend python sync_db.py
```

## 5. Monitoring & Debugging

### View Logs
```bash
docker logs -f supervision_worker    # Ingestion logs
docker logs -f supervision_backend   # API logs
```

### Ingestion Health Dashboard (Roadmap 5)
A synthetic dashboard is available on the main landing page to monitor ingestion health in real-time.

#### Health Status Legend
- 🟢 **OK**: All expected files received, events ingested, and integrity >= 95%.
- 🟡 **WARNING**: Integrity dropped below 95% OR PDF support files are missing for some XLS imports.
- 🔴 **CRITICAL**: No XLS files received for the day OR zero events ingested (potential parser failure).

#### API Endpoint
- `GET /api/v1/health/ingestion-summary`: Returns today's metrics aggregated by provider.
- *Dependencies*: Requires Administrator role.
- *Refresh Rate*: UI auto-refreshes every 60 seconds.

### Rule Trigger Monitoring (Roadmap 6)
Monitoring des déclenchements de règles d'alertes en temps réel.

#### Seuils d'Activité (config.yml)
Les statuts sont calculés selon des seuils modifiables dans `backend/config.yml` :
- `RULE_MONITORING_HIGH_THRESHOLD` (défaut: 100) -> 🔴 **HIGH**
- `RULE_MONITORING_LOW_THRESHOLD` (défaut: 1) -> 🟡 **LOW**

#### Drildown
Le clic sur une règle dans le dashboard redirige vers la page **Data Validation** pré-filtrée sur cette règle pour une analyse détaillée des événements.

#### API Endpoint
- `GET /api/v1/rules/trigger-summary?date=YYYY-MM-DD`
- *Dependencies*: Requires Administrator role.

### Business Rules Engine V1 (Stabilisation)
Les règles métier sont évaluées automatiquement par le worker après l'ingestion de chaque lot d'événements.

#### Règles V1 Actives
- `INTRUSION_NO_MAINTENANCE` : Déclenché si intrusion HL alors que le site n'est pas en maintenance.
- `ABSENCE_TEST` : Détecte l'absence de test cyclique prévu.
- `TECHNICAL_FAULT` : Capture les codes d'apparition de défaut technique.
- `EJECTION_48H` : Alerte sur les éjections (code 570) avec cycle de 48h.
- `ZONE_INHIBITION` : Repère les motifs `***` dans les messages.

#### Configuration (config.yml)
Les patterns et codes sont centralisés dans la section `business_rules`. Toute modification nécessite un redémarrage du service `worker`.

#### Vérification des Déclenchements
```bash
# Voir les dernières règles déclenchées
docker compose exec db psql -U admin -d supervision -c "SELECT rule_name, count(*) FROM event_rule_hits GROUP BY rule_name;"
```

#### Structured Logs (Roadmap 4)
Recherchez ces tags pour valider l'ingestion :
- `[Ingestion] ATTACHMENT_RECEIVED`: Nouveau fichier détecté.
- `[Ingestion] FILTER_DECISION`: ACCEPT/IGNORED (vérifie le format).
- `[Ingestion] PAIR_ATTEMPT`: Tentative de liaison PDF <-> XLS.
- `[Ingestion] PDF_SUPPORT_WRITTEN`: Confirmation de l'écriture des métadonnées PDF.
- `[Resolver] MATCH/FALLBACK`: Détails de l'identification du provider.

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
| **100% Events Marked Duplicate** | Deduplication used `time.time()` (Processing Time) vs `event.time`. | Changed Dedupe key to use Event Time Bucket. | Idempotence must rely on deterministic data, not processing time. |
| **UI: Zebra Striping Broken** | Default MUI CSS specificity was higher than custom class. | Used `sx` prop or `!important` utility classes correctly. | Ensure custom theme classes have sufficient specificity. |
| **Site Code contains "C-"** | Raw data often has prefixes (e.g., `C-69000`). | added Regex `\D` replacement in Normalizer. | Always sanitize identifiers (Digits Only) before storage. |
| **Frontend build broken** | Relative import `../../../utils/api` in generic pages. | Always use the alias `@/lib/api`. | Leverage TS paths for cleaner and more robust imports. |
| **DB Reset in Production** | `create_all` called on every boot in older versions. | Hard locking of `create_all` if `ENVIRONMENT != development`. | Production DB schema must only change via migrations. |
| **Emails "Lost"** | Missing keyword or invalid format. | Check `ImportLog` with status `IGNORED`. | Traceability is key for debugging ingestion pipelines. |

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

---

## Connexion PostgreSQL — Référence

> [!IMPORTANT]
> L'utilisateur de la base est **`admin`** (PAS `postgres`). La base s'appelle **`supervision`** (PAS `supervision_db`).

```bash
# Connexion psql directe
docker exec supervision_db psql -U admin -d supervision -c "SELECT now();"

# Vérification statuts imports
docker exec supervision_db psql -U admin -d supervision -c "SELECT status, COUNT(*) FROM imports GROUP BY 1 ORDER BY 2 DESC;"

# Structure event_rule_hits (inclut hit_metadata depuis Roadmap 10)
docker exec supervision_db psql -U admin -d supervision -c "\d+ event_rule_hits"
```

---

## Roadmap 10 — Alert Lifecycle + Client Report

### Nouveaux endpoints

| Méthode | URL | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/alerts/active` | Operator/Admin | Alertes actives (APPARITION sans DISPARITION) |
| `GET` | `/api/v1/alerts/archived?days=7` | Operator/Admin | Alertes fermées N derniers jours |
| `GET` | `/api/v1/client/{site_code}/report?days=30` | User | Rapport consolidé par site |

### Schéma ajouté (Roadmap 10)

```sql
-- Migration idempotente (rejouer sans risque)
ALTER TABLE event_rule_hits ADD COLUMN IF NOT EXISTS hit_metadata jsonb;
```

### Fix REPLAY_REQUESTED orphelins (2026-02-28)

Les imports bloqués en `REPLAY_REQUESTED` (suite aux sessions de replay Roadmap 9) ont été normalisés :

```sql
BEGIN;
UPDATE imports SET status = 'SUCCESS' WHERE status = 'REPLAY_REQUESTED' AND events_count > 0;
UPDATE imports SET status = 'ERROR'   WHERE status = 'REPLAY_REQUESTED' AND events_count = 0;
COMMIT;
```

**Résultat** : 32 → SUCCESS, 217 → ERROR. Total final : 51 SUCCESS, 222 ERROR.

---

## 9. Phase 2A Hotfix — Safe Replay & Hardening

### Safe Replay (Atomic REPLACE)
Le moteur de rejeu (`replay-all`) a été sécurisé pour éviter toute suppression globale destructive.

#### Modes de rejeu
- **REPLACE (Défaut)** : Supprime et recalcule les hits uniquement pour les événements traités dans le lot actuel. Aucune interruption globale du service.
- **FULL** : Vide l'ensemble de la table `event_rule_hits` avant de recalculer.
  - **Sécurité** : Nécessite le flag DB `monitoring.rules.replay_allow_full_clear` à `true` ET le paramètre API `force=true`.

#### Scope temporel
Le rejeu peut être restreint à une plage de dates (basée sur `Event.created_at`) :
```bash
# Exemple via curl (REPLACE par défaut sur une plage)
curl -X POST http://localhost:8000/api/v1/rules/replay-all \
     -H "Content-Type: application/json" \
     -d '{"date_from": "2026-03-01T00:00:00", "mode": "REPLACE"}'
```

### Robustesse des Settings
Les overrides via la table `settings` sont désormais typés et validés :
- Si une valeur JSON est invalide ou d'un type incorrect (ex: string au lieu de bool), le système logue un `WARNING` et utilise la valeur par défaut du `config.yml`.
- **Logs à surveiller** : `[SETTINGS_OVERRIDE_INVALID_JSON]`, `[SETTINGS_OVERRIDE_TYPE_MISMATCH]`.

### Sécurité Rule ID (ENGINE_V1)
Le fallback vers `ID=1` a été supprimé. Le système exige l'existence de la règle système nommée `ENGINE_V1`.
- Si manquante : le worker lève une `RuntimeError` et logue en `CRITICAL`.
- **Vérification SQL** :
  ```sql
  SELECT id, name, condition_type FROM alert_rules WHERE name='ENGINE_V1';
  ```

### Feature Flag Engine V1
Il est possible de désactiver le moteur V1 (legacy) tout en gardant le moteur V2 (DB) actif :
- Setting : `monitoring.rules.engine_v1_enabled` (`true`/`false`).
- Log : `[ENGINE_V1] enabled=false`.

---

## 10. Phase 2B — Scoring (V2)

### Scoring Engine
Le moteur de scoring permet de pondérer les hits des règles V2 et de filtrer le bruit.

#### Paramètres globaux (config.yml)
- `scoring_enabled`: `false` (par défaut). Si `false`, tous les hits sont enregistrés avec `score=NULL`.
- `score_threshold_default`: `0.7` (seuil pour enregistrer un hit).
- `score_default_weight`: `1.0` (poids par défaut si non spécifié par la règle).
- `score_normalization`: `1.0` (facteur de normalisation).
- `scoring_record_below_threshold`: `false`. Si `true` (Mode Audit), les hits sous le seuil sont enregistrés avec un flag.

#### Overrides par règle (logic_tree)
Chaque règle peut overrider les paramètres globaux dans son champ `logic_tree` :
- `"weight"`: `float` (ex: `1.5` pour une règle critique).
- `"score_threshold"`: `float` between `0..1`.
- `"scoring_enabled"`: `bool`.

#### Mode Audit (Calibration)
Pour calibrer les seuils sans perdre de données :
1. Régler `monitoring.rules.scoring_enabled` à `true`.
2. Régler `monitoring.rules.scoring_record_below_threshold` à `true`.
3. Analyser les hits en DB :
   ```sql
   SELECT rule_name, score, hit_metadata->'below_threshold' as below 
   FROM event_rule_hits 
   WHERE score IS NOT NULL;
   ```

#### Sécurité & Robustesse
- **Priorité**: Rule Override > DB settings > YAML defaults.
- **Validation**:
  - `weight` doit être `>= 0`.
  - `score_threshold` doit être entre `0` et `1`.
  - `normalization` doit être `> 0` (fallback `1.0` sinon).
- **Logs**:
  - `[SCORING_SKIPPED]`: Hit ignoré car score < seuil.
  - `[SCORING_INVALID_OVERRIDE]`: Override ignoré car type ou valeur invalide.
