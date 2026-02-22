import logging
import yaml
from pathlib import Path
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import DBIngestionProfile
from app.core.config import settings
from app.schemas.ingestion_profile import IngestionProfile, DetectionRules, NormalizationRule

logger = logging.getLogger("profile-manager")

class ProfileManager:
    def __init__(self, profiles_dir: str = "profiles"):
        self.profiles_dir = Path(profiles_dir)
        self.profiles: Dict[str, IngestionProfile] = {}
        self.invalid_profiles: List[str] = []

    async def load_profiles(self, db: Optional[AsyncSession] = None):
        """
        Loads profiles according to settings.PROFILE_SOURCE_MODE.
        DB profiles always prevail over YAML if they exist.
        """
        self.profiles = {}
        self.invalid_profiles = []
        
        mode = settings.PROFILE_SOURCE_MODE
        
        # 1. Load from DB if session provided
        db_profiles_count = 0
        if db:
            try:
                stmt = select(DBIngestionProfile).where(DBIngestionProfile.is_active == True)
                result = await db.execute(stmt)
                db_models = result.scalars().all()
            except Exception as e:
                logger.error(f"Erreur lors de la requête DB profiles : {e}")
                db_models = []

            for model in db_models:
                try:
                    # --- Deserialize JSONB -> Pydantic nested models ---
                    detection_raw = model.detection or {}
                    if isinstance(detection_raw, dict):
                        detection = DetectionRules(**detection_raw)
                    else:
                        detection = detection_raw

                    normalization_raw = model.normalization or []
                    normalization = [
                        NormalizationRule(**n) if isinstance(n, dict) else n
                        for n in normalization_raw
                    ]

                    profile_data = {
                        "profile_id": model.profile_id,
                        "name": model.name,
                        "priority": model.priority,
                        "source_timezone": model.source_timezone,
                        "version_number": model.version_number,
                        "updated_at": model.updated_at,
                        "confidence_threshold": model.confidence_threshold,
                        "detection": detection,
                        "mapping": model.mapping or [],
                        "parser_config": model.parser_config or {},
                        "extraction_rules": model.extraction_rules or {},
                        "normalization": normalization,
                        "excel_options": model.excel_options,
                        "csv_options": model.csv_options,
                        "provider_code": getattr(model, "provider_code", None),
                    }
                    p = IngestionProfile(**profile_data)
                    self.profiles[p.profile_id] = p
                    db_profiles_count += 1
                    logger.debug(f"Profil DB chargé : {p.profile_id}")
                except Exception as e:
                    logger.error(f"Erreur conversion profil DB '{model.profile_id}': {e}")
                    self.invalid_profiles.append(model.profile_id)

            logger.info(f"{db_profiles_count} profils chargés depuis la BASE DE DONNÉES.")

        # 2. Fallback to YAML only when mode is DB_FALLBACK_YAML and DB was empty
        if mode == "DB_FALLBACK_YAML" and db_profiles_count == 0:
            if self.profiles_dir.exists():
                for yaml_file in self.profiles_dir.glob("*.yaml"):
                    try:
                        with open(yaml_file, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f)
                            if not data: continue
                            
                            p = IngestionProfile(**data)
                            if p.profile_id not in self.profiles:
                                self.profiles[p.profile_id] = p
                                logger.info(f"Profil chargé depuis YAML : {p.profile_id} ({yaml_file.name})")
                            else:
                                logger.debug(f"Profil YAML '{p.profile_id}' ignoré car déjà présent en DB.")
                    except Exception as e:
                        logger.error(f"Erreur YAML {yaml_file.name} : {e}")
                        self.invalid_profiles.append(str(yaml_file))
        elif mode == "DB_FALLBACK_YAML" and db_profiles_count > 0:
            # DB had profiles — still try YAML for any profile_id not yet in DB
            if self.profiles_dir.exists():
                for yaml_file in self.profiles_dir.glob("*.yaml"):
                    try:
                        with open(yaml_file, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f)
                            if not data: continue
                            p = IngestionProfile(**data)
                            if p.profile_id not in self.profiles:
                                self.profiles[p.profile_id] = p
                                logger.info(f"Profil chargé depuis YAML (complément DB) : {p.profile_id}")
                            else:
                                logger.debug(f"Profil YAML '{p.profile_id}' ignoré (DB prioritaire).")
                    except Exception as e:
                        logger.error(f"Erreur YAML {yaml_file.name} : {e}")
                        self.invalid_profiles.append(str(yaml_file))


        logger.info(f"Total profils actifs : {len(self.profiles)}")

    def get_profile(self, profile_id: str) -> Optional[IngestionProfile]:
        return self.profiles.get(profile_id)

    def list_profiles(self) -> List[IngestionProfile]:
        return list(self.profiles.values())
