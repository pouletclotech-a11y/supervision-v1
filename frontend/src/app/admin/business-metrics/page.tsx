'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import {
    Box, Grid, Paper, Typography, CircularProgress, Alert,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    TablePagination, Chip, Select, MenuItem, FormControl, InputLabel
} from '@mui/material';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useAuth } from '../../../context/AuthContext';
import { fetchWithAuth } from '../../../utils/api';

// ── Types ─────────────────────────────────────────────────────────────────────
interface ProviderSummary {
    provider_label: string;
    provider_code: string;
    total_sites: number;
    total_events: number;
}

interface TimeseriesPoint {
    period: string;
    new_sites: number;
}

interface SiteRow {
    id: number;
    code_site: string;
    client_name: string;
    provider_label: string;
    first_seen_at: string;
    last_seen_at: string;
    total_events: number;
}

interface SitesResponse {
    items: SiteRow[];
    total: number;
    page: number;
    size: number;
}

const PROVIDER_COLORS: Record<string, string> = {
    PROVIDER_ALPHA: '#3b82f6',
    PROVIDER_BETA: '#22c55e',
    PROVIDER_GAMMA: '#f59e0b',
    PROVIDER_UNCLASSIFIED: '#6b7280',
};

function SummaryCard({ data }: { data: ProviderSummary }) {
    const color = PROVIDER_COLORS[data.provider_code] || '#6b7280';
    return (
        <Paper sx={{ p: 3, borderRadius: 3, borderTop: `4px solid ${color}` }}>
            <Typography variant="overline" color="text.secondary">{data.provider_label}</Typography>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                <Box>
                    <Typography variant="h4" fontWeight={700}>{data.total_sites}</Typography>
                    <Typography variant="caption" color="text.secondary">Codes site</Typography>
                </Box>
                <Box textAlign="right">
                    <Typography variant="h5" color="text.secondary">{data.total_events.toLocaleString()}</Typography>
                    <Typography variant="caption" color="text.secondary">Événements</Typography>
                </Box>
            </Box>
        </Paper>
    );
}

export default function BusinessMetricsPage() {
    const { user } = useAuth();

    const [summary, setSummary] = useState<ProviderSummary[]>([]);
    const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
    const [sites, setSites] = useState<SiteRow[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(25);
    const [granularity, setGranularity] = useState<'month' | 'year'>('month');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const loadSummary = useCallback(async () => {
        const res = await fetchWithAuth(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/admin/business/summary`);
        if (!res.ok) throw new Error('Summary fetch failed');
        return res.json();
    }, []);

    const loadTimeseries = useCallback(async () => {
        const res = await fetchWithAuth(
            `${process.env.NEXT_PUBLIC_API_URL}/api/v1/admin/business/timeseries?granularity=${granularity}`
        );
        if (!res.ok) throw new Error('Timeseries fetch failed');
        return res.json();
    }, [granularity]);

    const loadSites = useCallback(async () => {
        const res = await fetchWithAuth(
            `${process.env.NEXT_PUBLIC_API_URL}/api/v1/admin/business/sites?page=${page + 1}&size=${rowsPerPage}`
        );
        if (!res.ok) throw new Error('Sites fetch failed');
        return res.json() as Promise<SitesResponse>;
    }, [page, rowsPerPage]);

    useEffect(() => {
        setLoading(true);
        Promise.all([loadSummary(), loadTimeseries(), loadSites()])
            .then(([sumData, tsData, sitesData]) => {
                setSummary(sumData);
                setTimeseries(tsData.map((t: TimeseriesPoint) => ({
                    ...t,
                    period: new Date(t.period).toLocaleDateString('fr-FR', {
                        month: granularity === 'month' ? 'short' : undefined,
                        year: 'numeric'
                    })
                })));
                setSites(sitesData.items);
                setTotal(sitesData.total);
            })
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, [loadSummary, loadTimeseries, loadSites, granularity]);

    if (loading) return (
        <Layout>
            <Box display="flex" justifyContent="center" alignItems="center" height="60vh">
                <CircularProgress />
            </Box>
        </Layout>
    );

    return (
        <Layout>
            <Box sx={{ p: 3 }}>
                {/* Header */}
                <Box sx={{ mb: 4 }}>
                    <Typography variant="h5" fontWeight={700}>
                        📊 Métriques Business — Raccordements
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        Comptage des codes site distincts par télésurveilleur
                    </Typography>
                </Box>

                {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

                {/* Summary Widgets */}
                <Grid container spacing={2} sx={{ mb: 4 }}>
                    {summary.map((s) => (
                        <Grid item xs={12} sm={6} md={3} key={s.provider_code}>
                            <SummaryCard data={s} />
                        </Grid>
                    ))}
                </Grid>

                {/* Timeseries Chart */}
                <Paper sx={{ p: 3, mb: 4, borderRadius: 3 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                        <Typography variant="h6" fontWeight={600}>Nouveaux raccordements</Typography>
                        <FormControl size="small">
                            <InputLabel>Granularité</InputLabel>
                            <Select
                                label="Granularité"
                                value={granularity}
                                onChange={(e) => setGranularity(e.target.value as 'month' | 'year')}
                            >
                                <MenuItem value="month">Par mois</MenuItem>
                                <MenuItem value="year">Par année</MenuItem>
                            </Select>
                        </FormControl>
                    </Box>
                    <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={timeseries}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                            <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                            <YAxis tick={{ fontSize: 12 }} />
                            <Tooltip
                                contentStyle={{ borderRadius: 8 }}
                                formatter={(v: number) => [v, 'Nouveaux sites']}
                            />
                            <Bar dataKey="new_sites" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </Paper>

                {/* Drilldown Table */}
                <Paper sx={{ borderRadius: 3 }}>
                    <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                        <Typography variant="h6" fontWeight={600}>Détail des raccordements</Typography>
                    </Box>
                    <TableContainer>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>Code site</TableCell>
                                    <TableCell>Nom client</TableCell>
                                    <TableCell>Provider</TableCell>
                                    <TableCell>Premier vu</TableCell>
                                    <TableCell>Dernier vu</TableCell>
                                    <TableCell align="right">Événements</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {sites.map((row) => (
                                    <TableRow key={row.id} hover>
                                        <TableCell><code>{row.code_site}</code></TableCell>
                                        <TableCell>{row.client_name || '—'}</TableCell>
                                        <TableCell>
                                            <Chip
                                                label={row.provider_label}
                                                size="small"
                                                sx={{
                                                    bgcolor: PROVIDER_COLORS[row.provider_label?.toUpperCase().replace(/ /g, '_')] || '#6b7280',
                                                    color: '#fff',
                                                    fontWeight: 600,
                                                    fontSize: 11
                                                }}
                                            />
                                        </TableCell>
                                        <TableCell>{new Date(row.first_seen_at).toLocaleDateString('fr-FR')}</TableCell>
                                        <TableCell>{new Date(row.last_seen_at).toLocaleDateString('fr-FR')}</TableCell>
                                        <TableCell align="right">{row.total_events.toLocaleString()}</TableCell>
                                    </TableRow>
                                ))}
                                {sites.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={6} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                                            Aucun raccordement enregistré
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                    <TablePagination
                        component="div"
                        count={total}
                        page={page}
                        rowsPerPage={rowsPerPage}
                        onPageChange={(_: any, newPage: number) => setPage(newPage)}
                        onRowsPerPageChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                            setRowsPerPage(parseInt(e.target.value, 10));
                            setPage(0);
                        }}
                        rowsPerPageOptions={[25, 50, 100]}
                        labelRowsPerPage="Lignes :"
                    />
                </Paper>
            </Box>
        </Layout>
    );
}
