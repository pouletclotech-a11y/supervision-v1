"""
test_profile_fallback.py — Tests: fallback YAML quand la DB est vide
Vérifie : ProfileManager en mode DB_FALLBACK_YAML et DB_ONLY.

Stratégie : on patche 'app.ingestion.profile_manager.settings' directement.
           Les tests DB utilisent uuid-based IDs pour l'isolation.
"""

import pytest
import uuid
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.ingestion.profile_manager import ProfileManager


def uid(prefix="") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


@pytest.fixture
def yaml_profiles_dir(tmp_path):
    """Répertoire temporaire avec 2 profils YAML abstraits."""
    p_dir = tmp_path / "profiles"
    p_dir.mkdir()
    (p_dir / "generic_xml.yaml").write_text(yaml.dump({
        "profile_id": "yaml_generic_xml",
        "name": "YAML Generic XML",
        "priority": 5,
        "confidence_threshold": 2.0,
        "provider_code": "PROV_YAML",
        "detection": {"extensions": [".xml"]},
        "mapping": [],
    }))
    (p_dir / "generic_json.yaml").write_text(yaml.dump({
        "profile_id": "yaml_generic_json",
        "name": "YAML Generic JSON",
        "priority": 5,
        "confidence_threshold": 2.0,
        "detection": {"extensions": [".json"]},
        "mapping": [],
    }))
    return str(p_dir)


@pytest.mark.asyncio
async def test_fallback_yaml_loads_when_db_empty(yaml_profiles_dir):
    """
    En mode DB_FALLBACK_YAML, DB vide → les profils YAML doivent être chargés.
    On passe db=None pour simuler une DB vide sans connexion réelle.
    """
    with patch("app.ingestion.profile_manager.settings") as mock_settings:
        mock_settings.PROFILE_SOURCE_MODE = "DB_FALLBACK_YAML"
        manager = ProfileManager(profiles_dir=yaml_profiles_dir)
        await manager.load_profiles(db=None)

    assert "yaml_generic_xml" in manager.profiles
    assert "yaml_generic_json" in manager.profiles
    assert len(manager.profiles) == 2


@pytest.mark.asyncio
async def test_db_profile_overrides_yaml(db_session, yaml_profiles_dir):
    """
    En mode DB_FALLBACK_YAML, un profil en DB prévaut sur le YAML du même profile_id.
    """
    from app.db.models import DBIngestionProfile

    db_session.add(DBIngestionProfile(
        profile_id="yaml_generic_xml",
        name="DB OVERRIDE of XML",
        priority=99,
        confidence_threshold=5.0,
        detection={"extensions": [".xml"]},
        mapping=[],
        is_active=True,
    ))
    await db_session.commit()

    with patch("app.ingestion.profile_manager.settings") as mock_settings:
        mock_settings.PROFILE_SOURCE_MODE = "DB_FALLBACK_YAML"
        manager = ProfileManager(profiles_dir=yaml_profiles_dir)
        await manager.load_profiles(db_session)

    profile = manager.get_profile("yaml_generic_xml")
    assert profile is not None
    assert profile.name == "DB OVERRIDE of XML"
    assert profile.confidence_threshold == 5.0


@pytest.mark.asyncio
async def test_db_only_mode_ignores_yaml(yaml_profiles_dir):
    """
    En mode DB_ONLY, les fichiers YAML ne doivent pas être chargés,
    même si le répertoire YAML contient des profils valides.
    On passe db=None → DB vide → profils=0.
    """
    with patch("app.ingestion.profile_manager.settings") as mock_settings:
        mock_settings.PROFILE_SOURCE_MODE = "DB_ONLY"
        manager = ProfileManager(profiles_dir=yaml_profiles_dir)
        await manager.load_profiles(db=None)

    # DB_ONLY + db=None → aucun chargement YAML
    assert len(manager.profiles) == 0


def test_yaml_invalid_profile_skipped(tmp_path):
    """Un fichier YAML sans profile_id doit être ignoré (dans invalid_profiles)."""
    p_dir = tmp_path / "profiles"
    p_dir.mkdir()
    (p_dir / "broken.yaml").write_text("name: Missing ID\ndetection:\n  extensions: ['.xls']")

    import asyncio
    with patch("app.ingestion.profile_manager.settings") as mock_settings:
        mock_settings.PROFILE_SOURCE_MODE = "DB_FALLBACK_YAML"
        manager = ProfileManager(profiles_dir=str(p_dir))
        asyncio.get_event_loop().run_until_complete(manager.load_profiles(db=None))

    assert len(manager.profiles) == 0
    assert len(manager.invalid_profiles) == 1


@pytest.mark.asyncio
async def test_yaml_profile_missing_profile_id_tracked(tmp_path):
    """Profile YAML sans profile_id → enregistré dans invalid_profiles."""
    p_dir = tmp_path / "profiles"
    p_dir.mkdir()
    (p_dir / "noid.yaml").write_text("name: No ID\npriority: 5\ndetection:\n  extensions:\n  - .csv\n")

    with patch("app.ingestion.profile_manager.settings") as mock_settings:
        mock_settings.PROFILE_SOURCE_MODE = "DB_FALLBACK_YAML"
        manager = ProfileManager(profiles_dir=str(p_dir))
        await manager.load_profiles(db=None)

    assert len(manager.profiles) == 0
    assert len(manager.invalid_profiles) >= 1
