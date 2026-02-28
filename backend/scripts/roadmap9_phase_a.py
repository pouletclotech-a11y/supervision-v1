import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.db.models import DBIngestionProfile, MonitoringProvider

DATABASE_URL = "postgresql+asyncpg://admin:admin@localhost:5432/supervision"

async def main():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Get Provider ID
        stmt = select(MonitoringProvider).where(MonitoringProvider.code == 'YPSILON_HISTO')
        result = await session.execute(stmt)
        provider = result.scalar_one_or_none()
        
        if not provider:
            print("Error: YPSILON_HISTO provider not found.")
            return

        # 2. Create Profile
        profile_data = {
            "profile_id": "ypsilon_histo_v2",
            "name": "YPSILON HISTO (AUTO MATCH)",
            "priority": 20,
            "source_timezone": "Europe/Paris",
            "provider_code": "YPSILON_HISTO",
            "confidence_threshold": 1.5,
            "is_active": True,
            "detection": {
                "extensions": [".xls", ".xlsx", ".pdf"],
                "filename_pattern": ".*YPSILON_HISTO.*",
                "required_headers": [],
                "required_text": []
            },
            "parser_config": {
                "format": "HISTO"
            },
            "excel_options": {
                "use_raw_values": True
            },
            "mapping": [
                {"source": 0, "target": "site_code"},
                {"source": 1, "target": "client_name"},
                {"source": 6, "target": "timestamp"},
                {"source": 8, "target": "raw_message"},
                {"source": 11, "target": "raw_code"}
            ],
            "extraction_rules": {
                "site_code": "(?P<site_code>\\d{4,6})",
                "timestamp": "(?P<timestamp>\\d{2}/\\d{2}/\\d{4} \\d{2}:\\d{2}:\\d{2})",
                "raw_message": "(?P<raw_message>.*)"
            }
        }

        # Check existing
        stmt = select(DBIngestionProfile).where(DBIngestionProfile.profile_id == "ypsilon_histo_v2")
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            print("Profile ypsilon_histo_v2 already exists. Updating.")
            existing.name = profile_data["name"]
            existing.detection = profile_data["detection"]
            existing.mapping = profile_data["mapping"]
            existing.parser_config = profile_data["parser_config"]
            existing.extraction_rules = profile_data["extraction_rules"]
            existing.excel_options = profile_data["excel_options"]
        else:
            print("Creating profile ypsilon_histo_v2.")
            new_profile = DBIngestionProfile(
                profile_id=profile_data["profile_id"],
                name=profile_data["name"],
                priority=profile_data["priority"],
                source_timezone=profile_data["source_timezone"],
                provider_id=provider.id,
                is_active=True,
                detection=profile_data["detection"],
                mapping=profile_data["mapping"],
                parser_config=profile_data["parser_config"],
                extraction_rules=profile_data["extraction_rules"],
                excel_options=profile_data["excel_options"],
                version_number=1
            )
            session.add(new_profile)
        
        await session.commit()
        print("Success.")

if __name__ == "__main__":
    asyncio.run(main())
