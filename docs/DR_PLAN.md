# Plan de Disaster Recovery (Phase 5)

Ce document décrit les procédures et politiques pour garantir la disponibilité et la récupération des données de TLS-Y Supervision après une panne majeure.

---

## 1. Stratégie de Sauvegarde

### A. Base de Données (Postgres/Timescale)
- **Fréquence** : 
    - Full Dump quotidien (S3).
    - Logs de transaction périodiques (PITR) pour une récupération à la minute près.
- **Rétention** :
    - 30 jours de dumps quotidiens.
    - 12 mois de dumps mensuels.

### B. Fichiers & Sources (Object Storage)
- Synchronisation multi-régionale (Cross-Region Replication) pour les fichiers `raw_data` et archives.

---

## 2. Procédures de DR Drill (Trimestriel)

### A. Restauration Complète
Simulation d'une perte totale d'infrastructure cloud.
- **Action** : Déployer l'infrastructure complète via Terraform/Docker Compose dans une nouvelle zone géographique.
- **Action** : Restaurer le dernier dump valide et vérifier l'intégrité des données.

### B. Simulation de Panne d'Instance
- Couper brutalement un worker ou une instance API.
- Vérifier que l'orchestrateur (Docker Swarm/K8s) redémarre le composant sans perte de données.

### C. Validation RPO / RTO
- **RPO (Recovery Point Objective)** : Cible < 15 minutes.
- **RTO (Recovery Time Objective)** : Cible < 1 heure pour une reprise complète.

---

## 3. Rotation des Secrets & Sécurité

### A. Politique de Rotation
- **JWT Keys** : Rotation trimestrielle.
- **DB Credentials** : Rotation automatisée tous les 6 mois via Vault.
- **Certificats SSL** : Renouvellement automatique (Let's Encrypt).

### B. Audit Trail & Immuabilité
- Les logs d'audit sont envoyés vers un stockage "Append-Only".
- Réplication des logs vers un bucket S3 distinct avec verrouillage logiciel (WORM - Write Once Read Many).

---

## Checklist de Restauration Testée
- [ ] Procédure SSH de secours documentée dans le Runbook.
- [ ] Script de restauration automatisé `/scripts/restore_db.sh` validé.
- [ ] Dernier rapport de DR Drill : **[Lien vers rapport interne]**.
- [ ] RPO/RTO mesurés lors du dernier test.
