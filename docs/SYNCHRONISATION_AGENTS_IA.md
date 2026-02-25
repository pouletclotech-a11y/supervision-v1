# SYNCHRONISATION DES AGENTS IA – TLS SUPERVISION

Ce document constitue le snapshot technique et stratégique ultime du projet **TLS Supervision**. Il est conçu pour permettre à un agent IA tiers de comprendre, reconstruire et prolonger le développement du système sans aucun contexte préalable.

---

## 1. VISION GLOBALE DU PROJET

### Objectif métier
Centraliser, normaliser et analyser les flux d'événements de sécurité (alarmes, rapports) provenant de multiples télésurveilleurs (Providers) pour offrir une vue consolidée et intelligente de la sécurité d'un parc de sites.

### Cible client
Grands comptes multisites, gestionnaires de sécurité, et centres opérationnels.

### Positionnement
Le système se positionne comme un agrégateur agnostique capable d'ingérer des formats hétérogènes (XLS, PDF via SMTP/Dropbox) et de transformer des logs bruts en **Incidents** et **Alertes** qualifiées.

### Architecture générale
- **Ingestion** : Flux asynchrones basés sur un Watcher/Worker surveillant des répertoires ou des boîtes mails.
- **Backend** : API REST FastAPI (Python) traitant la logique métier et le stockage.
- **Stockage** : PostgreSQL 16 + TimescaleDB (pour les séries temporelles d'événements).
- **Caching/Queue** : Redis pour le verrouillage d'idempotence et la coordination des workers.
- **Frontend** : Application SPA Next.js moderne (MUI/TypeScript).

---

## 2. ARCHITECTURE TECHNIQUE DÉTAILLÉE

### Stack complète
- **Backend** : Python 3.11+, FastAPI, SQLModel (SQLAlchemy 2.0 style), Alembic, Pydantic v2.
- **Frontend** : Next.js 14 (App Router), TypeScript, Material UI (MUI), Recharts, Lucide Icons.
- **Base de données** : PostgreSQL 16 avec extension TimescaleDB.
- **Worker/Tasks** : Custom Async Loop with Redis locking.

### Structure des dossiers (backend + frontend)
```text
supervision-v1/
├── backend/
│   ├── app/
│   │   ├── api/          # Endpoints REST (FastAPI)
│   │   ├── auth/         # JWT Login, RBAC
│   │   ├── core/         # Config & Sécurité
│   │   ├── db/           # Modèles SQL (models.py) & Session
│   │   ├── ingestion/    # Logique Worker, Normalisation, Deduplication
│   │   ├── parsers/      # Adaptateurs PDF & Excel
│   │   └── services/     # Alerting, Incident, Classification (Business Logic)
├── frontend/
│   ├── src/
│   │   ├── app/          # Pages & Routing (Next.js)
│   │   ├── components/   # Composants UI réutilisables
│   │   ├── context/      # AuthContext, AuthProvider
│   │   └── lib/          # API Helpers (api.ts)
└── docker/               # Dockerfiles & scripts init
```

### Schéma Base de Données (tables, relations, index critiques)
- **sites** : Référentiel des sites clients (`code_client` unique, indexé).
- **events** : **Hypertable TimescaleDB**. Partitionnée par temps.
  - *Relations* : `import_id` (FK vers `imports`).
  - *Index critiques* : `ix_events_site_time`, `ix_events_site_severity_time`, `ix_events_site_type_time`.
- **imports** : Journal des ingestions (statuts: `SUCCESS`, `ERROR`, `PROFILE_NOT_CONFIDENT`).
  - *Relations* : `provider_id` (FK vers `monitoring_providers`).
- **monitoring_providers** : Entités télésurveilleurs (ex: SPGO, CORS).
- **smtp_provider_rules** : Mapping `sender_email` -> `provider_id`.
  - *Types* : `EXACT`, `DOMAIN`, `REGEX`.
- **site_connections** : Business Counter (Raccordements actifs).
  - *Index unique* : `(provider_id, code_site)`.
- **incidents** : Agrégation intelligente d'événements (START/STOP).
- **alert_rules** : Moteur de règles complexes (AST JSONB, Sequences, Sliding Windows).

### Gestion multi-tenant (actuel + futur prévu)
- **Actuel** : Champ `tenant_id` dans les modèles d'événements et profils d'ingestion.
- **Futur** : Isolation stricte via schémas PostgreSQL par client ou RLS.

### Provider-centric model (EXACT > DOMAIN > REGEX)
Le `ClassificationService` traite les emails entrants :
1. **EXACT** : Match sur l'adresse email complète.
2. **DOMAIN** : Match sur le `@domaine.com`.
3. **REGEX** : Pattern complexe si nécessaire.
L'attribution au Provider est cruciale pour la facturation et le comptage business.

### Statuts (SUCCESS / ERROR / IGNORED)
- **SUCCESS** : Import fini, événements créés.
- **ERROR** : Crash technique ou parsing impossible.
- **PROFILE_NOT_CONFIDENT** : Profil d'ingestion non reconnu (confiance < seuil).

---

## 3. INFRASTRUCTURE & DEVOPS

### Docker compose complet expliqué
- `db` : PostgreSQL + TimescaleDB (Port 5432).
- `redis` : Verrouillage asynchrone pour éviter les rames d'ingestion concurrentes (Port 6379).
- `backend` : API Uvicorn (Port 8000).
- `worker` : Traitement de fond des fichiers (Dropbox/SMTP).
- `frontend` : App Next.js (Port 3000).

### Volumes DB (persistance)
- `./docker/data/db` : Données PostgreSQL.
- `./dropbox_in` : Fichiers en attente d'ingestion.
- `./archive` : Fichiers traités avec succès (stratégie de stockage à long terme).

### Variables d’environnement
- `POSTGRES_SERVER`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`.
- `NEXT_PUBLIC_API_URL` : URL de l'API (ex: `http://localhost:8000/api/v1`).

### Modes DEV vs PROD
- **DEV** : `docker-compose.yml`. Reloading actif, logs détaillés.
- **PROD** : `docker-compose.prod.yml`. Services hardenisés, certificats SSL, pas de `create_all` DB.

### CI/CD actuel
GitHub Actions :
- `ci.yml` : Checks lint, type-checking, tests unitaires sur chaque PR.
- `cd-staging.yml` : Push automatique sur environnement de staging après succès de la CI.

---

## 4. FRONTEND

### Règles API (fetchWithAuth / fetchPublic)
- **fetchWithAuth** : Injecte le JWT, gère le refresh et redirige vers `/login` sur 401.
- **fetchPublic** : Utilisé uniquement pour le login ou les assets sans authentification.

### Règles repo strictes
- **PAS de `/api/v1` manuel** dans les pages.
- **PAS de `process.env.NEXT_PUBLIC_API_URL`** direct dans les composants.
- Utiliser uniquement les helpers de `src/lib/api.ts`.

### Assets statiques
Les avatars et photos de profil utilisent `API_ORIGIN` (constant centralisée et SSR-safe) car ils sont servis par le serveur web Backend mais hors préfixe `/api/v1`.

---

## 5. ROADMAP ACTUELLE

### Ce qui est terminé (Phase A → v2.5)
- Ingestion XLS/PDF robuste.
- Base de données consolidée (TimescaleDB).
- Business Metrics (Compteurs de raccordements).
- Classification SMTP Providers.
- UI Admin complète.
- Sécurisation des URLs et assets.

### Ce qui est en cours
- Phase 2.C : Validation sur dataset réel massif.

### Ce qui est prévu
- Alerting V3 (Tree Logic AST).
- Incident Reconstruction (Auto-pairing).
- RBAC granulaire.

### Ce qui est différé
- Client Groups (Regroupements d'enseignes).
- Internationalisation complète (FR/EN).

---

## 6. RÈGLES STRUCTURELLES IMPORTANTES

- **Aucun mot-clé hardcodé** : Tout comportement d'import doit être régi par un `IngestionProfile` en DB.
- **Idempotence totale** : Hash SHA256 systématique avant traitement.
- **Persistance IGNORED** : Les fichiers non reconnus sont loggés avec leur payload brut pour permettre une calibration future de profil.
- **Protection DB production** : Migrations Alembic obligatoires (pas de modification manuelle ou via ORM direct en prod).

---

## 7. ZONES COMPLEXES À CONNAÎTRE

### Ingestion PDF parsing
Technique de blocage texte. Sensible à la structure visuelle des rapports providers.

### Normalisation regex
Le `Normalizer` extrait les codes sites par regex. Règle critique : extraction des chiffres uniquement pour `site_code` (ex: `C-69000` -> `69000`).

### Alerting Engine
- **Sliding window** : Corrélation d'événements sur $X$ jours glissants via `sliding_window_days`.
- **AST JSON** : Arbres logiques binaires combinant des conditions simples ou ordonnées.

### Business counter distinct codes_site
Le calcul de facturation repose sur le décompte des codes site uniques vus par provider, stocké dans `site_connections`.

---

## 8. CHECKPOINT DE RECONSTRUCTION

### Étapes pour reconstruire projet from scratch
1. Cloner et configurer `.env`.
2. Lancer la DB/Redis : `docker-compose up -d db redis`.
3. Appliquer les schémas : `cd backend && python -m alembic upgrade head`.
4. Seeder les données essentielles : `python init_settings.py` et `python init_b1_rules.py`.
5. Créer l'admin : `python create_admin.py --email admin@supervision.local`.
6. Lancer le frontend : `cd frontend && npm install && npm run dev`.

### Tests critiques à passer
- `pytest tests/test_parser_v2.py` (Ingestion).
- `pytest tests/test_real_data_logic.py` (Classification).
- `pytest tests/test_step_5_alerting.py` (Moteur de règles).

---
*Document certifié pour synchronisation d'agents.*
