import re
import csv
import json
import pytz
from datetime import datetime
from typing import List, Optional
from app.parsers.base import BaseParser
from app.ingestion.models import NormalizedEvent
from app.utils.text import normalize_text, clean_excel_value

class ExcelParser(BaseParser):
    """
    Parses 'Pseudo-Excel' files (YPSILON.xls) which are actually Tab-Separated Values (TSV)
    wrapped in Excel formulas (e.g. ="Value").
    
    V2 Implementation: Cell-aware context propagation.
    - Col A: site_code (inherits down)
    - Col B: day (inherits down)
    - Col C: date/time (inherits date part down)
    - Col D: action/type
    - Col F: details
    """

    def supported_extensions(self) -> List[str]:
        return ['.xls']

    def parse(self, file_path: str, source_timezone: str = "UTC", parser_config: dict = None) -> List[NormalizedEvent]:
        # Check if it's a real Excel file (binary)
        is_binary = False
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4)
                if header == b'PK\x03\x04': # ZIP header for .xlsx
                    is_binary = True
        except Exception:
            pass

        if is_binary:
            return self._parse_real_excel(file_path, source_timezone, parser_config)
        else:
            return self._parse_tsv_excel(file_path, source_timezone, parser_config)

    def _parse_real_excel(self, file_path: str, source_timezone: str = "UTC", parser_config: dict = None) -> List[NormalizedEvent]:
        import pandas as pd
        events = []
        try:
            df = pd.read_excel(file_path, header=None, engine='openpyxl')
            
            # Detect format (Condition 6 - Zéro Hardcode)
            is_histo = False
            if parser_config and parser_config.get("format") == "HISTO":
                is_histo = True
            elif not df.empty and str(df.iloc[0, 0]).strip().upper() == 'YPSILON_HISTO':
                # Legacy fallback
                is_histo = True
                
            # Context trackers (Inheritance)
            ctx_site_code = None
            ctx_client_name = None
            ctx_day = None
            ctx_date = None # Last seen full date

            for idx, row_series in df.iterrows():
                # Keep raw values for better type detection (like Timestamp)
                row = row_series.tolist()
                row_idx = idx + 1
                
                # Replace None or NaN with empty string
                row = ["" if c is None or (isinstance(c, float) and pd.isna(c)) else c for c in row]
                
                # Pad to at least 15 columns for HISTO
                while len(row) < 15:
                    row.append("")
                
                processed = self._process_row(row, row_idx, file_path, ctx_site_code, ctx_client_name, ctx_day, ctx_date, is_histo, source_timezone)
                if processed:
                    evt, ctx_site_code, ctx_client_name, ctx_day, ctx_date = processed
                    if evt:
                        events.append(evt)
            
        except Exception as e:
            import logging
            logging.getLogger("excel-parser").error(f"Failed to parse binary excel {file_path}: {e}")
            raise e
            
        return events

    def _parse_tsv_excel(self, file_path: str, source_timezone: str = "UTC", parser_config: dict = None) -> List[NormalizedEvent]:
        events = []
        # Context trackers (Inheritance)
        ctx_site_code = None
        ctx_client_name = None
        ctx_day = None
        ctx_date = None # Last seen full date

        with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
            reader = csv.reader(f, delimiter='\t')
            row_idx = 0
            for row in reader:
                row_idx += 1
                if not row: continue
                # Clean row elements
                clean_row = [clean_excel_value(c) for c in row]
                # Pad to at least 6 columns
                while len(clean_row) < 6:
                    clean_row.append("")
                
                processed = self._process_row(clean_row, row_idx, file_path, ctx_site_code, ctx_client_name, ctx_day, ctx_date, False, source_timezone)
                if processed:
                    evt, ctx_site_code, ctx_client_name, ctx_day, ctx_date = processed
                    if evt:
                        events.append(evt)
        return events

    def _process_row(self, clean_row, row_idx, file_path, ctx_site_code, ctx_client_name, ctx_day, ctx_date, is_histo=False, source_timezone="UTC"):
        if is_histo:
            return self._process_row_histo(clean_row, row_idx, file_path, ctx_site_code, ctx_client_name, ctx_day, ctx_date, source_timezone)
        
        col_a, col_b, col_c, col_d, col_e, col_f = [clean_excel_value(c) for c in clean_row[:6]]

        # --- 1. SITE_CODE PROPAGATION (Col A) ---
        if col_a:
            col_a_clean = str(col_a).strip()
            # Match digits-only or C-digits, but keep original if it looks like a code
            site_match = re.match(r'^(C-)?(\d+)$', col_a_clean)
            if site_match:
                ctx_site_code = site_match.group(2) 
                # Client name is usually in Col B of the header row
                if col_b and str(col_b).upper()[:3] not in ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"]:
                    ctx_client_name = str(col_b).strip()

        # --- 2. DAY PROPAGATION (Col B) ---
        days_map = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"]
        if col_b and str(col_b).upper()[:3] in days_map:
            ctx_day = str(col_b).upper()[:3]

        # --- 3. DATE/TIME PROPAGATION (Col C) ---
        ts = None
        if col_c:
            # Case A: Full Date 27/01/2026 16:24:25
            try:
                ts = datetime.strptime(str(col_c), "%d/%m/%Y %H:%M:%S")
                ctx_date = ts.date()
            except ValueError:
                # Case B: Time only 16:24:25
                if re.match(r'^\d{2}:\d{2}:\d{2}$', str(col_c)) and ctx_date:
                    try:
                        t_part = datetime.strptime(str(col_c), "%H:%M:%S").time()
                        ts = datetime.combine(ctx_date, t_part)
                    except ValueError:
                        pass
        
        # --- 4. ACTION & DETAILS (Col D & F) ---
        action = str(col_d).strip()
        details = str(col_f).strip()
        raw_code = str(col_e).strip() if col_e and str(col_e).lower() != 'nan' else None

        # --- 5. EVENT GENERATION ---
        if not ts or not action or not ctx_site_code or action.lower() == 'nan':
            return None, ctx_site_code, ctx_client_name, ctx_day, ctx_date
        
        # State mapping
        state = "UNKNOWN"
        if "APPARITION" in action.upper(): state = "APPARITION"
        elif "DISPARITION" in action.upper(): state = "DISPARITION"
        elif "EXPIRATION" in action.upper(): state = "EXPIRATION"
        elif "MISE EN SERVICE" in action.upper(): state = "MISE_EN_SERVICE"
        elif "MISE HORS SERVICE" in action.upper(): state = "MISE_HORS_SERVICE"

        event = NormalizedEvent(
            timestamp=self._normalize_timestamp(ts, source_timezone),
            site_code=ctx_site_code,
            client_name=ctx_client_name,
            weekday_label=ctx_day,
            event_type=action,
            raw_message=f"{action} | {details}" if details and details.lower() != 'nan' else action,
            normalized_message=normalize_text(f"{action} | {details}" if details and details.lower() != 'nan' else action),
            raw_code=raw_code,
            status="ALARM" if state == "APPARITION" else "INFO",
            source_file=file_path,
            row_index=row_idx,
            raw_data=json.dumps(clean_row if isinstance(clean_row, list) else []),
            tenant_id="default-tenant"
        )
        
        event.metadata = {
            "raw_action": action,
            "raw_details": details,
            "col_e": col_e,
            "state": state
        }
        
        return event, ctx_site_code, ctx_client_name, ctx_day, ctx_date

    def _process_row_histo(self, clean_row, row_idx, file_path, ctx_site_code, ctx_client_name, ctx_day, ctx_date, source_timezone="UTC"):
        # Format YPSILON_HISTO:
        # Col 0: Site code (8 digits) OR empty
        # Col 1: Client name OR empty
        # Col 6: Timestamp "dd/mm/yyyy hh:mm:ss" OR datetime object
        # Col 7: Action (APPARITION, etc.)
        # Col 8: Message
        
        col_site = str(clean_excel_value(clean_row[0])).strip()
        col_client = str(clean_excel_value(clean_row[1])).strip()
        col_ts = clean_row[6]
        col_action = str(clean_excel_value(clean_row[7])).strip()
        col_msg = str(clean_excel_value(clean_row[8])).strip()

        # 1. Propagation
        if col_site:
            col_site_clean = str(col_site).strip()
            # Handle both formats: "69000" or "C-69000"
            match_site = re.match(r'^(C-)?(\d+)$', col_site_clean)
            if match_site:
                ctx_site_code = match_site.group(2)
                if col_client and col_client.lower() != 'nan':
                    ctx_client_name = col_client.strip()
        
        # 2. Timestamp
        ts = None
        if isinstance(col_ts, datetime):
            ts = col_ts
        elif col_ts:
            col_ts_str = str(clean_excel_value(col_ts)).strip()
            if col_ts_str:
                for fmt in ["%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        ts = datetime.strptime(col_ts_str, fmt)
                        break
                    except ValueError:
                        continue
        
        if not ts or not col_msg or col_msg.lower() == 'nan' or not ctx_site_code:
            return None, ctx_site_code, ctx_client_name, ctx_day, ctx_date
        
        # State mapping
        state = "UNKNOWN"
        if "APPARITION" in col_action.upper(): state = "APPARITION"
        elif "DISPARITION" in col_action.upper(): state = "DISPARITION"
        elif "EXPIRATION" in col_action.upper(): state = "EXPIRATION"
        elif "MISE EN SERVICE" in col_action.upper(): state = "MISE_EN_SERVICE"
        elif "MISE HORS SERVICE" in col_action.upper(): state = "MISE_HORS_SERVICE"

        event = NormalizedEvent(
            timestamp=self._normalize_timestamp(ts, source_timezone),
            site_code=ctx_site_code,
            client_name=ctx_client_name,
            weekday_label=None,
            event_type=col_action if col_action and col_action.lower() != 'nan' else "EVENT",
            raw_message=f"{col_action} | {col_msg}" if col_action and col_action.lower() != 'nan' else col_msg,
            normalized_message=normalize_text(f"{col_action} | {col_msg}" if col_action and col_action.lower() != 'nan' else col_msg),
            raw_code=None,
            status="ALARM" if state == "APPARITION" else "INFO",
            source_file=file_path,
            row_index=row_idx,
            raw_data=json.dumps(clean_row if isinstance(clean_row, list) else []),
            tenant_id="default-tenant"
        )

        # In HISTO, the code might be inside the message after a '$'
        if not event.raw_code and '$' in col_msg:
            match_code = re.search(r'\$([\w-]+)', col_msg) # Allow hyphen in code
            if match_code:
                event.raw_code = match_code.group(1)
        
        event.metadata = {
            "state": state,
            "raw_action": col_action,
            "raw_message": col_msg
        }

        # Weekday
        days_map_fr = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"]
        event.weekday_label = days_map_fr[ts.weekday()]

        return event, ctx_site_code, ctx_client_name, ctx_day, ctx_date

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
