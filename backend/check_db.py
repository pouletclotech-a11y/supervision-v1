import asyncio
from sqlalchemy import select, func
from app.db.session import AsyncSessionLocal
from app.db.models import Event

async def check_null_codes():
    async with AsyncSessionLocal() as session:
        stmt = select(func.count(Event.id)).where(Event.raw_code.is_(None))
        res = await session.execute(stmt)
        count_null = res.scalar()
        
        stmt = select(func.count(Event.id)).where(Event.raw_code == '')
        res = await session.execute(stmt)
        count_empty = res.scalar()
        
        print(f"Null raw_code: {count_null}")
        print(f"Empty raw_code: {count_empty}")

if __name__ == "__main__":
    asyncio.run(check_null_codes())
