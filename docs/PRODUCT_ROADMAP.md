# Roadmap Produit : TLS-Y Supervision (SaaS Industrialisé)

Ce document définit la stratégie d'industrialisation du produit pour passer d'un outil interne à une plateforme SaaS multi-clients (cible 100–1000 tenants).

---

## Phase 0 — Fondations & Gouvernance DevOps
**Objectif** : Industrialiser le cycle de vie du code, sécuriser les environnements et établir la gouvernance technique.

- **Isolation Scellée** : Variables d’environnements et secrets (`.env.local`, `.env.staging`, `.env.prod`). Aucun secret en dur.
- **Gouvernance DB** : Migrations versionnées (Alembic) + Procédures de rollback automatisées.
- **CI/CD Robuste** : 
    - CI : Tests auto + build Docker Hardened + Security linting.
    - CD Staging : Déploiement avec `prune` et `remove-orphans`.
- **Registre Privé** : Publication d’images officielles sur GHCR.io (versions hashées).
- **SLA Baseline** : Mise en place des sondes de disponibilité de base.

---

## Phase 1 — Staging Public + Observabilité
**Objectif** : Rendre le service accessible et monitoré en situation réelle.

- **SSL/Domaine** : Let's Encrypt / Cloudflare WAF.
- **Stack Observabilité** : Centralisation des logs (Loki), métriques (Prometheus) et tableaux de bord (Grafana).
- **Gestion des Erreurs** : Intégration Sentry (Back/Front).
- **Stratégie Backups** : Automatisation des dumps Postgres + Synchronisation S3 (Object Storage).
- **Status Page** : Portail public de suivi de la disponibilité (SLA) et uptime.
- **Gouvernance RGPD** : Définition contractuelle du cycle de vie des données et politique de rétention.

---

## Phase 2 — Produit V1 Multi-Tenant
**Objectif** : Ouverture aux clients externes avec isolation stricte.

- **Isolation Tenant** : `tenant_id` systématique + Row Level Security (RLS) sur PostgreSQL.
- **Gestion IAM** : Authentification OIDC/JWT (Keycloak ou Auth0).
- **Portail Client V1** : Interface simplifiée pour les clients finaux (KPIs, Incidents).
- **RBAC Avancé** : Rôles granulaires (Admin interne, Admin client, Opérateur).
- **Isolation Logique** : Préparation des hooks pour le "Tenant Isolation Mode".
- **Feature Flags** : Activation/Désactivation de fonctionnalités par tenant (Tiering).

---

## Phase 3 — Scale & Performance (Renforcement)
**Objectif** : Support de la croissance massive (100 -> 1000 clients).

- **Architecture Distribuée** : Séparation physique des noeuds (Edge, API, Workers dédiés).
- **DB Optimization** : 
    - Index multi-colonnes (`tenant_id`, `event_timestamp`).
    - Partitionnement temporel agressif (TimescaleDB).
- **Scale & Protection** : 
    - Rate Limiting par tenant et par IP.
    - Isolation CPU/RAM des workers.
    - Monitoring des queues Redis (Alerting seuil de backlog).
- **Stress Testing** : Validation via k6 simulant jusqu'à 1000 tenants.

---

## Phase 4 — Entreprise & Audit
**Objectif** : Conformité, intégration SI et traçabilité.

- **SSO Entreprise** : Support SAML / Azure AD.
- **Audit Trail** : Journalisation immuable "Qui fait quoi, quand, sur quel tenant".
- **SaaS Quotas** : Limites d'événements/mois, stockage et volume d'export par tenant.

---

## Phase 5 — HA & Disaster Recovery (Renforcement)
**Objectif** : Résilience et continuité de service garanties.

- **HA (Clustering)** : Redondance complète de tous les composants critiques.
- **PITR** : Point-In-Time Recovery pour la base de données.
- **Audit Trail HA** : Réplication et garantie d'intégrité immuable (append-only).
- **Gestion des Secrets** : Politique de rotation automatique (JWT, DB, SSL).
- **Versioning des Règles** : Historisation, Rollback instantané et Sandbox de simulation.
- **DR Drill** : Simulation trimestrielle de perte totale avec rapport RPO/RTO.

---

## Phase 6 — Industrialisation Commerciale
**Objectif** : Monétisation et automatisation du packaging.

- **Billing SaaS** : Intégration Stripe (usage-based billing).
- **Expert Rules Builder** : Editeur graphique de règles AST JSON avec validation.
- **RGPD Automatisé** : Outils de droit à l'oubli et suppression sécurisée.
- **Reporting Business** : Moteur de templates Word/PDF paramétrables par client.

---

## Stack Recommandée
- **Edge/Proxy** : Traefik / Nginx.
- **Secrets** : Vault / Cloud Secrets Manager.
- **SLA/Status** : Cachet / Upptime.
- **Storage** : S3 Compatible (Wasabi/Scaleway).
