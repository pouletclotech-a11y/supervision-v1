import pytest
import os
import yaml
from pathlib import Path
from unittest.mock import MagicMock
from sqlalchemy import select
from app.ingestion.profile_manager import ProfileManager
from app.ingestion.profile_matcher import ProfileMatcher
from app.db.models import DBIngestionProfile, ImportLog
from app.schemas.ingestion_profile import IngestionProfile, DetectionRules
from app.core.config import settings
from app.ingestion.worker import process_ingestion_item

@pytest.fixture
def temp_profiles_dir(tmp_path):
    d = tmp_path / "profiles"
    d.mkdir()
    p1 = {
        "profile_id": "yaml_only",
        "name": "YAML Only",
        "detection": {"extensions": [".xls"]},
        "mapping": []
    }
    with open(d / "p1.yaml", "w") as f:
        yaml.dump(p1, f)
    return d

@pytest.mark.asyncio
async def test_fallback_yaml(db_session, temp_profiles_dir):
    # Ensure DB is empty
    manager = ProfileManager(profiles_dir=str(temp_profiles_dir))
    settings.PROFILE_SOURCE_MODE = "DB_FALLBACK_YAML"
    
    await manager.load_profiles(db_session)
    
    assert "yaml_only" in manager.profiles
    assert manager.get_profile("yaml_only").name == "YAML Only"

@pytest.mark.asyncio
async def test_profile_not_confident_persistence(db_session, redis_client):
    from app.services.repository import EventRepository
    from app.ingestion.worker import _get_file_probe
    from app.ingestion.profile_manager import ProfileManager
    from app.ingestion.profile_matcher import ProfileMatcher
    import app.ingestion.worker as worker
    
    # 1. Setup a profile with high threshold
    db_profile = DBIngestionProfile(
        profile_id="strict_profile",
        name="Strict",
        confidence_threshold=10.0,
        detection={"extensions": [".pdf"], "required_text": ["MUST_HAVE_THIS"]},
        mapping=[]
    )
    db_session.add(db_profile)
    await db_session.commit()
    
    # 2. Mock adapter item
    item = MagicMock()
    item.path = "test.pdf"
    item.filename = "test.pdf"
    item.source = "TEST"
    item.metadata = {}
    item.sha256 = "dummy_hash"
    
    # Create a dummy file
    Path("test.pdf").write_text("Some random content without keywords")
    
    # 3. Running process_ingestion_item (partially mocked if needed, but let's try real)
    # We need to ensure ProfileMatcher uses our session-loaded profiles
    manager = ProfileManager(profiles_dir="non_existent")
    worker.profile_manager = manager
    worker.profile_matcher = ProfileMatcher(manager)
    
    # Mock Redis Lock
    lock = MagicMock()
    lock.acquire.return_value = True
    
    adapter = MagicMock()
    
    await process_ingestion_item(adapter, item, lock, redis_client)
    
    # 4. Verify ImportLog in DB
    result = await db_session.execute(select(ImportLog).where(ImportLog.status == "PROFILE_NOT_CONFIDENT"))
    log = result.scalar_one_or_none()
    
    assert log is not None
    assert log.status == "PROFILE_NOT_CONFIDENT"
    assert log.import_metadata["match_score"] == 1.0 # Only extension match
    assert log.import_metadata["best_candidate"] == "strict_profile"
    assert "Some random content" in log.raw_payload
    
    # Cleanup
    if os.path.exists("test.pdf"):
        os.remove("test.pdf")
