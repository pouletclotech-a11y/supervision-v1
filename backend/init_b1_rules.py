import asyncio
from app.db.session import AsyncSessionLocal
from app.db.models import AlertRule
from sqlalchemy import select

async def init_rules():
    print("Initializing B1 Pilot Rules...")
    async with AsyncSessionLocal() as session:
        # Define Pilot Rules
        rules_data = [
            {
                "name": "B1 - Acharnement Intrusion",
                "condition_type": "SEVERITY",
                "value": "CRITICAL", # Usually mapped from BURGLARY_ALARM -> CRITICAL
                "frequency_count": 3,
                "frequency_window": 900, # 15 min
                "time_scope": None,
                "is_active": True
            },
            {
                "name": "B1 - Intrusion Week-end/Férié",
                "condition_type": "SEVERITY",
                "value": "CRITICAL",
                "frequency_count": 1,
                "frequency_window": 0,
                "time_scope": "WEEKEND_OR_HOLIDAY",
                "is_active": True
            },
            {
                "name": "B1 - Instabilité Secteur",
                "condition_type": "KEYWORD",
                "value": "DEFAUT SECTEUR", # AC_POWER_FAIL
                "frequency_count": 2,
                "frequency_window": 3600, # 60 min
                "time_scope": None,
                "is_active": True
            }
        ]

        for r_data in rules_data:
            # Check if exists
            stmt = select(AlertRule).where(AlertRule.name == r_data["name"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"Updating rule: {r_data['name']}")
                for k, v in r_data.items():
                    setattr(existing, k, v)
            else:
                print(f"Creating rule: {r_data['name']}")
                new_rule = AlertRule(**r_data)
                session.add(new_rule)
        
        await session.commit()
    print("Rules initialized.")

if __name__ == "__main__":
    asyncio.run(init_rules())
