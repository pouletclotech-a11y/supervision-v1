import sys
import os
import json
from datetime import datetime

# Add /app to sys.path
sys.path.append('/app')

from app.parsers.excel_parser import ExcelParser

def test_parser():
    parser = ExcelParser()
    path = '/app/data/archive/2026/02/05/2026-02-05-18-YPSILON_HISTO.xlsx'
    if not os.path.exists(path):
        # Find any other HISTO.xlsx
        import glob
        files = glob.glob('/app/data/archive/**/*.xlsx', recursive=True)
        files = [f for f in files if 'HISTO' in f]
        if not files:
            print("No HISTO files found")
            return
        path = files[0]
    
    print(f"Testing with: {path}")
    events = parser.parse(path)
    print(f"Extracted {len(events)} events")
    
    for e in events[:20]:
        print(f"{e.timestamp} | {e.site_code} | {e.raw_message}")

if __name__ == "__main__":
    test_parser()
