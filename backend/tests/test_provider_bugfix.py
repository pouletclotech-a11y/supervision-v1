import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock
from app.main import app
from app.db.models import MonitoringProvider

from app.api.v1.endpoints.connections import get_db, get_current_operator_or_admin
from app.auth.deps import get_current_user

@pytest.mark.asyncio
async def test_provider_creation_minimal():
    """Vérifie qu'un provider créé avec peu de champs reçoit les défauts."""
    payload = {
        "code": "TEST_MIN",
        "label": "Test Minimal"
    }
    
@pytest.mark.asyncio
async def test_provider_creation_minimal():
    """Vérifie qu'un provider créé avec peu de champs reçoit les défauts."""
    payload = {
        "code": "TEST_MIN",
        "label": "Test Minimal"
    }
    
    # On mocke la session pour retourner "pas de provider existant" lors du check d'unicité
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res
    
    # db.add est SYNCHRONE en SQLAlchemy
    mock_session.add = MagicMock()
    def side_effect_add(obj):
        obj.id = 1
    mock_session.add.side_effect = side_effect_add
    
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_current_operator_or_admin] = lambda: MagicMock(role="ADMIN")
    
    try:
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post("/api/v1/connections/providers", json=payload)
    finally:
        app.dependency_overrides.clear()
                
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "TEST_MIN"
    assert data["is_active"] is True
    assert data["expected_emails_per_day"] == 0
    assert data["expected_frequency_type"] == "daily"
    assert data["silence_threshold_minutes"] == 1440
    assert data["monitoring_enabled"] is False

@pytest.mark.asyncio
async def test_provider_patch_partial_merge():
    """Vérifie qu'un patch partiel ne remplace pas les champs absents par NULL."""
    provider_id = 99
    payload = {
        "monitoring_enabled": True,
        "silence_threshold_minutes": 500
    }
    
    # Existing provider mock
    existing_provider = MonitoringProvider(
        id=provider_id,
        code="PATCH_TEST",
        label="Patch Test",
        is_active=True,
        expected_emails_per_day=42,
        expected_frequency_type="weekly",
        silence_threshold_minutes=1440,
        monitoring_enabled=False
    )
    
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_provider
    mock_session.execute.return_value = mock_res
    mock_session.refresh = AsyncMock()
    
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_current_operator_or_admin] = lambda: MagicMock(role="ADMIN")
    
    try:
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.patch(f"/api/v1/connections/providers/{provider_id}", json=payload)
    finally:
        app.dependency_overrides.clear()
                
    assert response.status_code == 200
    assert existing_provider.monitoring_enabled is True
    assert existing_provider.silence_threshold_minutes == 500
    assert existing_provider.expected_emails_per_day == 42
    assert existing_provider.expected_frequency_type == "weekly"

@pytest.mark.asyncio
async def test_event_repository_update_last_import():
    """Vérifie que la méthode déplacée dans EventRepository fonctionne."""
    from app.services.repository import EventRepository
    from datetime import datetime
    
    mock_session = AsyncMock()
    repo = EventRepository(mock_session)
    
    provider_id = 123
    ts = datetime.utcnow()
    
    await repo.update_provider_last_import(provider_id, ts)
    
    # L'exécution doit avoir eu lieu sans AttributeError
    assert mock_session.execute.called
