# Developer & Contributing Guide

## Philosophy & Golden Rules

> [!IMPORTANT]
> **1. Documentation First**
> No code is written before the documentation (Architecture, Specs) is updated and approved.
>
> **2. No UI Regressions**
> The V1 UI (Dark Theme, Layout, Fonts) is validated. Any technical change must preserve the visual identity exactly.
>
> **3. Respect the V1**
> The current state is "Stable". Do not refactor core components without a specific B1/V2 requirement.

## 1. Local Development Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (recommended for local Intellisense)

### Setup
1. Clone the repository.
2. Create virtualenv (optional):
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   ```
3. Start Infrastructure:
   ```bash
   docker compose up -d db redis
   ```

## 2. Project Structure
- `backend/app/ingestion`: Core logic (Watcher, Worker, Normalizer, Deduplication).
- `backend/app/parsers`: Protocol-specific parsers.
- `docker/init`: SQL Migration scripts.
- `docs/`: **The Source of Truth**.

## 3. Testing
**Current Status**: Manual Testing.

- **Ingestion**: Drop files into `dropbox_in/`.
- **Verification**: Check logs (`docker logs supervision_worker`) and UI (`/admin/data-validation`).
- **Unit Tests**: Planned for V2.

## 4. Alerting V3
Pour ajouter de nouvelles capacités de détection :

### Ajouter une Condition Réutilisable
1. Modifiez `backend/migrations/12_rule_conditions.sql` (ou créez une nouvelle migration).
2. Ajoutez un `code` unique et un `payload` JSON (matching keyword/category).
3. Exécutez la migration.

### Ajouter une Règle Complexe (AST)
1. Utilisez l'éditeur JSON dans l'UI des Alertes.
2. Structurez votre arbre avec des opérateurs `AND`/`OR` et des références `cond:CODE`.

### Test & Validation
Utilisez `backend/migrations/16_seed_test_rules.sql` comme base pour vos tests locaux.
Vérifiez l'évaluation via le bouton **Dry Run** dans l'UI.
