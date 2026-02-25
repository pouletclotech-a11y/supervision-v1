import pytest
from datetime import datetime, timedelta, timezone
from app.services.repository import AdminRepository
from app.db.models import MonitoringProvider, ImportLog

@pytest.mark.asyncio
async def test_calculate_health_ok(db_session):
    """Test health status OK: enough emails and recent activity."""
    # Setup provider
    p = MonitoringProvider(
        code="TEST_OK", 
        label="Test Provider OK", 
        monitoring_enabled=True,
        expected_emails_per_day=10,
        silence_threshold_minutes=60,
        last_successful_import_at=datetime.now(timezone.utc) - timedelta(minutes=10)
    )
    db_session.add(p)
    await db_session.flush()

    # Add 10 successful imports in last 24h
    for i in range(10):
        db_session.add(ImportLog(
            provider_id=p.id, 
            status="SUCCESS", 
            filename=f"test_{i}.xls",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1)
        ))
    await db_session.flush()
    await db_session.commit()

    repo = AdminRepository(db_session)
    health = await repo.get_providers_health()
    
    test_p = next(h for h in health if h['code'] == "TEST_OK")
    assert test_p['status'] == "OK"
    assert test_p['received_24h'] == 10
    assert test_p['completion_rate'] == 1.0

@pytest.mark.asyncio
async def test_calculate_health_silent(db_session):
    """Test health status SILENT: last activity too old."""
    # Setup provider
    p = MonitoringProvider(
        code="SILENT_P", 
        label="Silent Provider", 
        monitoring_enabled=True,
        expected_emails_per_day=5,
        silence_threshold_minutes=30,
        last_successful_import_at=datetime.now(timezone.utc) - timedelta(minutes=40)
    )
    db_session.add(p)
    await db_session.commit()

    repo = AdminRepository(db_session)
    health = await repo.get_providers_health()
    
    test_p = next(h for h in health if h['code'] == "SILENT_P")
    assert test_p['status'] == "SILENT"

@pytest.mark.asyncio
async def test_calculate_health_late(db_session):
    """Test health status LATE: recent activity but not enough volume."""
    # Setup provider
    p = MonitoringProvider(
        code="LATE_P", 
        label="Late Provider", 
        monitoring_enabled=True,
        expected_emails_per_day=10,
        silence_threshold_minutes=60,
        last_successful_import_at=datetime.now(timezone.utc) - timedelta(minutes=10)
    )
    db_session.add(p)
    await db_session.flush()
    
    # Only 5 imports (expected 10)
    for i in range(5):
        db_session.add(ImportLog(
            provider_id=p.id, 
            status="SUCCESS", 
            filename=f"test_{i}.xls",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1)
        ))
    await db_session.commit()

    repo = AdminRepository(db_session)
    health = await repo.get_providers_health()
    
    test_p = next(h for h in health if h['code'] == "LATE_P")
    assert test_p['status'] == "LATE"
    assert test_p['completion_rate'] == 0.5

@pytest.mark.asyncio
async def test_calculate_health_unconfigured(db_session):
    """Test health status UNCONFIGURED: expected=0 and monitoring disabled."""
    # Setup provider
    p = MonitoringProvider(
        code="UNCONFIG", 
        label="Unconfigured Provider", 
        monitoring_enabled=False,
        expected_emails_per_day=0
    )
    db_session.add(p)
    await db_session.commit()

    repo = AdminRepository(db_session)
    health = await repo.get_providers_health()
    
    test_p = next(h for h in health if h['code'] == "UNCONFIG")
    assert test_p['status'] == "UNCONFIGURED"
