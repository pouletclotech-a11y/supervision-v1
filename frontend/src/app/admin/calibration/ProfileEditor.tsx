'use client';

import React, { useState, useEffect } from 'react';
import {
    Box,
    Typography,
    Button,
    Paper,
    Divider,
    IconButton,
    TextField,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    CircularProgress,
    Chip,
    Alert
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { Edit3, Play, Plus, Save, Trash2, Upload } from 'lucide-react';
import { fetchWithAuth } from '../../../lib/api';

export default function ProfileEditor() {
    const [profiles, setProfiles] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [selectedProfile, setSelectedProfile] = useState<any | null>(null);
    const [editJson, setEditJson] = useState('');
    const [editOpen, setEditOpen] = useState(false);
    const [saving, setSaving] = useState(false);

    // Sandbox
    const [sandboxFile, setSandboxFile] = useState<File | null>(null);
    const [sandboxResult, setSandboxResult] = useState<any | null>(null);
    const [simulating, setSimulating] = useState(false);

    const fetchProfiles = async () => {
        setLoading(true);
        try {
            const res = await fetchWithAuth('/admin/profiles');
            if (res.ok) {
                const data = await res.json();
                setProfiles(data);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchProfiles();
    }, []);

    const handleEdit = (profile: any) => {
        setSelectedProfile(profile);
        // Clean technical fields for display
        const displayData = { ...profile };
        delete displayData.id;
        delete displayData.created_at;
        delete displayData.updated_at;

        setEditJson(JSON.stringify(displayData, null, 2));
        setEditOpen(true);
    };

    const handleSave = async () => {
        if (!selectedProfile) return;
        setSaving(true);
        try {
            const body = JSON.parse(editJson);
            const res = await fetchWithAuth(`/admin/profiles/${selectedProfile.id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            if (res.ok) {
                setEditOpen(false);
                fetchProfiles();
            } else {
                const err = await res.json();
                alert(`Error: ${JSON.stringify(err.detail) || 'Failed to save'}`);
            }
        } catch (err) {
            alert("Invalid JSON format");
        } finally {
            setSaving(false);
        }
    };

    const handleSandbox = async () => {
        if (!sandboxFile) return;
        setSimulating(true);
        setSandboxResult(null);
        try {
            const formData = new FormData();
            formData.append('file', sandboxFile);

            const res = await fetchWithAuth('/admin/sandbox/ingest', {
                method: 'POST',
                body: formData
            });
            if (res.ok) {
                const data = await res.json();
                setSandboxResult(data);
            } else {
                alert("Simulation failed on server.");
            }
        } catch (err) {
            console.error(err);
            alert("Network error during simulation.");
        } finally {
            setSimulating(false);
        }
    };

    const columns: GridColDef[] = [
        { field: 'profile_id', headerName: 'Profile ID', width: 180 },
        { field: 'name', headerName: 'Label', width: 250, flex: 1 },
        { field: 'priority', headerName: 'Prio', width: 80, align: 'center' },
        { field: 'version_number', headerName: 'V', width: 60, align: 'center' },
        {
            field: 'is_active', headerName: 'Active', width: 100,
            renderCell: (params: GridRenderCellParams) => (
                <Chip
                    label={params.value ? 'Active' : 'Disabled'}
                    color={params.value ? 'success' : 'default'}
                    size="small"
                    sx={{ fontWeight: 'bold' as any }}
                />
            )
        },
        {
            field: 'actions', headerName: 'Edit', width: 80, align: 'right',
            renderCell: (params: GridRenderCellParams) => (
                <IconButton size="small" color="primary" onClick={() => handleEdit(params.row)}>
                    <Edit3 size={16} />
                </IconButton>
            )
        }
    ];

    return (
        <Box sx={{ height: '100%', display: 'flex', gap: 3 }}>
            {/* LEFT: PROFILE LIST */}
            <Paper variant="outlined" sx={{ flex: 1, p: 0, display: 'flex', flexDirection: 'column', bgcolor: 'background.paper', borderRadius: 2 }}>
                <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', bgcolor: 'rgba(255,255,255,0.02)', borderBottom: 1, borderColor: 'divider' }}>
                    <Typography variant="subtitle1" fontWeight="bold">Ingestion Profiles (DB)</Typography>
                    <Button startIcon={<Plus size={18} />} size="small" variant="contained" disabled>Create</Button>
                </Box>
                <DataGrid
                    rows={profiles}
                    columns={columns}
                    loading={loading}
                    disableRowSelectionOnClick
                    density="compact"
                    sx={{ border: 0 }}
                />
            </Paper>

            {/* RIGHT: SANDBOX */}
            <Paper variant="outlined" sx={{ width: 400, p: 3, display: 'flex', flexDirection: 'column', gap: 2, bgcolor: 'background.paper', borderRadius: 2, borderLeft: '4px solid', borderLeftColor: 'success.main' }}>
                <Typography variant="subtitle1" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Play size={20} color="#4caf50" /> Sandbox Ingestion
                </Typography>
                <Typography variant="caption" color="text.secondary">
                    Test a file against current database profiles. High isolation (no writes).
                </Typography>

                <Box sx={{
                    mt: 2,
                    p: 3,
                    border: '2px dashed',
                    borderColor: sandboxFile ? 'success.main' : 'divider',
                    borderRadius: 2,
                    textAlign: 'center',
                    bgcolor: sandboxFile ? 'rgba(76, 175, 80, 0.05)' : 'transparent',
                    transition: 'all 0.2s'
                }}>
                    <input
                        type="file"
                        id="sandbox-file"
                        hidden
                        onChange={(e) => setSandboxFile(e.target.files?.[0] || null)}
                    />
                    <label htmlFor="sandbox-file">
                        <Button component="span" startIcon={<Upload size={18} />} sx={{ mb: 1, textTransform: 'none' }}>
                            {sandboxFile ? 'Change File' : 'Drop file here or browse'}
                        </Button>
                    </label>
                    {sandboxFile && (
                        <Typography variant="body2" sx={{ fontWeight: 500, color: 'success.main' }}>
                            {sandboxFile.name}
                        </Typography>
                    )}
                </Box>

                <Button
                    variant="contained"
                    color="success"
                    fullWidth
                    disabled={!sandboxFile || simulating}
                    onClick={handleSandbox}
                    startIcon={simulating ? <CircularProgress size={18} color="inherit" /> : <Play size={18} />}
                    sx={{ py: 1.5, fontWeight: 'bold' }}
                >
                    {simulating ? 'Simulating...' : 'Run Simulation'}
                </Button>

                {sandboxResult && (
                    <Box sx={{ mt: 2 }}>
                        <Typography variant="caption" color="text.secondary" fontWeight="bold" gutterBottom display="block" sx={{ textTransform: 'uppercase' }}>Simulation Result</Typography>
                        <Alert icon={false} severity={sandboxResult.is_matched ? "success" : "warning"} sx={{ bgcolor: 'rgba(0,0,0,0.2)', border: '1px solid', borderColor: sandboxResult.is_matched ? 'success.dark' : 'warning.dark' }}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                <Typography variant="body2" fontWeight="bold" sx={{ color: sandboxResult.is_matched ? 'success.main' : 'warning.main' }}>
                                    {sandboxResult.is_matched ? "MATCH DETECTED" : "REJECTED (LOW CONFIDENCE)"}
                                </Typography>
                                <Divider sx={{ my: 0.5, borderColor: 'rgba(255,255,255,0.1)' }} />
                                <Typography variant="caption" sx={{ color: 'text.primary' }}>
                                    <strong>Profile:</strong> {sandboxResult.matched_profile_id || "NoneMatched"}
                                </Typography>
                                <Typography variant="caption" sx={{ color: 'text.primary' }}>
                                    <strong>Score:</strong> {sandboxResult.best_score.toFixed(2)} / {sandboxResult.threshold}
                                </Typography>
                                <Typography variant="caption" sx={{ color: 'text.primary' }}>
                                    <strong>Total Events:</strong> {sandboxResult.total_events}
                                </Typography>
                            </Box>
                        </Alert>
                    </Box>
                )}
            </Paper>

            {/* EDIT DIALOG */}
            <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="md" fullWidth PaperProps={{ sx: { bgcolor: 'background.paper' } }}>
                <DialogTitle sx={{ borderBottom: 1, borderColor: 'divider', fontWeight: 'bold' }}>
                    Edit Profile: {selectedProfile?.profile_id}
                </DialogTitle>
                <DialogContent sx={{ pt: 3 }}>
                    <Typography variant="caption" color="warning.main" sx={{ mb: 2, display: 'block' }}>
                        Warning: Direct JSON editing is powerful. Ensure all required fields (detection, mapping) are valid.
                    </Typography>
                    <TextField
                        multiline
                        fullWidth
                        rows={18}
                        value={editJson}
                        onChange={(e) => setEditJson(e.target.value)}
                        variant="outlined"
                        sx={{
                            mt: 1,
                            '& .MuiInputBase-root': {
                                fontFamily: 'monospace',
                                fontSize: 12,
                                bgcolor: 'rgba(0,0,0,0.2)'
                            }
                        }}
                    />
                </DialogContent>
                <DialogActions sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
                    <Button onClick={() => setEditOpen(false)} sx={{ color: 'text.secondary' }}>Cancel</Button>
                    <Button
                        onClick={handleSave}
                        variant="contained"
                        color="primary"
                        disabled={saving}
                        startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <Save size={16} />}
                        sx={{ fontWeight: 'bold' }}
                    >
                        Save Version {selectedProfile ? (selectedProfile.version_number + 1) : 1}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}

