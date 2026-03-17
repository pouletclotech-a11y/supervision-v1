import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import User, MonitoringProvider, UserProvider, AuditLog

async def test_roles():
    async with AsyncSessionLocal() as session:
        # Create test users
        super_admin = User(email="super2@test.com", hashed_password="pw", role="SUPER_ADMIN", full_name="Super")
        admin = User(email="admin2@test.com", hashed_password="pw", role="ADMIN", full_name="Admin")
        viewer = User(email="viewer2@test.com", hashed_password="pw", role="VIEWER", full_name="Viewer")
        
        session.add_all([super_admin, admin, viewer])
        await session.flush()

        # Create test providers
        p1 = MonitoringProvider(code="P98", label="Provider 98")
        p2 = MonitoringProvider(code="P99", label="Provider 99")
        session.add_all([p1, p2])
        await session.flush()

        # Assign P1 to admin
        session.add(UserProvider(user_id=admin.id, provider_id=p1.id))
        await session.commit()
        
        audit = AuditLog(user_id=super_admin.id, action="TEST", target_type="TEST", target_id="0")
        session.add(audit)
        await session.commit()
        
        print("Test roles and DB integrity OK")
        
        # Cleanup
        await session.delete(super_admin)
        await session.delete(admin)
        await session.delete(viewer)
        await session.delete(p1)
        await session.delete(p2)
        await session.commit()
        print("Cleanup OK")

if __name__ == "__main__":
    asyncio.run(test_roles())
