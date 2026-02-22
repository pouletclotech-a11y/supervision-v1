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
from app.db.models import AlertRule, Event, Incident, ImportLog

async def test_step_5_alerting():
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete
        
        # 1. Cleanup
        await session.execute(delete(AlertRule).where(AlertRule.name.like("TEST_RULE_%")))
        await session.execute(delete(Incident).where(Incident.site_code == "TEST050"))
        await session.execute(delete(Event).where(Event.site_code == "TEST050"))
        await session.commit()
        
        repo = EventRepository(session)
        alert_service = AlertingService()
        
        import_log = await repo.create_import_log("test_step_5.xls")
        
        # 2. Setup Scenario 1: Sliding Window (3 in 2 days)
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        
        # Insert 2 past events
        e1 = Event(time=now - timedelta(days=1), site_code="TEST050", normalized_type="APPARITION", category="operator_check", raw_message="NVF: Test 1", import_id=import_log.id)
        e2 = Event(time=now - timedelta(hours=12), site_code="TEST050", normalized_type="APPARITION", category="operator_check", raw_message="NVF: Test 2", import_id=import_log.id)
        session.add_all([e1, e2])
        await session.commit()
        
        # Current event (3rd one)
        e3_norm = type('obj', (object,), {
            'timestamp': now, 
            'site_code': 'TEST050', 
            'normalized_type': 'APPARITION', 
            'category': 'operator_check', 
            'raw_message': 'NVF: Test 3',
            'status': 'INFO'
        })
        
        rule_v3 = AlertRule(
            name="TEST_RULE_V3",
            condition_type="KEYWORD",
            value="NVF",
            match_category="operator_check",
            sliding_window_days=2,
            frequency_count=3,
            is_active=True,
            scope_site_code="TEST050"
        )
        
        print("--- Testing Sliding Window (3 in 2 days) ---")
        res = await alert_service.evaluate_rule(e3_norm, rule_v3, repo=repo)
        for d in res["details"]: print(f"  - {d}")
        assert res["triggered"] is True
        print("✅ Sliding Window MATCH OK")
        
        # 3. Setup Scenario 2: Keyword filter
        rule_key = AlertRule(
            name="TEST_RULE_KEY",
            condition_type="SEVERITY",
            value="INFO",
            match_keyword="Porte",
            match_category="operator_check",
            sliding_window_days=1,
            frequency_count=1,
            is_active=True,
            scope_site_code="TEST050"
        )
        e_key_match = type('obj', (object,), {'timestamp': now, 'site_code': 'TEST050', 'normalized_type': 'APPARITION', 'category': 'operator_check', 'raw_message': 'Porte ouverte', 'status': 'INFO'})
        e_key_no_match = type('obj', (object,), {'timestamp': now, 'site_code': 'TEST050', 'normalized_type': 'APPARITION', 'category': 'operator_check', 'raw_message': 'Fenetre ouverte', 'status': 'INFO'})
        
        print("\n--- Testing Keyword Filter ---")
        res_ok = await alert_service.evaluate_rule(e_key_match, rule_key, repo=repo)
        assert res_ok["triggered"] is True
        print("✅ Keyword 'Porte' MATCH OK")
        
        res_no = await alert_service.evaluate_rule(e_key_no_match, rule_key, repo=repo)
        assert res_no["triggered"] is False
        print("✅ Keyword 'Porte' NO MATCH OK")

        # 4. Setup Scenario 3: Open Only
        rule_open = AlertRule(
            name="TEST_RULE_OPEN",
            condition_type="KEYWORD",
            value="Incendie",
            match_category="fire",
            is_open_only=True,
            sliding_window_days=1,
            frequency_count=1,
            is_active=True,
            scope_site_code="TEST050"
        )
        
        # Add an OPEN incident
        e_fire = Event(time=now, site_code="TEST050", normalized_type="APPARITION", category="fire", raw_message="Incendie Garage", import_id=import_log.id)
        session.add(e_fire)
        await session.flush()
        
        inc = Incident(site_code="TEST050", incident_key="fire_key", label="Incendie", opened_at=now, status="OPEN", open_event_id=e_fire.id)
        session.add(inc)
        await session.commit()
        
        e_fire_norm = type('obj', (object,), {'timestamp': now, 'site_code': 'TEST050', 'normalized_type': 'APPARITION', 'category': 'fire', 'raw_message': 'Incendie Garage', 'status': 'INFO'})
        
        print("\n--- Testing Open Only (OPEN state) ---")
        res_open = await alert_service.evaluate_rule(e_fire_norm, rule_open, repo=repo)
        assert res_open["triggered"] is True
        print("✅ Open Only (OPEN) MATCH OK")
        
        # Close the incident
        inc.status = "CLOSED"
        inc.closed_at = now + timedelta(minutes=1)
        await session.commit()
        
        print("--- Testing Open Only (CLOSED state) ---")
        # Now it shouldn't match because we ONLY count OPEN incidents
        # IMPORTANT: We provide the 'id' of the inserted event to simulate a Dry Run on historical data
        e_fire_closed = type('obj', (object,), {
            'id': e_fire.id,
            'timestamp': now, 
            'site_code': 'TEST050', 
            'normalized_type': 'APPARITION', 
            'category': 'fire', 
            'raw_message': 'Incendie Garage', 
            'status': 'INFO'
        })
        res_closed = await alert_service.evaluate_rule(e_fire_closed, rule_open, repo=repo)
        assert res_closed["triggered"] is False
        print("✅ Open Only (CLOSED) NO MATCH OK")

        print("\n✅ ALL STEP 5 TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_step_5_alerting())
