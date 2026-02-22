import asyncio
import logging
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration-runner")

# SQL Migration Scripts
MIGRATION_02 = """
-- Migration 02: Normalization
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='events' AND column_name='zone_label') THEN
        ALTER TABLE events ADD COLUMN zone_label VARCHAR(255);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='events' AND column_name='event_metadata') THEN
        ALTER TABLE events ADD COLUMN event_metadata JSON DEFAULT '{}'::json;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_events_burst_lookup') THEN
        CREATE INDEX idx_events_burst_lookup ON events (site_id, normalized_type, time DESC);
    END IF;
END $$;
"""

MIGRATION_03 = """
-- Migration 03: Import Tracking & Idempotence
DO $$
BEGIN
    -- 1. ADD COLUMNS TO IMPORTS TABLE
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='imports' AND column_name='file_hash') THEN
        ALTER TABLE imports ADD COLUMN file_hash VARCHAR(64);
        CREATE INDEX idx_imports_hash ON imports(file_hash);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='imports' AND column_name='unmatched_count') THEN
        ALTER TABLE imports ADD COLUMN unmatched_count INTEGER DEFAULT 0;
    END IF;

    -- 2. ADD FOREIGN KEY TO EVENTS TABLE
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='events' AND column_name='import_id') THEN
        ALTER TABLE events ADD COLUMN import_id INTEGER;
        CREATE INDEX idx_events_import_id ON events(import_id);
    END IF;
END $$;
"""

MIGRATION_04 = """
-- Migration 04: User Profile Photo
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='profile_photo') THEN
        ALTER TABLE users ADD COLUMN profile_photo TEXT;
    END IF;
END $$;
"""

MIGRATION_05 = """
-- Migration 05: Alert Rules Expansion & Performance Indices
DO $$
BEGIN
    -- 1. ALERT RULES COLUMNS
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='alert_rules' AND column_name='schedule_start') THEN
        ALTER TABLE alert_rules ADD COLUMN schedule_start VARCHAR(5);
        ALTER TABLE alert_rules ADD COLUMN schedule_end VARCHAR(5);
        ALTER TABLE alert_rules ADD COLUMN time_scope VARCHAR(50) DEFAULT 'NONE';
        ALTER TABLE alert_rules ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
        ALTER TABLE alert_rules ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;

    -- 2. PERFORMANCE INDICES FOR EVENTS
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_events_site_time') THEN
        CREATE INDEX ix_events_site_time ON events (site_code, time);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_events_site_severity_time') THEN
        CREATE INDEX ix_events_site_severity_time ON events (site_code, severity, time);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_events_site_type_time') THEN
        CREATE INDEX ix_events_site_type_time ON events (site_code, normalized_type, time);
    END IF;

    -- 3. REPLAY JOBS TABLE
    CREATE TABLE IF NOT EXISTS replay_jobs (
        id SERIAL PRIMARY KEY,
        status VARCHAR(20) DEFAULT 'RUNNING',
        started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        ended_at TIMESTAMP WITH TIME ZONE,
        events_scanned INTEGER DEFAULT 0,
        alerts_created INTEGER DEFAULT 0,
        error_message TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
END $$;
"""

MIGRATION_06 = """
-- Migration 06: Event Rule Hits (Phase 1 Auditability)
DO $$
BEGIN
    CREATE TABLE IF NOT EXISTS event_rule_hits (
        id SERIAL PRIMARY KEY,
        event_id BIGINT NOT NULL,
        rule_id INTEGER NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
        rule_name VARCHAR(100) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- UNIQUE Index for idempotence
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_event_rule_hit_unique') THEN
        CREATE UNIQUE INDEX ix_event_rule_hit_unique ON event_rule_hits (event_id, rule_id);
    END IF;
    
    -- Performance Index
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_event_rule_hits_event_id') THEN
        CREATE INDEX ix_event_rule_hits_event_id ON event_rule_hits (event_id);
    END IF;
END $$;
"""

MIGRATION_07 = """
-- Migration 07: Adapter Name & Unmatched Count in Imports
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='imports' AND column_name='adapter_name') THEN
        ALTER TABLE imports ADD COLUMN adapter_name VARCHAR(50);
        CREATE INDEX idx_imports_adapter_name ON imports(adapter_name);
    END IF;
END $$;
"""

MIGRATION_08 = """
-- Migration 08: Email Bookmarking (Resilience)
DO $$
BEGIN
    CREATE TABLE IF NOT EXISTS email_bookmarks (
        id SERIAL PRIMARY KEY,
        folder VARCHAR(100) NOT NULL UNIQUE,
        last_uid BIGINT DEFAULT 0,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_email_bookmarks_folder ON email_bookmarks(folder);
END $$;
"""

MIGRATIONS = [MIGRATION_02, MIGRATION_03, MIGRATION_04, MIGRATION_05, MIGRATION_06, MIGRATION_07, MIGRATION_08]

async def run_migration():
    logger.info("Starting Persistent Migrations...")
    
    try:
        async with AsyncSessionLocal() as session:
            for idx, sql in enumerate(MIGRATIONS, 2):
                 logger.info(f"Executing Migration {idx:02d}...")
                 await session.execute(text(sql))
                 await session.commit()
            
        logger.info("All Migrations completed successfully.")
             
    except Exception as e:
        logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_migration())
