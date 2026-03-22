import asyncio
from datetime import date
from sqlalchemy import select, func, Date
from app.db.session import AsyncSessionLocal
from app.db.models import Event, EventRuleHit, ImportLog

async def reproduce_stats_error():
    async with AsyncSessionLocal() as session:
        target_date = date(2026, 3, 22)
        print(f"Testing stats for {target_date}...")
        
        try:
            # Replicate the query in get_intrusion_stats
            stmt = (
                select(func.count(func.distinct(Event.site_code)))
                .join(EventRuleHit, Event.id == EventRuleHit.event_id)
                .where(func.cast(EventRuleHit.created_at, Date) == target_date)
            )
            
            # Simulate provider filter (often active for operators)
            provider_ids = [1, 2, 3] # Dummy IDs
            stmt = stmt.join(ImportLog, Event.import_id == ImportLog.id).where(ImportLog.provider_id.in_(provider_ids))
            
            print("Executing query...")
            res = await session.execute(stmt)
            count = res.scalar()
            print(f"Success! Count: {count}")
            
        except Exception as e:
            print(f"CAUGHT ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(reproduce_stats_error())
