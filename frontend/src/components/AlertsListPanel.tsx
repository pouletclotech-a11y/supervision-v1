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
    CircularProgress,
    Alert,
    Pagination,
    Stack
} from '@mui/material';
import { RefreshCw, Filter, ShieldAlert, ArrowUpRight, Clock } from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { format } from 'date-fns';
import EventDetailDrawer from './EventDetailDrawer';

interface AlertsListPanelProps {
    dateFrom?: string;
    dateTo?: string;
}

export default function AlertsListPanel({ dateFrom, dateTo }: AlertsListPanelProps) {
    const router = useRouter();
    const [alerts, setAlerts] = useState<any[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const limit = 10;

    const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
    const [drawerOpen, setDrawerOpen] = useState(false);

    const fetchAlerts = async () => {
        setLoading(true);
        try {
            let url = `/alerts/?page=${page}&limit=${limit}`;
            if (dateFrom) url += `&date_from=${dateFrom}`;
            if (dateTo) url += `&date_to=${dateTo}`;
            
            const res = await fetchWithAuth(url);
            if (res.ok) {
                const json = await res.json();
                setAlerts(json.items);
                setTotal(json.total);
                setError(null);
            } else {
                setError('Failed to fetch alerts');
            }
        } catch (err) {
            console.error("Alerts API Error:", err);
            setError('Erreur lors de la connexion à l\'API Alerts');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAlerts();
    }, [page, dateFrom, dateTo]);

    const handleRowClick = (eventId: number) => {
        setSelectedEventId(eventId);
        setDrawerOpen(true);
    };

    return (
        <Paper sx={{ p: 3, height: '100%', minHeight: 500, display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Box sx={{ p: 1, borderRadius: 2, bgcolor: 'error.main', color: 'white', display: 'flex' }}>
                        <ShieldAlert size={20} />
                    </Box>
                    <Box>
                        <Typography variant="h6" fontWeight={700}>Individual Alerts</Typography>
                        <Typography variant="caption" color="text.secondary">
                            {dateFrom && dateTo ? `Real-time hits (${dateFrom} au ${dateTo})` : 'Real-time detection hits'}
                        </Typography>
                    </Box>
                </Box>
                <IconButton size="small" onClick={fetchAlerts} disabled={loading}>
                    <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                </IconButton>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            <TableContainer sx={{ flexGrow: 1, overflow: 'auto' }}>
                <Table size="small" stickyHeader>
                    <TableHead>
                        <TableRow>
                            <TableCell sx={{ fontWeight: 700 }}>Time</TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>Rule</TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>Site</TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>Provider</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 700 }}>Score</TableCell>
                            <TableCell align="right" sx={{ fontWeight: 700 }}>Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {loading ? (
                            <TableRow><TableCell colSpan={6} align="center" sx={{ py: 8 }}><CircularProgress size={24} /></TableCell></TableRow>
                        ) : error ? (
                            <TableRow><TableCell colSpan={6} align="center" sx={{ py: 8 }}>
                                <Typography variant="body2" color="error">{error}</Typography>
                            </TableCell></TableRow>
                        ) : alerts.length === 0 ? (
                            <TableRow><TableCell colSpan={6} align="center" sx={{ py: 8 }}>
                                <Typography variant="body2" color="text.secondary">Aucune alerte détectée sur cette période.</Typography>
                            </TableCell></TableRow>
                        ) : (
                            alerts.map((row) => (
                                <TableRow
                                    key={row.hit_id}
                                    hover
                                    sx={{ cursor: 'pointer' }}
                                    onClick={() => handleRowClick(row.event_id)}
                                >
                                    <TableCell sx={{ fontSize: '0.75rem' }}>
                                        <Typography suppressHydrationWarning variant="inherit">
                                            {format(new Date(row.created_at), 'dd/MM HH:mm:ss')}
                                        </Typography>
                                    </TableCell>
                                    <TableCell sx={{ fontWeight: 600 }}>{row.rule_name}</TableCell>
                                    <TableCell>
                                        <Typography 
                                            variant="body2" 
                                            color="primary.main"
                                            sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                router.push(`/client/${row.site_code}`);
                                            }}
                                        >
                                            {row.site_code}
                                        </Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant="caption">{row.provider_name}</Typography>
                                    </TableCell>
                                    <TableCell align="center">
                                        {row.score !== null ? (
                                            <Chip label={row.score.toFixed(2)} size="small" color="primary" sx={{ height: 18, fontSize: 10 }} />
                                        ) : '-'}
                                    </TableCell>
                                    <TableCell align="right">
                                        <ArrowUpRight size={14} style={{ opacity: 0.5 }} />
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>

            <Stack direction="row" justifyContent="center" sx={{ mt: 3 }}>
                <Pagination
                    count={Math.ceil(total / limit)}
                    page={page}
                    onChange={(e, v) => setPage(v)}
                    size="small"
                    color="primary"
                />
            </Stack>

            <EventDetailDrawer
                eventId={selectedEventId}
                open={drawerOpen}
                onClose={() => setDrawerOpen(false)}
            />
        </Paper>
    );
}
