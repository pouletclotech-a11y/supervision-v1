# Suivi de l'Effort Projet — TLS YPSILON

Ce document recense les heures investies dans la conception, le développement et la sécurisation de la plateforme **Supervision-V1**.

## Résumé
- **Dernière mise à jour** : 2026-03-21

---

## 1. Répartition par Phase

| Phase | Description | Heures Estimées | État |
| :--- | :--- | :---: | :--- |
| **Setup Infra** | Dockerization, PostgreSQL/TimescaleDB, Redis, Architecture multi-services backend/frontend. | 20h | Terminé |
| **Phase A (Core)** | Moteur d'ingestion, Profiling dynamique (vms_ypsilon), Parsing XLS/PDF, Déduplication temporelle. | 40h | Terminé |
| **Gates A1/A2 (Prod)** | Sécurisation du déploiement (Gates), Scripts de backup locaux/docker, Non-régression Gold Master. | 15h | Terminé |
| **Phase B (Adapteurs)** | Modularisation des entrées (Adapteur Dropbox), Locking Redis distribué, Archivage atomique. | 10h | Terminé |
| **Phase C (Inspector)** | API Ingestion Logs + UI Data Inspector (Headers extraction, Skeleton gen). | 15h | Terminé |
| **Phase D (Validation & Close-out)** | Guardrails IMAP per-item + fail-soft COPY/STORE, durcissement BookmarkProtection, tests idempotence. | 10h | **TERMINÉ** |
| **Phase E (Observability Minimale)** | poll_run_id UUID, métriques METRIC structurées, timings poll_cycle_done, poll_cycle_error. | 7h | **TERMINÉ** |
| **Phase 2A Hotfix** | Safe Replay (Atomic REPLACE), Rule ID safety (ENGINE_V1), Settings Robustness & Typing. | 4h | **TERMINÉ** |
| **Phase 2B Scoring** | Optional scoring behind flag, score column, per-rule overrides, audit mode (below_threshold). | 6h | **TERMINÉ** |
| **Phase 8 (Stability)** | Logic Regression & Schema Hardening (500/CORS Fixes). | 5h | **TERMINÉ** |
| **Phase 9 (Inspect)** | Inspection NaN-safe & Test Ingest multi-provider. | 4h | **TERMINÉ** |
| **Phase 10 (Replay)** | Rule Replay Stability & Performance (Cache settings). | 3h | **TERMINÉ** |
| **Phase 11 (Catalog V4)** | Optimisation SQL & Durcissement logique "Vérité" (100% invariant). | 4h | **TERMINÉ** |
| **Phase 1 (Synthèse)** | Invariance Slider, Token Split, Log Context (±10m), Intrusion Counter, Persistent Alerts. | 8h | **TERMINÉ** |
| **Phase 2 (Ack)** | Workflow d'acquittement manuel avec justification, opérateur et traçabilité AuditLog. | 4h | **TERMINÉ** |
| **Refactors & Debug** | Refonte UI, corrections de schémas DB, optimisation des requêtes, gestion des erreurs. | 25h | Continu |

---

### 2026-03-13 — Correction Parser Excel CORS [+2h]
- **Status**: DONE (Mar 13, 2026)
- **Description**: Correction du mapping des colonnes pour les fichiers Excel du provider CORS et gestion des actions opérateur.
- **Key Contributions**:
    - `site_code` -> Colonne A
    - `datetime` -> Colonne G
    - `state` -> Colonne H
    - `alarm_code` -> Colonne I
    - `details` -> Colonne J
    - `operator_action` -> Colonne N (Extraction et marquage `OPERATOR_ACTION`)
- **Validation**: Test d'ingestion sur le fichier `2026-03-13-06-YPSILON_HISTO.xlsx`.

---

## 2. Historique des Ajouts

### 2026-03-22 — Phase 2 — Workflow d'Acquittement & Audit [+4h]
- **Status**: DONE (Mar 22, 2026)
- **Description**: Ajout de la capacité d'acquittement manuel des incidents pour les opérateurs.
- **Key Contributions**:
    - **Backend** : Migration DB (colonnes `acknowledged_*`), endpoint `/ack` et intégration `AuditLog`.
    - **Frontend** : Dialogue d'acquittement avec justificatif obligatoire dans `ActiveIncidentsPanel`.
    - **Traçabilité** : Enregistrement automatique de l'opérateur, date/heure et commentaire.
- **Validation** : Script `verify_ack_logic.py` validé (Open -> Ack -> Auto-Close).

### 2026-03-22 — Phase 1 — Synthèse Chantiers & Stabilisation [+8h]
- **Status**: DONE (Mar 22, 2026)
- **Description**: Implémentation complète de la phase demandée par Sébastien pour améliorer le catalogue, le contexte et le suivi des alertes.
- **Key Contributions**:
    - **Catalogue** : Slider d'invariance (50-100%) et affichage de la distribution des tokens.
    - **Contexte** : Visualisation temporelle ±10 min pour chaque événement/alerte.
    - **Dashboard** : Compteur de sites distincts en intrusion et panel d'alertes persistantes (Incidents).
    - **Backend** : Service d'incidents (Apparition/Disparition) avec normalisation des clés pour la clôture automatique.
- **Validation** : Test script global validé dans le container (Ouverture/Fermeture). Vérification des endpoints `/context` et `/incidents`.

### 2026-03-21 — Phase 11 — Optimisation & Durcissement Catalogue V4 [+4h]
- **Status**: DONE (Mar 21, 2026)
- **Description**: Résolution des timeouts catalogue et durcissement de la logique de génération des labels (Règle 100% Sébastien).
- **Key Contributions**:
    - Indexation SQL sur `events.raw_code` (Gain performance 5x).
    - Refonte de `get_canonical_label` (100% invariance, exclusion des mots d'état comme "APPARITION").
    - Correction du label `$0001` (Nucleus vide -> Fallback sur le CODE propre).
- **Validation**: Vérification par subagent browser (Loading ~12s, labels $0001/$710 validés).

### 2026-03-20 — Annuaire V3 & Planification "Catalogue de Vérité" [+5h]
- **Status**: DONE (Mar 20, 2026)
- **Description**: Finalisation du module Annuaire (Pagination, Actions) et conception du Catalogue de Vérité V4.
- **Key Contributions**:
    - Implémentation du module UI interactif avec pagination et colonne "TYPE(S) ACTION".
    - Bugfix SQL (`GROUP BY` correct) et UI (`Tooltip` wrapper `<span>`).
    - Audit technique du moteur de règles (`match_category`, `ast_logic`, `window_sec`).
    - Conception de l'algorithme "Canonical Label" par extraction de tokens invariants (seuil 90%).
- **Validation**: Vérification par subagent (Screenshots validés).

### 2026-03-20 — Phase 3 — Assistant Catalogue & Aide aux Règles [+3h]
- **Status**: DONE (Mar 20, 2026)
- **Description**: Intégration du Catalogue V4 comme assistant contextuel dans l'éditeur de règles.
- **Key Contributions**:
    - Bouton "Aide Catalogue" déclenchant un Drawer latéral.
    - Injection automatique du triplet `code`/`label`/`category` dans le formulaire de règle.
    - Ajout de tooltips explicatifs sur les champs techniques (`match_category`, `match_keyword`).
    - Unités temporelles explicites (`sec`, `jours`) sur les fenêtres de fréquence.
- **Validation**: Vérification de la structure JSX et de la présence du code assistant.

### 2026-03-19 — Audit Technique Moteur de Règles & Documentation [+4h]
- **Status**: DONE (Mar 19, 2026)
- **Description**: Audit complet du moteur de règles (Simple, Sequence, AST) et production de la documentation utilisateur.
- **Key Contributions**:
    - Identification du mapping réel des champs de règle (`match_category` -> `category`, `match_keyword` -> `normalized_message`).
    - Analyse du comportement des fenêtres temporelles (`window_sec=0` / `max_delay=0`).
    - Vérification de l'état (inactif) de l'alerte email.
    - Établissement du plan de passage aux "Alertes Persistantes" (Apparition/Disparition).
    - Création de la notice utilisateur `documentation_alertes.md`.
- **Validation**: Vérification croisée entre `alerting.py`, `business_rules.py` et `repository.py`.

### 2026-03-06 — Phase 11 — Attachment Grouping & PDF Security [+6h]
- **Status**: DONE (Mar 06, 2026)
- **Description**: Implemented reliable grouping of Excel/PDF attachments by email source and hardened PDF profile selection.
- **Key Contributions**: Logic for single ImportLog reuse via `source_message_id`, enriched `import_metadata` with email headers, and strict `filename_regex` for PDF profiles to prevent SPGO/CORS collisions.
- **Validation**: Fixed an alerting engine regression (`AttributeError` on metadata). Validated grouping and matching via SQL proofs and simulation scripts.

### 2026-03-05 — Phase 10 — Replay All Optimization [+3h]
- **Status**: DONE (Mar 05, 2026)
- **Description**: Fixed 500/CORS error on `replay-all` and optimized DB query per-event overhead.
- **Key Contributions**: Resolved a `ResponseValidationError` caused by name collision, and implemented a settings cache in `BusinessRuleEngine` to avoid thousands of redundant SQL queries during large replays.
- **Validation**: Stress test with 103,409 events completed in ~2 minutes with 200 OK.

### 2026-03-05 — Phase 9 — Inspection & Test Ingest [+4h]
- **Status**: DONE (Mar 05, 2026)
- **Description**: Fixed 500 ERROR on `/inspect` due to `NaN` and expanded `test-ingest` to all providers.
- **Key Contributions**: Robust JSON sanitization for inspection results, transition to production-grade `ProfileMatcher` for admin testing, and refactoring format detection to shared utilities.
- **Validation**: Verified `NaN` conversion to `null`, multi-provider support (CORS), and `strict_baseline` safety checks.

### 2026-03-05 — Phase 8 — Regression & Stability Fixes [+5h]
- **Status**: DONE (Mar 05, 2026)
- **Description**: Fix for `ResponseValidationError` on admin endpoints and logic cleanup for ingestion profiles.
- **Key Contributions**: Hardened Pydantic schemas with `coerce_empty_list_to_dict` validators, corrected SQLAlchemy model defaults for JSONB fields, and created an idempotent database synchronization script (`fix_profile_data.py`).
- **Validation**: Manual verification of `/api/v1/admin/profiles` (200 OK) and `test-ingest` robustness with dummy files (400/200 clean responses). Frontend access restored.

### 2026-03-04 — Phase 6.5 — Operational Ingestion Tool (Admin) [+7h]
- **Backend API**: Endpoint `/test-ingest` + Logic multipart (Hardened).
- **Frontend UI**: Page `Admin > Test Ingest` + Routing in Sidebar.
- **Security**: File size limits, NamedTempFile, and transaction rollbacks.

### 2026-03-04 — Phase 6 — SPGO Hardening & PDF Mirroring [+5h]
- **Status**: DONE (Mar 04, 2026)
- **Description**: Re-parsing of SPGO XLS/TSV and PDF reports to ensure 100% time coverage and correct classification of Operator Notes/Actions.
- **Key Contributions**: Strict SPGO indexing (A..F), Time reconstruction for partial timestamps, OCR-ready PDF mirror parsing, and PDF companion linking in DB (`archive_path_pdf`).
- **Validation**: CI Golden Gate pass (SPGO: 319, CORS: 1832). SQL proof of 0 null-time.
- **Ops** : Heartbeat Redis worker (30s) + Endpoint `/health` (DB/Redis/Worker check).

[... Historique Troncqué ...]

---

**Total cumulé** : 386 heures
