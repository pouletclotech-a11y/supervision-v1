-- Seed: 16_seed_test_rules.sql

-- 1. Rule Conditions (Reusable bricks)
INSERT INTO rule_conditions (code, label, type, payload, is_active)
VALUES
('intrusion_text', 'Détection mot "intrusion"', 'SIMPLE_V3', '{"match_keyword": "intrusion"}', true),
('mvs_operator', 'Action Opérateur MVS', 'SIMPLE_V3', '{"match_category": "operator_check"}', true),
('camera_active', 'Activité Caméra', 'SIMPLE_V3', '{"match_category": "camera"}', true),
('open_intrusion', 'Intrusion sur Incident Ouvert', 'SIMPLE_V3', '{"match_keyword": "intrusion", "is_open_only": true}', true),
('seq_mes_then_intrusion', 'Mise en service -> Intrusion (5m)', 'SEQUENCE', '{"seq_a_keyword": "mise en service", "seq_b_keyword": "intrusion", "seq_max_delay_seconds": 300, "seq_lookback_days": 1}', true)
ON CONFLICT (code) DO UPDATE SET payload = EXCLUDED.payload;

-- 2. Alert Rules (Base cases)

-- A) Intrusion 3 fois en 2 jours (Sliding Window V3)
INSERT INTO alert_rules (name, condition_type, value, frequency_count, sliding_window_days, is_active, match_keyword)
VALUES ('RÉPÉTITION: Intrusion (3x / 2j)', 'V3_FREQUENCY', 'N/A', 3, 2, true, 'intrusion')
ON CONFLICT (name) DO NOTHING;

-- B) Intrusion sur Incident Ouvert uniquement
INSERT INTO alert_rules (name, condition_type, value, is_open_only, is_active, match_keyword)
VALUES ('ALERTE: Intrusion (Sur Incident Ouvert)', 'V3_OPEN_ONLY', 'N/A', true, true, 'intrusion')
ON CONFLICT (name) DO NOTHING;

-- C) Séquence: Mise en Service -> Intrusion
INSERT INTO alert_rules (name, condition_type, value, sequence_enabled, seq_a_keyword, seq_b_keyword, seq_max_delay_seconds, seq_lookback_days, is_active)
VALUES ('SÉQUENCE: MES -> Intrusion (5min)', 'V3_SEQUENCE', 'N/A', true, 'mise en service', 'intrusion', 300, 1, true)
ON CONFLICT (name) DO NOTHING;

-- D) AST: OR(intrusion_text, AND(mvs_operator, open_intrusion))
-- Signifie: Alerte si "intrusion" OU si (Opérateur travaille ET incident tjs ouvert)
INSERT INTO alert_rules (name, condition_type, value, logic_enabled, logic_tree, is_active)
VALUES (
    'LOGIQUE: Intrusion OU (Opérateur + Ouvert)', 
    'V3_LOGIC', 
    'N/A', 
    true, 
    '{
        "op": "OR",
        "children": [
            {"ref": "cond:intrusion_text"},
            {
                "op": "AND",
                "children": [
                    {"ref": "cond:mvs_operator"},
                    {"ref": "cond:open_intrusion"}
                ]
            }
        ]
    }', 
    true
)
ON CONFLICT (name) DO NOTHING;
