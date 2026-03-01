'use client';

import React, { useState, useEffect } from 'react';
import Layout from '@/components/Layout';
import {
    Box,
    Grid,
    Paper,
    Typography,
    Chip,
    Tabs,
    Tab,
    CircularProgress,
    Alert,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Pagination,
    Stack
} from '@mui/material';
import {
    Activity,
    ShieldAlert,
    Clock,
    ArrowUpRight,
    CheckCircle,
    AlertTriangle,
    BarChart3
} from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';
import { format } from 'date-fns';
import EventDetailDrawer from '@/components/EventDetailDrawer';

export default function ClientSitePage({ params }: { params: { site_code: string } }) {
    const site_code = params.site_code;
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);
    const [tab, setTab] = useState(0);

    // Pagination params
    const [eventsPage, setEventsPage] = useState(1);
    const [alertsPage, setAlertsPage] = useState(1);
    const limit = 10;

    // Detail Drawer
    const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
    const [drawerOpen, setDrawerOpen] = useState(false);

    useEffect(() => {
        fetchData();
    }, [site_code, eventsPage, alertsPage]);

    const fetchData = async () => {
        setLoading(true);
        try {
            const res = await fetchWithAuth(
                `/client-site/${site_code}/summary?events_page=${eventsPage}&alerts_page=${alertsPage}&limit=${limit}`
            );
            if (!res.ok) {
                if (res.status === 404) throw new Error('Site non trouvé');
                throw new Error('Erreur lors du chargement des données');
            }
            const json = await res.json();
            setData(json);
            setError(null);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleEventClick = (id: number) => {
        setSelectedEventId(id);
        setDrawerOpen(true);
    };

    if (error) {
        return (
            <Layout>
                <Box sx={{ p: 4, textAlign: 'center' }}>
                    <Alert severity="error" sx={{ maxWidth: 400, mx: 'auto' }}>{error}</Alert>
                </Box>
            </Layout>
        );
    }

    if (loading && !data) {
        return (
            <Layout>
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                    <CircularProgress />
                </Box>
            </Layout>
        );
    }

    return (
        <Layout>
            <Box sx={{ p: 3, maxWidth: 1400, mx: 'auto' }}>

                {/* HEADER */}
                <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                    <Box>
                        <Typography variant="h4" fontWeight={700} sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 2 }}>
                            Dashboard Site {site_code}
                            <Chip label={data?.provider_name} size="small" color="primary" sx={{ fontWeight: 600 }} />
                        </Typography>
                        <Typography color="text.secondary">
                            Client: <strong>{data?.client_name}</strong> | Supervision consolidée (7 derniers jours)
                        </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Chip icon={<CheckCircle size={14} />} label="Operational" color="success" size="small" />
                    </Box>
                </Box>

                {/* KPI CARDS */}
                <Grid container spacing={3} sx={{ mb: 4 }}>
                    {[
                        { title: 'Événements (7j)', value: data?.kpis.events_count, icon: <Activity />, color: 'primary' },
                        { title: 'Alertes (7j)', value: data?.kpis.alerts_count, icon: <ShieldAlert />, color: 'error' },
                        { title: 'Dernier Événement', value: data?.kpis.last_event_at ? format(new Date(data.kpis.last_event_at), 'dd/MM HH:mm') : '-', icon: <Clock />, color: 'info' },
                        { title: 'Dernière Alerte', value: data?.kpis.last_alert_at ? format(new Date(data.kpis.last_alert_at), 'dd/MM HH:mm') : '-', icon: <AlertTriangle />, color: 'warning' },
                    ].map((kpi, i) => (
                        <Grid item xs={12} sm={6} md={3} key={i}>
                            <Paper sx={{ p: 3 }}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                                    <Box sx={{ p: 1, borderRadius: 2, bgcolor: `${kpi.color}.main`, color: 'white', display: 'flex' }}>
                                        {kpi.icon}
                                    </Box>
                                </Box>
                                <Typography variant="h5" fontWeight={700}>{kpi.value}</Typography>
                                <Typography variant="caption" color="text.secondary">{kpi.title}</Typography>
                            </Paper>
                        </Grid>
                    ))}
                </Grid>

                <Grid container spacing={3}>
                    {/* TIMELINES */}
                    <Grid item xs={12} md={8}>
                        <Paper sx={{ p: 0, overflow: 'hidden' }}>
                            <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                                <Tabs value={tab} onChange={(e, v) => setTab(v)}>
                                    <Tab label="Events Timeline" icon={<Clock size={16} />} iconPosition="start" />
                                    <Tab label="Triggered Alerts" icon={<ShieldAlert size={16} />} iconPosition="start" />
                                </Tabs>
                            </Box>

                            <Box sx={{ p: 2 }}>
                                {tab === 0 ? (
                                    <Box>
                                        <TableContainer>
                                            <Table size="small">
                                                <TableHead>
                                                    <TableRow>
                                                        <TableCell sx={{ fontWeight: 600 }}>Time</TableCell>
                                                        <TableCell sx={{ fontWeight: 600 }}>Message</TableCell>
                                                        <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                                                        <TableCell align="right" sx={{ fontWeight: 600 }}>Actions</TableCell>
                                                    </TableRow>
                                                </TableHead>
                                                <TableBody>
                                                    {data?.timeline.events.events.map((evt: any) => (
                                                        <TableRow key={evt.id} hover sx={{ cursor: 'pointer' }} onClick={() => handleEventClick(evt.id)}>
                                                            <TableCell sx={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                                                                {format(new Date(evt.timestamp), 'dd/MM HH:mm:ss')}
                                                            </TableCell>
                                                            <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                                {evt.raw_message}
                                                            </TableCell>
                                                            <TableCell>
                                                                <Chip label={evt.normalized_type} size="small" variant="outlined" sx={{ height: 20, fontSize: 10 }} />
                                                            </TableCell>
                                                            <TableCell align="right">
                                                                <ArrowUpRight size={14} style={{ opacity: 0.5 }} />
                                                            </TableCell>
                                                        </TableRow>
                                                    ))}
                                                </TableBody>
                                            </Table>
                                        </TableContainer>
                                        <Stack direction="row" justifyContent="center" sx={{ mt: 2 }}>
                                            <Pagination
                                                count={Math.ceil(data?.timeline.events.total / limit)}
                                                page={eventsPage}
                                                onChange={(e, v) => setEventsPage(v)}
                                                size="small"
                                            />
                                        </Stack>
                                    </Box>
                                ) : (
                                    <Box>
                                        <TableContainer>
                                            <Table size="small">
                                                <TableHead>
                                                    <TableRow>
                                                        <TableCell sx={{ fontWeight: 600 }}>Date</TableCell>
                                                        <TableCell sx={{ fontWeight: 600 }}>Rule</TableCell>
                                                        <TableCell sx={{ fontWeight: 600 }}>Score</TableCell>
                                                        <TableCell align="right" sx={{ fontWeight: 600 }}>Actions</TableCell>
                                                    </TableRow>
                                                </TableHead>
                                                <TableBody>
                                                    {data?.timeline.alerts.items.map((alert: any) => (
                                                        <TableRow key={alert.hit_id} hover sx={{ cursor: 'pointer' }} onClick={() => handleEventClick(alert.event_id)}>
                                                            <TableCell sx={{ fontSize: '0.75rem' }}>
                                                                {format(new Date(alert.created_at), 'dd/MM/yyyy HH:mm')}
                                                            </TableCell>
                                                            <TableCell sx={{ fontWeight: 600 }}>{alert.rule_name}</TableCell>
                                                            <TableCell>
                                                                {alert.score !== null ? <Chip label={alert.score.toFixed(2)} size="small" color="primary" sx={{ height: 20, fontSize: 10 }} /> : '-'}
                                                            </TableCell>
                                                            <TableCell align="right">
                                                                <ArrowUpRight size={14} style={{ opacity: 0.5 }} />
                                                            </TableCell>
                                                        </TableRow>
                                                    ))}
                                                </TableBody>
                                            </Table>
                                        </TableContainer>
                                        <Stack direction="row" justifyContent="center" sx={{ mt: 2 }}>
                                            <Pagination
                                                count={Math.ceil(data?.timeline.alerts.total / limit)}
                                                page={alertsPage}
                                                onChange={(e, v) => setAlertsPage(v)}
                                                size="small"
                                            />
                                        </Stack>
                                    </Box>
                                )}
                            </Box>
                        </Paper>
                    </Grid>

                    {/* TOP RULES */}
                    <Grid item xs={12} md={4}>
                        <Paper sx={{ p: 3, height: '100%' }}>
                            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <BarChart3 size={20} color="#197fe6" /> Top Rules (7j)
                            </Typography>
                            <Box sx={{ mt: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
                                {data?.kpis.top_rules.map((rule: any, i: number) => (
                                    <Box key={i}>
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                            <Typography variant="body2" fontWeight={600}>{rule.rule_name}</Typography>
                                            <Typography variant="body2" fontWeight={700} color="primary">{rule.count}</Typography>
                                        </Box>
                                        <Box sx={{ width: '100%', height: 6, bgcolor: 'background.default', borderRadius: 3, overflow: 'hidden' }}>
                                            <Box sx={{
                                                width: `${(rule.count / data.kpis.alerts_count) * 100}%`,
                                                height: '100%',
                                                bgcolor: 'primary.main',
                                                borderRadius: 3
                                            }} />
                                        </Box>
                                    </Box>
                                ))}
                                {data?.kpis.top_rules.length === 0 && (
                                    <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                                        Aucune alerte récente.
                                    </Typography>
                                )}
                            </Box>
                        </Paper>
                    </Grid>
                </Grid>

            </Box>

            <EventDetailDrawer
                eventId={selectedEventId}
                open={drawerOpen}
                onClose={() => setDrawerOpen(false)}
            />
        </Layout>
    );
}
