import asyncio
from app.db.session import AsyncSessionLocal
from app.db.models import MonitoringProvider, User
from sqlalchemy import select
from app.auth import deps

async def verify():
    async with AsyncSessionLocal() as session:
        # 1. Check all providers
        res = await session.execute(select(MonitoringProvider).where(MonitoringProvider.deleted_at.is_(None)))
        providers = res.scalars().all()
        print(f"Total providers (not deleted): {len(providers)}")

        # 2. Simulate endpoint logic for ADMIN user
        # We'll pick the first admin user
        res_user = await session.execute(select(User).where(User.role == "ADMIN"))
        user = res_user.scalar_one_or_none()
        if not user:
            print("No ADMIN user found")
            return
        
        print(f"User: {user.email} Role: {user.role}")
        
        # Simulate get_user_provider_ids logic
        if user.role in ["SUPER_ADMIN", "ADMIN"]:
            provider_ids = None
        else:
            # We don't have UserProvider entries based on previous check
            provider_ids = []
            
        print(f"Simulated provider_ids: {provider_ids}")

        stmt = select(MonitoringProvider).where(MonitoringProvider.deleted_at.is_(None))
        if provider_ids is not None:
            stmt = stmt.where(MonitoringProvider.id.in_(provider_ids))
            
        res_final = await session.execute(stmt)
        final_providers = res_final.scalars().all()
        print(f"Final results count: {len(final_providers)}")
        for p in final_providers:
            print(f"- {p.code}")

if __name__ == "__main__":
    asyncio.run(verify())
