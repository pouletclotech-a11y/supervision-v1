import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.db.models import DBIngestionProfile

async def main():
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(DBIngestionProfile).where(DBIngestionProfile.profile_id == 'spgo_tsv'))
        p = r.scalar_one()
        print('detection:', p.detection)

asyncio.run(main())
