import asyncio
import sys
import argparse
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import ImportLog

async def assert_counts(filename_pattern, expected_count):
    print(f"Asserting counts for filename matching: {filename_pattern}")
    async with AsyncSessionLocal() as db:
        # Get the latest import for this pattern
        stmt = (
            select(ImportLog)
            .where(ImportLog.filename.ilike(f"%{filename_pattern}%"))
            .order_by(ImportLog.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        imp = result.scalar_one_or_none()
        
        if not imp:
            print(f"ERROR: No import found matching {filename_pattern}")
            return False
            
        print(f"Found Import ID {imp.id} ({imp.filename}) status: {imp.status}")
        
        # 1. Check Events Count
        if imp.events_count != expected_count:
            print(f"FAILURE: Expected {expected_count} events, got {imp.events_count}")
            return False
            
        # 2. Check Reports Presence
        if not imp.quality_report or not isinstance(imp.quality_report, dict):
            print(f"FAILURE: Missing or invalid quality_report for {imp.id}")
            return False
            
        print(f"SUCCESS: Import {imp.id} validated (Events: {imp.events_count}, Reports: OK)")
        return True

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--filename", required=True)
    parser.add_argument("--expected", type=int, required=True)
    args = parser.parse_args()
    
    success = await assert_counts(args.filename, args.expected)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
