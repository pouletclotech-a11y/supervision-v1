# Dictionnaire de la Base de Données — TLS Supervision

Ce document décrit la structure physique de la base de données PostgreSQL (TimescaleDB) du projet.

## 1. Schéma Global
Le système utilise principalement le schéma `public`. Les tables liées aux séries temporelles (ex: `events`) bénéficient des fonctionnalités de TimescaleDB (hypertables).

---

## 2. Table : `imports`
Stocke l'historique des fichiers ingérés.

| Colonne | Type | Nullable | Défaut | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | integer | NO | nextval | PK |
| `filename` | varchar | NO | - | Nom original du fichier. |
| `status` | varchar | NO | 'PENDING' | SUCCESS, ERROR, IGNORED, REPLAY_REQUESTED. |
| `events_count` | integer | NO | 0 | Nombre d'événements extraits. |
| `duplicates_count` | integer | NO | 0 | Événements ignorés (déjà existants). |
| `unmatched_count` | integer | NO | 0 | Événements non classifiés. |
| `created_at` | timestamptz | NO | now() | Date de l'import. |
| `archive_path` | varchar | YES | - | Chemin vers le fichier archivé. |
| `file_hash` | varchar | YES | - | Hash du contenu pour l'idempotence. |
| `provider_id` | integer | YES | - | FK vers `monitoring_providers`. |
| `import_metadata` | jsonb | YES | - | Données riches (pairing, integrity, etc.). |

---

## 3. Table : `events` (Hypertable)
Stocke les événements de télésurveillance normalisés.

| Colonne | Type | Nullable | Défaut | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | integer | NO | nextval | PK |
| `time` | timestamptz | NO | - | **Partition Key**. Date/heure de l'événement. |
| `site_code` | varchar | YES | - | Code identifiant du raccordement. |
| `raw_message` | text | NO | - | Message brut reçu. |
| `raw_code` | varchar | YES | - | Code alarme/transmission brut. |
| `normalized_type` | varchar | YES | - | APPARITION, DISPARITION, TEST_ROUTINE, etc. |
| `severity` | varchar | YES | - | INFO, WARNING, CRITICAL, ALARM. |
| `import_id` | integer | YES | - | FK vers `imports`. |
| `created_at` | timestamptz | NO | now() | Date d'insertion. |

---

## 4. Table : `event_rule_hits`
Résultat de l'évaluation des règles métier sur les événements.

| Colonne | Type | Nullable | Défaut | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | integer | NO | nextval | PK |
| `event_id` | integer | NO | - | FK vers `events`. |
| `rule_id` | integer | NO | - | ID de la règle (0 si V1 hardcoded/config). |
| `rule_name` | varchar | YES | - | Code de la règle (ex: INTRUSION_NO_MAINTENANCE). |
| `hit_metadata` | jsonb | YES | - | Détails du déclenchement. |
| `created_at` | timestamptz | NO | now() | - |

---

## 5. Table : `site_connections`
Référentiel des sites détectés par provider.

| Colonne | Type | Nullable | Défaut | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | integer | NO | nextval | PK |
| `provider_id` | integer | NO | - | FK vers `monitoring_providers`. |
| `site_code` | varchar | NO | - | Code site normalisé. |
| `client_name` | varchar | YES | - | Nom du client (extrait de Col B XLS). |
| `total_events` | integer | NO | 0 | Compteur cumulé. |
| `last_seen_at` | timestamptz | YES | - | Dernière activité. |

---

## 6. Table : `monitoring_providers`
Configuration des télésurveilleurs.

| Colonne | Type | Nullable | Défaut | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | integer | NO | nextval | PK |
| `code` | varchar | NO | - | Identifiant court (ex: PROVIDER_A). |
| `label` | varchar | NO | - | Nom complet. |
| `is_active` | boolean | NO | true | - |
| `expected_emails_per_day` | integer | NO | 0 | Métrique de monitoring. |

---

## 7. Index Principaux
- `ix_events_time` : Index temporel (TimescaleDB).
- `ix_events_import_id` : Pour le drill-down depuis les imports.
- `ix_site_connections_provider_code` : Unique index `(provider_id, site_code)` pour l'idempotence.
- `ix_users_email` : Unicité des emails clients.
