import sys
from app.parsers.excel_parser import ExcelParser

parser = ExcelParser()
# Select the same histo file
file_path = "/app/data/archive/2026/02/06/2026-02-05-18-YPSILON_HISTO.xlsx"
events = parser.parse(file_path)

print(f"Total events: {len(events)}")
with_code = [e for e in events if e.raw_code]
print(f"Events with code: {len(with_code)}")

for e in with_code[:10]:
    print(f"Code: {e.raw_code} | Msg: {e.raw_message}")
