import os
import sys
from datetime import datetime

# Add the app directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.parsers.excel_parser import ExcelParser

def test_parser_v2():
    # Mock TSV data based on user spec
    # Col A: site_code, Col B: day, Col C: date/time, Col D: action, Col E: empty, Col F: details
    mock_content = (
        '="C-69001"\t="LUN"\t="02/02/2026 08:00:00"\t="APPARITION"\t=""\t="Intrusion Zone 1"\n'
        '=""\t=""\t="08:05:22"\t="DISPARITION"\t=""\t="Intrusion Zone 1"\n'
        '=""\t=""\t="08:10:00"\t="APPARITION"\t=""\t="Porte Hall"\n'
        '="C-69002"\t="MAR"\t="03/02/2026 22:00:00"\t="APPARITION"\t=""\t="Vandalisme"\n'
        '=""\t=""\t="22:15:00"\t="DISPARITION"\t=""\t="Vandalisme"\n'
    )
    
    test_file = "test_ingestion_v2.xls"
    with open(test_file, "w", encoding="latin-1") as f:
        f.write(mock_content)
        
    try:
        parser = ExcelParser()
        events = parser.parse(test_file)
        
        print(f"Parsed {len(events)} events.")
        
        # Validation
        for i, e in enumerate(events):
            print(f"Event {i}: {e.timestamp} | Site: {e.site_code} | Day: {e.weekday_label} | Msg: {e.raw_message}")
            
            # Check Site Inheritance
            if i <= 2:
                assert e.site_code == "69001"
            else:
                assert e.site_code == "69002"
                
            # Check Day Inheritance
            if i <= 2:
                assert e.weekday_label == "LUN"
            else:
                assert e.weekday_label == "MAR"
                
            # Check Date Inheritance
            if i == 0:
                assert e.timestamp == datetime(2026, 2, 2, 8, 0, 0)
            elif i == 1:
                assert e.timestamp == datetime(2026, 2, 2, 8, 5, 22)
            elif i == 2:
                assert e.timestamp == datetime(2026, 2, 2, 8, 10, 0)
            elif i == 3:
                assert e.timestamp == datetime(2026, 2, 3, 22, 0, 0)
                
            # Check raw_data
            assert e.raw_data is not None
            
        print("✅ ALL TESTS PASSED!")
        
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

if __name__ == "__main__":
    test_parser_v2()
