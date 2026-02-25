import asyncio
import os
import sys
from datetime import date
from sqlalchemy import select, update, or_

# Add backend to sys.path
sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal
from app.db.models import ImportLog

async def trigger_replay():
    target_date = date(2026, 2, 25)
    print(f"--- TRIGGER REPLAY FOR {target_date} ---")
    
    async with AsyncSessionLocal() as session:
        # Select ALL imports from target date
        stmt = select(ImportLog).where(
            ImportLog.created_at >= target_date,
            ImportLog.created_at < date(2026, 2, 26)
        )
        result = await session.execute(stmt)
        imports = result.scalars().all()
        
        if not imports:
            print("No imports found for this date with SUCCESS/ERROR status.")
            return

        import_ids = [imp.id for imp in imports]
        print(f"Found {len(imports)} imports concernés : {import_ids}")
        
        # Update status to REPLAY_REQUESTED
        stmt_update = update(ImportLog).where(
            ImportLog.id.in_(import_ids)
        ).values(status="REPLAY_REQUESTED")
        
        await session.execute(stmt_update)
        await session.commit()
        
        print(f"Successfully marked {len(imports)} imports as REPLAY_REQUESTED.")

if __name__ == "__main__":
    asyncio.run(trigger_replay())
