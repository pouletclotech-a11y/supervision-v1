import asyncio
import logging
import json
from datetime import datetime
from app.db.session import AsyncSessionLocal
from app.db.models import Event, EventRuleHit, AlertRule, Setting
from app.services.business_rules import BusinessRuleEngine, replay_all_rules, _get_db_setting
from sqlalchemy import select, delete, func, update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test-scoring")

async def setup_test_rules():
    async with AsyncSessionLocal() as session:
        # Update existing test rules with some weights
        await session.execute(update(AlertRule).where(AlertRule.name == 'TEST_RAW_EXACT').values(
            logic_tree={"raw_code": "01401-MHS", "raw_code_mode": "EXACT", "weight": 0.5}
        ))
        await session.execute(update(AlertRule).where(AlertRule.name == 'TEST_RAW_IN').values(
            logic_tree={"raw_codes": ["0600", "0911", "344"], "raw_code_mode": "IN", "weight": 1.2, "score_threshold": 0.2}
        ))
        await session.commit()
        logger.info("Test rules updated with weights.")

async def clear_settings():
    async with AsyncSessionLocal() as session:
        keys = [
            'monitoring.rules.scoring_enabled',
            'monitoring.rules.score_threshold_default',
            'monitoring.rules.score_default_weight',
            'monitoring.rules.score_normalization',
            'monitoring.rules.scoring_record_below_threshold'
        ]
        await session.execute(delete(Setting).where(Setting.key.in_(keys)))
        await session.commit()
        logger.info("Settings cleared (reset to YAML defaults).")

async def test_case_off():
    logger.info("--- TEST A: Scoring OFF (Default) ---")
    async with AsyncSessionLocal() as session:
        # 1. Clear hits
        await session.execute(delete(EventRuleHit))
        await session.commit()
        
        # 2. Run replay 
        await replay_all_rules(session, mode="REPLACE", batch_size=1000)
        
        # 3. Verify
        res_count = await session.execute(select(func.count()).select_from(EventRuleHit))
        count = res_count.scalar()
        
        res_score = await session.execute(select(func.count()).select_from(EventRuleHit).where(EventRuleHit.score.isnot(None)))
        score_count = res_score.scalar()
        
        logger.info(f"Hits count (OFF): {count}")
        logger.info(f"Hits with score (OFF): {score_count}")
        assert score_count == 0, "Score should be NULL when scoring is OFF"
        return count

async def test_case_on():
    logger.info("--- TEST B: Scoring ON (Threshold 0.8) ---")
    async with AsyncSessionLocal() as session:
        # Enable scoring globally
        session.add(Setting(key='monitoring.rules.scoring_enabled', value='true'))
        session.add(Setting(key='monitoring.rules.score_threshold_default', value='0.8'))
        session.add(Setting(key='monitoring.rules.score_normalization', value='1.0'))
        await session.commit()
        
        # Replay
        await replay_all_rules(session, mode="REPLACE", batch_size=1000)
        
        # Verify
        # Rule TEST_RAW_EXACT has weight 0.5 -> score 0.5 / 1.0 = 0.5. Since 0.5 < 0.8, should be SKIPPED.
        # Rule TEST_RAW_IN has weight 1.2 and threshold 0.2 -> score 1.2. Since 1.2 > 0.2 (override), should PASS.
        
        res_hits = await session.execute(select(EventRuleHit.rule_name, EventRuleHit.score))
        hits = res_hits.all()
        
        exact_hits = [h for h in hits if h.rule_name == 'TEST_RAW_EXACT']
        in_hits = [h for h in hits if h.rule_name == 'TEST_RAW_IN']
        
        logger.info(f"TEST_RAW_EXACT hits: {len(exact_hits)} (Expected: 0 if threshold 0.8)")
        logger.info(f"TEST_RAW_IN hits: {len(in_hits)} (Expected: >0 since weight 1.2 > override threshold 0.2)")
        
        assert len(exact_hits) == 0, "TEST_RAW_EXACT should have been filtered out"
        assert len(in_hits) > 0, "TEST_RAW_IN should have hits"
        for h in in_hits:
            assert h.score == 1.2, f"Expected score 1.2, got {h.score}"

async def test_case_audit():
    logger.info("--- TEST C: Audit Mode (Record below threshold) ---")
    async with AsyncSessionLocal() as session:
        # Enable Audit Mode
        session.add(Setting(key='monitoring.rules.scoring_record_below_threshold', value='true'))
        await session.commit()
        
        # Replay
        await replay_all_rules(session, mode="REPLACE", batch_size=1000)
        
        # Verify: TEST_RAW_EXACT should now have hits with below_threshold=true in metadata
        res_hits = await session.execute(select(EventRuleHit).where(EventRuleHit.rule_name == 'TEST_RAW_EXACT').limit(1))
        hit = res_hits.scalar()
        
        assert hit is not None, "TEST_RAW_EXACT should be recorded in audit mode"
        assert hit.score == 0.5, f"Expected score 0.5, got {hit.score}"
        assert hit.hit_metadata.get('below_threshold') is True, "Metadata should flag below_threshold"
        logger.info("Audit mode verified: hits under threshold recorded correctly.")

async def run_all():
    await setup_test_rules()
    await clear_settings()
    count_off = await test_case_off()
    await test_case_on()
    await test_case_audit()
    await clear_settings()
    
    # Final check: back to OFF
    count_final = await test_case_off()
    assert count_off == count_final, f"Regresion: count changed from {count_off} to {count_final}"
    logger.info("REGRESSION TEST PASSED: Hit counts identical when scoring is OFF.")

if __name__ == "__main__":
    asyncio.run(run_all())
