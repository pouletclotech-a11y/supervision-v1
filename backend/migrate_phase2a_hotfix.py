import asyncio
import logging
from app.db.session import AsyncSessionLocal
from app.db.models import AlertRule
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

async def migrate_engine_v1():
    async with AsyncSessionLocal() as session:
        # Check if ENGINE_V1 exists
        stmt = select(AlertRule).where(AlertRule.name == 'ENGINE_V1')
        result = await session.execute(stmt)
        rule = result.scalar_one_or_none()
        
        if not rule:
            logger.info("Creating system rule: ENGINE_V1")
            rule = AlertRule(
                name='ENGINE_V1',
                condition_type='SYSTEM',
                value='LEGACY_V1',
                is_active=True,
                logic_enabled=False
            )
            session.add(rule)
            await session.commit()
            logger.info("ENGINE_V1 created.")
        else:
            logger.info(f"ENGINE_V1 already exists (id={rule.id}, condition_type={rule.condition_type})")
            if rule.condition_type != 'SYSTEM':
                logger.info(f"Updating condition_type to SYSTEM for ENGINE_V1")
                rule.condition_type = 'SYSTEM'
                await session.commit()

if __name__ == "__main__":
    asyncio.run(migrate_engine_v1())
