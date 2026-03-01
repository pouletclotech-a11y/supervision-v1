import asyncio
import logging
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

async def migrate():
    async with AsyncSessionLocal() as session:
        try:
            # Add column 'score' if not exists
            await session.execute(text("""
                ALTER TABLE event_rule_hits 
                ADD COLUMN IF NOT EXISTS score FLOAT;
            """))
            await session.commit()
            logger.info("Column 'score' added successfully to 'event_rule_hits' (idempotent).")
        except Exception as e:
            await session.rollback()
            logger.error(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(migrate())
