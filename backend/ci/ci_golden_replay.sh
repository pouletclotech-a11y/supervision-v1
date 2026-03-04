#!/bin/bash
set -e

BACKEND_DIR="/app"
GOLDEN_SPGO="/app/data/archive/duplicates/2026-03-02-18-YPSILON_3SPGO.xls"
GOLDEN_CORS="/app/data/archive/duplicates/2026-03-02-19-YPSILON_HISTOCORS.xlsx"

echo "=== PHASE 5 CI GATE: STARTING GOLDEN REPLAY ==="

echo "Step 1: Processing SPGO..." # Step 1: Processing SPGO... (157 security events + 162 operator notes = 319)
PYTHONPATH=.:/home/appuser/.local/lib/python3.11/site-packages python ci/trigger_ci_ingestion.py "$GOLDEN_SPGO"
PYTHONPATH=.:/home/appuser/.local/lib/python3.11/site-packages python ci/assert_import_counts.py --filename "YPSILON_3SPGO" --expected 319

# Step 2: Processing CORS... (1709 security events + 123 operator actions = 1832)
PYTHONPATH=.:/home/appuser/.local/lib/python3.11/site-packages python ci/trigger_ci_ingestion.py "$GOLDEN_CORS"
PYTHONPATH=.:/home/appuser/.local/lib/python3.11/site-packages python ci/assert_import_counts.py --filename "HISTOCORS" --expected 1832

echo "=== PHASE 5 CI GATE: ALL TESTS PASSED ==="
exit 0
