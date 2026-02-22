-- Seed update: 15_add_nvf_to_catalog.sql

INSERT INTO event_code_catalog (code, label, category, severity, alertable_default)
VALUES 
('NVF', 'Noise Video Filter', 'operator_check', 'info', false)
ON CONFLICT (code) DO UPDATE SET 
    category = EXCLUDED.category,
    severity = EXCLUDED.severity,
    alertable_default = EXCLUDED.alertable_default;
