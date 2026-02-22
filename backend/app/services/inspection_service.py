import os
import csv
import re
import pandas as pd
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from app.utils.text import clean_excel_value

class InspectionService:
    @staticmethod
    def inspect_file(file_path: str) -> Dict[str, Any]:
        path_obj = Path(file_path)
        if not path_obj.exists():
            return {"error": "File not found"}

        ext = path_obj.suffix.lower()
        
        # 1. Detect Type
        is_binary_excel = False
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4)
                if header == b'PK\x03\x04': # ZIP header for .xlsx
                    is_binary_excel = True
        except Exception:
            pass

        if ext == '.pdf':
            return InspectionService._inspect_pdf(file_path)
        elif is_binary_excel:
            return InspectionService._inspect_xlsx(file_path)
        elif ext in ['.xls', '.csv', '.tsv']:
            return InspectionService._inspect_tsv(file_path)
        
        return {"file_type": "UNKNOWN", "error": f"Unsupported extension {ext}"}

    @staticmethod
    def _inspect_tsv(file_path: str) -> Dict[str, Any]:
        sample_rows = []
        try:
            # Try to read as TSV (standard for YPSILON .xls)
            with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
                reader = csv.reader(f, delimiter='\t')
                for i, row in enumerate(reader):
                    if i >= 10: break # Only 10 lines
                    sample_rows.append([clean_excel_value(c) for c in row])
        except Exception as e:
            return {"error": f"TSV Read Error: {str(e)}"}

        headers = sample_rows[0] if sample_rows else []
        
        return {
            "file_type": "XLS_TSV",
            "headers": headers,
            "sample_rows": sample_rows[1:6] if len(sample_rows) > 1 else [],
            "skeleton_yaml": InspectionService._generate_skeleton("XLS_TSV", headers)
        }

    @staticmethod
    def _inspect_xlsx(file_path: str) -> Dict[str, Any]:
        try:
            df = pd.read_excel(file_path, header=None, engine='openpyxl')
            if df.empty:
                return {"file_type": "XLSX", "headers": [], "sample_rows": []}
            
            # Use first row as headers
            headers = [str(c) for c in df.iloc[0].tolist()]
            sample_rows = df.iloc[1:6].values.tolist()
            
            return {
                "file_type": "XLSX",
                "headers": headers,
                "sample_rows": sample_rows,
                "skeleton_yaml": InspectionService._generate_skeleton("XLSX", headers)
            }
        except Exception as e:
             return {"error": f"XLSX Read Error: {str(e)}"}

    @staticmethod
    def _inspect_pdf(file_path: str) -> Dict[str, Any]:
        if pdfplumber is None:
            return {"error": "pdfplumber not installed"}
        
        raw_text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                # Extract first page only for inspection
                if pdf.pages:
                    raw_text = pdf.pages[0].extract_text() or ""
        except Exception as e:
            return {"error": f"PDF Read Error: {str(e)}"}

        return {
            "file_type": "PDF",
            "raw_text_sample": raw_text[:2000], # First 2k chars
            "skeleton_yaml": InspectionService._generate_skeleton("PDF", raw_text=raw_text)
        }

    @staticmethod
    def _generate_skeleton(file_type: str, headers: List[str] = None, raw_text: str = "") -> str:
        profile_id = "new_profile_suggestion"
        
        if file_type == "PDF":
            return f"""profile_id: {profile_id}
name: Nouveau Profil PDF
priority: 5
detection:
  extensions:
    - .pdf
  required_text:
    - "{raw_text[:20].strip() if raw_text else 'KEYWORD'}"
mapping:
  - source: "REGEX_HERE"
    target: site_code
"""
        
        # For Excel/TSV
        h_str = "\n    - ".join(headers[:3]) if headers else "TITRE"
        return f"""profile_id: {profile_id}
name: Nouveau Profil Excel
priority: 5
detection:
  extensions:
    - .xls
    - .xlsx
  required_headers:
    - {h_str}
mapping:
  - source: 0
    target: site_code
  - source: 1
    target: client_name
"""
