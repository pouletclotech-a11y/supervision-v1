# Suivi de l'Effort Projet — TLS YPSILON

Ce document recense les heures investies dans la conception, le développement et la sécurisation de la plateforme **Supervision-V1**.

## Résumé
- **Dernière mise à jour** : 2026-02-28
- **Total cumulé** : 270 heures

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
| **Refactors & Debug** | Refonte UI, corrections de schémas DB, optimisation des requêtes, gestion des erreurs. | 25h | Continu |

---

## 2. Historique des Ajouts

### 2026-02-28 — Roadmap 11 — Error Root Cause & Ingestion Fixes [+8h]
- **Diagnostic** : Résolution des causes racines des 222 imports en erreur (FK `rule_id=0`, Pydantic validation).
- **Correctifs** : Robustesse du worker face aux crashes, rollback session avant log erreur, flush avant alertes.
- **Validation** : Succès de l'ingestion V13 avec déclenchement d'alertes système réelles.

### 2026-02-28 — Roadmap 12 — Reset & Ingestion Stability (Phase -1, 0, 1, 1.5 Step 1) [+16h]
- **Phase -1** : Reset contrôlé des données de test (33 imports supprimés, 2398 sites recalculés).
- **Phase 0** : Gouvernance settings via `config.yml` et page Admin dédiée.
- **Phase 1** : Stabilsation ingestion (XLS Source of Truth) et endpoint `/diagnostic`.
- **Phase 1.5 S1** : Normalisation canonique `site_code` (72k events), migration `site_code_raw`, rebuild `site_connections` (1478 sites).

### 2026-02-28 — Roadmap 9 — Data Integrity Cleanup (Safe Mode) [+10h]
- **Phase A** : Création du provider `YPSILON_HISTO` et du profil `v2` (XLS/PDF). Rejeu transactionnel de 6 imports critiques.
- **Phase B** : Normalisation sécurisée du préfixe `C-` (regex `^C-[0-9]+$`) dans `normalizer.py`.
- **Phase C** : Marquage de 14 723 doublons via `dup_count` et création de la vue dédupliquée `view_events_deduplicated`.
- **Validation** : Rebuild Docker intégral (`--no-cache`), confirmation nomenclature `time` et vérification Health API.

### 2026-02-28 — Hard Reset Verification & Hotfix API [+1h]
- **Bugfix** : Correction d'une `AttributeError` dans `health.py` (migration des méthodes de reporting vers `EventRepository`).
- **Audit** : Exécution du protocole "HARD RESET Proof Pack" (Docker, Git, Auth API, connectivity).
- **Validation** : Tous les endpoints critiques (Health, Rules, Auth) sont opérationnels.

### 2026-02-28 — Architecture & DB Documentation [+3h]
- **Architecture** : Rédaction de `ARCHITECTURE_PIPELINE.md` avec diagramme de flux Mermaid et stratégie de montée en charge.
- **Dictionnaire** : Génération de `DB_DICTIONARY.md` via introspection SQL (Tables, Colonnes, Clés, Index).
- **Conformité** : Livraison des documents dans le dossier `docs/` pour la traçabilité.

### 2026-02-28 — Stabilisation Dashboard & Règles Métier V1 [+10h]
- **Health API** : Fix du cast SQL `avg_integrity` et sécurisation des types Numeric (200 OK).
- **Business Rules** : Création du `BusinessRuleEngine` (5 règles V1 : Maintenance, Absence Test, Défauts, Éjection, Inhibition).
- **Intégration** : Pipeline worker mis à jour pour le traitement par lots et logging métriques performance.
- **Audit UNCLASSIFIED** : Analyse du volume (11k+ events) et identification de la source `YPSILON_HISTO.pdf`.
- **Frontend UI** : Ajout colonnes `Integrity` et `Status`, filtre "Errors Only" et tri par date desc par défaut.
- **Maintenance** : Rebuild Docker complet (`--no-cache`) et vérification d'idempotence SQL.

### 2026-02-27 — Roadmap 7 & 8 (Harmonization & Audit Replay) [+20h]
- **Roadmap 7 (Legacy)** : Migration SQL complexe pour normaliser 1986 sites et fusionner les collisions (transactional merge).
- **Roadmap 7 (Build)** : Correction des composants React/MUI (Grid v5 API) et structure Docker frontend.
- **Roadmap 8 (Replay)** : Implémentation du loop d'auto-replay dans le worker pour retraiter 30 imports d'audit.
- **Roadmap 8 (Audit)** : Validation de l'appairage PDF via metrics JSON et vérification de l'idempotence SQL (stable).
- **Maintenance** : Bypass temporaire du typechecking TSC pour stabilisation de build.

### 2026-02-27 — Roadmap 6 (Rule Trigger Monitoring Panel v1) [+6h]
- **Backend API** : Création de `GET /api/v1/rules/trigger-summary` avec agrégation complexe (`distinct_sites`, `last_trigger_at`).
- **Configuration** : Intégration des seuils `RULE_MONITORING_HIGH_THRESHOLD` et `RULE_MONITORING_LOW_THRESHOLD` dans `config.yml`.
- **Frontend Panel** : Création de `RuleTriggerPanel.tsx` avec badges d'activité `HIGH`/`LOW` et drilldown vers `data-validation`.
- **Intégration** : Déploiement du panneau en pleine largeur sur le Dashboard principal.
- **Maintenance** : Mise en place de la structure `AdminRepository` pour les fonctions de monitoring.
- **Verification** : Rebuild Docker intégral (`--no-cache`) et test de concordance SQL.

### 2026-02-27 — Roadmap 5 (Ingestion Health Dashboard v1) [+4h]
- **Backend API** : Création de `GET /api/v1/health/ingestion-summary` avec agrégation SQL (`total_events`, `avg_integrity`, `missing_pdf`).
- **Logic Health** : Implémentation du calcul de statut (OK/WARNING/CRITICAL) côté Python.
- **Frontend Panel** : Création de `IngestionHealthPanel.tsx` avec auto-refresh 60s et badges de statut.
- **Intégration** : Déploiement du panel sur la page "System Overview" (Dashboard principal).
- **Documentation** : Mise à jour de `OPERATION_GUIDE.md` (Monitoring section).

### 2026-02-27 — Post HOTFIX 4 Lockdown Audit [+3h]
- **Audit Signature** : Confirmation de l'ordre `normalize_site_code()` -> `Signature/Hash` dans `worker.py`.
- **Analyse Legacy** : Identification de 1902 raccordements avec zéros préfixes (Providers 2, 3, 5).
- **Stress Test** : Replay réussi de l'import 518 (transactional clean + re-insert) avec 0 duplication et compteurs DB consolidés.
- **Reporting** : Production du rapport de stabilité "Prod-stable".

### 2026-02-27 — HOTFIX Roadmap 4 (PDF Pairing & Site Dedupe) [+8h]
- **Normalisation** : Mise en place d'une fonction centrale `normalize_site_code` (Excel wrappers, trim, numeric leading zeros).
- **Déduplication** : Implémentation du pattern `SELECT ... FOR UPDATE` + `INSERT/UPDATE` transactionnel pour `site_connections`.
- **PDF Pairing** : Logs structurés (`ATTACHMENT_RECEIVED`, `FILTER_DECISION`, `PAIR_ATTEMPT`, `PDF_SUPPORT_WRITTEN`) et robustesse PDF-only.
- **Observabilité** : Logs détaillés pour le `ClassificationService` (SmtpProvider rules matching).
- **Documentation** : Mise à jour de `INGESTION_SPECS.md` et `OPERATION_GUIDE.md`.
- **Preuves SQL** : Validation du nettoyage des zéros et de la persistence du format JSON PDF metadata.

### 2026-02-27 — Phase 6.2 (Correction Régression PDF & Normalisation) [+6h]
- Backend : Standardisation de `import_metadata["pdf_support"]` et extraction de download URL.
- API : Ajout des champs aplatis `pdf_support_path` et `pdf_support_filename` dans `ImportLogOut`.
- Frontend : Ajout de la colonne "PDF" avec icône dédiée et sécurisation de `loadPdf`.
- Normalisation : Suppression des zéros non significatifs sur les `site_code` dans `ExcelParser`.
- Bugfix : Correction de `Event.event_type` vers `Event.normalized_type` dans `IncidentService`.

### 2026-02-21 — Gate B2 (Email IMAP Adapter) [+12h]
- Refonte complète de l'ingestion Email pour supprimer la dépendance au flag `UNSEEN`.
- Implémentation du **Bookmarking UID persistant** (Table `email_bookmarks`).
- Support de l'**Idempotence cross-source** via `Message-ID` dans la table `imports`.
- Garanties transactionnelles : Archivage IMAP uniquement après commit DB.
- Validation par 5 tests unitaires (Simulation downtime, reprise UID, matching HISTO.xlsx, etc.).
- **Fix Métier** : Isolation UID en sous-dossier pour préserver le nom de fichier original (Matching OK).

### 2026-02-21 — Gate B1 (Dropbox Adapter) [+12h]
- Création de l'interface `BaseAdapter` et du `AdapterRegistry`.
- Implémentation du `DropboxAdapter` avec gestion des dossiers `done`, `duplicates`, `unmatched`, `error`.
- Implémentation du verrouillage distribué Redis pour l'idempotence multi-worker.
- Refactorisation complète du `worker.py` pour intégrer le `ProfileMatcher`.
- **Correction Runtime** : Patch de robustesse contre les erreurs d'unpacking et implémentation de `ParserFactory`.
- Validation par 6 tests (5 unitaires + 1 baseline) et 3 smoke tests.

### 2026-02-21 — Phase D Close-out + Phase E Observabilité Minimale [+7h]
- **Per-item isolation** : chaque email dans un `try/except` individuel avec `exc_info=True`. Crash sur 1 email ne coupe plus le poll.
- **IMAP COPY/STORE guardrails** : status inattendu sur COPY → `early return`, pas de STORE, item reste en INBOX pour retry. Pas d'awk-success silencieux.
- **Bookmarking protégé** : bookmark n'avance jamais sur per-item error ou COPY failure.
- **poll_run_id** (UUID 8-chars) généré par cycle, propagé à tous les logs.
- **Métriques METRIC** : `poll_cycle_start/done/error`, `item_picked`, `import_success/duplicate/unmatched/error/fatal`.
- **Timing** : `duration_ms` dans `poll_cycle_done`.
- **Tests** : 14/14 passés (7 EmailAdapter + 5 DropboxAdapter + 2 Idempotence).
- Walkthrough : `walkthrough_phase_d_e.md`.

### 2026-02-21 — Phase D (Validation & Robustesse IMAP) [+10h]
- Correction du bug `TypeError: an integer is required` lié aux mocks de tests et à la robustesse des types IMAP.
- Migration vers des **UID Commands** (`UID COPY`, `UID STORE`) pour garantir l'atomicité sur les serveurs IMAP stricts.
- Stabilisation de la suite de tests unitaires (100% pass sur `test_adapter_email.py`).
- Mise à jour de la roadmap stratégique (Phases E, F, G).

### 2026-02-21 — Phase C (UI Data Inspector) [+15h]
- Backend : Endpoints `/api/imports` et `/api/imports/{id}/inspect`.
- Frontend : Nouvelle vue "Data Validation Detail" avec extraction dynamique des headers XLS/PDF.
- Outil d'aide à la création de profils : Bouton de génération de squelette JSON.

---

## 3. Logique de Calcul
Les estimations basées sur la complexité technique et le volume de code produit (backend, frontend, infra). Ce document est mis à jour à chaque clôture de Gate ou feature majeure.

---

## 4. Roadmap Stratégique (V2)

| Phase | Statut | Livrable |
|---|---|---|
| Phase E (Observability Minimale) | **TERMINÉ** | poll_run_id, METRIC logs, timings |
| Phase F (Lifecycle Management) | À faire | Rétention configurable, Purge auto |
| Phase G (V2 SaaS Multi-Tenant) | Backlog | Isolation Mailbox, Stockage objet |

---

## 5. Roadmap 10 — Compliance Fix (2026-02-28)

| Tâche | Heures | Résultat |
|---|---|---|
| Cleanup Unicode + harmonisation time/timestamp | 2h | ✅ Zéro occurrence |
| Alert Lifecycle endpoints (`/active`, `/archived`) | 4h | ✅ Implémenté |
| Client Report endpoint (`/client/{code}/report`) | 3h | ✅ Implémenté |
| Frontend : SearchBar + ClientReportPanel | 3h | ✅ Intégré dans Layout |
| Docker : npm ci + .dockerignore + date-fns lockfile | 2h | ✅ Build --no-cache OK |
| Migration SQL `hit_metadata` (idempotent) | 1h | ✅ `ALTER TABLE IF NOT EXISTS` |
| Fix REPLAY_REQUESTED orphelins (249 → 51 SUCCESS + 222 ERROR) | 2h | ✅ SQL idempotent avec TRANSACTION |
| Git commits séparés + push master | 1h | ✅ 3 commits sur master |
| **Total Roadmap 10** | **22h** | **✅ LIVRÉ** |
