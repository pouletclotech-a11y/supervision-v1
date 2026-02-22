import pytest
import pytz
from datetime import datetime
from app.parsers.excel_parser import ExcelParser
from app.parsers.pdf_parser import PdfParser
from app.ingestion.models import NormalizedEvent

def test_excel_timezone_conversion():
    parser = ExcelParser()
    # Mock a datetime found in the file: 2026-02-22 10:00:00
    naive_dt = datetime(2026, 2, 22, 10, 0, 0)
    
    # 1. Test with Paris (UTC+1 in Feb)
    utc_dt_paris = parser._normalize_timestamp(naive_dt, "Europe/Paris")
    # 10:00 Paris -> 09:00 UTC
    assert utc_dt_paris.hour == 9
    assert utc_dt_paris.tzinfo == pytz.UTC
    
    # 2. Test with Dubai (UTC+4)
    utc_dt_dubai = parser._normalize_timestamp(naive_dt, "Asia/Dubai")
    # 10:00 Dubai -> 06:00 UTC
    assert utc_dt_dubai.hour == 6
    assert utc_dt_dubai.tzinfo == pytz.UTC

def test_pdf_timezone_conversion():
    parser = PdfParser()
    naive_dt = datetime(2026, 2, 22, 10, 0, 0)
    
    # Paris (UTC+1)
    utc_dt = parser._normalize_timestamp(naive_dt, "Europe/Paris")
    assert utc_dt.hour == 9
    
    # New York (UTC-5 in Feb)
    utc_dt_ny = parser._normalize_timestamp(naive_dt, "America/New_York")
    # 10:00 NY -> 15:00 UTC
    assert utc_dt_ny.hour == 15
