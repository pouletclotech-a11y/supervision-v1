import sys
import os
from datetime import datetime

# Add /app to sys.path
sys.path.append('/app')

from app.parsers.pdf_parser import PdfParser

def test_parser():
    parser = PdfParser()
    path = '/app/data/archive/2026/02/06/2026-02-06-06-YPSILON_HISTO.pdf'
    
    print(f"Testing with: {path}")
    events = parser.parse(path)
    print(f"Extracted {len(events)} events")
    
    for e in events[:20]:
        print(f"{e.timestamp} | {e.site_code} | {e.client_name} | {e.raw_message}")

if __name__ == "__main__":
    test_parser()
