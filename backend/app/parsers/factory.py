from typing import List, Type, Dict
from pathlib import Path
from app.parsers.base import BaseParser
from app.parsers.excel_parser import ExcelParser
from app.parsers.pdf_parser import PdfParser

class ParserFactory:
    _parsers: Dict[str, Type[BaseParser]] = {}

    @classmethod
    def register_parser(cls, parser_cls: Type[BaseParser]):
        # Optional: dynamic registration
        pass 

    @classmethod
    def get_parser(cls, ext: str) -> BaseParser:
        """
        Returns a parser instance for the given extension (e.g. '.xls')
        """
        ext = ext.lower()
        if ext in ['.xls', '.xlsx']:
            return ExcelParser()
        elif ext == '.pdf':
            return PdfParser()
        
        return None
