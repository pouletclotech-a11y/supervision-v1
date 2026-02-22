import os
import sys
import asyncio
import logging
from pathlib import Path
from sqlalchemy import select, delete

# Add app to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.db.models import ImportLog, Event, SiteConnection
from app.parsers.pdf_parser import PdfParser
from app.services.repository import EventRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reparse-cors")

async def reparse():
    async with AsyncSessionLocal() as session:
        repo = EventRepository(session)
        parser = PdfParser()
        
        # 1. Select all CORS imports (provider_id = 3)
        stmt = select(ImportLog).where(ImportLog.provider_id == 3).where(ImportLog.archive_path != None)
        res = await session.execute(stmt)
        imports = res.scalars().all()
        
        logger.info(f"Found {len(imports)} CORS imports to reparse")
        
        for imp in imports:
            file_path = imp.archive_path
            if not os.path.exists(file_path) or not file_path.lower().endswith('.pdf'):
                continue
                
            logger.info(f"Reparsing {file_path} for import {imp.id}...")
            
            # A. Parse events properly with new regex
            try:
                new_events = parser.parse(file_path)
                # Filter out pure SYSTEM/PARSING events if we found real data
                real_events = [e for e in new_events if e.site_code != "SYSTEM"]
                
                if real_events:
                    logger.info(f"Extracted {len(real_events)} REAL events from {imp.filename}")
                    
                    # B. Clear old events for this import
                    # (To avoid duplicates and clean up "SYSTEM" logs)
                    stmt_del = delete(Event).where(Event.import_id == imp.id)
                    await session.execute(stmt_del)
                    
                    # C. Batch Insert new events
                    # We need to map them back to the import_id
                    await repo.create_batch(real_events, import_id=imp.id)
                    
                    # D. Update counts in import log
                    imp.events_count = len(real_events)
                    session.add(imp)
                    
                    # E. Populate site_connections
                    await repo.populate_site_connections(real_events, imp.provider_id, imp.id)
                else:
                    logger.warning(f"No real events found for {imp.filename} even with new parser.")
                    
            except Exception as e:
                logger.error(f"Failed to reparse {imp.filename}: {e}")
        
        await session.commit()
        logger.info("Reparse CORS complete.")

if __name__ == "__main__":
    asyncio.run(reparse())
