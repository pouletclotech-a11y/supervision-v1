import re
import logging
from typing import Optional, Dict, Any
from app.ingestion.models import NormalizedEvent
from app.core.config import settings

logger = logging.getLogger("normalizer")

def normalize_site_code(raw: str) -> str:
    """
    Centralized site_code normalization logic for Roadmap 4.
    Rules:
    - strip wrappers ="..."
    - trim spaces
    - if numeric (digits only): strip leading zeros (e.g. 00032009 -> 32009)
    - if result is empty -> "0"
    - otherwise keep as is (alphas, etc.)
    """
    if not raw:
        return raw

    original = raw
    # 1. Strip Excel wrappers ="VALUE"
    if raw.startswith('="') and raw.endswith('"'):
        raw = raw[2:-1]
    
    # 2. Trim spaces
    raw = raw.strip()

    # 3. Numeric leading zeros logic
    # Regex ^0+\d+$ matches "01", "007", but not "0", "A01", "0A"
    if re.match(r'^0+\d+$', raw):
        raw = raw.lstrip('0')
        if not raw:
            raw = "0"
    
    if raw != original:
        logger.debug(f"SiteCode Normalized: '{original}' -> '{raw}'")
    
    return raw

class Normalizer:
    def __init__(self):
        self.rules = settings.NORMALIZATION.get('rules', [])
        self.stop_at_first_match = settings.NORMALIZATION.get('stop_at_first_match', True)
        
        # Pre-compile regexes
        self.compiled_rules = []
        for rule in self.rules:
            try:
                self.compiled_rules.append({
                    "regex": re.compile(rule['regex'], re.IGNORECASE),
                    "type": rule.get('type'),
                    "severity": rule.get('severity'),
                    "extract": rule.get('extract', {})
                })
            except re.error as e:
                logger.error(f"Invalid Regex Rule '{rule.get('regex')}': {e}")

    def normalize(self, event: NormalizedEvent) -> NormalizedEvent:
        """
        Applies normalization rules to the event.
        Updates normalized_type, severity, zone_label, and metadata.
        """
        msg = event.raw_message
        if not msg:
            return event

        matched = False
        
        for rule in self.compiled_rules:
            match = rule['regex'].search(msg)
            if match:
                matched = True
                
                # 1. Set Type & Severity
                if rule['type']:
                    event.event_type = rule['type']
                    event.normalized_type = rule['type'] # Update both for consistency if used differently
                
                if rule['severity']:
                    event.status = rule['severity'] # Mapped to status/severity field
                
                # 2. Extractions
                extract_map = rule['extract']
                groups = match.groups()
                
                # Handle group extraction
                for field_name, group_index in extract_map.items():
                    # group_index is 1-based in config usually, but let's assume 1-based for users
                    # regex groups are 1-based in match.group()
                    try:
                        idx = int(group_index)
                        if 1 <= idx <= len(groups):
                            val = groups[idx-1] # groups() tuple is 0-indexed corresponding to group 1, 2..
                            if val:
                                val = val.strip()
                                self._apply_extraction(event, field_name, val)
                    except (ValueError, IndexError):
                        pass

                if self.stop_at_first_match:
                    break
        
        if not matched:
            # Fallback or just keep defaults
            pass
            
        return event

    def _apply_extraction(self, event: NormalizedEvent, field: str, value: str):
        """
        Maps extracted value to event fields or metadata.
        """
        if field == 'zone_label':
            event.zone_label = value
        elif field == 'site_code':
            # Use centralized normalization
            event.site_code = normalize_site_code(value)
        elif field == 'sub_type':
            event.sub_type = value
        elif field == 'ticket_code':
            if not event.metadata: event.metadata = {}
            event.metadata['ticket_code'] = value
        elif field == 'actor':
            if not event.metadata: event.metadata = {}
            event.metadata['actor'] = value
        else:
            # Generic metadata
            if not event.metadata: event.metadata = {}
            event.metadata[field] = value
