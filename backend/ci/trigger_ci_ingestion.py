import asyncio
import os
import sys
import re
from pathlib import Path
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import ImportLog, MonitoringProvider
from app.services.repository import EventRepository, AdminRepository
from app.parsers.factory import ParserFactory
from app.ingestion.worker import detect_file_format
from app.services.pdf_match_service import PdfMatchService
from app.parsers.pdf_parser import PdfParser
from app.ingestion.profile_manager import ProfileManager

profile_manager = ProfileManager()

async def trigger_ingestion(file_path_str):
    print(f"Triggering CI ingestion for: {file_path_str}")
    file_path = Path(file_path_str)
    if not file_path.exists():
        print(f"ERROR: File not found at {file_path}")
        return False
        
    async with AsyncSessionLocal() as db:
        repo = EventRepository(db)
        admin_repo = AdminRepository(db)
        await profile_manager.load_profiles(db)
        
        # 1. Create a "DUMMY" ImportLog for CI (or find if exists)
        filename = file_path.name
        stmt = select(ImportLog).where(ImportLog.filename == filename).order_by(ImportLog.created_at.desc()).limit(1)
        res = await db.execute(stmt)
        imp = res.scalar_one_or_none()
        
        if not imp:
            print(f"Creating new ImportLog for {filename}")
            imp = ImportLog(filename=filename, status="PENDING")
            db.add(imp)
            await db.flush()
            
        print(f"Using Import ID {imp.id}")
        
        # 2. Mimic Replay Logic (Cleanup + Parse + Store)
        kind = detect_file_format(file_path)
        
        # Map provider by filename hint
        provider_code = "SPGO" if "SPGO" in filename else "CORS" if "CORS" in filename else "UNKNOWN"
        stmt_p = select(MonitoringProvider).where(MonitoringProvider.code == provider_code)
        monitoring_provider = (await db.execute(stmt_p)).scalar_one_or_none()
        
        if monitoring_provider:
             imp.provider_id = monitoring_provider.id

        profiles = profile_manager.list_profiles()
        matched_profile = None
        for p in sorted(profiles, key=lambda x: x.priority, reverse=True):
            if p.format_kind == kind and (not p.provider_code or p.provider_code == provider_code):
                pattern = p.detection.filename_pattern or p.filename_regex
                if not pattern or re.search(pattern, filename, re.IGNORECASE):
                    matched_profile = p; break
        
        if not matched_profile:
            print(f"ERROR: No profile matched for {filename}")
            return False
            
        print(f"Matched Profile: {matched_profile.profile_id}")
        
        parser = ParserFactory.get_parser_by_kind(matched_profile.format_kind)
        await admin_repo.delete_import_data(imp.id)
        
        parsed_events = parser.parse(
            str(file_path),
            source_timezone=matched_profile.source_timezone,
            parser_config={
                "mapping": matched_profile.mapping,
                "action_config": matched_profile.action_config
            }
        )
        
        db_evts = await repo.create_batch(parsed_events, import_id=imp.id)
        
        # PDF Match (optional for CI if companion exists)
        pdf_match_report = {}
        potential_pdf = file_path.with_suffix('.pdf')
        if potential_pdf.exists() and monitoring_provider:
            print("Found PDF companion, matching...")
            pdf_parser = PdfParser()
            pdf_events = pdf_parser.parse(str(potential_pdf))
            pdf_matcher = PdfMatchService()
            provider_conf = {
                "code": monitoring_provider.code,
                "pdf_warning_threshold": monitoring_provider.pdf_warning_threshold,
                "pdf_critical_threshold": monitoring_provider.pdf_critical_threshold,
                "pdf_ignore_case": monitoring_provider.pdf_ignore_case,
                "pdf_ignore_accents": monitoring_provider.pdf_ignore_accents
            }
            pdf_match_report = pdf_matcher.calculate_match_report(db_evts, pdf_events, provider_conf)
            imp.archive_path_pdf = str(potential_pdf)

        imp.status = "SUCCESS"
        imp.events_count = len(db_evts)
        imp.quality_report = getattr(parser, 'last_metrics', {})
        imp.pdf_match_report = pdf_match_report
        imp.archive_path = str(file_path)
        
        await db.commit()
        print(f"CI Ingestion Complete for {filename}. Events: {len(db_evts)}")
        return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trigger_ci_ingestion.py <file_path>")
        sys.exit(1)
    
    asyncio.run(trigger_ingestion(sys.argv[1]))
