import asyncio
import logging
from datetime import datetime, timedelta, timezone
import argparse
from sqlalchemy import select, delete
from app.db.session import AsyncSessionLocal
from app.db.models import MonitoringProvider, ImportLog, Event, AuditLog

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("purge-trash")

async def purge_trash(dry_run: bool = False, days: int = 30):
    async with AsyncSessionLocal() as session:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        logger.info(f"Looking for providers deleted before {cutoff_date}")
        
        stmt = select(MonitoringProvider).where(MonitoringProvider.deleted_at < cutoff_date)
        result = await session.execute(stmt)
        providers_to_delete = result.scalars().all()
        
        if not providers_to_delete:
            logger.info("No providers found in trash ready for purge.")
            return

        for provider in providers_to_delete:
            logger.info(f"Purging provider: {provider.code} (ID: {provider.id}, deleted_at: {provider.deleted_at})")
            
            if not dry_run:
                # 1. Fetch related imports
                imports_stmt = select(ImportLog.id).where(ImportLog.provider_id == provider.id)
                imports_result = await session.execute(imports_stmt)
                import_ids = list(imports_result.scalars().all())
                
                # 2. Delete events linked to these imports
                if import_ids:
                    events_deleted = await session.execute(delete(Event).where(Event.import_id.in_(import_ids)))
                    logger.info(f"  -> Deleted events related to {len(import_ids)} imports.")
                    
                    # 3. Delete imports
                    await session.execute(delete(ImportLog).where(ImportLog.provider_id == provider.id))
                    logger.info("  -> Deleted imports.")
                
                # 4. user_providers and smtp_provider_rules are handled by ON DELETE CASCADE
                # We can now delete the provider
                await session.execute(delete(MonitoringProvider).where(MonitoringProvider.id == provider.id))
                
                # 5. Audit Log
                audit = AuditLog(user_id=1, action="PURGE_PROVIDER", target_type="PROVIDER", target_id=str(provider.id), payload={"code": provider.code})
                session.add(audit)
                
                logger.info(f"  -> Provider {provider.code} physically purged.")
        
        if not dry_run:
            await session.commit()
            logger.info("Purge commit successful.")
        else:
            logger.info("DRY RUN: No changes committed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Purge physically deleted providers from the database.")
    parser.add_argument("--dry-run", action="store_true", help="Do not commit changes to the DB")
    parser.add_argument("--days", type=int, default=30, help="Days to keep in trash")
    args = parser.parse_args()
    
    asyncio.run(purge_trash(dry_run=args.dry_run, days=args.days))
