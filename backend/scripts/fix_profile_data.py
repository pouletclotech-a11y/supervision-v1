import asyncio
import argparse
import sys
import json
from pathlib import Path
from app.db.session import AsyncSessionLocal
from app.db.models import DBIngestionProfile
from sqlalchemy import select

async def fix_profile_data(apply: bool = False):
    print(f"--- PROFILE DATA CLEANUP START (apply={apply}) ---")
    
    async with AsyncSessionLocal() as session:
        stmt = select(DBIngestionProfile)
        result = await session.execute(stmt)
        profiles = result.scalars().all()
        
        backup_data = []
        changes_detected = 0
        
        for profile in profiles:
            needs_update = False
            original_data = {
                "id": profile.id,
                "profile_id": profile.profile_id,
                "extraction_rules": profile.extraction_rules,
                "normalization": profile.normalization
            }
            
            # Check extraction_rules (should be a dict)
            if profile.extraction_rules is None or isinstance(profile.extraction_rules, list):
                print(f"[{profile.profile_id}] extraction_rules is {type(profile.extraction_rules).__name__}, coercing to {{}}")
                profile.extraction_rules = {}
                needs_update = True
                
            # Check normalization (should be a dict)
            if profile.normalization is None or isinstance(profile.normalization, list):
                print(f"[{profile.profile_id}] normalization is {type(profile.normalization).__name__}, coercing to {{}}")
                profile.normalization = {}
                needs_update = True
                
            if needs_update:
                changes_detected += 1
                new_data = {
                    "id": profile.id,
                    "profile_id": profile.profile_id,
                    "extraction_rules": profile.extraction_rules,
                    "normalization": profile.normalization
                }
                backup_data.append({"id": profile.id, "before": original_data, "after": new_data})
                session.add(profile)

        if changes_detected > 0:
            # Export backup
            backup_file = Path("profile_fix_backup.json")
            try:
                with backup_file.open("w") as f:
                    json.dump(backup_data, f, indent=2, default=str)
                print(f"Backup exported to {backup_file.absolute()}")
            except Exception as be:
                print(f"Warning: Could not write backup file: {be}")
            
            if apply:
                print(f"Applying {changes_detected} changes...")
                await session.commit()
                print("Commit successful.")
            else:
                print(f"Dry run: {changes_detected} changes detected but not applied. Use --apply to save.")
        else:
            print("No inconsistent data detected.")

    print("--- PROFILE DATA CLEANUP DONE ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix inconsistent JSONB data in ingestion_profiles.")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the database")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(fix_profile_data(args.apply))
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
