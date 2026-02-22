import asyncio
import os
import sys
from datetime import datetime
import json
import pytz

# Add backend to path
sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal
from app.services.repository import EventRepository
from app.services.alerting import AlertingService
from app.db.models import AlertRule, Event, RuleCondition

async def test_step_7_logic():
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete
        
        # 1. Cleanup
        await session.execute(delete(AlertRule).where(AlertRule.name.like("TEST_LOGIC_%")))
        await session.execute(delete(RuleCondition).where(RuleCondition.code.like("cond_%")))
        await session.execute(delete(Event).where(Event.site_code == "TEST070"))
        await session.commit()
        
        repo = EventRepository(session)
        alert_service = AlertingService()
        
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        
        # 2. Setup Conditions
        c1 = RuleCondition(code="cond_a", label="Keyword A", type="SIMPLE_V3", payload={"match_keyword": "Pomme"})
        c2 = RuleCondition(code="cond_b", label="Keyword B", type="SIMPLE_V3", payload={"match_keyword": "Poire"})
        c3 = RuleCondition(code="cond_c", label="Keyword C", type="SIMPLE_V3", payload={"match_keyword": "Banane"})
        session.add_all([c1, c2, c3])
        await session.commit()
        
        # 3. Scenario 1: AND(A, B) -> MATCH
        # Event with both keywords
        e_ab = type('obj', (object,), {
            'timestamp': now, 'site_code': 'TEST070', 
            'normalized_type': 'APPARITION', 'category': 'test', 
            'raw_message': 'Pomme et Poire', 'status': 'INFO'
        })
        rule_and = AlertRule(
            name="TEST_LOGIC_AND",
            logic_enabled=True,
            logic_tree={"op": "AND", "children": [{"ref": "cond:cond_a"}, {"ref": "cond:cond_b"}]},
            is_active=True,
            scope_site_code="TEST070"
        )
        
        print("--- Testing AND(A, B) MATCH ---")
        res_and = await alert_service.evaluate_rule(e_ab, rule_and, repo=repo)
        assert res_and["triggered"] is True
        print("✅ AND(A, B) MATCH OK")
        
        # 4. Scenario 2: OR(A, B) -> NO MATCH (neither)
        # Event with none
        e_none = type('obj', (object,), {
            'timestamp': now, 'site_code': 'TEST070', 
            'normalized_type': 'APPARITION', 'category': 'test', 
            'raw_message': 'Orange', 'status': 'INFO'
        })
        print("\n--- Testing OR(A, B) NO MATCH ---")
        rule_or = AlertRule(
            name="TEST_LOGIC_OR",
            logic_enabled=True,
            logic_tree={"op": "OR", "children": [{"ref": "cond:cond_a"}, {"ref": "cond:cond_b"}]},
            is_active=True,
            scope_site_code="TEST070"
        )
        res_or = await alert_service.evaluate_rule(e_none, rule_or, repo=repo)
        assert res_or["triggered"] is False
        print("✅ OR(A, B) NO MATCH OK")

        # 5. Scenario 3: Short-circuiting AND (A=False -> B skipped)
        print("\n--- Testing AND Short-circuit (1st False) ---")
        res_sc = await alert_service.evaluate_rule(e_none, rule_and, repo=repo)
        assert res_sc["triggered"] is False
        # Check skipped in tree
        last_child = res_sc["logic_tree_eval"]["children"][1]
        assert last_child.get("skipped") is True
        print("✅ AND Short-circuit OK (2nd node skipped)")

        # 6. Scenario 4: Nested A OR (B AND C)
        # Event has B and C but not A
        e_bc = type('obj', (object,), {
            'timestamp': now, 'site_code': 'TEST070', 
            'normalized_type': 'APPARITION', 'category': 'test', 
            'raw_message': 'Poire et Banane', 'status': 'INFO'
        })
        rule_nested = AlertRule(
            name="TEST_LOGIC_NESTED",
            logic_enabled=True,
            logic_tree={
                "op": "OR",
                "children": [
                    {"ref": "cond:cond_a"},
                    {
                        "op": "AND",
                        "children": [{"ref": "cond:cond_b"}, {"ref": "cond:cond_c"}]
                    }
                ]
            },
            is_active=True,
            scope_site_code="TEST070"
        )
        print("\n--- Testing Nested A OR (B AND C) MATCH ---")
        res_nest = await alert_service.evaluate_rule(e_bc, rule_nested, repo=repo)
        assert res_nest["triggered"] is True
        print("✅ Nested MATCH OK")
        
        # Dry Run display test
        print("\n--- Dry Run Tree Sample ---")
        print(json.dumps(res_nest["logic_tree_eval"], indent=2))

        print("\n✅ ALL STEP 7 TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_step_7_logic())
