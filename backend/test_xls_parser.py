import sys
import os
import json
from datetime import datetime

# Add /app to sys.path
sys.path.append('/app')

from app.parsers.excel_parser import ExcelParser

def test_parser():
    parser = ExcelParser()
    # Find any .xls file that is NOT HISTO
    import glob
    files = glob.glob('/app/data/archive/**/*.xls', recursive=True)
    files = [f for f in files if 'HISTO' not in f]
    if not files:
        print("No .xls files found")
        return
    path = files[0]
    
    print(f"Testing with: {path}")
    events = parser.parse(path)
    print(f"Extracted {len(events)} events")
    
    for e in events[:20]:
        print(f"{e.timestamp} | {e.site_code} | {e.client_name} | {e.raw_message}")

if __name__ == "__main__":
    test_parser()
