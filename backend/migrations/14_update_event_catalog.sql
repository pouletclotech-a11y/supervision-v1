-- Seed: 14_update_event_catalog.sql

-- Clear old seed (optional, keep live data)
-- TRUNCATE TABLE event_code_catalog;

-- 1. Real System/Protocol Codes (Col E)
INSERT INTO event_code_catalog (code, label, category, severity, alertable_default)
VALUES 
('MVS', 'MVS / myVideoSuite', 'operator_check', 'info', false),
('SMAIL', 'Envoi Email', 'operator_check', 'info', false),
('WEBBROWSER', 'Accès Web Browser', 'operator_check', 'info', false),
('796', 'Test cyclique', 'supervision_check', 'info', false),
('776', 'Test manuel', 'supervision_check', 'info', false),
('100001', 'Connexion Système', 'supervision_check', 'info', false),
('$MAINT', 'Mode Maintenance', 'maintenance', 'warning', false),
('$INHIB', 'Inhibition zone', 'maintenance', 'warning', false),
('CAM', 'Message Caméra (Pattern)', 'camera', 'info', false),
('UNKNOWN', 'Code Inconnu', 'unknown', 'info', false)
ON CONFLICT (code) DO UPDATE SET 
    category = EXCLUDED.category,
    severity = EXCLUDED.severity,
    alertable_default = EXCLUDED.alertable_default;

-- 2. Business Keywords (Detect via TaggingService matching catalog label in normalized_message)
INSERT INTO event_code_catalog (code, label, category, severity, alertable_default)
VALUES 
('KW_INTRUSION', 'INTRUSION', 'security', 'critical', true),
('KW_FEU', 'FEU', 'fire', 'critical', true),
('KW_PANIQUE', 'PANIQUE', 'hold_up', 'critical', true),
('KW_MAINT_AUTO', 'MAINTENANCE AUTOMATIQUE', 'maintenance', 'warning', false)
ON CONFLICT (code) DO UPDATE SET 
    category = EXCLUDED.category,
    severity = EXCLUDED.severity,
    alertable_default = EXCLUDED.alertable_default;

-- Mapping code 130 which is used for Intrusion in the XLS
INSERT INTO event_code_catalog (code, label, category, severity, alertable_default)
VALUES 
('130', 'ALARME INTRUSION', 'security', 'critical', true)
ON CONFLICT (code) DO UPDATE SET 
    category = EXCLUDED.category,
    severity = EXCLUDED.severity,
    alertable_default = EXCLUDED.alertable_default;
