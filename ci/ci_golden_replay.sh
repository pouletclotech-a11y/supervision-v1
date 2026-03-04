#!/bin/bash
# CI Golden Replay - Phase 5
# Purpose: Dynamic validation of ingestion pipeline without hardcoded IDs.

set -e

BACKEND_DIR="/app"
GOLDEN_SPGO="/app/data/archive/duplicates/2026-03-02-18-YPSILON_3SPGO.xls"
GOLDEN_CORS="/app/data/archive/duplicates/2026-03-02-19-YPSILON_HISTOCORS.xlsx"

echo "=== PHASE 5 CI GATE: STARTING GOLDEN REPLAY ==="

# 1. Trigger SPGO
echo "Step 1: Processing SPGO..."
PYTHONPATH=. python ci/trigger_ci_ingestion.py "$GOLDEN_SPGO"
PYTHONPATH=. python ci/assert_import_counts.py --filename "YPSILON_3SPGO" --expected 157

# 2. Trigger CORS
echo "Step 2: Processing CORS..."
PYTHONPATH=. python ci/trigger_ci_ingestion.py "$GOLDEN_CORS"
PYTHONPATH=. python ci/assert_import_counts.py --filename "HISTOCORS" --expected 1709

echo "=== PHASE 5 CI GATE: ALL TESTS PASSED ==="
exit 0
