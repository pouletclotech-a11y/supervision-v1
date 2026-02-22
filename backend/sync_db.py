import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.db.models import Base
from app.core.config import settings

async def sync_db():
    print(f"Syncing DB: {settings.SQLALCHEMY_DATABASE_URI}")
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, echo=True)
    async with engine.begin() as conn:
        # Instead of drop_all, we could use create_all to add new tables
        # But for test/dev, recreating is fine.
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("DB Sync complete.")

if __name__ == "__main__":
    asyncio.run(sync_db())
