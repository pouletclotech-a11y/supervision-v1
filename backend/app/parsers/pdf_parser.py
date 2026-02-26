import re
import pytz
from datetime import datetime
from typing import List
from app.parsers.base import BaseParser
from app.ingestion.models import NormalizedEvent
import logging
from app.core.config import settings

logger = logging.getLogger("pdf-parser")

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

class PdfParser(BaseParser):
    """
    Parses PDF reports (YPSILON.pdf).
    Strategy: Extract text line by line and use Regex State Machine similarly to ExcelParser.
    """

    def supported_extensions(self) -> List[str]:
        return ['.pdf']

    def parse(self, file_path: str, source_timezone: str = "UTC", parser_config: dict = None) -> List[NormalizedEvent]:
        if pdfplumber is None:
            error_msg = "pdfplumber module is not installed. Impossible to parse PDF."
            logger.error(error_msg)
            raise ImportError(error_msg)

        events = []
        current_site_code = None
        current_site_name = None
        current_site_secondary = None
        last_event_date = None
        
        # Regex Patterns
        # Site: "C-69000 NOM CLIENT" or "00032009 NOM CLIENT" or "SITE : 00032308 NOM CLIENT"
        RE_SITE_CODE_C = r'^(?:SITE\s*:\s*)?(C-\d+)\s+(.*)$'
        RE_SITE_CODE_NUM = r'^(?:SITE\s*:\s*)?(\d{8,})\s+(.*)$'
        
        # Event Header: "Mar 27/01/2026 16:24:25 TYPE" OR "LU02/02/2026 09:37:02..."
        # Regex updated to capture Day, Date, Time, and potential Code prefix
        RE_EVENT_HEADER = r'^(Lun|Mar|Mer|Jeu|Ven|Sam|Dim|LU|MA|ME|JE|VE|SA|DI|Di|Lu|Ma|Me|Je|Ve|Sa)\s*(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2}:\d{2})\s*(.*)$'
        
        # Sub Event: "16:24:28 Message..."
        RE_SUB_EVENT = r'^(\d{2}:\d{2}:\d{2})\s+(.*)$'
        
        try:
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                total_text_len = 0
                debug_lines = []
                
                logger.info(f"PDF Debug: Starting parse of {file_path} (Pages: {total_pages})")

                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if not text: 
                        continue
                    
                    text_len = len(text)
                    total_text_len += text_len
                    
                    # Capture first 20 lines for debug
                    if len(debug_lines) < 20:
                        lines = text.split('\n')
                        debug_lines.extend(lines[:20 - len(debug_lines)])

                    for line in text.split('\n'):
                        line = line.strip()
                        if not line: continue
                        
                        # 1. Detect Site
                        match_c = re.match(RE_SITE_CODE_C, line)
                        match_num = re.match(RE_SITE_CODE_NUM, line)
                        
                        if match_c:
                            current_site_code = match_c.group(1)
                            current_site_name = match_c.group(2).strip()
                            current_site_secondary = None
                            continue
                        elif match_num:
                            # If line explicitly says "SITE :", it's a primary site reset
                            is_site_header = line.upper().startswith("SITE")
                            if is_site_header or not current_site_code:
                                current_site_code = match_num.group(1)
                                current_site_name = match_num.group(2).strip()
                                current_site_secondary = None
                            else:
                                current_site_secondary = match_num.group(1)
                            continue

                        if not current_site_code: continue

                        # 2. Detect Event Header
                        match_header = re.match(RE_EVENT_HEADER, line)
                        if match_header:
                            day_label = match_header.group(1).upper()[:3]
                            date_str = match_header.group(2)
                            time_str = match_header.group(3)
                            remainder = match_header.group(4).strip()
                            
                            try:
                                ts_naive = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M:%S")
                                last_event_date = ts_naive
                                
                                # State & Code Extraction from remainder
                                state = "UNKNOWN"
                                alarm_code = None
                                
                                # State mapping
                                upper_rem = remainder.upper()
                                if "APPARITION" in upper_rem: state = "APPARITION"
                                elif "DISPARITION" in upper_rem: state = "DISPARITION"
                                elif "EXPIRATION" in upper_rem: state = "EXPIRATION"
                                elif "MISE EN SERVICE" in upper_rem: state = "MISE_EN_SERVICE"
                                elif "MISE HORS SERVICE" in upper_rem: state = "MISE_HORS_SERVICE"

                                # Code detection (starts with $ or pattern digits-suffix)
                                match_code = re.search(r'\$([\w-]+)|(\d{5,}-[\w-]+)', remainder)
                                if match_code:
                                    alarm_code = match_code.group(0).replace('$', '')
                                
                                # Operator Action detection
                                is_operator = remainder.startswith("$") or "MODIFICATION DE DOSSIER" in upper_rem

                                event = NormalizedEvent(
                                    timestamp=self._normalize_timestamp(ts_naive, source_timezone),
                                    site_code=current_site_code,
                                    client_name=current_site_name,
                                    secondary_code=current_site_secondary,
                                    weekday_label=day_label,
                                    event_type="OPERATOR_ACTION" if is_operator else "PDF_EVENT",
                                    raw_message=remainder,
                                    raw_code=alarm_code,
                                    status="ALARM" if state == "APPARITION" else "INFO",
                                    source_file=file_path,
                                    tenant_id="default-tenant"
                                )
                                event.metadata = {
                                    "state": state,
                                    "raw_line": line,
                                    "is_operator": is_operator
                                }
                                events.append(event)
                            except ValueError:
                                pass
                            continue
                        
                        # 3. Detect Sub Event
                        match_sub = re.match(RE_SUB_EVENT, line)
                        if match_sub and last_event_date:
                            time_str = match_sub.group(1)
                            message = match_sub.group(2)
                            
                            try:
                                t_part = datetime.strptime(time_str, "%H:%M:%S").time()
                                full_ts = datetime.combine(last_event_date.date(), t_part)
                                
                                # State check on sub message too
                                state = "UNKNOWN"
                                if "APPARITION" in message.upper(): state = "APPARITION"
                                elif "DISPARITION" in message.upper(): state = "DISPARITION"
                                
                                sub_event = NormalizedEvent(
                                    timestamp=self._normalize_timestamp(full_ts, source_timezone),
                                    site_code=current_site_code,
                                    client_name=current_site_name,
                                    secondary_code=current_site_secondary,
                                    event_type="DETAIL_LOG",
                                    sub_type="PDF_LOG",
                                    raw_message=message,
                                    status="INFO",
                                    source_file=file_path,
                                    tenant_id="default-tenant"
                                )
                                sub_event.metadata = {"raw_line": line, "state": state}
                                events.append(sub_event)
                            except ValueError:
                                pass
                            continue

                # Post-processing Debug Logs
                logger.info(f"PDF Debug: Finished {file_path}. Total Text Length: {total_text_len} chars.")
                
                if total_text_len < 200:
                    logger.warning(f"PDF WARNING: {file_path} seems empty or scanned image (Text len < 200).")
                    # Synthetic event for visibility
                    events.append(NormalizedEvent(
                        timestamp=datetime.now(pytz.UTC),
                        site_code="SYSTEM",
                        event_type="PARSING_ERROR",
                        raw_message=f"PDF seems empty or scanned (Text len: {total_text_len}). OCR required?",
                        status="new",
                        source_file=file_path,
                        tenant_id="default-tenant"
                    ))
                elif len(events) == 0:
                     events.append(NormalizedEvent(
                        timestamp=datetime.now(),
                        site_code="SYSTEM",
                        event_type="PARSING_WARNING",
                        raw_message=f"Text extracted ({total_text_len} chars) but no events matched regex patterns. Check format.",
                        status="new",
                        source_file=file_path,
                        tenant_id="default-tenant"
                    ))
                
                if settings.INGESTION.get('pdf_debug', False):
                    logger.info("PDF DEBUG: First 20 lines extracted:")
                    for i, l in enumerate(debug_lines):
                        logger.info(f"[{i:02d}] {l}")


        except Exception as e:
            # Re-raise unless it is an ImportError we just raised ourselves?
            # Actually, just log and allow worker to catch it as parsing error is fine.
            # But specific file-level errors are handled by worker.
             raise e 
            
        return events

    def _normalize_timestamp(self, ts: datetime, source_timezone: str) -> datetime:
        """
        Converts a naive or local datetime to timezone-aware UTC.
        """
        if ts is None:
            return None
            
        # If already aware, convert to UTC
        if ts.tzinfo is not None:
            return ts.astimezone(pytz.UTC)
            
        # If naive, localize with source_timezone then convert to UTC
        try:
            tz = pytz.timezone(source_timezone)
            aware_ts = tz.localize(ts)
            return aware_ts.astimezone(pytz.UTC)
        except Exception:
            # Fallback to UTC if timezone is invalid
            aware_ts = pytz.UTC.localize(ts)
            return aware_ts
