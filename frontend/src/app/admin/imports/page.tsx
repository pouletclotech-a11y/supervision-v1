'use client';

import React, { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
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
    Button,
    Drawer,
    Divider,
    Alert,
    CircularProgress,
    Stack,
    TextField,
    InputAdornment
} from '@mui/material';
import {
    RefreshCw,
    Search,
    Eye,
    Download,
    FileText,
    Database,
    Mail,
    AlertCircle,
    CheckCircle2,
    Clock,
    X,
    Code
} from 'lucide-react';
import { useAuth } from '../../../context/AuthContext';

export default function ImportsPage() {
    const { user } = useAuth();
    const [imports, setImports] = useState<any[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(15);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');

    // Inspection Drawer State
    const [selectedImport, setSelectedImport] = useState<any>(null);
    const [inspectionData, setInspectionData] = useState<any>(null);
    const [inspectLoading, setInspectLoading] = useState(false);

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

    const fetchImports = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_URL}/imports/?skip=${page * rowsPerPage}&limit=${rowsPerPage}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
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

    const handleInspect = async (imp: any) => {
        setSelectedImport(imp);
        setInspectLoading(true);
        setInspectionData(null);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_URL}/imports/${imp.id}/inspect`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            setInspectionData(data);
        } catch (error) {
            console.error('Failed to inspect import', error);
        } finally {
            setInspectLoading(false);
        }
    };

    const getStatusChip = (status: string) => {
        switch (status) {
            case 'SUCCESS': return <Chip icon={<CheckCircle2 size={14} />} label="SUCCESS" color="success" size="small" />;
            case 'ERROR': return <Chip icon={<AlertCircle size={14} />} label="ERROR" color="error" size="small" />;
            case 'UNMATCHED': return <Chip icon={<AlertCircle size={14} />} label="UNMATCHED" color="warning" size="small" />;
            default: return <Chip icon={<Clock size={14} />} label={status} variant="outlined" size="small" />;
        }
    };

    const getSourceIcon = (adapter: string) => {
        if (adapter?.toLowerCase().includes('email')) return <Mail size={16} />;
        return <Database size={16} />;
    };

    return (
        <Layout>
            <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
                <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box>
                        <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
                            Imports Inspector
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Audit ingestion logs, inspect headers, and generate configuration skeletons.
                        </Typography>
                    </Box>
                    <Button
                        variant="contained"
                        startIcon={<RefreshCw size={18} />}
                        onClick={fetchImports}
                        sx={{ borderRadius: 2 }}
                    >
                        Refresh
                    </Button>
                </Box>

                <Paper sx={{ mb: 3, p: 2, borderRadius: 2 }}>
                    <TextField
                        fullWidth
                        placeholder="Search by filename or Message-ID..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        slotProps={{
                            input: {
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <Search size={20} />
                                    </InputAdornment>
                                ),
                            }
                        }}
                    />
                </Paper>

                <TableContainer component={Paper} sx={{ borderRadius: 2, overflow: 'hidden' }}>
                    <Table size="small">
                        <TableHead sx={{ bgcolor: 'background.paper' }}>
                            <TableRow>
                                <TableCell sx={{ fontWeight: 600 }}>Date</TableCell>
                                <TableCell sx={{ fontWeight: 600 }}>File Name</TableCell>
                                <TableCell sx={{ fontWeight: 600 }}>Source</TableCell>
                                <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                                <TableCell sx={{ fontWeight: 600 }}>Events</TableCell>
                                <TableCell sx={{ fontWeight: 600 }}>Unmatched</TableCell>
                                <TableCell sx={{ fontWeight: 600 }} align="right">Actions</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {loading ? (
                                <TableRow>
                                    <TableCell colSpan={7} align="center" sx={{ py: 10 }}>
                                        <CircularProgress size={40} />
                                    </TableCell>
                                </TableRow>
                            ) : imports.map((imp) => (
                                <TableRow key={imp.id} hover>
                                    <TableCell>{new Date(imp.created_at).toLocaleString()}</TableCell>
                                    <TableCell sx={{ fontWeight: 500 }}>{imp.filename}</TableCell>
                                    <TableCell>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            {getSourceIcon(imp.adapter_name)}
                                            {imp.adapter_name}
                                        </Box>
                                    </TableCell>
                                    <TableCell>{getStatusChip(imp.status)}</TableCell>
                                    <TableCell>{imp.events_count}</TableCell>
                                    <TableCell>
                                        {imp.unmatched_count > 0 ? (
                                            <Typography color="warning.main" fontWeight={700}>
                                                {imp.unmatched_count}
                                            </Typography>
                                        ) : '0'}
                                    </TableCell>
                                    <TableCell align="right">
                                        <Stack direction="row" spacing={1} justifyContent="flex-end">
                                            <IconButton size="small" onClick={() => handleInspect(imp)} color="primary">
                                                <Eye size={18} />
                                            </IconButton>
                                            <IconButton size="small" component="a" href={`${API_URL}/imports/${imp.id}/download`} target="_blank">
                                                <Download size={18} />
                                            </IconButton>
                                        </Stack>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                    <TablePagination
                        component="div"
                        count={total}
                        page={page}
                        onPageChange={(e, newPage) => setPage(newPage)}
                        rowsPerPage={rowsPerPage}
                        onRowsPerPageChange={(e) => setRowsPerPage(parseInt(e.target.value, 10))}
                    />
                </TableContainer>

                {/* INSPECTION DRAWER */}
                <Drawer
                    anchor="right"
                    open={!!selectedImport}
                    onClose={() => setSelectedImport(null)}
                    PaperProps={{ sx: { width: { xs: '100%', md: 600 }, p: 0 } }}
                >
                    {selectedImport && (
                        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                            <Box sx={{ p: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center', bgcolor: 'background.paper', borderBottom: '1px solid', borderColor: 'divider' }}>
                                <Typography variant="h6" fontWeight={700}>
                                    Import Inspection
                                </Typography>
                                <IconButton onClick={() => setSelectedImport(null)}><X size={20} /></IconButton>
                            </Box>

                            <Box sx={{ p: 3, flexGrow: 1, overflow: 'auto' }}>
                                <Typography variant="subtitle2" color="text.secondary" gutterBottom>METADATA</Typography>
                                <Paper variant="outlined" sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
                                    <Grid container spacing={2}>
                                        <Grid size={{ xs: 6 }}>
                                            <Typography variant="caption" color="text.secondary">File Name</Typography>
                                            <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>{selectedImport.filename}</Typography>
                                        </Grid>
                                        <Grid size={{ xs: 6 }}>
                                            <Typography variant="caption" color="text.secondary">Source Hash</Typography>
                                            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{selectedImport.file_hash}</Typography>
                                        </Grid>
                                        <Grid size={{ xs: 6 }}>
                                            <Typography variant="caption" color="text.secondary">Adapter</Typography>
                                            <Typography variant="body2">{selectedImport.adapter_name}</Typography>
                                        </Grid>
                                        <Grid size={{ xs: 6 }}>
                                            <Typography variant="caption" color="text.secondary">Message ID</Typography>
                                            <Typography variant="body2" sx={{ wordBreak: 'break-all', fontSize: '0.75rem' }}>{selectedImport.source_message_id || 'N/A'}</Typography>
                                        </Grid>
                                    </Grid>
                                </Paper>

                                <Typography variant="subtitle2" color="text.secondary" gutterBottom>FILE CONTENT PREVIEW</Typography>
                                {inspectLoading ? (
                                    <Box sx={{ textAlign: 'center', py: 5 }}><CircularProgress size={30} /></Box>
                                ) : inspectionData ? (
                                    <Box>
                                        {inspectionData.file_type === 'PDF' ? (
                                            <Paper variant="outlined" sx={{ p: 2, mb: 3, bgcolor: '#1e293b', color: '#e2e8f0', fontFamily: 'monospace', whiteSpace: 'pre-wrap', fontSize: '0.75rem', maxHeight: 300, overflow: 'auto' }}>
                                                {inspectionData.raw_text_sample}
                                            </Paper>
                                        ) : (
                                            <TableContainer component={Paper} variant="outlined" sx={{ mb: 3, maxHeight: 300 }}>
                                                <Table size="small" stickyHeader>
                                                    <TableHead>
                                                        <TableRow>
                                                            {inspectionData.headers?.map((h: string, i: number) => (
                                                                <TableCell key={i} sx={{ bgcolor: 'background.paper', fontWeight: 700, fontSize: '0.7rem' }}>{h}</TableCell>
                                                            ))}
                                                        </TableRow>
                                                    </TableHead>
                                                    <TableBody>
                                                        {inspectionData.sample_rows?.map((row: any[], i: number) => (
                                                            <TableRow key={i}>
                                                                {row.map((cell: any, j: number) => (
                                                                    <TableCell key={j} sx={{ fontSize: '0.7rem' }}>{String(cell)}</TableCell>
                                                                ))}
                                                            </TableRow>
                                                        ))}
                                                    </TableBody>
                                                </Table>
                                            </TableContainer>
                                        )}

                                        <Typography variant="subtitle2" color="text.secondary" gutterBottom>YPSILON PROFILE SKELETON (SUGGESTION)</Typography>
                                        <Box sx={{ position: 'relative' }}>
                                            <Paper sx={{ p: 2, bgcolor: '#0f172a', color: '#38bdf8', fontFamily: 'monospace', fontSize: '0.8rem', position: 'relative' }}>
                                                <pre style={{ margin: 0 }}>{inspectionData.skeleton_yaml}</pre>
                                                <Button size="small" startIcon={<Code size={14} />} sx={{ position: 'absolute', top: 8, right: 8, color: '#94a3b8' }}>Copy</Button>
                                            </Paper>
                                        </Box>
                                    </Box>
                                ) : (
                                    <Alert severity="error">Failed to extract file content.</Alert>
                                )}
                            </Box>

                            <Box sx={{ p: 3, bgcolor: 'background.paper', borderTop: '1px solid', borderColor: 'divider' }}>
                                <Button fullWidth variant="contained" size="large" sx={{ borderRadius: 2 }}>
                                    Manage Profiles
                                </Button>
                            </Box>
                        </Box>
                    )}
                </Drawer>
            </Box>
        </Layout>
    );
}

import { Grid2 as Grid } from '@mui/material';
