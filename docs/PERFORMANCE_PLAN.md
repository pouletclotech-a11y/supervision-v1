# Plan de Performance et Stress Test (Phase 3)

Ce document détaille la stratégie pour garantir que TLS-Y Supervision peut supporter 1000 tenants simultanés avec une ingestion continue.

---

## 1. Optimisation Database (PostgreSQL / TimescaleDB)

### A. Indexation Stratégique
Les requêtes les plus fréquentes (dashboard, alerting) doivent être couvertes par des index optimisés.
- **Index Multi-colonnes** :
    ```sql
    CREATE INDEX idx_events_tenant_time ON events (tenant_id, time DESC);
    CREATE INDEX idx_incidents_tenant_status ON incidents (tenant_id, status);
    ```
- **Politique de Maintenance** :
    - Utilisation systématique de `EXPLAIN ANALYZE` pour chaque nouvelle requête complexe.
    - Autovacuum agressif sur les tables à fort volume.

### B. Partitionnement TimescaleDB
- **Chaque tenant** doit bénéficier d'un partitionnement temporel efficace.
- **Compression** : Activer la compression TimescaleDB pour les données de plus de 7 jours.
- **Retention Policy** : Purge automatique des données brutes après 90 jours.

---

## 2. Stress Testing Automatisé (k6)

### A. Scénarios de Test
Utiliser **k6** (JavaScript) pour simuler la charge réelle.
- **S1 : Ingestion Massive** : 1000 requêtes d'ingestion/sec réparties sur 500 tenants.
- **S2 : Consultation Dashboard** : 200 utilisateurs consultant les KPIs en simultané.
- **S3 : Mixte (Worst Case)** : Ingestion forte + Multi-consultation + Déclenchement de règles complexes.

### B. Objectifs de Performance (SLA)
- **Ingestion** : Temps de réponse API < 100ms (P95).
- **Dashboard** : Chargement initial < 2s.
- **Moteur de Règles** : Délai entre l'arrivée d'un événement et l'alerte < 5s.

---

## 3. Protection contre Saturation & Rate Limiting

### A. Limites API
- **Par IP** : Empêcher le brute force ou le déni de service.
- **Par Tenant** : Quota CPU/RAM via limitation du nombre de requêtes par seconde (ex: 10 req/s pour un tenant standard).

### B. Monitoring des Queues (Redis)
- **Indicateur Critique** : `redis_backlog_size`.
- **Alerting** : Envoi immédiat d'une alerte si la queue dépasse 10 000 événements pendant plus de 2 minutes.

---

## Checklist de Validation
- [ ] Scripts k6 intégrés dans `/tests/stress`.
- [ ] Rapport de performance généré après chaque release majeure.
- [ ] Test de montée en charge validé à 1000 tenants simulés.
- [ ] Alertes Redis testées par saturation artificielle.
