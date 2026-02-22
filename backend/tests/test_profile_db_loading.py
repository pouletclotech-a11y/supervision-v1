"""
test_profile_db_loading.py — Tests: chargement des profils depuis la DB
Vérifie : is_active filtering, versioning, provider_code, updated_at.

Stratégie d'isolation : chaque test génère un profile_id unique via uuid4.
"""

import pytest
import uuid
from app.db.models import DBIngestionProfile
from app.ingestion.profile_manager import ProfileManager


def uid(prefix="") -> str:
    """Génère un profile_id unique pour chaque test (évite UNIQUE violations)."""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


@pytest.mark.asyncio
async def test_db_profile_loaded(db_session):
    """Un profil DB actif doit être chargé par le ProfileManager."""
    pid = uid("p_alpha_")
    db_profile = DBIngestionProfile(
        profile_id=pid,
        name="DB Alpha",
        priority=10,
        source_timezone="UTC",
        provider_code="PROV_X",
        confidence_threshold=3.0,
        detection={"extensions": [".pdf"], "required_text": ["SIGNATURE_ALPHA"]},
        mapping=[],
        version_number=2,
        is_active=True,
    )
    db_session.add(db_profile)
    await db_session.commit()

    manager = ProfileManager(profiles_dir="non_existent_dir")
    await manager.load_profiles(db_session)

    profile = manager.get_profile(pid)
    assert profile is not None, f"Profile '{pid}' not found in manager"
    assert profile.name == "DB Alpha"
    assert profile.version_number == 2
    assert profile.provider_code == "PROV_X"
    assert profile.confidence_threshold == 3.0


@pytest.mark.asyncio
async def test_db_profile_inactive_excluded(db_session):
    """Un profil DB inactif (is_active=False) ne doit PAS être chargé."""
    pid = uid("p_inactive_")
    db_session.add(DBIngestionProfile(
        profile_id=pid,
        name="Inactive Beta",
        detection={"extensions": [".xls"]},
        mapping=[],
        is_active=False,
    ))
    await db_session.commit()

    manager = ProfileManager(profiles_dir="non_existent_dir")
    await manager.load_profiles(db_session)

    assert manager.get_profile(pid) is None


@pytest.mark.asyncio
async def test_db_profile_priority_ordering(db_session):
    """Profile haute priorité sélectionné en cas d'extension partagée."""
    low_pid = uid("low_")
    high_pid = uid("high_")
    db_session.add(DBIngestionProfile(
        profile_id=low_pid,
        name="Low Priority",
        priority=5,
        confidence_threshold=0.5,  # Low threshold so extension match passes
        detection={"extensions": [".xml"]},
        mapping=[],
        is_active=True,
    ))
    db_session.add(DBIngestionProfile(
        profile_id=high_pid,
        name="High Priority",
        priority=50,
        confidence_threshold=0.5,  # Low threshold so extension match passes
        detection={"extensions": [".xml"]},
        mapping=[],
        is_active=True,
    ))
    await db_session.commit()

    from app.ingestion.profile_matcher import ProfileMatcher
    manager = ProfileManager(profiles_dir="non_existent_dir")
    await manager.load_profiles(db_session)

    # On instancie un matcher avec SEULEMENT ces 2 profils
    filtered_manager = ProfileManager(profiles_dir="non_existent_dir")
    filtered_manager.profiles = {}
    low_p = manager.get_profile(low_pid)
    high_p = manager.get_profile(high_pid)
    assert low_p is not None, f"low profile '{low_pid}' not found"
    assert high_p is not None, f"high profile '{high_pid}' not found"
    filtered_manager.profiles = {low_pid: low_p, high_pid: high_p}

    matcher = ProfileMatcher(filtered_manager)
    profile, report = matcher.match("data.xml")

    assert profile is not None, f"No profile matched data.xml — report: {report}"
    assert profile.profile_id == high_pid


@pytest.mark.asyncio
async def test_db_profile_updated_at_set(db_session):
    """updated_at doit être automatiquement défini à la création."""
    pid = uid("ts_")
    db_session.add(DBIngestionProfile(
        profile_id=pid,
        name="TS Check",
        detection={"extensions": [".pdf"]},
        mapping=[],
        is_active=True,
    ))
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(
        select(DBIngestionProfile).where(DBIngestionProfile.profile_id == pid)
    )
    row = result.scalar_one()
    assert row.updated_at is not None
    assert row.version_number == 1


@pytest.mark.asyncio
async def test_db_multiple_profiles_loaded(db_session):
    """Plusieurs profils actifs doivent tous être chargés."""
    ids = [uid("multi_") for _ in range(3)]
    for pid in ids:
        db_session.add(DBIngestionProfile(
            profile_id=pid,
            name=f"Profile {pid}",
            detection={"extensions": [".pdf"]},
            mapping=[],
            is_active=True,
        ))
    await db_session.commit()

    manager = ProfileManager(profiles_dir="non_existent_dir")
    await manager.load_profiles(db_session)

    for pid in ids:
        assert manager.get_profile(pid) is not None, f"Profile {pid} missing"
