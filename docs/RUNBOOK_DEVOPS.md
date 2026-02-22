# Runbook DevOps & Maintenance

Ce document contient les procédures opérationnelles pour la maintenance de TLS-Y Supervision.

---

## 1. Gestion des Secrets

### A. Isolation des Environnements
Toutes les configurations sensibles doivent résider dans des fichiers `.env` non-commités.
- `.env.staging` : Pour le serveur de test.
- `.env.prod` : Pour la production (accès restreint).

### B. Rotation des Secrets
1. **Identifiants DB** : Changer le mot de passe dans `.env` et redémarrer les services.
2. **Clés JWT** : Rotation trimestrielle recommandée via script de maintenance générant une nouvelle `SECRET_KEY`.
3. **Certificats SSL** : Renouvellement automatique via Traefik (Let's Encrypt).

---

## 2. Déploiement Staging & Prod

### A. Procédure de Mise à Jour (Automatisée via CD)
```bash
docker compose down
docker compose pull
docker compose up -d --remove-orphans
docker image prune -f
```

### B. Pré-déploiement
- Toujours vérifier que les tests passent : `pytest` dans `/backend`.
- Vérifier la validité du schéma DB : `alembic current`.

---

## 3. Backups & Restauration

### A. Sauvegarde Manuelle
```bash
docker exec supervision_db pg_dump -U admin supervision > backup_$(date +%Y%m%d).sql
```

### B. Restauration de Test
```bash
cat backup.sql | docker exec -i supervision_db psql -U admin supervision
```

---

## 4. Observabilité & Uptime
- **Frontend** : [https://supervision.tls](https://supervision.tls)
- **API** : [https://api.supervision.tls](https://api.supervision.tls)
- **Grafana** : [https://grafana.supervision.tls](https://grafana.supervision.tls)
- **Status Page** : [https://status.supervision.tls](https://status.supervision.tls)
- **Monitoring** : Dashboard Grafana accessible via le sous-domaine dédié.
