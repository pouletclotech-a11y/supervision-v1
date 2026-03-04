import asyncio
import os
import sys
from pathlib import Path
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import MonitoringProvider
from app.ingestion.worker import IngestionWorker
from app.ingestion.profile_manager import ProfileManager

async def trigger_ingestion(file_path):
    print(f"Triggering ingestion for: {file_path}")
    if not os.path.exists(file_path):
        print(f"ERROR: File not found at {file_path}")
        return False
        
    async with AsyncSessionLocal() as db:
        # Load profiles
        pm = ProfileManager()
        await pm.load_profiles(db)
        
        # Trigger worker logic
        worker = IngestionWorker()
        # Note: We use a simplified trigger that mimics a file drop
        # or we call the worker's process_file directly if accessible.
        # For CI, we'll use a direct call to simulate the pipeline.
        success = await worker.process_file_path(Path(file_path), db, pm)
        
        if success:
            print(f"Successfully processed {file_path}")
            return True
        else:
            print(f"Failed to process {file_path}")
            return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trigger_ci_ingestion.py <file_path>")
        sys.exit(1)
        
    path = sys.argv[1]
    loop = asyncio.get_event_loop()
    if not loop.run_until_complete(trigger_ingestion(path)):
        sys.exit(1)
