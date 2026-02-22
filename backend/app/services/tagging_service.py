import re
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import EventCodeCatalog
from app.utils.text import normalize_text
from app.ingestion.models import NormalizedEvent

logger = logging.getLogger(__name__)

class TaggingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._cache: Dict[str, Any] = {}

    async def _ensure_cache(self):
        """Loads the catalog into memory for fast lookup during batch processing."""
        if self._cache:
            return
        
        stmt = select(EventCodeCatalog).where(EventCodeCatalog.is_active == True)
        result = await self.session.execute(stmt)
        catalog_items = result.scalars().all()
        
        for item in catalog_items:
            self._cache[item.code.upper()] = {
                "category": item.category,
                "severity": item.severity,
                "alertable_default": item.alertable_default,
                "label": item.label
            }
        
        logger.debug(f"Tagging cache initialized with {len(self._cache)} items.")

    def _extract_code(self, event: NormalizedEvent) -> str:
        """
        Attempts to find the most relevant code for lookup.
        Tries raw_code, or identifies specific patterns (CAM).
        """
        if event.raw_code:
            code = event.raw_code.upper().strip()
            # Handle numerical codes that might be wrapped in quotes
            return code.replace('"', '').replace('=', '')
            
        evt_msg = getattr(event, 'normalized_message', None) or normalize_text(getattr(event, 'raw_message', ''))
        
        # CAM Pattern: CAMx-y or CAMx
        if re.search(r'cam\d+(-\d+)?', evt_msg):
            return "CAM"
            
        return "UNKNOWN"

    async def tag_event(self, event: NormalizedEvent) -> NormalizedEvent:
        """
        Enriches the event with catalog data.
        Prioritizes:
        1. Exact Code Match
        2. Keyword Match (from Catalog Label)
        3. Pattern Match (CAM)
        """
        await self._ensure_cache()
        
        code = self._extract_code(event)
        evt_msg = getattr(event, 'normalized_message', None) or normalize_text(getattr(event, 'raw_message', ''))
        
        mapping = None
        
        # 1. Exact Match on Code
        if code != "UNKNOWN":
            mapping = self._cache.get(code)
        
        # 2. Keyword Match (iterate over catalog to find matches in message)
        if not mapping:
            # We look for catalog items where either the CODE or the LABEL exists in the message
            for c_code, c_data in self._cache.items():
                # Check Code
                if c_code != "UNKNOWN" and c_code.lower() in evt_msg:
                    mapping = c_data
                    break
                # Check Label
                label = c_data.get("label")
                if label:
                    norm_label = normalize_text(label)
                    if norm_label in evt_msg:
                        mapping = c_data
                        break
        
        # 3. Fallback to UNKNOWN
        if not mapping:
            mapping = self._cache.get("UNKNOWN", {
                "category": "unknown",
                "severity": "info",
                "alertable_default": False,
                "label": "Unknown Code"
            })
            
        # Apply tags
        event.category = mapping["category"]
        event.status = mapping["severity"].upper()
        event.alertable_default = mapping["alertable_default"]
        
        # Optional: store catalog label in metadata
        if "label" in mapping:
            event.metadata["catalog_label"] = mapping["label"]
            
        return event

    async def tag_batch(self, events: List[NormalizedEvent]) -> List[NormalizedEvent]:
        """Tags a list of events efficiently."""
        await self._ensure_cache()
        for e in events:
            await self.tag_event(e)
        return events
