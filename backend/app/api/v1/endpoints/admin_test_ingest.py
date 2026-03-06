import os
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import deps
from app.db.models import User, ImportLog, MonitoringProvider
from app.schemas.admin import TestIngestResultOut
from app.parsers.factory import ParserFactory
from app.ingestion.profile_manager import ProfileManager
from app.ingestion.profile_matcher import ProfileMatcher
from app.ingestion.utils import detect_file_format, get_file_probe
from app.services.pdf_match_service import PdfMatchService
from app.services.repository import EventRepository

logger = logging.getLogger("admin-test-ingest")
router = APIRouter()

# Configuration
TEST_UPLOAD_DIR = Path("/app/data/test_uploads")
ALLOWED_EXTENSIONS_EXCEL = {".xls", ".xlsx", ".tsv"}
ALLOWED_EXTENSIONS_PDF = {".pdf"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

def validate_file(file: UploadFile, allowed_ext: set):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Invalid file extension: {suffix}")
    # Size check would require reading or checking headers, but UploadFile doesn't expose size easily before reading
    # For now we rely on the container/reverse proxy if present, or add a read-based check if critical.

@router.post("/test-ingest", response_model=TestIngestResultOut)
async def admin_test_ingest(
    provider_code: str = Form(...),
    excel_file: UploadFile = File(...),
    pdf_file: Optional[UploadFile] = File(None),
    strict_baseline: bool = Form(False),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Manually trigger a test ingestion for a specific provider.
    Saves files, parses them, and returns counts + match report.
    """
    # 1. Validation signatures
    validate_file(excel_file, ALLOWED_EXTENSIONS_EXCEL)
    if pdf_file:
        validate_file(pdf_file, ALLOWED_EXTENSIONS_PDF)

    # 2. Get Provider
    stmt_p = select(MonitoringProvider).where(MonitoringProvider.code == provider_code)
    provider = (await db.execute(stmt_p)).scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider {provider_code} not found")

    # 3. Create temp directory
    TEST_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    excel_path = None
    pdf_path = None

    try:
        # Read and check size for Excel
        content_excel = await excel_file.read()
        if len(content_excel) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"Excel file too large (> {MAX_FILE_SIZE/(1024*1024)}MB)")
        
        # Save Excel securely
        with tempfile.NamedTemporaryFile(delete=False, dir=TEST_UPLOAD_DIR, suffix=Path(excel_file.filename).suffix) as tmp_excel:
            tmp_excel.write(content_excel)
            excel_path = Path(tmp_excel.name)

        # Handle PDF if present
        if pdf_file:
            content_pdf = await pdf_file.read()
            if len(content_pdf) > MAX_FILE_SIZE:
                raise HTTPException(status_code=400, detail=f"PDF file too large (> {MAX_FILE_SIZE/(1024*1024)}MB)")
            
            with tempfile.NamedTemporaryFile(delete=False, dir=TEST_UPLOAD_DIR, suffix=Path(pdf_file.filename).suffix) as tmp_pdf:
                tmp_pdf.write(content_pdf)
                pdf_path = Path(tmp_pdf.name)

        # 4. Create ImportLog
        imp = ImportLog(
            filename=excel_file.filename,
            status="MANUAL_VALIDATION",
            provider_id=provider.id,
            archive_path=str(excel_path),
            archive_path_pdf=str(pdf_path) if pdf_path else None,
            import_metadata={
                "source": "admin_test_upload",
                "provider": provider_code,
                "strict_mode": strict_baseline,
                "user_id": current_user.id
            }
        )
        db.add(imp)
        await db.flush()

        # 5. Ingestion Pipeline (Production-Grade Resolution)
        # Use existing ProfileMatcher to find the best profile for this file
        profile_manager = ProfileManager()
        await profile_manager.load_profiles(db)
        profile_matcher = ProfileMatcher(profile_manager)
        
        detected_kind = detect_file_format(excel_path)
        headers_probe, text_probe = get_file_probe(excel_path)
        
        matched_profile, match_report = profile_matcher.match(
            excel_path,
            detected_format=detected_kind,
            headers=headers_probe,
            text_content=text_probe
        )
        
        # Security check: If provider_id of profile doesn't match selected provider_code
        # we still proceed but we warn or force re-classification like in worker.py
        if matched_profile and matched_profile.provider_code and matched_profile.provider_code != provider_code:
            logger.info(f"[TestIngest] Re-classified via profile: {provider_code} -> {matched_profile.provider_code}")
        
        if not matched_profile:
            raise HTTPException(status_code=400, detail=f"No profile matched for file {excel_file.filename} (detected_kind={detected_kind})")

        # 6. Parsing
        parser = ParserFactory.get_parser_by_kind(matched_profile.format_kind)
        if not parser:
            # Fallback to extension
            parser = ParserFactory.get_parser(excel_path.suffix)
            
        if not parser:
            raise HTTPException(status_code=400, detail=f"No parser found for kind {matched_profile.format_kind}")

        # Convert List[MappingRule] to Dict for parsers
        mapping_dict = {m.target: m.source for m in matched_profile.mapping}
        
        excel_events = parser.parse(
            str(excel_path), 
            source_timezone="Europe/Paris",
            parser_config={
                "mapping": mapping_dict,
                "action_config": matched_profile.action_config,
                **(matched_profile.parser_config or {})
            }
        )
        
        pdf_events = []
        if pdf_path:
            # For PDF, we try to use the PDF parser if it matches the profile or extension
            pdf_parser = ParserFactory.get_parser(".pdf")
            if pdf_parser:
                pdf_events = pdf_parser.parse(str(pdf_path), source_timezone="Europe/Paris")

        # 6. Store Data
        repo = EventRepository(db)
        db_evts = await repo.create_batch(excel_events, import_id=imp.id)

        # 7. Match Report
        match_report = {}
        if pdf_path and pdf_events:
            matcher = PdfMatchService()
            provider_conf = {
                "code": provider.code,
                "pdf_warning_threshold": provider.pdf_warning_threshold,
                "pdf_critical_threshold": provider.pdf_critical_threshold,
                "pdf_ignore_case": provider.pdf_ignore_case,
                "pdf_ignore_accents": provider.pdf_ignore_accents
            }
            match_report = matcher.calculate_match_report(db_evts, pdf_events, provider_conf)

        # Update ImportLog
        # Try to get metrics from parser if available (metrics are not standardized yet across all parsers)
        metrics = getattr(parser, 'last_metrics', {})
        imp.quality_report = metrics
        imp.pdf_match_report = match_report
        imp.events_count = len(db_evts)
        
        await db.commit()

        # 8. Result Summary
        counts = {"security": 0, "operator": 0}
        for e in excel_events:
            if e.normalized_type == "OPERATOR_NOTE":
                counts["operator"] += 1
            else:
                counts["security"] += 1
        
        time_null = sum(1 for e in db_evts if e.time is None)
        ratio = match_report.get('match_ratio', 0.0)

        res_status = "SUCCESS"
        if strict_baseline:
            if provider_code != "SPGO":
                 raise HTTPException(status_code=400, detail="Strict baseline check is only supported for SPGO provider")
            if counts["security"] != 157 or counts["operator"] != 162 or time_null > 0:
                res_status = "BASELINE_FAILED"

        return TestIngestResultOut(
            import_id=imp.id,
            security_count=counts["security"],
            operator_count=counts["operator"],
            total_count=len(excel_events),
            time_null=time_null,
            pdf_match_ratio=ratio,
            status=res_status
        )

    except HTTPException:
        await db.rollback()
        if excel_path and excel_path.exists(): excel_path.unlink()
        if pdf_path and pdf_path.exists(): pdf_path.unlink()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Test ingestion failed: {e}")
        # Cleanup on failure
        if excel_path and excel_path.exists(): excel_path.unlink()
        if pdf_path and pdf_path.exists(): pdf_path.unlink()
        raise HTTPException(status_code=400, detail=f"Ingestion failed: {str(e)}")
