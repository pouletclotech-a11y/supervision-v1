-- Migration: 13_normalized_message.sql

-- Add normalized_message column to events
ALTER TABLE events ADD COLUMN IF NOT EXISTS normalized_message TEXT;

-- Index for fast keyword matching
CREATE INDEX IF NOT EXISTS ix_events_normalized_message ON events USING gin (normalized_message gin_trgm_ops) WHERE normalized_message IS NOT NULL;
-- Note: Requires pg_trgm extension for GIN trgm. If not available, standard B-tree or just btree index.
-- Standard B-tree for exact/prefix or just index it.
CREATE INDEX IF NOT EXISTS ix_events_normalized_message_btree ON events (normalized_message);

-- Initialize existing data (optional but good for consistency)
-- UPDATE events SET normalized_message = lower(raw_message); -- Basic init
