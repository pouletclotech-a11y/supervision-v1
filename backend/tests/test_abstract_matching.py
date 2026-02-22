"""
test_abstract_matching.py — Tests: scoring abstrait du ProfileMatcher
Vérifie : matching sans aucun nom de télésurveilleur hardcodé,
           thresholds de confiance, tie-break par priorité.
"""

import pytest
from app.ingestion.profile_manager import ProfileManager
from app.ingestion.profile_matcher import ProfileMatcher
from app.schemas.ingestion_profile import IngestionProfile, DetectionRules


@pytest.fixture
def abstract_manager():
    """Deux profils entièrement abstraits — aucun nom métier."""
    manager = ProfileManager(profiles_dir="non_existent_dir")
    p_alpha = IngestionProfile(
        profile_id="generic_alpha",
        name="Generic Alpha",
        priority=10,
        confidence_threshold=3.0,
        provider_code="PROV_A",
        detection=DetectionRules(
            extensions=[".pdf"],
            required_text=["SIGNATURE_ALPHA"],
        ),
        mapping=[],
    )
    p_beta = IngestionProfile(
        profile_id="generic_beta",
        name="Generic Beta",
        priority=10,
        confidence_threshold=3.0,
        provider_code="PROV_B",
        detection=DetectionRules(
            extensions=[".pdf"],
            required_text=["SIGNATURE_BETA"],
        ),
        mapping=[],
    )
    manager.profiles = {
        "generic_alpha": p_alpha,
        "generic_beta": p_beta,
    }
    return manager


def test_abstract_match_alpha(abstract_manager):
    """SIGNATURE_ALPHA → doit matcher generic_alpha uniquement."""
    matcher = ProfileMatcher(abstract_manager)
    profile, report = matcher.match("report.pdf", text_content="This is a SIGNATURE_ALPHA doc")

    assert profile is not None
    assert profile.profile_id == "generic_alpha"
    assert profile.provider_code == "PROV_A"
    assert report["best_score"] >= 3.0
    assert report["threshold_met"] is True


def test_abstract_match_beta(abstract_manager):
    """SIGNATURE_BETA → doit matcher generic_beta uniquement."""
    matcher = ProfileMatcher(abstract_manager)
    profile, report = matcher.match("report.pdf", text_content="SIGNATURE_BETA found here")

    assert profile is not None
    assert profile.profile_id == "generic_beta"
    assert profile.provider_code == "PROV_B"


def test_threshold_rejection(abstract_manager):
    """Sans mot-clé requis → score < seuil → prof=None, rapport conservé."""
    matcher = ProfileMatcher(abstract_manager)
    profile, report = matcher.match("report.pdf", text_content="Nothing relevant")

    assert profile is None
    assert report["threshold_met"] is False
    # best_score présent dans le rapport même en cas d'échec
    assert "best_score" in report
    # Score négatif attendu (pénalité -10 pour texte obligatoire absent)
    assert report["best_score"] < 3.0


def test_no_hardcoded_names(abstract_manager):
    """Le rapport ne doit contenir aucun nom interne de télésurveilleur."""
    matcher = ProfileMatcher(abstract_manager)
    _, report = matcher.match("report.pdf", text_content="SIGNATURE_ALPHA")
    report_str = str(report)
    for forbidden in ["SPGO", "CORS", "YPSILON"]:
        assert forbidden not in report_str, f"Hardcode détecté : {forbidden}"


def test_filename_pattern_boost(abstract_manager):
    """Un pattern filename booste le score et change le gagnant."""
    # Ajouter un profil avec filename_pattern
    from app.schemas.ingestion_profile import DetectionRules, IngestionProfile
    p_specific = IngestionProfile(
        profile_id="specific_gamma",
        name="Specific Gamma",
        priority=10,
        confidence_threshold=3.0,
        provider_code="PROV_C",
        detection=DetectionRules(
            extensions=[".pdf"],
            filename_pattern="SPECIFIC_REPORT",
            required_text=["SIGNATURE_ALPHA"],
        ),
        mapping=[],
    )
    abstract_manager.profiles["specific_gamma"] = p_specific

    matcher = ProfileMatcher(abstract_manager)
    profile, report = matcher.match(
        "SPECIFIC_REPORT_2026.pdf",
        text_content="SIGNATURE_ALPHA found"
    )
    # specific_gamma a filename pattern +5 → score plus haut que generic_alpha
    assert profile is not None
    assert profile.profile_id == "specific_gamma"
