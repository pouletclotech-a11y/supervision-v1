import unicodedata
import re

def normalize_text(text: str) -> str:
    if not text:
        return ""
    
    # 1. Strip Excel-style wrapping ="..."
    if text.startswith('="') and text.endswith('"'):
        text = text[2:-1]
    
    # 2. Basic cleaning
    text = text.strip()
    
    # 3. Lowercase
    text = text.lower()
    
    # 4. Remove accents
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    
    # 5. Normalize spaces and special chars (keep only alphanumeric and spaces)
    text = re.sub(r'[^a-z0-9 ]+', ' ', text)
    text = ' '.join(text.split())
    
    return text

def clean_excel_value(val: str) -> str:
    """Just strips the ="..." without full normalization (for raw storage)."""
    if val.startswith('="') and val.endswith('"'):
        return val[2:-1].strip()
    return val.strip()
