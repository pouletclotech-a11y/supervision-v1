import pytest
import os
from httpx import AsyncClient
from app.main import app
from app.db.models import ImportLog, User
from app.db.session import AsyncSessionLocal
from app.auth.deps import get_current_user
from pathlib import Path

# Mock user for auth
mock_user = User(id=1, email="test@test.com", full_name="Test User", role="ADMIN", is_active=True)

async def mock_get_current_user():
    return mock_user

app.dependency_overrides[get_current_user] = mock_get_current_user

@pytest.mark.asyncio
async def test_inspect_import_api():
    # 1. Prepare a mock file
    test_file_path = "/tmp/test_inspect.xls"
    content = "HEADER1\tHEADER2\tHEADER3\nValue1\tValue2\tValue3\n"
    with open(test_file_path, "w", encoding="latin-1") as f:
        f.write(content)

    # 2. Create a dummy ImportLog entry
    async with AsyncSessionLocal() as session:
        log = ImportLog(
            filename="test_inspect.xls",
            archive_path=test_file_path,
            status="SUCCESS",
            adapter_name="test_adapter"
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        import_id = log.id

    # 3. Call the API using AsyncClient
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/imports/{import_id}/inspect")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["file_type"] == "XLS_TSV"
    assert "HEADER1" in data["headers"]
    assert len(data["sample_rows"]) > 0
    assert "skeleton_yaml" in data

    # Cleanup
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
    
    # Reset overrides
    app.dependency_overrides = {}
