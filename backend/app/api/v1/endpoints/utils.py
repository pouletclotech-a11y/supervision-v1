import re
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter()

class RegexTestRequest(BaseModel):
    text: str
    regex: str
    flags: Optional[str] = "IGNORECASE" 

class RegexTestResponse(BaseModel):
    matched: bool
    groups: Optional[list] = None
    group_dict: Optional[Dict[str, str]] = None
    error: Optional[str] = None

@router.post("/regex-test", response_model=RegexTestResponse)
def test_regex_endpoint(req: RegexTestRequest):
    try:
        flags = 0
        if "IGNORECASE" in (req.flags or "").upper():
            flags |= re.IGNORECASE
        if "MULTILINE" in (req.flags or "").upper():
            flags |= re.MULTILINE
        
        pattern = re.compile(req.regex, flags)
        match = pattern.search(req.text)
        
        if match:
            return {
                "matched": True,
                "groups": list(match.groups()),
                "group_dict": match.groupdict() if match.groupdict() else None
            }
        else:
            return {"matched": False}
            
    except re.error as e:
         return {"matched": False, "error": f"Regex Error: {str(e)}"}
    except Exception as e:
         return {"matched": False, "error": f"Internal Error: {str(e)}"}
