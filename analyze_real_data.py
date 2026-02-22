import csv
import re
import json
from collections import Counter

def analyze_xls(file_paths):
    all_codes = Counter()
    all_messages = Counter()
    
    for path in file_paths:
        print(f"Analyzing {path}...")
        try:
            with open(path, 'r', encoding='latin-1', errors='replace') as f:
                reader = csv.reader(f, delimiter='\t')
                for row in reader:
                    if len(row) < 6: continue
                    
                    # Columns according to ExcelParser:
                    # A: SiteCode, B: Day, C: Date, D: Action/Message, E: Code, F: Details
                    msg = row[3].strip()
                    code = row[4].strip()
                    
                    if code: all_codes[code] += 1
                    if msg: all_messages[msg] += 1
        except Exception as e:
            print(f"Error reading {path}: {e}")

    print("\n--- UNIQUE CODES (Col E) ---")
    for code, count in all_codes.most_common():
        print(f"{code}: {count}")

    print("\n--- MESSAGE PATTERNS (Col D) ---")
    # Group by similarity or just most common
    for msg, count in all_messages.most_common(50):
        print(f"{count}x | {msg}")

if __name__ == "__main__":
    files = [
        "/app/data/archive/duplicates/1769814589_2026-01-28-07-YPSILON.xls",
        "/app/data/archive/duplicates/1769814590_2026-01-30-07-YPSILON.xls"
    ]
    # Adjust paths if needed (relative to root)
    analyze_xls(files)
