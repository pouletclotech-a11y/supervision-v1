import asyncio
from pathlib import Path
import sys
import os

# Add backend to sys.path
sys.path.append(os.getcwd())

from app.ingestion.utils import get_file_probe

async def main():
    file_path = Path("/app/data/archive/2026/02/06/2026-02-06-00-YPSILON_4.xls")
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
    
    import pandas as pd
    try:
        # Check if it's binary or TSV
        is_binary = False
        with open(file_path, 'rb') as f:
            head = f.read(4)
            if head == b'PK\x03\x04' or head == b'\xd0\xcf\x11\xe0': # ZIP (.xlsx) or OLE (.xls)
                is_binary = True
        
        if is_binary:
            df = pd.read_excel(str(file_path), nrows=10, header=None)
            print("First 10 rows (Excel Binary):")
            print(df)
        else:
            with open(file_path, 'r', encoding='latin-1') as f:
                lines = [f.readline() for _ in range(10)]
                print("First 10 lines (TSV/Text):")
                for l in lines:
                    print(repr(l))
    except Exception as e:
        print(f"Error reading rows: {e}")

if __name__ == "__main__":
    asyncio.run(main())
