# Release Note — Phase D+E (Supervision-V1)

**Date** : 2026-02-21 · **Version** : V3.2 · **Statut** : ✅ GO RELEASE

---

## Résumé

Clôture de la Phase D (Robustesse IMAP) et de la Phase E (Observabilité minimale).
Aucune migration DB. Aucun changement d'interface API. Aucun invariant modifié.

---

## Changements — Phase D Close-out

### `backend/app/ingestion/adapters/email.py`

| Changement | Détail |
|---|---|
| **Per-item error isolation** | Chaque email dans la boucle IMAP est dans son propre `try/except` avec `exc_info=True`. Un glitch sur UID X ne coupe plus le poll. Bookmark n'avance pas → retry naturel au cycle suivant. |
| **IMAP COPY fail-soft** | Si `uid('COPY', ...)` retourne `NO`/`BAD` : warning loggué + early return. `STORE` jamais appelé. Item reste en INBOX. |
| **IMAP STORE warning** | Si `uid('STORE', ...)` échoue après COPY OK : warning loggué (item copié, pas supprimé). |
| **poll_run_id propagé** | Reçu en paramètre depuis `worker.py`, stocké dans `item.metadata` pour corrélation des logs. |

### `backend/app/ingestion/worker.py`

| Changement | Détail |
|---|---|
| **poll_run_id UUID** | UUID 8-chars généré par cycle, propagé à tous les logs et aux `process_ingestion_item`. |
| **[METRIC] logs** | Logs structurés sur tous les chemins : `poll_cycle_start/done/error`, `item_picked`, `import_success/duplicate/unmatched/error/fatal`. |
| **Timing** | `duration_ms` dans `poll_cycle_done`. |
| **poll_cycle_error** | Exception globale dans la boucle → log avec `exc_info=True` + `run_id`. |

---

## Nouveaux Tests

| Fichier | Test | Vérifie |
|---|---|---|
| `test_adapter_email.py` | `test_email_adapter_per_item_isolation` | UID1 crash → UID2 passe, bookmark 901 n'avance pas |
| `test_adapter_email.py` | `test_email_adapter_imap_copy_fails_soft` | COPY "NO" → pas de STORE, pas de suppression |
| `test_idempotence.py` | `test_sha256_duplicate_calls_ack_duplicate` | Restart worker + même SHA256 → `ack_duplicate` uniquement |
| `test_idempotence.py` | `test_sha256_not_in_db_proceeds_normally` | SHA256 absent → pipeline continue normalement |

**Résultat final : 14/14 PASSED** (Python 3.11.14 / pytest 9.0.2)

---

## Invariants — Non modifiés

- ✅ Idempotence SHA256 (`compute_sha256` + `get_import_by_hash`)
- ✅ `import_id` FK sur events
- ✅ `file_hash` conservé
- ✅ Lifecycle Dropbox : SUCCESS → `dropbox_done/YYYY/MM`, ERROR → `dropbox_error`
- ✅ Aucun mot-clé en dur
- ✅ **Aucune migration DB**
- ✅ Aucune modification de schéma DB

---

## GO / NO-GO Final

| Critère | Statut |
|---|---|
| 14/14 tests unitaires | ✅ |
| Smoke test Dropbox (idempotence prod) | ✅ DUPLICATE correct (ExistingImportID=687) |
| Logs METRIC visibles en prod | ✅ |
| Aucune régression DB | ✅ |
| Docs cohérentes (PROJECT_EFFORT, RELEASE_VALIDATION) | ✅ |

**→ GO ✅**
