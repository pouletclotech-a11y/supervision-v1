from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator

class DetectionRules(BaseModel):
    extensions: List[str] = Field(default_factory=list, description="Extensions supportées (ex: .xls, .pdf)")
    filename_pattern: Optional[str] = Field(None, description="Regex pour le nom de fichier")
    required_headers: List[str] = Field(default_factory=list, description="Colonnes/Headers obligatoires pour match")
    required_text: List[str] = Field(default_factory=list, description="Mots-clés obligatoires dans le texte (PDF)")

class MappingRule(BaseModel):
    source: Union[str, int] = Field(..., description="Nom de colonne ou index (0-based)")
    target: str = Field(..., description="Champ canonique (timestamp, site_code, etc.)")
    transform: Optional[str] = Field(None, description="Fonction de transformation (ex: uppercase, date_euro)")

class ExcelOptions(BaseModel):
    sheet_name: Union[str, int] = 0
    header_row: int = 0
    skip_rows: int = 0
    use_raw_values: bool = False

class CsvOptions(BaseModel):
    delimiter: str = ","
    encoding: str = "utf-8"
    quotechar: str = '"'

class NormalizationRule(BaseModel):
    field: str
    pattern: str
    replacement: str

class IngestionProfile(BaseModel):
    version: str = "1.0"
    profile_id: str = Field(..., description="Identifiant unique du profil")
    name: str = Field(..., description="Nom affichable")
    priority: int = Field(0, description="Priorité pour le tie-break (plus haut = prioritaire)")
    
    detection: DetectionRules
    
    # Options spécifiques au format
    excel_options: Optional[ExcelOptions] = None
    csv_options: Optional[CsvOptions] = None
    
    mapping: List[MappingRule] = Field(default_factory=list)
    extraction_rules: Dict[str, str] = Field(default_factory=dict, description="Regex nommées pour extraction de texte")
    normalization: List[NormalizationRule] = Field(default_factory=list)

    @validator("profile_id")
    def validate_profile_id(cls, v):
        if not v.replace("_", "").isalnum():
            raise ValueError("profile_id doit être alphanumérique (underscores autorisés)")
        return v
