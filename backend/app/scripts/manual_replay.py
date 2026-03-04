import asyncio
import logging
import re
from pathlib import Path
from datetime import datetime, timedelta
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("manual-replay")

async def run_manual_replay():
    async with AsyncSessionLocal() as db:
        repo = EventRepository(db)
        admin_repo = AdminRepository(db)
        
        # 1. Fetch Golden References for validation
        stmt = select(ImportLog).where(
            ImportLog.id.in_([646, 1627])
        )
        result = await db.execute(stmt)
        imports = result.scalars().all()
        
        if not imports:
            logger.info("No imports marked as REPLAY_REQUESTED found.")
            return

        await profile_manager.load_profiles(db)

        for imp in imports:
            logger.info(f"Processing replay for import {imp.id} ({imp.filename})")
            try:
                if not imp.archive_path:
                    logger.warning(f"No archive path for import {imp.id}")
                    continue
                
                file_path = Path(imp.archive_path)
                # Handle path conversion if needed (docker vs host)
                if not file_path.exists():
                     # try /app prefix inside container
                     file_path = Path("/app") / str(file_path).lstrip('/')
                
                if not file_path.exists():
                    logger.error(f"File not found: {file_path}")
                    continue

                # Parse & Update
                kind = detect_file_format(file_path)
                monitoring_provider = await repo.get_monitoring_provider(imp.provider_id)
                provider_code = monitoring_provider.code if monitoring_provider else "UNKNOWN"
                
                profiles = profile_manager.list_profiles()
                matched_profile = None
                for p in sorted(profiles, key=lambda x: x.priority, reverse=True):
                    # extension check (only if profile declares extensions)
                    ext = file_path.suffix.lower()
                    if p.detection.extensions and ext not in p.detection.extensions:
                         continue

                    if p.format_kind == kind and (not p.provider_code or p.provider_code == provider_code):
                        pattern = p.detection.filename_pattern or p.filename_regex
                        if pattern:
                            if re.search(pattern, imp.filename, re.IGNORECASE):
                                matched_profile = p; break
                        else:
                            matched_profile = p; break
                
                if not matched_profile:
                    logger.warning(f"No profile matched for import {imp.id} (kind={kind}, provider={provider_code})")
                    continue
                
                logger.info(f"Matched profile: {matched_profile.profile_id} for {imp.filename}")

                parser = ParserFactory.get_parser_by_kind(matched_profile.format_kind)
                if not parser:
                    logger.error(f"No parser for kind {matched_profile.format_kind}")
                    continue

                # Transactional Clear & Parse
                logger.info(f"Clearing old data for import {imp.id}")
                await admin_repo.delete_import_data(imp.id)
                
                logger.info(f"Parsing file {file_path}")
                parsed_events = parser.parse(
                    str(file_path),
                    source_timezone=matched_profile.source_timezone,
                    parser_config={
                        "mapping": matched_profile.mapping,
                        "action_config": matched_profile.action_config
                    }
                )
                
                logger.info(f"Inserting {len(parsed_events)} events")
                db_evts = await repo.create_batch(parsed_events, import_id=imp.id)
                
                # PDF Match
                pdf_match_report = {}
                potential_pdf = file_path.with_suffix('.pdf')
                if potential_pdf.exists() and monitoring_provider:
                    logger.info(f"Found PDF companion, starting match report")
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
                
                # Store Metrics & Update
                imp.status = "SUCCESS"
                imp.events_count = len(db_evts)
                imp.quality_report = getattr(parser, 'last_metrics', {})
                imp.pdf_match_report = pdf_match_report
                
                logger.info(f"Committing import {imp.id}")
                await db.commit()
                logger.info(f"Import {imp.id} replayed successfully. Events: {len(db_evts)}")

            except Exception as e:
                logger.error(f"Failed to replay import {imp.id}: {e}", exc_info=True)
                await db.rollback()
                continue

            # NEW: Archive Path PDF persistence
            if not imp.archive_path_pdf and potential_pdf.exists():
                imp.archive_path_pdf = str(potential_pdf)

if __name__ == "__main__":
    asyncio.run(run_manual_replay())
