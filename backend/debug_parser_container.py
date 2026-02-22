
import csv
import re
import os

# Create dummy file matching user description
file_content = """C-69000	BLEIN VIRGINIE	00032009
Lun	27/01/2026 09:00:00	OUVERTURE	CONTROLE	Utilisateur
Tu	27/01/2026 10:00:00	FERMETURE		
"""

DUMMY_PATH = "dummy_test.xls"
with open(DUMMY_PATH, "w", encoding="latin-1") as f:
    f.write(file_content)

def clean_field(val: str) -> str:
    if not val: return ""
    match = re.match(r'^="?(.*?)"?$', val.strip())
    if match:
        return match.group(1).strip()
    return val.strip()

print(f"Testing Parser on:\n{file_content}")
print("-" * 20)

try:
    with open(DUMMY_PATH, 'r', encoding='latin-1') as f:
        reader = csv.reader(f, delimiter='\t')
        row_idx = 0
        current_site_code = None
        
        for row in reader:
            row_idx += 1
            clean_row = [clean_field(c) for c in row if c.strip()]
            if not clean_row: continue
            
            print(f"Row {row_idx}: {clean_row}")
            first_col = clean_row[0]
            
            # Regex Test
            match_c = re.match(r'^C-\d+$', first_col)
            match_d = re.match(r'^\d{8}$', first_col)
            
            if match_c:
                print(f"  -> MATCH C-CODE: {match_c.group(0)}")
                current_site_code = re.sub(r'\D', '', first_col)
            elif match_d:
                 print(f"  -> MATCH DIGIT: {match_d.group(0)}")
                 current_site_code = first_col
            else:
                 print(f"  -> NO HEADER MATCH. Current Context: {current_site_code}")

except Exception as e:
    print(f"Error: {e}")
