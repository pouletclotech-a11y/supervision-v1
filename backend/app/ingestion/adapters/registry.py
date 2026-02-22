import os
import logging
from typing import List, Tuple, Iterable
from app.ingestion.adapters.base import BaseAdapter, AdapterItem
from app.ingestion.adapters.dropbox import DropboxAdapter
from app.ingestion.adapters.email import EmailAdapter

logger = logging.getLogger("adapter-registry")

class AdapterRegistry:
    def __init__(self):
        self._adapters: List[BaseAdapter] = []
        self._load_adapters()

    def _load_adapters(self):
        """Initialize adapters based on environment configuration."""
        enabled_adapters_str = os.getenv("INGESTION_ADAPTERS", "dropbox,email")
        enabled_names = [name.strip().lower() for name in enabled_adapters_str.split(",")]

        if "dropbox" in enabled_names:
            logger.info("Registering DropboxAdapter")
            self._adapters.append(DropboxAdapter())
        
        if "email" in enabled_names:
            logger.info("Registering EmailAdapter")
            self._adapters.append(EmailAdapter())

    async def poll_all(self) -> Iterable[Tuple[BaseAdapter, AdapterItem]]:
        """Poll all registered adapters and yield items with their respective adapter."""
        for adapter in self._adapters:
            try:
                items = await adapter.poll()
                for item in items:
                    yield adapter, item
            except Exception as e:
                logger.error(f"Error polling adapter {adapter.__class__.__name__}: {e}")
