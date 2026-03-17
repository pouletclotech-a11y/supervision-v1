import asyncio
import logging
from datetime import datetime, timedelta, timezone
import argparse
from sqlalchemy import select, delete
from app.db.session import AsyncSessionLocal
from app.db.models import MonitoringProvider, ImportLog, Event, AuditLog

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("purge-trash")

async def purge_trash(confirm: bool = False, days: int = 30):
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
            
            if confirm:
                # 1. Fetch related imports
                imports_stmt = select(ImportLog.id).where(ImportLog.provider_id == provider.id)
                imports_result = await session.execute(imports_stmt)
                import_ids = list(imports_result.scalars().all())
                
                # 2. Delete Events and their dependencies
                if import_ids:
                    # Retrieve all event_ids for cascading
                    events_stmt = select(Event.id).where(Event.import_id.in_(import_ids))
                    events_result = await session.execute(events_stmt)
                    event_ids = list(events_result.scalars().all())
                    
                    if event_ids:
                        from app.db.models import EventRuleHit, Incident, SiteConnection
                        # Cascade: Delete EventRuleHits
                        hit_del = await session.execute(delete(EventRuleHit).where(EventRuleHit.event_id.in_(event_ids)))
                        logger.info(f"  -> Deleted {hit_del.rowcount} EventRuleHits.")
                        
                        # Cascade: Delete Incidents
                        inc_del = await session.execute(delete(Incident).where(
                            (Incident.open_event_id.in_(event_ids)) | (Incident.close_event_id.in_(event_ids))
                        ))
                        logger.info(f"  -> Deleted {inc_del.rowcount} Incidents.")
                        
                        # Finally: Delete Events
                        evt_del = await session.execute(delete(Event).where(Event.id.in_(event_ids)))
                        logger.info(f"  -> Deleted {evt_del.rowcount} Events.")
                    
                    # 3. Delete imports
                    imp_del = await session.execute(delete(ImportLog).where(ImportLog.provider_id == provider.id))
                    logger.info(f"  -> Deleted {imp_del.rowcount} Imports.")
                
                # 4. Cascade: Site Connections
                from app.db.models import SiteConnection
                conn_del = await session.execute(delete(SiteConnection).where(SiteConnection.provider_id == provider.id))
                logger.info(f"  -> Deleted {conn_del.rowcount} Site Connections.")
                
                # 5. user_providers and smtp_provider_rules are handled by ON DELETE CASCADE
                # We can now delete the provider
                await session.execute(delete(MonitoringProvider).where(MonitoringProvider.id == provider.id))
                
                # 6. Audit Log
                audit = AuditLog(user_id=1, action="PURGE_PROVIDER", target_type="PROVIDER", target_id=str(provider.id), payload={"code": provider.code})
                session.add(audit)
                
                logger.info(f"  -> Provider {provider.code} physically purged.")
        
        if confirm:
            await session.commit()
            logger.info("Purge commit successful.")
        else:
            logger.info("DRY RUN: No changes committed. Use --confirm to execute.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Purge physically deleted providers from the database.")
    parser.add_argument("--confirm", action="store_true", help="Confirm execution and commit changes to DB. Without this, runs as dry-run.")
    parser.add_argument("--days", type=int, default=30, help="Days to keep in trash")
    args = parser.parse_args()
    
    asyncio.run(purge_trash(confirm=args.confirm, days=args.days))
