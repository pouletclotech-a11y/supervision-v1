import pytest
import os
import json
from pathlib import Path
from app.parsers.excel_parser import ExcelParser
from app.parsers.pdf_parser import PdfParser
from datetime import datetime

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "ingestion"
GOLD_MASTER_DIR = FIXTURE_DIR / "gold_master"

def serialize_event(event):
    """Converts a NormalizedEvent to a deterministic dict for comparison."""
    data = event.model_dump()
    # Handle datetime serialization
    if isinstance(data.get('timestamp'), datetime):
        data['timestamp'] = data['timestamp'].isoformat()
    # Remove fields that are non-deterministic or environment-dependent
    data.pop('id', None)
    data.pop('source_file', None) # Path might change in CI
    data.pop('row_index', None) 
    # Handle nested metadata if needed
    return data

def get_gold_master_path(fixture_name):
    return GOLD_MASTER_DIR / f"{fixture_name}.json"

@pytest.mark.parametrize("fixture_file, parser_cls", [
    ("sample_ypsilon.xls", ExcelParser),
    # ("sample_ypsilon_histo.xlsx", ExcelParser), # Add when ready
    # ("sample_ypsilon.pdf", PdfParser), # Add when ready
])
def test_ingestion_baseline(fixture_file, parser_cls):
    fixture_path = FIXTURE_DIR / fixture_file
    if not fixture_path.exists():
        pytest.skip(f"Fixture {fixture_file} not found")

    # 1. Process with current parser
    parser = parser_cls()
    events = parser.parse(str(fixture_path))
    
    current_results = [serialize_event(e) for e in events]
    
    # Sort results for deterministic comparison if needed (e.g. by timestamp and site_code)
    current_results.sort(key=lambda x: (x['timestamp'], x['site_code'], x['event_type']))

    gold_master_path = get_gold_master_path(fixture_file)

    # 2. Update or Verify
    # If the environment variable GENERATE_GOLD_MASTER is set, we overwrite the reference
    if os.environ.get("GENERATE_GOLD_MASTER") == "1":
        GOLD_MASTER_DIR.mkdir(parents=True, exist_ok=True)
        with open(gold_master_path, "w", encoding="utf-8") as f:
            json.dump(current_results, f, indent=2, ensure_ascii=False)
        pytest.skip(f"Gold Master generated for {fixture_file}")

    # Otherwise, we compare
    assert gold_master_path.exists(), f"Gold Master missing for {fixture_file}. Run with GENERATE_GOLD_MASTER=1 to create it."
    
    with open(gold_master_path, "r", encoding="utf-8") as f:
        reference_results = json.load(f)

    # 3. Assertions
    assert len(current_results) == len(reference_results), f"Event count mismatch for {fixture_file}"
    
    for i, (current, reference) in enumerate(zip(current_results, reference_results)):
        assert current == reference, f"Divergence detected at event index {i} in {fixture_file}"

if __name__ == "__main__":
    # Convenience for generating masters manually
    os.environ["GENERATE_GOLD_MASTER"] = "1"
    # This is a bit hacky but helps for one-off generation
    import sys
    pytest.main([__file__])
