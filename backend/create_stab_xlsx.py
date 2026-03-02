import pandas as pd
import os

xlsx_path = "/app/data/ingress/YPSILON_STAB_FINAL.xlsx"
meta_path = xlsx_path + ".meta.json"

data = [
    ['TITRE EXPORT', '', '', '', '', ''],
    [69000, 'CLIENT ALPHA', '27/01/2026 10:00:00', 'APPARITION', 'CODE1', 'DETAILS 1'],
    ['', 'LUN', '10:05:00', 'DISPARITION', 'CODE1', 'DETAILS 1'], 
    [75001, 'CLIENT BETA', '28/01/2026 11:00:00', 'MISE EN SERVICE', 'CODE2', 'DETAILS 2'],
]

try:
    df = pd.DataFrame(data)
    df.to_excel(xlsx_path, index=False, header=False, engine='openpyxl')
    print(f"File saved to {xlsx_path}")
    if os.path.exists(xlsx_path):
        print(f"Verification: {xlsx_path} exists. Size: {os.path.getsize(xlsx_path)}")
    else:
        print(f"Verification FAILED: {xlsx_path} DOES NOT EXIST after saving.")
except Exception as e:
    print(f"CRITICAL ERROR during to_excel: {e}")

try:
    with open(meta_path, 'w') as f:
        f.write('{"sender_email": "test@supervision.local"}')
    print(f"Meta file saved to {meta_path}")
except Exception as e:
    print(f"ERROR during meta file creation: {e}")
