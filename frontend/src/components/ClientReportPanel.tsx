'use client';

import React, { useState, useEffect } from 'react';
import {
    Box,
    Drawer,
    Typography,
    IconButton,
    Grid,
    Paper,
    Divider,
    Tabs,
    Tab,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Chip,
    CircularProgress,
    Button,
    Badge,
    Alert as MuiAlert
} from '@mui/material';
import {
    X,
    TrendingUp,
    ShieldAlert,
    Clock,
    User,
    ArrowUpRight,
    Search,
    Download
} from 'lucide-react';
import { API_ORIGIN } from '@/lib/api';
import { format } from 'date-fns';

interface ClientReportPanelProps {
    siteCode: string | null;
    open: boolean;
    onClose: () => void;
}

export default function ClientReportPanel({ siteCode, open, onClose }: ClientReportPanelProps) {
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState<any>(null);
    const [tab, setTab] = useState(0);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (open && siteCode) {
            fetchReport();
        }
    }, [open, siteCode]);

    const fetchReport = async () => {
        setLoading(true);
        setError(null);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_ORIGIN}/api/v1/client/${siteCode}/report?days=30`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error('Failed to fetch client report');
            const json = await res.json();
            setData(json);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const getStatusColor = (status: string) => {
        if (status === 'ACTIVE') return 'error';
        if (status === 'ARCHIVED') return 'success';
        return 'default';
    };

    return (
        <Drawer
            anchor="right"
            open={open}
            onClose={onClose}
            sx={{ '& .MuiDrawer-paper': { width: { xs: '100%', sm: 600, md: 800 }, bgcolor: 'background.default' } }}
        >
            {/* HEADER */}
            <Box sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'background.paper' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Box sx={{ p: 1, borderRadius: 2, bgcolor: 'primary.main', color: '#fff' }}>
                        <User size={24} />
                    </Box>
                    <Box>
                        <Typography variant="h6" fontWeight={700}>Client Report</Typography>
                        <Typography variant="caption" color="text.secondary">Site Code: {siteCode}</Typography>
                    </Box>
                </Box>
                <IconButton onClick={onClose}><X size={20} /></IconButton>
            </Box>

            {!siteCode ? (
                <Box sx={{ p: 4, textAlign: 'center' }}>
                    <Typography color="text.secondary">No site selected.</Typography>
                </Box>
            ) : loading ? (
                <Box sx={{ p: 8, textAlign: 'center' }}>
                    <CircularProgress size={40} thickness={4} />
                    <Typography sx={{ mt: 2 }} color="text.secondary">Loading consolidated data...</Typography>
                </Box>
            ) : error ? (
                <Box sx={{ p: 4 }}>
                    <MuiAlert severity="error">{error}</MuiAlert>
                </Box>
            ) : data && (
                <Box sx={{ overflowY: 'auto', p: 3 }}>

                    {/* INFO HEADER */}
                    <Paper sx={{ p: 3, mb: 3, bgcolor: 'primary.dark', color: '#fff' }}>
                        <Grid container spacing={2}>
                            <Grid item xs={12} sm={8}>
                                <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>{data.provider}</Typography>
                                <Typography variant="body2" sx={{ opacity: 0.8 }}>Consolidated reporting for site {siteCode}</Typography>
                            </Grid>
                            <Grid item xs={12} sm={4} sx={{ textAlign: { sm: 'right' } }}>
                                <Button startIcon={<Download size={16} />} variant="contained" color="inherit" size="small" sx={{ color: 'primary.main', fontWeight: 600 }}>
                                    Export PDF
                                </Button>
                            </Grid>
                        </Grid>
                    </Paper>

                    {/* KPI CARDS */}
                    <Grid container spacing={2} sx={{ mb: 3 }}>
                        {[
                            { label: 'Total Events', val: data.summary.total_events, icon: <TrendingUp size={18} />, color: 'primary' },
                            { label: 'Total Alerts', val: data.summary.total_alerts, icon: <ShieldAlert size={18} />, color: 'warning' },
                            { label: 'Active', val: data.summary.active_alerts, icon: <ArrowUpRight size={18} />, color: 'error' },
                            { label: 'Archived', val: data.summary.archived_alerts, icon: <Clock size={18} />, color: 'success' },
                        ].map((kpi, i) => (
                            <Grid item xs={6} md={3} key={i}>
                                <Paper sx={{ p: 2, textAlign: 'center' }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'center', mb: 1, color: `${kpi.color}.main` }}>{kpi.icon}</Box>
                                    <Typography variant="h5" fontWeight={700}>{kpi.val}</Typography>
                                    <Typography variant="caption" color="text.secondary">{kpi.label}</Typography>
                                </Paper>
                            </Grid>
                        ))}
                    </Grid>

                    {/* TABS */}
                    <Tabs value={tab} onChange={(e: any, v: number) => setTab(v)} sx={{ mb: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                        <Tab label="Alert Lifecycle" />
                        <Tab label="Event Timeline" />
                    </Tabs>

                    {/* ALERTS TAB */}
                    {tab === 0 && (
                        <TableContainer component={Paper}>
                            <Table size="small">
                                <TableHead sx={{ bgcolor: 'background.default' }}>
                                    <TableRow>
                                        <TableCell sx={{ fontWeight: 600 }}>Rule</TableCell>
                                        <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                                        <TableCell sx={{ fontWeight: 600 }}>First Seen</TableCell>
                                        <TableCell sx={{ fontWeight: 600 }}>Closed At</TableCell>
                                        <TableCell align="right" sx={{ fontWeight: 600 }}>Hits</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {data.alerts.length === 0 ? (
                                        <TableRow><TableCell colSpan={5} sx={{ py: 4, textAlign: 'center' }}>No alerts triggered for this client.</TableCell></TableRow>
                                    ) : data.alerts.map((alert: any, i: number) => (
                                        <TableRow key={i}>
                                            <TableCell sx={{ fontWeight: 500 }}>{alert.rule_name}</TableCell>
                                            <TableCell>
                                                <Chip label={alert.status} size="small" variant="outlined" color={getStatusColor(alert.status) as any} />
                                            </TableCell>
                                            <TableCell sx={{ fontSize: '0.75rem' }}>{format(new Date(alert.first_seen), 'dd/MM HH:mm')}</TableCell>
                                            <TableCell sx={{ fontSize: '0.75rem' }}>
                                                {alert.closed_at ? format(new Date(alert.closed_at), 'dd/MM HH:mm') : '-'}
                                            </TableCell>
                                            <TableCell align="right">
                                                <Badge badgeContent={alert.count_hits} color="primary" max={99} />
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    )}

                    {/* TIMELINE TAB */}
                    {tab === 1 && (
                        <Box>
                            {data.timeline.map((evt: any, i: number) => (
                                <Box key={evt.id} sx={{
                                    display: 'flex', gap: 2, mb: 2,
                                    pb: 2, borderBottom: '1px solid', borderColor: 'divider',
                                    position: 'relative'
                                }}>
                                    <Box sx={{ minWidth: 60, pt: 0.5 }}>
                                        <Typography variant="caption" color="text.secondary" fontWeight={600}>
                                            {format(new Date(evt.timestamp), 'HH:mm:ss')}
                                        </Typography>
                                        <Typography variant="caption" display="block" color="text.secondary">
                                            {format(new Date(evt.timestamp), 'dd/MM')}
                                        </Typography>
                                    </Box>
                                    <Box sx={{ flexGrow: 1 }}>
                                        <Box sx={{ display: 'flex', gap: 1, mb: 0.5, alignItems: 'center' }}>
                                            <Chip
                                                label={evt.normalized_type || 'Unknown'}
                                                size="small"
                                                color={evt.severity === 'CRITICAL' ? 'error' : 'default'}
                                                variant="outlined"
                                                sx={{ height: 20, fontSize: '0.65rem' }}
                                            />
                                            {evt.triggered_rules?.length > 0 && (
                                                <Chip icon={<ShieldAlert size={12} />} label="Alert" size="small" color="error" sx={{ height: 20, fontSize: '0.65rem' }} />
                                            )}
                                        </Box>
                                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                                            {evt.raw_message}
                                        </Typography>
                                    </Box>
                                </Box>
                            ))}
                        </Box>
                    )}

                </Box>
            )}
        </Drawer>
    );
}
