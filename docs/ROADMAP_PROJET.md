# Roadmap Globale — TLS Supervision

Ce document recense l'ensemble des fonctionnalités et évolutions demandées, planifiées ou réalisées depuis le début du projet.

## 🟢 Phase 1 : Cœur du Système (Réalisé)
- [x] Moteur d'ingestion multi-fournisseurs (CORS, SPGO, YPSILON).
- [x] Parsing XLS, XLSX et PDF.
- [x] Déduplication temporelle intelligente.
- [x] Profiling dynamique et normalisation des événements.
- [x] Dashboard de santé de l'ingestion (Reçus vs Attendus).


## 🟡 Phase 2 : Moteur de Règles & Alertes (En cours)
- [x] Rule Builder : Modes Simple, Séquence et Logique (AST).
- [x] Audit complet du moteur (Mapping des champs, Fenêtres temporelles).
- [x] Documentation utilisateur des alertes.
- [ ] **Évolution A** : Ergonomie des unités de temps (sec/min/heures).
- [ ] **Évolution B** : Alertes Persistantes (Ouverture / Fermeture via Disparition).
- [ ] **Évolution C** : Règles Composées (A ET (B OU C)).
- [ ] **Évolution D** : Configuration SMTP par prestataire.

## 🔵 Phase 3 : Catalogue & Annuaire (Terminé)
- [x] **P3.1** : Extraction et génération manuelle de l'annuaire (Markdown/CSV).
- [x] **P3.2** : Groupement par code unique (multi-prestataires par ligne).
- [x] **P3.3** : Automatisation de la mise à jour (chaque jour via le worker).
- [x] **P3.4** : Module UI Interactif ("Annuaire des codes").
- [ ] **P3.5** : Enrichissement sémantique (Intentions métier).

## ⚪ Évolutions Futures
- [ ] Rapports automatisés périodiques.
- [ ] Exportation PDF des rapports d'incidents.
- [ ] Interface de gestion des comptes utilisateurs (RBAC avancé).

---
*Dernière mise à jour : 20/03/2026*
