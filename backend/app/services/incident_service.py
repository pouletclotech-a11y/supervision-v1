import hashlib
import re
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Event, Incident

logger = logging.getLogger(__name__)

class IncidentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def generate_incident_key(self, site_code: str, raw_message: str) -> str:
        """
        Generates a stable signature for an incident.
        Excludes operator markers (Cam1/2/3, NVF) to ensure pairing stability.
        """
        # 1. Normalize message: Uppercase, trim, collapse spaces
        msg = raw_message.upper().strip()
        msg = re.sub(r'\s+', ' ', msg)
        
        # 2. Strip operator markers (Case insensitive check via upper)
        # We strip common patterns like Cam 1, Cam. 2, NVF, etc.
        msg = re.sub(r'CAM\s*\d+', '', msg)
        msg = re.sub(r'NVF', '', msg)
        
        # 3. Final cleanup after replacement
        msg = msg.strip()
        
        # 4. Hash (site_code + normalized message)
        seed = f"{site_code}:{msg}"
        return hashlib.sha256(seed.encode()).hexdigest()

    async def get_incident_by_signature(self, site_code: str, incident_key: str, opened_at: datetime) -> Optional[Incident]:
        """Finds an incident by its unique signature."""
        stmt = (
            select(Incident)
            .where(Incident.site_code == site_code)
            .where(Incident.incident_key == incident_key)
            .where(Incident.opened_at == opened_at)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_open_incident(self, site_code: str, incident_key: str) -> Optional[Incident]:
        """Finds the latest OPEN incident for a given key and site."""
        stmt = (
            select(Incident)
            .where(Incident.site_code == site_code)
            .where(Incident.incident_key == incident_key)
            .where(Incident.status == 'OPEN')
            .order_by(Incident.opened_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_incident_by_close_event(self, event_id: int) -> Optional[Incident]:
        """Finds if an incident was already closed by this specific event."""
        stmt = (
            select(Incident)
            .where(Incident.close_event_id == event_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def process_batch_incidents(self, import_id: int):
        """
        Processes events for a specific import to reconstruct incidents.
        Events are sorted by time and ID to ensure determinism.
        """
        # Fetch events for this import, sorted
        stmt = (
            select(Event)
            .where(Event.import_id == import_id)
            .where(Event.normalized_type != 'OPERATOR_ACTION')
            .order_by(Event.time.asc(), Event.id.asc())
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()
        
        unmatched_close = 0
        
        for event in events:
            action = (event.normalized_type or event.raw_message or "").upper()
            
            # Signature generation
            # Note: normalized_type might be "APPARITION", "DISPARITION"
            # We use raw_message for the "signature" part of the key
            key = self.generate_incident_key(event.site_code, event.raw_message)
            
            if "APPARITION" in action:
                # 1. Check for EXACT duplicate (idempotence)
                exact_match = await self.get_incident_by_signature(event.site_code, key, event.time)
                if exact_match:
                    logger.debug(f"Incident already exists for {event.site_code}:{key} at {event.time}. Skipping.")
                    continue

                # 2. Check if an incident is already OPEN for this key (suppress duplicates)
                existing_open = await self.get_open_incident(event.site_code, key)
                if not existing_open:
                    # Create new OPEN incident
                    new_incident = Incident(
                        site_code=event.site_code,
                        incident_key=key,
                        label=event.raw_message, # Use first msg as label
                        opened_at=event.time,
                        status='OPEN',
                        open_event_id=event.id
                    )
                    self.session.add(new_incident)
                    await self.session.flush()
                else:
                    logger.debug(f"Incident already OPEN for {event.site_code}:{key}. Skipping duplicate apparition.")
            
            elif "DISPARITION" in action:
                # 2. Check if this specific event already closed an incident (idempotence)
                already_closed = await self.get_incident_by_close_event(event.id)
                if already_closed:
                    logger.debug(f"Event {event.id} already closed incident {already_closed.id}. Skipping.")
                    continue

                # 3. Try to close an existing OPEN incident
                open_inc = await self.get_open_incident(event.site_code, key)
                if open_inc:
                    # Close it
                    open_inc.closed_at = event.time
                    open_inc.status = 'CLOSED'
                    open_inc.close_event_id = event.id
                    
                    # Calculate duration
                    delta = (event.time - open_inc.opened_at).total_seconds()
                    open_inc.duration_seconds = int(max(0, delta))
                    
                    await self.session.flush()
                else:
                    unmatched_close += 1
                    logger.debug(f"Unmatched DISPARITION for {event.site_code}:{key}")

        return unmatched_close
