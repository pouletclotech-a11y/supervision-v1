'use client';

import React, { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    MenuItem,
    IconButton,
    Chip,
    Alert,
    CircularProgress,
    Avatar
} from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { Users, UserPlus, Edit2, Trash2, Shield, Camera } from 'lucide-react';
import Layout from '../../../components/Layout';
import { fetchWithAuth } from '../../../lib/api';
import { useAuth } from '@/context/AuthContext';

interface User {
    id: number;
    email: string;
    full_name: string | null;
    role: string;
    is_active: boolean;
    profile_photo: string | null;
    created_at: string;
}

export default function UsersPage() {
    const { user: currentUser, checkAuth } = useAuth();
    const [users, setUsers] = React.useState<User[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

    // Dialog State
    const [openDialog, setOpenDialog] = useState(false);
    const [editingUser, setEditingUser] = useState<User | null>(null);
    const [formData, setFormData] = useState({
        email: '',
        password: '',
        full_name: '',
        role: 'VIEWER',
        is_active: true,
        profile_photo: ''
    });

    const fileInputRef = React.useRef<HTMLInputElement>(null);

    const fetchUsers = async () => {
        setLoading(true);
        try {
            const res = await fetchWithAuth('/users/');
            if (res.ok) {
                const data = await res.json();
                setUsers(data);
            } else {
                setError("Failed to load users. RBAC Restricted?");
            }
        } catch (err) {
            setError("Network error.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    const handleOpenCreate = () => {
        setEditingUser(null);
        setFormData({ email: '', password: '', full_name: '', role: 'VIEWER', is_active: true, profile_photo: '' });
        setOpenDialog(true);
    };

    const handleOpenEdit = (user: User) => {
        setEditingUser(user);
        setFormData({
            email: user.email,
            password: '', // Leave empty for passwords
            full_name: user.full_name || '',
            role: user.role,
            is_active: user.is_active,
            profile_photo: user.profile_photo || ''
        });
        setOpenDialog(true);
    };

    const handleSave = async () => {
        const url = editingUser ? `/users/${editingUser.id}` : '/users/';
        const method = editingUser ? 'PATCH' : 'POST';

        // Clean data for PATCH
        const payload = { ...formData };
        if (editingUser && !payload.password) delete (payload as any).password;
        if (editingUser) delete (payload as any).email; // Email is unique/fixed usually

        try {
            const res = await fetchWithAuth(url, {
                method,
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                setMessage({ type: 'success', text: editingUser ? "User updated" : "User created" });
                setOpenDialog(false);
                fetchUsers();
            } else {
                const err = await res.json();
                setMessage({ type: 'error', text: err.detail || "Error saving user" });
            }
        } catch (err) {
            setMessage({ type: 'error', text: "Network error" });
        }
    };

    const handleToggleStatus = async (user: User) => {
        try {
            const res = await fetchWithAuth(`/users/${user.id}`, {
                method: 'PATCH',
                body: JSON.stringify({ is_active: !user.is_active })
            });
            if (res.ok) fetchUsers();
        } catch (err) {
            console.error(err);
        }
    };

    const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.[0] || !editingUser) return;

        const file = e.target.files[0];
        const data = new FormData();
        data.append('file', file);

        try {
            const res = await fetchWithAuth(`/users/${editingUser.id}/photo`, {
                method: 'POST',
                body: data,
            });

            if (res.ok) {
                const updatedUser = await res.json();
                setFormData(prev => ({ ...prev, profile_photo: updatedUser.profile_photo }));
                fetchUsers(); // Refresh user list to show updated photo

                // Refresh global auth context if editing self
                if (editingUser.id === currentUser?.id) {
                    checkAuth();
                }
            } else {
                const error = await res.json();
                alert(`Upload failed: ${error.detail || 'Unknown error'}`);
            }
        } catch (err) {
            console.error("Photo upload error", err);
            alert("Network error during photo upload.");
        }
    };

    const columns: GridColDef[] = [
        {
            field: 'avatar', headerName: '', width: 50, sortable: false,
            renderCell: (params) => (
                <Avatar
                    src={params.row.profile_photo ? (params.row.profile_photo.startsWith('http') ? params.row.profile_photo : `${(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace('/api/v1', '')}${params.row.profile_photo}`) : undefined}
                    sx={{ width: 32, height: 32, fontSize: 12, bgcolor: 'primary.main' }}
                >
                    {params.row.full_name?.[0] || params.row.email[0].toUpperCase()}
                </Avatar>
            )
        },
        { field: 'id', headerName: 'ID', width: 60 },
        { field: 'email', headerName: 'Email', flex: 1 },
        { field: 'full_name', headerName: 'Name', flex: 1 },
        {
            field: 'role', headerName: 'Role', width: 120,
            renderCell: (params) => (
                <Chip
                    icon={<Shield size={14} />}
                    label={params.value}
                    color={params.value === 'ADMIN' ? 'error' : params.value === 'OPERATOR' ? 'primary' : 'default'}
                    size="small"
                />
            )
        },
        {
            field: 'is_active', headerName: 'Status', width: 100,
            renderCell: (params) => (
                <Chip
                    label={params.value ? 'Active' : 'Inactive'}
                    color={params.value ? 'success' : 'warning'}
                    variant="outlined"
                    size="small"
                />
            )
        },
        {
            field: 'actions', headerName: 'Actions', width: 150, align: 'right',
            renderCell: (params) => (
                <Box>
                    <IconButton size="small" onClick={() => handleOpenEdit(params.row)}><Edit2 size={16} /></IconButton>
                    <IconButton
                        size="small"
                        color={params.row.is_active ? 'warning' : 'success'}
                        onClick={() => handleToggleStatus(params.row)}
                    >
                        <Trash2 size={16} />
                    </IconButton>
                </Box>
            )
        }
    ];

    return (
        <Layout>
            <Box sx={{ p: 4 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                    <Box>
                        <Typography variant="h4" sx={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Users /> User Management
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Admin only: Control access and permissions.
                        </Typography>
                    </Box>
                    <Button variant="contained" startIcon={<UserPlus size={18} />} onClick={handleOpenCreate}>
                        Add User
                    </Button>
                </Box>

                {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}
                {message && (
                    <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage(null)}>
                        {message.text}
                    </Alert>
                )}

                <Paper sx={{ height: 600, width: '100%', bgcolor: 'background.paper' }}>
                    <DataGrid
                        rows={users}
                        columns={columns}
                        loading={loading}
                        disableRowSelectionOnClick
                        density="comfortable"
                    />
                </Paper>

                {/* CREATE/EDIT DIALOG */}
                <Dialog open={openDialog} onClose={() => setOpenDialog(false)}>
                    <DialogTitle>{editingUser ? 'Edit User' : 'New User'}</DialogTitle>
                    <DialogContent sx={{ pt: 1, display: 'flex', flexDirection: 'column', gap: 2, minWidth: 400 }}>
                        <TextField
                            label="Email" fullWidth disabled={!!editingUser}
                            value={formData.email} onChange={e => setFormData({ ...formData, email: e.target.value })}
                        />
                        <TextField
                            label="Password" type="password" fullWidth
                            placeholder={editingUser ? '(Hold to keep same)' : ''}
                            value={formData.password} onChange={e => setFormData({ ...formData, password: e.target.value })}
                        />
                        <TextField
                            label="Full Name" fullWidth
                            value={formData.full_name} onChange={e => setFormData({ ...formData, full_name: e.target.value })}
                        />
                        <TextField
                            select label="Role" fullWidth
                            value={formData.role} onChange={e => setFormData({ ...formData, role: e.target.value })}
                        >
                            <MenuItem value="ADMIN">ADMIN</MenuItem>
                            <MenuItem value="OPERATOR">OPERATOR</MenuItem>
                            <MenuItem value="VIEWER">VIEWER</MenuItem>
                        </TextField>
                        <TextField
                            label="URL Photo de profil" fullWidth
                            placeholder="https://example.com/photo.jpg"
                            value={formData.profile_photo || ''} onChange={e => setFormData({ ...formData, profile_photo: e.target.value })}
                        />
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 1 }}>
                            <Button
                                variant="outlined"
                                startIcon={<Camera size={18} />}
                                onClick={() => fileInputRef.current?.click()}
                                size="small"
                            >
                                Upload Photo
                            </Button>
                            <input
                                type="file"
                                hidden
                                ref={fileInputRef}
                                onChange={handlePhotoUpload}
                                accept="image/png, image/jpeg"
                            />
                            {formData.profile_photo && (
                                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                    Photo chargée
                                </Typography>
                            )}
                        </Box>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
                        <Button variant="contained" onClick={handleSave}>Save</Button>
                    </DialogActions>
                </Dialog>
            </Box>
        </Layout>
    );
}
