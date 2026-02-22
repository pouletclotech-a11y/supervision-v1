import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal
from app.services.repository import EventRepository
from app.services.incident_service import IncidentService
from app.ingestion.models import NormalizedEvent

async def test_step_3_incidents():
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete, select, func
        from app.db.models import Incident, Event
        
        # Cleanup
        await session.execute(delete(Incident).where(Incident.site_code.like("TEST00%")))
        await session.execute(delete(Event).where(Event.site_code.like("TEST00%")))
        await session.commit()
        
        repo = EventRepository(session)
        service = IncidentService(session)
        
        # 1. Create a dummy import log
        import_log = await repo.create_import_log("test_incidents.xls")
        print(f"Created Import #{import_log.id}")
        
        # 2. Mock Events for Test Case 1: APPARITION + DISPARITION (Closed)
        t0 = datetime.utcnow()
        e1 = NormalizedEvent(
            timestamp=t0,
            site_code="TEST001",
            event_type="APPARITION",
            raw_message="Pression Basse Cam 1",
            source_file="test.xls",
            raw_data='["TEST001", "LUN", "...", "APPARITION", "", "Pression Basse Cam 1"]'
        )
        e2 = NormalizedEvent(
            timestamp=t0 + timedelta(minutes=5),
            site_code="TEST001",
            event_type="DISPARITION",
            raw_message="Pression Basse Cam 1",
            source_file="test.xls",
            raw_data='["TEST001", "LUN", "...", "DISPARITION", "", "Pression Basse Cam 1"]'
        )
        
        # 3. Mock Events for Test Case 2: APPARITION alone (Open)
        e3 = NormalizedEvent(
            timestamp=t0 + timedelta(hours=1),
            site_code="TEST002",
            event_type="APPARITION",
            raw_message="Intrusion Secteur Nord",
            source_file="test.xls",
            raw_data='["TEST002", "LUN", "...", "APPARITION", "", "Intrusion Secteur Nord"]'
        )
        
        # 4. Mock Events for Test Case 3: DISPARITION alone (Orphan)
        e4 = NormalizedEvent(
            timestamp=t0 + timedelta(hours=2),
            site_code="TEST003",
            event_type="DISPARITION",
            raw_message="Feu Garage",
            source_file="test.xls",
            raw_data='["TEST003", "LUN", "...", "DISPARITION", "", "Feu Garage"]'
        )
        
        # Insert them
        await repo.create_batch([e1, e2, e3, e4], import_id=import_log.id)
        await session.commit()
        print("Events inserted and committed.")
        
        # 5. Process Incidents
        unmatched = await service.process_batch_incidents(import_log.id)
        await session.commit()
        print(f"Incident reconstruction done. Unmatched: {unmatched}")
        
        # 6. Verification
        from app.db.models import Incident
        from sqlalchemy import select
        
        # Test Case 1: CLOSED incident
        key1 = service.generate_incident_key("TEST001", "Pression Basse Cam 1")
        stmt1 = select(Incident).where(Incident.site_code == "TEST001").where(Incident.incident_key == key1)
        inc1 = (await session.execute(stmt1)).scalar_one()
        print(f"Incident 1: Status={inc1.status}, Duration={inc1.duration_seconds}s")
        assert inc1.status == "CLOSED"
        assert inc1.duration_seconds == 300
        
        # Test Case 2: OPEN incident
        key2 = service.generate_incident_key("TEST002", "Intrusion Secteur Nord")
        stmt2 = select(Incident).where(Incident.site_code == "TEST002").where(Incident.incident_key == key2)
        inc2 = (await session.execute(stmt2)).scalar_one()
        print(f"Incident 2: Status={inc2.status}, OpenedAt={inc2.opened_at}")
        assert inc2.status == "OPEN"
        assert inc1.closed_at is not None
        assert inc2.closed_at is None
        
        # Test Case 3: Orphan DISPARITION
        key3 = service.generate_incident_key("TEST003", "Feu Garage")
        stmt3 = select(Incident).where(Incident.site_code == "TEST003").where(Incident.incident_key == key3)
        inc3 = (await session.execute(stmt3)).scalar_one_or_none()
        print(f"Incident 3 (Orphan): Found={inc3 is not None}")
        assert inc3 is None
        assert unmatched == 1
        
        # 7. Idempotence Check
        print("Running reconstruction again for same import...")
        unmatched_again = await service.process_batch_incidents(import_log.id)
        await session.commit()
        print(f"Re-run unmatched: {unmatched_again}")
        
        # Count total incidents for this import (should be same)
        stmt_count = select(func.count(Incident.id)).where(Incident.site_code.in_(["TEST001", "TEST002"]))
        count = (await session.execute(stmt_count)).scalar()
        print(f"Total incidents after rerun: {count}")
        assert count == 2
        
        print("✅ ALL STEP 3 TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_step_3_incidents())
