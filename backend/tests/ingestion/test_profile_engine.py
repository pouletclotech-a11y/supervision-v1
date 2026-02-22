import pytest
import os
import shutil
from pathlib import Path
from app.ingestion.profile_manager import ProfileManager
from app.ingestion.profile_matcher import ProfileMatcher

@pytest.fixture
def temp_profiles_dir(tmp_path):
    d = tmp_path / "profiles"
    d.mkdir()
    return d

def create_profile_yaml(directory, profile_id, extensions=None, priority=0, filename_pattern=None, required_headers=None):
    import yaml
    content = {
        "profile_id": profile_id,
        "name": f"Profile {profile_id}",
        "priority": priority,
        "detection": {
            "extensions": extensions or [".xls"],
            "filename_pattern": filename_pattern,
            "required_headers": required_headers or []
        }
    }
    with open(directory / f"{profile_id}.yaml", "w") as f:
        yaml.dump(content, f)

def test_profile_loader_valid(temp_profiles_dir):
    create_profile_yaml(temp_profiles_dir, "test_p1", extensions=[".xls"])
    manager = ProfileManager(str(temp_profiles_dir))
    manager.load_profiles()
    assert len(manager.profiles) == 1
    assert "test_p1" in manager.profiles

def test_profile_loader_invalid(temp_profiles_dir):
    # Fichier YAML invalide (manque profile_id)
    with open(temp_profiles_dir / "invalid.yaml", "w") as f:
        f.write("name: Missing ID\ndetection:\n  extensions: ['.xls']")
    
    manager = ProfileManager(str(temp_profiles_dir))
    manager.load_profiles()
    assert len(manager.profiles) == 0
    assert len(manager.invalid_profiles) == 1

def test_matcher_single_match(temp_profiles_dir):
    create_profile_yaml(temp_profiles_dir, "xls_profile", extensions=[".xls"])
    manager = ProfileManager(str(temp_profiles_dir))
    manager.load_profiles()
    matcher = ProfileMatcher(manager)
    
    matched = matcher.match("test.xls")
    assert matched is not None
    assert matched.profile_id == "xls_profile"

def test_matcher_priority_tie_break(temp_profiles_dir):
    # Deux profils matchant le .xls, mais p2 a une priorité plus haute
    create_profile_yaml(temp_profiles_dir, "p1", priority=10)
    create_profile_yaml(temp_profiles_dir, "p2", priority=20)
    
    manager = ProfileManager(str(temp_profiles_dir))
    manager.load_profiles()
    matcher = ProfileMatcher(manager)
    
    matched = matcher.match("data.xls")
    assert matched.profile_id == "p2"

def test_matcher_filename_pattern(temp_profiles_dir):
    create_profile_yaml(temp_profiles_dir, "generic", priority=0)
    create_profile_yaml(temp_profiles_dir, "specific", filename_pattern="SUPERVISION", priority=0)
    
    manager = ProfileManager(str(temp_profiles_dir))
    manager.load_profiles()
    matcher = ProfileMatcher(manager)
    
    # Doit matcher 'specific' car score plus haut (+5 pour le pattern)
    matched = matcher.match("SUPERVISION_2026.xls")
    assert matched.profile_id == "specific"

def test_matcher_headers_match(temp_profiles_dir):
    create_profile_yaml(temp_profiles_dir, "h1", required_headers=["Site", "Action"])
    create_profile_yaml(temp_profiles_dir, "h2", required_headers=["Site", "Code"])
    
    manager = ProfileManager(str(temp_profiles_dir))
    manager.load_profiles()
    matcher = ProfileMatcher(manager)
    
    # Match h1 car il a 2 headers qui matchent
    matched = matcher.match("file.xls", headers=["Site", "Action", "Status"])
    assert matched.profile_id == "h1"

def test_matcher_no_match(temp_profiles_dir):
    create_profile_yaml(temp_profiles_dir, "p1", extensions=[".xls"])
    manager = ProfileManager(str(temp_profiles_dir))
    manager.load_profiles()
    matcher = ProfileMatcher(manager)
    
    matched = matcher.match("test.pdf") # Extension non supportée
    assert matched is None

def test_matcher_ambiguity_deterministic(temp_profiles_dir):
    # Même score (0), même priorité (0). Doit choisir par ID alphabétique (p1)
    create_profile_yaml(temp_profiles_dir, "p1", priority=0)
    create_profile_yaml(temp_profiles_dir, "p2", priority=0)
    
    manager = ProfileManager(str(temp_profiles_dir))
    manager.load_profiles()
    matcher = ProfileMatcher(manager)
    
    matched = matcher.match("ambig.xls")
    assert matched.profile_id == "p1"
