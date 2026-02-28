'use client';

import React, { useState, useEffect } from 'react';
import {
    Box, Typography, Paper, Button, TextField, Switch, FormControlLabel,
    Grid, CircularProgress, Alert, Divider, Slider, Tooltip
} from '@mui/material';
import { Settings, Shield, Zap, RefreshCw, Save, Info } from 'lucide-react';
import Layout from '../../../components/Layout';
import { fetchWithAuth } from '@/lib/api';

interface MonitoringSettings {
    integrity: {
        warn_pct: number;
        critical_pct: number;
        block_on_xls_error: boolean;
        xls_is_source_of_truth: boolean;
    };
    rules: {
        score_threshold_default: number;
        exclude_dup_count: boolean;
    };
    replay: {
        default_full_history: boolean;
    };
    ui: {
        client_report_days_default: number;
    };
}

export default function AdminSettingsPage() {
    const [settings, setSettings] = useState<MonitoringSettings | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [saveLoading, setSaveLoading] = useState(false);
    const [success, setSuccess] = useState(false);

    const loadSettings = async () => {
        setLoading(true);
        setError('');
        try {
            const res = await fetchWithAuth('/settings/monitoring');
            if (!res.ok) throw new Error('Failed to fetch monitoring settings');
            const data = await res.json();
            setSettings(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadSettings();
    }, []);

    const handleSave = async () => {
        if (!settings) return;
        setSaveLoading(true);
        setSuccess(false);
        try {
            // Flatten settings for backend POST /api/v1/settings/
            const flattened: Record<string, string> = {
                'monitoring.integrity.warn_pct': settings.integrity.warn_pct.toString(),
                'monitoring.integrity.critical_pct': settings.integrity.critical_pct.toString(),
                'monitoring.integrity.block_on_xls_error': settings.integrity.block_on_xls_error.toString(),
                'monitoring.integrity.xls_is_source_of_truth': settings.integrity.xls_is_source_of_truth.toString(),
                'monitoring.rules.score_threshold_default': settings.rules.score_threshold_default.toString(),
                'monitoring.rules.exclude_dup_count': settings.rules.exclude_dup_count.toString(),
                'monitoring.replay.default_full_history': settings.replay.default_full_history.toString(),
                'monitoring.ui.client_report_days_default': settings.ui.client_report_days_default.toString(),
            };

            const res = await fetchWithAuth('/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(flattened)
            });

            if (!res.ok) throw new Error('Failed to update settings');

            setSuccess(true);
            setTimeout(() => setSuccess(false), 3000);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setSaveLoading(false);
        }
    };

    if (loading) return (
        <Layout>
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
                <CircularProgress />
            </Box>
        </Layout>
    );

    return (
        <Layout>
            <Box sx={{ p: 4, maxWidth: 1000, mx: 'auto' }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                    <Box>
                        <Typography variant="h4" fontWeight={800} sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Settings size={32} color="#3b82f6" /> Gouvernance & Settings
                        </Typography>
                        <Typography variant="body1" color="text.secondary">
                            Configuration globale du moteur d'ingestion et des règles métier (Roadmap V12)
                        </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2 }}>
                        <Button
                            startIcon={<RefreshCw size={18} />}
                            onClick={loadSettings}
                        >
                            Actualiser
                        </Button>
                        <Button
                            variant="contained"
                            color="primary"
                            startIcon={saveLoading ? <CircularProgress size={18} color="inherit" /> : <Save size={18} />}
                            onClick={handleSave}
                            disabled={saveLoading}
                        >
                            Enregistrer
                        </Button>
                    </Box>
                </Box>

                {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}
                {success && <Alert severity="success" sx={{ mb: 3 }}>Paramètres mis à jour avec succès !</Alert>}

                {settings && (
                    <Grid container spacing={4}>
                        {/* SECTION 1: INTEGRITE */}
                        <Grid item xs={12} md={6}>
                            <Paper sx={{ p: 3, borderRadius: 3, height: '100%' }}>
                                <Typography variant="h6" fontWeight={700} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Shield size={20} color="#10b981" /> Intégrité PDF/XLS
                                </Typography>
                                <Divider sx={{ my: 2 }} />

                                <Box sx={{ mb: 4 }}>
                                    <Typography variant="body2" gutterBottom sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                        Seuil Warning Integrity (%)
                                        <strong>{settings.integrity.warn_pct}%</strong>
                                    </Typography>
                                    <Slider
                                        value={settings.integrity.warn_pct}
                                        onChange={(_, val) => setSettings({ ...settings, integrity: { ...settings.integrity, warn_pct: val as number } })}
                                        min={0} max={100}
                                    />
                                </Box>

                                <Box sx={{ mb: 4 }}>
                                    <Typography variant="body2" gutterBottom sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                        Seuil Critique Integrity (%)
                                        <strong>{settings.integrity.critical_pct}%</strong>
                                    </Typography>
                                    <Slider
                                        value={settings.integrity.critical_pct}
                                        onChange={(_, val) => setSettings({ ...settings, integrity: { ...settings.integrity, critical_pct: val as number } })}
                                        min={0} max={100} color="error"
                                    />
                                </Box>

                                <FormControlLabel
                                    control={<Switch checked={settings.integrity.xls_is_source_of_truth} onChange={(e) => setSettings({ ...settings, integrity: { ...settings.integrity, xls_is_source_of_truth: e.target.checked } })} />}
                                    label={
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                            XLS est la source de vérité
                                            <Tooltip title="Si actif, un XLS valide passera en SUCCESS même si le PDF est manquant ou incomplet.">
                                                <Info size={14} style={{ opacity: 0.5 }} />
                                            </Tooltip>
                                        </Box>
                                    }
                                />

                                <FormControlLabel
                                    control={<Switch checked={settings.integrity.block_on_xls_error} onChange={(e) => setSettings({ ...settings, integrity: { ...settings.integrity, block_on_xls_error: e.target.checked } })} />}
                                    label="Bloquer sur erreur XLS"
                                />
                            </Paper>
                        </Grid>

                        {/* SECTION 2: REGLES METIER */}
                        <Grid item xs={12} md={6}>
                            <Paper sx={{ p: 3, borderRadius: 3, height: '100%' }}>
                                <Typography variant="h6" fontWeight={700} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Zap size={20} color="#f59e0b" /> Moteur de Règles
                                </Typography>
                                <Divider sx={{ my: 2 }} />

                                <Box sx={{ mb: 4 }}>
                                    <Typography variant="body2" gutterBottom sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                        Seuil de déclenchement (Score)
                                        <strong>{settings.rules.score_threshold_default}</strong>
                                    </Typography>
                                    <Slider
                                        value={settings.rules.score_threshold_default}
                                        onChange={(_, val) => setSettings({ ...settings, rules: { ...settings.rules, score_threshold_default: val as number } })}
                                        min={0} max={100}
                                    />
                                </Box>

                                <FormControlLabel
                                    control={<Switch checked={settings.rules.exclude_dup_count} onChange={(e) => setSettings({ ...settings, rules: { ...settings.rules, exclude_dup_count: e.target.checked } })} />}
                                    label="Exclure les doublons (dup_count > 0)"
                                />

                                <Box sx={{ mt: 4 }}>
                                    <Typography variant="subtitle2" gutterBottom>Options de Replay</Typography>
                                    <FormControlLabel
                                        control={<Switch checked={settings.replay.default_full_history} onChange={(e) => setSettings({ ...settings, replay: { ...settings.replay, default_full_history: e.target.checked } })} />}
                                        label="Replay sur tout l'historique par défaut"
                                    />
                                </Box>
                            </Paper>
                        </Grid>

                        {/* SECTION 3: UI & REPORTING */}
                        <Grid item xs={12}>
                            <Paper sx={{ p: 3, borderRadius: 3 }}>
                                <Typography variant="h6" fontWeight={700} gutterBottom>
                                    Expérience Utilisateur & Dashboard
                                </Typography>
                                <Divider sx={{ my: 2 }} />
                                <Grid container spacing={3}>
                                    <Grid item xs={12} sm={6}>
                                        <TextField
                                            fullWidth
                                            label="Historique par défaut du Rapport Client (jours)"
                                            type="number"
                                            value={settings.ui.client_report_days_default}
                                            onChange={(e) => setSettings({ ...settings, ui: { ...settings.ui, client_report_days_default: parseInt(e.target.value) || 30 } })}
                                        />
                                    </Grid>
                                </Grid>
                            </Paper>
                        </Grid>
                    </Grid>
                )}
            </Box>
        </Layout>
    );
}
