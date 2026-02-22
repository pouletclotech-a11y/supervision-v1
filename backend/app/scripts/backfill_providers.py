import os
import sys
import asyncio
import logging
from pathlib import Path
from sqlalchemy import select, update
import pdfplumber

# Add app to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.db.models import ImportLog, MonitoringProvider, Event
from app.services.repository import EventRepository
from app.ingestion.models import NormalizedEvent
from app.ingestion.profile_manager import ProfileManager
from app.ingestion.profile_matcher import ProfileMatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill-providers")

async def backfill():
    async with AsyncSessionLocal() as session:
        repo = EventRepository(session)
        
        # 1. Initialize Profile Engine
        manager = ProfileManager()
        await manager.load_profiles(session)
        matcher = ProfileMatcher(manager)
        
        # 2. Get all providers for easy mapping (Code -> ID)
        stmt_p = select(MonitoringProvider)
        res_p = await session.execute(stmt_p)
        providers = res_p.scalars().all()
        provider_map = {p.code: p.id for p in providers}
        
        # 3. Find imports without provider_id
        stmt = select(ImportLog).where(ImportLog.provider_id == None).where(ImportLog.archive_path != None)
        res = await session.execute(stmt)
        imports = res.scalars().all()
        
        logger.info(f"Found {len(imports)} imports to backfill")
        
        updated_count = 0
        
        for imp in imports:
            file_path = imp.archive_path
            
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                continue
                
            # 4. Probe & Match (Profile Driven)
            headers = None
            text = None
            ext = Path(file_path).suffix.lower()
            
            try:
                if ext == '.pdf':
                    with pdfplumber.open(file_path) as pdf:
                        if pdf.pages:
                            text = pdf.pages[0].extract_text() or ""
                elif ext in ['.xls', '.xlsx']:
                    # Simple probe for Excel (first row if possible, or just headers)
                    # For backfill simplicity, we'll try to match by name/ext if probe fails
                    pass
                
                profile, report = matcher.match(file_path, headers=headers, text_content=text)
                
                if profile and profile.provider_code:
                    provider_id = provider_map.get(profile.provider_code.upper())
                    
                    if provider_id:
                        logger.info(f"Resolved import {imp.id} ({imp.filename}) -> Profile={profile.profile_id}, Provider={profile.provider_code}")
                        imp.provider_id = provider_id
                        session.add(imp)
                        updated_count += 1
                        
                        # Populate site_connections
                        stmt_events = select(Event).where(Event.import_id == imp.id)
                        res_events = await session.execute(stmt_events)
                        db_events = res_events.scalars().all()
                        
                        if db_events:
                            norm_events = [
                                NormalizedEvent(
                                    timestamp=e.time,
                                    site_code=e.site_code or "UNKNOWN",
                                    client_name=e.client_name,
                                    raw_message=e.raw_message or "",
                                    status=e.severity or "INFO",
                                    event_type=e.normalized_type or "BACKFILL",
                                    source_file=imp.filename,
                                    tenant_id="default-tenant"
                                ) for e in db_events
                            ]
                            
                            added = await repo.populate_site_connections(norm_events, provider_id, imp.id)
                            logger.info(f"Populated {added} connections for import {imp.id}")
                else:
                    logger.warning(f"Could not match confident profile for {imp.filename} (Score: {report.get('best_score')})")

            except Exception as e:
                logger.error(f"Error processing import {imp.id}: {e}")
        
        await session.commit()
        logger.info(f"Backfill complete. Updated {updated_count} imports in total.")

if __name__ == "__main__":
    asyncio.run(backfill())
