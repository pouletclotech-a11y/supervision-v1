-- Migration to add Normalization columns
-- Idempotent: safe to run multiple times

DO $$
BEGIN
    -- Add zone_label
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='events' AND column_name='zone_label') THEN
        ALTER TABLE events ADD COLUMN zone_label VARCHAR(255);
    END IF;

    -- Add event_metadata
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='events' AND column_name='event_metadata') THEN
        ALTER TABLE events ADD COLUMN event_metadata JSON DEFAULT '{}'::json;
    END IF;

    -- Create index for Burst Collapse performance
    -- (site_id, normalized_type, zone_label, time)
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_events_burst_lookup') THEN
        CREATE INDEX idx_events_burst_lookup ON events (site_id, normalized_type, time DESC);
        -- Note: zone_label might be null, usually indexed separately or included if partial index needed, 
        -- but site_id + normalized_type + time is usually good enough for efficient lookup.
    END IF;
END $$;
