import pandas as pd
import os

files = {
    "NORDEDATA_XLS": "/app/data/archive/2026/02/25/1769814589_2026-01-27-07-YPSILON_HISTO.xls",
    "NORDEDATA_XLSX": "/app/data/archive/2026/02/04/2026-01-30-07-YPSILON_HISTO.xlsx",
    "SPGO_XLS": "/app/data/archive/2026/02/22/smoke_spgo.xls"
}

def analyze_file(label, path):
    print(f"\n{'='*60}")
    print(f"ANALYSIS FOR: {label}")
    print(f"PATH: {path}")
    print(f"{'='*60}")
    
    if not os.path.exists(path):
        print("ERROR: File not found.")
        return

    df = None
    method = ""
    
    # Try Excel first
    try:
        engine = "xlrd" if path.endswith(".xls") else "openpyxl"
        df = pd.read_excel(path, sheet_name=0, header=None, engine=engine)
        method = f"EXCEL ({engine})"
    except Exception as e:
        print(f"Excel Load Failed: {str(e)[:100]}")
        # Try TSV/CSV manually line by line to handle varying column counts
        try:
            with open(path, 'r', encoding='latin-1') as f:
                lines = f.readlines()
            data = [line.strip().split('\t') for line in lines]
            # Normalize to max columns with None
            max_cols = max(len(row) for row in data)
            normalized_data = [row + [None]*(max_cols - len(row)) for row in data]
            df = pd.DataFrame(normalized_data)
            method = "TSV (Manual Line Splitting)"
        except Exception as e2:
            print(f"TSV Load Failed: {str(e2)[:100]}")
            return

    if df is not None:
        print(f"LOAD METHOD: {method}")
        print(f"SHAPE: {df.shape}")
        
        # Cleanup routine: remove ="..." formatting if found
        def cleanup(val):
            if isinstance(val, str):
                if val.startswith('="') and val.endswith('"'):
                    return val[2:-1].strip()
            return val
        
        df = df.map(cleanup)
        
        print(f"COLUMNS (Raw Indices): {df.columns.tolist()}")
        print("\nTYPES DETECTED:")
        print(df.dtypes)
        
        print("\nRAW DUMP (FIRST 10 ROWS):")
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        print(df.head(10))
        
        print("\nCOLUMNS INDEXED LOG:")
        for i, col in enumerate(df.columns):
            sample = df[col].dropna().head(3).tolist()
            print(f"Col {i} ({chr(65+i) if i < 26 else i}): Sample {sample}")

for label, path in files.items():
    analyze_file(label, path)
