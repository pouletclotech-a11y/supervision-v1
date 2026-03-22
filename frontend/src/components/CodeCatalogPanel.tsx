'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
    Box,
    Paper,
    Typography,
    TextField,
    InputAdornment,
    CircularProgress,
    Alert,
    IconButton,
    Chip,
    useTheme,
    TableSortLabel,
    Drawer,
    List,
    ListItem,
    ListItemText,
    Divider,
    FormControl,
    Select,
    MenuItem,
    InputLabel,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    Stack,
    TableContainer,
    Table,
    TableBody,
    TableHead,
    TableRow,
    TableCell,
    TablePagination,
    Slider
} from '@mui/material';
import { Search, RefreshCw, BookOpen, Clock, Hash, Activity, Filter, Layers, List as ListIcon, Info, ChevronRight, CheckCircle } from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';
import { format } from 'date-fns';

interface CodeCatalogPanelProps {
    onSelectCode?: (item: any) => void;
}

export default function CodeCatalogPanel({ onSelectCode }: CodeCatalogPanelProps = {}) {
    const theme = useTheme();
    const [items, setItems] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    // FILTERS
    const [searchTerm, setSearchTerm] = useState('');
    const [codeFilter, setCodeFilter] = useState('');
    const [providerStatus, setProviderStatus] = useState('active');
    const [mode, setMode] = useState('COMPACT');
    const [invariance, setInvariance] = useState(1.0);
    
    // SORTING
    const [sortBy, setSortBy] = useState('occurrences');
    const [sortDir, setSortDir] = useState('desc');
    
    // PAGINATION
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(100);
    const [total, setTotal] = useState(0);

    // DRILLDOWN
    const [selectedCode, setSelectedCode] = useState<string | null>(null);
    const [variants, setVariants] = useState<any[]>([]);
    const [loadingVariants, setLoadingVariants] = useState(false);

    // DEBOUNCE LOGIC
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [debouncedCode, setDebouncedCode] = useState('');

    useEffect(() => {
        const timer = setTimeout(() => setDebouncedSearch(searchTerm), 500);
        return () => clearTimeout(timer);
    }, [searchTerm]);

    useEffect(() => {
        const timer = setTimeout(() => setDebouncedCode(codeFilter), 500);
        return () => clearTimeout(timer);
    }, [codeFilter]);

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            let url = `/health/catalog?skip=${page * rowsPerPage}&limit=${rowsPerPage}`;
            url += `&mode=${mode}`;
            url += `&provider_status=${providerStatus}`;
            url += `&sort_by=${sortBy}`;
            url += `&sort_dir=${sortDir}`;
            url += `&invariance=${invariance}`;
            
            if (debouncedSearch) url += `&q=${encodeURIComponent(debouncedSearch)}`;
            if (debouncedCode) url += `&code=${encodeURIComponent(debouncedCode)}`;
            
            const res = await fetchWithAuth(url);
            if (res.ok) {
                const json = await res.json();
                setItems(json.items || []);
                setTotal(json.total || 0);
                setError(null);
            } else {
                setError('Impossible de charger l\'annuaire des codes.');
            }
        } catch (err) {
            console.error("Catalog API Error:", err);
            setError('Erreur réseau lors de la communication avec l\'API.');
        } finally {
            setLoading(false);
        }
    }, [page, rowsPerPage, debouncedSearch, debouncedCode, mode, providerStatus, sortBy, sortDir, invariance]);

    const fetchVariants = async (code: string) => {
        setSelectedCode(code);
        setLoadingVariants(true);
        try {
            const res = await fetchWithAuth(`/health/catalog/variants/${code}`);
            if (res.ok) {
                const json = await res.json();
                setVariants(json.variants || []);
            }
        } catch (err) {
            console.error("Fetch variants error:", err);
        } finally {
            setLoadingVariants(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const handleChangePage = (event: unknown, newPage: number) => {
        setPage(newPage);
    };

    const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
        setRowsPerPage(parseInt(event.target.value, 10));
        setPage(0);
    };

    // Reset page when filters change
    useEffect(() => {
        setPage(0);
    }, [debouncedSearch, debouncedCode, mode, providerStatus]);

    const handleSort = (property: string) => {
        const isAsc = sortBy === property && sortDir === 'asc';
        setSortDir(isAsc ? 'desc' : 'asc');
        setSortBy(property);
    };

    return (
        <Paper 
            elevation={0} 
            sx={{ 
                p: 3, 
                borderRadius: 4, 
                border: '1px solid', 
                borderColor: 'divider',
                bgcolor: 'background.paper',
                display: 'flex',
                flexDirection: 'column',
                height: 'calc(100vh - 120px)',
                overflow: 'hidden'
            }}
        >
            {/* HEADER AREA */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                    <Box 
                        sx={{ 
                            p: 1.5, 
                            borderRadius: 3, 
                            background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.primary.dark})`,
                            color: 'white',
                            display: 'flex',
                            boxShadow: '0 4px 12px rgba(25, 127, 230, 0.3)'
                        }}
                    >
                        <BookOpen size={24} />
                    </Box>
                    <Box>
                        <Typography variant="h5" fontWeight={800} sx={{ letterSpacing: '-0.5px' }}>
                            Annuaire des Codes
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Référentiel global des événements, actions et messages par prestataire
                        </Typography>
                    </Box>
                </Box>
                <Box>
                    <Tooltip title="Rafraîchir les données">
                        <span>
                            <IconButton onClick={fetchData} disabled={loading} sx={{ border: '1px solid', borderColor: 'divider' }}>
                                <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                            </IconButton>
                        </span>
                    </Tooltip>
                </Box>
            </Box>

            {/* FILTERS AREA */}
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 3 }} alignItems="center">
                <TextField
                    placeholder="Code (ex: 710)"
                    variant="outlined"
                    size="small"
                    value={codeFilter}
                    onChange={(e) => setCodeFilter(e.target.value)}
                    sx={{ width: { xs: '100%', md: 150 } }}
                    InputProps={{
                        startAdornment: (
                            <InputAdornment position="start">
                                <Hash size={14} color={theme.palette.text.secondary} />
                            </InputAdornment>
                        ),
                    }}
                />
                <TextField
                    placeholder="Chercher un mot-clé (ex: intrusion)"
                    variant="outlined"
                    size="small"
                    fullWidth
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    InputProps={{
                        startAdornment: (
                            <InputAdornment position="start">
                                <Search size={14} color={theme.palette.text.secondary} />
                            </InputAdornment>
                        ),
                    }}
                />
                
                <ToggleButtonGroup
                    value={mode}
                    exclusive
                    onChange={(e, val) => val && setMode(val)}
                    size="small"
                    color="primary"
                >
                    <ToggleButton value="COMPACT" sx={{ px: 2 }}>
                        <Layers size={14} style={{ marginRight: 8 }} /> COMPACT
                    </ToggleButton>
                    <ToggleButton value="DETAILED" sx={{ px: 2 }}>
                        <ListIcon size={14} style={{ marginRight: 8 }} /> DÉTAILLÉ
                    </ToggleButton>
                </ToggleButtonGroup>

                <Box sx={{ minWidth: 200, px: 2, display: mode === 'COMPACT' ? 'block' : 'none' }}>
                    <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block', fontWeight: 600 }}>
                        Seuil d'invariance: {Math.round(invariance * 100)}%
                    </Typography>
                    <Slider
                        size="small"
                        value={invariance}
                        min={0.5}
                        max={1.0}
                        step={0.05}
                        onChange={(e, val) => setInvariance(val as number)}
                        valueLabelDisplay="auto"
                        valueLabelFormat={(v) => `${Math.round(v * 100)}%`}
                        sx={{ py: 1 }}
                    />
                </Box>
            </Stack>

            {error && <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>{error}</Alert>}

            {/* TABLE AREA */}
            <TableContainer sx={{ flexGrow: 1, overflow: 'auto', borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
                <Table stickyHeader size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell sx={{ fontWeight: 800, bgcolor: 'background.paper', width: '90px' }}>
                                <TableSortLabel
                                    active={sortBy === 'code'}
                                    direction={sortBy === 'code' ? sortDir as any : 'asc'}
                                    onClick={() => handleSort('code')}
                                >
                                    CODE
                                </TableSortLabel>
                            </TableCell>
                            <TableCell sx={{ fontWeight: 800, bgcolor: 'background.paper' }}>
                                {mode === 'COMPACT' ? 'LABEL CANONIQUE (VÉRITÉ)' : 'MESSAGE NORMALISÉ'}
                            </TableCell>
                            {mode === 'COMPACT' && (
                                <TableCell sx={{ fontWeight: 800, bgcolor: 'background.paper' }}>TOP MESSAGE (FRÉQUENT)</TableCell>
                            )}
                            <TableCell sx={{ fontWeight: 800, bgcolor: 'background.paper', width: '180px' }}>PRESTATAIRE(S)</TableCell>
                            <TableCell align="center" sx={{ fontWeight: 800, bgcolor: 'background.paper', width: '80px' }}>
                                <TableSortLabel
                                    active={sortBy === 'occurrences'}
                                    direction={sortBy === 'occurrences' ? sortDir as any : 'asc'}
                                    onClick={() => handleSort('occurrences')}
                                >
                                    OCC.
                                </TableSortLabel>
                            </TableCell>
                            {mode === 'COMPACT' && (
                                <TableCell align="center" sx={{ fontWeight: 800, bgcolor: 'background.paper', width: '80px' }}>
                                    <TableSortLabel
                                        active={sortBy === 'variant_count'}
                                        direction={sortBy === 'variant_count' ? sortDir as any : 'asc'}
                                        onClick={() => handleSort('variant_count')}
                                    >
                                        VAR.
                                    </TableSortLabel>
                                </TableCell>
                            )}
                            {mode === 'COMPACT' && (
                                <TableCell align="center" sx={{ fontWeight: 800, bgcolor: 'background.paper', width: '80px' }}>CONFIANCE</TableCell>
                            )}
                            <TableCell align="right" sx={{ fontWeight: 800, bgcolor: 'background.paper', width: '150px' }}>
                                <TableSortLabel
                                    active={sortBy === 'last_seen'}
                                    direction={sortBy === 'last_seen' ? sortDir as any : 'asc'}
                                    onClick={() => handleSort('last_seen')}
                                >
                                    DERNIÈRE VUE
                                </TableSortLabel>
                            </TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {loading && items.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={mode === 'COMPACT' ? 8 : 5} align="center" sx={{ py: 10 }}>
                                    <CircularProgress size={30} thickness={4} />
                                    <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>Analyse statistique en cours...</Typography>
                                </TableCell>
                            </TableRow>
                        ) : items.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={mode === 'COMPACT' ? 8 : 5} align="center" sx={{ py: 10 }}>
                                    <Typography variant="body1" color="text.secondary" fontWeight={500}>Aucun résultat correspond aux critères.</Typography>
                                </TableCell>
                            </TableRow>
                        ) : (
                            items.map((item, idx) => (
                                <TableRow 
                                    key={`${item.code}-${idx}`} 
                                    hover 
                                    onClick={() => mode === 'COMPACT' && fetchVariants(item.code)}
                                    sx={{ 
                                        opacity: loading ? 0.6 : 1,
                                        transition: 'opacity 0.2s',
                                        cursor: mode === 'COMPACT' ? 'pointer' : 'default',
                                        '&:last-child td, &:last-child th': { border: 0 } 
                                    }}
                                >
                                    <TableCell>
                                        <Typography variant="body2" fontWeight={700} sx={{ fontFamily: 'monospace', color: 'primary.main', bgcolor: theme.palette.mode === 'dark' ? 'rgba(25, 127, 230, 0.1)' : 'rgba(25, 127, 230, 0.05)', px: 0.8, py: 0.3, borderRadius: 1, display: 'inline-block' }}>
                                            {item.code || '-'}
                                        </Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant="body2" sx={{ fontWeight: 700, color: 'text.primary', display: 'flex', alignItems: 'center', gap: 1 }}>
                                            {item.canonical_label || item.top_message || `CODE ${item.code}` || <span style={{ opacity: 0.4, fontStyle: 'italic' }}>Message non disponible</span>}
                                            {mode === 'COMPACT' && <ChevronRight size={14} style={{ opacity: 0.3 }} />}
                                        </Typography>
                                        <Typography variant="caption" color="text.disabled">
                                            Catégorie: {item.category}
                                        </Typography>
                                    </TableCell>
                                    {mode === 'COMPACT' && (
                                        <TableCell>
                                            <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                                                {item.top_message}
                                            </Typography>
                                        </TableCell>
                                    )}
                                    <TableCell>
                                        <Stack direction="row" flexWrap="wrap" gap={0.5}>
                                            {(item.providers || '').split(', ').map((p: string) => p && (
                                                <Chip 
                                                    key={p} 
                                                    label={p} 
                                                    size="small" 
                                                    variant="outlined"
                                                    sx={{ 
                                                        height: 20, 
                                                        fontSize: '0.6rem', 
                                                        fontWeight: 700,
                                                        borderColor: 'divider',
                                                        bgcolor: 'background.default'
                                                    }} 
                                                />
                                            ))}
                                        </Stack>
                                    </TableCell>
                                    <TableCell align="center">
                                        <Typography variant="body2" fontWeight={700} color="text.secondary">
                                            {item.occurrences.toLocaleString()}
                                        </Typography>
                                    </TableCell>
                                    {mode === 'COMPACT' && (
                                        <TableCell align="center">
                                            <Typography variant="body2" fontWeight={600} color="primary">
                                                {item.variant_count}
                                            </Typography>
                                        </TableCell>
                                    )}
                                    {mode === 'COMPACT' && (
                                        <TableCell align="center">
                                            <Box sx={{ position: 'relative', display: 'inline-flex' }}>
                                                <CircularProgress 
                                                    variant="determinate" 
                                                    value={item.confidence_score * 100} 
                                                    size={24} 
                                                    thickness={6}
                                                    color={item.confidence_score > 0.8 ? "success" : item.confidence_score > 0.5 ? "warning" : "error"}
                                                />
                                                <Box sx={{ position: 'absolute', top: 0, left: 0, bottom: 0, right: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                                    <Typography variant="caption" sx={{ fontSize: '0.55rem', fontWeight: 800 }}>
                                                        {Math.round(item.confidence_score * 100)}
                                                    </Typography>
                                                </Box>
                                            </Box>
                                        </TableCell>
                                    )}
                                    <TableCell align="right">
                                        <Stack direction="row" alignItems="center" justifyContent="flex-end" spacing={1}>
                                            {onSelectCode && (
                                                <Tooltip title="Sélectionner pour la règle">
                                                    <IconButton 
                                                        size="small" 
                                                        color="primary" 
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            onSelectCode(item);
                                                        }}
                                                        sx={{ border: '1px solid', borderColor: 'primary.light', bgcolor: 'primary.contrastText' }}
                                                    >
                                                        <CheckCircle size={14} />
                                                    </IconButton>
                                                </Tooltip>
                                            )}
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                                <Clock size={12} color={theme.palette.text.disabled} />
                                                <Typography variant="caption" color="text.secondary" suppressHydrationWarning>
                                                    {item.last_seen ? format(new Date(item.last_seen), 'dd/MM/yyyy') : '-'}
                                                </Typography>
                                            </Box>
                                        </Stack>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>

            {/* PAGINATION & FOOTER */}
            <Box sx={{ mt: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <TablePagination
                    component="div"
                    count={total}
                    page={page}
                    onPageChange={handleChangePage}
                    rowsPerPage={rowsPerPage}
                    onRowsPerPageChange={handleChangeRowsPerPage}
                    rowsPerPageOptions={[50, 100, 200, 500]}
                    labelRowsPerPage="Par page"
                    labelDisplayedRows={({ from, to, count }) => `${from}-${to} sur ${count !== -1 ? count : `plus de ${to}`}`}
                    sx={{ border: 'none', '.MuiTablePagination-selectLabel, .MuiTablePagination-displayedRows': { fontSize: '0.75rem', color: 'text.secondary' } }}
                />
                <Stack direction="row" spacing={1} alignItems="center" sx={{ pr: 2 }}>
                    {loading && <CircularProgress size={12} thickness={5} />}
                    <Activity size={12} color={theme.palette.success.main} />
                    <Typography variant="caption" color="success.main" fontWeight={600}>
                        Catalogue de Vérité V4
                    </Typography>
                </Stack>
            </Box>

            {/* DRILLDOWN DRAWER */}
            <Drawer
                anchor="right"
                open={!!selectedCode}
                onClose={() => {
                    setSelectedCode(null);
                    setVariants([]);
                }}
                PaperProps={{ sx: { width: { xs: '100%', sm: 550 }, p: 0 } }}
            >
                <Box sx={{ p: 4, height: '100%', display: 'flex', flexDirection: 'column' }}>
                    <Box sx={{ mb: 3 }}>
                        <Typography variant="h6" fontWeight={800} gutterBottom>
                            Variantes et Analyse des Tokens pour le Code {selectedCode}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Analyse de la distribution des mots et détail des messages bruts.
                        </Typography>
                    </Box>
                    
                    <Divider sx={{ mb: 3 }} />
                    
                    {loadingVariants ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
                            <CircularProgress size={40} />
                        </Box>
                    ) : (
                        <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
                            {/* TOKEN STATS SECTION */}
                            {items.find(i => i.code === selectedCode)?.token_stats && (
                                <Box sx={{ mb: 4 }}>
                                    <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <Layers size={16} color={theme.palette.primary.main} /> Distribution des Tokens (Mots-clés)
                                    </Typography>
                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                                        {items.find(i => i.code === selectedCode).token_stats.map((ts: any, i: number) => (
                                            <Tooltip key={ts.token} title={`${ts.count} occurrences (${Math.round(ts.percentage * 100)}%)`}>
                                                <Chip
                                                    label={`${ts.token} (${Math.round(ts.percentage * 100)}%)`}
                                                    variant="outlined"
                                                    size="small"
                                                    color={ts.percentage >= invariance ? "primary" : "default"}
                                                    sx={{ 
                                                        fontWeight: ts.percentage >= invariance ? 700 : 400,
                                                        borderWidth: ts.percentage >= invariance ? 2 : 1,
                                                        bgcolor: ts.percentage >= invariance ? `${theme.palette.primary.main}11` : 'transparent'
                                                    }}
                                                />
                                            </Tooltip>
                                        ))}
                                    </Box>
                                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block', fontStyle: 'italic' }}>
                                        En bleu : Tokens retenus dans le label canonique (seuil à {Math.round(invariance * 100)}%).
                                    </Typography>
                                </Box>
                            )}

                            <Divider sx={{ mb: 3 }} />

                            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                                <ListIcon size={16} color={theme.palette.primary.main} /> Messages Réels (Variantes)
                            </Typography>
                            <List>
                                {variants.map((v, i) => (
                                    <Box key={i}>
                                        <ListItem 
                                            sx={{ 
                                                px: 0, 
                                                py: 2, 
                                                display: 'flex', 
                                                flexDirection: 'column', 
                                                alignItems: 'flex-start' 
                                            }}
                                        >
                                            <Typography variant="body2" fontWeight={600}>
                                                {v.message}
                                            </Typography>
                                            <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
                                                <Chip 
                                                    label={`${v.occurrences} occurrences`} 
                                                    size="small" 
                                                    variant="outlined" 
                                                    sx={{ fontSize: '0.65rem', height: 20 }}
                                                />
                                                <Typography variant="caption" color="text.disabled">
                                                    Vu le : {v.last_seen ? format(new Date(v.last_seen), 'dd/MM/yyyy HH:mm') : '-'}
                                                </Typography>
                                            </Stack>
                                        </ListItem>
                                        <Divider />
                                    </Box>
                                ))}
                            </List>
                        </Box>
                    )}
                    
                    <Box sx={{ mt: 'auto', pt: 2 }}>
                        <Alert icon={<Info size={16} />} severity="info" sx={{ '& .MuiAlert-message': { fontSize: '0.75rem' } }}>
                            Le label canonique est construit par extraction des tokens (mots) dont la fréquence d'apparition dépasse le seuil d'invariance sélectionné.
                        </Alert>
                    </Box>
                </Box>
            </Drawer>
        </Paper>
    );
}
