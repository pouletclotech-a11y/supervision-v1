import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def fix_data():
    print("Normalizing alert_rules data...")
    async with AsyncSessionLocal() as session:
        # Update null or invalid time_scope to 'NONE'
        # Note: HOLIDAYS was HOLIDAY in previous version maybe, so we map it.
        await session.execute(text("""
            UPDATE alert_rules 
            SET time_scope = 'NONE' 
            WHERE time_scope IS NULL 
               OR time_scope NOT IN ('NONE', 'NIGHT', 'WEEKEND', 'HOLIDAYS', 'OFF_BUSINESS_HOURS', 'BUSINESS_HOURS')
        """))
        
        # Specific fixes if needed
        await session.execute(text("UPDATE alert_rules SET time_scope = 'WEEKEND' WHERE time_scope = 'WEEKEND_OR_HOLIDAY'"))
        
        await session.commit()
    print("Data normalization completed.")

if __name__ == "__main__":
    asyncio.run(fix_data())
