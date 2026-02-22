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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill-providers")

async def backfill():
    async with AsyncSessionLocal() as session:
        repo = EventRepository(session)
        
        # 1. Get all providers for easy mapping
        stmt = select(MonitoringProvider)
        res = await session.execute(stmt)
        providers = res.scalars().all()
        provider_map = {p.code: p.id for p in providers}
        
        # 2. Find imports without provider_id
        stmt = select(ImportLog).where(ImportLog.provider_id == None).where(ImportLog.archive_path != None)
        res = await session.execute(stmt)
        imports = res.scalars().all()
        
        logger.info(f"Found {len(imports)} imports to backfill")
        
        updated_count = 0
        
        for imp in imports:
            provider_id = None
            file_path = imp.archive_path
            
            # Resolve absolute path for the container
            # The DB stores /app/data/archive/... which is correct inside the container
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                continue
                
            if file_path.lower().endswith('.pdf'):
                try:
                    with pdfplumber.open(file_path) as pdf:
                        first_page_text = pdf.pages[0].extract_text() or ""
                        
                        if "CORS" in first_page_text.upper():
                            provider_id = provider_map.get('CORS')
                        elif "SPGO" in first_page_text.upper():
                            provider_id = provider_map.get('SPGO')
                except Exception as e:
                    logger.error(f"Error parsing PDF {file_path}: {e}")
            
            # If still null and it's an XLS, try to guess from prefix
            if provider_id is None and (file_path.lower().endswith('.xls') or file_path.lower().endswith('.xlsx')):
                # Look for a PDF with the same prefix in the same folder
                prefix = Path(file_path).stem
                # Try to find if any PDF in the same batch has been resolved
                # Simplified: search for a PDF import with similar name
                pdf_filename = prefix + ".pdf"
                stmt_pdf = select(ImportLog).where(ImportLog.filename == pdf_filename).where(ImportLog.provider_id != None)
                res_pdf = await session.execute(stmt_pdf)
                resolved_pdf = res_pdf.scalar_one_or_none()
                if resolved_pdf:
                    provider_id = resolved_pdf.provider_id
                else:
                    # Fallback to SPGO if it's the most common and filename looks like YPSILON
                    if "YPSILON" in prefix.upper():
                        provider_id = provider_map.get('SPGO')

            if provider_id:
                logger.info(f"Updating import {imp.id} ({imp.filename}) -> provider_id={provider_id}")
                imp.provider_id = provider_id
                session.add(imp)
                updated_count += 1
                
                # Now populate site_connections for this import
                # We need to fetch events for this import
                stmt_events = select(Event).where(Event.import_id == imp.id)
                res_events = await session.execute(stmt_events)
                db_events = res_events.scalars().all()
                
                if db_events:
                    # Convert DB events to NormalizedEvent for the repo method
                    norm_events = []
                    for e in db_events:
                        norm_events.append(NormalizedEvent(
                            timestamp=e.time,
                            site_code=e.site_code or "UNKNOWN",
                            client_name=e.client_name,
                            raw_message=e.raw_message or "",
                            status=e.severity or "INFO",
                            event_type=e.normalized_type or "BACKFILL",
                            source_file=imp.filename
                        ))
                    
                    added = await repo.populate_site_connections(norm_events, provider_id, imp.id)
                    logger.info(f"Populated {added} connections for import {imp.id}")
        
        await session.commit()
        logger.info(f"Backfill complete. Updated {updated_count} imports in total.")

if __name__ == "__main__":
    asyncio.run(backfill())
