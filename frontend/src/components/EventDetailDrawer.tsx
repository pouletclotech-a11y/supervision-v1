'use client';

import React, { useState, useEffect } from 'react';
import {
    Box,
    Drawer,
    Typography,
    IconButton,
    Paper,
    Divider,
    Chip,
    Button,
    CircularProgress,
    Stack,
    Grid
} from '@mui/material';
import { X, ExternalLink, ShieldAlert, FileText, User, Clock } from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';
import { format } from 'date-fns';
import Link from 'next/link';

interface EventDetailDrawerProps {
    eventId: number | null;
    open: boolean;
    onClose: () => void;
}

export default function EventDetailDrawer({ eventId, open, onClose }: EventDetailDrawerProps) {
    const [loading, setLoading] = useState(false);
    const [event, setEvent] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (open && eventId) {
            fetchEventDetails();
        }
    }, [open, eventId]);

    const fetchEventDetails = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetchWithAuth(`/events/${eventId}`);
            if (!res.ok) throw new Error('Failed to fetch event details');
            const json = await res.json();
            setEvent(json);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Drawer
            anchor="right"
            open={open}
            onClose={onClose}
            sx={{ '& .MuiDrawer-paper': { width: { xs: '100%', sm: 500 }, bgcolor: 'background.default' } }}
        >
            {/* HEADER */}
            <Box sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'background.paper' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Box sx={{ p: 1, borderRadius: 2, bgcolor: 'error.main', color: '#fff' }}>
                        <ShieldAlert size={20} />
                    </Box>
                    <Box>
                        <Typography variant="h6" fontWeight={700}>Event Details</Typography>
                        <Typography variant="caption" color="text.secondary">ID: #{eventId}</Typography>
                    </Box>
                </Box>
                <IconButton onClick={onClose}><X size={20} /></IconButton>
            </Box>

            {!eventId ? (
                <Box sx={{ p: 4, textAlign: 'center' }}><Typography color="text.secondary">No event selected.</Typography></Box>
            ) : loading ? (
                <Box sx={{ p: 8, textAlign: 'center' }}>
                    <CircularProgress size={40} />
                    <Typography sx={{ mt: 2 }} color="text.secondary">Fetching details...</Typography>
                </Box>
            ) : error ? (
                <Box sx={{ p: 4 }}><Typography color="error">{error}</Typography></Box>
            ) : event && (
                <Box sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 3, overflowY: 'auto' }}>

                    {/* INFO BOX */}
                    <Paper sx={{ p: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
                        <Stack spacing={2}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                <Typography variant="caption" color="text.secondary">Site Code</Typography>
                                <Typography variant="body2" fontWeight={600} sx={{ color: 'primary.main' }}>{event.site_code}</Typography>
                            </Box>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                <Typography variant="caption" color="text.secondary">Occurred At</Typography>
                                <Typography variant="body2">{format(new Date(event.created_at), 'dd/MM/yyyy HH:mm:ss')}</Typography>
                            </Box>
                            {event.score !== null && (
                                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <Typography variant="caption" color="text.secondary">Confidence Score</Typography>
                                    <Chip label={event.score.toFixed(2)} size="small" color="primary" />
                                </Box>
                            )}
                        </Stack>
                    </Paper>

                    {/* ACTIONS */}
                    <Box sx={{ display: 'flex', gap: 2 }}>
                        <Button
                            component={Link}
                            href={`/client/${event.site_code}`}
                            variant="outlined"
                            fullWidth
                            size="small"
                            startIcon={<User size={16} />}
                        >
                            Voir Site
                        </Button>
                        <Button
                            component={Link}
                            href={`/admin/imports/${event.import_id}`}
                            variant="outlined"
                            fullWidth
                            size="small"
                            startIcon={<FileText size={16} />}
                        >
                            Voir Import
                        </Button>
                    </Box>

                    {/* MESSAGES */}
                    <Box>
                        <Typography variant="subtitle2" gutterBottom color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Clock size={16} /> Raw Message
                        </Typography>
                        <Paper sx={{ p: 2, bgcolor: 'rgba(255,255,255,0.03)', fontFamily: 'monospace', fontSize: '0.85rem', wordBreak: 'break-all' }}>
                            {event.message}
                        </Paper>
                    </Box>

                    {event.normalized_message && (
                        <Box>
                            <Typography variant="subtitle2" gutterBottom color="text.secondary">Normalized Message</Typography>
                            <Typography variant="body2" sx={{ bgcolor: 'rgba(0,0,0,0.1)', p: 1.5, borderRadius: 1 }}>
                                {event.normalized_message}
                            </Typography>
                        </Box>
                    )}

                    {/* METADATA */}
                    <Box>
                        <Typography variant="subtitle2" gutterBottom color="text.secondary">Technical Details</Typography>
                        <Grid container spacing={1}>
                            <Grid item xs={6}>
                                <Typography variant="caption" display="block" color="text.secondary">Raw site code</Typography>
                                <Typography variant="body2">{event.site_code_raw || '-'}</Typography>
                            </Grid>
                            <Grid item xs={6}>
                                <Typography variant="caption" display="block" color="text.secondary">Raw Code</Typography>
                                <Typography variant="body2">{event.raw_code || '-'}</Typography>
                            </Grid>
                            <Grid item xs={6}>
                                <Typography variant="caption" display="block" color="text.secondary">Duplicate Count</Typography>
                                <Typography variant="body2">{event.dup_count}</Typography>
                            </Grid>
                            <Grid item xs={6}>
                                <Typography variant="caption" display="block" color="text.secondary">Import ID</Typography>
                                <Typography variant="body2">#{event.import_id}</Typography>
                            </Grid>
                        </Grid>
                    </Box>

                </Box>
            )}
        </Drawer>
    );
}
