
import asyncio
import logging
from sqlalchemy import select, update, delete, text
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models import Event, SiteConnection
from app.ingestion.normalizer import normalize_site_code_full

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration-v12")

async def migrate_site_codes():
    logger.info("Starting site_code normalization migration (Phase 1.5 Step 1)")
    
    async with AsyncSessionLocal() as session:
        # 1. Update Events
        logger.info("Normalizing all events site_code...")
        
        total_updated = 0
        limit = 1000
        
        while True:
            # Selec events where site_code_raw is still NULL
            stmt = select(Event).filter(Event.site_code_raw == None).limit(limit)
            result = await session.execute(stmt)
            events = result.scalars().all()
            
            if not events:
                break
                
            for event in events:
                canonical, raw = normalize_site_code_full(event.site_code)
                event.site_code_raw = raw
                event.site_code = canonical
                total_updated += 1
            
            await session.commit()
            logger.info(f"Updated {total_updated} events...")
            
        logger.info(f"Finished updating {total_updated} events.")
        
        # 2. Rebuild Site Connections
        logger.info("Rebuilding site_connections table...")
        
        await session.execute(text("TRUNCATE TABLE site_connections CASCADE"))
        await session.commit()
        
        # Repopulate from normalized events
        insert_stmt = text("""
            INSERT INTO site_connections (provider_id, code_site, site_code_raw, client_name, first_seen_at, last_seen_at, total_events, first_import_id)
            SELECT 
                i.provider_id,
                e.site_code,
                MIN(e.site_code_raw),
                MAX(e.client_name),
                MIN(e.time),
                MAX(e.time),
                COUNT(*),
                MIN(e.import_id)
            FROM events e
            JOIN imports i ON e.import_id = i.id
            GROUP BY i.provider_id, e.site_code
        """)
        
        await session.execute(insert_stmt)
        await session.commit()
        
        # Verify
        result = await session.execute(text("SELECT COUNT(*) FROM site_connections"))
        count = result.scalar()
        logger.info(f"Site connections rebuilt: {count} entries.")

if __name__ == "__main__":
    asyncio.run(migrate_site_codes())
