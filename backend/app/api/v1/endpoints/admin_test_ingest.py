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
from app.parsers.tsv_parser import TsvParser as SpgoTsvParser
from app.parsers.pdf_parser import PdfParser as SpgoPdfParser
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

        # 5. Parsing (Isolated Provider Logic)
        if provider_code == "SPGO":
            # SPGO Specific Logic
            tsv_parser = SpgoTsvParser()
            excel_events = tsv_parser.parse(str(excel_path), source_timezone="Europe/Paris")
            
            pdf_events = []
            if pdf_path:
                pdf_parser = SpgoPdfParser()
                pdf_events = pdf_parser.parse(str(pdf_path), source_timezone="Europe/Paris")
        else:
            raise HTTPException(status_code=400, detail="Only SPGO is currently supported for strict test ingestion")

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
        imp.quality_report = getattr(tsv_parser, 'last_metrics', {})
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

    except Exception as e:
        await db.rollback()
        logger.error(f"Test ingestion failed: {e}")
        # Cleanup on failure
        if excel_path and excel_path.exists(): excel_path.unlink()
        if pdf_path and pdf_path.exists(): pdf_path.unlink()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
