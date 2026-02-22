-- Migration 03: Import Tracking & Idempotence
-- Goal: Add file_hash to imports, unmatched_count, and link events to import_id

DO $$
BEGIN
    -- 1. ADD COLUMNS TO IMPORTS TABLE
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='imports' AND column_name='file_hash') THEN
        ALTER TABLE imports ADD COLUMN file_hash VARCHAR(64); -- SHA256 hex
        CREATE INDEX idx_imports_hash ON imports(file_hash);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='imports' AND column_name='unmatched_count') THEN
        ALTER TABLE imports ADD COLUMN unmatched_count INTEGER DEFAULT 0;
    END IF;

    -- 2. ADD FOREIGN KEY TO EVENTS TABLE
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='events' AND column_name='import_id') THEN
        ALTER TABLE events ADD COLUMN import_id INTEGER;
        
        -- Creating FK constraint (optional for TimescaleDB heavily partitioned, but good for integrity if volume allows)
        -- We will keep it loose for performance or add a simple index
        CREATE INDEX idx_events_import_id ON events(import_id);
    END IF;
    
END $$;
