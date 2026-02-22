-- Migration: 09_event_catalog.sql

-- 1. Create Catalog Table
CREATE TABLE IF NOT EXISTS event_code_catalog (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    label VARCHAR(255),
    category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',
    alertable_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Add columns to Events table for tagging
ALTER TABLE events ADD COLUMN IF NOT EXISTS category VARCHAR(50);
ALTER TABLE events ADD COLUMN IF NOT EXISTS alertable_default BOOLEAN DEFAULT FALSE;

-- 3. Seed Initial Data
INSERT INTO event_code_catalog (code, label, category, severity, alertable_default)
VALUES 
    ('NVF', 'Non-Validation de Fermeture', 'operator_check', 'warning', FALSE),
    ('CAM', 'Détection Caméra (Générique)', 'operator_check', 'info', FALSE),
    ('CAM1', 'Caméra 1', 'operator_check', 'info', FALSE),
    ('CAM2', 'Caméra 2', 'operator_check', 'info', FALSE),
    ('CAM3', 'Caméra 3', 'operator_check', 'info', FALSE)
ON CONFLICT (code) DO NOTHING;
