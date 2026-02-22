from abc import ABC, abstractmethod
from typing import Iterable, Optional, Tuple, Any, Dict
from pydantic import BaseModel
from datetime import datetime

class AdapterItem(BaseModel):
    path: str
    filename: str
    size_bytes: int
    mtime: datetime
    source: str
    sha256: Optional[str] = None
    source_message_id: Optional[str] = None
    metadata: Dict[str, Any] = {}

class BaseAdapter(ABC):
    @abstractmethod
    async def poll(self) -> Iterable[AdapterItem]:
        """Poll the source for new items to process."""
        pass

    @abstractmethod
    async def ack_success(self, item: AdapterItem, import_id: int):
        """Acknowledge successful processing. Move to archive."""
        pass

    @abstractmethod
    async def ack_duplicate(self, item: AdapterItem, existing_import_id: int):
        """Handle duplicate item. Move to duplicates archive."""
        pass

    @abstractmethod
    async def ack_unmatched(self, item: AdapterItem, reason: str):
        """Handle unmatched item. Move to unmatched folder."""
        pass

    @abstractmethod
    async def ack_error(self, item: AdapterItem, reason: str):
        """Handle processing error. Move to error folder."""
        pass
