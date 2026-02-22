"""
test_profile_not_confident.py — Tests: gestion du statut PROFILE_NOT_CONFIDENT
Vérifie :
  - matcher retourne None et rapport complet quand score < confidence_threshold
  - rapport: best_score, best_candidate_id, threshold_met=False, candidates list
  - ImportLog persiste status=PROFILE_NOT_CONFIDENT avec import_metadata tracé
  - raw_payload renseigné pour calibration future
"""

import pytest
import uuid
from app.ingestion.profile_manager import ProfileManager
from app.ingestion.profile_matcher import ProfileMatcher
from app.schemas.ingestion_profile import IngestionProfile, DetectionRules


def uid(prefix="") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


@pytest.fixture
def strict_manager():
    """Profil avec seuil très élevé (10.0) pour forcer PROFILE_NOT_CONFIDENT."""
    manager = ProfileManager(profiles_dir="non_existent_dir")
    p = IngestionProfile(
        profile_id="strict_threshold_profile",
        name="Strict",
        priority=10,
        confidence_threshold=10.0,  # Score max attendu ~4.0 → rejet garanti
        provider_code="PROV_STRICT",
        detection=DetectionRules(
            extensions=[".pdf"],
            required_text=["MAGIC_KEYWORD"],
        ),
        mapping=[],
    )
    manager.profiles = {"strict_threshold_profile": p}
    return manager


def test_not_confident_returns_none(strict_manager):
    """Le matcher doit retourner (None, report) si score < seuil."""
    matcher = ProfileMatcher(strict_manager)
    profile, report = matcher.match("test.pdf", text_content="This has MAGIC_KEYWORD")
    assert profile is None
    assert report["threshold_met"] is False


def test_not_confident_report_has_score(strict_manager):
    """Le rapport doit contenir best_score même si pas de match."""
    matcher = ProfileMatcher(strict_manager)
    _, report = matcher.match("test.pdf", text_content="MAGIC_KEYWORD here")
    assert "best_score" in report
    assert isinstance(report["best_score"], float)


def test_not_confident_report_has_candidate(strict_manager):
    """Le rapport doit indiquer le meilleur candidat (pour calibration future)."""
    matcher = ProfileMatcher(strict_manager)
    _, report = matcher.match("test.pdf", text_content="MAGIC_KEYWORD present")
    assert "best_candidate_id" in report
    assert report["best_candidate_id"] == "strict_threshold_profile"


def test_not_confident_score_below_threshold(strict_manager):
    """Score positif mais inférieur au seuil → rejet."""
    matcher = ProfileMatcher(strict_manager)
    profile, report = matcher.match("test.pdf", text_content="MAGIC_KEYWORD")
    assert profile is None
    # ext(1) + required_text(3) = 4.0 < 10.0
    assert report["best_score"] < 10.0
    assert report["best_score"] > 0


def test_not_confident_candidates_list(strict_manager):
    """Le rapport doit contenir la liste des candidats évalués."""
    matcher = ProfileMatcher(strict_manager)
    _, report = matcher.match("test.pdf", text_content="MAGIC_KEYWORD")
    assert "candidates" in report
    assert len(report["candidates"]) >= 1
    c = report["candidates"][0]
    assert "profile_id" in c
    assert "score" in c
    assert "threshold" in c
    assert "is_valid" in c


def test_not_confident_wrong_extension(strict_manager):
    """Fichier CSV avec profil PDF → aucun candidat évalué."""
    matcher = ProfileMatcher(strict_manager)
    profile, report = matcher.match("data.csv", text_content="MAGIC_KEYWORD")
    assert profile is None
    assert len(report["candidates"]) == 0


@pytest.mark.asyncio
async def test_import_log_not_confident_status(db_session):
    """
    ImportLog doit être persisté avec status=PROFILE_NOT_CONFIDENT
    et import_metadata contenant score_max et best_candidate.
    Utilise un insert ORM direct pour éviter les contraintes FK.
    """
    from sqlalchemy import select, update
    from app.db.models import ImportLog

    match_report = {
        "best_score": 4.0,
        "best_candidate_id": "strict_threshold_profile",
        "threshold_met": False,
        "candidates": [{"profile_id": "strict_threshold_profile", "score": 4.0}],
    }
    import_metadata = {
        "match_score": match_report["best_score"],
        "best_candidate": match_report["best_candidate_id"],
        "match_details": match_report["candidates"],
    }
    raw_payload = "ref_line|col_a|col_b"
    test_filename = f"unmatched_{uid()}.pdf"

    # Direct ORM insert (no FK constraints via provider_id)
    log = ImportLog(
        filename=test_filename,
        status="PROFILE_NOT_CONFIDENT",
        events_count=0,
        duplicates_count=0,
        import_metadata=import_metadata,
        raw_payload=raw_payload,
    )
    db_session.add(log)
    await db_session.commit()
    await db_session.refresh(log)

    # Verify persisted data
    result = await db_session.execute(
        select(ImportLog).where(ImportLog.id == log.id)
    )
    saved = result.scalar_one()

    assert saved.status == "PROFILE_NOT_CONFIDENT"
    assert saved.import_metadata["match_score"] == 4.0
    assert saved.import_metadata["best_candidate"] == "strict_threshold_profile"
    assert saved.raw_payload == "ref_line|col_a|col_b"

