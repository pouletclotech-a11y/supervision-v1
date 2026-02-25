# Architecture Documentation

> [!IMPORTANT]
> **Current Version**: `V1.0` (Stable)
>
> This document reflects the deployed architecture of the Supervision Tool V1.

## Overview
Supervision Tool V1 is a data ingestion and monitoring platform designed to collect, normalize, and deduce events from various sources (PDF, Excel, API) for security supervision.

## System Components

### Stable Components (Core)
These components are considered mature and should not be modified without significant justification.

#### 1. Ingestion Worker (`backend/app/ingestion`)
- **Role**: Watches `dropbox_in` for new files (PDF/XLS), parses content, normalizes events, applies deduplication logic, and inserts data into the database.
- **Key Files**:
    - `watcher.py`: Monitors directory changes.
    - `worker.py`: Main processing loop.
    - `normalizer.py`: Regex-based event enrichment.
    - `deduplication.py`: Redis-backed burst collapse and anti-spam.

#### 2. Backend API (`backend/app/api`)
- **Role**: Serves data to the frontend and provides debug endpoints.
- **Framework**: FastAPI (Python 3.11).
- **Security**: JWT Authentication + RBAC (Admin/Operator/Viewer).
- **Key Endpoints**:
    - `/api/v1/auth/login`: Authentication.
    - `/api/v1/imports`: Import logs and status (Secured).
    - `/api/v1/events`: Normalized event stream (Secured).
    - `/uploads`: Static file service for user profile photos (Public Read/Auth Write).

#### 3. Database Layer
- **Primary DB**: Postgres 16 (TimescaleDB extension enabled).
- **Tables**:
    - `users`: Credentials and Roles.
    - `events`: Hypertable (partitioned by time).
    - `imports`: Job logs.
    - `alert_rules`: Configuration for detection engine.
- **ORM**: SQLAlchemy (Async).

#### 4. Cache & Queue
- **Redis**: Used for task queueing, locks, and deduplication sliding windows.

#### 5. Moteur d'Alerte (V3)
-   **AlertingService**: Moteur hybride gérant trois modes :
    *   **SIMPLE (V3 Frequency)** : Compteurs glissants sur plusieurs jours (`sliding_window_days`) et mode `is_open_only`.
    *   **SEQUENCE (A ➔ B)** : Détection de patterns temporels (ex: MES puis Intrusion dans les 5 min).
    *   **AST (Logic Tree)** : Évaluation de prédicats complexes via des arbres logiques (AND/OR) référençant des `rule_conditions`.
-   **Déterminisme** : Le moteur privilégie l'évaluation dans l'ordre : Logic Tree > Séquences > Simple.
-   **CalendarService**: Gestion des jours fériés français pour le scoping temporel.

### Evolving Components
These areas are subject to change in upcoming V2 phases.

-   **Frontend (`frontend/`)**: Currently tailored for V1 Data Validation. Will evolve to support Dashboards and Ticketing (V2).
-   **Output Handling**: Currently alerts are logged. Future V2 will add Email/Push notifications.

## Data Flow
1.  **File Drop**: User/System places file in `dropbox_in`.
2.  **Detection**: Watcher detects file.
3.  **Parsing**: Parser extracts raw lines (`.xls` is authority, `.pdf` is proof).
4.  **Normalization**: Regex rules apply Type & Severity.
5.  **Deduplication**: Burst Collapse + Anti-Spam Hash.
6.  **Persistence**: Insert into DB.
7.  **Traçabilité**: Chaque import génère un `ImportLog` permettant l'audit, le filtrage par statut/date et le replay des événements.
8.  **Lifecycle**: File moved to `archive/YYYY/MM/DD`.

## Project Memory (Errors & Lessons)
*A record of significant technical challenges and their solutions to prevent regression.*

| Component | Issue | Cause | Solution | Lesson |
|-----------|-------|-------|----------|--------|
| **API** | Serialization Error (500) | **Pydantic V2** transition. | Updated schemas with `model_validate` and `from_attributes=True`. | Always check Pydantic V2 config/migration guides. |
| **Ingestion** | 100% Duplicates on re-import | **Deduplication Logic** used Redis TTL (processing time) vs Event Time. | Added `TIME_BUCKET` to the hash key logic. | Idempotence requires determinism based on *data content*, not *process time*. |
| **Docker** | `02_normalization.sql` not found | **Windows Volume Mount** issues with SQL files. | Embedded SQL directly into `run_migration.py`. | On Windows, prefer embedding critical init scripts or robust volume paths. |
| **UI** | Zebra Striping Readability | Default MUI styles overrode custom rows. | Implemented custom `row-theme-a/b` classes tied to `site_code`. | Use functional CSS classes for logic-based styling (like grouping by Site). |
| **Parsing** | Data Missing in Events | Regex applied before extraction. | Ordered normalization to ensure `site_code` (Digits) and `client_name` are extracted first. | Data cleaning (Digits only for Site Code) is crucial before storage. |

---

## Roadmap 2.A — Business Metrics Layer

### Vue d'ensemble
La Phase 2.A ajoute un layer de comptage des raccordements (codes site distincts) par télésurveilleur (Provider), avec classification automatique des imports par expéditeur SMTP.

### Flux de Classification & Business Counter

```
Email entrant
    │
    ├─ metadata.sender_email (exemple: "alerts@beta.com")
    │
    ▼
 ClassificationService
    │  Lit smtp_provider_rules (par priorité croissante)
    │  Match EXACT / DOMAIN / CONTAINS / REGEX
    │
    ├─ Match trouvé → provider_id = 2 (PROVIDER_BETA)
    └─ Aucun match  → provider_id = PROVIDER_UNCLASSIFIED
    │
    ▼
 Worker (pour chaque NormalizedEvent)
    │  UPSERT site_connections (ON CONFLICT provider_id, code_site)
    │  ├─ INSERT si nouveau raccordement (first_seen_at fixé une fois)
    │  └─ UPDATE last_seen_at + total_events++
    │
    ▼
 API Admin /business/
    ├─ /summary       → totaux par provider
    ├─ /timeseries    → nouveaux raccordements par mois/année
    ├─ /sites         → drilldown paginé
    └─ /smtp-rules    → CRUD des règles de classification
```

### Tables impliquées

| Table | Rôle |
|---|---|
| `monitoring_providers` | Registre des télésurveilleurs (code UNIQUE) |
| `smtp_provider_rules` | Règles de classification SMTP (priorité, match_type, pattern) |
| `site_connections` | Compteur business par (code_site, provider_id) |

- Provider `PROVIDER_UNCLASSIFIED` : fallback obligatoire si aucune règle ne matche

## Phase 2.B : Provider Monitoring Layer

### Vue d'ensemble
Cette couche surveille la régularité des flux entrants pour détecter les pannes chez les télésurveilleurs ou les problèmes réseau avant qu'ils ne deviennent critiques.

### Logique de Détection
1.  **Surveillance du Silence** : Le worker maintient `last_successful_import_at` pour chaque provider. Si `now() - last` dépasse `silence_threshold_minutes`, une alerte système est levée.
2.  **Volumétrie (Attendu vs Reçu)** : Un calcul périodique compare le nombre d'imports réussis sur 24h avec `expected_emails_per_day`.

### Composants de Monitoring
- **Background Task** : Analyse régulière des délais depuis le dernier import.
- **Incident System** : Génération d'incidents internes de type `SYSTEM_SILENCE` ou `SYSTEM_VOLUME_DROP`.

## Technology Stack
- **Languages**: Python 3.11, JavaScript/TypeScript (Next.js)
- **Containerization**: Docker Compose
- **Database**: PostgreSQL 16 + TimescaleDB
- **Cache**: Redis 7
- **Frontend**: Next.js 14 (React)
