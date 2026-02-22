'use client';

import React, { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    Button,
    IconButton,
    Chip,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    FormControlLabel,
    Switch,
    Grid,
    Alert,
    Tooltip,
    Divider,
    CircularProgress,
    Box as MuiBox
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { Plus, Trash2, Edit, Play, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import Layout from '../../../components/Layout';

import { fetchWithAuth } from '../../../lib/api';

// TYPES
interface AlertRule {
    id: number;
    name: string;
    condition_type: string;
    value: string;
    scope_site_code?: string;

    // V3 / Sliding Window
    frequency_count: number;
    frequency_window: number;
    sliding_window_days: number;
    is_open_only: boolean;

    // Sequences
    sequence_enabled: boolean;
    seq_a_category?: string;
    seq_a_keyword?: string;
    seq_b_category?: string;
    seq_b_keyword?: string;
    seq_max_delay_seconds: number;
    seq_lookback_days: number;

    // Logic
    logic_enabled: boolean;
    logic_tree?: any;

    // Filters
    match_category?: string;
    match_keyword?: string;

    schedule_start?: string;
    schedule_end?: string;
    time_scope: 'NONE' | 'NIGHT' | 'WEEKEND' | 'HOLIDAYS' | 'OFF_BUSINESS_HOURS' | 'BUSINESS_HOURS';
    email_notify: boolean;
    is_active: boolean;
}

const DEFAULT_RULE: Partial<AlertRule> = {
    name: '',
    condition_type: 'V3_FREQUENCY',
    value: 'N/A',
    scope_site_code: '',
    frequency_count: 1,
    frequency_window: 0,
    sliding_window_days: 0,
    is_open_only: false,
    sequence_enabled: false,
    logic_enabled: false,
    time_scope: 'NONE',
    email_notify: false,
    is_active: true
};

export default function RulesPage() {
    const [rules, setRules] = useState<AlertRule[]>([]);
    const [loading, setLoading] = useState(true);
    const [open, setOpen] = useState(false);
    const [editingRule, setEditingRule] = useState<Partial<AlertRule> | null>(null);

    // DRY RUN STATE
    const [dryRunOpen, setDryRunOpen] = useState(false);
    const [selectedRule, setSelectedRule] = useState<AlertRule | null>(null);
    const [dryRunTime, setDryRunTime] = useState(new Date().toISOString().slice(0, 16));
    const [dryRunResults, setDryRunResults] = useState<any>(null);
    const [dryRunLoading, setDryRunLoading] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [replayLoading, setReplayLoading] = useState(false);
    const [replayMessage, setReplayMessage] = useState<string | null>(null);

    // FETCH
    const fetchRules = async () => {
        setLoading(true);
        try {
            const res = await fetchWithAuth('/alerts/rules');
            if (!res.ok) throw new Error('Failed to fetch rules');
            const data = await res.json();
            setRules(data);
            setError(null);
        } catch (err: any) {
            console.error(err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchRules(); }, []);

    // HANDLERS
    const handleOpenCreate = () => {
        setEditingRule(DEFAULT_RULE);
        setIsEditing(false);
        setOpen(true);
    };

    const handleOpenEdit = (rule: AlertRule) => {
        setEditingRule(rule);
        setIsEditing(true);
        setOpen(true);
    };

    const handleOpenDryRun = (rule: AlertRule) => {
        setSelectedRule(rule);
        setDryRunResults(null);
        setDryRunOpen(true);
    };

    const runDryRun = async () => {
        if (!selectedRule) return;
        setDryRunLoading(true);
        try {
            const res = await fetchWithAuth(`/alerts/rules/${selectedRule.id}/dry-run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    reference_time_override: dryRunTime,
                    limit: 50
                })
            });
            if (!res.ok) throw new Error('Dry run failed');
            const data = await res.json();
            setDryRunResults(data);
        } catch (err: any) {
            alert(err.message);
        } finally {
            setDryRunLoading(false);
        }
    };

    const handleClose = () => {
        setOpen(false);
        setError(null);
    };

    const formatTime = (value: string) => {
        // Only allow digits and colon
        const clean = value.replace(/[^\d]/g, '');
        if (clean.length <= 2) return clean;
        if (clean.length <= 4) return `${clean.slice(0, 2)}:${clean.slice(2)}`;
        return `${clean.slice(0, 2)}:${clean.slice(2, 4)}`;
    };

    const handleSave = async () => {
        try {
            const method = isEditing ? 'PUT' : 'POST';
            const url = isEditing
                ? `/alerts/rules/${editingRule.id}`
                : `/alerts/rules`;

            // Clean up empty strings for optional fields
            const payload = { ...editingRule };
            if (payload.scope_site_code === '') payload.scope_site_code = null;
            if (payload.schedule_start === '') payload.schedule_start = null;
            if (payload.schedule_end === '') payload.schedule_end = null;

            // Mode-specific cleanup
            if (payload.sequence_enabled) {
                payload.logic_enabled = false;
                payload.sliding_window_days = 0;
            } else if (payload.logic_enabled) {
                payload.sequence_enabled = false;
                payload.sliding_window_days = 0;
            }

            const res = await fetchWithAuth(url, {
                method,
                body: JSON.stringify(payload)
            });

            if (!res.ok) throw new Error('Failed to save rule');

            fetchRules();
            handleClose();
        } catch (err: any) {
            setError(err.message);
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Are you sure you want to delete this rule?')) return;
        try {
            const res = await fetchWithAuth(`/alerts/rules/${id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Failed to delete rule');
            fetchRules();
        } catch (err: any) {
            alert(err.message);
        }
    };

    const handleReplay = async () => {
        if (!confirm('This will re-process ALL historical events against ACTIVE rules. Determine alerts?')) return;
        setReplayLoading(true);
        try {
            const res = await fetchWithAuth('/alerts/replay', { method: 'POST' });
            if (!res.ok) throw new Error('Replay failed');
            setReplayMessage('Replay started in background...');
            setTimeout(() => setReplayMessage(null), 5000);
        } catch (err: any) {
            alert(err.message);
        } finally {
            setReplayLoading(false);
        }
    };

    const handleToggle = async (id: number, field: string, value: boolean) => {
        try {
            const res = await fetchWithAuth(`/alerts/rules/${id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ [field]: value })
            });
            if (!res.ok) throw new Error('Update failed');
            fetchRules();
        } catch (err: any) {
            alert(err.message);
        }
    };

    // UI COLUMNS
    const columns: GridColDef[] = [
        { field: 'id', headerName: 'ID', width: 60 },
        {
            field: 'is_active', headerName: 'Active', width: 90,
            renderCell: (params) => (
                <Switch
                    size="small"
                    checked={params.value}
                    onChange={(e) => handleToggle(params.row.id, 'is_active', e.target.checked)}
                    color="success"
                />
            )
        },
        {
            field: 'email_notify', headerName: 'Email', width: 90,
            renderCell: (params) => (
                <Switch
                    size="small"
                    checked={params.value}
                    onChange={(e) => handleToggle(params.row.id, 'email_notify', e.target.checked)}
                    color="primary"
                />
            )
        },
        {
            field: 'mode', headerName: 'Mode', width: 110,
            valueGetter: (params) => {
                const row = params.row;
                if (row.logic_enabled) return 'AST';
                if (row.sequence_enabled) return 'SEQUENCE';
                return 'SIMPLE';
            },
            renderCell: (params) => {
                const color = params.value === 'AST' ? 'secondary' : (params.value === 'SEQUENCE' ? 'warning' : 'primary');
                return <Chip label={params.value} size="small" color={color} sx={{ fontSize: 10, height: 18 }} />;
            }
        },
        {
            field: 'summary', headerName: 'Configuration Summary', flex: 1, minWidth: 250,
            renderCell: (params) => {
                const row = params.row;
                if (row.logic_enabled) {
                    return <Typography variant="caption" sx={{ color: 'secondary.main', fontStyle: 'italic' }}>Arbre logique actif (Complex Rule)</Typography>;
                }
                if (row.sequence_enabled) {
                    return (
                        <Box sx={{ fontSize: 10 }}>
                            <span style={{ fontWeight: 'bold' }}>{row.seq_a_keyword || row.seq_a_category || '?'}</span>
                            {' ➔ '}
                            <span style={{ fontWeight: 'bold' }}>{row.seq_b_keyword || row.seq_b_category || '?'}</span>
                            {` in ${row.seq_max_delay_seconds}s`}
                        </Box>
                    );
                }
                const filter = row.match_keyword ? `Key: ${row.match_keyword}` : (row.match_category ? `Cat: ${row.match_category}` : 'All');
                const freq = `${row.frequency_count}x`;
                const win = row.sliding_window_days > 0 ? `in ${row.sliding_window_days}d` : `in ${row.frequency_window}s`;
                const open = row.is_open_only ? '(Open Only)' : '';
                return (
                    <Box sx={{ fontSize: 10 }}>
                        <Typography variant="caption" display="block">
                            {filter} | <strong>{freq}</strong> {win} {open}
                        </Typography>
                    </Box>
                );
            }
        },
        { field: 'scope_site_code', headerName: 'Site', width: 80, valueFormatter: (params) => params.value || 'ALL' },
        {
            field: 'time_scope', headerName: 'Scope', width: 120,
            renderCell: (params) => (
                <Box>
                    <Chip label={params.value} size="small" variant="outlined" sx={{ fontSize: 8, height: 16 }} />
                    {params.row.schedule_start && (
                        <Typography variant="caption" display="block" sx={{ fontSize: 8, mt: 0.2 }}>
                            {params.row.schedule_start}-{params.row.schedule_end}
                        </Typography>
                    )}
                </Box>
            )
        },
        {
            field: 'actions', headerName: 'Actions', width: 130, align: 'right', headerAlign: 'right',
            renderCell: (params) => (
                <Box>
                    <Tooltip title="Tester la règle (Dry Run)">
                        <IconButton size="small" color="primary" onClick={() => handleOpenDryRun(params.row)}>
                            <Play size={16} />
                        </IconButton>
                    </Tooltip>
                    <IconButton size="small" onClick={() => handleOpenEdit(params.row)}><Edit size={16} /></IconButton>
                    <IconButton size="small" color="error" onClick={() => handleDelete(params.row.id)}><Trash2 size={16} /></IconButton>
                </Box>
            )
        }
    ];

    return (
        <Layout>
            <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', p: 3, gap: 2 }}>

                {/* HEADER */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box>
                        <Typography variant="h5" fontWeight="bold">Alert Rules</Typography>
                        <Typography variant="body2" color="text.secondary">
                            Configure automatic detection rules and notifications.
                        </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2 }}>
                        <Button
                            variant="outlined"
                            color="warning"
                            startIcon={<Play size={16} />}
                            onClick={handleReplay}
                            disabled={replayLoading}
                        >
                            {replayLoading ? 'Replaying...' : 'Replay Rules'}
                        </Button>
                        <Button
                            variant="contained"
                            startIcon={<Plus size={18} />}
                            onClick={handleOpenCreate}
                        >
                            New Rule
                        </Button>
                    </Box>
                </Box>

                <Alert severity="info" sx={{ mb: 1 }}>
                    ⚠️ Les changements de règles (activation/désactivation) n'affectent pas l'historique tant que vous ne relancez pas un <strong>Replay</strong> (mode "Replace Hits").
                </Alert>

                {replayMessage && <Alert severity="success" sx={{ mb: 1 }}>{replayMessage}</Alert>}
                {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}

                {/* TABLE */}
                <Paper sx={{ flex: 1, bgcolor: 'background.paper', overflow: 'hidden' }}>
                    <DataGrid
                        rows={rules}
                        columns={columns}
                        loading={loading}
                        rowHeight={50}
                        disableRowSelectionOnClick
                        sx={{ border: 0 }}
                    />
                </Paper>

                {/* DIALOG FOR CREATE/EDIT */}
                <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
                    <DialogTitle>{isEditing ? 'Edit Alert Rule' : 'Create New Alert Rule'}</DialogTitle>
                    <DialogContent dividers>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>

                            {/* BASIC INFO */}
                            <TextField
                                label="Rule Name"
                                fullWidth
                                size="small"
                                value={editingRule?.name || ''}
                                onChange={(e) => setEditingRule({ ...editingRule, name: e.target.value })}
                                placeholder="e.g. Critical Connection Loss"
                            />

                            {/* MODE SELECTOR */}
                            <Typography variant="caption" sx={{ mt: 1, fontWeight: 'bold', color: 'primary.main', textTransform: 'uppercase' }}>Detection Mode</Typography>
                            <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                                <Button
                                    variant={!editingRule?.sequence_enabled && !editingRule?.logic_enabled ? "contained" : "outlined"}
                                    size="small"
                                    onClick={() => setEditingRule({ ...editingRule, sequence_enabled: false, logic_enabled: false })}
                                    sx={{ flex: 1, fontSize: 10 }}
                                >
                                    Simple
                                </Button>
                                <Button
                                    variant={editingRule?.sequence_enabled ? "contained" : "outlined"}
                                    size="small"
                                    color="warning"
                                    onClick={() => setEditingRule({ ...editingRule, sequence_enabled: true, logic_enabled: false })}
                                    sx={{ flex: 1, fontSize: 10 }}
                                >
                                    Sequence
                                </Button>
                                <Button
                                    variant={editingRule?.logic_enabled ? "contained" : "outlined"}
                                    size="small"
                                    color="secondary"
                                    onClick={() => setEditingRule({ ...editingRule, sequence_enabled: false, logic_enabled: true })}
                                    sx={{ flex: 1, fontSize: 10 }}
                                >
                                    Logic (AST)
                                </Button>
                            </Box>

                            <Divider />

                            {/* --- MODE SIMPLE --- */}
                            {!editingRule?.sequence_enabled && !editingRule?.logic_enabled && (
                                <Grid container spacing={2}>
                                    <Grid item xs={12} md={6}>
                                        <TextField
                                            label="Match Category"
                                            fullWidth
                                            size="small"
                                            value={editingRule?.match_category || ''}
                                            onChange={(e) => setEditingRule({ ...editingRule, match_category: e.target.value })}
                                            placeholder="e.g. security, camera"
                                        />
                                    </Grid>
                                    <Grid item xs={12} md={6}>
                                        <TextField
                                            label="Match Keyword"
                                            fullWidth
                                            size="small"
                                            value={editingRule?.match_keyword || ''}
                                            onChange={(e) => setEditingRule({ ...editingRule, match_keyword: e.target.value })}
                                            placeholder="e.g. intrusion"
                                        />
                                    </Grid>
                                    <Grid item xs={6}>
                                        <TextField
                                            label="Sliding Window (Days)"
                                            type="number"
                                            fullWidth
                                            size="small"
                                            value={editingRule?.sliding_window_days || 0}
                                            onChange={(e) => setEditingRule({ ...editingRule, sliding_window_days: parseInt(e.target.value) })}
                                        />
                                    </Grid>
                                    <Grid item xs={6}>
                                        <FormControlLabel
                                            control={<Switch size="small" checked={editingRule?.is_open_only || false} onChange={(e) => setEditingRule({ ...editingRule, is_open_only: e.target.checked })} />}
                                            label={<Typography variant="caption">Open Only (Incident)</Typography>}
                                        />
                                    </Grid>
                                </Grid>
                            )}

                            {/* --- MODE SEQUENCE --- */}
                            {editingRule?.sequence_enabled && (
                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                                    <Typography variant="caption" sx={{ color: 'warning.main', fontWeight: 'bold' }}>Séquence A ➔ B</Typography>
                                    <Grid container spacing={1}>
                                        <Grid item xs={6}>
                                            <TextField label="A: Keyword" size="small" fullWidth value={editingRule?.seq_a_keyword || ''} onChange={(e) => setEditingRule({ ...editingRule, seq_a_keyword: e.target.value })} />
                                        </Grid>
                                        <Grid item xs={6}>
                                            <TextField label="A: Category" size="small" fullWidth value={editingRule?.seq_a_category || ''} onChange={(e) => setEditingRule({ ...editingRule, seq_a_category: e.target.value })} />
                                        </Grid>
                                        <Grid item xs={6}>
                                            <TextField label="B: Keyword" size="small" fullWidth value={editingRule?.seq_b_keyword || ''} onChange={(e) => setEditingRule({ ...editingRule, seq_b_keyword: e.target.value })} />
                                        </Grid>
                                        <Grid item xs={6}>
                                            <TextField label="B: Category" size="small" fullWidth value={editingRule?.seq_b_category || ''} onChange={(e) => setEditingRule({ ...editingRule, seq_b_category: e.target.value })} />
                                        </Grid>
                                        <Grid item xs={6}>
                                            <TextField label="Max Delay (sec)" type="number" size="small" fullWidth value={editingRule?.seq_max_delay_seconds || 300} onChange={(e) => setEditingRule({ ...editingRule, seq_max_delay_seconds: parseInt(e.target.value) })} />
                                        </Grid>
                                        <Grid item xs={6}>
                                            <TextField label="Lookback (days)" type="number" size="small" fullWidth value={editingRule?.seq_lookback_days || 2} onChange={(e) => setEditingRule({ ...editingRule, seq_lookback_days: parseInt(e.target.value) })} />
                                        </Grid>
                                    </Grid>
                                </Box>
                            )}

                            {/* --- MODE AST --- */}
                            {editingRule?.logic_enabled && (
                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                    <Alert severity="warning" sx={{ fontSize: 10, py: 0 }}>
                                        Mode Editeur JSON (AST). Exemple: <code>{`{"op": "AND", "children": [{"ref": "cond:CODE"}]}`}</code>
                                    </Alert>
                                    <TextField
                                        label="Logic Tree (JSON)"
                                        multiline
                                        rows={4}
                                        fullWidth
                                        value={typeof editingRule?.logic_tree === 'string' ? editingRule.logic_tree : JSON.stringify(editingRule?.logic_tree, null, 2)}
                                        onChange={(e) => {
                                            try {
                                                const parsed = JSON.parse(e.target.value);
                                                setEditingRule({ ...editingRule, logic_tree: parsed });
                                            } catch (err) {
                                                setEditingRule({ ...editingRule, logic_tree: e.target.value });
                                            }
                                        }}
                                        sx={{ fontFamily: 'monospace', fontSize: 11 }}
                                    />
                                </Box>
                            )}

                            <Divider />

                            {/* COMMON: SCOPE & FREQUENCY */}
                            <Grid container spacing={2}>
                                <Grid item xs={12} md={4}>
                                    <TextField
                                        label="Site (Optional)"
                                        size="small"
                                        fullWidth
                                        value={editingRule?.scope_site_code || ''}
                                        onChange={(e) => setEditingRule({ ...editingRule, scope_site_code: e.target.value })}
                                    />
                                </Grid>
                                <Grid item xs={6} md={4}>
                                    <TextField
                                        label="Min Occurrences"
                                        type="number"
                                        size="small"
                                        fullWidth
                                        value={editingRule?.frequency_count || 1}
                                        onChange={(e) => setEditingRule({ ...editingRule, frequency_count: parseInt(e.target.value) })}
                                    />
                                </Grid>
                                <Grid item xs={6} md={4}>
                                    <TextField
                                        label="Window (sec)"
                                        type="number"
                                        size="small"
                                        fullWidth
                                        value={editingRule?.frequency_window || 0}
                                        onChange={(e) => setEditingRule({ ...editingRule, frequency_window: parseInt(e.target.value) })}
                                    />
                                </Grid>
                                <Grid item xs={12} md={6}>
                                    <FormControl fullWidth size="small">
                                        <InputLabel>Time Scope</InputLabel>
                                        <Select
                                            value={editingRule?.time_scope || 'NONE'}
                                            label="Time Scope"
                                            onChange={(e) => setEditingRule({ ...editingRule, time_scope: e.target.value as any })}
                                        >
                                            <MenuItem value="NONE">None (Always)</MenuItem>
                                            <MenuItem value="BUSINESS_HOURS">Business Hours</MenuItem>
                                            <MenuItem value="OFF_BUSINESS_HOURS">Off-Business Hours</MenuItem>
                                            <MenuItem value="NIGHT">Night (22:00-06:00)</MenuItem>
                                            <MenuItem value="WEEKEND">Weekend (Sat-Sun)</MenuItem>
                                            <MenuItem value="HOLIDAYS">French Holidays</MenuItem>
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid item xs={12} md={6}>
                                    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', height: '100%' }}>
                                        <FormControlLabel
                                            control={<Switch size="small" checked={editingRule?.email_notify || false} onChange={(e) => setEditingRule({ ...editingRule, email_notify: e.target.checked })} />}
                                            label={<Typography variant="caption">Email Alert</Typography>}
                                        />
                                        <FormControlLabel
                                            control={<Switch size="small" checked={editingRule?.is_active || false} onChange={(e) => setEditingRule({ ...editingRule, is_active: e.target.checked })} />}
                                            label={<Typography variant="caption">Active</Typography>}
                                        />
                                    </Box>
                                </Grid>
                            </Grid>

                        </Box>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={handleClose}>Cancel</Button>
                        <Button onClick={handleSave} variant="contained" disabled={!editingRule?.name}>
                            Save Rule
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* DRY RUN MODAL */}
                <Dialog open={dryRunOpen} onClose={() => setDryRunOpen(false)} maxWidth="md" fullWidth>
                    <DialogTitle>
                        Dry Run Analysis: {selectedRule?.name}
                    </DialogTitle>
                    <DialogContent dividers>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
                            <Alert severity="info" icon={<Clock size={20} />}>
                                Simulez le déclenchement de cette règle sur les derniers événements en changeant l'heure de référence (déterminisme temporel).
                            </Alert>

                            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                                <TextField
                                    label="Reference Time Override"
                                    type="datetime-local"
                                    size="small"
                                    value={dryRunTime}
                                    onChange={(e: any) => setDryRunTime(e.target.value)}
                                    sx={{ flex: 1 }}
                                />
                                <Button
                                    variant="contained"
                                    onClick={runDryRun}
                                    disabled={dryRunLoading}
                                    startIcon={dryRunLoading ? <CircularProgress size={16} color="inherit" /> : <Play size={16} />}
                                >
                                    {dryRunLoading ? 'Evaluating...' : 'Run Simulation'}
                                </Button>
                            </Box>

                            {dryRunResults && (
                                <Box sx={{ mt: 2 }}>
                                    <Divider sx={{ mb: 2 }} />
                                    <Typography variant="h6" gutterBottom sx={{ fontSize: '1rem' }}>
                                        Results: {dryRunResults.matched_count} matches / {dryRunResults.evaluated_count} evaluated
                                    </Typography>

                                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                        {dryRunResults.results.map((res: any, idx: number) => (
                                            <Paper key={idx} variant="outlined" sx={{ p: 1.5, borderColor: res.triggered ? 'success.main' : 'divider', borderLeftWidth: 4, borderLeftColor: res.triggered ? 'success.main' : 'error.light' }}>
                                                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                                    <Typography variant="caption" fontWeight="bold">
                                                        Event #{res.event_id} - {new Date(res.event_time).toLocaleString()}
                                                    </Typography>
                                                    <Chip
                                                        label={res.triggered ? 'TRIGGERED' : 'IGNORED'}
                                                        size="small"
                                                        color={res.triggered ? 'success' : 'default'}
                                                        sx={{ height: 18, fontSize: 9 }}
                                                    />
                                                </Box>
                                                <Box sx={{ fontSize: 10, color: 'text.secondary', mt: 0.5 }}>
                                                    {res.explanations.map((msg: string, i: number) => (
                                                        <Box key={i} sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5, color: msg.includes('met') || msg.includes('matched') ? 'success.main' : (msg.includes('mismatch') || msg.includes('fail') || msg.includes('Outside') ? 'error.main' : 'text.primary') }}>
                                                            • {msg}
                                                        </Box>
                                                    ))}
                                                </Box>
                                            </Paper>
                                        ))}
                                    </Box>
                                </Box>
                            )}
                        </Box>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setDryRunOpen(false)}>Fermer</Button>
                    </DialogActions>
                </Dialog>

            </Box>
        </Layout >
    );
}
