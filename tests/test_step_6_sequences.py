import asyncio
import os
import sys
from datetime import datetime, timedelta
import pytz

# Add backend to path
sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal
from app.services.repository import EventRepository
from app.services.alerting import AlertingService
from app.db.models import AlertRule, Event, ImportLog

async def test_step_6_sequences():
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete
        
        # 1. Cleanup
        await session.execute(delete(AlertRule).where(AlertRule.name.like("TEST_SEQ_%")))
        await session.execute(delete(Event).where(Event.site_code == "TEST060"))
        await session.commit()
        
        repo = EventRepository(session)
        alert_service = AlertingService()
        import_log = await repo.create_import_log("test_step_6.xls")
        
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        
        # 2. Setup Scenario 1: MATCH (A + B in 300s)
        # A at T, B at T + 180s (3 min)
        t_a = now - timedelta(hours=1)
        t_b = t_a + timedelta(seconds=180)
        
        e_a = Event(time=t_a, site_code="TEST060", normalized_type="APPARITION", category="armement", raw_message="Mise en service", import_id=import_log.id)
        e_b = Event(time=t_b, site_code="TEST060", normalized_type="APPARITION", category="intrusion", raw_message="Intrusion zone 1", import_id=import_log.id)
        session.add_all([e_a, e_b])
        await session.commit()
        
        rule_seq = AlertRule(
            name="TEST_SEQ_MATCH",
            sequence_enabled=True,
            seq_a_category="armement",
            seq_b_category="intrusion",
            seq_max_delay_seconds=300,
            seq_lookback_days=1,
            is_active=True,
            scope_site_code="TEST060"
        )
        
        # Current event is the one reaching the engine (B in this case)
        e_trigger = type('obj', (object,), {'id': e_b.id, 'timestamp': now, 'site_code': 'TEST060', 'normalized_type': 'APPARITION', 'category': 'intrusion', 'raw_message': 'Intrusion zone 1', 'status': 'INFO'})
        
        print("--- Testing Sequence MATCH (A -> B in 180s, max 300s) ---")
        res = await alert_service.evaluate_rule(e_trigger, rule_seq, repo=repo)
        for d in res["details"]: print(f"  - {d}")
        assert res["triggered"] is True
        print("✅ Sequence MATCH OK")
        
        # 3. Setup Scenario 2: NO MATCH (Delay exceeded)
        # B at T + 400s
        t_b_late = t_a + timedelta(seconds=400)
        await session.execute(delete(Event).where(Event.id == e_b.id)) # Remove previous B
        e_b_late = Event(time=t_b_late, site_code="TEST060", normalized_type="APPARITION", category="intrusion", raw_message="Intrusion Tardive", import_id=import_log.id)
        session.add(e_b_late)
        await session.commit()
        
        e_trigger_late = type('obj', (object,), {'id': e_b_late.id, 'timestamp': now, 'site_code': 'TEST060', 'normalized_type': 'APPARITION', 'category': 'intrusion', 'raw_message': 'Intrusion Tardive', 'status': 'INFO'})
        
        print("\n--- Testing Sequence NO MATCH (Delay 400s > 300s) ---")
        res_late = await alert_service.evaluate_rule(e_trigger_late, rule_seq, repo=repo)
        for d in res_late["details"]: print(f"  - {d}")
        assert res_late["triggered"] is False
        print("✅ Sequence DELAY NO MATCH OK")

        # 4. Setup Scenario 3: NO MATCH (Category mismatch)
        rule_seq_cat = AlertRule(
            name="TEST_SEQ_CAT",
            sequence_enabled=True,
            seq_a_category="fire", # Wrong A category
            seq_b_category="intrusion",
            seq_max_delay_seconds=300,
            seq_lookback_days=1,
            is_active=True,
            scope_site_code="TEST060"
        )
        print("\n--- Testing Sequence NO MATCH (Category mismatch) ---")
        res_cat = await alert_service.evaluate_rule(e_trigger, rule_seq_cat, repo=repo)
        assert res_cat["triggered"] is False
        print("✅ Sequence CATEGORY NO MATCH OK")

        print("\n✅ ALL STEP 6 TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_step_6_sequences())
