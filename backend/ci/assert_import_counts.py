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
        q_report = imp.quality_report or {}
        if not q_report or not isinstance(q_report, dict):
            print(f"FAILURE: Missing or invalid quality_report for {imp.id}")
            return False
            
        # 3. Quality Ratios Assertions
        rows_detected = q_report.get("rows_detected", 0)
        events_created = imp.events_count
        missing_action = q_report.get("missing_action_count", 0)
        with_code = q_report.get("with_code_count", 0)
        
        # In our parser, events_created ARE events with time.
        # So created_ratio is the with_time_ratio.
        created_ratio = events_created / rows_detected if rows_detected > 0 else 1.0
        with_action_ratio = (events_created - missing_action) / events_created if events_created > 0 else 1.0
        with_code_ratio = with_code / events_created if events_created > 0 else 0.0
        
        print(f"Quality Metrics: created_ratio={created_ratio:.2f}, action_ratio={with_action_ratio:.2f}, code_ratio={with_code_ratio:.2f}")
        
        # Thresholds
        min_created = 0.4 if "SPGO" in filename_pattern else 0.7
        
        if created_ratio < min_created:
            print(f"FAILURE: created_ratio {created_ratio:.2f} < {min_created}")
            return False
            
        if with_action_ratio < 0.9: # Strict on Goldens
            print(f"FAILURE: with_action_ratio {with_action_ratio:.2f} < 0.9")
            return False
            
        if with_code_ratio < 0.5:
            if "CORS" in filename_pattern:
                print(f"INFO: with_code_ratio {with_code_ratio:.2f} is low but expected for CORS Excel (INFO ONLY)")
            else:
                print(f"FAILURE: with_code_ratio {with_code_ratio:.2f} < 0.5")
                return False

        print(f"SUCCESS: Import {imp.id} validated (Events: {imp.events_count}, Quality: OK)")
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
