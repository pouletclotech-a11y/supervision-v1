import logging
import os
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.ingestion.worker import detect_file_format
from app.parsers.factory import ParserFactory
from app.ingestion.profile_manager import ProfileManager
from app.db.models import MonitoringProvider, DBIngestionProfile
from app.schemas.response_models import ImportQualitySummary

logger = logging.getLogger("preview-parse")
profile_manager = ProfileManager()

class PreviewParseService:
    @staticmethod
    async def preview_file(
        db: AsyncSession, 
        file_path: Path, 
        provider_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Preview a file: detect format, find profile, parse in-memory, return summary.
        NO EVENTS ARE CREATED IN DB.
        """
        filename = file_path.name
        detected_kind = detect_file_format(file_path)
        
        await profile_manager.load_profiles(db)
        profiles = profile_manager.list_profiles()
        
        # 1. Match Profile
        matched_profile = None
        sorted_profiles = sorted(profiles, key=lambda x: x.priority, reverse=True)
        
        for p in sorted_profiles:
            if p.format_kind != detected_kind:
                continue
            
            # Simple matching logic similar to worker
            filename_match = False
            if p.filename_regex and re.search(p.filename_regex, filename, re.IGNORECASE):
                filename_match = True
            
            provider_match = (provider_code and p.provider_code == provider_code)
            
            if filename_match or provider_match:
                matched_profile = p
                break
        
        if not matched_profile:
            # Fallback to any profile matching the kind if no specific match
            for p in sorted_profiles:
                if p.format_kind == detected_kind:
                    matched_profile = p
                    break

        if not matched_profile:
            return {
                "success": False,
                "error": f"No profile found for kind {detected_kind}",
                "detected_kind": detected_kind
            }

        # 2. Parse File
        parser = ParserFactory.get_parser_by_kind(matched_profile.format_kind)
        if not parser:
             return {"success": False, "error": f"No parser for {matched_profile.format_kind}"}

        parsed_events = parser.parse(
            str(file_path),
            source_timezone=matched_profile.source_timezone,
            parser_config={
                "mapping": matched_profile.mapping,
                "action_config": matched_profile.action_config
            }
        )
        
        # 3. Build Quality Summary
        metrics = getattr(parser, 'last_metrics', {})
        total_rows = metrics.get('rows_detected', 0)
        created_count = len(parsed_events)
        
        quality_summary = {
            "created_ratio": round(created_count / total_rows, 2) if total_rows > 0 else 0,
            "skipped_count": metrics.get('events_skipped_count', 0),
            "top_reasons": list(metrics.get('skipped_reasons', {}).keys())[:3],
            "status": "OK",
            "pdf_match_ratio": None # PDF matching requires companion file, skipped for simple preview
        }
        
        # Deterministic status
        if quality_summary["created_ratio"] < 0.4:
            quality_summary["status"] = "CRIT"
        elif quality_summary["created_ratio"] < 0.8:
            quality_summary["status"] = "WARN"

        return {
            "success": True,
            "filename": filename,
            "detected_kind": detected_kind,
            "profile_matched": matched_profile.profile_id,
            "quality_summary": quality_summary,
            "sample_events": [e[:3] for e in [parsed_events]][0][:5], # First 5 events
            "metrics": metrics
        }
