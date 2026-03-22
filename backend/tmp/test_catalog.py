import asyncio
from app.db.session import AsyncSessionLocal
from app.services.repository import EventRepository
import json

async def test_catalog():
    async with AsyncSessionLocal() as session:
        repo = EventRepository(session)
        items = await repo.get_event_catalog()
        print(f"COUNT: {len(items)}")
        if items:
            # Sort by occurrences DESC to see top items
            items.sort(key=lambda x: x['occurrences'], reverse=True)
            print(f"TOP ITEM: {json.dumps(items[0], indent=2, default=str)}")
        else:
            print("CATALOG IS EMPTY")
            # Debug: check if events exist at all
            from sqlalchemy import text
            res = await session.execute(text("SELECT COUNT(*) FROM events"))
            count = res.scalar()
            print(f"TOTAL EVENTS IN DB: {count}")
            
            res = await session.execute(text("SELECT COUNT(*) FROM events e JOIN imports i ON e.import_id = i.id JOIN monitoring_providers p ON i.provider_id = p.id"))
            joined_count = res.scalar()
            print(f"JOINED EVENTS COUNT: {joined_count}")

if __name__ == "__main__":
    asyncio.run(test_catalog())
