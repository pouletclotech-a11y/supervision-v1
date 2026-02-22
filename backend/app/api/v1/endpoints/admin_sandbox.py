import os
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import deps
from app.db.models import User
from app.ingestion.profile_manager import ProfileManager
from app.ingestion.profile_matcher import ProfileMatcher
from app.parsers.factory import ParserFactory
from app.ingestion.utils import get_file_probe
from app.schemas.admin import SandboxResultOut
from app.ingestion.normalizer import Normalizer
from app.ingestion.models import NormalizedEvent

logger = logging.getLogger("admin-sandbox")
router = APIRouter()

# Global profile engine for sandbox
profile_manager = ProfileManager()
normalizer = Normalizer()

@router.post("/ingest", response_model=SandboxResultOut)
async def sandbox_ingest(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Simulation of ingestion. "No-Write" safety.
    Returns the match report and a preview of extracted events.
    """
    # 1. Reload profiles from DB for current state
    await profile_manager.load_profiles(db)
    matcher = ProfileMatcher(profile_manager)
    
    # 2. Save temporarily
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
        
    try:
        # 3. Match
        headers, text = get_file_probe(tmp_path)
        profile, match_report = matcher.match(tmp_path, headers=headers, text_content=text)
        
        is_matched = profile is not None
        matched_id = profile.profile_id if is_matched else None
        
        events_preview = []
        total_events = 0
        
        if is_matched:
            # 4. Parse (Simulated)
            ext = tmp_path.suffix.lower()
            parser = ParserFactory.get_parser(ext)
            if parser:
                try:
                    events = parser.parse(str(tmp_path), source_timezone=profile.source_timezone)
                    if isinstance(events, list):
                        total_events = len(events)
                        # Normalize and prepare preview (first 10)
                        for e in events[:10]:
                            normalizer.normalize(e)
                            # Convert to dict for JSON response
                            events_preview.append(e.model_dump())
                    else:
                        events_preview = [{"error": "Parser did not return a list of events"}]
                except Exception as parse_err:
                    logger.error(f"Sandbox parse error: {parse_err}")
                    events_preview = [{"error": f"Parsing failed: {str(parse_err)}"}]
            else:
                events_preview = [{"error": f"No parser found for {ext}"}]

        return SandboxResultOut(
            matched_profile_id=matched_id,
            best_candidate_id=match_report.get("best_candidate_id"),
            best_score=match_report.get("best_score", 0.0),
            threshold=profile.confidence_threshold if is_matched else 2.0,
            is_matched=is_matched,
            events_preview=events_preview,
            total_events=total_events
        )
        
    finally:
        if tmp_path.exists():
            os.remove(tmp_path)
