import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from app.db.models import Event, EventRuleHit, SiteConnection
from app.core.config import settings

logger = logging.getLogger("business-rules")

class BusinessRuleEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.config = getattr(settings, "BUSINESS_RULES", {})

    async def evaluate_batch(self, events: List[Event]):
        """Evaluate rules for a batch of persisted events."""
        for event in events:
            await self.evaluate_rules(event)

    async def evaluate_rules(self, event: Event):
        """Evaluate all V1 business rules for a single event."""
        # 1. Intrusion with Maintenance
        await self.rule_intrusion_maintenance(event)
        
        # 2. Absence Test
        await self.rule_absence_test(event)
        
        # 3. Technical Faults
        await self.rule_technical_faults(event)
        
        # 4. Ejection (48h)
        await self.rule_ejection_48h(event)
        
        # 5. Inhibition
        await self.rule_inhibition(event)

    async def rule_intrusion_maintenance(self, event: Event):
        keywords = self.config.get("intrusion", {}).get("keywords", [])
        msg = (event.normalized_message or "").lower()
        if any(k in msg for k in keywords):
            if event.in_maintenance:
                return # Cancelled by maintenance
            await self._record_hit(event, "INTRUSION_NO_MAINTENANCE", "Intrusion sans maintenance active")

    async def rule_absence_test(self, event: Event):
        triggers = self.config.get("absence_test", {}).get("trigger_keywords", [])
        msg = (event.normalized_message or "").lower()
        if any(t in msg for t in triggers):
            await self._record_hit(event, "ABSENCE_TEST", "Manque de test cyclique détecté")

    async def rule_technical_faults(self, event: Event):
        codes = self.config.get("faults", {}).get("apparition_codes", [])
        if event.raw_code in codes:
            await self._record_hit(event, "TECHNICAL_FAULT", f"Défaut technique rapporté: {event.raw_code}")

    async def rule_ejection_48h(self, event: Event):
        ejection_code = self.config.get("ejection", {}).get("code", "570")
        if event.raw_code == ejection_code:
            await self._record_hit(event, "EJECTION_48H", "Éjection détectée (surveillance 48h)")

    async def rule_inhibition(self, event: Event):
        inhibition_keyword = self.config.get("inhibition", {}).get("keyword", "***")
        msg = (event.normalized_message or "")
        if inhibition_keyword in msg:
            await self._record_hit(event, "ZONE_INHIBITION", f"Zone inhibée détectée: {msg}")

    async def _record_hit(self, event: Event, rule_code: str, explanation: str):
        # Resolve rule_id from DB if possible, or use a default
        # For Phase 1, we use rule_name as the primary identifier in EventRuleHit
        hit = EventRuleHit(
            event_id=event.id,
            rule_id=0, # Dynamic resolution later
            rule_name=rule_code
        )
        self.session.add(hit)
        logger.info(f"[RULE_HIT] {rule_code} on event {event.id}")
