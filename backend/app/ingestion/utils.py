import hashlib
import logging
from pathlib import Path
from typing import Tuple, Optional, List

logger = logging.getLogger("ingestion-utils")

def compute_sha256(file_path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_file_probe(file_path: Path) -> Tuple[Optional[List[str]], Optional[str]]:
    """
    Extracts a small sample of headers or text to help the ProfileMatcher.
    - Excel: A1 value (first row)
    - PDF: First page text (limit to 2000 chars)
    """
    ext = file_path.suffix.lower()
    headers = None
    text_content = None
    
    try:
        if ext in ['.xls', '.xlsx']:
            # Check if binary or TSV
            is_binary = False
            with open(file_path, 'rb') as f:
                head = f.read(4)
                if head == b'PK\x03\x04': # ZIP header for .xlsx
                    is_binary = True
            
            if is_binary:
                import pandas as pd
                # Read only 1 row, no header assume first row is data or signal
                df = pd.read_excel(str(file_path), nrows=1, header=None)
                if not df.empty:
                    headers = [str(c).strip() for c in df.iloc[0].tolist() if c is not None]
            else:
                import csv
                try:
                    from app.utils.text import clean_excel_value
                except ImportError:
                    # Fallback if utils.text not available or differently named
                    def clean_excel_value(v): return str(v).strip()

                with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
                    reader = csv.reader(f, delimiter='\t')
                    # V1 Minimal: Scan up to 20 lines to skip empty leading rows
                    for _ in range(20):
                        row = next(reader, None)
                        if row is None: 
                            break
                        row_headers = [clean_excel_value(c) for c in row if c]
                        if row_headers:
                            headers = row_headers
                            break
        
        elif ext == '.pdf':
            import pdfplumber
            with pdfplumber.open(str(file_path)) as pdf:
                if pdf.pages:
                    text_content = pdf.pages[0].extract_text()
                    if text_content:
                        text_content = text_content[:2000]
    except Exception as e:
        logger.warning(f"[Probe] Failed for {file_path.name}: {e}")
        
    return headers, text_content
def detect_file_format(path: Path) -> str:
    """
    Detect format by magic numbers and content (Phase 2).
    """
    try:
        with open(path, 'rb') as f:
            header = f.read(8)
            # PK ZIP (XLSX)
            if header.startswith(b'PK\x03\x04'):
                return "XLSX_NATIVE"
            # OLE2 (Old XLS)
            if header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
                return "OLE2_XLS"
            # PDF Magic Number
            if header.startswith(b'%PDF'):
                return "PDF"
        
        # Fallback to Text/TSV detection
        with open(path, 'r', encoding='latin-1', errors='replace') as f:
            # Check first 5 lines for tabs
            lines = [f.readline() for _ in range(5)]
            tab_count = sum(line.count('\t') for line in lines)
            if tab_count > 0:
                return "TSV_XLS"
    except:
        pass
    return "UNKNOWN"
