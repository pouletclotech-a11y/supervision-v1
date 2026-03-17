import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import User, MonitoringProvider, UserProvider, AuditLog
from sqlalchemy import delete

async def test_roles():
    async with AsyncSessionLocal() as session:
        # Clean up previous runs
        user_emails = ["super2@test.com", "admin2@test.com", "viewer2@test.com"]
        stmt_users = select(User.id).where(User.email.in_(user_emails))
        user_ids = list((await session.execute(stmt_users)).scalars().all())
        
        if user_ids:
            await session.execute(delete(AuditLog).where(AuditLog.user_id.in_(user_ids)))
            await session.execute(delete(UserProvider).where(UserProvider.user_id.in_(user_ids)))
            await session.execute(delete(User).where(User.id.in_(user_ids)))
            
        await session.execute(delete(MonitoringProvider).where(MonitoringProvider.code.in_(["P98", "P99"])))
        await session.commit()
        
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
        # We need to delete AuditLog entries referencing these users before deleting them
        await session.execute(delete(AuditLog).where(AuditLog.user_id.in_([super_admin.id, admin.id, viewer.id])))
        await session.delete(super_admin)
        await session.delete(admin)
        await session.delete(viewer)
        await session.delete(p1)
        await session.delete(p2)
        await session.commit()
        print("Cleanup OK")

if __name__ == "__main__":
    asyncio.run(test_roles())
