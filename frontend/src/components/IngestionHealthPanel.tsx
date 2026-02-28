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
    Alert
} from '@mui/material';
import { RefreshCw, Mail, FileText, Database, Activity, AlertCircle, CheckCircle, Info } from 'lucide-react';
import { fetchWithAuth } from '../lib/api';

interface HealthRow {
    provider_id: number;
    provider_label: string;
    provider_code: string;
    total_imports: number;
    total_emails: number;
    total_xls: number;
    total_pdf: number;
    total_events: number;
    avg_integrity: number;
    missing_pdf: number;
    health_status: 'OK' | 'WARNING' | 'CRITICAL';
}

interface DailyReceiptStatus {
    provider_id: number;
    provider_label: string;
    provider_code: string;
    received_today: number;
    expected_today: number;
    delta: number;
    status: 'OK' | 'WARNING' | 'CRITICAL';
}

export default function IngestionHealthPanel() {
    const [data, setData] = useState<HealthRow[]>([]);
    const [dailyReceipt, setDailyReceipt] = useState<DailyReceiptStatus[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

    const fetchData = async () => {
        setLoading(true);
        try {
            const res = await fetchWithAuth('/health/ingestion-summary');
            if (res.ok) {
                const json = await res.json();
                setData(json.summary);
                setDailyReceipt(json.daily_receipt || []);
                setLastUpdated(new Date());
                setError(null);
            } else {
                setError('Failed to fetch ingestion health summary');
            }
        } catch (err) {
            setError('Error connecting to health API');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 60000); // 60s
        return () => clearInterval(interval);
    }, []);

    const getStatusChip = (status: string) => {
        switch (status) {
            case 'OK':
                return <Chip icon={<CheckCircle size={14} />} label="OK" color="success" size="small" variant="filled" />;
            case 'WARNING':
                return <Chip icon={<AlertCircle size={14} />} label="WARNING" color="warning" size="small" variant="filled" />;
            case 'CRITICAL':
                return <Chip icon={<Activity size={14} />} label="CRITICAL" color="error" size="small" variant="filled" />;
            default:
                return <Chip label={status} size="small" />;
        }
    };

    return (
        <Paper sx={{ p: 3, height: '100%', minHeight: 400, display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Box sx={{ p: 1, borderRadius: 2, bgcolor: 'primary.main', color: 'white', display: 'flex' }}>
                        <Activity size={20} />
                    </Box>
                    <Box>
                        <Typography variant="h6" fontWeight={700}>Ingestion Health</Typography>
                        <Typography variant="caption" color="text.secondary">Today's metrics per provider</Typography>
                    </Box>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                        Last update: {lastUpdated.toLocaleTimeString()}
                    </Typography>
                    <IconButton size="small" onClick={fetchData} disabled={loading}>
                        <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                    </IconButton>
                </Box>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
            )}

            <TableContainer sx={{ flexGrow: 1, overflow: 'auto' }}>
                <Table size="small" stickyHeader>
                    <TableHead>
                        <TableRow>
                            <TableCell sx={{ fontWeight: 700 }}>Provider</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 700 }}>Emails</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 700 }}>XLS</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 700 }}>PDF</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 700 }}>Events</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 700 }}>Integrity</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 700 }}>Miss. PDF</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 700 }}>Status</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {loading && data.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={8} align="center" sx={{ py: 8 }}>
                                    <CircularProgress size={24} />
                                </TableCell>
                            </TableRow>
                        ) : data.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={8} align="center" sx={{ py: 8 }}>
                                    <Typography variant="body2" color="text.secondary">No data for today yet</Typography>
                                </TableCell>
                            </TableRow>
                        ) : (
                            data.map((row: HealthRow) => (
                                <TableRow key={row.provider_id} hover>
                                    <TableCell>
                                        <Typography variant="body2" fontWeight={600}>{row.provider_label}</Typography>
                                        <Typography variant="caption" color="text.secondary">{row.provider_code}</Typography>
                                    </TableCell>
                                    <TableCell align="center">
                                        <Tooltip title="Total unique Email IDs">
                                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                                                <Mail size={12} /> {row.total_emails}
                                            </Box>
                                        </Tooltip>
                                    </TableCell>
                                    <TableCell align="center">
                                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                                            <Database size={12} /> {row.total_xls}
                                        </Box>
                                    </TableCell>
                                    <TableCell align="center">
                                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                                            <FileText size={12} /> {row.total_pdf}
                                        </Box>
                                    </TableCell>
                                    <TableCell align="center">
                                        <Typography variant="body2" fontWeight={700}>{row.total_events.toLocaleString()}</Typography>
                                    </TableCell>
                                    <TableCell align="center">
                                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
                                            <Typography variant="body2" color={row.avg_integrity >= 95 ? 'success.main' : 'warning.main'} fontWeight={600}>
                                                {row.avg_integrity.toFixed(1)}%
                                            </Typography>
                                        </Box>
                                    </TableCell>
                                    <TableCell align="center">
                                        {row.missing_pdf > 0 ? (
                                            <Chip label={row.missing_pdf} size="small" color="warning" variant="outlined" />
                                        ) : (
                                            <Typography variant="caption" color="text.secondary">-</Typography>
                                        )}
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

            <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider', display: 'flex', gap: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: 'success.main' }} />
                    <Typography variant="caption" color="text.secondary">Optimal Ingestion</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: 'warning.main' }} />
                    <Typography variant="caption" color="text.secondary">Missing PDF/Low Integrity</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: 'error.main' }} />
                    <Typography variant="caption" color="text.secondary">XLS Missing/Zero Events</Typography>
                </Box>
            </Box>

            {/* Daily Receipt Widget */}
            {dailyReceipt.length > 0 && (
                <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ display: 'block', mb: 1, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                        Reçus / Attendus aujourd'hui
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {dailyReceipt.map((r) => {
                            const statusColor = r.status === 'OK' ? 'success.main' : r.status === 'WARNING' ? 'warning.main' : 'error.main';
                            const deltaLabel = r.delta > 0 ? `+${r.delta}` : `${r.delta}`;
                            return (
                                <Box key={r.provider_id} sx={{ px: 1.5, py: 1, borderRadius: 2, border: '1px solid', borderColor: statusColor, bgcolor: `${r.status === 'OK' ? '#2e7d32' : r.status === 'WARNING' ? '#ed6c02' : '#d32f2f'}14`, minWidth: 120, textAlign: 'center' }}>
                                    <Typography variant="h6" fontWeight={700} color={statusColor}>
                                        {r.received_today} / {r.expected_today === 0 ? '—' : r.expected_today}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">{r.provider_label}</Typography>
                                    {r.expected_today > 0 && (
                                        <Typography variant="caption" display="block" color={statusColor} fontWeight={600}>{deltaLabel}</Typography>
                                    )}
                                </Box>
                            );
                        })}
                    </Box>
                </Box>
            )}
        </Paper>
    );
}
