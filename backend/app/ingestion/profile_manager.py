import yaml
import logging
import os
from pathlib import Path
from typing import List, Dict, Optional
from app.schemas.ingestion_profile import IngestionProfile
from pydantic import ValidationError

logger = logging.getLogger("profile-manager")

class ProfileManager:
    def __init__(self, profiles_dir: str = "profiles"):
        self.profiles_dir = Path(profiles_dir)
        self.profiles: Dict[str, IngestionProfile] = {}
        self.invalid_profiles: List[str] = []

    def load_profiles(self):
        """Loads and validates all YAML profiles from the profiles directory."""
        self.profiles = {}
        self.invalid_profiles = []

        if not self.profiles_dir.exists():
            logger.warning(f"Répertoire des profils non trouvé : {self.profiles_dir}")
            return

        for yaml_file in self.profiles_dir.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if not data:
                        continue
                    
                    profile = IngestionProfile(**data)
                    if profile.profile_id in self.profiles:
                        logger.error(f"Doublon de profile_id '{profile.profile_id}' dans {yaml_file}")
                        self.invalid_profiles.append(str(yaml_file))
                        continue

                    self.profiles[profile.profile_id] = profile
                    logger.info(f"Profil chargé avec succès : {profile.profile_id} ({yaml_file.name})")

            except ValidationError as ve:
                logger.error(f"Erreur de validation pour {yaml_file.name} : {ve}")
                self.invalid_profiles.append(str(yaml_file))
            except Exception as e:
                logger.error(f"Erreur lors du chargement de {yaml_file.name} : {e}")
                self.invalid_profiles.append(str(yaml_file))

        if self.invalid_profiles:
            logger.warning(f"{len(self.invalid_profiles)} profil(s) invalide(s) ignoré(s) : {self.invalid_profiles}")

    def get_profile(self, profile_id: str) -> Optional[IngestionProfile]:
        return self.profiles.get(profile_id)

    def list_profiles(self) -> List[IngestionProfile]:
        return list(self.profiles.values())
