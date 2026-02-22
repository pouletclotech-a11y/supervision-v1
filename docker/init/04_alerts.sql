-- 04_alerts.sql
CREATE TABLE IF NOT EXISTS alert_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    condition_type VARCHAR(50) NOT NULL, -- 'KEYWORD' or 'SEVERITY'
    value VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seed Default Rules
INSERT INTO alert_rules (name, condition_type, value) VALUES
('Critical Events', 'SEVERITY', 'CRITICAL'),
('Intrusion Detection', 'KEYWORD', 'intrusion'),
('Sabotage Detection', 'KEYWORD', 'sabotage'),
('Minor Default Test', 'KEYWORD', 'defaut mineur');
