-- Migration: 10_advanced_alerting.sql

-- Add advanced filtering and sliding window fields to alert_rules
ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS match_category VARCHAR(50);
ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS match_keyword VARCHAR(255);
ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS is_open_only BOOLEAN DEFAULT FALSE;
ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS sliding_window_days INTEGER DEFAULT 0;

-- Optional: Indexing for performance
CREATE INDEX IF NOT EXISTS ix_alert_rules_category ON alert_rules (match_category) WHERE match_category IS NOT NULL;
