'use client';

import React from 'react';
import Layout from '../components/Layout';
import {
    Box,
    Grid,
    Paper,
    Typography,
    IconButton,
    Chip,
    LinearProgress
} from '@mui/material';
import {
    Activity,
    Server,
    Database,
    AlertTriangle,
    MoreHorizontal,
    ArrowUpRight,
    Clock
} from 'lucide-react';
import IngestionHealthPanel from '../components/IngestionHealthPanel';

export default function DashboardPage() {
    return (
        <Layout>
            <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>

                {/* WELCOME SECTION */}
                <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'end' }}>
                    <Box>
                        <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
                            System Overview
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Good afternoon, Administrator. System is running optimally.
                        </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Chip label="v1.0.2-beta" size="small" variant="outlined" sx={{ borderColor: 'divider' }} />
                        <Chip icon={<Activity size={14} />} label="Healthy" color="success" size="small" />
                    </Box>
                </Box>

                {/* STATS CARDS */}
                <Grid container spacing={3} sx={{ mb: 4 }}>
                    {[
                        { title: 'Events Today', value: '128,430', change: '+12%', color: '#197fe6', icon: <Activity /> },
                        { title: 'Processing Rate', value: '450 ev/s', change: '+5%', color: '#10b981', icon: <Server /> },
                        { title: 'Pending Imports', value: '3', change: '-2', color: '#f59e0b', icon: <Database /> },
                        { title: 'Active Alerts', value: '12', change: '+4', color: '#ef4444', icon: <AlertTriangle /> },
                    ].map((stat, i) => (
                        <Grid key={i} size={{ xs: 12, sm: 6, md: 3 }}>
                            <Paper sx={{ p: 3, position: 'relative', overflow: 'hidden' }}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 2 }}>
                                    <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: `${stat.color}22`, color: stat.color }}>
                                        {stat.icon}
                                    </Box>
                                    <IconButton size="small" sx={{ color: 'text.secondary' }}><MoreHorizontal size={16} /></IconButton>
                                </Box>
                                <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5 }}>
                                    {stat.value}
                                </Typography>
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                    <Box component="span" sx={{ color: stat.change.startsWith('+') ? 'success.main' : 'error.main', display: 'flex', alignItems: 'center' }}>
                                        {stat.change.startsWith('+') ? <ArrowUpRight size={14} /> : <ArrowUpRight size={14} style={{ transform: 'rotate(90deg)' }} />}
                                        {stat.change}
                                    </Box>
                                    from yesterday
                                </Typography>
                            </Paper>
                        </Grid>
                    ))}
                </Grid>

                {/* MAIN GRID */}
                <Grid container spacing={3}>
                    {/* LEFT: INGESTION HEALTH */}
                    <Grid size={{ xs: 12, md: 8 }}>
                        <IngestionHealthPanel />
                    </Grid>

                    {/* RIGHT: SYSTEM STATUS */}
                    <Grid size={{ xs: 12, md: 4 }}>
                        <Paper sx={{ p: 3, height: '100%' }}>
                            <Typography variant="h6" sx={{ mb: 3 }}>System Health</Typography>

                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                                {[
                                    { label: 'Ingestion Worker', status: 'Optimal', val: 92, color: 'success' },
                                    { label: 'Database (Timescale)', status: 'Heavy Load', val: 78, color: 'warning' },
                                    { label: 'Redis Queue', status: 'Optimal', val: 12, color: 'info' },
                                    { label: 'API Gateway', status: 'Optimal', val: 99, color: 'success' },
                                ].map((sys, i) => (
                                    <Box key={i}>
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                                            <Typography variant="body2" fontWeight={600}>{sys.label}</Typography>
                                            <Typography variant="caption" color={`${sys.color}.main`}>{sys.status}</Typography>
                                        </Box>
                                        <LinearProgress
                                            variant="determinate"
                                            value={sys.val}
                                            color={sys.color as any}
                                            sx={{ height: 6, borderRadius: 4, bgcolor: 'background.default' }}
                                        />
                                    </Box>
                                ))}
                            </Box>

                            <Box sx={{ mt: 4, pt: 3, borderTop: '1px solid', borderColor: 'divider' }}>
                                <Typography variant="subtitle2" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Clock size={16} /> Recent Logs
                                </Typography>
                                {[
                                    { time: '10:42 AM', msg: 'Backup completed successfully', type: 'info' },
                                    { time: '10:30 AM', msg: 'High latency on Zone B', type: 'warning' },
                                    { time: '09:15 AM', msg: 'Worker restarted', type: 'error' },
                                ].map((log, i) => (
                                    <Box key={i} sx={{ display: 'flex', gap: 2, mb: 1.5, fontSize: '0.75rem' }}>
                                        <Typography color="text.secondary" sx={{ minWidth: 60 }}>{log.time}</Typography>
                                        <Typography color="text.primary">{log.msg}</Typography>
                                    </Box>
                                ))}
                            </Box>
                        </Paper>
                    </Grid>
                </Grid>

            </Box>
        </Layout>
    );
}
