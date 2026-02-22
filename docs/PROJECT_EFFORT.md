# Suivi de l'Effort Projet — TLS YPSILON

Ce document recense les heures investies dans la conception, le développement et la sécurisation de la plateforme **Supervision-V1**.

## Résumé
- **Dernière mise à jour** : 2026-02-21
- **Total cumulé** : 143 heures

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
