import asyncio
import logging
from app.db.session import AsyncSessionLocal
from app.db.models import Event
from app.ingestion.models import NormalizedEvent
from app.services.repository import EventRepository
from app.services.alerting import AlertingService
from sqlalchemy import select

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("replay-alerts")

async def replay_alerts():
    print("Starting Alert Replay on Historical Data...")
    
    async with AsyncSessionLocal() as session:
        repo = EventRepository(session)
        service = AlertingService()

        # 1. Fetch Active Rules
        rules = await repo.get_active_rules()
        print(f"Loaded {len(rules)} active rules.")
        for r in rules:
            print(f" - Rule: {r.name} (Scope: {r.time_scope or 'All Time'}, Freq: {r.frequency_count}/{r.frequency_window}s)")

        # 2. Fetch All Events
        print("Fetching events from DB...")
        stmt = select(Event).order_by(Event.time.asc())
        result = await session.execute(stmt)
        events = result.scalars().all()
        print(f"Loaded {len(events)} events.")

        # 3. Process
        triggers = {}
        updates_count = 0
        
        for e in events:
            # Map ORM -> Normalized (Duck Typing or Explicit)
            norm_event = NormalizedEvent(
                timestamp=e.time,
                site_code=e.site_code or "UNKNOWN",
                secondary_code=None,
                client_name=e.client_name,
                weekday_label=e.weekday_label,
                event_type=e.normalized_type or "UNKNOWN",
                normalized_type=e.normalized_type,
                sub_type=e.sub_type,
                raw_message=e.raw_message or "",
                raw_code=e.raw_code,
                status=e.severity or "INFO",
                zone_label=e.zone_label,
                metadata=e.event_metadata,
                source_file=e.source_file or "REPLAY"
            )

            # Check Alerts
            # AlertingService modifies norm_event.status to 'CRITICAL' if triggered
            # We capture logs via logger, but here we check status change
            initial_status = norm_event.status
            
            # We must pass 'repo' to allow frequency checks (that query DB)
            await service.check_and_trigger_alerts(norm_event, rules, repo=repo)
            
            if norm_event.status == 'CRITICAL' and initial_status != 'CRITICAL':
                # Triggered!
                updates_count += 1
                rule_name = "Unknown" # Service doesn't return rule name easily yet without logs capture
                # But we can infer valid alert.
                
                # Update DB Object
                e.severity = 'CRITICAL'
                # Log Summary
                # print(f"ALERT: Site {e.site_code} | Msg: {e.raw_message}")
                
        # 4. Commit Changes
        if updates_count > 0:
            print(f"Updating {updates_count} events to CRITICAL severity in DB...")
            await session.commit()
        else:
            print("No new alerts triggered.")
            
    print("Replay Complete.")

if __name__ == "__main__":
    asyncio.run(replay_alerts())
