'use client';

import React, { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Chip,
    IconButton,
    Tooltip,
    CircularProgress,
    Alert,
    TextField
} from '@mui/material';
import { RefreshCw, Activity, AlertTriangle, CheckCircle, Clock, Filter, ExternalLink, Info } from 'lucide-react';
import { fetchWithAuth } from '../lib/api';
import { useRouter } from 'next/navigation';
import { format } from 'date-fns';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    List,
    ListItem,
    ListItemText,
    Divider
} from '@mui/material';
import EventDetailDrawer from './EventDetailDrawer';

interface RuleTriggerRow {
    rule_id: number;
    rule_name: string;
    provider_id: number | null;
    provider_label: string;
    total_triggers: number;
    distinct_sites: number;
    last_trigger_at: string;
    health_status: 'HIGH_ACTIVITY' | 'LOW_ACTIVITY' | 'NORMAL';
}

export default function RuleTriggerPanel() {
    const [data, setData] = useState<RuleTriggerRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
    const [providerFilter, setProviderFilter] = useState('');
    // Default to today; user can change to see historical data
    const [selectedDate, setSelectedDate] = useState<string>(() => new Date().toISOString().split('T')[0]);
    const router = useRouter();

    // Drilldown state
    const [drilldownOpen, setDrilldownOpen] = useState(false);
    const [selectedRule, setSelectedRule] = useState<RuleTriggerRow | null>(null);
    const [drilldownData, setDrilldownData] = useState<any[]>([]);
    const [drilldownLoading, setDrilldownLoading] = useState(false);
    const [drilldownTotal, setDrilldownTotal] = useState(0);
    const [drilldownPage, setDrilldownPage] = useState(1);

    // Event Detail Drawer
    const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
    const [drawerOpen, setDrawerOpen] = useState(false);

    const fetchData = async (dateStr?: string) => {
        setLoading(true);
        try {
            const d = dateStr || selectedDate;
            const res = await fetchWithAuth(`/rules/trigger-summary?date=${d}`);
            if (res.ok) {
                const json = await res.json();
                setData(json.summary);
                setLastUpdated(new Date());
                setError(null);
            } else {
                setError('Failed to fetch rule trigger summary');
            }
        } finally {
            setLoading(false);
        }
    };

    const fetchDrilldown = async (ruleId: number, page: number = 1) => {
        setDrilldownLoading(true);
        try {
            const res = await fetchWithAuth(`/rules/${ruleId}/events?page=${page}&limit=20`);
            if (res.ok) {
                const json = await res.json();
                setDrilldownData(json.items || []);
                setDrilldownTotal(json.total || 0);
            }
        } catch (err) {
            console.error("Failed to fetch drilldown", err);
        } finally {
            setDrilldownLoading(false);
        }
    };

    useEffect(() => {
        fetchData(selectedDate);
        const interval = setInterval(() => fetchData(selectedDate), 60000);
        return () => clearInterval(interval);
    }, [selectedDate]);

    const getStatusChip = (status: string) => {
        switch (status) {
            case 'NORMAL':
                return <Chip label="NORMAL" color="success" size="small" variant="outlined" />;
            case 'LOW_ACTIVITY':
                return <Chip icon={<AlertTriangle size={12} />} label="LOW" color="warning" size="small" variant="filled" />;
            case 'HIGH_ACTIVITY':
                return <Chip icon={<Activity size={12} />} label="HIGH" color="error" size="small" variant="filled" />;
            default:
                return <Chip label={status} size="small" />;
        }
    };

    const handleRowClick = (row: RuleTriggerRow) => {
        setSelectedRule(row);
        setDrilldownPage(1);
        setDrilldownOpen(true);
        fetchDrilldown(row.rule_id, 1);
    };

    const handleEventClick = (eventId: number) => {
        setSelectedEventId(eventId);
        setDrawerOpen(true);
    };

    const filteredData = data.filter((row: RuleTriggerRow) =>
        row.provider_label.toLowerCase().includes(providerFilter.toLowerCase()) ||
        row.rule_name.toLowerCase().includes(providerFilter.toLowerCase())
    );

    return (
        <Paper sx={{ p: 3, height: '100%', minHeight: 400, display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Box sx={{ p: 1, borderRadius: 2, bgcolor: 'secondary.main', color: 'white', display: 'flex' }}>
                        <Activity size={20} />
                    </Box>
                    <Box>
                        <Typography variant="h6" fontWeight={700}>Rule Monitoring</Typography>
                        <Typography variant="caption" color="text.secondary">Triggers par journée sélectionnée</Typography>
                    </Box>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <TextField
                        type="date"
                        size="small"
                        value={selectedDate}
                        onChange={(e) => setSelectedDate(e.target.value)}
                        sx={{ width: 140, '& .MuiInputBase-input': { fontSize: '0.75rem', py: 0.5 } }}
                    />
                    <TextField
                        size="small"
                        placeholder="Search..."
                        value={providerFilter}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setProviderFilter(e.target.value)}
                        InputProps={{
                            startAdornment: <Filter size={14} style={{ marginRight: 8, opacity: 0.5 }} />
                        }}
                        sx={{ mr: 1, '& .MuiInputBase-input': { fontSize: '0.8rem' } }}
                    />
                    <IconButton size="small" onClick={() => fetchData(selectedDate)} disabled={loading}>
                        <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                    </IconButton>
                </Box>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            <TableContainer sx={{ flexGrow: 1, overflow: 'auto' }}>
                <Table size="small" stickyHeader>
                    <TableHead>
                        <TableRow>
                            <TableCell sx={{ fontWeight: 700 }}>Rule</TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>Provider</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 700 }}>Triggers</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 700 }}>Sites</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 700 }}>Last Seen</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 700 }}>Activity</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {loading && data.length === 0 ? (
                            <TableRow><TableCell colSpan={6} align="center" sx={{ py: 8 }}><CircularProgress size={24} /></TableCell></TableRow>
                        ) : filteredData.length === 0 ? (
                            <TableRow><TableCell colSpan={6} align="center" sx={{ py: 8 }}>
                                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, opacity: 0.6 }}>
                                    <Clock size={28} />
                                    <Typography variant="body2" color="text.secondary">Aucun déclenchement le {selectedDate}</Typography>
                                    <Typography variant="caption" color="text.secondary">Essayez une date différente ou vérifiez que les règles sont actives.</Typography>
                                </Box>
                            </TableCell></TableRow>
                        ) : (
                            filteredData.map((row: RuleTriggerRow) => (
                                <TableRow
                                    key={`${row.rule_id}-${row.provider_id}`}
                                    hover
                                    sx={{ cursor: 'pointer' }}
                                    onClick={() => handleRowClick(row)}
                                >
                                    <TableCell>
                                        <Typography variant="body2" fontWeight={600} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            {row.rule_name} <ExternalLink size={12} style={{ opacity: 0.3 }} />
                                        </Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant="caption">{row.provider_label}</Typography>
                                    </TableCell>
                                    <TableCell align="center">
                                        <Typography variant="body2" fontWeight={700}>{row.total_triggers}</Typography>
                                    </TableCell>
                                    <TableCell align="center">
                                        <Typography variant="body2">{row.distinct_sites}</Typography>
                                    </TableCell>
                                    <TableCell align="center">
                                        <Tooltip title={new Date(row.last_trigger_at).toLocaleString()}>
                                            <Typography variant="caption">{new Date(row.last_trigger_at).toLocaleTimeString()}</Typography>
                                        </Tooltip>
                                    </TableCell>
                                    <TableCell align="center">
                                        {getStatusChip(row.health_status)}
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>

            {/* Drilldown Dialog */}
            <Dialog
                open={drilldownOpen}
                onClose={() => setDrilldownOpen(false)}
                maxWidth="md"
                fullWidth
                PaperProps={{ sx: { borderRadius: 3 } }}
            >
                <DialogTitle>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Box>
                            <Typography variant="h6" fontWeight={700}>{selectedRule?.rule_name}</Typography>
                            <Typography variant="caption" color="text.secondary">
                                {selectedRule?.provider_label} | {selectedRule?.total_triggers} triggers (Page {drilldownPage})
                            </Typography>
                        </Box>
                        <Chip label={selectedRule?.health_status} size="small" color={selectedRule?.health_status === 'HIGH_ACTIVITY' ? 'error' : 'success'} />
                    </Box>
                </DialogTitle>
                <DialogContent dividers sx={{ p: 0 }}>
                    {drilldownLoading ? (
                        <Box sx={{ p: 4, textAlign: 'center' }}><CircularProgress size={24} /></Box>
                    ) : (
                        <TableContainer sx={{ maxHeight: 400 }}>
                            <Table size="small" stickyHeader>
                                <TableHead>
                                    <TableRow>
                                        <TableCell sx={{ fontWeight: 600 }}>Télémétrie / Déclenchement</TableCell>
                                        <TableCell sx={{ fontWeight: 600 }}>Site</TableCell>
                                        <TableCell sx={{ fontWeight: 600 }}>Message</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {drilldownData.map((item) => (
                                        <TableRow key={item.id} hover onClick={() => handleEventClick(item.id)} sx={{ cursor: 'pointer' }}>
                                            <TableCell sx={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                                                {format(new Date(item.matched_at), 'dd/MM HH:mm:ss')}
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="body2" fontWeight={600}>{item.site_code}</Typography>
                                                <Typography variant="caption" color="text.secondary">{item.client_name}</Typography>
                                            </TableCell>
                                            <TableCell sx={{ fontSize: '0.75rem', fontFamily: 'monospace', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                {item.raw_message}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDrilldownOpen(false)}>Fermer</Button>
                    <Button
                        variant="outlined"
                        size="small"
                        onClick={() => {
                            const searchParams = new URLSearchParams();
                            searchParams.set('rule', selectedRule?.rule_name || '');
                            router.push(`/admin/data-validation?${searchParams.toString()}`);
                        }}
                    >
                        Explorer dans Validation
                    </Button>
                </DialogActions>
            </Dialog>

            <EventDetailDrawer
                eventId={selectedEventId}
                open={drawerOpen}
                onClose={() => setDrawerOpen(false)}
            />
        </Paper>
    );
}
