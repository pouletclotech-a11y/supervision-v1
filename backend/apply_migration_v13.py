import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = "postgresql+asyncpg://admin:admin@localhost:5432/supervision"

async def run_migration():
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    migration_sql = """
    -- Table: imports
    DO $$ 
    BEGIN 
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='imports' AND column_name='quality_report') THEN
            ALTER TABLE imports ADD COLUMN quality_report JSONB DEFAULT '{}';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='imports' AND column_name='pdf_match_report') THEN
            ALTER TABLE imports ADD COLUMN pdf_match_report JSONB DEFAULT '{}';
        END IF;
    END $$;

    -- Table: monitoring_providers
    DO $$ 
    BEGIN 
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='monitoring_providers' AND column_name='pdf_warning_threshold') THEN
            ALTER TABLE monitoring_providers ADD COLUMN pdf_warning_threshold FLOAT DEFAULT 0.9;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='monitoring_providers' AND column_name='pdf_critical_threshold') THEN
            ALTER TABLE monitoring_providers ADD COLUMN pdf_critical_threshold FLOAT DEFAULT 0.7;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='monitoring_providers' AND column_name='pdf_ignore_case') THEN
            ALTER TABLE monitoring_providers ADD COLUMN pdf_ignore_case BOOLEAN DEFAULT TRUE;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='monitoring_providers' AND column_name='pdf_ignore_accents') THEN
            ALTER TABLE monitoring_providers ADD COLUMN pdf_ignore_accents BOOLEAN DEFAULT TRUE;
        END IF;
    END $$;
    """
    
    async with engine.begin() as conn:
        for statement in migration_sql.split(';'):
            if statement.strip():
                await conn.execute(text(statement))
    
    print("Migration V13 applied successfully.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_migration())
