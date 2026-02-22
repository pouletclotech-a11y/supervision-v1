import pytest
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from app.ingestion.profile_manager import ProfileManager
from app.ingestion.profile_matcher import ProfileMatcher
from app.services.provider_resolver import ProviderResolver
from app.db.models import SmtpProviderRule

# Mocking adapter item for tests
class MockItem:
    def __init__(self, filename, path, sender_email=None):
        self.filename = filename
        self.path = path
        self.metadata = {"sender_email": sender_email} if sender_email else {}
        self.source = "test"
        self.sha256 = "dummy_hash"

@pytest.fixture
def test_profiles(tmp_path):
    p_dir = tmp_path / "profiles"
    p_dir.mkdir()
    
    # 1. Neutral Histo Profile
    (p_dir / "ypsilon_histo_excel.yaml").write_text("""
profile_id: ypsilon_histo_excel
name: YPSILON HISTO
priority: 15
detection:
  extensions: [.xls, .xlsx]
  required_headers: ["YPSILON_HISTO"]
mapping:
  - source: 0
    target: site_code
""")

    # 2. CORS PDF Profile
    (p_dir / "cors_pdf.yaml").write_text("""
profile_id: cors_pdf
name: CORS ONLINE PDF
priority: 20
detection:
  extensions: [.pdf]
  required_text: ["CORS ONLINE"]
""")

    # 3. SPGO PDF Profile
    (p_dir / "spgo_pdf.yaml").write_text("""
profile_id: spgo_pdf
name: SPGO PDF
priority: 20
detection:
  extensions: [.pdf]
  required_text: ["SPGO High Tec"]
""")

    # 4. Standard VMS Profile (for regression check)
    (p_dir / "vms_ypsilon_standard.yaml").write_text("""
profile_id: vms_ypsilon_standard
name: VMS Standard
priority: 10
detection:
  extensions: [.xls, .xlsx]
  required_headers: ["TITRE EXPORT"]
""")

    manager = ProfileManager(str(p_dir))
    manager.load_profiles()
    return manager

def test_matcher_cors_pdf(test_profiles):
    matcher = ProfileMatcher(test_profiles)
    # 1. Avec probe correcte -> Match (Score 1.0 ext + 3.0 text = 4.0 >= 2.0)
    result = matcher.match("file.pdf", text_content="Report for CORS ONLINE - 2026")
    assert result is not None
    assert result.profile_id == "cors_pdf"
    
    # 2. Sans probe -> No Match (Score 1.0 < 2.0 threshold pour profil strict)
    result_no_probe = matcher.match("file.pdf", text_content=None)
    assert result_no_probe is None

def test_matcher_spgo_pdf(test_profiles):
    matcher = ProfileMatcher(test_profiles)
    # Simulation d'un probe qui trouve "SPGO High Tec"
    result = matcher.match("file.pdf", text_content="SPGO High Tec Security Report")
    assert result is not None
    assert result.profile_id == "spgo_pdf"

def test_matcher_histo_excel(test_profiles):
    matcher = ProfileMatcher(test_profiles)
    # Simulation d'une probe Excel qui trouve "YPSILON_HISTO" en A1 (passé comme header)
    # Score: 1.0 (ext) + 1.0 (header) = 2.0 >= 2.0
    result = matcher.match("data.xlsx", headers=["YPSILON_HISTO"])
    assert result is not None
    assert result.profile_id == "ypsilon_histo_excel"

def test_matcher_no_probe_rejected_for_stricts(test_profiles):
    matcher = ProfileMatcher(test_profiles)
    # Sans probe, les profils stricts (ypsilon_histo_excel, vms_ypsilon_standard)
    # ne dépassent pas score 1.0 (extension match).
    # Le min_score de 2.0 les rejette.
    result = matcher.match("test.xls", headers=None)
    assert result is None # Correct prod behavior: no signal, no match

def test_matcher_vms_standard_match(test_profiles):
    matcher = ProfileMatcher(test_profiles)
    # Test avec le header standard VMS
    result = matcher.match("export.xls", headers=["TITRE EXPORT"])
    assert result is not None
    assert result.profile_id == "vms_ypsilon_standard"

def test_matcher_min_score_unmatched(test_profiles):
    matcher = ProfileMatcher(test_profiles)
    # Fichier inconnu ou sans extension -> None
    result = matcher.match("unknown.txt")
    assert result is None

@pytest.mark.asyncio
async def test_provider_resolution_logic():
    resolver = ProviderResolver()
    
    # Mocking DB session
    db = AsyncMock()
    
    # Mocking rules from DB
    rule_spgo = SmtpProviderRule(id=1, match_type='DOMAIN', match_value='spgo.fr', provider_id=2, priority=10, is_active=True)
    rule_cors = SmtpProviderRule(id=2, match_type='DOMAIN', match_value='cors-online.com', provider_id=3, priority=10, is_active=True)
    rule_cors_fr = SmtpProviderRule(id=3, match_type='DOMAIN', match_value='cors-online.fr', provider_id=3, priority=10, is_active=True)
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [rule_spgo, rule_cors, rule_cors_fr]
    db.execute.return_value = mock_result
    
    # Test resolution
    assert await resolver.resolve_provider("robot@spgo.fr", db) == 2
    assert await resolver.resolve_provider("alertes@cors-online.com", db) == 3
    assert await resolver.resolve_provider("info@cors-online.fr", db) == 3
    assert await resolver.resolve_provider("unknown@gmail.com", db) is None
