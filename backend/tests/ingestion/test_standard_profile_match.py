import pytest
from app.ingestion.profile_manager import ProfileManager
from app.ingestion.profile_matcher import ProfileMatcher
from pathlib import Path

def test_vms_ypsilon_standard_matches():
    # Poit to the real profiles directory
    profiles_dir = Path(__file__).parent.parent.parent / "profiles"
    manager = ProfileManager(str(profiles_dir))
    manager.load_profiles()
    matcher = ProfileMatcher(manager)
    
    # Check that our standard fixture matches the standard profile
    # The fixture sample_ypsilon.xls contains "TITRE EXPORT" in col 3 (index 3)
    fixture_path = Path(__file__).parent.parent / "fixtures" / "ingestion" / "sample_ypsilon.xls"
    
    # In a real scenario, we'd extract headers. Here we simulate for matching logic.
    headers = ["C-12345678", "CLIENT TEST", "LUNDI 27/01/2026", "TITRE EXPORT"]
    
    matched = matcher.match(str(fixture_path), headers=headers)
    
    assert matched is not None
    assert matched.profile_id == "vms_ypsilon_standard"
