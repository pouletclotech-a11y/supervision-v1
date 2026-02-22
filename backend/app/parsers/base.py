from abc import ABC, abstractmethod
from typing import List
from app.ingestion.models import NormalizedEvent

class BaseParser(ABC):
    """
    Interface for all file parsers.
    """
    
    @abstractmethod
    def parse(self, file_path: str, source_timezone: str = "UTC", parser_config: dict = None) -> List[NormalizedEvent]:
        """
        Parse a file and return a list of normalized events.
        """
        pass

    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """
        Return list of supported file extensions (e.g. ['.xls', '.xlsx'])
        """
        pass
