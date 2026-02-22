# Tenant Isolation Mode (Capacité Stratégique)

Ce document décrit le fonctionnement et l'activation du mode d'isolation dédié pour les clients à haute sensibilité.

---

## 1. Concept de l'Isolation Mode

Le produit TLS-Y Supervision est conçu comme un SaaS multi-tenant classique (données mélangées mais filtrées par `tenant_id`). 
L'"Isolation Mode" permet de basculer un tenant spécifique sur une infrastructure de calcul ou de stockage dédiée, tout en conservant le même code métier.

### Niveaux d'Isolation
- **Niveau 1 : Logique (Défaut)** : RLS (Row Level Security) sur PostgreSQL.
- **Niveau 2 : Namespace dédié** : Isolation via Kubernetes Namespaces ou Docker Networks isolés.
- **Niveau 3 : Instance dédiée** : API et Workers tournant sur des ressources CPU/RAM dédiées pour ce client.

---

## 2. Implémentation Technique

### A. Flag de Configuration
Une nouvelle colonne dans la table `tenants` (ou table `settings`) :
- `dedicated_instance` (boolean)
- `namespace_target` (string)

### B. Orchestration Infra
- **Routing** : Le reverse proxy (Traefik/Nginx) utilise le Header de requête ou le sous-domaine pour router vers l'instance dédiée si le flag est actif.
- **Workers** : Le worker de ce client ne traite que les messages de sa queue Redis dédiée (`queue_tenant_X`).

---

## 3. Plan d'Activation pour un Client Sensible

1. **Configuration** : Créer le tenant avec `dedicated_instance = true`.
2. **Déploiement** : Lancer un set de conteneurs (API + Worker) avec des variables d'environnement pointant vers le même `tenant_id` mais des ressources isolées.
3. **DNS/SSL** : Affecter un sous-domaine spécifique (ex: `client-special.supervision.tls-y.com`).
4. **Validation** : Vérifier que les logs et transactions CPU de ce client ne sont pas visibles/partagés sur les noeuds communs.

---

## Checklist Activation Client
- [ ] Nom de domaine dédié configuré.
- [ ] Isolation réseau validée (Docker Network/K8s).
- [ ] Queue Redis spécifique provisionnée.
- [ ] Rapport d'intégrité de l'isolation fourni au client.
