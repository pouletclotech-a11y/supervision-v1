# Project Roadmap

This document outlines the current status (V1), immediate priorities (B1), and the long-term vision (V2) for the Supervision Tool.

> [!NOTE]
> **Priority Rule**: No V2 feature implementation should begin before the **B1 (Alarm Rules)** phase is fully validated operationally.

---

## Phase 2.A — Business Metrics Layer
**Status**: `✅ TERMINÉE` | **Livré le**: 2026-02-22

Mise en place du layer de comptage des raccordements (codes site distincts) par télésurveilleur.

- **Compteur raccordements** : `site_connections` → upsert idempotent via `ON CONFLICT(provider_id, code_site) DO UPDATE`
- **Classification SMTP** : `ClassificationService` dynamique — règles en DB (`EXACT / DOMAIN / CONTAINS / REGEX`), priorité configurable
- **Providers génériques seedés** : `PROVIDER_ALPHA`, `PROVIDER_BETA`, `PROVIDER_GAMMA`, `PROVIDER_UNCLASSIFIED`
- **Fallback garanti** : tout import sans match → `PROVIDER_UNCLASSIFIED`
- **Dashboard admin** : `/admin/business-metrics` — widgets, graphique Recharts, drilldown paginé
- **API** : `GET /summary`, `/timeseries`, `/sites`, `/smtp-rules`
- **Tests** : 9/9 tests unitaires passés (classification SMTP)
- **Source SMTP officielle** : `imports.import_metadata->>'sender_email'`

> [!NOTE]
> **Stabilisation ingestion validée avant Phase 2.B.**

---

## Phase 2.B — Provider Monitoring Layer
**Status**: `✅ TERMINÉE` | **Livré le**: 2026-02-23

Renforcement du module `MonitoringProvider` avec des paramètres opérationnels pour surveiller la “santé du flux” et détecter les anomalies de réception.
- [x] Bugfix : NotNullViolation sur Monitoring Providers (Phase 2.B)

### 1. Évolutions du Modèle (MonitoringProvider)
- **recovery_email** : Contact technique pour les alertes de santé du flux.
- **expected_emails_per_day** : Seuil nominal d'imports/emails attendus par 24h.
- **expected_frequency_type** : Granularité de surveillance (`daily`, `weekly`).
- **silence_threshold_minutes** : Fenêtre de tolérance avant déclenchement d'alerte de silence (par défaut 1440m = 24h).
- **last_successful_import_at** : Timestamp du dernier succès pour calcul efficace du silence.

### 2. Logique de Surveillance
- **Calcul "Attendu vs Reçu"** : Comparaison volumétrique sur 24h glissantes.
- **Détection de Silence** : Alerte automatique si `now() - last_successful_import_at > threshold`.
- **Incidents Flux** : Création d'événements `SYSTEM_SILENCE` et incidents internes visibles sur le dashboard.

### 3. Interface Admin & Monitoring
- **Configuration** : Nouveaux champs dans `Admin > Providers`.
- **Health Dashboard** : Widget "Santé des Flux" avec codes couleurs (Vert/Orange/Rouge) et jauges de complétion par provider.

---

## Phase 2.C — Dataset Réel & Validation Ingestion
**Status**: `PLANNED`

Validation end-to-end avec données réelles et enrichissement des KPI (Initialement 2.B).

## V1: Foundation (Stable & Acquired)
**Status**: `RELEASED` | **Version**: `1.0`

The foundation of the system is now stable and operational.

- **Ingestion**: 
  - Robust parsing of `.xls` (Source of Truth) and `.pdf` (Proof).
  - Normalization of events (Type, Severity, Zone, Site, Client).
  - "Dropbox" style ingress (`dropbox_in`) with automated archival.
- **Data Integrity**:
  - **Anti-Deduplication**: Two-tier logic (Burst Collapse + Hash-based Anti-Spam).
  - **Persistence**: PostgreSQL 16 + TimescaleDB for time-series efficiency.
- **User Interface**:
  - **Data Validation**: Dark theme, Zebra striping (Site Code based), effective filtering.
  - **Layout**: Stable responsive navigation.

---

## B2: Advanced Engine (XLS V2 + Alerting V3)
**Status**: `STARTING`

Evolution of the ingestion and alerting system to support complex business logic.

### 1. XLS Parsing V2 (Context-Aware)
- **Cell-Aware Reading**: Handle merged cells and inheritance from previous rows/columns.
- **Propagation Logic**: 
  - `site_code` (Col A) propagation to empty rows.
  - `day` (Col B) propagation to empty rows.
  - `date` (Col C) inheritance when only time is provided.
- **Full Times**: Reconstruct complete UTC times for every event line.

### 2. Incident Management
- **Pairing**: Match `APPARITION` and `DISPARITION` events to create `Incidents`.
- **States**: `OPEN`, `CLOSED`, `OPEN_ONLY` (no disparition).
- **Analytics**: Calculate incident duration and groupings.

### 3. Advanced Rules Engine
- **Event Catalog**: Centralized registry of event codes, categories, and default severities.
- **Frequency Analysis**: $X$ occurrences over $Y$ days (sliding window).
- **Temporal Sequences**: Detect Pattern A followed by Pattern B within $\Delta t$.
- **Boolean Logic**: Tree-based `AND` / `OR` rules using a library of named conditions.

### 4. Interactive Dry Run
- **Explanations**: Detailed "Why it matched" or "Why it failed" reports.
- **Visual Builder**: Rule construction interface integrated with the test engine.

---

## V2: Evolution & Business Logic (Vision)

**Status**: `PLANNED`

Scaling the tool for multi-user, multi-site operational excellence.

### 1. User Management & Security
- **RBAC**: Admin, Operator, Read-Only roles.
- **Access Control**: Granular permissions for Settings, Rules, and Dashboard access.

### 2. Advanced Dashboards
- **Synthetic Views**: High-level alert summaries.
- **Incident View**: Focused view on active problems.
- **Site/Group Views**: Aggregated statistics by site or custom groups.

### 3. Ticketing & Workflows
- **Lifecycle**: New -> In Progress -> Closed.
- **Actions**:
  - Emails (Internal/Client).
  - Technician Intervention requests.
- **Traceability**: Full history of actions and comments.

### 4. Intelligent Grouping
- **Concept**: Transform raw "Events" into qualified "Alerts" and "Incidents".
- **Goal**: Reduce noise by hiding raw lines unless specifically requested.

### 5. Client Groups
- **Logic**: Regroup sites by Client Chain or Region (fuzzy matching or manual grouping).
- **Analytics**: Multi-day trends per group.

### 6. Complex Rules Engine
- **Composite Rules**: `(Rule A AND Rule B) OR Rule C`.
- **Dependencies**: Prioritization of alarms based on context.
- **Calendars (FR)**:
  - Fixed Public Holidays.
  - Variable Holidays.
  - Integration as conditional logic for rules.

### 7. Internationalization (i18n)
- **Toggle**: FR / EN.
- **Default**: French.
