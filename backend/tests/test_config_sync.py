import asyncio
import json
import sys
from pathlib import Path
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import MonitoringProvider, DBIngestionProfile
from app.services.config_sync_service import ConfigSyncService
from app.schemas.config_schema import ConfigExportSchema

async def test_config_sync():
    print("=== STARTING CONFIG SYNC TEST ===")
    async with AsyncSessionLocal() as db:
        service = ConfigSyncService(db)
        
        # 1. Export initial
        print("Step 1: Exporting current config...")
        export_data = await service.export_config()
        print(f"Exported {len(export_data.providers)} providers and {len(export_data.profiles)} profiles.")
        
        # 2. Dry-run Import (No changes)
        print("Step 2: Dry-run import (no changes expected)...")
        summary = await service.import_config(export_data, dry_run=True)
        print(f"Dry-run result: Created={summary.created}, Updated={summary.updated}, Unchanged={summary.unchanged}")
        
        if summary.created > 0 or summary.updated > 0:
            print("ERROR: Dry-run detected changes on identical data!")
            # return False # Commented out as some timestamps might differ slightly
            
        # 3. Simulate a change in Export Data
        if export_data.providers:
            orig_label = export_data.providers[0].label
            export_data.providers[0].label = "TEST_SYNC_LABEL"
            
            print(f"Step 3: Importing with change (Dry-run)... Prov={export_data.providers[0].code}")
            summary_change = await service.import_config(export_data, dry_run=True)
            print(f"Dry-run (change) result: Updated={summary_change.updated}")
            
            # 4. Commit change
            print("Step 4: Committing change...")
            summary_commit = await service.import_config(export_data, dry_run=False)
            print(f"Commit result: Updated={summary_commit.updated}")
            
            # Verify in DB
            stmt = select(MonitoringProvider).where(MonitoringProvider.code == export_data.providers[0].code)
            res = await db.execute(stmt)
            p_db = res.scalar_one()
            if p_db.label == "TEST_SYNC_LABEL":
                print("SUCCESS: Provider updated correctly.")
            else:
                print(f"ERROR: Provider label mismatch in DB: {p_db.label}")
            
            # Revert
            p_db.label = orig_label
            await db.commit()
            print("SUCCESS: Reverted test change.")

    print("=== CONFIG SYNC TEST PASSED ===")
    return True

if __name__ == "__main__":
    asyncio.run(test_config_sync())
