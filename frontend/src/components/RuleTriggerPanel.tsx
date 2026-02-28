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
import { RefreshCw, Activity, AlertTriangle, CheckCircle, Clock, Filter, ExternalLink } from 'lucide-react';
import { fetchWithAuth } from '../lib/api';
import { useRouter } from 'next/navigation';

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
        } catch (err) {
            setError('Error connecting to rules API');
        } finally {
            setLoading(false);
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

    const handleRowClick = (ruleName: string) => {
        // Rediriger vers la page de validation avec filtre par règle
        const searchParams = new URLSearchParams();
        searchParams.set('rule', ruleName);
        router.push(`/admin/data-validation?${searchParams.toString()}`);
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
                                    onClick={() => handleRowClick(row.rule_name)}
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
        </Paper>
    );
}
