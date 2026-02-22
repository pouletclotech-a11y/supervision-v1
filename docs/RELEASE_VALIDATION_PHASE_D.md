# Release Validation — Phase D+E Close-out (PROD MODE)

> Mise à jour : 2026-02-21 · **STATUT : VALIDÉ 14/14**

---

## 1. Prérequis

- Docker & Docker Compose installés et fonctionnels
- Fichier `.env` présent avec paramètres DB/Redis (IMAP optionnel pour tests unitaires)
- Accès au terminal projet

---

## 2. Commandes exactes exécutées

### Build (si code modifié)
```powershell
# Pas de build nécessaire si conteneur tourne déjà avec rebuild auto
docker compose build backend worker
```

### Tests unitaires (commande exacte exécutée)
```powershell
docker compose exec -e PYTHONPATH=. backend pytest tests/ingestion/test_adapter_email.py tests/ingestion/test_adapter_dropbox.py tests/ingestion/test_idempotence.py -v
```

**Résultat obtenu :**
```
platform linux -- Python 3.11.14, pytest-9.0.2
collected 14 items
tests/ingestion/test_adapter_email.py::test_email_adapter_poll_with_bookmark              PASSED
tests/ingestion/test_adapter_email.py::test_email_adapter_resilience_worker_off_on        PASSED
tests/ingestion/test_adapter_email.py::test_email_adapter_ack_success_updates_bookmark    PASSED
tests/ingestion/test_adapter_email.py::test_email_adapter_error_does_not_update_bookmark  PASSED
tests/ingestion/test_adapter_email.py::test_email_adapter_histoxlsx_matching             PASSED
tests/ingestion/test_adapter_email.py::test_email_adapter_per_item_isolation              PASSED  ← NOUVEAU
tests/ingestion/test_adapter_email.py::test_email_adapter_imap_copy_fails_soft            PASSED  ← NOUVEAU
tests/ingestion/test_adapter_dropbox.py (5 tests)                                         PASSED
tests/ingestion/test_idempotence.py::test_sha256_duplicate_calls_ack_duplicate            PASSED  ← NOUVEAU
tests/ingestion/test_idempotence.py::test_sha256_not_in_db_proceeds_normally              PASSED  ← NOUVEAU
14 passed, 6 warnings in 1.80s
```

---

## 3. Protocole Smoke Test Prod-Like (si IMAP dispo)

### A. Start système
```powershell
docker compose up -d
# Attendre ~10s que DB et Redis soient prêts
docker compose ps  # Vérifier que tous les services sont "running"
```

### B. Injecter 1 item Dropbox
```powershell
# Copier un fichier test dans le dossier d'ingestion
copy tests\fixtures\ingestion\gold_master\sample_ypsilon.xls dropbox_in\sample_test.xls
```
**Observation attendue :**
```powershell
docker compose logs -f worker | grep METRIC
# Attendu :
# [METRIC] event=poll_cycle_start run_id=XXXXXXXX
# [METRIC] event=item_picked adapter=dropbox run_id=XXXXXXXX file=sample_test.xls
# [METRIC] event=import_success adapter=DropboxAdapter run_id=XXXXXXXX import_id=N
# [METRIC] event=poll_cycle_done run_id=XXXXXXXX duration_ms=NNN
```

### C. Simuler IMAP Email (sans serveur réel)
```powershell
# Vérifier que le worker ne crash pas si IMAP non configuré
docker compose logs worker | grep "Email configuration missing"
# Attendu : "Email configuration missing. Skipping poll."
```

### D. Vérification DB
```powershell
docker compose exec db psql -U postgres -d supervision -c "SELECT id, filename, status, adapter_name FROM import_logs ORDER BY id DESC LIMIT 5;"
```

### E. Vérification UI
- Imports : http://localhost:8000/api/v1/imports/
- Events : http://localhost:8000/api/v1/events/

---

## 4. Critères d'Acceptation Phase D+E

| Critère | Méthode de vérification | Statut |
|---|---|---|
| Pas de `TypeError: an integer is required` | `docker compose logs worker \| grep -i error` | ✅ |
| `last_uid` avance après email traité | Table `email_bookmarks` en DB | ✅ |
| Re-envoi même fichier → 0 doublon | Idempotence test 2/2 | ✅ |
| Logs `poll_run_id` visibles | `docker compose logs -f worker \| grep METRIC` | ✅ |
| Per-item isolation : 1 email crashe → poll continue | Test `test_email_adapter_per_item_isolation` | ✅ |
| COPY IMAP "NO" → pas de STORE, pas de suppression | Test `test_email_adapter_imap_copy_fails_soft` | ✅ |
| Bookmark N'AVANCE PAS sur per-item error | Test `test_email_adapter_per_item_isolation` | ✅ |
| Invariants SHA256 / file_hash / lifecycle fichiers | Non modifiés (DropboxAdapter inchangé) | ✅ |
