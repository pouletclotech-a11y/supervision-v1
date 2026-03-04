'use client';

import React, { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import { fetchWithAuth } from '@/lib/api';
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
    TablePagination,
    Chip,
    IconButton,
    Drawer,
    Divider,
    CircularProgress,
    Stack,
    LinearProgress,
    Tooltip
} from '@mui/material';
import {
    RefreshCw,
    Eye,
    AlertCircle,
    CheckCircle2,
    Clock,
    X,
    BarChart3,
    FileSearch,
    TrendingUp
} from 'lucide-react';
import { useAuth } from '../../../context/AuthContext';

export default function QualityReportPage() {
    const { user } = useAuth();
    const [imports, setImports] = useState<any[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(15);
    const [loading, setLoading] = useState(true);

    // Detail Drawer State
    const [selectedImport, setSelectedImport] = useState<any>(null);
    const [qualityReport, setQualityReport] = useState<any>(null);
    const [pdfReport, setPdfReport] = useState<any>(null);
    const [detailLoading, setDetailLoading] = useState(false);

    const fetchImports = async () => {
        setLoading(true);
        try {
            const res = await fetchWithAuth(`/imports?skip=${page * rowsPerPage}&limit=${rowsPerPage}`);
            if (!res.ok) throw new Error('Failed to fetch imports');
            const data = await res.json();
            setImports(data.imports || []);
            setTotal(data.total || 0);
        } catch (error) {
            console.error('Failed to fetch imports', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchImports();
    }, [page, rowsPerPage]);

    const handleViewDetails = async (imp: any) => {
        setSelectedImport(imp);
        setDetailLoading(true);
        setQualityReport(null);
        setPdfReport(null);
        try {
            // Lazy load reports
            const [qRes, pRes] = await Promise.all([
                fetchWithAuth(`/imports/${imp.id}/quality-report`),
                fetchWithAuth(`/imports/${imp.id}/pdf-match-report`)
            ]);

            if (qRes.ok) setQualityReport(await qRes.json());
            if (pRes.ok) setPdfReport(await pRes.json());
        } catch (error) {
            console.error('Failed to fetch detailed reports', error);
        } finally {
            setDetailLoading(false);
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'OK': return 'success';
            case 'WARN': return 'warning';
            case 'CRIT': return 'error';
            default: return 'default';
        }
    };

    const renderRatio = (value: number) => {
        const pct = Math.round(value * 100);
        let color: "success" | "warning" | "error" = "success";
        if (pct < 80) color = "warning";
        if (pct < 50) color = "error";

        return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Box sx={{ flex: 1, minWidth: 60 }}>
                    <LinearProgress variant="determinate" value={pct} color={color} sx={{ height: 6, borderRadius: 3 }} />
                </Box>
                <Typography variant="caption" sx={{ fontWeight: 600, minWidth: 35 }}>{pct}%</Typography>
            </Box>
        );
    };

    return (
        <Layout>
            <Box sx={{ p: 3 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
                    <Box>
                        <Typography variant="h5" sx={{ fontWeight: 700, color: 'text.primary', display: 'flex', alignItems: 'center', gap: 1.5 }}>
                            <TrendingUp /> Import Quality Gate
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Monitor ingestion health, skip ratios, and PDF matching scores.
                        </Typography>
                    </Box>
                    <IconButton onClick={fetchImports} disabled={loading}>
                        <RefreshCw size={20} className={loading ? 'animate-spin' : ''} />
                    </IconButton>
                </Stack>

                <Paper sx={{ width: '100%', overflow: 'hidden', borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
                    <TableContainer sx={{ maxHeight: 'calc(100vh - 280px)' }}>
                        <Table stickyHeader size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell sx={{ fontWeight: 600 }}>ID</TableCell>
                                    <TableCell sx={{ fontWeight: 600 }}>File / Provider</TableCell>
                                    <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                                    <TableCell sx={{ fontWeight: 600 }}>Created</TableCell>
                                    <TableCell sx={{ fontWeight: 600 }}>Action</TableCell>
                                    <TableCell sx={{ fontWeight: 600 }}>Code</TableCell>
                                    <TableCell sx={{ fontWeight: 600 }}>Skipped</TableCell>
                                    <TableCell sx={{ fontWeight: 600 }}>Top Reasons</TableCell>
                                    <TableCell sx={{ fontWeight: 600 }}>PDF Match</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 600 }}>Action</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {loading && imports.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={8} align="center" sx={{ py: 10 }}>
                                            <CircularProgress size={30} />
                                        </TableCell>
                                    </TableRow>
                                ) : imports.map((imp) => {
                                    const summary = imp.quality_summary;
                                    return (
                                        <TableRow key={imp.id} hover>
                                            <TableCell>{imp.id}</TableCell>
                                            <TableCell>
                                                <Typography variant="button" sx={{ display: 'block', fontSize: '0.75rem', fontWeight: 600 }}>
                                                    {imp.filename}
                                                </Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    {imp.adapter_name} • {new Date(imp.created_at).toLocaleString()}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={summary?.status || 'UNKNOWN'}
                                                    color={getStatusColor(summary?.status)}
                                                    size="small"
                                                    sx={{ fontWeight: 700, fontSize: '0.65rem' }}
                                                />
                                            </TableCell>
                                            <TableCell sx={{ minWidth: 100 }}>
                                                {summary ? renderRatio(summary.created_ratio) : '-'}
                                            </TableCell>
                                            <TableCell sx={{ minWidth: 100 }}>
                                                {summary ? renderRatio(summary.with_action_ratio) : '-'}
                                            </TableCell>
                                            <TableCell sx={{ minWidth: 100 }}>
                                                {summary ? renderRatio(summary.with_code_ratio) : '-'}
                                            </TableCell>
                                            <TableCell>
                                                {summary?.skipped_count > 0 ? (
                                                    <Typography variant="body2" color="error.main" sx={{ fontWeight: 600 }}>
                                                        {summary.skipped_count}
                                                    </Typography>
                                                ) : <CheckCircle2 size={16} color="#2e7d32" />}
                                            </TableCell>
                                            <TableCell>
                                                <Stack direction="row" spacing={0.5}>
                                                    {summary?.top_reasons?.map((r: string) => (
                                                        <Tooltip key={r} title={r}>
                                                            <Chip label={r.split('_').pop()} size="small" variant="outlined" sx={{ fontSize: '0.6rem' }} />
                                                        </Tooltip>
                                                    ))}
                                                </Stack>
                                            </TableCell>
                                            <TableCell>
                                                {summary?.pdf_match_ratio !== null ? (
                                                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                                        {Math.round(summary.pdf_match_ratio * 100)}%
                                                    </Typography>
                                                ) : '-'}
                                            </TableCell>
                                            <TableCell align="right">
                                                <IconButton size="small" onClick={() => handleViewDetails(imp)}>
                                                    <Eye size={18} />
                                                </IconButton>
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </TableContainer>
                    <TablePagination
                        rowsPerPageOptions={[15, 30, 50]}
                        component="div"
                        count={total}
                        rowsPerPage={rowsPerPage}
                        page={page}
                        onPageChange={(_, p) => setPage(p)}
                        onRowsPerPageChange={(e) => {
                            setRowsPerPage(parseInt(e.target.value, 10));
                            setPage(0);
                        }}
                    />
                </Paper>
            </Box>

            {/* DETAIL DRAWER */}
            <Drawer
                anchor="right"
                open={!!selectedImport}
                onClose={() => setSelectedImport(null)}
                PaperProps={{ sx: { width: 600, p: 0 } }}
            >
                {selectedImport && (
                    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                        <Box sx={{ p: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', bgcolor: 'background.default' }}>
                            <Box>
                                <Typography variant="h6" sx={{ fontWeight: 700 }}>Import #{selectedImport.id} Report</Typography>
                                <Typography variant="caption" color="text.secondary">{selectedImport.filename}</Typography>
                            </Box>
                            <IconButton onClick={() => setSelectedImport(null)}><X size={20} /></IconButton>
                        </Box>

                        <Divider />

                        <Box sx={{ p: 3, flex: 1, overflowY: 'auto' }}>
                            {detailLoading ? (
                                <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}><CircularProgress /></Box>
                            ) : (
                                <Stack spacing={3}>
                                    <Box>
                                        <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <BarChart3 size={16} /> Quality Report Details
                                        </Typography>
                                        <Paper variant="outlined" sx={{ p: 2, bgcolor: 'grey.50', fontFamily: 'monospace', fontSize: '0.8rem', overflowX: 'auto' }}>
                                            <pre>{JSON.stringify(qualityReport, null, 2)}</pre>
                                        </Paper>
                                    </Box>

                                    {pdfReport && (
                                        <Box>
                                            <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                <FileSearch size={16} /> PDF Match Details
                                            </Typography>
                                            <Paper variant="outlined" sx={{ p: 2, bgcolor: 'grey.50', fontFamily: 'monospace', fontSize: '0.8rem', overflowX: 'auto' }}>
                                                <pre>{JSON.stringify(pdfReport, null, 2)}</pre>
                                            </Paper>
                                        </Box>
                                    )}
                                </Stack>
                            )}
                        </Box>
                    </Box>
                )}
            </Drawer>
        </Layout>
    );
}
