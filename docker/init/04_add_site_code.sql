ALTER TABLE events ADD COLUMN IF NOT EXISTS site_code VARCHAR(50);
CREATE INDEX IF NOT EXISTS ix_events_site_code ON events (site_code);
