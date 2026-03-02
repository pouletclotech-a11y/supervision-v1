from typing import List, Type, Dict, Optional
from pathlib import Path
from app.parsers.base import BaseParser
from app.parsers.excel_parser import ExcelParser
from app.parsers.pdf_parser import PdfParser
from app.parsers.tsv_parser import TsvParser

class ParserFactory:
    _parsers: Dict[str, Type[BaseParser]] = {}

    @classmethod
    def register_parser(cls, parser_cls: Type[BaseParser]):
        pass 

    @classmethod
    def get_parser(cls, ext: str) -> BaseParser:
        """
        Backward compatible extension-based selection
        """
        ext = ext.lower()
        if ext == '.xlsx':
            return ExcelParser()
        elif ext == '.xls':
            # Default to Excel for safety, but worker will prefer kind
            return ExcelParser()
        elif ext == '.pdf':
            return PdfParser()
        elif ext == '.tsv':
            return TsvParser()
        
        return None

    @classmethod
    def get_parser_by_kind(cls, kind: str) -> Optional[BaseParser]:
        """
        Explicit selection by format_kind (Phase 2)
        """
        if kind == "XLSX_NATIVE":
            return ExcelParser()
        elif kind == "TSV_XLS":
            return TsvParser()
        return None
