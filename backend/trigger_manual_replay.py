import asyncio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.models import ImportLog

DATABASE_URL = "postgresql+asyncpg://admin:admin@localhost:5432/supervision"

async def request_replay(import_id: int):
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        stmt = update(ImportLog).where(ImportLog.id == import_id).values(status="REPLAY_REQUESTED")
        await session.execute(stmt)
        await session.commit()
    
    print(f"Import {import_id} marked as REPLAY_REQUESTED.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(request_replay(1627))
