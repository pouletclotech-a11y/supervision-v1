'use client';

import React, { useState, useEffect } from 'react';
import {
    Box,
    Typography,
    Button,
    Chip,
    IconButton,
    Paper,
    TextField,
    CircularProgress,
    Divider,
    Tooltip,
    Alert,
    Tabs,
    Tab,
    Drawer,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import {
    Zap,
    RefreshCw,
    Search,
    AlertCircle,
    FileWarning,
    Play,
    Eye,
    Edit3,
    History,
    CheckCircle
} from 'lucide-react';
import Layout from '../../../components/Layout';
import { fetchWithAuth } from '../../../lib/api';
import ProfileEditor from './ProfileEditor';

interface UnmatchedImport {
    id: number;
    filename: string;
    status: string;
    created_at: string;
    max_score?: number;
    best_candidate?: string;
    import_metadata: any;
    raw_payload?: string;
}

export default function CalibrationPage() {
    const [tab, setTab] = useState(0);
    const [unmatched, setUnmatched] = useState<UnmatchedImport[]>([]);
    const [loading, setLoading] = useState(false);
    const [selectedImport, setSelectedImport] = useState<UnmatchedImport | null>(null);
    const [reprocessLoading, setReprocessLoading] = useState<number | null>(null);

    const fetchUnmatched = async () => {
        setLoading(true);
        try {
            const res = await fetchWithAuth('/admin/unmatched?limit=50');
            if (res.ok) {
                const data = await res.json();
                setUnmatched(data);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUnmatched();
    }, []);

    const handleReprocess = async (importId: number) => {
        setReprocessLoading(importId);
        try {
            const res = await fetchWithAuth(`/admin/reprocess/import/${importId}`, {
                method: 'POST'
            });
            if (res.ok) {
                // Wait a bit for the background task to start/finish
                setTimeout(fetchUnmatched, 1500);
            }
        } catch (err) {
            console.error(err);
            alert("Reprocess failed. See console.");
        } finally {
            setReprocessLoading(null);
        }
    };

    const columns: GridColDef[] = [
        { field: 'id', headerName: 'ID', width: 70 },
        {
            field: 'created_at',
            headerName: 'Date',
            width: 170,
            valueFormatter: (params: any) => {
                if (!params.value) return '';
                return new Date(params.value).toLocaleString();
            }
        },
        { field: 'filename', headerName: 'File', minWidth: 200, flex: 1 },
        {
            field: 'status', headerName: 'Status', width: 220,
            renderCell: (params: GridRenderCellParams) => {
                let color: any = 'warning';
                const s = params.value;
                if (s === 'SUCCESS') color = 'success';
                else if (s === 'ERROR' || s === 'NO_PROFILE_MATCH' || s === 'PARSER_FAILED') color = 'error';
                else if (s === 'PENDING') color = 'info';

                return <Chip label={s} color={color} size="small" variant="filled" sx={{ fontWeight: 'bold' }} />;
            }
        },
        {
            field: 'max_score', headerName: 'Score', width: 80,
            renderCell: (params: GridRenderCellParams) => params.value ? parseFloat(params.value).toFixed(2) : '-'
        },
        {
            field: 'actions', headerName: 'Actions', width: 120, align: 'right',
            renderCell: (params: GridRenderCellParams) => (
                <Box sx={{ display: 'flex', gap: 1 }}>
                    <IconButton size="small" onClick={() => setSelectedImport(params.row)} title="View Detail">
                        <Eye size={16} />
                    </IconButton>
                    <IconButton
                        size="small"
                        color="primary"
                        onClick={() => handleReprocess(params.row.id)}
                        disabled={reprocessLoading === params.row.id || params.row.status === 'PENDING'}
                        title="Reprocess"
                    >
                        {reprocessLoading === params.row.id ? <CircularProgress size={16} /> : <RefreshCw size={16} />}
                    </IconButton>
                </Box>
            )
        }
    ];

    return (
        <Layout>
            <Box sx={{ p: 4, height: '100%', display: 'flex', flexDirection: 'column', bgcolor: 'background.default' }}>
                <Typography variant="h4" fontWeight="bold" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 2, color: 'primary.main' }}>
                    <Zap size={32} /> Calibration Tool
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    Diagnose unmatched events and recalibrate ingestion profiles.
                </Typography>

                <Tabs value={tab} onChange={(_: any, v: number) => setTab(v)} sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}>
                    <Tab label="Unmatched Imports" icon={<FileWarning size={18} />} iconPosition="start" />
                    <Tab label="Profile Editor" icon={<Edit3 size={18} />} iconPosition="start" />
                    <Tab label="History & Jobs" icon={<History size={18} />} iconPosition="start" />
                </Tabs>

                <Box sx={{ flex: 1, minHeight: 0 }}>
                    {tab === 0 && (
                        <Paper sx={{ height: '100%', width: '100%', p: 0, bgcolor: 'background.paper', borderRadius: 2, overflow: 'hidden' }}>
                            <DataGrid
                                rows={unmatched}
                                columns={columns}
                                loading={loading}
                                rowHeight={50}
                                density="compact"
                                disableRowSelectionOnClick
                                sx={{
                                    border: 0,
                                    '& .MuiDataGrid-columnHeaders': {
                                        bgcolor: 'rgba(255,255,255,0.02)',
                                        borderBottom: '1px solid',
                                        borderColor: 'divider'
                                    }
                                }}
                            />
                        </Paper>
                    )}

                    {tab === 1 && (
                        <ProfileEditor />
                    )}

                    {tab === 2 && (
                        <Box sx={{ p: 4, textAlign: 'center' }}>
                            <History size={64} style={{ opacity: 0.1, marginBottom: 16 }} />
                            <Typography variant="h6" color="text.secondary">Audit Logs & Jobs</Typography>
                            <Typography variant="body2" color="text.disabled">
                                Tracking of admin actions and background reprocessing jobs.
                            </Typography>
                        </Box>
                    )}
                </Box>
            </Box>

            {/* DETAIL DRAWER */}
            <Drawer
                anchor="right"
                open={!!selectedImport}
                onClose={() => setSelectedImport(null)}
                PaperProps={{ sx: { width: 600, bgcolor: 'background.paper' } }}
            >
                {selectedImport && (
                    <Box sx={{ p: 4 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                            <Typography variant="h5" fontWeight="bold">Import Detail</Typography>
                            <Chip label={`#${selectedImport.id}`} variant="outlined" />
                        </Box>

                        <Divider sx={{ mb: 3 }} />

                        <Box sx={{ mb: 3 }}>
                            <Typography variant="caption" color="text.secondary" fontWeight="bold" sx={{ textTransform: 'uppercase', mb: 1, display: 'block' }}>Filename</Typography>
                            <Typography variant="body1">{selectedImport.filename}</Typography>
                        </Box>

                        <Box sx={{ mb: 3 }}>
                            <Typography variant="caption" color="text.secondary" fontWeight="bold" sx={{ textTransform: 'uppercase', mb: 1, display: 'block' }}>Status</Typography>
                            <Chip label={selectedImport.status} color="warning" size="small" />
                        </Box>

                        <Typography variant="caption" color="text.secondary" fontWeight="bold" sx={{ textTransform: 'uppercase', mb: 1, display: 'block' }}>Match Metadata</Typography>
                        <Paper variant="outlined" sx={{ p: 2, mb: 3, bgcolor: 'rgba(0,0,0,0.2)', border: '1px solid', borderColor: 'divider' }}>
                            <pre style={{ margin: 0, fontSize: 11, overflow: 'auto', color: '#64B5F6' }}>
                                {JSON.stringify(selectedImport.import_metadata, null, 2)}
                            </pre>
                        </Paper>

                        {selectedImport.raw_payload && (
                            <>
                                <Typography variant="caption" color="text.secondary" fontWeight="bold" sx={{ textTransform: 'uppercase', mb: 1, display: 'block' }}>Raw Payload (Sample)</Typography>
                                <Paper variant="outlined" sx={{ p: 2, mb: 3, bgcolor: 'rgba(255,255,255,0.02)', border: '1px solid', borderColor: 'divider' }}>
                                    <Typography sx={{ fontFamily: 'monospace', fontSize: 11, whiteSpace: 'pre-wrap', color: 'text.secondary' }}>
                                        {selectedImport.raw_payload}
                                    </Typography>
                                </Paper>
                            </>
                        )}

                        <Box sx={{ mt: 6 }}>
                            <Button
                                variant="contained"
                                color="primary"
                                startIcon={<RefreshCw size={18} />}
                                onClick={() => handleReprocess(selectedImport.id)}
                                fullWidth
                                disabled={selectedImport.status === 'PENDING'}
                                sx={{ py: 1.5, fontWeight: 'bold' }}
                            >
                                Force Reprocess
                            </Button>
                            <Typography variant="caption" color="text.disabled" sx={{ mt: 1, textAlign: 'center', display: 'block' }}>
                                This will purge existing events and reset the import for the worker.
                            </Typography>
                        </Box>
                    </Box>
                )}
            </Drawer>
        </Layout>
    );
}
