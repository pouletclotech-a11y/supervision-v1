import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal
from app.services.repository import EventRepository
from app.services.tagging_service import TaggingService
from app.services.incident_service import IncidentService
from app.ingestion.models import NormalizedEvent

async def test_step_4_catalog_and_tagging():
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete, select, func
        from app.db.models import Incident, Event, EventCodeCatalog
        
        # Cleanup
        await session.execute(delete(Incident).where(Incident.site_code.like("TEST04%")))
        await session.execute(delete(Event).where(Event.site_code.like("TEST04%")))
        await session.commit()
        
        repo = EventRepository(session)
        tagger = TaggingService(session)
        inc_service = IncidentService(session)
        
        # 1. Create a dummy import log
        import_log = await repo.create_import_log("test_step_4.xls")
        print(f"Created Import #{import_log.id}")
        
        # 2. Mock Events for Tagging
        e1 = NormalizedEvent(
            timestamp=datetime.utcnow(),
            site_code="TEST041",
            event_type="APPARITION",
            raw_message="NVF: Porte non fermée",
            source_file="test.xls"
        )
        e2 = NormalizedEvent(
            timestamp=datetime.utcnow(),
            site_code="TEST041",
            event_type="APPARITION",
            raw_message="Intrusion Cam 1",
            source_file="test.xls"
        )
        e3 = NormalizedEvent(
            timestamp=datetime.utcnow(),
            site_code="TEST041",
            event_type="APPARITION",
            raw_message="Pression Pneu 3.0", # Unknown
            source_file="test.xls"
        )
        
        # 3. Tagging Verification
        print("Taggings events...")
        await tagger.tag_event(e1)
        await tagger.tag_event(e2)
        await tagger.tag_event(e3)
        
        print(f"E1 (NVF) -> Category: {e1.category}, Alertable: {e1.alertable_default}")
        assert e1.category == "operator_check"
        assert e1.alertable_default is False
        
        print(f"E2 (CAM1) -> Category: {e2.category}")
        assert e2.category == "camera"
        
        print(f"E3 (Unknown) -> Category: {e3.category}")
        assert e3.category == "unknown"
        
        # 4. Persistence and Incident Non-regression
        t_inc = datetime.utcnow()
        e_open = NormalizedEvent(
            timestamp=t_inc,
            site_code="TEST042",
            event_type="APPARITION",
            normalized_type="APPARITION", # Explicit for pairing
            raw_message="Incendie Garage",
            source_file="test.xls"
        )
        e_close = NormalizedEvent(
            timestamp=t_inc + timedelta(minutes=10),
            site_code="TEST042",
            event_type="DISPARITION",
            normalized_type="DISPARITION",
            raw_message="Incendie Garage",
            source_file="test.xls"
        )
        
        await tagger.tag_event(e_open)
        await tagger.tag_event(e_close)
        
        # Insert batch
        await repo.create_batch([e1, e2, e3, e_open, e_close], import_id=import_log.id)
        await session.commit()
        
        # Process Incidents (Step 3 logic check)
        print("Running Incident Reconstruction...")
        await inc_service.process_batch_incidents(import_log.id)
        await session.commit()
        
        # Verify Incident
        key = inc_service.generate_incident_key("TEST042", "Incendie Garage")
        stmt = select(Incident).where(Incident.site_code == "TEST042").where(Incident.incident_key == key)
        inc = (await session.execute(stmt)).scalar_one()
        print(f"Incident check: Status={inc.status}, Duration={inc.duration_seconds}s")
        assert inc.status == "CLOSED"
        assert inc.duration_seconds == 600
        
        print("✅ ALL STEP 4 TESTS PASSED (Catalog + Tagging + Step 3 compatibility)")

if __name__ == "__main__":
    asyncio.run(test_step_4_catalog_and_tagging())
