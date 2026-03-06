import os
import sys
import asyncio
import yaml
import logging
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add app to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.db.models import DBIngestionProfile
from app.schemas.ingestion_profile import IngestionProfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sync-profiles")

async def sync_profiles():
    profiles_dir = Path("profiles")
    if not profiles_dir.exists():
        logger.error(f"Profiles directory {profiles_dir.absolute()} not found.")
        return

    async with AsyncSessionLocal() as session:
        for yaml_file in profiles_dir.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if not data: continue
                    
                    # Validate with Pydantic
                    profile = IngestionProfile(**data)
                    
                    # Check if exists
                    stmt = select(DBIngestionProfile).where(DBIngestionProfile.profile_id == profile.profile_id)
                    result = await session.execute(stmt)
                    db_profile = result.scalars().first()
                    
                    # Prepare data for DB
                    db_data = {
                        "name": profile.name,
                        "priority": profile.priority,
                        "source_timezone": profile.source_timezone,
                        "detection": profile.detection.model_dump() if hasattr(profile.detection, 'model_dump') else profile.detection,
                        "mapping": [m.model_dump() if hasattr(m, 'model_dump') else m for m in profile.mapping],
                        "parser_config": profile.parser_config,
                        "extraction_rules": profile.extraction_rules,
                        "normalization": profile.normalization if isinstance(profile.normalization, dict) else {},
                        "provider_code": getattr(profile, 'provider_code', None),
                        "format_kind": getattr(profile, 'format_kind', 'XLSX_NATIVE'),
                        "action_config": getattr(profile, 'action_config', {}),
                        "filename_regex": getattr(profile, 'filename_regex', None),
                        "is_active": True
                    }
                    
                    if db_profile:
                        logger.info(f"Updating profile {profile.profile_id} from {yaml_file.name}")
                        for key, value in db_data.items():
                            setattr(db_profile, key, value)
                    else:
                        logger.info(f"Creating profile {profile.profile_id} from {yaml_file.name}")
                        new_profile = DBIngestionProfile(
                            profile_id=profile.profile_id,
                            **db_data
                        )
                        session.add(new_profile)
            except Exception as e:
                logger.error(f"Failed to sync {yaml_file.name}: {e}")
        
        await session.commit()
        logger.info("Profile synchronization complete.")

if __name__ == "__main__":
    asyncio.run(sync_profiles())
