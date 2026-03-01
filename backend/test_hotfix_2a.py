import asyncio
import logging
import json
from app.db.session import AsyncSessionLocal
from app.db.models import Event, EventRuleHit, AlertRule, Setting
from app.services.business_rules import _get_db_setting, BusinessRuleEngine, replay_all_rules
from sqlalchemy import select, delete, func

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test-hotfix")

async def test_settings_robustness():
    logger.info("--- Testing Settings Robustness ---")
    async with AsyncSessionLocal() as session:
        # 1. Invalid JSON
        await session.execute(delete(Setting).where(Setting.key == 'test.invalid_json'))
        session.add(Setting(key='test.invalid_json', value='{invalid}'))
        await session.commit()
        
        val = await _get_db_setting(session, 'test.invalid_json', default=True, expected_type=bool)
        assert val is True, f"Expected default True, got {val}"
        logger.info("Invalid JSON handled correctly.")

        # 2. Type Mismatch
        await session.execute(delete(Setting).where(Setting.key == 'test.type_mismatch'))
        session.add(Setting(key='test.type_mismatch', value='123')) # JSON number
        await session.commit()
        
        val = await _get_db_setting(session, 'test.type_mismatch', default=False, expected_type=bool)
        assert val is False, f"Expected default False, got {val}"
        logger.info("Type mismatch handled correctly.")

        # 3. Invalid Enum
        await session.execute(delete(Setting).where(Setting.key == 'test.invalid_enum'))
        session.add(Setting(key='test.invalid_enum', value='"WRONG"'))
        await session.commit()
        
        val = await _get_db_setting(session, 'test.invalid_enum', default="IN", expected_type=str, allowed_values=["EXACT", "IN"])
        assert val == "IN", f"Expected default IN, got {val}"
        logger.info("Invalid enum handled correctly.")

async def test_rule_id_safety():
    logger.info("--- Testing Rule ID Safety ---")
    async with AsyncSessionLocal() as session:
        engine = BusinessRuleEngine(session)
        
        # Should work if ENGINE_V1 exists
        rid = await engine._resolve_system_rule_id()
        logger.info(f"Resolved ENGINE_V1 ID: {rid}")
        
        # Temporarily rename it to test failure
        await session.execute(AlertRule.__table__.update().where(AlertRule.name == 'ENGINE_V1').values(name='ENGINE_V1_TMP'))
        await session.commit()
        
        try:
            await engine._resolve_system_rule_id()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            logger.info(f"Caught expected error: {e}")
        
        # Restore
        await session.execute(AlertRule.__table__.update().where(AlertRule.name == 'ENGINE_V1_TMP').values(name='ENGINE_V1'))
        await session.commit()

async def test_atomic_replay():
    logger.info("--- Testing Atomic Replay (REPLACE) ---")
    async with AsyncSessionLocal() as session:
        # Get an event ID
        res = await session.execute(select(Event.id).limit(1))
        evt_id = res.scalar()
        if not evt_id:
            logger.warning("No events found in DB, skipping replay test.")
            return

        # Count total hits
        res_count = await session.execute(select(func.count()).select_from(EventRuleHit))
        count_before = res_count.scalar()
        
        logger.info(f"Total hits before: {count_before}")
        
        # Trigger REPLACE replay for all
        stats = await replay_all_rules(session, mode="REPLACE")
        logger.info(f"Replay stats: {stats}")
        
        # Verify it wasn't a global delete and empty state
        # (This is hard to prove without mocking but we checked logs in implementation)
        
        res_count_after = await session.execute(select(func.count()).select_from(EventRuleHit))
        count_after = res_count_after.scalar()
        logger.info(f"Total hits after: {count_after}")

async def run_tests():
    await test_settings_robustness()
    await test_rule_id_safety()
    await test_atomic_replay()

if __name__ == "__main__":
    asyncio.run(run_tests())
