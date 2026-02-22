## 1. Mise à zéro de l'environnement (Clean State)

Avant toute restauration, il est **impératif** de supprimer les conteneurs et les volumes persistants pour repartir d'une base vierge.

```bash
docker compose down -v
docker compose up -d db
```

---

## 2. Restauration de la Base de Données

### Étapes
1. Démarrer uniquement le service de base de données :
   ```bash
   docker compose up -d db
   ```
2. Attendre que Postgres soit prêt (vériifer avec `docker compose logs -f db`).
3. Injecter le dump SQL :
   ```bash
   cat backups/latest_dump.sql | docker exec -i supervision_db psql -U admin supervision
   ```

---

## 3. Restauration des Fichiers

```bash
# Restaurer le dossier d'ingestion
cp -r backups/files_latest/dropbox_in/* ./dropbox_in/

# Restaurer les archives
cp -r backups/files_latest/archive/* ./archive/
```

---

## 4. Vérification post-restauration

- Lancer l'application complète : `docker compose up -d`.
- Vérifier l'accès au dashboard : `http://localhost:3000`.
- Vérifier la présence des derniers imports dans l'historique admin.
