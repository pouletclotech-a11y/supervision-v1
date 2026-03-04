import asyncio
import os
import sys
import argparse
from pathlib import Path
from sqlalchemy import select, delete
from app.db.session import AsyncSessionLocal
from app.db.models import ImportLog, MonitoringProvider, Event
from app.parsers.tsv_parser import TsvParser as SpgoTsvParser
from app.parsers.pdf_parser import PdfParser as SpgoPdfParser
from app.services.pdf_match_service import PdfMatchService
from app.services.repository import EventRepository

# Ensure SPGO-only focus
PROVIDER_CODE = "SPGO"

async def run_pair_ingestion(excel_path: str, pdf_path: str, strict: bool):
    print(f"=== STRICT SPGO PAIR INGESTION TOOL ===")
    
    excel_file = Path(excel_path)
    pdf_file = Path(pdf_path)
    
    # 1. Check file existence (Exit 2)
    if not excel_file.exists() or not pdf_file.exists():
        if not excel_file.exists(): print(f"ERROR: Excel file not found: {excel_path}")
        if not pdf_file.exists(): print(f"ERROR: PDF file not found: {pdf_path}")
        sys.exit(2)

    async with AsyncSessionLocal() as db:
        # 1. Get Provider (SPGO ONLY)
        stmt_p = select(MonitoringProvider).where(MonitoringProvider.code == PROVIDER_CODE)
        provider = (await db.execute(stmt_p)).scalar_one_or_none()
        if not provider:
            print(f"ERROR: Provider {PROVIDER_CODE} not found in DB.")
            sys.exit(1)
            
        # 2. Setup ImportLog (MANUAL_VALIDATION)
        # Cleanup previous run for identical filename to be idempotent
        stmt_cleanup = select(ImportLog).where(ImportLog.filename == excel_file.name)
        old_imp = (await db.execute(stmt_cleanup)).scalars().first()
        if old_imp:
            print(f"Cleaning up previous import ID {old_imp.id}...")
            await db.execute(delete(Event).where(Event.import_id == old_imp.id))
            await db.delete(old_imp)
            await db.commit()

        imp = ImportLog(
            filename=excel_file.name,
            status="MANUAL_VALIDATION",
            provider_id=provider.id,
            archive_path=str(excel_file),
            archive_path_pdf=str(pdf_file),
            import_metadata={
                "source": "local_pair_tool",
                "provider": PROVIDER_CODE,
                "strict_mode": strict
            }
        )
        db.add(imp)
        await db.flush()
        import_id = imp.id
        print(f"Created Import ID: {import_id} (Status: MANUAL_VALIDATION)")

        # 3. Parse Excel (SpgoTsvParser logic)
        print("Parsing Excel (SpgoTsvParser)...")
        tsv_parser = SpgoTsvParser()
        # Explicitly passing Europe/Paris as it's standard for SPGO
        excel_events = tsv_parser.parse(
            str(excel_file),
            source_timezone="Europe/Paris"
        )
        
        # 4. Parse PDF (SpgoPdfParser Mirror Logic)
        print("Parsing PDF (SpgoPdfParser Mirror)...")
        pdf_parser = SpgoPdfParser()
        pdf_events = pdf_parser.parse(
            str(pdf_file),
            source_timezone="Europe/Paris"
        )
        
        # 5. Store Excel Events
        repo = EventRepository(db)
        db_evts = await repo.create_batch(excel_events, import_id=import_id)
        
        # 6. Matching Service
        print("Calculating PDF Match Report...")
        matcher = PdfMatchService()

        # DEBUG: Print some keys
        def get_sample_keys(evts, name, limit=3):
            print(f"Sample keys for {name}:")
            for e in evts[:limit]:
                # Directly simulate key building logic to see what's wrong
                site = getattr(e, 'site_code', '')
                evt_dt = getattr(e, 'timestamp', getattr(e, 'time', None))
                dt = evt_dt.strftime("%Y-%m-%d %H:%M:%S") if evt_dt else ""
                code = (getattr(e, 'raw_code', "") or "").strip()
                action = (getattr(e, 'status', getattr(e, 'severity', "")) or "").strip().upper()
                print(f"  {site}|{dt}|{code}|{action}")

        get_sample_keys(db_evts, "Excel (DB)")
        get_sample_keys(pdf_events, "PDF (Parsed)")

        provider_conf = {
            "code": provider.code,
            "pdf_warning_threshold": provider.pdf_warning_threshold,
            "pdf_critical_threshold": provider.pdf_critical_threshold,
            "pdf_ignore_case": provider.pdf_ignore_case,
            "pdf_ignore_accents": provider.pdf_ignore_accents
        }
        match_report = matcher.calculate_match_report(db_evts, pdf_events, provider_conf)
        
        imp.quality_report = getattr(tsv_parser, 'last_metrics', {})
        imp.pdf_match_report = match_report
        imp.events_count = len(db_evts)
        
        await db.commit()
        
        # 7. Metrics calculation
        counts = {}
        for e in excel_events:
            t = e.normalized_type or "UNKNOWN"
            counts[t] = counts.get(t, 0) + 1
            
        security_total = sum(v for k, v in counts.items() if k != "OPERATOR_NOTE")
        operator_total = counts.get("OPERATOR_NOTE", 0)
        total = len(excel_events)
        time_null = sum(1 for e in db_evts if e.time is None)
        ratio = match_report.get('match_ratio', 0)
        
        print(f"\nRESULTS for Import {import_id}:")
        print(f"- Security Events: {security_total}")
        print(f"- Operator Notes : {operator_total}")
        print(f"- Total Events   : {total}")
        print(f"- Time Null      : {time_null}")
        print(f"- PDF Match Ratio: {ratio*100:.2f}% ({match_report.get('status')})")
        
        # 8. EXIT STRATEGY
        if strict:
            # security=157, operator=162, total=319, time_null=0
            if (security_total == 157 and operator_total == 162 and 
                total == 319 and time_null == 0 and ratio > 0):
                print("\nSTRICT BASELINE: PASSED")
                os._exit(0)
            else:
                print("\nSTRICT BASELINE: FAILED")
                os._exit(1)
        else:
            # security=157, time_null=0, pdf_match_report non null
            if security_total == 157 and time_null == 0 and match_report:
                print("\nVALIDATION: PASSED")
                os._exit(0)
            else:
                print("\nVALIDATION: FAILED")
                os._exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strict SPGO Ingestion Tool.")
    parser.add_argument("--excel", required=True, help="Path to Excel file")
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--strict-baseline", action="store_true", help="Enforce 157/162/319")
    
    args = parser.parse_args()
    # Use os._exit() in run_pair_ingestion to avoid catching SystemExit in asyncio
    asyncio.run(run_pair_ingestion(args.excel, args.pdf, args.strict_baseline))
