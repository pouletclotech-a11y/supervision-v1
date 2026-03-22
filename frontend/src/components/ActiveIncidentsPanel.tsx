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
    Stack,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Tooltip
} from '@mui/material';
import { RefreshCw, ShieldAlert, Clock, AlertTriangle, CheckCircle, MessageSquare, User } from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';
import { format, formatDistanceToNow } from 'date-fns';
import { fr } from 'date-fns/locale';

export default function ActiveIncidentsPanel() {
    const [incidents, setIncidents] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Ack Dialog State
    const [ackDialogOpen, setAckDialogOpen] = useState(false);
    const [ackComment, setAckComment] = useState('');
    const [selectedIncident, setSelectedIncident] = useState<any | null>(null);
    const [ackSubmitting, setAckSubmitting] = useState(false);

    const fetchIncidents = async () => {
        setLoading(true);
        try {
            const res = await fetchWithAuth('/alerts/incidents?status=OPEN');
            if (res.ok) {
                const json = await res.json();
                setIncidents(json);
                setError(null);
            } else {
                setError('Impossible de charger les alertes en cours.');
            }
        } catch (err) {
            console.error("Incidents API Error:", err);
            setError('Erreur de connexion aux incidents.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchIncidents();
        const timer = setInterval(fetchIncidents, 60000);
        return () => clearInterval(timer);
    }, []);

    const handleOpenAckDialog = (incident: any) => {
        setSelectedIncident(incident);
        setAckComment('');
        setAckDialogOpen(true);
    };

    const handleCloseAckDialog = () => {
        setAckDialogOpen(false);
        setSelectedIncident(null);
        setAckComment('');
    };

    const handleConfirmAck = async () => {
        if (!selectedIncident || !ackComment.trim()) return;

        setAckSubmitting(true);
        try {
            const res = await fetchWithAuth(`/alerts/incidents/${selectedIncident.id}/ack`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ comment: ackComment })
            });

            if (res.ok) {
                // Refresh local state or re-fetch
                await fetchIncidents();
                handleCloseAckDialog();
            } else {
                const errJson = await res.json();
                alert(errJson.detail || "Erreur lors de l'acquittement.");
            }
        } catch (err) {
            console.error("Ack Error:", err);
            alert("Erreur de connexion.");
        } finally {
            setAckSubmitting(false);
        }
    };

    return (
        <Paper sx={{ p: 3, borderRadius: 4, border: '1px solid', borderColor: 'divider', height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Box sx={{ p: 1, borderRadius: 2, bgcolor: 'error.main', color: 'white', display: 'flex' }}>
                        <AlertTriangle size={20} />
                    </Box>
                    <Box>
                        <Typography variant="h6" fontWeight={700}>Alertes Persistantes (Ouvertes)</Typography>
                        <Typography variant="caption" color="text.secondary">
                            Incidents en cours de résolution (Apparition sans Disparition)
                        </Typography>
                    </Box>
                </Box>
                <IconButton size="small" onClick={fetchIncidents} disabled={loading}>
                    <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                </IconButton>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            <TableContainer sx={{ flexGrow: 1, overflow: 'auto' }}>
                <Table size="small" stickyHeader>
                    <TableHead>
                        <TableRow>
                            <TableCell sx={{ fontWeight: 700 }}>Début</TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>Site</TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>Description / Label</TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>Ancienneté</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 700 }}>Statut / Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {loading && incidents.length === 0 ? (
                            <TableRow><TableCell colSpan={5} align="center" sx={{ py: 8 }}><CircularProgress size={24} /></TableCell></TableRow>
                        ) : incidents.length === 0 ? (
                            <TableRow><TableCell colSpan={5} align="center" sx={{ py: 8 }}>
                                <Typography variant="body2" color="text.secondary">Aucune alerte persistante détectée.</Typography>
                            </TableCell></TableRow>
                        ) : (
                            incidents.map((row) => (
                                <TableRow key={row.id} hover>
                                    <TableCell sx={{ fontSize: '0.75rem' }}>
                                        <Typography variant="inherit" suppressHydrationWarning>
                                            {format(new Date(row.opened_at), 'dd/MM HH:mm:ss')}
                                        </Typography>
                                    </TableCell>
                                    <TableCell sx={{ fontWeight: 700, color: 'primary.main' }}>
                                        {row.site_code}
                                    </TableCell>
                                    <TableCell sx={{ maxWidth: 300 }}>
                                        <Typography variant="body2" sx={{ fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                            {row.label}
                                        </Typography>
                                        {row.acknowledged_at && (
                                            <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.5 }}>
                                                <Tooltip title={`Par: ${row.acknowledged_by} le ${format(new Date(row.acknowledged_at), 'dd/MM HH:mm')}`}>
                                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'success.main', fontSize: '0.7rem' }}>
                                                        <CheckCircle size={10} /> Acquitté
                                                    </Box>
                                                </Tooltip>
                                                {row.ack_comment && (
                                                    <Tooltip title={row.ack_comment}>
                                                        <Box sx={{ display: 'flex', alignItems: 'center', color: 'text.secondary', fontSize: '0.7rem' }}>
                                                            <MessageSquare size={10} style={{ marginRight: 2 }} /> Note
                                                        </Box>
                                                    </Tooltip>
                                                )}
                                            </Stack>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant="caption" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                            <Clock size={12} /> {formatDistanceToNow(new Date(row.opened_at), { addSuffix: false, locale: fr })}
                                        </Typography>
                                    </TableCell>
                                    <TableCell align="center">
                                        <Stack direction="row" spacing={1} justifyContent="center" alignItems="center">
                                            <Chip 
                                                label={row.acknowledged_at ? "ACQUITTÉ" : "OUVERT"} 
                                                size="small" 
                                                color={row.acknowledged_at ? "success" : "error"} 
                                                variant={row.acknowledged_at ? "outlined" : "filled"}
                                                sx={{ height: 18, fontSize: 10, fontWeight: 700 }} 
                                            />
                                            {!row.acknowledged_at && (
                                                <Button 
                                                    variant="contained" 
                                                    size="small" 
                                                    disableElevation
                                                    sx={{ fontSize: 9, py: 0, px: 1, minWidth: 0, height: 20 }}
                                                    onClick={() => handleOpenAckDialog(row)}
                                                >
                                                    Acquitter
                                                </Button>
                                            )}
                                        </Stack>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>

            {/* Acknowledgment Dialog */}
            <Dialog open={ackDialogOpen} onClose={handleCloseAckDialog} fullWidth maxWidth="xs">
                <DialogTitle sx={{ fontWeight: 700, fontSize: '1.1rem' }}>Acquittement de l'incident</DialogTitle>
                <DialogContent>
                    <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
                        Veuillez saisir un justificatif pour marquer cet incident comme traité. Cette action sera tracée au nom de votre compte.
                    </Typography>
                    <TextField
                        autoFocus
                        label="Justificatif (Mandatoire)"
                        multiline
                        rows={3}
                        fullWidth
                        variant="outlined"
                        value={ackComment}
                        onChange={(e) => setAckComment(e.target.value)}
                        error={!ackComment.trim() && ackComment.length > 0}
                        helperText={!ackComment.trim() ? "Le commentaire est obligatoire." : ""}
                    />
                </DialogContent>
                <DialogActions sx={{ p: 2, pt: 1 }}>
                    <Button onClick={handleCloseAckDialog} color="inherit">Annuler</Button>
                    <Button 
                        onClick={handleConfirmAck} 
                        variant="contained" 
                        color="success" 
                        disabled={!ackComment.trim() || ackSubmitting}
                        startIcon={ackSubmitting ? <CircularProgress size={16} /> : <CheckCircle size={16} />}
                    >
                        Confirmer l'Acquittement
                    </Button>
                </DialogActions>
            </Dialog>
        </Paper>
    );
}
