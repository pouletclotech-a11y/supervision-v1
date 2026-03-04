# Execution Roadmap — Phase 4

## 1. Data Layer
- [ ] Créer `backend/migration_v13.sql` (idempotent).
- [ ] Appliquer la migration via `psql`.
- [ ] Mettre à jour `backend/app/db/models.py`.

## 2. Parsers
- [ ] Mettre à jour `tsv_parser.py` (SPGO : skip details + metrics).
- [ ] Mettre à jour `excel_parser.py` (CORS : mapping + strip leading zeros).
- [ ] Mettre à jour `pdf_parser.py` (extraction pour matching).

## 3. Business Logic
- [ ] Créer `pdf_match_service.py` (Multi-strategy key builder).
- [ ] Mettre à jour `worker.py` (Orchestration quality_report + pdf_match).

## 4. API & Verification
- [ ] Mettre à jour `ingestion.py` (Endpoints + Replay logic).
- [ ] Lancer Replay 48h sur Golden Files.
- [ ] Valider via SQL Proofs.
