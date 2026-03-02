import asyncio
import logging
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

async def migrate():
    async with AsyncSessionLocal() as session:
        try:
            # 1. Index on event_rule_hits.event_id
            await session.execute(text("CREATE INDEX IF NOT EXISTS ix_event_rule_hits_event_id ON event_rule_hits (event_id);"))
            
            # 2. Index on event_rule_hits.created_at
            await session.execute(text("CREATE INDEX IF NOT EXISTS ix_event_rule_hits_created_at ON event_rule_hits (created_at);"))
            
            # 3. Index on events.site_code (already exists in models.py, but confirming)
            await session.execute(text("CREATE INDEX IF NOT EXISTS ix_events_site_code ON events (site_code);"))
            
            await session.commit()
            logger.info("Indices for Phase 3 created successfully.")
        except Exception as e:
            await session.rollback()
            logger.error(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(migrate())
