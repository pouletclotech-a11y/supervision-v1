-- Migration: 11_sequences.sql

-- Add temporal sequence detection fields to alert_rules
ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS sequence_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS seq_a_category VARCHAR(50);
ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS seq_a_keyword VARCHAR(255);
ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS seq_b_category VARCHAR(50);
ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS seq_b_keyword VARCHAR(255);
ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS seq_max_delay_seconds INTEGER DEFAULT 0;
ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS seq_lookback_days INTEGER DEFAULT 2;

-- Indexing for performance
CREATE INDEX IF NOT EXISTS ix_alert_rules_seq_enabled ON alert_rules (sequence_enabled) WHERE sequence_enabled = TRUE;
