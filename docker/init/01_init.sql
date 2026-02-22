-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- SITES
CREATE TABLE IF NOT EXISTS sites (
    id SERIAL PRIMARY KEY,
    code_client VARCHAR(50) UNIQUE NOT NULL, -- ex: C-69000
    secondary_code VARCHAR(50),              -- ex: 32009
    name VARCHAR(255) NOT NULL,
    address TEXT,
    contact_info JSONB,                      -- { "phone": "...", "email": "..." }
    status VARCHAR(20) DEFAULT 'ACTIVE',     -- ACTIVE, SUSPENDED
    tags JSONB DEFAULT '[]',                 -- ["vip", "sensible"]
    config_override JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ZONES
CREATE TABLE IF NOT EXISTS zones (
    id SERIAL PRIMARY KEY,
    site_id INTEGER REFERENCES sites(id) ON DELETE CASCADE,
    code_zone VARCHAR(50) NOT NULL,          -- ex: Z01
    label VARCHAR(255),                      -- Normalized label
    original_label VARCHAR(255),             -- As received in events
    type VARCHAR(50) DEFAULT 'UNKNOWN',      -- INTRUSION, TECHNIQUE, FIRE
    status VARCHAR(20) DEFAULT 'ACTIVE',     -- ACTIVE, MUTED, EXCLUDED, INACTIVE
    last_triggered_at TIMESTAMPTZ,
    mute_until TIMESTAMPTZ,
    trigger_count_30d INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(site_id, code_zone)
);

-- INCIDENTS
CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    site_id INTEGER REFERENCES sites(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,               -- INTRUSION_BURST, VIDEO_LOSS
    status VARCHAR(20) DEFAULT 'OPEN',       -- OPEN, ACK, RESOLVED, CLOSED
    severity VARCHAR(20) DEFAULT 'info',     -- critical, warning, info
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    operator_comment TEXT,
    external_ref VARCHAR(100),               -- Ticket ID if linked
    linked_event_ids BIGINT[]                -- Array of event IDs
);

-- MAINTENANCE PERIODS
CREATE TABLE IF NOT EXISTS maintenance_periods (
    id SERIAL PRIMARY KEY,
    site_id INTEGER REFERENCES sites(id) ON DELETE CASCADE,
    start_ts TIMESTAMPTZ NOT NULL,
    end_ts TIMESTAMPTZ,
    technician_name VARCHAR(100),
    type VARCHAR(50) DEFAULT 'PREVENTIVE',
    zones_tested_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- EVENTS (Hypertable)
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL,                            -- No Primary Key constraint on ID alone for hypertables usually, but useful for referencing (composite PK with time recommended)
    time TIMESTAMPTZ NOT NULL,               -- Renamed from timestamp to time for Timescale convention
    site_id INTEGER,                         -- No FK constraint for performance if high volume, but safe here for V1
    zone_id INTEGER,
    raw_message TEXT,
    raw_code VARCHAR(50),
    normalized_type VARCHAR(100),
    sub_type VARCHAR(50),
    severity VARCHAR(20),
    source_file VARCHAR(255),
    dup_count INTEGER DEFAULT 0,
    in_maintenance BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert 'events' to hypertable partitioned by 'time'
SELECT create_hypertable('events', 'time', if_not_exists => TRUE);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_events_site_time ON events (site_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events (normalized_type);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status);
CREATE INDEX IF NOT EXISTS idx_sites_code ON sites (code_client);
