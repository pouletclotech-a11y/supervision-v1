import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.db.models import Base
from app.core.config import settings

import os
import sys

async def sync_db():
    env = settings.ENVIRONMENT
    print(f"Syncing DB: {settings.SQLALCHEMY_DATABASE_URI} [ENV={env}]")
    
    if env == "production":
        # Double lock check
        allow = os.getenv("ALLOW_SYNC_DB") == "1"
        confirm = os.getenv("I_UNDERSTAND_DATA_LOSS") == "YES"
        
        if not (allow and confirm):
            print("CRITICAL: sync_db is forbidden in production environment!")
            print("To override this, you MUST set BOTH:")
            print("  ALLOW_SYNC_DB=1")
            print("  I_UNDERSTAND_DATA_LOSS=YES")
            return

    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, echo=True)
    async with engine.begin() as conn:
        # Instead of drop_all, we could use create_all to add new tables
        # But for test/dev, recreating is fine.
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("DB Sync complete.")

if __name__ == "__main__":
    asyncio.run(sync_db())
