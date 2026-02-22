# Supervision Tool V1

## Overview
Automated ingestion system for security logs (PDF, Excel).
Provides Normalization, Deduplication (Burst Collapse), and Persistence to TimescaleDB.

## Quick Links
- [Architecture Overview](docs/ARCHITECTURE.md)
- [Ingestion Specs (Normalization rules)](docs/INGESTION_SPECS.md)
- [Operation Guide (Runbook)](docs/RUNBOOK_DEVOPS.md)
- [Developer Guide](docs/DEV_CONTRIBUTING.md)
- [Project Effort & Roadmap](docs/PROJECT_EFFORT.md)
- [Release Validation Phase D+E](docs/RELEASE_VALIDATION_PHASE_D.md)

## Quickstart

### 1. Start System
```bash
docker compose up --build -d
```

### 2. Ingest Files
Drop `.pdf` or `.xls` files into the `dropbox_in/` folder.

### 3. Check Status
- **Imports**: http://localhost:8000/api/v1/imports/
- **Events**: http://localhost:8000/api/v1/events/
- **Debug**: http://localhost:8000/api/v1/debug/sample

## License
Proprietary.
