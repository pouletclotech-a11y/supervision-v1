import pytest
from httpx import AsyncClient
from app.main import app
from app.db.models import User, DBIngestionProfile, ImportLog, ReprocessJob, AuditLog
from app.auth.deps import get_current_active_admin, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from unittest.mock import MagicMock
from fastapi import BackgroundTasks

@pytest.fixture
async def admin_user(db_session):
    """Creates a real admin user in the test database and returns it."""
    # Check if exists (though cleanup should have run)
    from sqlalchemy import select
    stmt = select(User).where(User.email == "admin@test.com")
    res = await db_session.execute(stmt)
    user = res.scalar_one_or_none()
    
    if not user:
        user = User(email="admin@test.com", hashed_password="pw", role="ADMIN", is_active=True)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
    return user

@pytest.fixture
def override_deps(db_session, admin_user):
    """Overrides dependencies for Admin API testing."""
    async def mock_get_admin():
        return admin_user
    
    app.dependency_overrides[get_current_active_admin] = mock_get_admin
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[BackgroundTasks] = lambda: MagicMock()
    yield
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_admin_unmatched_api(db_session: AsyncSession, override_deps):
    # Setup failed imports
    log1 = ImportLog(
        filename="unmatched1.xls", 
        status="PROFILE_NOT_CONFIDENT", 
        import_metadata={},
        created_at=datetime.utcnow()
    )
    db_session.add(log1)
    await db_session.commit()
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/admin/unmatched")
        
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["filename"] == "unmatched1.xls"

@pytest.mark.asyncio
async def test_admin_profiles_api(db_session: AsyncSession, override_deps):
    # Test Create
    profile_in = {
        "profile_id": "test_api_p",
        "name": "Test API P",
        "priority": 5,
        "is_active": True,
        "detection": {"extensions": [".xls"]},
        "mapping": []
    }
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/v1/admin/profiles", json=profile_in)
    
    if response.status_code != 200:
        print(response.json())
        
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["profile_id"] == "test_api_p"
    assert res_data["version_number"] == 1
    
    # Test Patch
    update_data = {**profile_in, "priority": 15}
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.patch(
            f"/api/v1/admin/profiles/{res_data['id']}", 
            json={"profile_in": update_data, "change_reason": "test update"}
        )
    
    if response.status_code != 200:
        print(f"PATCH 422 Detail: {response.json()}")
        
    assert response.status_code == 200
    assert response.json()["priority"] == 15
    assert response.json()["version_number"] == 2

@pytest.mark.asyncio
async def test_admin_reprocess_api(db_session: AsyncSession, override_deps):
    # Setup import
    log = ImportLog(
        filename="to_repro.xls", 
        status="ERROR", 
        import_metadata={},
        created_at=datetime.utcnow()
    )
    db_session.add(log)
    await db_session.commit()
    await db_session.refresh(log)
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(f"/api/v1/admin/reprocess/import/{log.id}")
        
    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "PENDING"
    assert job["scope"]["import_id"] == log.id
