-- Migration: 12_rule_conditions.sql

-- 1. Create table for named conditions (library)
CREATE TABLE IF NOT EXISTS rule_conditions (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    label VARCHAR(255),
    type VARCHAR(20) NOT NULL CHECK (type IN ('SIMPLE_V3', 'SEQUENCE')),
    payload JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Add logic fields to alert_rules
ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS logic_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS logic_tree JSONB;

-- Indexing for performance
CREATE INDEX IF NOT EXISTS ix_rule_conditions_code ON rule_conditions (code);
