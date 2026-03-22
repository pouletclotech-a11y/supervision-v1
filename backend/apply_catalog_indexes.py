import asyncio
from sqlalchemy import text
from app.db.session import SessionLocal

async def apply_indexes():
    async with SessionLocal() as session:
        print("Applying migration: indexes on events table...")
        try:
            # 1. raw_code index
            await session.execute(text("CREATE INDEX IF NOT EXISTS ix_events_raw_code ON events (raw_code)"))
            # 2. composite index for catalog speed
            await session.execute(text("CREATE INDEX IF NOT EXISTS ix_events_raw_code_time ON events (raw_code, time DESC)"))
            await session.commit()
            print("Successfully applied indexes.")
        except Exception as e:
            print(f"Error applying indexes: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(apply_indexes())
