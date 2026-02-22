-- 06_settings.sql
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description VARCHAR(255),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed Default Settings
INSERT INTO settings (key, value, description) VALUES 
('imap_host', 'ssl0.ovh.net', 'IMAP Server Address'),
('imap_port', '993', 'IMAP Port (SSL)'),
('imap_user', 'user@domain.com', 'Email Account'),
('imap_password', '', 'Email Password'),
('whitelist_senders', '[]', 'List of allowed sender emails (JSON)'),
('attachment_types', '["pdf", "xlsx", "xls"]', 'Allowed extensions (JSON)'),
('cleanup_mode', 'MOVE', 'MOVE or DELETE')
ON CONFLICT (key) DO NOTHING;
