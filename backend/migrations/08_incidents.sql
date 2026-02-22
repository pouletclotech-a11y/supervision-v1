-- Migration: 08_incidents.sql
CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    site_code VARCHAR(50) NOT NULL,
    incident_key VARCHAR(128) NOT NULL,
    label TEXT,
    opened_at TIMESTAMP WITH TIME ZONE NOT NULL,
    closed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN', -- OPEN, CLOSED
    duration_seconds INTEGER,
    open_event_id BIGINT,
    close_event_id BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraint for idempotence (Step 3: site_code + incident_key + opened_at)
    CONSTRAINT uq_incident_unique UNIQUE (site_code, incident_key, opened_at)
);

CREATE INDEX IF NOT EXISTS ix_incidents_site_status ON incidents (site_code, status);
CREATE INDEX IF NOT EXISTS ix_incidents_key_opened ON incidents (incident_key, opened_at);
