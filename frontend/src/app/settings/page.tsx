'use client';

import React, { useState, useEffect } from 'react';
import Layout from '../../components/Layout';
import { fetchWithAuth } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';

import {
    Box,
    Paper,
    Typography,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Button,
    Tabs,
    Tab,
    Alert,
    CircularProgress,
    Divider,
    Grid,
    MenuItem,
    Chip,
    IconButton
} from '@mui/material';
import { Save, Mail, Server, ShieldCheck, Trash2, Plus } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface Setting {
    key: string;
    value: string;
    description?: string;
}

interface MonitoringProvider {
    id: number;
    code: string;
    label: string;
    ui_color?: string;
    is_active: boolean;
}

interface SmtpRule {
    id: number;
    provider_id: number;
    match_type: string;
    match_value: string;
    priority: number;
    is_active: boolean;
}

export default function SettingsPage() {
    const { user } = useAuth();
    const [tab, setTab] = useState(0);
    const [settings, setSettings] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [testLoading, setTestLoading] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

    // Providers State
    const [providers, setProviders] = useState<MonitoringProvider[]>([]);
    const [rules, setRules] = useState<Record<number, SmtpRule[]>>({});
    const [loadingProviders, setLoadingProviders] = useState(false);

    // Modal States
    const [openProviderDialog, setOpenProviderDialog] = useState(false);
    const [selectedProvider, setSelectedProvider] = useState<MonitoringProvider | null>(null);
    const [providerForm, setProviderForm] = useState({ code: '', label: '', ui_color: '', is_active: true });

    const [openRuleDialog, setOpenRuleDialog] = useState(false);
    const [selectedRule, setSelectedRule] = useState<SmtpRule | null>(null);
    const [ruleForm, setRuleForm] = useState({ match_type: 'DOMAIN', match_value: '', priority: 0, is_active: true });
    const [activeProviderId, setActiveProviderId] = useState<number | null>(null);

    // Whitelist State
    const [whitelistInput, setWhitelistInput] = useState('');

    // Test Email Dialog
    const [openEmailDialog, setOpenEmailDialog] = useState(false);
    const [testRecipient, setTestRecipient] = useState('');

    // Fetch on mount
    useEffect(() => {
        if (user && user.role === 'ADMIN') {
            fetchSettings();
        }
        fetchProviders();
    }, [user]);

    const fetchSettings = async () => {
        setLoading(true);
        try {
            const res = await fetchWithAuth('/settings/');
            if (res.ok) {
                const data: Setting[] = await res.json();
                const map: Record<string, string> = {};
                data.forEach(s => map[s.key] = s.value);
                setSettings(map);
            }
        } catch (err) {
            console.error(err);
            setMessage({ type: 'error', text: 'Failed to load settings.' });
        } finally {
            setLoading(false);
        }
    };

    const fetchProviders = async () => {
        setLoadingProviders(true);
        try {
            const res = await fetchWithAuth('/connections/providers');
            if (res.ok) {
                setProviders(await res.json());
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoadingProviders(false);
        }
    };

    const fetchRules = async (providerId: number) => {
        try {
            const res = await fetchWithAuth(`/connections/providers/${providerId}/rules`);
            if (res.ok) {
                const data = await res.json();
                setRules((prev: Record<number, SmtpRule[]>) => ({ ...prev, [providerId]: data }));
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleSaveProvider = async () => {
        setSaving(true);
        try {
            const method = selectedProvider ? 'PATCH' : 'POST';
            const url = selectedProvider ? `/connections/providers/${selectedProvider.id}` : '/connections/providers';
            const res = await fetchWithAuth(url, {
                method,
                body: JSON.stringify(providerForm)
            });
            if (res.ok) {
                setMessage({ type: 'success', text: `Provider ${selectedProvider ? 'updated' : 'created'} successfully.` });
                setOpenProviderDialog(false);
                fetchProviders();
            } else {
                const err = await res.json();
                setMessage({ type: 'error', text: err.detail || 'Failed to save provider.' });
            }
        } catch (err) {
            setMessage({ type: 'error', text: 'Network error.' });
        } finally {
            setSaving(false);
        }
    };

    const handleDeleteProvider = async (id: number) => {
        if (!confirm('Are you sure you want to delete this provider? This will delete all its connections and rules.')) return;
        try {
            const res = await fetchWithAuth(`/connections/providers/${id}`, { method: 'DELETE' });
            if (res.ok) {
                setMessage({ type: 'success', text: 'Provider deleted.' });
                fetchProviders();
            } else {
                const err = await res.json();
                setMessage({ type: 'error', text: err.detail || 'Failed to delete provider.' });
            }
        } catch (err) {
            setMessage({ type: 'error', text: 'Network error.' });
        }
    };

    const handleSaveRule = async () => {
        if (!activeProviderId) return;
        setSaving(true);
        try {
            const method = selectedRule ? 'PATCH' : 'POST';
            const url = selectedRule
                ? `/connections/providers/${activeProviderId}/rules/${selectedRule.id}`
                : `/connections/providers/${activeProviderId}/rules`;
            const res = await fetchWithAuth(url, {
                method,
                body: JSON.stringify(ruleForm)
            });
            if (res.ok) {
                setMessage({ type: 'success', text: 'Rule saved.' });
                setOpenRuleDialog(false);
                fetchRules(activeProviderId);
            } else {
                const err = await res.json();
                setMessage({ type: 'error', text: err.detail || 'Failed to save rule.' });
            }
        } catch (err) {
            setMessage({ type: 'error', text: 'Network error.' });
        } finally {
            setSaving(false);
        }
    };

    const handleDeleteRule = async (providerId: number, ruleId: number) => {
        if (!confirm('Delete this rule?')) return;
        try {
            const res = await fetchWithAuth(`/connections/providers/${providerId}/rules/${ruleId}`, { method: 'DELETE' });
            if (res.ok) {
                fetchRules(providerId);
            } else {
                const err = await res.json();
                alert(err.detail || 'Failed to delete rule.');
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleChange = (key: string, value: string) => {
        setSettings((prev: Record<string, string>) => ({ ...prev, [key]: value }));
    };

    const handleSave = async () => {
        setSaving(true);
        setMessage(null);
        try {
            const res = await fetchWithAuth('/settings/', {
                method: 'POST',
                body: JSON.stringify(settings)
            });
            if (res.ok) {
                setMessage({ type: 'success', text: 'Settings saved successfully.' });
            } else {
                setMessage({ type: 'error', text: 'Failed to save settings.' });
            }
        } catch (err) {
            console.error(err);
            setMessage({ type: 'error', text: 'Network error.' });
        } finally {
            setSaving(false);
        }
    };

    const handleTestIMAP = async () => {
        setTestLoading(true);
        setMessage(null);
        try {
            const res = await fetchWithAuth('/settings/test-imap', {
                method: 'POST',
                body: JSON.stringify(settings)
            });
            const data = await res.json();
            if (res.ok) {
                setMessage({ type: 'success', text: data.message });
            } else {
                setMessage({ type: 'error', text: data.detail || 'IMAP Connection Failed' });
            }
        } catch (err) {
            setMessage({ type: 'error', text: 'Network Error during Test' });
        } finally {
            setTestLoading(false);
        }
    };

    const handleTestSMTP = async () => {
        setTestLoading(true);
        setMessage(null);
        try {
            const res = await fetchWithAuth('/settings/test-smtp', {
                method: 'POST',
                body: JSON.stringify({ settings, recipient: testRecipient })
            });
            const data = await res.json();
            if (res.ok) {
                setMessage({ type: 'success', text: data.message });
                setOpenEmailDialog(false);
            } else {
                setMessage({ type: 'error', text: data.detail || 'SMTP Send Failed' });
            }
        } catch (err) {
            setMessage({ type: 'error', text: 'Network Error during Test' });
        } finally {
            setTestLoading(false);
        }
    };

    return (
        <Layout>
            <Box sx={{ p: 3, maxWidth: 1000, mx: 'auto' }}>
                <Typography variant="h4" sx={{ fontWeight: 700, mb: 1, display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Server /> System Settings
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
                    Configure external connections and system behavior.
                </Typography>

                {message && (
                    <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage(null)}>
                        {message.text}
                    </Alert>
                )}

                <Paper sx={{ width: '100%', mb: 3 }}>
                    <Tabs value={tab} onChange={(_e: React.SyntheticEvent, v: number) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}>
                        <Tab label="Email Connector" icon={<Mail size={16} />} iconPosition="start" />
                        <Tab label="Security & Whitelist" icon={<ShieldCheck size={16} />} iconPosition="start" />
                        <Tab label="Télésurveilleurs" icon={<ShieldCheck size={16} />} iconPosition="start" />
                    </Tabs>

                    {loading ? (
                        <Box sx={{ p: 5, display: 'flex', justifyContent: 'center' }}><CircularProgress /></Box>
                    ) : (
                        <Box component="form" noValidate sx={{ p: 4 }}>
                            {/* TAB 0: EMAIL CONNECTOR */}
                            {tab === 0 && (
                                <Grid container spacing={3}>
                                    <Grid item xs={12}>
                                        <Typography variant="h6" sx={{ mb: 1 }}>IMAP Configuration (OVH)</Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            Used to fetch extraction files from emails.
                                        </Typography>
                                    </Grid>
                                    <Grid item xs={8}>
                                        <TextField
                                            label="IMAP Host" fullWidth
                                            value={settings['imap_host'] || ''}
                                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleChange('imap_host', e.target.value)}
                                            placeholder="ssl0.ovh.net"
                                        />
                                    </Grid>
                                    <Grid item xs={4}>
                                        <TextField
                                            label="Port" fullWidth
                                            value={settings['imap_port'] || ''}
                                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleChange('imap_port', e.target.value)}
                                            placeholder="993"
                                        />
                                    </Grid>
                                    <Grid item xs={6}>
                                        <TextField
                                            label="Username / Email" fullWidth
                                            value={settings['imap_user'] || ''}
                                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleChange('imap_user', e.target.value)}
                                            placeholder="bip@supervision.com"
                                        />
                                    </Grid>
                                    <Grid item xs={6}>
                                        <TextField
                                            label="Password" type="password" fullWidth
                                            value={settings['imap_password'] || ''}
                                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleChange('imap_password', e.target.value)}
                                        />
                                    </Grid>

                                    <Grid item xs={12}><Divider sx={{ my: 1 }} /></Grid>

                                    <Grid item xs={12}>
                                        <Typography variant="h6">Processing Behavior</Typography>
                                    </Grid>
                                    <Grid item xs={6}>
                                        <TextField
                                            select label="Cleanup Mode" fullWidth
                                            value={settings['cleanup_mode'] || 'MOVE'}
                                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleChange('cleanup_mode', e.target.value)}
                                        >
                                            <MenuItem value="MOVE">Move to 'Processed' Folder</MenuItem>
                                            <MenuItem value="DELETE">Delete Email</MenuItem>
                                            <MenuItem value="NONE">Keep (Mark Read)</MenuItem>
                                        </TextField>
                                    </Grid>
                                    <Grid item xs={6}>
                                        <TextField
                                            label="Target Folder (if Move)" fullWidth
                                            value={settings['imap_folder'] || 'Processed'}
                                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleChange('imap_folder', e.target.value)}
                                        />
                                    </Grid>
                                    <Grid item xs={12}>
                                        <TextField
                                            label="Scan Interval (Seconds)" type="number" fullWidth
                                            value={settings['email_scan_interval'] || '60'}
                                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleChange('email_scan_interval', e.target.value)}
                                            helperText="How often to check for new emails."
                                        />
                                    </Grid>
                                </Grid>
                            )}

                            {/* TAB 1: SECURITY */}
                            {tab === 1 && (
                                <Grid container spacing={3}>
                                    <Grid item xs={12}>
                                        <Typography variant="h6">Sender Whitelist</Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            Only emails from these addresses will be processed. JSON Array format.
                                        </Typography>
                                    </Grid>
                                    <Grid item xs={12}>
                                        <Grid item xs={12}>
                                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                                                {(function () {
                                                    try {
                                                        return JSON.parse(settings['whitelist_senders'] || '[]');
                                                    } catch { return []; }
                                                })().map((email: string) => (
                                                    <Chip
                                                        key={email}
                                                        label={email}
                                                        onDelete={() => {
                                                            try {
                                                                const current = JSON.parse(settings['whitelist_senders'] || '[]');
                                                                const updated = current.filter((e: string) => e !== email);
                                                                handleChange('whitelist_senders', JSON.stringify(updated));
                                                            } catch (e) {
                                                                console.error("Error updating whitelist", e);
                                                            }
                                                        }}
                                                    />
                                                ))}
                                            </Box>
                                            <TextField
                                                label="Add Allowed Email" fullWidth
                                                value={whitelistInput}
                                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setWhitelistInput(e.target.value)}
                                                onKeyDown={(e: React.KeyboardEvent) => {
                                                    if (e.key === 'Enter') {
                                                        e.preventDefault();
                                                        if (!whitelistInput) return;
                                                        try {
                                                            const current = JSON.parse(settings['whitelist_senders'] || '[]');
                                                            if (!current.includes(whitelistInput)) {
                                                                const updated = [...current, whitelistInput];
                                                                handleChange('whitelist_senders', JSON.stringify(updated));
                                                            }
                                                            setWhitelistInput('');
                                                        } catch (e) {
                                                            // Reset if corrupted
                                                            handleChange('whitelist_senders', JSON.stringify([whitelistInput]));
                                                            setWhitelistInput('');
                                                        }
                                                    }
                                                }}
                                                placeholder="noreply@example.com (Press Enter to add)"
                                                helperText="Only emails from these senders will be processed."
                                                InputProps={{
                                                    endAdornment: (
                                                        <IconButton
                                                            onClick={() => {
                                                                if (!whitelistInput) return;
                                                                try {
                                                                    const current = JSON.parse(settings['whitelist_senders'] || '[]');
                                                                    if (!current.includes(whitelistInput)) {
                                                                        const updated = [...current, whitelistInput];
                                                                        handleChange('whitelist_senders', JSON.stringify(updated));
                                                                    }
                                                                    setWhitelistInput('');
                                                                } catch (e) {
                                                                    handleChange('whitelist_senders', JSON.stringify([whitelistInput]));
                                                                    setWhitelistInput('');
                                                                }
                                                            }}
                                                            edge="end"
                                                        >
                                                            <Plus size={20} />
                                                        </IconButton>
                                                    )
                                                }}
                                            />
                                        </Grid>
                                        <Grid item xs={12}>
                                            <Typography variant="h6" sx={{ mt: 2 }}>Attachment Filter</Typography>
                                        </Grid>
                                        <Grid item xs={12}>
                                            <TextField
                                                label="Allowed Extensions (JSON)" fullWidth
                                                value={settings['attachment_types'] || '["pdf", "xlsx", "xls"]'}
                                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleChange('attachment_types', e.target.value)}
                                            />
                                        </Grid>
                                    </Grid>
                                </Grid>
                            )}

                            {/* TAB 2: MONITORING PROVIDERS */}
                            {tab === 2 && (
                                <Box>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                                        <Box>
                                            <Typography variant="h6">Télésurveilleurs</Typography>
                                            <Typography variant="caption" color="text.secondary">
                                                Gérez les prestataires de télésurveillance et leurs règles de détection.
                                            </Typography>
                                        </Box>
                                        <Button
                                            variant="contained"
                                            startIcon={<Plus size={18} />}
                                            onClick={() => {
                                                setSelectedProvider(null);
                                                setProviderForm({ code: '', label: '', is_active: true });
                                                setOpenProviderDialog(true);
                                            }}
                                        >
                                            Ajouter
                                        </Button>
                                    </Box>

                                    {loadingProviders ? (
                                        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>
                                    ) : (
                                        <Grid container spacing={3}>
                                            {providers.map((p: MonitoringProvider) => (
                                                <Grid item xs={12} key={p.id}>
                                                    <Paper variant="outlined" sx={{ p: 2, bgcolor: 'rgba(255,255,255,0.02)' }}>
                                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                                                            <Box>
                                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                                    <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>{p.label}</Typography>
                                                                    <Chip label={p.code} size="small" variant="outlined" />
                                                                    {!p.is_active && <Chip label="Inactif" size="small" color="error" />}
                                                                </Box>
                                                            </Box>
                                                            <Box sx={{ display: 'flex', gap: 1 }}>
                                                                <Button
                                                                    size="small"
                                                                    onClick={() => {
                                                                        setSelectedProvider(p);
                                                                        setProviderForm({ code: p.code, label: p.label, ui_color: p.ui_color || '', is_active: p.is_active });
                                                                        setOpenProviderDialog(true);
                                                                    }}
                                                                >
                                                                    Modifier
                                                                </Button>
                                                                <IconButton
                                                                    size="small" color="error"
                                                                    onClick={() => handleDeleteProvider(p.id)}
                                                                >
                                                                    <Trash2 size={16} />
                                                                </IconButton>
                                                            </Box>
                                                        </Box>

                                                        <Divider sx={{ mb: 2, borderStyle: 'dashed' }} />

                                                        <Box>
                                                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                                                                <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase' }}>
                                                                    Règles SMTP
                                                                </Typography>
                                                                <Button
                                                                    size="small" startIcon={<Plus size={14} />}
                                                                    onClick={() => {
                                                                        setActiveProviderId(p.id);
                                                                        setSelectedRule(null);
                                                                        setRuleForm({ match_type: 'DOMAIN', match_value: '', priority: 0, is_active: true });
                                                                        setOpenRuleDialog(true);
                                                                    }}
                                                                >
                                                                    Ajouter une règle
                                                                </Button>
                                                            </Box>

                                                            {!rules[p.id] ? (
                                                                <Button variant="text" size="small" onClick={() => fetchRules(p.id)}>Charger les règles</Button>
                                                            ) : (
                                                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                                                    {rules[p.id].length === 0 && (
                                                                        <Typography variant="caption" color="text.disabled">Aucune règle configurée.</Typography>
                                                                    )}
                                                                    {rules[p.id].map((r: SmtpRule) => (
                                                                        <Box
                                                                            key={r.id}
                                                                            sx={{
                                                                                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                                                                p: 1, borderRadius: 1, bgcolor: 'rgba(255,255,255,0.03)',
                                                                                border: '1px solid transparent',
                                                                                '&:hover': { borderColor: 'divider' }
                                                                            }}
                                                                        >
                                                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                                                                <Chip label={r.match_type} size="small" sx={{ fontSize: 9, height: 18 }} color="primary" variant="outlined" />
                                                                                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{r.match_value}</Typography>
                                                                                <Typography variant="caption" color="text.secondary">Prio: {r.priority}</Typography>
                                                                                {!r.is_active && <Chip label="Désactivée" size="small" sx={{ height: 16, fontSize: 8 }} />}
                                                                            </Box>
                                                                            <Box sx={{ display: 'flex' }}>
                                                                                <IconButton
                                                                                    size="small"
                                                                                    onClick={() => {
                                                                                        setActiveProviderId(p.id);
                                                                                        setSelectedRule(r);
                                                                                        setRuleForm({
                                                                                            match_type: r.match_type,
                                                                                            match_value: r.match_value,
                                                                                            priority: r.priority,
                                                                                            is_active: r.is_active
                                                                                        });
                                                                                        setOpenRuleDialog(true);
                                                                                    }}
                                                                                >
                                                                                    <ShieldCheck size={14} />
                                                                                </IconButton>
                                                                                <IconButton
                                                                                    size="small" color="error"
                                                                                    onClick={() => handleDeleteRule(p.id, r.id)}
                                                                                >
                                                                                    <Trash2 size={14} />
                                                                                </IconButton>
                                                                            </Box>
                                                                        </Box>
                                                                    ))}
                                                                </Box>
                                                            )}
                                                        </Box>
                                                    </Paper>
                                                </Grid>
                                            ))}
                                        </Grid>
                                    )}
                                </Box>
                            )}

                            {tab !== 2 && (
                                <Box sx={{ mt: 4, display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
                                    <Button
                                        variant="outlined"
                                        color="secondary"
                                        onClick={handleTestIMAP}
                                        startIcon={testLoading ? <CircularProgress size={16} /> : <Server size={18} />}
                                        disabled={testLoading}
                                    >
                                        Test IMAP Connection
                                    </Button>
                                    <Button
                                        variant="outlined"
                                        color="info"
                                        onClick={() => setOpenEmailDialog(true)}
                                        startIcon={<Mail size={18} />}
                                    >
                                        Test Send Email
                                    </Button>
                                    <Button
                                        variant="contained"
                                        startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <Save size={18} />}
                                        onClick={handleSave}
                                        disabled={saving || testLoading}
                                    >
                                        Save Configuration
                                    </Button>
                                </Box>
                            )}
                        </Box>
                    )}
                </Paper>

                {/* TEST EMAIL DIALOG */}
                <Dialog open={openEmailDialog} onClose={() => setOpenEmailDialog(false)}>
                    <DialogTitle>Send Test Email</DialogTitle>
                    <DialogContent sx={{ minWidth: 400, pt: 1 }}>
                        <TextField
                            label="Recipient Email"
                            fullWidth
                            autoFocus
                            value={testRecipient}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTestRecipient(e.target.value)}
                            placeholder="you@example.com"
                        />
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setOpenEmailDialog(false)}>Cancel</Button>
                        <Button
                            variant="contained"
                            onClick={handleTestSMTP}
                            disabled={testLoading || !testRecipient}
                            startIcon={testLoading ? <CircularProgress size={16} /> : null}
                        >
                            Send
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* PROVIDER DIALOG */}
                <Dialog open={openProviderDialog} onClose={() => setOpenProviderDialog(false)}>
                    <DialogTitle>{selectedProvider ? 'Modifier' : 'Nouveau'} Télésurveilleur</DialogTitle>
                    <DialogContent sx={{ minWidth: 400, pt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <TextField
                            label="Code (ex: SPGO)"
                            fullWidth
                            autoFocus
                            value={providerForm.code}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setProviderForm({ ...providerForm, code: e.target.value.toUpperCase() })}
                            disabled={!!selectedProvider}
                            sx={{ mt: 1 }}
                        />
                        <TextField
                            label="Label UI (ex: SPGO + Online)"
                            fullWidth
                            value={providerForm.label}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setProviderForm({ ...providerForm, label: e.target.value })}
                        />
                        <TextField
                            label="Couleur (Code Hex ou Nom CSS)"
                            fullWidth
                            value={providerForm.ui_color}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setProviderForm({ ...providerForm, ui_color: e.target.value })}
                            placeholder="#1976d2 ou primary"
                            helperText="Ex: #2e7d32 (Vert), #d32f2f (Rouge), #1976d2 (Bleu)"
                            sx={{ mt: 1 }}
                            InputProps={{
                                endAdornment: (
                                    <input
                                        type="color"
                                        value={providerForm.ui_color?.startsWith('#') ? providerForm.ui_color : '#1976d2'}
                                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setProviderForm({ ...providerForm, ui_color: e.target.value })}
                                        style={{ width: 30, height: 30, padding: 0, border: 'none', cursor: 'pointer', background: 'none' }}
                                    />
                                )
                            }}
                        />

                        <Box sx={{ mt: 0, mb: 1 }}>
                            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                                Palette suggérée :
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                {[
                                    { name: 'Success', color: '#2e7d32' },
                                    { name: 'Error', color: '#d32f2f' },
                                    { name: 'Info', color: '#0288d1' },
                                    { name: 'Warning', color: '#ed6c02' },
                                    { name: 'Purple', color: '#9c27b0' },
                                    { name: 'Cyan', color: '#00bcd4' },
                                    { name: 'Grey', color: '#607d8b' },
                                    { name: 'Black', color: '#212121' }
                                ].map((c) => (
                                    <Box
                                        key={c.color}
                                        onClick={() => setProviderForm({ ...providerForm, ui_color: c.color })}
                                        sx={{
                                            width: 20,
                                            height: 20,
                                            borderRadius: '50%',
                                            bgcolor: c.color,
                                            cursor: 'pointer',
                                            border: providerForm.ui_color === c.color ? '2px solid #fff' : 'none',
                                            boxShadow: providerForm.ui_color === c.color ? 3 : 1,
                                            transition: 'transform 0.1s',
                                            '&:hover': { transform: 'scale(1.2)' }
                                        }}
                                        title={c.name}
                                    />
                                ))}
                            </Box>
                        </Box>

                        <TextField
                            select label="Statut" fullWidth
                            value={providerForm.is_active ? 'YES' : 'NO'}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setProviderForm({ ...providerForm, is_active: e.target.value === 'YES' })}
                        >
                            <MenuItem value="YES">Actif</MenuItem>
                            <MenuItem value="NO">Inactif</MenuItem>
                        </TextField>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setOpenProviderDialog(false)}>Annuler</Button>
                        <Button
                            variant="contained" color="primary"
                            onClick={handleSaveProvider}
                            disabled={saving || !providerForm.code || !providerForm.label}
                        >
                            Enregistrer
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* RULE DIALOG */}
                <Dialog open={openRuleDialog} onClose={() => setOpenRuleDialog(false)}>
                    <DialogTitle>{selectedRule ? 'Modifier' : 'Ajouter'} une Règle SMTP</DialogTitle>
                    <DialogContent sx={{ minWidth: 400, pt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <TextField
                            select label="Type" fullWidth
                            autoFocus
                            value={ruleForm.match_type}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRuleForm({ ...ruleForm, match_type: e.target.value })}
                            sx={{ mt: 1 }}
                        >
                            <MenuItem value="EXACT">Email Exact</MenuItem>
                            <MenuItem value="DOMAIN">Nom de Domaine</MenuItem>
                            <MenuItem value="REGEX">Expression Régulière</MenuItem>
                        </TextField>
                        <TextField
                            label="Valeur (ex: @spgo.fr)"
                            fullWidth
                            value={ruleForm.match_value}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRuleForm({ ...ruleForm, match_value: e.target.value })}
                        />
                        <TextField
                            label="Priorité (plus haut = testé en premier)"
                            type="number"
                            fullWidth
                            value={ruleForm.priority}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRuleForm({ ...ruleForm, priority: parseInt(e.target.value) || 0 })}
                        />
                        <TextField
                            select label="Statut" fullWidth
                            value={ruleForm.is_active ? 'YES' : 'NO'}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRuleForm({ ...ruleForm, is_active: e.target.value === 'YES' })}
                        >
                            <MenuItem value="YES">Active</MenuItem>
                            <MenuItem value="NO">Désactivée</MenuItem>
                        </TextField>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setOpenRuleDialog(false)}>Annuler</Button>
                        <Button
                            variant="contained" color="primary"
                            onClick={handleSaveRule}
                            disabled={saving || !ruleForm.match_value}
                        >
                            Enregistrer
                        </Button>
                    </DialogActions>
                </Dialog>
            </Box>
        </Layout>
    );
}
