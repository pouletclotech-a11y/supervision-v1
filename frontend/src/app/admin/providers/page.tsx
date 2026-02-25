'use client';

import React, { useState, useEffect } from 'react';
import {
    Box, Typography, Paper, Button, IconButton, Chip,
    Dialog, DialogTitle, DialogContent, DialogActions,
    TextField, Switch, FormControlLabel, Grid, Select, MenuItem, InputLabel, FormControl,
    CircularProgress, Alert, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    Tabs, Tab, List, ListItem, ListItemText, ListItemSecondaryAction, Divider
} from '@mui/material';
import { Edit3, RefreshCw, Zap, Mail, Activity, Clock, Shield, Plus, X, Globe, UserCheck } from 'lucide-react';
import Layout from '../../../components/Layout';
import { fetchWithAuth } from '@/lib/api';

interface SmtpRule {
    id?: number;
    match_type: string;
    match_value: string;
    priority: number;
    is_active: boolean;
    expected_emails_per_day?: number;
    expected_interval_minutes?: number;
}

interface Provider {
    id: number;
    code: string;
    label: string;
    ui_color: string | null;
    is_active: boolean;
    recovery_email: string | null;
    expected_emails_per_day: number;
    expected_frequency_type: string;
    silence_threshold_minutes: number;
    expected_interval_minutes: number | null;
    monitoring_enabled: boolean;
    accepted_attachment_types: string[];
    email_match_keyword: string | null;
    last_successful_import_at: string | null;
}

export default function ProvidersPage() {
    const [providers, setProviders] = useState<Provider[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [editingProvider, setEditingProvider] = useState<Partial<Provider> | null>(null);
    const [providerRules, setProviderRules] = useState<SmtpRule[]>([]);
    const [tabIndex, setTabIndex] = useState(0);
    const [saveLoading, setSaveLoading] = useState(false);

    // Form states for adding rules/formats
    const [newRuleValue, setNewRuleValue] = useState('');
    const [newRuleType, setNewRuleType] = useState('EXACT');
    const [newFormat, setNewFormat] = useState('');

    const loadProviders = async () => {
        setLoading(true);
        setError('');
        try {
            const res = await fetchWithAuth('/admin/providers');
            if (!res.ok) throw new Error('Failed to fetch providers');
            const data = await res.json();
            setProviders(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const loadRules = async (providerId: number) => {
        try {
            const res = await fetchWithAuth(`/admin/providers/${providerId}/rules`);
            if (res.ok) {
                const data = await res.json();
                setProviderRules(data);
            }
        } catch (err) {
            console.error("Failed to load rules", err);
        }
    };

    const handleEdit = (provider: Provider) => {
        setEditingProvider(provider);
        setTabIndex(0);
        loadRules(provider.id);
    };

    const handleCreateNew = () => {
        setEditingProvider({
            code: '',
            label: '',
            ui_color: '#3b82f6',
            is_active: true,
            recovery_email: '',
            expected_emails_per_day: 0,
            expected_frequency_type: 'daily',
            silence_threshold_minutes: 1440,
            expected_interval_minutes: null,
            monitoring_enabled: false,
            accepted_attachment_types: ['pdf', 'xls', 'xlsx'],
            email_match_keyword: ''
        });
        setProviderRules([]);
        setTabIndex(0);
    };

    useEffect(() => {
        loadProviders();
    }, []);

    const handleSave = async () => {
        if (!editingProvider) return;
        setSaveLoading(true);
        try {
            const isNew = !editingProvider.id;
            const url = isNew ? '/admin/providers' : `/admin/providers/${editingProvider.id}`;

            const method = isNew ? 'POST' : 'PATCH';
            const res = await fetchWithAuth(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(editingProvider)
            });

            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(errorData.detail || `Failed to save: ${res.statusText}`);
            }

            await loadProviders();
            setEditingProvider(null);
        } catch (err: any) {
            alert(`Erreur: ${err.message}`);
        } finally {
            setSaveLoading(false);
        }
    };

    const addRule = async () => {
        if (!newRuleValue || !editingProvider?.id) return;
        try {
            const res = await fetchWithAuth(`/admin/providers/${editingProvider.id}/rules`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    match_type: newRuleType,
                    match_value: newRuleValue,
                    priority: newRuleType === 'EXACT' ? 10 : 5,
                    is_active: true
                })
            });
            if (res.ok) {
                setNewRuleValue('');
                loadRules(editingProvider.id);
            }
        } catch (err) { alert("Failed to add rule"); }
    };

    const deleteRule = async (ruleId: number) => {
        try {
            const res = await fetchWithAuth(`/admin/providers/rules/${ruleId}`, {
                method: 'DELETE'
            });
            if (res.ok && editingProvider?.id) loadRules(editingProvider.id);
        } catch (err) { alert("Failed to delete rule"); }
    };

    const toggleFormat = (format: string) => {
        if (!editingProvider) return;
        const current = editingProvider.accepted_attachment_types || [];
        const next = current.includes(format)
            ? current.filter(f => f !== format)
            : [...current, format];
        setEditingProvider({ ...editingProvider, accepted_attachment_types: next });
    };

    const addCustomFormat = () => {
        if (!newFormat || !editingProvider) return;
        const cleanExt = newFormat.toLowerCase().replace('.', '').trim();
        const current = editingProvider.accepted_attachment_types || [];
        if (!current.includes(cleanExt)) {
            setEditingProvider({ ...editingProvider, accepted_attachment_types: [...current, cleanExt] });
        }
        setNewFormat('');
    };

    return (
        <Layout>
            <Box sx={{ p: 4 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                    <Box>
                        <Typography variant="h5" fontWeight={700} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Zap size={24} /> Providers (Source of Truth)
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Configuration unifiée : Sécurité, Whitelist et Monitoring
                        </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2 }}>
                        <Button
                            variant="contained"
                            color="success"
                            startIcon={<Zap size={18} />}
                            onClick={handleCreateNew}
                        >
                            Nouveau Provider
                        </Button>
                        <Button
                            startIcon={<RefreshCw size={18} />}
                            onClick={loadProviders}
                            disabled={loading}
                        >
                            Actualiser
                        </Button>
                    </Box>
                </Box>

                {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

                {loading ? (
                    <Box display="flex" justifyContent="center" p={5}><CircularProgress /></Box>
                ) : (
                    <TableContainer component={Paper} sx={{ borderRadius: 3 }}>
                        <Table>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Provider</TableCell>
                                    <TableCell>Code</TableCell>
                                    <TableCell>Filtrage</TableCell>
                                    <TableCell>Monitoring</TableCell>
                                    <TableCell>Dernier Import</TableCell>
                                    <TableCell align="right">Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {providers.map((p) => (
                                    <TableRow key={p.id} hover>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: p.ui_color || '#ccc' }} />
                                                <Typography variant="body2" fontWeight={600}>{p.label}</Typography>
                                            </Box>
                                        </TableCell>
                                        <TableCell><code>{p.code}</code></TableCell>
                                        <TableCell>
                                            {p.email_match_keyword ? (
                                                <Chip label={p.email_match_keyword} size="small" variant="outlined" color="primary" />
                                            ) : (
                                                <Typography variant="caption" color="text.disabled">Aucun keyword</Typography>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                <Chip
                                                    label={p.monitoring_enabled ? "Surveillance" : "Simple"}
                                                    size="small"
                                                    color={p.monitoring_enabled ? "success" : "default"}
                                                />
                                                <Typography variant="caption">{p.expected_emails_per_day}j</Typography>
                                            </Box>
                                        </TableCell>
                                        <TableCell>
                                            {p.last_successful_import_at ? new Date(p.last_successful_import_at).toLocaleString('fr-FR') : '—'}
                                        </TableCell>
                                        <TableCell align="right">
                                            <IconButton onClick={() => handleEdit(p)} size="small" color="primary">
                                                <Edit3 size={18} />
                                            </IconButton>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}

                {/* UNIFIED DIALOG */}
                <Dialog
                    open={!!editingProvider}
                    onClose={() => setEditingProvider(null)}
                    maxWidth="md"
                    fullWidth
                    PaperProps={{ sx: { borderRadius: 3, minHeight: '60vh' } }}
                >
                    <DialogTitle sx={{ fontWeight: 700, pb: 0 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Box sx={{ width: 16, height: 16, borderRadius: '50%', bgcolor: editingProvider?.ui_color || '#ccc' }} />
                            {editingProvider?.id ? `Modifier ${editingProvider.label}` : 'Nouveau Provider'}
                        </Box>
                        <Tabs value={tabIndex} onChange={(_, val) => setTabIndex(val)} sx={{ mt: 2 }}>
                            <Tab label="Général" icon={<Mail size={16} />} iconPosition="start" />
                            <Tab label="Monitoring" icon={<Activity size={16} />} iconPosition="start" />
                            <Tab label="Sécurité" icon={<Shield size={16} />} iconPosition="start" />
                        </Tabs>
                    </DialogTitle>

                    <DialogContent dividers>
                        {/* TAB 0: GENERAL */}
                        {tabIndex === 0 && (
                            <Grid container spacing={3} sx={{ mt: 1 }}>
                                <Grid item xs={12} sm={6}>
                                    <TextField
                                        fullWidth label="Code Provider"
                                        value={editingProvider?.code || ''}
                                        disabled={!!editingProvider?.id}
                                        onChange={(e) => setEditingProvider({ ...editingProvider, code: e.target.value.toUpperCase() })}
                                    />
                                </Grid>
                                <Grid item xs={12} sm={6}>
                                    <TextField
                                        fullWidth label="Nom / Label"
                                        value={editingProvider?.label || ''}
                                        onChange={(e) => setEditingProvider({ ...editingProvider, label: e.target.value })}
                                    />
                                </Grid>
                                <Grid item xs={12} sm={6}>
                                    <TextField
                                        fullWidth label="Couleur UI"
                                        type="color"
                                        value={editingProvider?.ui_color || '#3b82f6'}
                                        onChange={(e) => setEditingProvider({ ...editingProvider, ui_color: e.target.value })}
                                    />
                                </Grid>
                                <Grid item xs={12} sm={6}>
                                    <FormControlLabel
                                        control={<Switch checked={editingProvider?.is_active || false} onChange={(e) => setEditingProvider({ ...editingProvider, is_active: e.target.checked })} />}
                                        label="Provider Actif"
                                    />
                                </Grid>
                            </Grid>
                        )}

                        {/* TAB 1: MONITORING */}
                        {tabIndex === 1 && (
                            <Grid container spacing={3} sx={{ mt: 1 }}>
                                <Grid item xs={12}>
                                    <FormControlLabel
                                        control={<Switch checked={editingProvider?.monitoring_enabled || false} onChange={(e) => setEditingProvider({ ...editingProvider, monitoring_enabled: e.target.checked })} />}
                                        label="Activer les alertes de retard/silence"
                                    />
                                </Grid>
                                <Grid item xs={12} sm={6}>
                                    <TextField
                                        fullWidth label="Volume attendu / 24h" type="number"
                                        value={editingProvider?.expected_emails_per_day || 0}
                                        onChange={(e) => setEditingProvider({ ...editingProvider, expected_emails_per_day: parseInt(e.target.value) })}
                                        InputProps={{ startAdornment: <Activity size={18} style={{ marginRight: 8, opacity: 0.5 }} /> }}
                                    />
                                </Grid>
                                <Grid item xs={12} sm={6}>
                                    <TextField
                                        fullWidth label="Seuil de silence (min)" type="number"
                                        value={editingProvider?.silence_threshold_minutes || 1440}
                                        onChange={(e) => setEditingProvider({ ...editingProvider, silence_threshold_minutes: parseInt(e.target.value) })}
                                        helperText="1440 = 24h sans signal"
                                    />
                                </Grid>
                                <Grid item xs={12} sm={6}>
                                    <TextField
                                        fullWidth label="Intervalle entre imports (min)" type="number"
                                        value={editingProvider?.expected_interval_minutes || ''}
                                        onChange={(e) => setEditingProvider({ ...editingProvider, expected_interval_minutes: e.target.value ? parseInt(e.target.value) : null })}
                                        helperText="Optionnel : cadence régulière"
                                    />
                                </Grid>
                                <Grid item xs={12} sm={6}>
                                    <TextField
                                        fullWidth label="Email de secours"
                                        value={editingProvider?.recovery_email || ''}
                                        onChange={(e) => setEditingProvider({ ...editingProvider, recovery_email: e.target.value })}
                                        placeholder="alerte@exemple.com"
                                    />
                                </Grid>
                            </Grid>
                        )}

                        {/* TAB 2: SECURITE */}
                        {tabIndex === 2 && (
                            <Grid container spacing={3} sx={{ mt: 1 }}>
                                <Grid item xs={12}>
                                    <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <Shield size={16} /> Whitelist (Expéditeurs autorisés)
                                    </Typography>
                                    <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                                        <Select size="small" value={newRuleType} onChange={(e) => setNewRuleType(e.target.value)}>
                                            <MenuItem value="EXACT">Email</MenuItem>
                                            <MenuItem value="DOMAIN">Domaine</MenuItem>
                                        </Select>
                                        <TextField
                                            size="small" fullWidth placeholder={newRuleType === 'EXACT' ? "user@domain.com" : "domain.com"}
                                            value={newRuleValue} onChange={(e) => setNewRuleValue(e.target.value)}
                                        />
                                        <Button variant="outlined" onClick={addRule} disabled={!editingProvider?.id}><Plus size={20} /></Button>
                                    </Box>
                                    {!editingProvider?.id && <Alert severity="info" sx={{ mb: 2 }}>Enregistrez le provider pour pouvoir ajouter des règles de whitelist.</Alert>}
                                    <Paper variant="outlined" sx={{ maxHeight: 150, overflow: 'auto' }}>
                                        <List dense>
                                            {providerRules.length === 0 && <ListItem><ListItemText secondary="Aucune règle définie" /></ListItem>}
                                            {providerRules.map((rule) => (
                                                <ListItem key={rule.id}>
                                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                                                        {rule.match_type === 'EXACT' ? <UserCheck size={14} /> : <Globe size={14} />}
                                                        <ListItemText primary={rule.match_value} />
                                                        <ListItemSecondaryAction>
                                                            <IconButton edge="end" size="small" onClick={() => deleteRule(rule.id!)}>
                                                                <X size={14} />
                                                            </IconButton>
                                                        </ListItemSecondaryAction>
                                                    </Box>
                                                </ListItem>
                                            ))}
                                        </List>
                                    </Paper>
                                </Grid>

                                <Grid item xs={12}>
                                    <Divider sx={{ my: 1 }} />
                                    <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>Filtrage par mot-clé (Sujet)</Typography>
                                    <TextField
                                        fullWidth size="small" placeholder="Ex: RAPPORT, ALARME..."
                                        value={editingProvider?.email_match_keyword || ''}
                                        onChange={(e) => setEditingProvider({ ...editingProvider, email_match_keyword: e.target.value })}
                                        helperText="Ignorera les emails dont le sujet ne contient pas ce mot."
                                    />
                                </Grid>

                                <Grid item xs={12}>
                                    <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>Formats de fichiers acceptés</Typography>
                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                                        {['pdf', 'xls', 'xlsx', 'csv'].map(f => (
                                            <Chip
                                                key={f} label={f.toUpperCase()} clickable
                                                color={editingProvider?.accepted_attachment_types?.includes(f) ? "primary" : "default"}
                                                variant={editingProvider?.accepted_attachment_types?.includes(f) ? "filled" : "outlined"}
                                                onClick={() => toggleFormat(f)}
                                            />
                                        ))}
                                    </Box>
                                    <Box sx={{ display: 'flex', gap: 1 }}>
                                        <TextField
                                            size="small" label="Autre extension" placeholder="xml, txt..."
                                            value={newFormat} onChange={(e) => setNewFormat(e.target.value)}
                                        />
                                        <Button variant="outlined" onClick={addCustomFormat}><Plus size={20} /></Button>
                                    </Box>
                                    <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                        {editingProvider?.accepted_attachment_types?.filter(f => !['pdf', 'xls', 'xlsx', 'csv'].includes(f)).map(f => (
                                            <Chip key={f} label={f} size="small" onDelete={() => toggleFormat(f)} />
                                        ))}
                                    </Box>
                                </Grid>
                            </Grid>
                        )}
                    </DialogContent>

                    <DialogActions sx={{ p: 2, px: 3 }}>
                        <Button onClick={() => setEditingProvider(null)}>Annuler</Button>
                        <Button
                            variant="contained"
                            onClick={handleSave}
                            disabled={saveLoading}
                            startIcon={saveLoading ? <CircularProgress size={18} /> : null}
                        >
                            Enregistrer le Provider
                        </Button>
                    </DialogActions>
                </Dialog>
            </Box>
        </Layout>
    );
}
