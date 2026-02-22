-- Phase 3: Compteurs Raccordements par Télésurveilleur
-- Tables: monitoring_providers, smtp_provider_rules, site_connections
-- Modifie: imports (ajoute provider_id)

-- 1. Table des télésurveilleurs
CREATE TABLE IF NOT EXISTS monitoring_providers (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,       -- SPGO, CORS
    label VARCHAR(100) NOT NULL,            -- Affichage UI (CORS+Online)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Règles SMTP pour classification automatique
CREATE TABLE IF NOT EXISTS smtp_provider_rules (
    id SERIAL PRIMARY KEY,
    provider_id INT NOT NULL REFERENCES monitoring_providers(id) ON DELETE CASCADE,
    match_type VARCHAR(20) NOT NULL,        -- EXACT, DOMAIN, REGEX
    match_value VARCHAR(255) NOT NULL,      -- email@example.com, spgo.fr, .*@.*pattern.*
    priority INT DEFAULT 0,                 -- Plus élevé = testé en premier
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_smtp_rules_priority ON smtp_provider_rules(priority DESC, match_type);

-- 3. Raccordements sites (unique par provider + code_site)
CREATE TABLE IF NOT EXISTS site_connections (
    id SERIAL PRIMARY KEY,
    provider_id INT NOT NULL REFERENCES monitoring_providers(id) ON DELETE CASCADE,
    code_site VARCHAR(50) NOT NULL,         -- Code client (homogène projet)
    client_name VARCHAR(255),               -- Nom client associé
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    first_import_id INT,                    -- Premier import ayant détecté ce site
    UNIQUE(provider_id, code_site)
);

CREATE INDEX IF NOT EXISTS ix_site_connections_provider ON site_connections(provider_id);
CREATE INDEX IF NOT EXISTS ix_site_connections_first_seen ON site_connections(first_seen_at);

-- 4. Ajouter provider_id sur imports (nullable pour rétrocompatibilité)
ALTER TABLE imports ADD COLUMN IF NOT EXISTS provider_id INT REFERENCES monitoring_providers(id);

-- 5. Seed initial: SPGO et CORS
INSERT INTO monitoring_providers (code, label) VALUES 
    ('SPGO', 'SPGO'),
    ('CORS', 'CORS+Online')
ON CONFLICT (code) DO NOTHING;

-- 6. Seed règles SMTP initiales (DOMAIN matching)
INSERT INTO smtp_provider_rules (provider_id, match_type, match_value, priority) VALUES
    ((SELECT id FROM monitoring_providers WHERE code = 'SPGO'), 'DOMAIN', 'spgo.fr', 10),
    ((SELECT id FROM monitoring_providers WHERE code = 'CORS'), 'DOMAIN', 'cors-online.com', 10)
ON CONFLICT DO NOTHING;
